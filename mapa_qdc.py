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
    circuitos = [dict(c) for c in (circuitos or [])]
    resumo_drs = [dict(d) for d in (resumo_drs or [])]
    resumo_protecao = dict(resumo_protecao or {})
    resultado_demanda = dict(resultado_demanda or {})

    por_numero = {
        int(c.get("numero", 0) or 0): c
        for c in circuitos
        if int(c.get("numero", 0) or 0) > 0
    }

    dispositivos = []

    dg_a = resultado_demanda.get("disjuntor_geral_a")
    dg_polos = _polos_numero(
        resumo_protecao.get("dg_polos", ""),
        2
    )

    if dg_a:
        dispositivos.append({
            "tipo": "DG",
            "identificador": "DG",
            "descricao": f"Disjuntor geral {dg_polos}P {int(dg_a)} A",
            "modulos": dg_polos,
            "grupo": "GERAL",
            "fase": "",
            "circuitos": "",
        })

    qtd_dps = _qtd_dps(
        resumo_protecao,
        dg_polos if dg_a else 0
    )
    for i in range(1, qtd_dps + 1):
        dispositivos.append({
            "tipo": "DPS",
            "identificador": f"DPS{i}",
            "descricao": "DPS 1P",
            "modulos": 1,
            "grupo": "GERAL",
            "fase": "",
            "circuitos": "",
        })

    circuitos_por_grupo = {}
    sem_dr = []
    for c in sorted(
        circuitos,
        key=lambda x: int(x.get("numero", 0) or 0)
    ):
        gid = str(c.get("dr", "") or "").strip()
        if gid:
            circuitos_por_grupo.setdefault(gid, []).append(c)
        else:
            sem_dr.append(c)

    # Circuitos que não exigem DR entram em seção própria.
    for c in sem_dr:
        n = int(c.get("numero", 0) or 0)
        polos = _polos_circuito(c)
        corrente = int(c.get("disjuntor", 0) or 0)
        fase = str(c.get("fase", "") or "")
        dispositivos.append({
            "tipo": "DJ",
            "identificador": f"C{n:02d}",
            "descricao": f"C{n:02d} {polos}P {corrente} A",
            "modulos": polos,
            "grupo": "SEM DR",
            "fase": fase,
            "circuitos": f"C{n:02d}",
        })

    ordem_drs = []
    for dr in resumo_drs:
        gid = str(dr.get("dr", "") or "").strip()
        if gid and gid not in ordem_drs:
            ordem_drs.append(gid)

    for gid in circuitos_por_grupo:
        if gid not in ordem_drs:
            ordem_drs.append(gid)

    resumo_dr_por_id = {
        str(dr.get("dr", "") or "").strip(): dr
        for dr in resumo_drs
    }

    for gid in ordem_drs:
        itens = circuitos_por_grupo.get(gid, [])
        if not itens:
            continue

        dr = resumo_dr_por_id.get(gid, {})
        polos_dr = _polos_dr(dr, por_numero)
        nominal = dr.get("corrente_nominal_a")
        sens = dr.get("sensibilidade_ma")

        descr = f"{gid} {polos_dr}P"
        if nominal:
            descr += f" {int(nominal)} A"
        if sens:
            descr += f" {int(sens)} mA"

        dispositivos.append({
            "tipo": "IDR",
            "identificador": gid,
            "descricao": descr,
            "modulos": polos_dr,
            "grupo": gid,
            "fase": "",
            "circuitos": ",".join(
                f"C{int(c.get('numero', 0) or 0):02d}"
                for c in itens
            ),
        })

        for c in itens:
            n = int(c.get("numero", 0) or 0)
            polos = _polos_circuito(c)
            corrente = int(c.get("disjuntor", 0) or 0)
            fase = str(c.get("fase", "") or "")
            dispositivos.append({
                "tipo": "DJ",
                "identificador": f"C{n:02d}",
                "descricao": f"C{n:02d} {polos}P {corrente} A",
                "modulos": polos,
                "grupo": gid,
                "fase": fase,
                "circuitos": f"C{n:02d}",
            })

    return dispositivos


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


def desenhar_mapa_fisico_qdc(
    msp,
    mapa,
    polilinhas_ambientes
):
    mapa = dict(mapa or {})
    if mapa.get("status") != "ok":
        return None

    pontos = []
    for pol in polilinhas_ambientes or []:
        pontos.extend(list(pol or []))

    max_x = max((p[0] for p in pontos), default=0.0)
    max_y = max((p[1] for p in pontos), default=10.0)

    # Unifilar ocupa aproximadamente max_x+3 até max_x+23.2.
    # O mapa físico nasce à direita com margem própria.
    x0 = max_x + 25.4
    y0 = max_y

    layer = "PROJ_ELETRICA_MAPA_QDC"
    layer_txt = "PROJ_ELETRICA_MAPA_QDC_TEXTO"

    colunas = int(mapa.get("colunas", 0) or 0)
    linhas = int(mapa.get("linhas", 0) or 0)

    modulo_w = 0.72
    trilho_h = 1.35
    gap = 0.55
    margem = 0.45
    titulo_h = 1.20

    largura = margem * 2 + colunas * modulo_w
    altura = titulo_h + margem + linhas * trilho_h + max(0, linhas - 1) * gap + margem

    ybase = y0 - altura
    _rect(msp, x0, ybase, x0 + largura, y0, layer)

    _text(
        msp,
        f"MAPA FISICO QDC - {int(mapa.get('qdc_posicoes', 0) or 0)} POSICOES DIN",
        x0 + 0.35,
        y0 - 0.45,
        0.18,
        layer_txt
    )
    _text(
        msp,
        "FASE 13.2 | POSICOES REAIS DE MONTAGEM",
        x0 + 0.35,
        y0 - 0.78,
        0.095,
        layer_txt
    )

    slots_por_pos = {
        int(s.get("posicao", 0) or 0): s
        for s in (mapa.get("slots", []) or [])
    }

    for linha in range(1, linhas + 1):
        top = y0 - titulo_h - (linha - 1) * (trilho_h + gap)
        bottom = top - trilho_h
        _text(
            msp,
            f"TRILHO {linha}",
            x0 + 0.08,
            top - 0.17,
            0.075,
            layer_txt
        )

        for coluna in range(1, colunas + 1):
            pos = (linha - 1) * colunas + coluna
            x1 = x0 + margem + (coluna - 1) * modulo_w
            x2 = x1 + modulo_w
            y1 = bottom + 0.12
            y2 = top - 0.30
            _rect(msp, x1, y1, x2, y2, layer)

            slot = slots_por_pos.get(pos, {})
            ident = str(slot.get("identificador", "LIVRE") or "LIVRE")
            tipo = str(slot.get("tipo", "") or "")

            _text(
                msp,
                f"{pos:02d}",
                x1 + 0.04,
                y1 + 0.06,
                0.055,
                layer_txt
            )

            if tipo == "RESERVA":
                label = "LIVRE"
            else:
                label = ident

            _text(
                msp,
                label,
                x1 + 0.08,
                y1 + 0.42,
                0.075,
                layer_txt
            )

    return {
        "origem": (x0, ybase),
        "largura": largura,
        "altura": altura,
        "qdc_posicoes": mapa.get("qdc_posicoes"),
        "linhas": linhas,
        "colunas": colunas,
    }
