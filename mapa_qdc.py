import math

TAMANHOS_PADRAO_QDC = (8, 12, 16, 18, 24, 36, 48, 54, 72)
RESERVA_MINIMA_MODULOS = 4
RESERVA_FRACAO = 0.20


def _polos_numero(valor, padrao=1):
    txt = str(valor or "").upper().strip()
    dig = "".join(ch for ch in txt if ch.isdigit())
    try:
        return max(1, int(dig))
    except Exception:
        return max(1, int(padrao))


def _polos_circuito(c):
    if c.get("polos"):
        return _polos_numero(c.get("polos"), 1)

    tensao = float(c.get("tensao", 0) or 0)
    tipo = str(c.get("tipo", "") or "").upper()

    if tipo == "TUE" or tensao > 127.5:
        return 2
    return 1


def _shape_qdc(posicoes):
    posicoes = int(posicoes or 0)
    shapes = {
        8: (1, 8),
        12: (1, 12),
        16: (2, 8),
        18: (2, 9),
        24: (2, 12),
        36: (3, 12),
        48: (4, 12),
        54: (3, 18),
        72: (4, 18),
    }
    if posicoes in shapes:
        return shapes[posicoes]

    if posicoes <= 12:
        return 1, max(1, posicoes)
    if posicoes <= 24:
        return 2, int(math.ceil(posicoes / 2))
    if posicoes <= 48:
        return int(math.ceil(posicoes / 12)), 12
    return int(math.ceil(posicoes / 18)), 18


def _proximo_qdc(necessidade):
    necessidade = max(1, int(necessidade))
    for tam in TAMANHOS_PADRAO_QDC:
        if tam >= necessidade:
            return tam
    return int(math.ceil(necessidade / 12.0) * 12)


def _qtd_dps(resumo_protecao, dg_polos):
    comp = str(
        (resumo_protecao or {}).get(
            "alimentador_composicao",
            ""
        )
        or ""
    )
    if "3F" in comp:
        return 3
    if "2F" in comp:
        return 2
    if comp.startswith("F") or "F +" in comp:
        return 1
    return max(0, int(dg_polos or 0))


def _polos_dr(dr, circuitos_por_numero):
    numeros = [
        int(n or 0)
        for n in (dr.get("circuitos", []) or [])
        if int(n or 0) > 0
    ]
    maior = max(
        (
            _polos_circuito(circuitos_por_numero[n])
            for n in numeros
            if n in circuitos_por_numero
        ),
        default=1
    )
    return 2 if maior <= 2 else maior


def _dispositivos_base(
    circuitos,
    resumo_drs,
    resumo_protecao,
    resultado_demanda
):
    """
    Fase 13.4 Rev.8:
    organiza os dispositivos para uma vista frontal convencional:
    proteção geral/IDRs/DPS na fileira superior e disjuntores dos
    circuitos nas fileiras seguintes.
    """
    circuitos = [dict(c) for c in (circuitos or [])]
    resumo_drs = [dict(d) for d in (resumo_drs or [])]
    resumo_protecao = dict(resumo_protecao or {})
    resultado_demanda = dict(resultado_demanda or {})

    por_numero = {
        int(c.get("numero", 0) or 0): c
        for c in circuitos
        if int(c.get("numero", 0) or 0) > 0
    }

    protecoes_gerais = []
    disjuntores_circuitos = []

    dg_a = resultado_demanda.get("disjuntor_geral_a")
    dg_polos = _polos_numero(
        resumo_protecao.get("dg_polos", ""),
        2
    )

    if dg_a:
        protecoes_gerais.append({
            "tipo": "DG",
            "identificador": "DG",
            "descricao": f"Disjuntor geral {dg_polos}P {int(dg_a)} A",
            "modulos": dg_polos,
            "grupo": "GERAL",
            "fase": "",
            "circuitos": "",
            "ambiente": "",
            "corrente_a": int(dg_a),
        })

    qtd_dps = _qtd_dps(
        resumo_protecao,
        dg_polos if dg_a else 0
    )
    fases_dps = ["A", "B", "C"][:qtd_dps]
    for i in range(1, qtd_dps + 1):
        fase_dps = fases_dps[i - 1] if i - 1 < len(fases_dps) else "A"
        protecoes_gerais.append({
            "tipo": "DPS",
            "identificador": f"DPS{i}",
            "descricao": f"DPS 1P - Fase {fase_dps}",
            "modulos": 1,
            "grupo": "GERAL",
            "fase": fase_dps,
            "circuitos": "",
            "ambiente": "",
            "corrente_a": None,
        })

    # IDRs ficam juntos na fileira superior.
    for dr in resumo_drs:
        gid = str(dr.get("dr", "") or "").strip()
        if not gid:
            continue

        numeros = [
            int(n or 0)
            for n in (dr.get("circuitos", []) or [])
            if int(n or 0) > 0
        ]
        itens = [
            por_numero[n]
            for n in numeros
            if n in por_numero
        ]
        if not itens:
            continue

        polos_dr = _polos_dr(
            dr,
            por_numero
        )
        nominal = dr.get("corrente_nominal_a")
        sens = dr.get("sensibilidade_ma")

        descr = f"{gid} {polos_dr}P"
        if nominal:
            descr += f" {int(nominal)} A"
        if sens:
            descr += f" {int(sens)} mA"

        fases_grupo = []
        for item in itens:
            fase_item = str(item.get("fase", "") or "").upper().strip()
            for token in ("A", "B", "C"):
                if token in fase_item and token not in fases_grupo:
                    fases_grupo.append(token)

        protecoes_gerais.append({
            "tipo": "IDR",
            "identificador": gid,
            "descricao": descr,
            "modulos": polos_dr,
            "grupo": gid,
            "fase": "/".join(fases_grupo),
            "circuitos": ",".join(f"C{n:02d}" for n in numeros),
            "ambiente": str(dr.get("descricao", "") or ""),
            "corrente_a": int(nominal) if nominal else None,
            "sensibilidade_ma": int(sens) if sens else None,
        })

    # Disjuntores terminais sempre ordenados por número de circuito.
    for c in sorted(
        circuitos,
        key=lambda x: int(x.get("numero", 0) or 0)
    ):
        n = int(c.get("numero", 0) or 0)
        if n <= 0:
            continue

        polos = _polos_circuito(c)
        corrente = int(c.get("disjuntor", 0) or 0)
        fase = str(c.get("fase", "") or "")
        gid = str(c.get("dr", "") or "").strip() or "SEM DR"
        ambiente = str(c.get("ambiente", "") or "")
        tipo = str(c.get("tipo", "") or "")
        potencia = float(c.get("potencia", 0) or 0)

        disjuntores_circuitos.append({
            "tipo": "DJ",
            "identificador": f"C{n:02d}",
            "descricao": f"C{n:02d} {polos}P {corrente} A",
            "modulos": polos,
            "grupo": gid,
            "fase": fase,
            "circuitos": f"C{n:02d}",
            "ambiente": ambiente,
            "tipo_circuito": tipo,
            "potencia_w": potencia,
            "corrente_a": corrente,
            "nova_fileira_antes": False,
        })

    if disjuntores_circuitos:
        # Força o aspecto convencional da referência:
        # dispositivos gerais em cima, circuitos na(s) fileira(s) abaixo.
        disjuntores_circuitos[0]["nova_fileira_antes"] = True

    return protecoes_gerais + disjuntores_circuitos



