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
    Fase 13.4:
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

    return {
        "status": "ok",
        "qdc_posicoes": posicoes,
        "linhas": layout["linhas"],
        "colunas": layout["colunas"],
        "modulos_dispositivos": modulos_dispositivos,
        "posicoes_livres": livres,
        "dispositivos": layout["dispositivos"],
        "slots": slots,
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


def _desenhar_trilho(msp, x1, x2, y, layer):
    _line(msp, (x1, y), (x2, y), layer)
    _line(msp, (x1, y - 0.08), (x2, y - 0.08), layer)
    passo = 0.34
    x = x1 + 0.18
    while x < x2 - 0.18:
        _line(
            msp,
            (x, y - 0.10),
            (x + 0.12, y + 0.02),
            layer
        )
        x += passo


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
    Fase 13.4 — QDC executivo no CAD.

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
    painel_circuitos_w = 7.10
    area_din_w = max(9.6, colunas * modulo_w + 2.30)
    largura = area_din_w + painel_circuitos_w + 1.20

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
        "VISTA FRONTAL - DIAGRAMA DE MONTAGEM E LIGACOES | FASE 13.4",
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
    _desenhar_trilho(
        msp,
        din_x1,
        din_x2,
        top_rail_y - 0.05,
        L
    )

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
        offsets = {"A": -0.16, "B": 0.0, "C": 0.16}

        for token in ("A", "B", "C"):
            xx = entrada_x + offsets[token]
            _line(
                msp,
                (xx, qy_top - 0.10),
                (xx, dg["y2"]),
                _layer_por_token(token)
            )
            _text(
                msp,
                f"L{('A','B','C').index(token)+1}",
                xx - 0.045,
                qy_top - 0.30,
                0.075,
                LT
            )

        _polyline(
            msp,
            [
                (entrada_x + 0.34, qy_top - 0.10),
                (entrada_x + 0.34, qy_top - 0.42),
                (neutro["x"], qy_top - 0.42),
                (neutro["x"], neutro["y_top"]),
            ],
            LN
        )
        _text(msp, "N", entrada_x + 0.30, qy_top - 0.30, 0.075, LT)
        _text(msp, "ENTRADA DA REDE", din_x1, qy_top - 0.18, 0.085, LT)

    if geral_geom:
        x_bus_ini = dg_geoms[0][1]["cx"] if dg_geoms else geral_geom[0][1]["cx"]
        x_bus_fim = geral_geom[-1][1]["cx"]

        for token in ("A", "B", "C"):
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
        _desenhar_trilho(
            msp,
            din_x1,
            din_x2,
            y_rail - 0.05,
            L
        )

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

            # Circuito/ambiente abaixo.
            _texto_central(
                msp,
                str(d.get("identificador", "")),
                geom["x1"],
                geom["x2"],
                geom["y1"] - 0.25,
                0.10,
                LT
            )

            ambiente = str(d.get("ambiente", "") or "")
            if ambiente:
                linhas_amb = _quebrar_texto(
                    ambiente,
                    15
                )
                yy = geom["y1"] - 0.48
                for linha in linhas_amb[:2]:
                    _texto_central(
                        msp,
                        linha,
                        geom["x1"] - 0.18,
                        geom["x2"] + 0.18,
                        yy,
                        0.065,
                        LT
                    )
                    yy -= 0.15

            # Saída de fase.
            layer_fase = _layer_fase(
                fase
            )
            _line(
                msp,
                (geom["cx"], geom["y1"]),
                (geom["cx"], geom["y1"] - 0.85),
                layer_fase
            )

            # PE até barramento esquerdo.
            y_pe = max(
                pe["y_bottom"] + 0.16,
                geom["y1"] - 0.68
            )
            _polyline(
                msp,
                [
                    (geom["cx"] - 0.12, geom["y1"] - 0.03),
                    (geom["cx"] - 0.12, y_pe),
                    (pe["x"], y_pe),
                ],
                LPE
            )

            # N em circuitos 1P.
            if mod == 1:
                y_n = max(
                    neutro["y_bottom"] + 0.16,
                    geom["y1"] - 0.52
                )
                _polyline(
                    msp,
                    [
                        (geom["cx"] + 0.12, geom["y1"] - 0.03),
                        (geom["cx"] + 0.12, y_n),
                        (neutro["x"], y_n),
                    ],
                    LN
                )

            x = geom["x2"] + 0.10
            usados += mod
            idx_circ += 1

        # Barramento pente acima desta fileira.
        if circuitos_geom:
            desta_fileira = [
                (d,g)
                for d,g in circuitos_geom
                if abs(g["y1"] - (y_rail - 0.85)) < 0.05
            ]
            if desta_fileira:
                x1p = desta_fileira[0][1]["x1"]
                x2p = desta_fileira[-1][1]["x2"]
                yp = y_rail + 0.90
                _line(
                    msp,
                    (x1p, yp),
                    (x2p, yp),
                    LP
                )
                _text(
                    msp,
                    "BARRAMENTO PENTE",
                    x1p,
                    yp + 0.15,
                    0.075,
                    LT
                )
                for d,g in desta_fileira:
                    _line(
                        msp,
                        (g["cx"], yp),
                        (g["cx"], g["y2"]),
                        _layer_fase(d.get("fase"))
                    )

        y_rail -= 3.15

    # -------------------------
    # Painel lateral
    # -------------------------
    px1 = qx2 + 0.35
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

    yy = py_top - 0.75
    for d in circuitos:
        if yy < ybase + 4.20:
            break
        ident = str(d.get("identificador", "") or "")
        ambiente = str(d.get("ambiente", "") or "")
        tipo_c = str(d.get("tipo_circuito", "") or "")
        fase_c = str(d.get("fase", "") or "").strip()
        dj_c = int(d.get("corrente_a", 0) or 0)
        texto = f"{ident} | {fase_c or '-'} | {dj_c}A | {ambiente}"
        if tipo_c:
            texto += f" | {tipo_c}"

        for li, linha in enumerate(_quebrar_texto(texto, 42)):
            _text(
                msp,
                linha,
                px1 + 0.25,
                yy,
                0.085,
                LT
            )
            yy -= 0.17
        yy -= 0.06

    # Legenda.
    leg_y = max(ybase + 2.30, yy - 0.15)
    _text(
        msp,
        "LEGENDA",
        px1 + 0.25,
        leg_y,
        0.15,
        LT
    )

    legendas = [
        ("Fase A / L1", LA),
        ("Fase B / L2", LB),
        ("Fase C / L3", LC),
        ("Neutro (N)", LN),
        ("Protecao / Terra (PE)", LPE),
        ("Barramento pente", LP),
    ]

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
