
LAYER_UNIFILAR = "PROJ_ELETRICA_UNIFILAR_QDC"
LAYER_UNIFILAR_TEXTO = "PROJ_ELETRICA_UNIFILAR_QDC_TEXTO"
LAYER_UNIFILAR_GUIA = "PROJ_ELETRICA_UNIFILAR_QDC_GUIA"


def _line(msp, p1, p2, layer=LAYER_UNIFILAR):
    msp.add_line(
        p1,
        p2,
        dxfattribs={"layer": layer}
    )


def _rect(msp, x1, y1, x2, y2, layer=LAYER_UNIFILAR):
    msp.add_lwpolyline(
        [
            (x1, y1),
            (x2, y1),
            (x2, y2),
            (x1, y2),
            (x1, y1)
        ],
        dxfattribs={"layer": layer}
    )


def _text(msp, text, x, y, h=0.15, layer=LAYER_UNIFILAR_TEXTO):
    if text is None:
        return

    texto = str(text).strip()

    if not texto:
        return

    msp.add_text(
        texto,
        dxfattribs={
            "layer": layer,
            "height": h,
            "insert": (x, y)
        }
    )


def _breaker(msp, x, y, w=0.58, h=0.34):
    _rect(
        msp,
        x - w / 2,
        y - h / 2,
        x + w / 2,
        y + h / 2
    )

    _line(
        msp,
        (
            x - w * 0.32,
            y - h * 0.28
        ),
        (
            x + w * 0.32,
            y + h * 0.28
        )
    )


def _dps(msp, x, y):
    _rect(
        msp,
        x - 0.32,
        y - 0.24,
        x + 0.32,
        y + 0.24
    )

    _line(
        msp,
        (x, y - 0.24),
        (x, y + 0.24)
    )

    _text(
        msp,
        "DPS",
        x - 0.16,
        y + 0.33,
        0.10
    )


def _dr(msp, x, y, titulo, nominal=None, sensibilidade=None):
    _rect(
        msp,
        x - 0.40,
        y - 0.42,
        x + 0.40,
        y + 0.42
    )

    _text(
        msp,
        titulo,
        x - 0.18,
        y + 0.15,
        0.12
    )

    if nominal is not None:
        _text(
            msp,
            f"{int(nominal)} A",
            x - 0.18,
            y - 0.05,
            0.095
        )

    if sensibilidade is not None:
        _text(
            msp,
            f"{int(sensibilidade)} mA",
            x - 0.18,
            y - 0.22,
            0.095
        )


def _cabo_texto(c):
    try:
        bit = float(
            c.get(
                "bitola",
                0
            )
            or 0
        )
    except Exception:
        bit = 0

    if bit <= 0:
        return ""

    tipo = str(
        c.get(
            "tipo",
            ""
        )
    ).upper()

    if tipo == "TUE":
        return f"2F x {bit:g} + PE {bit:g} mm2"

    return f"F+N x {bit:g} + PE {bit:g} mm2"


def _texto_circuito(c):
    numero = int(
        c.get(
            "numero",
            0
        )
        or 0
    )

    tipo = str(
        c.get(
            "tipo",
            "Circuito"
        )
    )

    ambiente = str(
        c.get(
            "ambiente",
            ""
        )
    )

    fase = str(
        c.get(
            "fase",
            ""
        )
        or ""
    ).strip()

    partes = [
        f"C{numero:02d}",
        tipo,
        ambiente
    ]

    if (
        fase
        and fase != "A definir"
    ):
        partes.append(
            f"FASE {fase}"
        )

    return " | ".join(
        partes
    )