def _tentar_alocar(dispositivos, posicoes):
    linhas, colunas = _shape_qdc(posicoes)
    slots = [
        {
            "posicao": i + 1,
            "linha": (i // colunas) + 1,
            "coluna": (i % colunas) + 1,
            "identificador": "LIVRE",
            "tipo": "RESERVA",
            "grupo": "RESERVA",
            "fase": "",
        }
        for i in range(linhas * colunas)
    ]

    dispositivos_alocados = []
    cursor = 0

    for disp in dispositivos:
        largura = max(1, int(disp.get("modulos", 1) or 1))

        if (
            disp.get("nova_fileira_antes")
            and cursor % colunas != 0
        ):
            cursor = (
                (cursor // colunas) + 1
            ) * colunas

        linha_atual = cursor // colunas
        coluna_atual = cursor % colunas

        if coluna_atual + largura > colunas:
            cursor = (linha_atual + 1) * colunas

        if cursor + largura > len(slots):
            return None

        inicio = cursor + 1
        fim = cursor + largura

        d = dict(disp)
        d["posicao_inicial"] = inicio
        d["posicao_final"] = fim
        d["linha"] = (cursor // colunas) + 1
        dispositivos_alocados.append(d)

        for k in range(largura):
            idx = cursor + k
            slots[idx].update({
                "identificador": disp.get("identificador", ""),
                "tipo": disp.get("tipo", ""),
                "grupo": disp.get("grupo", ""),
                "fase": disp.get("fase", ""),
            })

        cursor += largura

    return {
        "linhas": linhas,
        "colunas": colunas,
        "slots": slots,
        "dispositivos": dispositivos_alocados,
    }



def gerar_mapa_fisico_qdc(
    circuitos,
    resumo_drs,
    resumo_protecao,
    resultado_demanda,
    qdc_posicoes=None
):
    dispositivos = _dispositivos_base(
        circuitos,
        resumo_drs,
        resumo_protecao,
        resultado_demanda
    )

    modulos_dispositivos = sum(
        int(d.get("modulos", 0) or 0)
        for d in dispositivos
    )
    reserva_min = max(
        RESERVA_MINIMA_MODULOS,
        int(math.ceil(modulos_dispositivos * RESERVA_FRACAO))
    )

    necessidade = modulos_dispositivos + reserva_min
    posicoes = int(qdc_posicoes or 0)

    if posicoes < necessidade:
        posicoes = _proximo_qdc(necessidade)

    # Respeita quebra de linha sem dividir dispositivos.
    while True:
        layout = _tentar_alocar(
            dispositivos,
            posicoes
        )
        if layout is not None:
            break
        posicoes = _proximo_qdc(posicoes + 1)

    slots = layout["slots"]
    livres = sum(
        1
        for s in slots
        if s["tipo"] == "RESERVA"
    )

    resumo_protecao = dict(resumo_protecao or {})

    return {
        "status": "ok",
        "qdc_posicoes": posicoes,
        "linhas": layout["linhas"],
        "colunas": layout["colunas"],
        "modulos_dispositivos": modulos_dispositivos,
        "posicoes_livres": livres,
        "dispositivos": layout["dispositivos"],
        "slots": slots,
        "alimentador_composicao": resumo_protecao.get(
            "alimentador_composicao",
            ""
        ),
        "alimentador_fase_mm2": resumo_protecao.get(
            "alimentador_fase_mm2"
        ),
        "alimentador_neutro_mm2": resumo_protecao.get(
            "alimentador_neutro_mm2"
        ),
        "alimentador_pe_mm2": resumo_protecao.get(
            "alimentador_pe_mm2"
        ),
        "dg_polos": resumo_protecao.get(
            "dg_polos",
            ""
        ),
    }


def dataframe_slots(mapa):
    mapa = dict(mapa or {})
    linhas = int(mapa.get("linhas", 0) or 0)
    colunas = int(mapa.get("colunas", 0) or 0)
    slots = list(mapa.get("slots", []) or [])

    dados = []
    for linha in range(1, linhas + 1):
        row = {"Fileira": f"TRILHO {linha}"}
        for coluna in range(1, colunas + 1):
            slot = next(
                (
                    s
                    for s in slots
                    if int(s.get("linha", 0) or 0) == linha
                    and int(s.get("coluna", 0) or 0) == coluna
                ),
                None
            )
            if not slot:
                texto = "—"
            else:
                texto = str(slot.get("identificador", "LIVRE") or "LIVRE")
                fase = str(slot.get("fase", "") or "").strip()
                if fase and texto != "LIVRE":
                    texto += f" [{fase}]"
            row[f"P{((linha - 1) * colunas + coluna):02d}"] = texto
        dados.append(row)

    return dados


def _rect(msp, x1, y1, x2, y2, layer):
    return msp.add_lwpolyline(
        [
            (x1, y1),
            (x2, y1),
            (x2, y2),
            (x1, y2),
        ],
        close=True,
        dxfattribs={"layer": layer}
    )


def _line(msp, p1, p2, layer):
    return msp.add_line(
        p1,
        p2,
        dxfattribs={"layer": layer}
    )


def _polyline(msp, pontos, layer):
    return msp.add_lwpolyline(
        pontos,
        dxfattribs={"layer": layer}
    )


def _circle(msp, center, radius, layer):
    return msp.add_circle(
        center,
        radius,
        dxfattribs={"layer": layer}
    )


def _text(msp, texto, x, y, altura, layer):
    try:
        ent = msp.add_text(
            str(texto),
            dxfattribs={
                "layer": layer,
                "height": altura,
            }
        )
        ent.dxf.insert = (x, y)
        return ent
    except Exception:
        return None


def _texto_central(msp, texto, x1, x2, y, altura, layer):
    texto = str(texto or "")
    # Centralização aproximada, estável em TEXT CAD.
    largura_est = len(texto) * altura * 0.58
    x = (x1 + x2) / 2.0 - largura_est / 2.0
    return _text(msp, texto, x, y, altura, layer)


def _fases_do_texto(fase):
    texto = str(fase or "").upper()
    fases = []
    for token in ("A", "B", "C"):
        if token in texto:
            fases.append(token)
    return fases or ["A"]


def _layer_por_token(token):
    token = str(token or "A").upper()
    if token == "C":
        return "PROJ_ELETRICA_QDC_FASE_C"
    if token == "B":
        return "PROJ_ELETRICA_QDC_FASE_B"
    return "PROJ_ELETRICA_QDC_FASE_A"


def _layer_fase(fase):
    fase = str(fase or "").upper()
    if "C" in fase:
        return "PROJ_ELETRICA_QDC_FASE_C"
    if "B" in fase:
        return "PROJ_ELETRICA_QDC_FASE_B"
    return "PROJ_ELETRICA_QDC_FASE_A"


def _fases_alimentador(mapa):
    composicao = str(
        (mapa or {}).get(
            "alimentador_composicao",
            ""
        )
        or ""
    ).upper()

    if "3F" in composicao:
        return ["A", "B", "C"]
    if "2F" in composicao:
        return ["A", "B"]
    if "F" in composicao:
        return ["A"]
    return []


def _tem_neutro_alimentador(mapa):
    return "N" in str(
        (mapa or {}).get(
            "alimentador_composicao",
            ""
        )
        or ""
    ).upper()


def _tem_pe_alimentador(mapa):
    return "PE" in str(
        (mapa or {}).get(
            "alimentador_composicao",
            ""
        )
        or ""
    ).upper()


def _desenhar_trilho_segmento(msp, x1, x2, y, layer):
    if x2 <= x1:
        return
    _line(msp, (x1, y), (x2, y), layer)
    _line(msp, (x1, y - 0.08), (x2, y - 0.08), layer)

    passo = 0.34
    x = x1 + 0.18
    while x < x2 - 0.18:
        _line(
            msp,
            (x, y - 0.10),
            (min(x + 0.12, x2), y + 0.02),
            layer
        )
        x += passo


def _desenhar_trilho_com_vazios(
    msp,
    x1,
    x2,
    y,
    layer,
    geometrias
):
    """Desenha o trilho somente nas áreas externas aos aparelhos."""
    intervalos = sorted(
        [
            (
                float(g.get("x1", 0)) - 0.04,
                float(g.get("x2", 0)) + 0.04,
            )
            for g in (geometrias or [])
        ]
    )

    cursor = x1
    for a, b in intervalos:
        a = max(x1, a)
        b = min(x2, b)
        if a > cursor:
            _desenhar_trilho_segmento(
                msp,
                cursor,
                a,
                y,
                layer
            )
        cursor = max(cursor, b)

    if cursor < x2:
        _desenhar_trilho_segmento(
            msp,
            cursor,
            x2,
            y,
            layer
        )



def _desenhar_borne(msp, x, y, layer):
    _circle(msp, (x, y), 0.095, layer)
    _line(msp, (x - 0.045, y), (x + 0.045, y), layer)
    _line(msp, (x, y - 0.045), (x, y + 0.045), layer)


def _desenhar_barramento_vertical(
    msp,
    x,
    y_top,
    quantidade,
    layer,
    titulo,
    layer_txt
):
    espac = 0.34
    altura = max(0.9, quantidade * espac + 0.20)
    y_bottom = y_top - altura

    _rect(
        msp,
        x - 0.18,
        y_bottom,
        x + 0.18,
        y_top,
        layer
    )

    for i in range(quantidade):
        y = y_top - 0.18 - i * espac
        _desenhar_borne(
            msp,
            x,
            y,
            layer
        )

    _texto_central(
        msp,
        titulo,
        x - 0.55,
        x + 0.55,
        y_top + 0.25,
        0.12,
        layer_txt
    )

    return {
        "x": x,
        "y_top": y_top,
        "y_bottom": y_bottom,
        "bornes": quantidade,
    }


def _desenhar_dispositivo(
    msp,
    disp,
    x1,
    y1,
    modulo_w,
    altura,
    layer,
    layer_txt
):
    modulos = max(1, int(disp.get("modulos", 1) or 1))
    x2 = x1 + modulo_w * modulos
    y2 = y1 + altura

    _rect(
        msp,
        x1,
        y1,
        x2,
        y2,
        layer
    )

    # Bornes superior/inferior por polo/módulo.
    for i in range(modulos):
        cx = x1 + modulo_w * (i + 0.5)
        _desenhar_borne(
            msp,
            cx,
            y2 - 0.18,
            layer
        )
        _desenhar_borne(
            msp,
            cx,
            y1 + 0.18,
            layer
        )

    tipo = str(disp.get("tipo", "") or "")
    ident = str(disp.get("identificador", "") or "")
    corrente = disp.get("corrente_a")

    _texto_central(
        msp,
        ident,
        x1,
        x2,
        y1 + altura * 0.57,
        0.14 if tipo != "DJ" else 0.12,
        layer_txt
    )

    if corrente:
        _texto_central(
            msp,
            f"{int(corrente)}A",
            x1,
            x2,
            y1 + altura * 0.40,
            0.105,
            layer_txt
        )

    if tipo == "IDR" and disp.get("sensibilidade_ma"):
        _texto_central(
            msp,
            f"{int(disp.get('sensibilidade_ma'))}mA",
            x1,
            x2,
            y1 + altura * 0.27,
            0.083,
            layer_txt
        )

    if tipo in {"DG", "DJ"}:
        # Pequena alavanca.
        cx = (x1 + x2) / 2.0
        _rect(
            msp,
            cx - 0.11,
            y1 + altura * 0.29,
            cx + 0.11,
            y1 + altura * 0.36,
            layer
        )

    if tipo == "DPS":
        cx = (x1 + x2) / 2.0
        _rect(
            msp,
            cx - 0.09,
            y1 + altura * 0.30,
            cx + 0.09,
            y1 + altura * 0.36,
            layer
        )

    if tipo == "IDR":
        cx = (x1 + x2) / 2.0
        _circle(
            msp,
            (cx, y1 + altura * 0.33),
            0.075,
            layer
        )
        _text(
            msp,
            "T",
            cx - 0.025,
            y1 + altura * 0.305,
            0.055,
            layer_txt
        )

    return {
        "x1": x1,
        "x2": x2,
        "cx": (x1 + x2) / 2.0,
        "y1": y1,
        "y2": y2,
        "modulos": modulos,
        "tipo": tipo,
        "identificador": ident,
    }


def _quebrar_texto(texto, max_chars=27):
    palavras = str(texto or "").split()
    linhas = []
    atual = ""
    for palavra in palavras:
        teste = palavra if not atual else atual + " " + palavra
        if len(teste) <= max_chars:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas[:3]


def desenhar_mapa_fisico_qdc(
    msp,
    mapa,
    polilinhas_ambientes
):
    """
    Fase 13.4 Rev.8 — QDC executivo no CAD.

    O desenho passa a se aproximar de um diagrama de montagem real:
    trilhos DIN, dispositivos frontais, barramento pente, barramentos
    N/PE, condutores por função/fase e quadro lateral de circuitos.
    """
    mapa = dict(mapa or {})
    if mapa.get("status") != "ok":
        return None

    pontos = []
    for pol in polilinhas_ambientes or []:
        pontos.extend(list(pol or []))

    max_x = max((p[0] for p in pontos), default=0.0)
    max_y = max((p[1] for p in pontos), default=10.0)

    # Unifilar permanece à esquerda; vista frontal nasce à direita.
    x0 = max_x + 25.4
    y0 = max_y

    L = "PROJ_ELETRICA_MAPA_QDC"
    LT = "PROJ_ELETRICA_MAPA_QDC_TEXTO"
    LA = "PROJ_ELETRICA_QDC_FASE_A"
    LB = "PROJ_ELETRICA_QDC_FASE_B"
    LC = "PROJ_ELETRICA_QDC_FASE_C"
    LN = "PROJ_ELETRICA_QDC_NEUTRO"
    LPE = "PROJ_ELETRICA_QDC_PE"
    LP = "PROJ_ELETRICA_QDC_PENTE"

    dispositivos = list(mapa.get("dispositivos", []) or [])
    gerais = [d for d in dispositivos if d.get("tipo") in {"DG", "DPS", "IDR"}]
    circuitos = [d for d in dispositivos if d.get("tipo") == "DJ"]

    colunas = int(mapa.get("colunas", 0) or 0)
    linhas = int(mapa.get("linhas", 0) or 0)

    modulo_w = 0.78
    disp_h = 1.60
    margem_x = 1.15
    painel_circuitos_w = 10.20
    separacao_painel = 1.60
    area_din_w = max(9.6, colunas * modulo_w + 2.30)
    largura = (
        area_din_w
        + separacao_painel
        + painel_circuitos_w
        + 1.00
    )

    # Altura adaptativa por número de trilhos e circuitos.
    trilhos_circuitos = max(
        1,
        int(math.ceil(
            sum(int(d.get("modulos", 1) or 1) for d in circuitos)
            / max(1, colunas)
        ))
    )
    altura_corpo = 4.40 + trilhos_circuitos * 3.15
    altura = max(11.5, altura_corpo + 2.00)
    ybase = y0 - altura

    # Moldura geral e cabeçalho.
    _rect(
        msp,
        x0,
        ybase,
        x0 + largura,
        y0,
        L
    )

    _text(
        msp,
        "QDC - QUADRO DE DISTRIBUICAO DE CIRCUITOS",
        x0 + 0.55,
        y0 - 0.55,
        0.25,
        LT
    )
    _text(
        msp,
        "VISTA FRONTAL - DIAGRAMA DE MONTAGEM E LIGACOES | FASE 13.4 REV.8",
        x0 + 0.55,
        y0 - 0.92,
        0.11,
        LT
    )

    # Região frontal do quadro.
    qx1 = x0 + 0.55
    qx2 = x0 + area_din_w
    qy_top = y0 - 1.35
    qy_bottom = ybase + 0.75

    _rect(
        msp,
        qx1,
        qy_bottom,
        qx2,
        qy_top,
        L
    )

    # Barramentos PE e N laterais.
    qtd_pe = max(4, len(circuitos) + 1)
    qtd_n = max(
        4,
        sum(
            1
            for d in circuitos
            if int(d.get("modulos", 1) or 1) == 1
        ) + 1
    )

    pe = _desenhar_barramento_vertical(
        msp,
        qx1 + 0.48,
        qy_top - 1.15,
        qtd_pe,
        LPE,
        "PE",
        LT
    )
    neutro = _desenhar_barramento_vertical(
        msp,
        qx2 - 0.48,
        qy_top - 1.15,
        qtd_n,
        LN,
        "N",
        LT
    )

    din_x1 = qx1 + 1.15
    din_x2 = qx2 - 1.15

    # -------------------------
    # Fileira superior: DG/DPS/IDR
    # -------------------------
    top_rail_y = qy_top - 2.25
    x = din_x1 + 0.20
    geral_geom = []
    for d in gerais:
        w = modulo_w * max(1, int(d.get("modulos", 1) or 1))
        if x + w > din_x2 - 0.15:
            break

        geom = _desenhar_dispositivo(
            msp,
            d,
            x,
            top_rail_y - 0.85,
            modulo_w,
            disp_h,
            L,
            LT
        )
        geral_geom.append((d, geom))
        x = geom["x2"] + 0.12

    _desenhar_trilho_com_vazios(
        msp,
        din_x1,
        din_x2,
        top_rail_y - 0.05,
        L,
        [g for _, g in geral_geom]
    )

    # Entrada elétrica e distribuição superior por fase.
    dg_geoms = [
        (d, g)
        for d, g in geral_geom
        if d.get("tipo") == "DG"
    ]

    barramentos_y = {
        "A": top_rail_y + 1.22,
        "B": top_rail_y + 1.08,
        "C": top_rail_y + 0.94,
    }

    if dg_geoms:
        dg_disp, dg = dg_geoms[0]
        entrada_x = dg["cx"]

        fases_entrada = _fases_alimentador(
            mapa
        )

        espacamento_entrada = 0.16
        largura_fases = (
            max(
                0,
                len(fases_entrada) - 1
            )
            * espacamento_entrada
        )

        x_inicio_fases = (
            entrada_x
            - largura_fases / 2.0
        )

        # Somente a quantidade real de fases dimensionada pelo sistema.
        for idx_fase, token in enumerate(
            fases_entrada
        ):
            xx = (
                x_inicio_fases
                + idx_fase * espacamento_entrada
            )

            _line(
                msp,
                (xx, qy_top - 0.10),
                (xx, dg["y2"]),
                _layer_por_token(token)
            )

            _text(
                msp,
                f"L{idx_fase + 1}",
                xx - 0.045,
                qy_top - 0.30,
                0.075,
                LT
            )

        x_aux = (
            entrada_x
            + largura_fases / 2.0
            + 0.24
        )

        if _tem_neutro_alimentador(
            mapa
        ):
            _polyline(
                msp,
                [
                    (x_aux, qy_top - 0.10),
                    (x_aux, qy_top - 0.42),
                    (neutro["x"], qy_top - 0.42),
                    (neutro["x"], neutro["y_top"]),
                ],
                LN
            )

            _text(
                msp,
                "N",
                x_aux - 0.02,
                qy_top - 0.30,
                0.075,
                LT
            )

            x_aux += 0.20

        if _tem_pe_alimentador(
            mapa
        ):
            _polyline(
                msp,
                [
                    (x_aux, qy_top - 0.10),
                    (x_aux, qy_top - 0.58),
                    (pe["x"], qy_top - 0.58),
                    (pe["x"], pe["y_top"]),
                ],
                LPE
            )

            _text(
                msp,
                "PE",
                x_aux - 0.05,
                qy_top - 0.30,
                0.075,
                LT
            )

        bitola_fase = mapa.get(
            "alimentador_fase_mm2"
        )

        composicao_txt = str(
            mapa.get(
                "alimentador_composicao",
                ""
            )
            or ""
        )

        rotulo_entrada = (
            "ENTRADA DA REDE"
            + (
                f" | {composicao_txt}"
                if composicao_txt
                else ""
            )
            + (
                f" | FASE {float(bitola_fase):g} mm2"
                if bitola_fase
                else ""
            )
        )

        _text(
            msp,
            rotulo_entrada,
            din_x1,
            qy_top - 0.18,
            0.080,
            LT
        )

    if geral_geom:
        x_bus_ini = dg_geoms[0][1]["cx"] if dg_geoms else geral_geom[0][1]["cx"]
        x_bus_fim = geral_geom[-1][1]["cx"]

        fases_disponiveis = _fases_alimentador(
            mapa
        )

        for token in fases_disponiveis:
            _line(
                msp,
                (x_bus_ini, barramentos_y[token]),
                (x_bus_fim, barramentos_y[token]),
                _layer_por_token(token)
            )

        # DPS: fase -> DPS -> PE.
        for d, g in geral_geom:
            if d.get("tipo") != "DPS":
                continue
            token = _fases_do_texto(d.get("fase"))[0]
            _line(
                msp,
                (g["cx"], barramentos_y[token]),
                (g["cx"], g["y2"]),
                _layer_por_token(token)
            )
            _texto_central(
                msp,
                f"L{('A','B','C').index(token)+1}",
                g["x1"],
                g["x2"],
                g["y1"] - 0.13,
                0.065,
                LT
            )
            _polyline(
                msp,
                [
                    (g["cx"], g["y1"]),
                    (g["cx"], g["y1"] - 0.28),
                    (pe["x"], g["y1"] - 0.28),
                ],
                LPE
            )

        # IDRs: recebem as fases presentes no grupo e retorno ao neutro.
        for d, g in geral_geom:
            if d.get("tipo") != "IDR":
                continue

            fases = _fases_do_texto(d.get("fase"))
            largura = max(1, len(fases))

            for idx, token in enumerate(fases):
                xx = (
                    g["x1"]
                    + (idx + 0.5)
                    * (g["x2"] - g["x1"])
                    / largura
                )
                _line(
                    msp,
                    (xx, barramentos_y[token]),
                    (xx, g["y2"]),
                    _layer_por_token(token)
                )

            _polyline(
                msp,
                [
                    (g["x2"] - 0.12, g["y1"]),
                    (g["x2"] - 0.12, g["y1"] - 0.24),
                    (neutro["x"], g["y1"] - 0.24),
                ],
                LN
            )

    # -------------------------
    # Fileiras inferiores: circuitos
    # -------------------------
    y_rail = top_rail_y - 3.15
    idx_circ = 0
    circuitos_geom = []

    for trilho in range(trilhos_circuitos):
        x = din_x1 + 0.20
        usados = 0

        while idx_circ < len(circuitos):
            d = circuitos[idx_circ]
            mod = max(1, int(d.get("modulos", 1) or 1))

            if usados + mod > colunas:
                break

            geom = _desenhar_dispositivo(
                msp,
                d,
                x,
                y_rail - 0.85,
                modulo_w,
                disp_h,
                L,
                LT
            )
            circuitos_geom.append((d, geom))

            # Fase acima do disjuntor.
            fase = str(d.get("fase", "") or "").strip() or "A"
            _texto_central(
                msp,
                fase,
                geom["x1"],
                geom["x2"],
                geom["y2"] + 0.18,
                0.09,
                LT
            )


            # Guarda somente a informação elétrica necessária para
            # montar a saída do circuito fora do corpo do disjuntor.
            geom["tem_neutro"] = (
                mod == 1
            )

            x = geom["x2"] + 0.10
            usados += mod
            idx_circ += 1

        desta_fileira_geom = [
            g
            for d, g in circuitos_geom
            if abs(
                g["y1"]
                - (y_rail - 0.85)
            )
            < 0.05
        ]

        _desenhar_trilho_com_vazios(
            msp,
            din_x1,
            din_x2,
            y_rail - 0.05,
            L,
            desta_fileira_geom
        )

        # Neutro e PE não saem dos disjuntores.
        # Eles vêm diretamente dos respectivos barramentos laterais e seguem
        # em corredores inferiores até a saída física de cada circuito.
        if desta_fileira_geom:
            y_corredor_pe = (
                y_rail
                - 1.74
            )

            y_corredor_n = (
                y_rail
                - 1.92
            )

            y_saida_circuito = (
                y_rail
                - 2.28
            )

            x_esq_corredor = (
                min(
                    g["x1"]
                    for g in desta_fileira_geom
                )
                - 0.12
            )

            x_dir_corredor = (
                max(
                    g["x2"]
                    for g in desta_fileira_geom
                )
                + 0.12
            )

            # PE: barramento vertical -> corredor inferior.
            _polyline(
                msp,
                [
                    (pe["x"], pe["y_bottom"]),
                    (pe["x"], y_corredor_pe),
                    (x_dir_corredor, y_corredor_pe),
                ],
                LPE
            )

            # N: barramento vertical -> corredor inferior.
            _polyline(
                msp,
                [
                    (neutro["x"], neutro["y_bottom"]),
                    (neutro["x"], y_corredor_n),
                    (x_esq_corredor, y_corredor_n),
                ],
                LN
            )

            for d, g in circuitos_geom:
                if abs(
                    g["y1"]
                    - (y_rail - 0.85)
                ) >= 0.05:
                    continue

                fase = str(
                    d.get(
                        "fase",
                        ""
                    )
                    or ""
                ).strip() or "A"

                # Fase é o único condutor que sai do disjuntor.
                _line(
                    msp,
                    (
                        g["cx"],
                        g["y1"]
                    ),
                    (
                        g["cx"],
                        y_saida_circuito
                    ),
                    _layer_fase(
                        fase
                    )
                )

                # PE desce do barramento lateral/corredor para o circuito,
                # sem tocar no corpo do disjuntor.
                x_pe_saida = (
                    g["cx"]
                    - 0.10
                )

                _line(
                    msp,
                    (
                        x_pe_saida,
                        y_corredor_pe
                    ),
                    (
                        x_pe_saida,
                        y_saida_circuito
                    ),
                    LPE
                )

                # Neutro somente quando o circuito realmente o utiliza.
                if g.get(
                    "tem_neutro"
                ):
                    x_n_saida = (
                        g["cx"]
                        + 0.10
                    )

                    _line(
                        msp,
                        (
                            x_n_saida,
                            y_corredor_n
                        ),
                        (
                            x_n_saida,
                            y_saida_circuito
                        ),
                        LN
                    )

                # Código do circuito na saída; nenhum ambiente/descrição aqui.
                _texto_central(
                    msp,
                    str(
                        d.get(
                            "identificador",
                            ""
                        )
                    ),
                    g["x1"],
                    g["x2"],
                    y_saida_circuito - 0.22,
                    0.085,
                    LT
                )

        # Barramento dos circuitos segmentado por grupo de proteção.
        if circuitos_geom:
            desta_fileira = [
                (d, g)
                for d, g in circuitos_geom
                if abs(
                    g["y1"]
                    - (y_rail - 0.85)
                )
                < 0.05
            ]

            if desta_fileira:
                yp = (
                    y_rail
                    + 0.90
                )

                grupos_fileira = []
                for d, g in desta_fileira:
                    grupo = str(
                        d.get(
                            "grupo",
                            "SEM DR"
                        )
                        or "SEM DR"
                    )

                    if (
                        not grupos_fileira
                        or grupos_fileira[-1][0]
                        != grupo
                    ):
                        grupos_fileira.append(
                            [
                                grupo,
                                []
                            ]
                        )

                    grupos_fileira[-1][1].append(
                        (
                            d,
                            g
                        )
                    )

                dr_geom_por_grupo = {
                    str(
                        d.get(
                            "grupo",
                            ""
                        )
                        or ""
                    ):
                    g
                    for d, g in geral_geom
                    if d.get(
                        "tipo"
                    )
                    == "IDR"
                }

                for grupo, itens_grupo in grupos_fileira:
                    x1p = itens_grupo[0][1]["x1"]
                    x2p = itens_grupo[-1][1]["x2"]

                    _line(
                        msp,
                        (x1p, yp),
                        (x2p, yp),
                        LP
                    )

                    _text(
                        msp,
                        (
                            "PENTE "
                            + str(
                                grupo
                            )
                        ),
                        x1p,
                        yp + 0.15,
                        0.070,
                        LT
                    )

                    # Dentes do pente para os disjuntores daquele grupo.
                    for d, g in itens_grupo:
                        _line(
                            msp,
                            (g["cx"], yp),
                            (g["cx"], g["y2"]),
                            _layer_fase(
                                d.get(
                                    "fase"
                                )
                            )
                        )

                    # Alimentação do segmento:
                    # - grupo protegido: saída do respectivo IDR;
                    # - SEM DR: saída direta do DG.
                    fonte_g = dr_geom_por_grupo.get(
                        grupo
                    )

                    if (
                        fonte_g is None
                        and str(
                            grupo
                        ).upper()
                        == "SEM DR"
                        and dg_geoms
                    ):
                        fonte_g = dg_geoms[0][1]

                    if fonte_g:
                        x_dest = (
                            x1p
                            + x2p
                        ) / 2.0

                        y_saida_fonte = (
                            fonte_g["y1"]
                            - 0.20
                        )

                        _polyline(
                            msp,
                            [
                                (
                                    fonte_g["cx"],
                                    fonte_g["y1"]
                                ),
                                (
                                    fonte_g["cx"],
                                    y_saida_fonte
                                ),
                                (
                                    x_dest,
                                    y_saida_fonte
                                ),
                                (
                                    x_dest,
                                    yp
                                ),
                            ],
                            LP
                        )

        y_rail -= 3.15

    # -------------------------
    # Painel lateral
    # -------------------------
    # A tabela deve nascer numa coluna independente da área DIN.
    # Não usar qx2 como referência: qx2 representa o limite gráfico
    # do diagrama e, em quadros largos, fazia a tabela sobrepor o QDC.
    px1 = (
        x0
        + margem_x
        + area_din_w
        + separacao_painel
    )
    px2 = x0 + largura - 0.45
    py_top = qy_top

    _rect(
        msp,
        px1,
        ybase + 0.75,
        px2,
        py_top,
        L
    )

    _text(
        msp,
        "LISTA DE CIRCUITOS",
        px1 + 0.25,
        py_top - 0.38,
        0.16,
        LT
    )

    # Tabela executiva:
    # Circuito | Fase | Disj. | Ambientes
    #
    # Fase 13.4 Rev.8:
    # cada célula é desenhada como um retângulo independente.
    # Evita linhas horizontais longas escapando para dentro do diagrama.
    tabela_x1 = px1 + 0.35
    tabela_largura = min(
        9.20,
        max(
            7.80,
            px2 - tabela_x1 - 0.35
        )
    )
    tabela_x2 = tabela_x1 + tabela_largura
    tabela_y_top = py_top - 0.72

    col_circuito = 1.05
    col_fase = 0.85
    col_dj = 1.10
    col_ambientes = (
        tabela_largura
        - col_circuito
        - col_fase
        - col_dj
    )

    x_c1 = tabela_x1
    x_c2 = x_c1 + col_circuito
    x_c3 = x_c2 + col_fase
    x_c4 = x_c3 + col_dj
    x_c5 = tabela_x2

    altura_cab = 0.42
    altura_linha_base = 0.38

    linhas_tabela = []

    for d in circuitos:
        ident = str(
            d.get(
                "identificador",
                ""
            )
            or ""
        )

        fase_c = str(
            d.get(
                "fase",
                ""
            )
            or ""
        ).strip()

        dj_c = int(
            d.get(
                "corrente_a",
                0
            )
            or 0
        )

        ambientes_txt = str(
            d.get(
                "ambiente",
                ""
            )
            or ""
        ).strip()

        # Usa largura visual da coluna Ambientes para definir a quebra.
        max_chars_amb = max(
            22,
            int(
                col_ambientes
                / 0.066
                / 0.58
            )
        )

        linhas_ambientes = _quebrar_texto(
            ambientes_txt or "-",
            max_chars_amb
        )

        if not linhas_ambientes:
            linhas_ambientes = ["-"]

        altura_linha = max(
            altura_linha_base,
            0.18
            + len(
                linhas_ambientes
            )
            * 0.17
        )

        linhas_tabela.append({
            "identificador": ident,
            "fase": fase_c or "-",
            "disjuntor": f"{dj_c} A",
            "ambientes": linhas_ambientes,
            "altura": altura_linha,
        })

    # Cabeçalho: quatro células independentes.
    y_top = tabela_y_top
    y_bottom = y_top - altura_cab

    cabecalhos = [
        (x_c1, x_c2, "Circuito"),
        (x_c2, x_c3, "Fase"),
        (x_c3, x_c4, "Disj."),
        (x_c4, x_c5, "Ambientes"),
    ]

    for xa, xb, titulo_coluna in cabecalhos:
        _rect(
            msp,
            xa,
            y_bottom,
            xb,
            y_top,
            L
        )
        _text(
            msp,
            titulo_coluna,
            xa + 0.08,
            y_top - 0.27,
            0.075,
            LT
        )

    yy_top = y_bottom

    # Linhas: cada uma composta de quatro retângulos.
    for item in linhas_tabela:
        altura_linha = item["altura"]
        yy_bottom = yy_top - altura_linha

        celulas = [
            (
                x_c1,
                x_c2,
                [item["identificador"]],
                0.072
            ),
            (
                x_c2,
                x_c3,
                [item["fase"]],
                0.072
            ),
            (
                x_c3,
                x_c4,
                [item["disjuntor"]],
                0.072
            ),
            (
                x_c4,
                x_c5,
                item["ambientes"],
                0.066
            ),
        ]

        for xa, xb, textos, altura_texto in celulas:
            _rect(
                msp,
                xa,
                yy_bottom,
                xb,
                yy_top,
                L
            )

            y_txt = yy_top - 0.24

            for texto_celula in textos:
                _text(
                    msp,
                    texto_celula,
                    xa + 0.08,
                    y_txt,
                    altura_texto,
                    LT
                )
                y_txt -= 0.17

        yy_top = yy_bottom

    tabela_y_bottom = yy_top

    # Legenda.
    leg_y = max(
        ybase + 2.30,
        tabela_y_bottom - 0.38
    )
    _text(
        msp,
        "LEGENDA",
        px1 + 0.25,
        leg_y,
        0.15,
        LT
    )

    legendas = []

    fases_reais = _fases_alimentador(
        mapa
    )

    if "A" in fases_reais:
        legendas.append(
            (
                "Fase A / L1",
                LA
            )
        )

    if "B" in fases_reais:
        legendas.append(
            (
                "Fase B / L2",
                LB
            )
        )

    if "C" in fases_reais:
        legendas.append(
            (
                "Fase C / L3",
                LC
            )
        )

    if _tem_neutro_alimentador(
        mapa
    ):
        legendas.append(
            (
                "Neutro (N)",
                LN
            )
        )

    if _tem_pe_alimentador(
        mapa
    ):
        legendas.append(
            (
                "Protecao / Terra (PE)",
                LPE
            )
        )

    legendas.append(
        (
            "Barramento pente",
            LP
        )
    )

    yleg = leg_y - 0.35
    for texto, layer in legendas:
        _line(
            msp,
            (px1 + 0.25, yleg + 0.04),
            (px1 + 0.95, yleg + 0.04),
            layer
        )
        _text(
            msp,
            texto,
            px1 + 1.10,
            yleg,
            0.08,
            LT
        )
        yleg -= 0.27

    # Dados do quadro no rodapé lateral.
    dados_y = ybase + 1.60
    _text(
        msp,
        "DADOS DO QUADRO",
        px1 + 0.25,
        dados_y + 0.85,
        0.15,
        LT
    )
    qtd_idr = sum(1 for d in gerais if d.get("tipo") == "IDR")
    qtd_dps_desenho = sum(1 for d in gerais if d.get("tipo") == "DPS")

    dados = [
        f"Posicoes: {int(mapa.get('qdc_posicoes', 0) or 0)}",
        f"Modulos ocupados: {int(mapa.get('modulos_dispositivos', 0) or 0)}",
        f"Posicoes livres: {int(mapa.get('posicoes_livres', 0) or 0)}",
        f"Fileiras DIN: {int(mapa.get('linhas', 0) or 0)}",
        f"IDRs: {qtd_idr}",
        f"DPS: {qtd_dps_desenho}",
    ]
    yy_d = dados_y + 0.50
    for linha in dados:
        _text(
            msp,
            linha,
            px1 + 0.25,
            yy_d,
            0.083,
            LT
        )
        yy_d -= 0.22

    return {
        "origem": (x0, ybase),
        "largura": largura,
        "altura": altura,
        "qdc_posicoes": mapa.get("qdc_posicoes"),
        "linhas": linhas,
        "colunas": colunas,
        "tipo_desenho": "vista_frontal_executiva",
    }