def _linha_circuito(
    msp,
    c,
    x_bus,
    x_cabo_fim,
    x_dj,
    x_info,
    x_saida,
    x_n,
    x_pe,
    y
):
    tipo = str(
        c.get(
            "tipo",
            "Circuito"
        )
    )

    try:
        pot = float(
            c.get(
                "potencia",
                0
            )
            or 0
        )
    except Exception:
        pot = 0

    try:
        corrente = float(
            c.get(
                "corrente",
                0
            )
            or 0
        )
    except Exception:
        corrente = 0

    try:
        dj = int(
            c.get(
                "disjuntor",
                0
            )
            or 0
        )
    except Exception:
        dj = 0

    polos = str(
        c.get(
            "polos",
            ""
        )
        or ""
    ).strip()

    # Barramento do grupo -> trecho reservado ao cabo.
    _line(
        msp,
        (x_bus, y),
        (x_cabo_fim, y)
    )

    cabo = _cabo_texto(
        c
    )

    if cabo:
        _text(
            msp,
            cabo,
            x_bus + 0.18,
            y + 0.12,
            0.072
        )

    # Pequeno trecho em branco antes do DJ.
    _line(
        msp,
        (x_cabo_fim, y),
        (x_dj - 0.31, y)
    )

    # Disjuntor do circuito.
    _breaker(
        msp,
        x_dj,
        y
    )

    if dj > 0:
        texto_dj = (
            f"DJ {dj} A"
        )

        if (
            polos
            and polos != "A definir"
        ):
            texto_dj += (
                f" {polos}"
            )

        _text(
            msp,
            texto_dj,
            x_dj - 0.29,
            y - 0.31,
            0.078
        )

    # DJ -> identificação do circuito.
    _line(
        msp,
        (x_dj + 0.29, y),
        (x_info - 0.12, y)
    )

    _text(
        msp,
        _texto_circuito(
            c
        ),
        x_info,
        y + 0.10,
        0.108
    )

    tensao = c.get("tensao")

    dados = f"{pot:.0f} W"
    if tensao is not None:
        try:
            dados += f" | {float(tensao):g} V"
        except Exception:
            pass
    dados += f" | {corrente:.2f} A"

    _text(
        msp,
        dados,
        x_info,
        y - 0.15,
        0.084
    )

    # Linha funcional até os barramentos N e PE.
    _line(
        msp,
        (
            x_info,
            y - 0.02
        ),
        (
            x_saida,
            y - 0.02
        )
    )

    # Conexão até N e PE.
    _line(
        msp,
        (x_saida, y - 0.02),
        (x_n, y - 0.02)
    )

    _line(
        msp,
        (x_n, y - 0.02),
        (x_pe, y - 0.02)
    )

    # Marcas de ligação.
    msp.add_circle(
        (x_n, y - 0.02),
        radius=0.055,
        dxfattribs={
            "layer": LAYER_UNIFILAR
        }
    )

    msp.add_circle(
        (x_pe, y - 0.02),
        radius=0.055,
        dxfattribs={
            "layer": LAYER_UNIFILAR
        }
    )


def _legenda(
    msp,
    x1,
    y1,
    x2,
    y2
):
    _rect(
        msp,
        x1,
        y1,
        x2,
        y2
    )

    _text(
        msp,
        "LEGENDA",
        x1 + 0.22,
        y2 - 0.28,
        0.105
    )

    # Duas linhas: evita que quatro definições disputem a mesma faixa.
    y_a = y2 - 0.72
    y_b = y2 - 1.25

    _breaker(
        msp,
        x1 + 0.42,
        y_a,
        w=0.34,
        h=0.22
    )
    _text(
        msp,
        "DG / DJ - DISJUNTOR TERMOMAGNETICO",
        x1 + 0.72,
        y_a - 0.03,
        0.065
    )

    _dps(
        msp,
        x1 + 6.15,
        y_a
    )
    _text(
        msp,
        "DPS - PROTECAO CONTRA SURTOS",
        x1 + 6.60,
        y_a - 0.03,
        0.065
    )

    _rect(
        msp,
        x1 + 0.25,
        y_b - 0.17,
        x1 + 0.59,
        y_b + 0.17
    )
    _text(
        msp,
        "DR - DIFERENCIAL RESIDUAL",
        x1 + 0.72,
        y_b - 0.03,
        0.065
    )

    _text(
        msp,
        "N - NEUTRO   |   PE - PROTECAO / TERRA",
        x1 + 6.15,
        y_b - 0.03,
        0.065
    )


def _notas(
    msp,
    x1,
    y1,
    x2,
    y2,
    parametros_rede,
    resumo_protecao
):
    _rect(
        msp,
        x1,
        y1,
        x2,
        y2
    )

    _text(
        msp,
        "NOTAS",
        x1 + 0.22,
        y2 - 0.28,
        0.105
    )

    tipo = str(
        parametros_rede.get(
            "tipo_fornecimento",
            ""
        )
        or ""
    ).strip()

    tensao = str(
        parametros_rede.get(
            "tensao_fornecimento",
            ""
        )
        or ""
    ).strip()

    linhas = []

    if tipo:
        linhas.append(
            f"FORNECIMENTO: {tipo}"
        )

    if tensao:
        linhas.append(
            f"TENSAO: {tensao}"
        )

    linhas.extend([
        "N: NEUTRO",
        "PE: PROTECAO / TERRA",
        "SELETIVIDADE: VALIDAR POR CURVAS/TABELAS DO FABRICANTE",
        "CAP. INTERRUPCAO: DEFINIR PELO ICC E FABRICANTE"
    ])

    # Cada nota ocupa sua própria linha. Nada é concatenado lateralmente.
    y = y2 - 0.67
    for texto in linhas:
        _text(
            msp,
            texto,
            x1 + 0.25,
            y,
            0.061
        )
        y -= 0.25


def desenhar_unifilar_qdc(
    msp,
    circuitos,
    polilinhas_ambientes,
    tensao_projeto=220,
    parametros_rede=None,
    resultado_demanda=None,
    resumo_balanceamento=None,
    resumo_drs=None,
    resumo_protecao=None
):
    circuitos = list(
        circuitos
        or []
    )

    if not circuitos:
        return None

    parametros_rede = dict(
        parametros_rede
        or {}
    )

    resultado_demanda = dict(
        resultado_demanda
        or {}
    )

    resumo_balanceamento = dict(
        resumo_balanceamento
        or {}
    )

    resumo_drs = list(
        resumo_drs
        or []
    )

    resumo_protecao = dict(
        resumo_protecao
        or {}
    )

    # ========================================================
    # EXTENSÃO DA PLANTA
    # ========================================================

    pontos = []

    for pol in (
        polilinhas_ambientes
        or []
    ):
        pontos.extend(
            list(
                pol
                or []
            )
        )

    max_x = max(
        (
            p[0]
            for p in pontos
        ),
        default=0.0
    )

    max_y = max(
        (
            p[1]
            for p in pontos
        ),
        default=10.0
    )

    # ========================================================
    # AGRUPAMENTO
    # ========================================================

    grupos = {}
    sem_dr = []

    for c in circuitos:
        dr = str(
            c.get(
                "dr",
                ""
            )
            or ""
        ).strip()

        if dr:
            grupos.setdefault(
                dr,
                []
            ).append(
                c
            )
        else:
            sem_dr.append(
                c
            )

    resumo_por_id = {
        str(
            g.get(
                "dr",
                ""
            )
        ): g
        for g in resumo_drs
    }

    ordem_drs = []

    for g in resumo_drs:
        gid = str(
            g.get(
                "dr",
                ""
            )
            or ""
        ).strip()

        if (
            gid
            and gid not in ordem_drs
        ):
            ordem_drs.append(
                gid
            )

    for gid in grupos:
        if gid not in ordem_drs:
            ordem_drs.append(
                gid
            )

    secoes = []

    for gid in ordem_drs:
        itens = grupos.get(
            gid,
            []
        )

        if itens:
            secoes.append({
                "id": gid,
                "titulo": gid,
                "itens": itens,
                "resumo": resumo_por_id.get(
                    gid,
                    {}
                ),
                "com_dr": True
            })

    if sem_dr:
        secoes.append({
            "id": "SEM_DR",
            "titulo": "CIRCUITOS SEM DR",
            "itens": sem_dr,
            "resumo": {},
            "com_dr": False
        })

    # ========================================================
    # DIMENSIONAMENTO DO QUADRO
    # ========================================================

    # Colunas fixas: garantem alinhamento de projeto para projeto.
    x0 = max_x + 3.0
    y0 = max_y

    margem_esq = 0.45
    margem_dir = 0.45

    largura = 20.2

    x_rede = x0 + 1.20
    x_main = x0 + 3.55
    x_dr = x0 + 5.05
    x_bus = x0 + 6.05
    x_cabo_fim = x0 + 8.25
    x_dj = x0 + 8.95
    x_info = x0 + 9.85
    x_saida = x0 + 16.35

    # N/PE calculados com o mesmo "respiro" visual da esquerda.
    # O primeiro barramento N fica próximo ao fim da coluna de identificação,
    # em vez de preso à borda direita do quadro.
    x_n = x0 + 17.05
    x_pe = x0 + 17.75

    # A moldura termina com respiro curto após PE.
    x2 = x0 + largura

    titulo_h = 1.65
    entrada_h = 2.25
    sec_header = 1.30
    circ_pitch = 1.02
    gap_sec = 0.78
    rodape_h = 3.35

    corpo_h = 0.0

    for sec in secoes:
        corpo_h += (
            sec_header
            +
            len(
                sec["itens"]
            )
            * circ_pitch
            +
            gap_sec
        )

    altura = max(
        12.0,
        titulo_h
        +
        entrada_h
        +
        corpo_h
        +
        rodape_h
        +
        0.90
    )

    ybase = y0 - altura

    # Moldura principal.
    _rect(
        msp,
        x0,
        ybase,
        x2,
        y0
    )

    # ========================================================
    # CABEÇALHO
    # ========================================================

    _text(
        msp,
        "QDC - QUADRO DE DISTRIBUICAO DE CIRCUITOS",
        x0 + 4.65,
        y0 - 0.42,
        0.24
    )

    linha_fase = "FASE 11.1"

    tipo_for = str(
        parametros_rede.get(
            "tipo_fornecimento",
            ""
        )
        or ""
    )

    tensao_for = str(
        parametros_rede.get(
            "tensao_fornecimento",
            ""
        )
        or ""
    )

    if tipo_for:
        linha_fase += (
            f" | {tipo_for}"
        )

    if tensao_for:
        linha_fase += (
            f" | {tensao_for}"
        )

    _text(
        msp,
        linha_fase,
        x0 + 4.55,
        y0 - 0.78,
        0.105
    )

    cargas = resumo_balanceamento.get(
        "fases",
        {}
    )

    if cargas:
        texto_cargas = " | ".join(
            (
                f"{fase}: "
                f"{pot / 1000:.2f} kW"
            )
            for fase, pot
            in cargas.items()
        )

        _text(
            msp,
            f"BALANCEAMENTO | {texto_cargas}",
            x0 + 4.55,
            y0 - 1.06,
            0.095
        )

    # ========================================================
    # COLUNA REDE / ENTRADA
    # ========================================================

    y_entrada = y0 - titulo_h - 0.55

    _text(
        msp,
        "REDE",
        x_rede - 0.16,
        y_entrada + 0.48,
        0.12
    )

    # Entrada horizontal limpa, como no modelo de referência.
    _line(
        msp,
        (
            x_rede - 0.35,
            y_entrada
        ),
        (
            x_main - 1.00,
            y_entrada
        )
    )

    # DG.
    x_dg = x_main - 0.55

    _breaker(
        msp,
        x_dg,
        y_entrada
    )

    _text(
        msp,
        "DG",
        x_dg - 0.10,
        y_entrada + 0.38,
        0.11
    )

    dg = resultado_demanda.get(
        "disjuntor_geral_a"
    )

    polos_dg = str(
        resumo_protecao.get(
            "dg_polos",
            ""
        )
        or ""
    )

    if dg is not None:
        txt = (
            f"{int(dg)} A"
        )

        if polos_dg:
            txt += (
                f" {polos_dg}"
            )

        _text(
            msp,
            txt,
            x_dg - 0.22,
            y_entrada - 0.36,
            0.090
        )

    # DG -> DPS.
    _line(
        msp,
        (
            x_dg + 0.29,
            y_entrada
        ),
        (
            x_main + 0.20,
            y_entrada
        )
    )

    x_dps = x_main + 0.55

    _dps(
        msp,
        x_dps,
        y_entrada
    )

    # DPS -> barramento principal.
    _line(
        msp,
        (
            x_dps + 0.32,
            y_entrada
        ),
        (
            x_main + 1.05,
            y_entrada
        )
    )

    x_barra_principal = x_main + 1.05

    # Alimentador em bloco próprio.
    _rect(
        msp,
        x0 + 0.45,
        y_entrada - 2.05,
        x0 + 2.60,
        y_entrada - 0.65
    )

    _text(
        msp,
        "ALIMENTADOR GERAL",
        x0 + 0.72,
        y_entrada - 0.92,
        0.11
    )

    sf = resumo_protecao.get(
        "alimentador_fase_mm2"
    )

    sn = resumo_protecao.get(
        "alimentador_neutro_mm2"
    )

    spe = resumo_protecao.get(
        "alimentador_pe_mm2"
    )

    comp = str(
        resumo_protecao.get(
            "alimentador_composicao",
            ""
        )
        or ""
    )

    if comp:
        _text(
            msp,
            comp,
            x0 + 0.72,
            y_entrada - 1.20,
            0.085
        )

    if sf is not None:
        _text(
            msp,
            f"F: {sf:g} mm2",
            x0 + 0.72,
            y_entrada - 1.43,
            0.085
        )

    if sn is not None:
        _text(
            msp,
            f"N: {sn:g} mm2",
            x0 + 0.72,
            y_entrada - 1.64,
            0.085
        )

    if spe is not None:
        _text(
            msp,
            f"PE: {spe:g} mm2",
            x0 + 0.72,
            y_entrada - 1.85,
            0.085
        )

    # ========================================================
    # BARRAMENTO PRINCIPAL E SEÇÕES
    # ========================================================

    y_sec = y_entrada - 0.95

    # Calcula última coordenada antes de desenhar barramento.
    total_corpo = 0.0

    for sec in secoes:
        total_corpo += (
            sec_header
            +
            len(
                sec["itens"]
            )
            * circ_pitch
            +
            gap_sec
        )

    y_fim_barra = (
        y_sec
        -
        total_corpo
        +
        gap_sec
        +
        0.18
    )

    _line(
        msp,
        (
            x_barra_principal,
            y_entrada
        ),
        (
            x_barra_principal,
            y_fim_barra
        )
    )

    for sec in secoes:
        # Cabeçalho da seção.
        y_header = y_sec

        _line(
            msp,
            (
                x_barra_principal,
                y_header
            ),
            (
                x_dr - 0.45,
                y_header
            )
        )

        if sec["com_dr"]:
            resumo = sec["resumo"]

            _dr(
                msp,
                x_dr,
                y_header,
                sec["titulo"],
                resumo.get(
                    "corrente_nominal_a"
                ),
                resumo.get(
                    "sensibilidade_ma"
                )
            )

            _line(
                msp,
                (
                    x_dr + 0.40,
                    y_header
                ),
                (
                    x_bus,
                    y_header
                )
            )

        else:
            # Circuitos sem DR: cabeçalho simples, sem caixa atravessada
            # por barramentos/linhas. A derivação sai diretamente do
            # barramento principal para o barramento do grupo.
            _text(
                msp,
                "CIRCUITOS SEM DR",
                x_dr - 0.45,
                y_header + 0.12,
                0.105
            )

            _line(
                msp,
                (
                    x_dr - 0.45,
                    y_header - 0.10
                ),
                (
                    x_dr + 1.45,
                    y_header - 0.10
                )
            )

            _line(
                msp,
                (
                    x_barra_principal,
                    y_header
                ),
                (
                    x_bus,
                    y_header
                )
            )

        # Barramento próprio do grupo.
        first_y = (
            y_header
            -
            sec_header
        )

        last_y = (
            first_y
            -
            (
                len(
                    sec["itens"]
                )
                - 1
            )
            *
            circ_pitch
        )

        _line(
            msp,
            (
                x_bus,
                y_header
            ),
            (
                x_bus,
                last_y
            )
        )

        # Circuitos.
        for i, c in enumerate(
            sec["itens"]
        ):
            cy = (
                first_y
                -
                i
                *
                circ_pitch
            )

            _linha_circuito(
                msp,
                c,
                x_bus,
                x_cabo_fim,
                x_dj,
                x_info,
                x_saida,
                x_n,
                x_pe,
                cy
            )

        y_sec = (
            last_y
            -
            gap_sec
            -
            0.35
        )

    # ========================================================
    # BARRAMENTOS N E PE
    # ========================================================

    y_bus_top = (
        y_entrada
        +
        0.62
    )

    y_bus_bottom = (
        ybase
        +
        rodape_h
        +
        0.50
    )

    # N e PE próximos ao conteúdo, com espaçamento curto e regular.
    _rect(
        msp,
        x_n - 0.08,
        y_bus_bottom,
        x_n + 0.08,
        y_bus_top
    )

    _rect(
        msp,
        x_pe - 0.08,
        y_bus_bottom,
        x_pe + 0.08,
        y_bus_top
    )

    _text(
        msp,
        "N",
        x_n - 0.05,
        y_bus_top + 0.18,
        0.12
    )

    _text(
        msp,
        "PE",
        x_pe - 0.08,
        y_bus_top + 0.18,
        0.12
    )

    # ========================================================
    # RODAPÉ
    # ========================================================

    y_rodape_top = (
        ybase
        +
        rodape_h
        -
        0.10
    )

    legenda_x1 = x0 + 0.25
    legenda_x2 = x0 + 12.75

    notas_x1 = x0 + 13.00
    notas_x2 = x2 - 0.25

    _legenda(
        msp,
        legenda_x1,
        ybase + 0.25,
        legenda_x2,
        y_rodape_top
    )

    _notas(
        msp,
        notas_x1,
        ybase + 0.25,
        notas_x2,
        y_rodape_top,
        parametros_rede,
        resumo_protecao
    )

    return {
        "quantidade_circuitos":
            len(
                circuitos
            ),
        "quantidade_drs":
            len(
                [
                    s
                    for s in secoes
                    if s["com_dr"]
                ]
            ),
        "quantidade_secoes":
            len(
                secoes
            ),
        "origem":
            (
                x0,
                ybase
            ),
        "largura":
            largura,
        "altura":
            altura,
        "barramento_n_x":
            x_n,
        "barramento_pe_x":
            x_pe
    }
