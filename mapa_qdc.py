import math
import re

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


def _condutores_dr(dr, circuitos_por_numero):
    """
    Retorna os condutores que realmente atravessam o IDR com base na
    coluna `fase` dos circuitos já balanceados.

    Exemplos:
      circuitos só em A (127 V)        -> A + N
      circuitos A-B apenas (220 V)     -> A + B
      circuitos em A e B com 127 V     -> A + B + N
      grupo usando A/B/C e 127 V       -> A + B + C + N
    """
    numeros = [
        int(n or 0)
        for n in (dr.get("circuitos", []) or [])
        if int(n or 0) > 0
    ]

    fases = []
    precisa_neutro = False

    for numero in numeros:
        circuito = circuitos_por_numero.get(
            numero
        )

        if not circuito:
            continue

        for token in _fases_do_texto(
            circuito.get(
                "fase",
                ""
            )
        ):
            if (
                token in ("A", "B", "C")
                and token not in fases
            ):
                fases.append(
                    token
                )

        # Circuito monopolar utiliza fase + neutro.
        if _polos_circuito(
            circuito
        ) == 1:
            precisa_neutro = True

    fases = [
        token
        for token in ("A", "B", "C")
        if token in fases
    ]

    condutores = list(
        fases
    )

    if precisa_neutro:
        condutores.append(
            "N"
        )

    return condutores


def _polos_dr(dr, circuitos_por_numero):
    """
    Dimensiona fisicamente o IDR pelos condutores reais do grupo.

    Em padrão DIN residencial:
      - 2 condutores -> IDR 2P;
      - 3 ou 4 condutores -> IDR 4P.
    """
    condutores = _condutores_dr(
        dr,
        circuitos_por_numero
    )

    qtd = len(
        condutores
    )

    if qtd <= 2:
        return 2

    return 4



def _dispositivos_base(
    circuitos,
    resumo_drs,
    resumo_protecao,
    resultado_demanda
):
    """
    Fase 13.6 Rev.105:
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

        condutores_grupo = _condutores_dr(
            dr,
            por_numero
        )

        fases_grupo = [
            token
            for token in condutores_grupo
            if token in ("A", "B", "C")
        ]

        protecoes_gerais.append({
            "tipo": "IDR",
            "identificador": gid,
            "descricao": descr,
            "modulos": polos_dr,
            "grupo": gid,
            "fase": "/".join(fases_grupo),
            "condutores": condutores_grupo,
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


# ============================================================
# FASE 13.6 REV.105 — PASSAGENS "POR TRÁS" DE TODOS OS APARELHOS
# ============================================================
_QDC_DJ_RECTS = []

# Rev.41 — retângulos externos de entrada/saída.
# Os cabos não podem ficar visíveis dentro dessas caixas.
_QDC_TERMINAL_RECTS = []

_QDC_LAYERS_CONDUTORES = {
    "PROJ_ELETRICA_QDC_FASE_A",
    "PROJ_ELETRICA_QDC_FASE_B",
    "PROJ_ELETRICA_QDC_FASE_C",
    "PROJ_ELETRICA_QDC_NEUTRO",
    "PROJ_ELETRICA_QDC_PE",
}


def _recortar_segmentos_por_retangulos(segmentos, retangulos):
    """
    Remove dos segmentos os trechos internos aos retângulos informados.
    Usado nos pequenos terminais de entrada/saída: o cabo chega até a
    borda do terminal, desaparece dentro dele e reaparece após a outra borda.
    """
    resultado = list(segmentos)

    for r in retangulos:
        novos = []
        rx1 = float(r["x1"])
        rx2 = float(r["x2"])
        ry1 = float(r["y1"])
        ry2 = float(r["y2"])

        for a, b in resultado:
            ax, ay = float(a[0]), float(a[1])
            bx, by = float(b[0]), float(b[1])

            # Segmento vertical.
            if abs(ax - bx) <= 1e-9 and rx1 < ax < rx2:
                lo = min(ay, by)
                hi = max(ay, by)

                if hi > ry1 and lo < ry2:
                    partes = []
                    if lo < ry1:
                        partes.append((lo, ry1))
                    if hi > ry2:
                        partes.append((ry2, hi))

                    for ylo, yhi in partes:
                        if ay <= by:
                            novos.append(((ax, ylo), (ax, yhi)))
                        else:
                            novos.append(((ax, yhi), (ax, ylo)))
                    continue

            # Segmento horizontal.
            if abs(ay - by) <= 1e-9 and ry1 < ay < ry2:
                lo = min(ax, bx)
                hi = max(ax, bx)

                if hi > rx1 and lo < rx2:
                    partes = []
                    if lo < rx1:
                        partes.append((lo, rx1))
                    if hi > rx2:
                        partes.append((rx2, hi))

                    for xlo, xhi in partes:
                        if ax <= bx:
                            novos.append(((xlo, ay), (xhi, ay)))
                        else:
                            novos.append(((xhi, ay), (xlo, ay)))
                    continue

            novos.append((a, b))

        resultado = novos

    return resultado


def _segmentos_fora_dos_disjuntores(p1, p2):
    """
    Rev.56 — recorta trechos de condutor que atravessam o INTERIOR
    de qualquer aparelho do QDC (DG, DPS, IDR/DR e DJ).
    O cabo existe eletricamente, mas visualmente passa por trás do aparelho.

    Conexões que terminam exatamente no borne/limite do disjuntor
    são preservadas.
    """
    segmentos = [(tuple(p1), tuple(p2))]

    for r in _QDC_DJ_RECTS:
        novos = []
        rx1 = float(r["x1"])
        rx2 = float(r["x2"])
        ry1 = float(r["y1"])
        ry2 = float(r["y2"])

        for a, b in segmentos:
            ax, ay = float(a[0]), float(a[1])
            bx, by = float(b[0]), float(b[1])

            # Segmento vertical atravessando o corpo do DJ.
            if abs(ax - bx) <= 1e-9 and rx1 < ax < rx2:
                lo = min(ay, by)
                hi = max(ay, by)

                if hi > ry1 and lo < ry2:
                    partes = []
                    if lo < ry1:
                        partes.append((lo, ry1))
                    if hi > ry2:
                        partes.append((ry2, hi))

                    for ylo, yhi in partes:
                        if ay <= by:
                            novos.append(((ax, ylo), (ax, yhi)))
                        else:
                            novos.append(((ax, yhi), (ax, ylo)))
                    continue

            # Segmento horizontal atravessando o corpo do DJ.
            if abs(ay - by) <= 1e-9 and ry1 < ay < ry2:
                lo = min(ax, bx)
                hi = max(ax, bx)

                if hi > rx1 and lo < rx2:
                    partes = []
                    if lo < rx1:
                        partes.append((lo, rx1))
                    if hi > rx2:
                        partes.append((rx2, hi))

                    for xlo, xhi in partes:
                        if ax <= bx:
                            novos.append(((xlo, ay), (xhi, ay)))
                        else:
                            novos.append(((xhi, ay), (xlo, ay)))
                    continue

            novos.append((a, b))

        segmentos = novos

    return segmentos


def _line(msp, p1, p2, layer):
    if layer in _QDC_LAYERS_CONDUTORES:
        criadas = []

        segmentos = _segmentos_fora_dos_disjuntores(
            p1,
            p2
        )

        # Rev.41 — o terminal representa fisicamente o ponto de conexão.
        # Portanto o condutor nunca é mostrado dentro do pequeno retângulo.
        segmentos = _recortar_segmentos_por_retangulos(
            segmentos,
            _QDC_TERMINAL_RECTS
        )

        for a, b in segmentos:
            if (
                abs(float(a[0]) - float(b[0])) <= 1e-9
                and abs(float(a[1]) - float(b[1])) <= 1e-9
            ):
                continue
            criadas.append(
                msp.add_line(
                    a,
                    b,
                    dxfattribs={"layer": layer}
                )
            )
        return criadas[-1] if criadas else None

    return msp.add_line(
        p1,
        p2,
        dxfattribs={"layer": layer}
    )


def _polyline(msp, pontos, layer):
    pontos = list(pontos or [])

    if layer in _QDC_LAYERS_CONDUTORES:
        ultima = None
        for i_seg in range(len(pontos) - 1):
            ultima = _line(
                msp,
                pontos[i_seg],
                pontos[i_seg + 1],
                layer
            )
        return ultima

    return msp.add_lwpolyline(
        pontos,
        dxfattribs={"layer": layer}
    )




def _eh_ultimo_ponto_da_fase(x, pontos_fase, tolerancia=1e-6):
    """
    Convenção gráfica da vista frontal:
    o último ponto de uma pista de fase é somente uma mudança de direção.
    Portanto, não recebe círculo preenchido.
    """
    pontos = [
        float(v)
        for v in (pontos_fase or [])
    ]

    if not pontos:
        return False

    return abs(
        float(x)
        - max(pontos)
    ) <= tolerancia


def _desenhar_no_se_derivacao(msp, x, y, token, pontos_fase):
    """
    Desenha nó somente quando a conexão é uma derivação.
    No último ponto da pista a linha apenas vira/desce.
    """
    if not _eh_ultimo_ponto_da_fase(
        x,
        pontos_fase
    ):
        _no_fase_preenchido(
            msp,
            x,
            y,
            token
        )


# Rev.37 — candidatos a nós. A decisão final é feita somente após
# todos os condutores terem sido desenhados.
_QDC_NODE_CANDIDATES = []
_QDC_NODE_SUPPRESSIONS = []

# Rev.82 — nós cuja existência é conhecida pela lógica elétrica.
# Eles são desenhados somente ao FINAL, após toda a geometria e clipping.
_QDC_LOGICAL_NODES = []

# Rev.85 — pistas horizontais lógicas de distribuição por fase.
# Guardamos o intervalo elétrico exato de cada pista para reconstruí-la
# no final, sem depender de encontros geométricos de linhas da mesma fase.
_QDC_LOGICAL_PHASE_TRACKS = []


def _no_fase_preenchido(msp, x, y, token, raio=0.035):
    """
    Registra um POSSÍVEL nó.

    A bolinha não é desenhada imediatamente. No fim da geração do QDC,
    a topologia real dos condutores é analisada e o nó só é desenhado
    quando existem pelo menos 3 ramos distintos no ponto.
    """
    _QDC_NODE_CANDIDATES.append({
        "msp": msp,
        "x": float(x),
        "y": float(y),
        "token": str(token),
        "raio": float(raio),
    })


def _desenhar_no_confirmado(msp, x, y, token, raio=0.035):
    layer = _layer_por_token(token)
    try:
        msp.add_circle(
            (float(x), float(y)),
            float(raio),
            dxfattribs={"layer": layer}
        )
        hatch = msp.add_hatch(
            color=256,
            dxfattribs={"layer": layer}
        )
        hatch.paths.add_edge_path().add_arc(
            center=(float(x), float(y)),
            radius=float(raio),
            start_angle=0.0,
            end_angle=360.0,
            ccw=True
        )
    except Exception:
        try:
            msp.add_circle(
                (float(x), float(y)),
                max(float(raio) * 0.55, 0.01),
                dxfattribs={"layer": layer}
            )
        except Exception:
            pass


def _ramos_reais_no_ponto(msp, x, y, token, tol=1e-6):
    layer = _layer_por_token(token)
    ramos = set()
    px = float(x)
    py = float(y)

    try:
        entidades = list(msp)
    except Exception:
        entidades = []

    for ent in entidades:
        try:
            if ent.dxftype() != "LINE":
                continue
            if str(ent.dxf.layer) != str(layer):
                continue

            a = ent.dxf.start
            b = ent.dxf.end
            ax, ay = float(a.x), float(a.y)
            bx, by = float(b.x), float(b.y)

            if abs(ay - by) <= tol and abs(py - ay) <= tol:
                xmin = min(ax, bx)
                xmax = max(ax, bx)
                if xmin - tol <= px <= xmax + tol:
                    if xmin < px - tol:
                        ramos.add("L")
                    if xmax > px + tol:
                        ramos.add("R")

            elif abs(ax - bx) <= tol and abs(px - ax) <= tol:
                ymin = min(ay, by)
                ymax = max(ay, by)
                if ymin - tol <= py <= ymax + tol:
                    if ymin < py - tol:
                        ramos.add("D")
                    if ymax > py + tol:
                        ramos.add("U")
        except Exception:
            continue

    return ramos


def _registrar_supressao_no_rev75(msp, x, y, token, raio_busca=0.03):
    _QDC_NODE_SUPPRESSIONS.append({
        "msp": msp,
        "x": float(x),
        "y": float(y),
        "token": str(token).upper(),
        "raio_busca": float(raio_busca),
    })


def _no_suprimido_rev75(msp, x, y, token):
    for item in _QDC_NODE_SUPPRESSIONS:
        if item.get("msp") is not msp:
            continue
        if str(item.get("token", "")).upper() != str(token).upper():
            continue
        dx = float(item["x"]) - float(x)
        dy = float(item["y"]) - float(y)
        if (dx * dx + dy * dy) ** 0.5 <= float(item["raio_busca"]):
            return True
    return False


def _aparar_sobras_horizontais_fase_rev84(msp, tol=1e-6):
    """
    Rev.84 — aparo final de pontas horizontais soltas em A/B/C.

    A Rev.83 exigia pelo menos duas conexões reais para aparar um trecho.
    Em alguns arranjos, o último ramo possui apenas UMA conexão interna
    identificável e uma ponta livre. Nesses casos a sobra continuava visível.

    Regra Rev.84:
    - analisa somente LINEs horizontais das fases A/B/C;
    - uma ponta horizontal é "protegida" se estiver conectada a outra linha
      da mesma fase por extremidade;
    - uma conexão vertical só vale se a EXTREMIDADE do vertical terminar
      exatamente no Y da horizontal;
    - cruzamento visual não conta;
    - nó lógico conhecido também vale como conexão;
    - se uma ponta está livre e existe uma conexão real mais para dentro,
      a ponta é aparada até a conexão mais externa daquele lado;
    - N e PE nunca são tocados.
    """
    layers_fase = {
        _layer_por_token("A"),
        _layer_por_token("B"),
        _layer_por_token("C"),
    }

    try:
        linhas = [
            ent
            for ent in list(msp)
            if (
                ent.dxftype() == "LINE"
                and str(ent.dxf.layer) in layers_fase
            )
        ]
    except Exception:
        return

    def _coords(ent):
        a = ent.dxf.start
        b = ent.dxf.end
        return (
            float(a.x), float(a.y),
            float(b.x), float(b.y),
        )

    def _mesmo_ponto(xa, ya, xb, yb):
        return (
            abs(xa - xb) <= tol
            and abs(ya - yb) <= tol
        )

    por_layer = {}
    for ent in linhas:
        por_layer.setdefault(str(ent.dxf.layer), []).append(ent)

    for layer, ents in por_layer.items():
        horizontais = []
        verticais = []

        for ent in ents:
            try:
                x1, y1, x2, y2 = _coords(ent)
            except Exception:
                continue

            if abs(y1 - y2) <= tol and abs(x1 - x2) > tol:
                horizontais.append((ent, x1, y1, x2, y2))
            elif abs(x1 - x2) <= tol and abs(y1 - y2) > tol:
                verticais.append((ent, x1, y1, x2, y2))

        token_layer = None
        for token_rev84 in ("A", "B", "C"):
            if _layer_por_token(token_rev84) == layer:
                token_layer = token_rev84
                break

        for ent_h, x1, y, x2, _ in horizontais:
            xmin = min(x1, x2)
            xmax = max(x1, x2)

            # ------------------------------------------------
            # Conexões REAIS existentes no interior da horizontal.
            # ------------------------------------------------
            suportes = []

            for _, xv1, yv1, xv2, yv2 in verticais:
                xv = xv1
                toca_por_extremo = (
                    abs(yv1 - y) <= tol
                    or abs(yv2 - y) <= tol
                )
                if (
                    toca_por_extremo
                    and xmin - tol <= xv <= xmax + tol
                ):
                    suportes.append(float(xv))

            if token_layer is not None:
                for item in _QDC_LOGICAL_NODES:
                    if (
                        item.get("msp") is msp
                        and str(item.get("token", "")).upper() == token_layer
                        and abs(float(item.get("y", 0.0)) - y) <= tol
                    ):
                        xn = float(item.get("x", 0.0))
                        if xmin - tol <= xn <= xmax + tol:
                            suportes.append(xn)

            suportes = sorted(
                set(round(float(x), 7) for x in suportes)
            )

            if not suportes:
                continue

            # ------------------------------------------------
            # Descobre se cada ponta da horizontal realmente continua
            # em outra entidade da MESMA fase.
            # ------------------------------------------------
            def _ponta_conectada(xp):
                for outro in ents:
                    if outro is ent_h:
                        continue
                    try:
                        ox1, oy1, ox2, oy2 = _coords(outro)
                    except Exception:
                        continue

                    if (
                        _mesmo_ponto(xp, y, ox1, oy1)
                        or _mesmo_ponto(xp, y, ox2, oy2)
                    ):
                        return True

                # Nó lógico exatamente na ponta também protege a extremidade.
                if token_layer is not None:
                    for item in _QDC_LOGICAL_NODES:
                        if (
                            item.get("msp") is msp
                            and str(item.get("token", "")).upper() == token_layer
                            and abs(float(item.get("x", 0.0)) - xp) <= tol
                            and abs(float(item.get("y", 0.0)) - y) <= tol
                        ):
                            return True

                return False

            esquerda_conectada = _ponta_conectada(xmin)
            direita_conectada = _ponta_conectada(xmax)

            novo_min = xmin
            novo_max = xmax

            # Ponta esquerda livre: corta até a conexão real mais à esquerda.
            if not esquerda_conectada:
                internos_dir = [
                    x for x in suportes
                    if x > xmin + tol
                ]
                if internos_dir:
                    novo_min = min(internos_dir)

            # Ponta direita livre: corta até a conexão real mais à direita.
            if not direita_conectada:
                internos_esq = [
                    x for x in suportes
                    if x < xmax - tol
                ]
                if internos_esq:
                    novo_max = max(internos_esq)

            if novo_max - novo_min <= tol:
                continue

            if (
                novo_min > xmin + tol
                or novo_max < xmax - tol
            ):
                try:
                    if x1 <= x2:
                        ent_h.dxf.start = (novo_min, y, 0.0)
                        ent_h.dxf.end = (novo_max, y, 0.0)
                    else:
                        ent_h.dxf.start = (novo_max, y, 0.0)
                        ent_h.dxf.end = (novo_min, y, 0.0)
                except Exception:
                    continue


def _registrar_pista_horizontal_rev85(
    msp,
    x1,
    x2,
    y,
    token,
    tol=1e-9,
):
    """
    Desenha e registra uma pista horizontal lógica.

    O intervalo registrado é a verdade elétrica da rota. Mais tarde,
    qualquer geometria coincidente no mesmo layer/Y será descartada e
    a pista será reconstruída somente com estes intervalos.
    """
    x1 = float(x1)
    x2 = float(x2)
    y = float(y)
    token = str(token).upper()

    if abs(x2 - x1) <= tol:
        return None

    lo = min(x1, x2)
    hi = max(x1, x2)

    _QDC_LOGICAL_PHASE_TRACKS.append({
        "msp": msp,
        "layer": _layer_por_token(token),
        "token": token,
        "y": y,
        "x1": lo,
        "x2": hi,
    })

    return _line(
        msp,
        (x1, y),
        (x2, y),
        _layer_por_token(token)
    )


def _normalizar_pistas_horizontais_rev85(msp, tol=1e-6):
    """
    Reconstrói as pistas horizontais A/B/C a partir da topologia registrada.

    Importante:
    - atua SOMENTE nos níveis Y que foram explicitamente registrados;
    - não toca neutro, PE, barramentos superiores ou outras cotas;
    - elimina linhas coincidentes/antigas que provocavam o "resto";
    - depois redesenha somente os intervalos lógicos verdadeiros.
    """
    registros = [
        r for r in _QDC_LOGICAL_PHASE_TRACKS
        if r.get("msp") is msp
    ]

    if not registros:
        return

    # Agrupa por layer e nível Y.
    grupos = {}
    for r in registros:
        chave = (
            str(r["layer"]),
            round(float(r["y"]), 7),
        )
        grupos.setdefault(chave, []).append(
            (float(r["x1"]), float(r["x2"]))
        )

    for (layer, y_round), intervalos in grupos.items():
        y = float(y_round)

        # Mescla SOMENTE intervalos lógicos que realmente se tocam.
        ints = sorted(
            (min(a, b), max(a, b))
            for a, b in intervalos
            if abs(b - a) > tol
        )

        if not ints:
            continue

        unidos = [list(ints[0])]
        for lo, hi in ints[1:]:
            if lo <= unidos[-1][1] + tol:
                unidos[-1][1] = max(unidos[-1][1], hi)
            else:
                unidos.append([lo, hi])

        x_global_min = min(lo for lo, _ in unidos)
        x_global_max = max(hi for _, hi in unidos)

        # Remove QUALQUER horizontal A/B/C existente nesse corredor lógico.
        # É justamente aqui que desaparece a continuação indevida da fase A.
        try:
            entidades = list(msp)
        except Exception:
            entidades = []

        for ent in entidades:
            try:
                if ent.dxftype() != "LINE":
                    continue
                if str(ent.dxf.layer) != layer:
                    continue

                a = ent.dxf.start
                b = ent.dxf.end
                ax, ay = float(a.x), float(a.y)
                bx, by = float(b.x), float(b.y)

                if abs(ay - by) > tol:
                    continue
                if abs(ay - y) > tol:
                    continue

                lo_ent = min(ax, bx)
                hi_ent = max(ax, bx)

                # Só apaga linhas que pertencem à região da pista registrada.
                if (
                    hi_ent >= x_global_min - 0.50
                    and lo_ent <= x_global_max + 0.50
                ):
                    try:
                        msp.delete_entity(ent)
                    except Exception:
                        try:
                            ent.destroy()
                        except Exception:
                            pass
            except Exception:
                continue

        # Redesenha exclusivamente os intervalos elétricos registrados.
        for lo, hi in unidos:
            if hi - lo <= tol:
                continue
            msp.add_line(
                (lo, y),
                (hi, y),
                dxfattribs={"layer": layer}
            )


def _registrar_no_logico_rev82(msp, x, y, token, raio=0.035):
    """Registra derivação elétrica REAL para desenhar somente ao final."""
    chave = (
        id(msp),
        round(float(x), 7),
        round(float(y), 7),
        str(token).upper(),
    )

    for item in _QDC_LOGICAL_NODES:
        chave_existente = (
            id(item["msp"]),
            round(float(item["x"]), 7),
            round(float(item["y"]), 7),
            str(item["token"]).upper(),
        )
        if chave_existente == chave:
            return

    _QDC_LOGICAL_NODES.append({
        "msp": msp,
        "x": float(x),
        "y": float(y),
        "token": str(token).upper(),
        "raio": float(raio),
    })


def _desenhar_nos_logicos_finais_rev82(msp):
    """
    Desenha somente as derivações previamente confirmadas pela topologia.
    É executado após todos os cabos e após o clipping final.
    """
    for item in list(_QDC_LOGICAL_NODES):
        if item.get("msp") is not msp:
            continue

        x = float(item["x"])
        y = float(item["y"])
        token = str(item["token"])
        raio = float(item.get("raio", 0.035))

        if _no_suprimido_rev75(msp, x, y, token):
            continue

        if _ja_existe_no_confirmado(msp, x, y, token):
            continue

        _desenhar_no_confirmado(
            msp,
            x,
            y,
            token,
            raio
        )


def _ja_existe_no_confirmado(msp, x, y, token, tol=1e-5):
    layer = _layer_por_token(token)
    px = float(x)
    py = float(y)
    try:
        entidades = list(msp)
    except Exception:
        return False

    for ent in entidades:
        try:
            if ent.dxftype() != "CIRCLE":
                continue
            if str(ent.dxf.layer) != str(layer):
                continue
            c = ent.dxf.center
            if (
                abs(float(c.x) - px) <= tol
                and abs(float(c.y) - py) <= tol
            ):
                return True
        except Exception:
            continue
    return False


def _finalizar_nos_topologicos(msp):
    """
    Rev.80 — nós somente em derivações elétricas lógicas.

    IMPORTANTE:
    - cruzamentos geométricos NÃO são tratados como conexão;
    - encontros visuais de linhas NÃO geram bolinha;
    - somente pontos registrados pela lógica de roteamento podem gerar nó;
    - nós estruturais já confirmados diretamente permanecem preservados.

    Para os candidatos lógicos, ainda exigimos 3 ou mais ramos reais.
    """
    vistos = set()

    for cand in list(_QDC_NODE_CANDIDATES):
        if cand.get("msp") is not msp:
            continue

        x = float(cand["x"])
        y = float(cand["y"])
        token = str(cand["token"])
        raio = float(cand.get("raio", 0.035))

        chave = (
            round(x, 7),
            round(y, 7),
            token,
        )

        if chave in vistos:
            continue
        vistos.add(chave)

        if _no_suprimido_rev75(
            msp,
            x,
            y,
            token
        ):
            continue

        ramos = _ramos_reais_no_ponto(
            msp,
            x,
            y,
            token
        )

        if (
            len(ramos) >= 3
            and not _ja_existe_no_confirmado(
                msp,
                x,
                y,
                token
            )
        ):
            _desenhar_no_confirmado(
                msp,
                x,
                y,
                token,
                raio
            )


def _reclipar_condutores_com_todos_aparelhos(msp):
    """
    Rev.57 — recorte final de todos os condutores com a geometria COMPLETA.

    As fileiras são construídas em sequência. Portanto uma linha criada na
    1ª ou 2ª fileira pode existir antes de o DJ da 3ª fileira ser registrado
    como obstáculo. Esta rotina é executada somente depois de TODAS as
    fileiras/dispositivos existirem.

    Não move cabos e não muda sua topologia. Apenas remove os trechos que
    ficaram dentro dos corpos de DG, DPS, IDR/DR, DJ ou terminais.
    """
    entidades = []

    try:
        entidades = list(msp)
    except Exception:
        return

    for ent in entidades:
        try:
            if ent.dxftype() != "LINE":
                continue

            layer = str(ent.dxf.layer)
            if layer not in _QDC_LAYERS_CONDUTORES:
                continue

            a = ent.dxf.start
            b = ent.dxf.end

            p1 = (float(a.x), float(a.y))
            p2 = (float(b.x), float(b.y))

            segmentos = _segmentos_fora_dos_disjuntores(
                p1,
                p2
            )
            segmentos = _recortar_segmentos_por_retangulos(
                segmentos,
                _QDC_TERMINAL_RECTS
            )

            # Se o segmento não sofreu alteração, preserva a entidade.
            if (
                len(segmentos) == 1
                and abs(segmentos[0][0][0] - p1[0]) <= 1e-9
                and abs(segmentos[0][0][1] - p1[1]) <= 1e-9
                and abs(segmentos[0][1][0] - p2[0]) <= 1e-9
                and abs(segmentos[0][1][1] - p2[1]) <= 1e-9
            ):
                continue

            try:
                msp.delete_entity(ent)
            except Exception:
                try:
                    ent.destroy()
                except Exception:
                    continue

            # Criação direta, sem chamar _line(), para não recortar duas vezes.
            for pa, pb in segmentos:
                if (
                    abs(float(pa[0]) - float(pb[0])) <= 1e-9
                    and abs(float(pa[1]) - float(pb[1])) <= 1e-9
                ):
                    continue

                msp.add_line(
                    pa,
                    pb,
                    dxfattribs={"layer": layer}
                )

        except Exception:
            continue


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
    if token == "N":
        return "PROJ_ELETRICA_QDC_NEUTRO"
    if token == "PE":
        return "PROJ_ELETRICA_QDC_PE"
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


def _y_borne_barramento(barramento, indice):
    """
    Retorna o Y do borne físico do barramento vertical.
    indice=0 -> 1º borne; indice=1 -> 2º borne; etc.
    Deve permanecer sincronizado com _desenhar_barramento_vertical().
    """
    espac = 0.34
    return (
        float(barramento["y_top"])
        - 0.18
        - max(0, int(indice)) * espac
    )


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

    # Fase 13.6 Rev.105:
    # cada módulo/polo fica visualmente separado dentro do aparelho.
    # Assim 1P, 2P, 3P e 4P têm dimensões e leitura física distintas.
    if modulos > 1:
        for i_sep in range(1, modulos):
            x_sep = x1 + modulo_w * i_sep
            _line(
                msp,
                (x_sep, y1 + 0.08),
                (x_sep, y2 - 0.08),
                layer
            )

    # Bornes superior/inferior por polo/módulo.
    #
    # Rev.42 — retângulos somente onde existe cabo real e na mesma
    # layer/cor do respectivo condutor.
    terminal_largura = 0.05
    terminal_altura = 0.075

    tipo_disp = str(disp.get("tipo", "") or "").upper()
    condutores_superiores = [None] * modulos
    condutores_inferiores = [None] * modulos

    if tipo_disp == "DG":
        fases_dg = ["A", "B", "C"][:modulos]
        for idx_c, token_c in enumerate(fases_dg):
            condutores_superiores[idx_c] = token_c
            condutores_inferiores[idx_c] = token_c

    elif tipo_disp == "DPS":
        fases_dps = _fases_do_texto(disp.get("fase", ""))
        if fases_dps:
            condutores_superiores[0] = fases_dps[0]
            condutores_inferiores[0] = "PE"

    elif tipo_disp == "IDR":
        condutores_idr = [
            str(c).upper()
            for c in (disp.get("condutores", []) or [])
        ]
        if modulos >= 4:
            ordem_fisica = ["A", "B", "C", "N"]
            for idx_c, token_c in enumerate(ordem_fisica[:modulos]):
                if token_c in condutores_idr:
                    condutores_superiores[idx_c] = token_c
                    condutores_inferiores[idx_c] = token_c
        else:
            for idx_c, token_c in enumerate(condutores_idr[:modulos]):
                condutores_superiores[idx_c] = token_c
                condutores_inferiores[idx_c] = token_c

    elif tipo_disp == "DJ":
        fases_dj = _fases_do_texto(disp.get("fase", ""))
        for idx_c, token_c in enumerate(fases_dj[:modulos]):
            condutores_superiores[idx_c] = token_c
            condutores_inferiores[idx_c] = token_c

    for i in range(modulos):
        cx = x1 + modulo_w * (i + 0.5)

        _desenhar_borne(msp, cx, y2 - 0.18, layer)
        _desenhar_borne(msp, cx, y1 + 0.18, layer)

        x_t1 = cx - terminal_largura / 2.0
        x_t2 = cx + terminal_largura / 2.0

        token_sup = condutores_superiores[i]
        if token_sup:
            y_sup_1 = y2
            y_sup_2 = y2 + terminal_altura
            layer_terminal_sup = _layer_por_token(token_sup)
            _rect(msp, x_t1, y_sup_1, x_t2, y_sup_2, layer_terminal_sup)
            _QDC_TERMINAL_RECTS.append({
                "x1": float(x_t1), "x2": float(x_t2),
                "y1": float(y_sup_1), "y2": float(y_sup_2),
            })

        token_inf = condutores_inferiores[i]
        if token_inf:
            y_inf_1 = y1 - terminal_altura
            y_inf_2 = y1
            layer_terminal_inf = _layer_por_token(token_inf)
            _rect(msp, x_t1, y_inf_1, x_t2, y_inf_2, layer_terminal_inf)
            _QDC_TERMINAL_RECTS.append({
                "x1": float(x_t1), "x2": float(x_t2),
                "y1": float(y_inf_1), "y2": float(y_inf_2),
            })

    tipo = str(disp.get("tipo", "") or "")
    ident = str(disp.get("identificador", "") or "")
    corrente = disp.get("corrente_a")

    # Fase 13.6 Rev.105:
    # identificação principal dos dispositivos superiores:
    # DG, DPS e DR/IDR com height fixo 0.105.
    # Disjuntores terminais mantêm o tamanho anterior.
    altura_identificacao = (
        0.105
        if tipo in {"DG", "DPS", "IDR"}
        else 0.12
    )

    _texto_central(
        msp,
        ident,
        x1,
        x2,
        y1 + altura * 0.57,
        altura_identificacao,
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

    _texto_central(
        msp,
        f"{modulos}P",
        x1,
        x2,
        y2 - 0.35,
        0.060,
        layer_txt
    )

    if tipo == "IDR" and disp.get("sensibilidade_ma"):
        # Fase 13.6 Rev.105:
        # a sensibilidade do DR fica abaixo do símbolo de teste,
        # evitando sobreposição entre "30mA" e o círculo central.
        _texto_central(
            msp,
            f"{int(disp.get('sensibilidade_ma'))}mA",
            x1,
            x2,
            y1 + altura * 0.205,
            0.078,
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

    # Rev.56 — TODOS os aparelhos ficam visualmente "na frente".
    # Qualquer cabo de passagem some ao atravessar o corpo de:
    # DG, DPS, IDR/DR ou DJ.
    if tipo in {"DG", "DPS", "IDR", "DJ"}:
        _QDC_DJ_RECTS.append({
            "x1": float(x1),
            "x2": float(x2),
            "y1": float(y1),
            "y2": float(y2),
            "tipo": tipo,
            "geom_id": None,  # preenchido após criação da geometria
        })

    geom_retorno = {
        "x1": x1,
        "x2": x2,
        "cx": (x1 + x2) / 2.0,
        "y1": y1,
        "y2": y2,
        "modulos": modulos,
        "tipo": tipo,
        "identificador": ident,
    }

    # Rev.56 — associa o obstáculo ao objeto geométrico retornado.
    if _QDC_DJ_RECTS and _QDC_DJ_RECTS[-1].get("geom_id") is None:
        ultimo = _QDC_DJ_RECTS[-1]
        if (
            abs(float(ultimo["x1"]) - float(x1)) <= 1e-9
            and abs(float(ultimo["x2"]) - float(x2)) <= 1e-9
            and abs(float(ultimo["y1"]) - float(y1)) <= 1e-9
            and abs(float(ultimo["y2"]) - float(y2)) <= 1e-9
        ):
            ultimo["geom_id"] = id(geom_retorno)

    return geom_retorno


def _x_passagem_lateral_disjuntor(geom, lado="esq", afastamento=0.08):
    """
    Retorna um eixo X de passagem FORA do corpo do disjuntor.
    Usado por condutores que apenas atravessam a região verticalmente,
    sem entrar eletricamente naquele aparelho.
    """
    if str(lado).lower().startswith("d"):
        return float(geom["x2"]) + float(afastamento)
    return float(geom["x1"]) - float(afastamento)


def _centros_polos(geom):
    modulos = max(
        1,
        int(
            geom.get(
                "modulos",
                1
            )
            or 1
        )
    )
    largura = (
        float(geom["x2"])
        - float(geom["x1"])
    )
    passo = largura / modulos
    return [
        float(geom["x1"])
        + passo * (i + 0.5)
        for i in range(modulos)
    ]


def _indice_fase(token):
    token = str(
        token
        or ""
    ).upper()

    return {
        "A": 0,
        "B": 1,
        "C": 2,
    }.get(
        token,
        0
    )


def _mapa_condutores_polos(disp, geom):
    """
    Mapeia cada condutor elétrico a um polo físico único.
    Nunca permite duas fases no mesmo polo.
    """
    centros = _centros_polos(
        geom
    )

    tipo = str(
        disp.get(
            "tipo",
            ""
        )
        or ""
    ).upper()

    if tipo == "DG":
        ordem = [
            "A",
            "B",
            "C",
        ][:len(
            centros
        )]

    elif tipo == "IDR":
        condutores = [
            str(c).upper()
            for c in (
                disp.get(
                    "condutores",
                    []
                )
                or []
            )
        ]

        if len(centros) >= 4:
            # Ordem física convencional e estável.
            ordem = [
                "A",
                "B",
                "C",
                "N",
            ]
        else:
            ordem = list(
                condutores
            )[:len(
                centros
            )]

    else:
        ordem = _fases_do_texto(
            disp.get(
                "fase",
                ""
            )
        )[:len(
            centros
        )]

    mapa = {}

    for idx, condutor in enumerate(
        ordem
    ):
        if idx >= len(
            centros
        ):
            break

        mapa[
            condutor
        ] = centros[
            idx
        ]

    return mapa


def _polo_para_fase(disp, geom, token):
    token = str(
        token
        or ""
    ).upper()

    mapa = _mapa_condutores_polos(
        disp,
        geom
    )

    if token in mapa:
        return mapa[
            token
        ]

    centros = _centros_polos(
        geom
    )

    return centros[
        0
    ]



def _mapa_fases_polos(disp, geom):
    """Associa as fases elétricas reais aos polos físicos do aparelho."""
    fases = _fases_do_texto(
        disp.get(
            "fase",
            ""
        )
    )
    centros = _centros_polos(
        geom
    )

    resultado = []
    for idx, fase in enumerate(fases):
        if idx >= len(centros):
            break
        resultado.append(
            (
                fase,
                centros[idx]
            )
        )
    return resultado


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


def _x_desvio_para_nao_invadir_dj(
    x_original,
    y_inicio,
    y_fim,
    dj_destino_geom=None,
    margem=0.12,
    tolerancia=1e-9,
):
    """
    Rev.56 — prioridade absoluta do cabo que ENTRA no disjuntor.

    Se um cabo vertical apenas atravessaria o corpo de outro DJ, ele não
    mantém o mesmo eixo X do borne daquele aparelho: recebe um corredor
    lateral fora do corpo. O cabo cujo destino é o próprio DJ mantém o
    eixo original e desce reto.
    """
    x_original = float(x_original)
    y_lo = min(float(y_inicio), float(y_fim))
    y_hi = max(float(y_inicio), float(y_fim))

    destino_id = id(dj_destino_geom) if dj_destino_geom is not None else None

    for r in _QDC_DJ_RECTS:
        # Só nos DJs terminais é aplicada a regra de "prioridade de entrada".
        # Os outros aparelhos já são tratados pelo clipping visual.
        if str(r.get("tipo", "DJ")).upper() != "DJ":
            continue

        if destino_id is not None and r.get("geom_id") == destino_id:
            continue

        rx1 = float(r["x1"])
        rx2 = float(r["x2"])
        ry1 = float(r["y1"])
        ry2 = float(r["y2"])

        cruza_y = y_hi > ry1 + tolerancia and y_lo < ry2 - tolerancia
        dentro_x = rx1 + tolerancia < x_original < rx2 - tolerancia

        if cruza_y and dentro_x:
            # Escolhe o lado mais próximo para o desvio.
            dist_esq = abs(x_original - rx1)
            dist_dir = abs(rx2 - x_original)
            if dist_esq <= dist_dir:
                return rx1 - float(margem)
            return rx2 + float(margem)

    return x_original


def _destino_alinhado_prioritario(x_origem, pontos, tolerancia=1e-9):
    """Rev.53: retorna o polo que pode receber o cabo reto e os demais."""
    pontos = sorted(set(float(x) for x in (pontos or [])))
    for x in pontos:
        if abs(x - float(x_origem)) <= tolerancia:
            return x, [p for p in pontos if abs(p - x) > tolerancia]
    return None, pontos


def desenhar_mapa_fisico_qdc(
    msp,
    mapa,
    polilinhas_ambientes,
    parametros_rede=None,
    resumo_balanceamento=None
):
    """
    Fase 13.6 Rev.105 — QDC executivo no CAD.

    O desenho passa a se aproximar de um diagrama de montagem real:
    trilhos DIN, dispositivos frontais, barramento pente, barramentos
    N/PE, condutores por função/fase e quadro lateral de circuitos.
    """
    mapa = dict(mapa or {})
    parametros_rede = dict(parametros_rede or {})
    resumo_balanceamento = dict(resumo_balanceamento or {})
    if mapa.get("status") != "ok":
        return None

    _QDC_DJ_RECTS.clear()
    _QDC_TERMINAL_RECTS.clear()
    _QDC_NODE_CANDIDATES.clear()
    _QDC_NODE_SUPPRESSIONS.clear()
    _QDC_LOGICAL_NODES.clear()
    _QDC_LOGICAL_PHASE_TRACKS.clear()

    pontos = []
    for pol in polilinhas_ambientes or []:
        pontos.extend(list(pol or []))

    max_x = max((p[0] for p in pontos), default=0.0)
    max_y = max((p[1] for p in pontos), default=10.0)

    # Fase 13.6 Rev.105 — o unifilar foi retirado do DXF.
    # A vista frontal passa a ocupar diretamente a área técnica à direita da planta.
    x0 = max_x + 2.50
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

    # Fase 13.6 Rev.105:
    # a vista frontal mantém a ordem lógica SEM DR, DR1, DR2, DR3...
    # aproveitando continuamente os módulos disponíveis do mesmo trilho.
    def _ordem_grupo_qdc(d):
        grupo = str(d.get("grupo", "") or "SEM DR").strip().upper()
        if grupo == "SEM DR":
            ordem = 0
        else:
            m = re.search(r"(\\d+)", grupo)
            ordem = int(m.group(1)) if m else 999
        # Rev.18: ordem física por fase dentro de cada grupo.
        fases = tuple(_fases_do_texto(d.get("fase", "")))
        assinatura_fase = {
            ("A",): 0, ("B",): 1, ("C",): 2,
            ("A", "B"): 3, ("A", "C"): 4,
            ("B", "C"): 5, ("A", "B", "C"): 6,
        }.get(fases, 99)

        ident = str(d.get("identificador", "") or "")
        m_c = re.search(r"(\\d+)", ident)
        circuito = int(m_c.group(1)) if m_c else 9999
        return (ordem, grupo, assinatura_fase, circuito)

    circuitos = sorted(circuitos, key=_ordem_grupo_qdc)

    colunas = int(mapa.get("colunas", 0) or 0)
    linhas = int(mapa.get("linhas", 0) or 0)

    # Fase 13.6 Rev.105 — padrão modular do QDC.
    # Cada polo ocupa exatamente 0,45 unidade CAD:
    # 1P=0,45 | 2P=0,90 | 3P=1,35 | 4P=1,80.
    # A mesma regra vale para DJ/DG, IDR/DR e DPS.
    modulo_w = 0.45
    disp_h = 1.60
    margem_x = 1.15
    # Fase 13.6 Rev.105 — painel lateral mais compacto.
    painel_circuitos_w = 8.10
    separacao_painel = 1.00
    modulos_superiores_previstos = sum(
        max(1, int(d.get("modulos", 1) or 1))
        for d in gerais
    )
    area_din_w = max(
        9.6,
        colunas * modulo_w + 2.30,
        modulos_superiores_previstos * modulo_w
        + max(0, len(gerais) - 1) * 0.06
        + 2.60
    )
    # Fase 13.6 Rev.105 — enquadramento compacto conforme referência aprovada.
    # O painel lateral fica próximo do diagrama, sem o grande corredor vazio.
    folga_painel_real = 0.38
    largura = (
        area_din_w
        + folga_painel_real
        + painel_circuitos_w
        + 0.72
    )

    # Fase 13.6 Rev.105:
    # os circuitos continuam ordenados por grupo elétrico, porém grupos
    # diferentes podem ocupar o mesmo trilho. Só abre um novo trilho quando
    # a capacidade física de módulos do trilho atual terminar.
    trilhos_circuitos = max(
        1,
        int(math.ceil(
            sum(
                max(1, int(d.get("modulos", 1) or 1))
                for d in circuitos
            )
            / max(1, colunas)
        ))
    )
    # Rev.57 — reserva inferior adicional para os chicotes finais
    # agrupados por circuito.
    altura_corpo = 5.80 + trilhos_circuitos * 3.15
    altura = max(11.5, altura_corpo + 2.00)
    ybase = y0 - altura

    # Fase 13.6 Rev.105 — a moldura geral será fechada no final,
    # usando os limites reais das duas molduras internas.
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
        "VISTA FRONTAL - DIAGRAMA DE MONTAGEM E LIGACOES | FASE 13.6 REV.105",
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

    # Fase 13.6 Rev.105:
    # a moldura do diagrama será desenhada APÓS toda a geometria,
    # para envolver entrada da rede, QDC e saídas inferiores com
    # margem visual uniforme.
    # Barramentos PE e N laterais.
    # Rev.56 — 1 borne entrada + 1 borne DPS + 1 borne por circuito.
    qtd_pe = max(4, len(circuitos) + 2)
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

    # Fase 13.6 Rev.105:
    # a fileira superior é dimensionada pela quantidade real de módulos
    # DG + DPS + IDRs. Nunca descarta o último aparelho por falta de folga.
    total_modulos_gerais = sum(
        max(
            1,
            int(
                d.get(
                    "modulos",
                    1
                )
                or 1
            )
        )
        for d in gerais
    )

    gap_geral = 0.06
    qtd_gaps_gerais = max(
        0,
        len(gerais) - 1
    )

    largura_util_gerais = max(
        1.0,
        (
            din_x2
            - din_x1
            - 0.30
            - qtd_gaps_gerais * gap_geral
        )
    )

    # Não comprimir os dispositivos superiores: a largura física é
    # sempre 0,45 x quantidade de polos.
    modulo_w_geral = modulo_w

    # Fase 13.6 Rev.105 — eixo geométrico único do "miolo" do QDC.
    # Todo o conjunto interno é centralizado entre os barramentos PE e N.
    # A fileira superior e as fileiras inferiores compartilham a mesma
    # lateral esquerda de referência, evitando deslocamento visual.
    centro_miolo_qdc = (pe["x"] + neutro["x"]) / 2.0

    largura_superior_real = (
        total_modulos_gerais * modulo_w_geral
        + max(0, len(gerais) - 1) * gap_geral
    )

    # Calcula a maior largura efetivamente usada por uma fileira inferior.
    larguras_fileiras_inferiores = []
    idx_largura = 0
    while idx_largura < len(circuitos):
        modulos_usados = 0
        qtd_dispositivos_fileira = 0
        largura_fileira = 0.0

        while idx_largura < len(circuitos):
            d_larg = circuitos[idx_largura]
            mod_larg = max(1, int(d_larg.get("modulos", 1) or 1))
            if modulos_usados + mod_larg > colunas:
                break

            if qtd_dispositivos_fileira:
                largura_fileira += 0.10
            largura_fileira += mod_larg * modulo_w

            modulos_usados += mod_larg
            qtd_dispositivos_fileira += 1
            idx_largura += 1

        if qtd_dispositivos_fileira:
            larguras_fileiras_inferiores.append(largura_fileira)
        else:
            break

    largura_miolo_qdc = max(
        [largura_superior_real] + larguras_fileiras_inferiores
    )

    x_miolo_inicio = centro_miolo_qdc - largura_miolo_qdc / 2.0

    x = x_miolo_inicio
    geral_geom = []

    for d in gerais:
        geom = _desenhar_dispositivo(
            msp,
            d,
            x,
            top_rail_y - 0.85,
            modulo_w_geral,
            disp_h,
            L,
            LT
        )
        geral_geom.append(
            (
                d,
                geom
            )
        )
        x = (
            geom["x2"]
            + gap_geral
        )

    _desenhar_trilho_com_vazios(
        msp,
        din_x1,
        din_x2,
        top_rail_y - 0.05,
        L,
        [g for _, g in geral_geom]
    )

    # Todos os dispositivos gerais calculados precisam estar presentes
    # na vista frontal; não existe descarte visual de DR/DPS/DG.
    if len(
        geral_geom
    ) != len(
        gerais
    ):
        raise RuntimeError(
            "Falha ao representar todos os dispositivos gerais do QDC."
        )

    # Entrada elétrica e distribuição superior por fase.
    dg_geoms = [
        (d, g)
        for d, g in geral_geom
        if d.get("tipo") == "DG"
    ]

    # Barramentos de fase separados verticalmente.
    # Todas as derivações "morrem" exatamente na barra da respectiva fase.
    # Fase 13.6 Rev.105:
    # corredores exclusivos para A/B/C. O afastamento é propositalmente
    # maior para impedir que uma derivação vertical coincida visualmente
    # com o barramento horizontal de outra fase.
    ESPACAMENTO_BARRAMENTOS_FASE = 0.30
    # Fase 13.6 Rev.105 — grade vertical equidistante das seis linhas
    # As seis linhas/cabos principais do QDC passam a ocupar níveis paralelos
    # com passo único. Isso evita a sensação de linhas comprimidas em uma
    # região e abertas em outra, mantendo A/B/C alinhadas aos bornes do DG.
    # Fase 13.6 Rev.105:
    # O espaçamento vertical é calculado conforme a quantidade REAL
    # de cabos presentes na entrada. Assim monofásico, bifásico e
    # trifásico mantêm a mesma proporção visual.
    #
    # Fórmula:
    # espaçamento = distância disponível / quantidade de cabos
    #
    # A referência superior é o PE e a inferior é o topo do DG.
    dg_ref_geom = dg_geoms[0][1] if dg_geoms else None
    y_topo_dg = (
        dg_ref_geom["y2"]
        if dg_ref_geom is not None
        else top_rail_y + 0.75
    )

    fases_presentes = _fases_alimentador(mapa)
    tem_neutro_grade = _tem_neutro_alimentador(mapa)
    tem_pe_grade = _tem_pe_alimentador(mapa)

    # Quantidade REAL de cabos da entrada:
    # fases existentes + N (se houver) + PE (se houver).
    qtd_cabos_grade = max(
        1,
        len(fases_presentes)
        + (1 if tem_neutro_grade else 0)
        + (1 if tem_pe_grade else 0)
    )

    # Referência superior = linha PE/N de entrada.
    # Referência inferior = topo físico do DG.
    y_pe_superior = qy_top - 0.62
    distancia_disponivel = max(
        0.60,
        y_pe_superior - y_topo_dg
    )

    # REGRA EXATA SOLICITADA:
    # espaçamento = distância entre cabo PE e topo do DG / nº de cabos
    ESPACAMENTO_VERTICAL_CABOS = (
        distancia_disponivel
        / qtd_cabos_grade
    )

    # PE e N de entrada compartilham o nível superior,
    # seguindo em sentidos opostos.
    niveis_cabos_qdc = {
        "PE": y_pe_superior,
        "N": y_pe_superior,
    }

    # As fases ocupam níveis sucessivos abaixo da linha PE/N.
    for idx, token in enumerate(
        fases_presentes,
        start=1
    ):
        niveis_cabos_qdc[token] = (
            y_pe_superior
            - idx * ESPACAMENTO_VERTICAL_CABOS
        )

    # O neutro de alimentação dos DRs ocupa o próximo nível da grade,
    # também calculado pelo MESMO espaçamento.
    indice_n_idr = (
        len(fases_presentes)
        + 1
    )
    niveis_cabos_qdc["N_IDR"] = (
        y_pe_superior
        - indice_n_idr * ESPACAMENTO_VERTICAL_CABOS
    )

    barramentos_y = {
        token: niveis_cabos_qdc[token]
        for token in fases_presentes
        if token in niveis_cabos_qdc
    }

    # REV.14 — regra dos barramentos laterais:
    # - entrada PE -> 1º borne do barramento PE;
    # - entrada N  -> 1º borne do barramento N, no mesmo alinhamento do PE;
    # - alimentação N dos IDRs -> 2º borne do barramento N;
    # - do 2º borne, N segue à esquerda e depois sobe ao alinhamento calculado;
    # - nó azul apenas nos pontos reais de derivação.

    if dg_geoms:
        dg_disp, dg = dg_geoms[0]

        fases_entrada = _fases_alimentador(
            mapa
        )

        tem_neutro = _tem_neutro_alimentador(
            mapa
        )

        tem_pe = _tem_pe_alimentador(
            mapa
        )

        # ====================================================
        # FASE 13.6 REV.105 — ENTRADA DA REDE
        # ====================================================
        # Convenção visual definida pelo usuário:
        # A | B | C | PE | N
        #
        # A/B/C nascem EXATAMENTE alinhadas aos bornes do DG.
        # PE e N continuam à direita, usando o mesmo passo horizontal
        # dos bornes do DG. Isso elimina cruzamentos/desvios desnecessários
        # logo na entrada do diagrama.
        polos_dg = _centros_polos(dg)

        # Passo real entre polos do DG; fallback apenas para geometria atípica.
        if len(polos_dg) >= 2:
            ESPACAMENTO_ENTRADA = abs(polos_dg[1] - polos_dg[0])
        else:
            ESPACAMENTO_ENTRADA = 0.42

        x_por_condutor = {}
        for idx_fase, token in enumerate(fases_entrada):
            if idx_fase < len(polos_dg):
                x_por_condutor[token] = polos_dg[idx_fase]

        # Após a última fase: primeiro PE e depois N.
        x_ultima_fase = (
            polos_dg[min(len(fases_entrada), len(polos_dg)) - 1]
            if polos_dg and fases_entrada
            else dg["cx"]
        )
        proximo_x = x_ultima_fase + ESPACAMENTO_ENTRADA
        if tem_pe:
            x_por_condutor["PE"] = proximo_x
            proximo_x += ESPACAMENTO_ENTRADA
        if tem_neutro:
            x_por_condutor["N"] = proximo_x

        y_inicio_entrada = qy_top - 0.15
        y_rotulos_entrada = qy_top - 0.38

        # Fases: ligação vertical direta, sem degrau horizontal.
        for idx_fase, token in enumerate(fases_entrada):
            if idx_fase >= len(polos_dg) or token not in x_por_condutor:
                break
            x_fase = x_por_condutor[token]
            _line(
                msp,
                (x_fase, y_inicio_entrada),
                (x_fase, dg["y2"]),
                _layer_por_token(token)
            )
            _text(msp, token, x_fase - 0.03, y_rotulos_entrada, 0.080, LT)

        # PE vem antes do N e segue diretamente ao barramento de proteção.
        if tem_pe:
            x_pe = x_por_condutor["PE"]
            _polyline(
                msp,
                [
                    (x_pe, y_inicio_entrada),
                    (x_pe, niveis_cabos_qdc.get("PE", qy_top - 0.62)),
                    (pe["x"], niveis_cabos_qdc.get("PE", qy_top - 0.62)),
                    (pe["x"], _y_borne_barramento(pe, 0)),
                ],
                LPE
            )
            _text(msp, "PE", x_pe - 0.05, y_rotulos_entrada, 0.080, LT)

        # Fase 13.6 Rev.105:
        # O N de entrada deve espelhar exatamente a geometria do PE:
        # sai da entrada, atinge o MESMO alinhamento horizontal do PE
        # e segue para a direita até o 1º borne do barramento N.
        if tem_neutro:
            x_n = x_por_condutor["N"]

            y_pe_referencia = niveis_cabos_qdc.get(
                "PE",
                qy_top - 0.62
            )

            _polyline(
                msp,
                [
                    (x_n, y_inicio_entrada),
                    (x_n, y_pe_referencia),
                    (neutro["x"], y_pe_referencia),
                    (neutro["x"], _y_borne_barramento(neutro, 0)),
                ],
                LN
            )
            _text(
                msp,
                "N",
                x_n - 0.03,
                y_rotulos_entrada,
                0.080,
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

        # Título em linha própria, acima das identificações A/B/C/N/PE.
        _text(
            msp,
            rotulo_entrada,
            din_x1,
            qy_top + 0.02,
            0.080,
            LT
        )

    # Rev.39 — o PE horizontal dos DPS participa da grade harmônica
    # da primeira fileira. Por isso sua geometria é coletada primeiro e
    # desenhada somente depois que os níveis horizontais forem calculados.
    # Rev.51 — saídas horizontais pós-DG também participarão
    # da grade global do primeiro vão.
    saidas_pos_dg_pendentes = []
    saidas_pos_dg_desenhadas = False

    dps_geom_pe = []
    pe_dps_desenhado = False

    if geral_geom:
        fases_disponiveis = _fases_alimentador(
            mapa
        )

        # ----------------------------------------------------
        # FASE 13.6 REV.105 — CONVENÇÃO DE NÓS DE DERIVAÇÃO
        # ----------------------------------------------------
        # Primeiro levantamos TODOS os pontos reais ligados a cada fase.
        # Assim o barramento termina exatamente na última ligação:
        # nesse último ponto a linha apenas vira/desce e NÃO recebe bolinha.
        pontos_superiores_por_fase = {
            token: []
            for token in fases_disponiveis
        }

        # Rev.43 — TOPOLOGIA ELÉTRICA PÓS-DG
        #
        # Regra adotada para esta vista:
        #   REDE A/B/C -> DG -> distribuição A/B/C -> DPS/IDRs/circuitos.
        #
        # Portanto, nenhuma derivação de fase destinada aos IDRs ou DPS
        # nasce mais do lado de entrada do DG.
        #
        # Os barramentos horizontais superiores continuam visualmente acima
        # da fileira, mas são energizados pelos BORNES INFERIORES do DG
        # através de corredores laterais externos ao corpo do aparelho.
        #
        # PE não atravessa DG/IDR.
        # N segue pelos barramentos N e pelos IDRs que efetivamente o utilizam.

        for d, g in geral_geom:
            tipo_d = str(
                d.get(
                    "tipo",
                    ""
                )
                or ""
            ).upper()

            if tipo_d == "DPS":
                fases_d = _fases_do_texto(
                    d.get(
                        "fase",
                        ""
                    )
                )
                if not fases_d:
                    continue
                token = fases_d[0]

                if token in pontos_superiores_por_fase:
                    pontos_superiores_por_fase[token].append(
                        _centros_polos(g)[0]
                    )

            elif tipo_d == "IDR":
                mapa_polos = _mapa_condutores_polos(
                    d,
                    g
                )

                for token in ("A", "B", "C"):
                    if (
                        token in pontos_superiores_por_fase
                        and token in (
                            d.get(
                                "condutores",
                                []
                            )
                            or []
                        )
                        and token in mapa_polos
                    ):
                        pontos_superiores_por_fase[token].append(
                            mapa_polos[token]
                        )

        # Rev.44 — origem física pós-DG de cada fase.
        # Usada para avaliar corretamente a bolinha no ponto em que a
        # saída do DG encontra o barramento de distribuição.
        origem_pos_dg_por_fase = {}

        # Fonte real das barras superiores = lado de CARGA do DG.
        if dg_geoms:
            dg_disp, dg_geom = dg_geoms[0]

            qtd_fases_dg = len(fases_disponiveis)
            if int(dg_geom.get("modulos", 0) or 0) < qtd_fases_dg:
                raise RuntimeError(
                    "DG com número de polos inferior ao número de fases "
                    "do alimentador. Revise o fornecimento/proteção geral."
                )

            # Corredores laterais entre o barramento PE e o DG.
            # Distribuímos um corredor por fase para não sobrepor A/B/C.
            x_lim_esq = pe["x"] + 0.26
            x_lim_dir = dg_geom["x1"] - 0.14

            largura_corredores = max(
                0.18,
                x_lim_dir - x_lim_esq
            )

            if qtd_fases_dg <= 1:
                xs_riser = [
                    (x_lim_esq + x_lim_dir) / 2.0
                ]
            else:
                passo_x_riser = largura_corredores / (
                    qtd_fases_dg + 1
                )
                xs_riser = [
                    x_lim_esq + (i + 1) * passo_x_riser
                    for i in range(qtd_fases_dg)
                ]

            for idx_fase, token in enumerate(fases_disponiveis):
                x_polo_dg = _polo_para_fase(
                    dg_disp,
                    dg_geom,
                    token
                )
                x_riser = xs_riser[
                    min(idx_fase, len(xs_riser) - 1)
                ]

                # Rev.51 — a saída horizontal pós-DG não usa mais
                # espaçamento fixo. Ela é armazenada e desenhada depois,
                # junto com TODOS os demais cabos horizontais do primeiro vão.
                saidas_pos_dg_pendentes.append({
                    "token": token,
                    "x_polo_dg": float(x_polo_dg),
                    "x_riser": float(x_riser),
                    "y_dg": float(dg_geom["y1"]),
                    "y_barramento": float(barramentos_y[token]),
                })

                # O ponto onde o riser encontra a barra é a origem física
                # da distribuição pós-DG.
                pontos_superiores_por_fase[token].append(
                    x_riser
                )
                origem_pos_dg_por_fase[token] = x_riser

        # Barramentos de distribuição pós-DG.
        # Cada fase vai da origem pós-DG até o último consumidor daquela fase.
        for token in fases_disponiveis:
            pontos_token = sorted(
                pontos_superiores_por_fase.get(
                    token,
                    []
                )
            )

            if len(pontos_token) >= 2:
                _line(
                    msp,
                    (
                        min(pontos_token),
                        barramentos_y[token]
                    ),
                    (
                        max(pontos_token),
                        barramentos_y[token]
                    ),
                    _layer_por_token(token)
                )

                # Rev.45 — o encontro do riser com o barramento não é
                # tratado automaticamente como nó de saída do DG.
                # Se naquele ponto surgir uma derivação real por outra lógica,
                # a regra topológica global poderá registrá-la normalmente.

        # DPS: fase PÓS-DG -> polo físico do DPS -> PE.
        # Rev.19: o PE dos DPS é representado como um único tronco
        # horizontal. L1/L2... recebem nó apenas quando são derivações
        # reais; o último DPS é apenas a curva final horizontal -> vertical.
        for d, g in geral_geom:
            if d.get("tipo") != "DPS":
                continue

            token = _fases_do_texto(
                d.get(
                    "fase"
                )
            )[0]

            polos_dps = _centros_polos(
                g
            )
            x_polo = polos_dps[0]

            _line(
                msp,
                (
                    x_polo,
                    barramentos_y[token]
                ),
                (
                    x_polo,
                    g["y2"]
                ),
                _layer_por_token(
                    token
                )
            )

            _desenhar_no_se_derivacao(
                msp,
                x_polo,
                barramentos_y[token],
                token,
                pontos_superiores_por_fase.get(
                    token,
                    []
                )
            )
            # Rev.42 — legenda L1/L2/L3 removida dos DPS.

            dps_geom_pe.append((d, g))

        # Rev.39: desenho do tronco PE dos DPS adiado para a grade
        # harmônica da primeira fileira, evitando coincidência com fase A.

        # IDRs: cada fase PÓS-DG entra em seu polo físico correspondente.
        for d, g in geral_geom:
            if d.get("tipo") != "IDR":
                continue

            mapa_polos = _mapa_condutores_polos(
                d,
                g
            )

            fases_idr = [
                token
                for token in ("A", "B", "C")
                if token in (
                    d.get(
                        "condutores",
                        []
                    )
                    or []
                )
            ]

            for token in fases_idr:
                if token not in barramentos_y:
                    continue

                xx = mapa_polos.get(
                    token
                )

                if xx is None:
                    continue

                _line(
                    msp,
                    (
                        xx,
                        g["y2"]
                    ),
                    (
                        xx,
                        barramentos_y[token]
                    ),
                    _layer_por_token(
                        token
                    )
                )

                _desenhar_no_se_derivacao(
                    msp,
                    xx,
                    barramentos_y[token],
                    token,
                    pontos_superiores_por_fase.get(
                        token,
                        []
                    )
                )

            # O neutro dos IDRs é montado depois em uma única linha,
            # derivada exclusivamente do 2º borne do barramento N.

    # ========================================================
    # FASE 13.6 REV.105 — NEUTRO DOS IDRs PELO 2º BORNE
    # ========================================================
    # Regras:
    # - N de entrada usa o 1º borne do barramento N.
    # - alimentação N dos IDRs usa o 2º borne do barramento N.
    # - do 2º borne, o cabo segue PRIMEIRO para a esquerda;
    # - depois sobe verticalmente até o nível correto da grade calculada;
    # - nesse nível segue horizontalmente e deriva para os bornes N dos IDRs;
    # - bolinha azul somente onde existe derivação real.
    idrs_com_neutro = []

    for d_idr, g_idr in geral_geom:
        if d_idr.get("tipo") != "IDR":
            continue

        condutores_idr = d_idr.get("condutores", []) or []
        if "N" not in condutores_idr:
            continue

        mapa_polos_idr = _mapa_condutores_polos(
            d_idr,
            g_idr
        )
        if "N" not in mapa_polos_idr:
            continue

        idrs_com_neutro.append(
            (d_idr, g_idr, mapa_polos_idr["N"])
        )

    if idrs_com_neutro:
        y_borne_n_2 = _y_borne_barramento(
            neutro,
            1
        )

        # O alinhamento do N dos IDRs é exatamente o nível N_IDR
        # calculado pela grade dinâmica:
        # (PE -> topo do DG) / quantidade real de cabos.
        y_alinhamento_n_idr = niveis_cabos_qdc[
            "N_IDR"
        ]

        xs_n_idr = sorted(
            x_n_idr
            for _, _, x_n_idr in idrs_com_neutro
        )

        x_idr_mais_direita = max(xs_n_idr)
        x_idr_mais_esquerda = min(xs_n_idr)

        # Pequeno recuo à esquerda do barramento N antes da subida.
        x_recuo_n = (
            neutro["x"]
            - max(
                0.22,
                ESPACAMENTO_VERTICAL_CABOS
            )
        )

        # 2º borne -> esquerda -> sobe até o alinhamento calculado.
        _polyline(
            msp,
            [
                (neutro["x"], y_borne_n_2),
                (x_recuo_n, y_borne_n_2),
                (x_recuo_n, y_alinhamento_n_idr),
            ],
            LN
        )

        # Linha principal do N dos IDRs, no alinhamento correto.
        _line(
            msp,
            (x_recuo_n, y_alinhamento_n_idr),
            (x_idr_mais_esquerda, y_alinhamento_n_idr),
            LN
        )

        # Derivações para os bornes N superiores.
        for d_idr, g_idr, x_n_idr in idrs_com_neutro:
            _line(
                msp,
                (x_n_idr, y_alinhamento_n_idr),
                (x_n_idr, g_idr["y2"]),
                LN
            )

            # Bolinha azul apenas quando o ponto é uma derivação real
            # e a linha principal continua para a esquerda.
            if x_n_idr > x_idr_mais_esquerda + 1e-9:
                _no_fase_preenchido(
                    msp,
                    x_n_idr,
                    y_alinhamento_n_idr,
                    "N"
                )

    # -------------------------
    # Fileiras inferiores: circuitos
    # -------------------------
    y_rail = top_rail_y - 3.15
    idx_circ = 0
    circuitos_geom = []

    # Rev.68 — níveis horizontais já usados à esquerda no primeiro vão.
    # Os neutros podem usar os MESMOS Ys do lado direito sem sobreposição.
    niveis_compartilhados_n68 = []

    # Rev.33 — memoriza a última ramificação de cada saída física.
    # Chave: (identificador da fonte, fase) -> último Y atendido.
    # Permite usar uma única saída do DR/DG e ramificar nas fileiras.
    troncos_fonte_fase = {}

    # Rev.18: a fileira inferior usa exatamente a mesma lateral
    # esquerda do primeiro dispositivo superior aprovado.
    x_alinhamento_dispositivos = (
        x_miolo_inicio
        if gerais
        else centro_miolo_qdc - largura_miolo_qdc / 2.0
    )

    # Rev.55 — cota GLOBAL das pontas finais dos circuitos.
    #
    # Primeira fileira:
    #   y_rail_inicial = top_rail_y - 3.15
    #
    # Última fileira real:
    #   y_rail_ultima = y_rail_inicial
    #                   - (trilhos_circuitos - 1) * 3.15
    #
    # Todas as saídas de TODOS os DJs, inclusive os das fileiras
    # superiores, seguem até abaixo da última fileira física.
    y_rail_inicial_circuitos = top_rail_y - 3.15
    y_rail_ultima_fileira = (
        y_rail_inicial_circuitos
        - (trilhos_circuitos - 1) * 3.15
    )

    y_saida_circuito_global = y_rail_ultima_fileira - 2.28
    y_identificacao_saida_global = y_saida_circuito_global - 0.22

    # ========================================================
    # FASE 13.6 REV.105 — GRADE DA SAÍDA FINAL DO QDC
    # ========================================================
    # Nesta revisão o H fica explicitamente definido.
    #
    # LIMITE SUPERIOR:
    # 0,10 m abaixo da base do pequeno retângulo terminal inferior
    # (retângulo = 0,075 m de altura).
    #
    # LIMITE INFERIOR:
    # 0,20 m acima da antiga cota global de saída.
    #
    # Portanto:
    # H = limite_superior - limite_inferior
    # E = H / (Q + 1)
    #
    # Q = TODOS os condutores finais que precisarão de trecho
    # horizontal nesta faixa: fases + neutros + PE.
    #
    # Cada condutor recebe UM nível Y exclusivo. A partir desse
    # nível ele segue na HORIZONTAL e só vira PARA BAIXO quando
    # chega à posição definitiva do seu circuito.
    mapa_nivel_saida_rev91 = {}
    mapa_x_handoff_rev91 = {}

    q_condutores_saida_rev91 = 0
    dados_tokens_saida_rev91 = []

    for d_rev91 in circuitos:
        fases_rev91 = _fases_do_texto(
            d_rev91.get("fase", "")
        )
        tokens_rev91 = list(fases_rev91)

        if (
            len(fases_rev91) == 1
            and int(d_rev91.get("modulos", 1) or 1) == 1
        ):
            tokens_rev91.append("N")

        tokens_rev91.append("PE")

        ident_rev91 = str(
            d_rev91.get("identificador", "") or ""
        ).strip().upper()

        for token_rev91 in tokens_rev91:
            dados_tokens_saida_rev91.append(
                (ident_rev91, token_rev91)
            )

    q_condutores_saida_rev91 = len(
        dados_tokens_saida_rev91
    )

    # Geometria determinística da última linha de DJs.
    y1_ultima_fileira_rev91 = (
        y_rail_ultima_fileira - 0.85
    )

    # Base do retângulo terminal inferior:
    # y1 do DJ - 0,075 m.
    y_base_terminal_inferior_rev91 = (
        y1_ultima_fileira_rev91 - 0.075
    )

    y_limite_superior_saida_rev91 = (
        y_base_terminal_inferior_rev91 - 0.10
    )

    y_limite_inferior_saida_rev91 = (
        y_saida_circuito_global + 0.20
    )

    # Fase 13.6 Rev.105:
    # por decisão de projeto, a faixa H da saída final passa a ser
    # FIXA em 2,00 m para melhorar a leitura do diagrama.
    h_saida_rev91 = 2.00

    # O limite inferior passa a ser consequência direta de H.
    y_limite_inferior_saida_rev91 = (
        y_limite_superior_saida_rev91
        - h_saida_rev91
    )

    e_saida_rev91 = (
        h_saida_rev91
        / (q_condutores_saida_rev91 + 1)
        if q_condutores_saida_rev91 > 0
        else 0.0
    )

    for idx_saida_rev91, chave_saida_rev91 in enumerate(
        dados_tokens_saida_rev91,
        start=1
    ):
        mapa_nivel_saida_rev91[
            chave_saida_rev91
        ] = (
            y_limite_superior_saida_rev91
            - idx_saida_rev91 * e_saida_rev91
        )

    def _nivel_final_rev91(disp_rev91, token_rev91):
        ident_rev91 = str(
            disp_rev91.get("identificador", "") or ""
        ).strip().upper()

        return mapa_nivel_saida_rev91.get(
            (ident_rev91, str(token_rev91).upper()),
            y_saida_circuito_global
        )

    def _registrar_x_handoff_rev91(
        disp_rev91,
        token_rev91,
        x_rev91
    ):
        ident_rev91 = str(
            disp_rev91.get("identificador", "") or ""
        ).strip().upper()

        mapa_x_handoff_rev91[
            (ident_rev91, str(token_rev91).upper())
        ] = float(x_rev91)

    def _x_handoff_rev91(
        disp_rev91,
        token_rev91,
        fallback_rev91
    ):
        ident_rev91 = str(
            disp_rev91.get("identificador", "") or ""
        ).strip().upper()

        return float(
            mapa_x_handoff_rev91.get(
                (
                    ident_rev91,
                    str(token_rev91).upper()
                ),
                fallback_rev91
            )
        )

    # ========================================================
    # FASE 13.6 REV.105 — DESTINO FINAL PRÉ-CALCULADO
    # ========================================================
    # Mesma filosofia usada com sucesso entre os níveis de DJs:
    # o cabo horizontal já nasce sabendo onde termina.
    #
    # Importante: usa "circuitos", que já existe aqui.
    # Não usa "circuitos_geom", pois essa lista ainda será montada
    # durante o desenho das fileiras.
    espaco_interno_rev96 = 0.08
    espaco_entre_circuitos_rev96 = 0.35

    mapa_x_final_rev96 = {}
    mapa_centro_circuito_rev96 = {}

    dados_saida_rev96 = []

    for d96 in circuitos:
        fases96 = _fases_do_texto(
            d96.get("fase", "")
        )
        tokens96 = list(fases96)

        if (
            len(fases96) == 1
            and int(d96.get("modulos", 1) or 1) == 1
        ):
            tokens96.append("N")

        tokens96.append("PE")
        dados_saida_rev96.append(
            (d96, tokens96)
        )

    larguras_rev96 = [
        (
            0.0
            if len(tokens96) <= 1
            else (len(tokens96) - 1)
            * espaco_interno_rev96
        )
        for _, tokens96 in dados_saida_rev96
    ]

    largura_total_rev96 = (
        sum(larguras_rev96)
        + max(0, len(dados_saida_rev96) - 1)
        * espaco_entre_circuitos_rev96
    )

    x_cursor_rev96 = (
        (din_x1 + din_x2) / 2.0
        - largura_total_rev96 / 2.0
    )

    for idx96, (d96, tokens96) in enumerate(
        dados_saida_rev96
    ):
        largura96 = larguras_rev96[idx96]

        if len(tokens96) <= 1:
            x_centro96 = x_cursor_rev96
            xs96 = [x_centro96]
        else:
            x_centro96 = (
                x_cursor_rev96 + largura96 / 2.0
            )
            x_primeiro96 = (
                x_centro96
                - (len(tokens96) - 1)
                * espaco_interno_rev96 / 2.0
            )
            xs96 = [
                x_primeiro96
                + i96 * espaco_interno_rev96
                for i96 in range(len(tokens96))
            ]

        ident96 = str(
            d96.get("identificador", "") or ""
        ).strip().upper()

        mapa_centro_circuito_rev96[
            ident96
        ] = float(x_centro96)

        for token96, x96 in zip(tokens96, xs96):
            mapa_x_final_rev96[
                (ident96, str(token96).upper())
            ] = float(x96)

        x_cursor_rev96 += (
            largura96
            + espaco_entre_circuitos_rev96
        )

    def _x_final_rev96(disp96, token96, fallback96):
        ident96 = str(
            disp96.get("identificador", "") or ""
        ).strip().upper()

        return float(
            mapa_x_final_rev96.get(
                (
                    ident96,
                    str(token96).upper()
                ),
                fallback96
            )
        )

    for trilho in range(trilhos_circuitos):
        x = x_alinhamento_dispositivos
        usados = 0

        grupos_na_fileira = []

        while idx_circ < len(circuitos):
            d = circuitos[idx_circ]
            grupo_d = str(
                d.get("grupo", "") or "SEM DR"
            ).strip().upper()

            # Mantém a sequência SEM DR -> DR1 -> DR2 -> DR3...
            # mas NÃO força mudança de trilho na troca de grupo.
            if grupo_d not in grupos_na_fileira:
                grupos_na_fileira.append(grupo_d)

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

            # Rev.22: identificação de condutores fica concentrada
            # na parte inferior do QDC, junto à saída do circuito.
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

        # Fase 13.6 Rev.105 — SAÍDAS DOS CIRCUITOS
        # ------------------------------------------------------------
        # Cada circuito sai pela parte inferior do respectivo disjuntor
        # com condutores verticais retos e identificação alinhada.
        #
        # 1P / 127 V: F + N + PE
        # 2P / 220 V: F + F + PE
        # 3P:         F + F + F + PE
        #
        # As saídas de todos os circuitos terminam na mesma cota global abaixo da última fileira.
        # Rev.54 — corredores técnicos precisam existir em TODAS
        # as fileiras, pois a distribuição de N/PE pode referenciá-los
        # mesmo quando a ponta final do circuito não é desenhada ali.
        y_corredor_pe = y_rail - 1.74
        y_corredor_n = y_rail - 1.92

        # Rev.55 — TODOS os circuitos têm sua ponta final abaixo
        # da última fileira física do QDC.
        #
        # Portanto não existe mais y_saida_circuito local por trilho.
        # A mesma cota global é usada por fases, neutro e PE.
        y_saida_circuito = y_saida_circuito_global
        y_identificacao_saida = y_identificacao_saida_global

        if desta_fileira_geom:
            for d_saida, g_saida in circuitos_geom:
                if abs(
                    g_saida["y1"] - (y_rail - 0.85)
                ) >= 0.05:
                    continue

                fases_saida = _fases_do_texto(
                    d_saida.get("fase", "")
                )
                polos_saida = _centros_polos(g_saida)

                # Fases: entram/saiem pelo borne real, mas a passagem
                # vertical prolongada é deslocada para fora do corpo do DJ.
                # Assim um condutor de outro circuito nunca aparece "por dentro"
                # de um disjuntor apenas porque compartilha o mesmo eixo X.
                xs_fases_saida = []
                for idx_fase_saida, fase_saida in enumerate(fases_saida):
                    x_borne_fase = _polo_para_fase(
                        d_saida,
                        g_saida,
                        fase_saida
                    )
                    xs_fases_saida.append(x_borne_fase)

                    # Rev.77 — quando houver 3ª linha física, o 1º condutor
                    # do 1º DJ da 2ª linha física sai 0,10 após o terminal,
                    # vira 0,10 para a esquerda e segue reto até a saída.
                    primeira_geom_da_fileira = min(
                        desta_fileira_geom,
                        key=lambda gg: float(gg["x1"])
                    ) if desta_fileira_geom else None

                    eh_primeiro_dj_segunda_fileira = (
                        # Rev.76 — contagem física do usuário:
                        # 1ª linha = DG/DPS/DRs;
                        # 2ª linha = trilho terminal 0;
                        # 3ª linha = trilho terminal 1.
                        trilhos_circuitos >= 2
                        and trilho == 0
                        and primeira_geom_da_fileira is not None
                        and abs(
                            float(g_saida["x1"])
                            - float(primeira_geom_da_fileira["x1"])
                        ) <= 1e-6
                    )

                    if eh_primeiro_dj_segunda_fileira and idx_fase_saida == 0:
                        x_desvio_rev75 = float(x_borne_fase) - 0.10
                        # Rev.77 — o 0,10 começa APÓS o pequeno
                        # retângulo terminal inferior (altura = 0,075).
                        # A parte visível do cabo sai da base do terminal e
                        # percorre 0,10 antes de virar 0,10 à esquerda.
                        y_base_terminal_rev77 = float(g_saida["y1"]) - 0.075
                        y_quebra_rev75 = y_base_terminal_rev77 - 0.10

                        _polyline(
                            msp,
                            [
                                (x_borne_fase, g_saida["y1"]),
                                (x_borne_fase, y_quebra_rev75),
                                (x_desvio_rev75, y_quebra_rev75),
                                # Rev.78 — permanece no eixo deslocado até
                                # a saída. Não existe retorno horizontal
                                # excedente para a direita.
                                (
                                    x_desvio_rev75,
                                    _nivel_final_rev91(
                                        d_saida,
                                        fase_saida
                                    )
                                ),
                                (
                                    _x_final_rev96(
                                        d_saida,
                                        fase_saida,
                                        x_desvio_rev75
                                    ),
                                    _nivel_final_rev91(
                                        d_saida,
                                        fase_saida
                                    )
                                ),
                            ],
                            _layer_por_token(fase_saida)
                        )

                        _registrar_x_handoff_rev91(
                            d_saida,
                            fase_saida,
                            _x_final_rev96(
                                d_saida,
                                fase_saida,
                                x_desvio_rev75
                            )
                        )
                    else:
                        y_nivel_fase_rev91 = _nivel_final_rev91(
                            d_saida,
                            fase_saida
                        )

                        _line(
                            msp,
                            (x_borne_fase, g_saida["y1"]),
                            (x_borne_fase, y_nivel_fase_rev91),
                            _layer_por_token(fase_saida)
                        )

                        x_final_fase_rev96 = _x_final_rev96(
                            d_saida,
                            fase_saida,
                            x_borne_fase
                        )

                        if abs(
                            x_final_fase_rev96 - x_borne_fase
                        ) > 1e-9:
                            _line(
                                msp,
                                (x_borne_fase, y_nivel_fase_rev91),
                                (x_final_fase_rev96, y_nivel_fase_rev91),
                                _layer_por_token(fase_saida)
                            )

                        _registrar_x_handoff_rev91(
                            d_saida,
                            fase_saida,
                            x_final_fase_rev96
                        )

                # Rev.56 — PE não nasce mais como pequeno trecho local.
                # Cada circuito receberá seu próprio cabo a partir de um borne
                # exclusivo do barramento PE, roteado pela lateral do QDC.

                # N apenas nos circuitos monopolares.
                tem_neutro_saida = (
                    len(fases_saida) == 1
                    and int(d_saida.get("modulos", 1) or 1) == 1
                )

                if tem_neutro_saida:
                    # O N já é conduzido pelo bloco do respectivo grupo DR.
                    # Mantemos aqui apenas a referência lateral, fora do DJ.
                    x_n_saida = _x_passagem_lateral_disjuntor(
                        g_saida,
                        "dir",
                        0.12
                    )

                # Rev.57 — a identificação Cxx será desenhada
                # somente na zona final, centralizada no chicote do circuito.

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

                # ====================================================
                # Fase 13.6 Rev.105 — GRADE VERTICAL DINÂMICA DA FILEIRA
                # ====================================================
                # O vão entre a BASE dos dispositivos superiores e o TOPO
                # dos disjuntores desta fileira é dividido em faixas iguais,
                # uma para cada condutor que realmente passa na horizontal.
                #
                # Os condutores ficam equidistantes das duas faces:
                #   passo = vão / (quantidade_real_de_condutores + 1)
                #
                # A ordem vertical é por fase A -> B -> C e, dentro da fase,
                # segue a ordem dos grupos SEM DR -> DR1 -> DR2 -> DR3...
                # Rev.33:
                # - primeira fileira: usa o vão abaixo de DG/DPS/DRs;
                # - fileiras seguintes: usam o vão abaixo da fileira anterior.
                # Assim fases que não pertencem aos DJs da fileira de cima
                # não atravessam visualmente aquele conjunto.
                if trilho == 0:
                    # Entre equipamentos superiores e 1ª fileira de DJs:
                    # base física dos equipamentos superiores.
                    y_base_fileira_superior = min(
                        g_sup["y1"]
                        for _, g_sup in geral_geom
                    ) if geral_geom else (y_rail + 2.30)
                else:
                    # Rev.52 — mesma regra aprovada para QUALQUER vão
                    # entre fileiras consecutivas, inclusive 2º -> 3º nível.
                    #
                    # superior = fileira imediatamente anterior
                    # inferior = fileira atual
                    #
                    # A base física da fileira anterior e o topo físico da
                    # fileira atual definem o vão D usado na grade.
                    #
                    # A fileira anterior foi desenhada com:
                    #   y1 = (y_rail + 3.15) - 0.85
                    y1_fileira_anterior_esperado = (
                        (y_rail + 3.15) - 0.85
                    )

                    geoms_fileira_anterior = [
                        g_ant
                        for _, g_ant in circuitos_geom
                        if abs(
                            g_ant["y1"]
                            - y1_fileira_anterior_esperado
                        ) < 1e-6
                    ]

                    if geoms_fileira_anterior:
                        y_base_fileira_superior = min(
                            g_ant["y1"]
                            for g_ant in geoms_fileira_anterior
                        )
                    else:
                        # Fallback determinístico baseado na própria
                        # geometria padrão da fileira anterior.
                        y_base_fileira_superior = (
                            y1_fileira_anterior_esperado
                        )

                # Topo físico da fileira inferior/atual.
                y_topo_fileira_inferior = max(
                    g_inf["y2"]
                    for _, g_inf in desta_fileira
                )

                # Rev.48 — mapas de fontes DR precisam existir ANTES
                # da análise da grade horizontal.
                dr_disp_geom_por_grupo = {
                    str(d.get("grupo", "") or ""): (d, g)
                    for d, g in geral_geom
                    if d.get("tipo") == "IDR"
                }
                dr_geom_por_grupo = {
                    grupo_idr: par_idr[1]
                    for grupo_idr, par_idr
                    in dr_disp_geom_por_grupo.items()
                }

                # Rev.52 — GRADE GLOBAL POR VÃO, SEM REESCRITA POSTERIOR.
                #
                # A lista abaixo representa TODOS os cabos horizontais
                # que pertencem ao vão entre a fileira superior e a atual.
                #
                # Isso vale de forma independente para:
                #   1º -> 2º nível
                #   2º -> 3º nível
                #   3º -> 4º nível
                #   etc.
                #
                # Regra:
                # - cada grupo com >=2 DJs cria pista horizontal por fase usada;
                # - neutro cria pista horizontal quando houver >=2 destinos N;
                # - grupo com 1 DJ só entra na grade se origem e destino
                #   tiverem X diferentes (há trecho horizontal real);
                # - PE dos DPS só existe no primeiro vão.
                #
                # Assim não há "nível fantasma" e também não precisamos mover
                # entidades já desenhadas, evitando pontas e perda de nós.
                condutores_horizontais = []

                def _fonte_grade(grupo_grade):
                    par = dr_disp_geom_por_grupo.get(grupo_grade)
                    if par is not None:
                        return par
                    if (
                        str(grupo_grade).upper() == "SEM DR"
                        and dg_geoms
                    ):
                        return dg_geoms[0]
                    return (None, None)

                for grupo_grade, itens_grade in grupos_fileira:
                    usar_pista_grade = len(itens_grade) >= 2

                    # Fases A/B/C
                    fases_usadas_grade = []
                    for d_grade, g_grade in itens_grade:
                        for fase_grade in _fases_do_texto(
                            d_grade.get("fase", "")
                        ):
                            if (
                                fase_grade in ("A", "B", "C")
                                and fase_grade not in fases_usadas_grade
                            ):
                                fases_usadas_grade.append(fase_grade)

                    disp_fonte_grade, geom_fonte_grade = _fonte_grade(
                        grupo_grade
                    )

                    for fase_grade in ("A", "B", "C"):
                        if fase_grade not in fases_usadas_grade:
                            continue

                        deve_reservar = usar_pista_grade

                        if (
                            not deve_reservar
                            and len(itens_grade) == 1
                            and disp_fonte_grade
                            and geom_fonte_grade
                        ):
                            d_unico_grade, g_unico_grade = itens_grade[0]
                            x_origem_grade = _polo_para_fase(
                                disp_fonte_grade,
                                geom_fonte_grade,
                                fase_grade
                            )
                            x_destino_grade = _polo_para_fase(
                                d_unico_grade,
                                g_unico_grade,
                                fase_grade
                            )
                            deve_reservar = (
                                abs(x_origem_grade - x_destino_grade) > 1e-9
                            )

                        if deve_reservar:
                            condutores_horizontais.append(
                                (grupo_grade, fase_grade)
                            )

                    # Rev.65 — N não ocupa mais pista horizontal
                    # no miolo. Todo neutro final usa a lateral direita.
                # Rev.51 — somar também TODAS as saídas horizontais
                # pós-DG A/B/C no primeiro vão.
                if trilho == 0 and saidas_pos_dg_pendentes:
                    for saida_dg_grade in saidas_pos_dg_pendentes:
                        if abs(
                            saida_dg_grade["x_polo_dg"]
                            - saida_dg_grade["x_riser"]
                        ) > 1e-9:
                            condutores_horizontais.append(
                                ("__DG__", saida_dg_grade["token"])
                            )

                if trilho == 0 and dps_geom_pe:
                    condutores_horizontais.append(
                        ("__GERAL__", "PE")
                    )

                # Ordem visual: PE -> A -> B -> C -> N.
                ordem_fase_grade = {
                    "PE": -1,
                    "A": 0,
                    "B": 1,
                    "C": 2,
                    "N": 3,
                }
                condutores_horizontais = sorted(
                    condutores_horizontais,
                    key=lambda item: (
                        ordem_fase_grade.get(item[1], 99),
                        0 if item[0] == "__DG__" else 1,
                    )
                )

                qtd_condutores_horizontais = len(
                    condutores_horizontais
                )

                # Rev.52 — regra EXATA para o vão atual:
                #
                #   D = base física da fileira superior
                #       - topo físico da fileira inferior
                #
                #   Q = TODOS os cabos horizontais deste vão
                #
                #   E = D / (Q + 1)
                #
                # Cada cabo ocupa um único nível da grade deste vão.
                # Assim a margem superior, os espaços cabo-a-cabo e a
                # margem inferior ficam todos iguais a E.
                vao_vertical_condutores = (
                    y_base_fileira_superior
                    - y_topo_fileira_inferior
                )

                if vao_vertical_condutores <= 0:
                    raise RuntimeError(
                        "Geometria inválida no QDC: a base da fileira "
                        "superior não está acima do topo da fileira inferior."
                    )

                if qtd_condutores_horizontais > 0:
                    passo_vertical_condutores = (
                        vao_vertical_condutores
                        / (
                            qtd_condutores_horizontais
                            + 1
                        )
                    )
                else:
                    passo_vertical_condutores = (
                        vao_vertical_condutores
                    )

                niveis_horizontais = {}
                for indice_condutor, chave_condutor in enumerate(
                    condutores_horizontais
                ):
                    niveis_horizontais[chave_condutor] = (
                        y_base_fileira_superior
                        - (indice_condutor + 1)
                        * passo_vertical_condutores
                    )

                # Rev.52 — validação da grade do vão.
                # Especialmente importante entre 2º e 3º nível:
                # nenhum cabo horizontal contado em Q pode ficar sem nível.
                if len(niveis_horizontais) != len(condutores_horizontais):
                    raise RuntimeError(
                        "Falha na grade do QDC: nem todos os cabos "
                        "horizontais do vão receberam nível de espaçamento."
                    )

                for chave_grade, y_grade in niveis_horizontais.items():
                    if not (
                        y_topo_fileira_inferior
                        < y_grade
                        < y_base_fileira_superior
                    ):
                        raise RuntimeError(
                            "Falha na grade do QDC: cabo horizontal fora "
                            "do vão entre duas fileiras de disjuntores."
                        )

                # Rev.68 — memoriza níveis já existentes no lado esquerdo.
                # Prioridade: PE, A, B, C. Eles podem ser reutilizados pelos
                # neutros à direita porque os trechos seguem em sentidos opostos.
                if trilho == 0 and not niveis_compartilhados_n68:
                    ordem_n68 = ["PE", "A", "B", "C"]
                    for token_n68 in ordem_n68:
                        candidatos_n68 = [
                            float(y_n68)
                            for chave_n68, y_n68 in niveis_horizontais.items()
                            if (
                                isinstance(chave_n68, tuple)
                                and len(chave_n68) >= 2
                                and str(chave_n68[1]) == token_n68
                            )
                        ]
                        for y_n68 in sorted(set(candidatos_n68), reverse=True):
                            if all(
                                abs(y_n68 - existente_n68) > 1e-9
                                for existente_n68 in niveis_compartilhados_n68
                            ):
                                niveis_compartilhados_n68.append(y_n68)

                # Rev.51 — desenha as saídas A/B/C do DG usando os
                # níveis da MESMA grade global de todos os cabos horizontais.
                if (
                    trilho == 0
                    and saidas_pos_dg_pendentes
                    and not saidas_pos_dg_desenhadas
                ):
                    for saida_dg in saidas_pos_dg_pendentes:
                        token_dg = saida_dg["token"]
                        y_saida_dg = niveis_horizontais.get(
                            ("__DG__", token_dg)
                        )
                        if y_saida_dg is None:
                            continue

                        x_polo_dg = saida_dg["x_polo_dg"]
                        x_riser_dg = saida_dg["x_riser"]

                        _polyline(
                            msp,
                            [
                                (x_polo_dg, saida_dg["y_dg"]),
                                (x_polo_dg, y_saida_dg),
                                (x_riser_dg, y_saida_dg),
                                (x_riser_dg, saida_dg["y_barramento"]),
                            ],
                            _layer_por_token(token_dg)
                        )

                        # Rev.83 — nó REAL da saída do DG.
                        #
                        # O ponto recebe bolinha somente quando existem:
                        # U = retorno ao DG,
                        # D = continuidade para circuito SEM DR desta fase,
                        # L/R = ramo para a distribuição pós-DG.
                        #
                        # A decisão é lógica e a bolinha só será desenhada
                        # depois de todo o desenho/clipping.
                        ha_sem_dr_na_fase_rev83 = any(
                            (
                                str(
                                    d_circ_rev83.get(
                                        "grupo",
                                        ""
                                    )
                                    or "SEM DR"
                                ).strip().upper() == "SEM DR"
                                and token_dg in _fases_do_texto(
                                    d_circ_rev83.get("fase", "")
                                )
                            )
                            for d_circ_rev83 in circuitos
                        )

                        ha_ramo_pos_dg_rev83 = (
                            abs(
                                float(x_riser_dg)
                                - float(x_polo_dg)
                            ) > 1e-9
                        )

                        if (
                            ha_sem_dr_na_fase_rev83
                            and ha_ramo_pos_dg_rev83
                        ):
                            _registrar_no_logico_rev82(
                                msp,
                                x_polo_dg,
                                y_saida_dg,
                                token_dg,
                                0.035
                            )

                    saidas_pos_dg_desenhadas = True

                # Rev.39 — desenha uma única vez o PE dos DPS no
                # nível reservado pela própria grade harmônica.
                #
                # Entrada PE da rede continua no 1º borne (aprovado).
                # A distribuição PE para DPS passa a sair do 2º borne,
                # separando fisicamente entrada e distribuição.
                if (
                    trilho == 0
                    and dps_geom_pe
                    and not pe_dps_desenhado
                ):
                    y_pe_dps = niveis_horizontais.get(
                        ("__GERAL__", "PE")
                    )

                    if y_pe_dps is not None:
                        xs_pe_dps = sorted(
                            g_dps["cx"]
                            for _, g_dps in dps_geom_pe
                        )
                        x_ultimo_pe_dps = max(xs_pe_dps)
                        y_borne_pe_distribuicao = _y_borne_barramento(
                            pe,
                            1
                        )

                        # Rev.82 — PE dos DPS sobe ANTES de alcançar
                        # o barramento. O corredor vertical fica à direita
                        # do barramento PE (lado dos DPS) e entra
                        # horizontalmente no 2º borne.
                        x_pe_antes_barramento = pe["x"] + 0.28

                        _polyline(
                            msp,
                            [
                                (x_ultimo_pe_dps, y_pe_dps),
                                (x_pe_antes_barramento, y_pe_dps),
                                (
                                    x_pe_antes_barramento,
                                    y_borne_pe_distribuicao
                                ),
                                (
                                    pe["x"],
                                    y_borne_pe_distribuicao
                                ),
                            ],
                            LPE
                        )

                        for d_dps, g_dps in dps_geom_pe:
                            x_dps = g_dps["cx"]

                            _line(
                                msp,
                                (x_dps, g_dps["y1"]),
                                (x_dps, y_pe_dps),
                                LPE
                            )

                            # A regra global da Rev.37 decidirá se existe
                            # derivação real suficiente para desenhar bolinha.
                            _no_fase_preenchido(
                                msp,
                                x_dps,
                                y_pe_dps,
                                "PE"
                            )

                        pe_dps_desenhado = True

                # ====================================================
                # Rev.21 — CORREDORES VERTICAIS EXCLUSIVOS
                # ====================================================
                # Cada alimentação que cruza verticalmente o vão entre os
                # trilhos recebe um X exclusivo. O algoritmo evita:
                # - outros corredores verticais;
                # - centros de polos dos dispositivos;
                # - posições de saída N/PE junto aos circuitos.
                x_proibidos_corredor = []

                for _, g_sup in geral_geom:
                    x_proibidos_corredor.extend(
                        _centros_polos(g_sup)
                    )

                for _, g_inf in desta_fileira:
                    x_proibidos_corredor.extend(
                        _centros_polos(g_inf)
                    )
                    x_proibidos_corredor.extend(
                        [
                            g_inf["cx"] - 0.10,
                            g_inf["cx"] + 0.10,
                        ]
                    )

                corredores_verticais_usados = []
                corredor_vertical_por_chave = {}

                def _reservar_corredor_vertical(chave, x_preferido):
                    if chave in corredor_vertical_por_chave:
                        return corredor_vertical_por_chave[chave]

                    limite_esq = x_miolo_inicio + 0.06
                    limite_dir = (
                        x_miolo_inicio
                        + largura_miolo_qdc
                        - 0.06
                    )

                    # procura ao redor do ponto preferido em passos regulares
                    # até achar uma faixa vertical realmente livre.
                    candidatos = [float(x_preferido)]
                    for passo_busca in range(1, 80):
                        delta = passo_busca * 0.07
                        candidatos.append(float(x_preferido) + delta)
                        candidatos.append(float(x_preferido) - delta)

                    escolhido = None
                    for candidato in candidatos:
                        if candidato < limite_esq or candidato > limite_dir:
                            continue

                        ocupado_por_eixo = any(
                            abs(candidato - x_existente) < 0.070
                            for x_existente in (
                                x_proibidos_corredor
                                + corredores_verticais_usados
                            )
                        )

                        # Rev.26: condutor que apenas PASSA pela fileira
                        # não pode cruzar o interior de nenhum disjuntor.
                        ocupado_por_disjuntor = any(
                            float(g_bloq["x1"]) - 0.08
                            <= candidato
                            <= float(g_bloq["x2"]) + 0.08
                            for _, g_bloq in desta_fileira
                        )

                        if (
                            not ocupado_por_eixo
                            and not ocupado_por_disjuntor
                        ):
                            escolhido = candidato
                            break

                    if escolhido is None:
                        # fallback determinístico: distribui no miolo sem
                        # reutilizar o mesmo X.
                        passo_fallback = max(
                            0.07,
                            largura_miolo_qdc
                            / max(
                                2,
                                len(condutores_horizontais) + 1
                            )
                        )
                        escolhido = (
                            limite_esq
                            + (len(corredores_verticais_usados) + 1)
                            * passo_fallback
                        )

                    corredor_vertical_por_chave[chave] = escolhido
                    corredores_verticais_usados.append(escolhido)
                    return escolhido

                for grupo, itens_grupo in grupos_fileira:
                    x1p = itens_grupo[0][1]["x1"]
                    x2p = itens_grupo[-1][1]["x2"]

                    # --------------------------------------------------
                    # NEUTRO DO GRUPO — REV.65
                    # --------------------------------------------------
                    # O neutro não é mais distribuído horizontalmente
                    # no miolo entre os disjuntores.
                    #
                    # A rota final será criada depois, com todos os DJs
                    # já desenhados:
                    #
                    #   SEM DR -> 3º borne do barramento N -> lateral direita
                    #          -> circuito
                    #
                    #   DRx    -> saída N do próprio DR -> lateral direita
                    #          -> circuito
                    #
                    # Aqui apenas identificamos quais circuitos precisam N.
                    itens_com_neutro = [
                        (d_item, g_item)
                        for d_item, g_item in itens_grupo
                        if g_item.get("tem_neutro")
                    ]

                    # Fase 13.6 Rev.105:
                    # barramento pente somente faz sentido quando alimenta
                    # dois ou mais disjuntores do mesmo grupo.
                    usar_pente = (
                        len(
                            itens_grupo
                        )
                        >= 2
                    )

                    # Rev.21 — representação gráfica dos pentes
                    # temporariamente removida para limpar o miolo do QDC.
                    # A variável usar_pente continua indicando somente que
                    # o grupo possui distribuição para múltiplos disjuntores.

                    # Fases realmente usadas neste grupo.
                    fases_grupo = []
                    for d_item, g_item in itens_grupo:
                        for fase_item in _fases_do_texto(
                            d_item.get(
                                "fase",
                                ""
                            )
                        ):
                            if fase_item not in fases_grupo:
                                fases_grupo.append(
                                    fase_item
                                )

                    fases_grupo = [
                        fase
                        for fase in (
                            "A",
                            "B",
                            "C"
                        )
                        if fase in fases_grupo
                    ]

                    # Cada fase ganha uma pista própria, paralela ao pente.
                    # REV.2: o pente mecânico e as pistas A/B/C possuem
                    # afastamento vertical próprio. Isto evita sobreposição
                    # gráfica entre PENTE, fases e textos dos circuitos.
                    # A pista termina exatamente no último disjuntor que usa
                    # aquela fase; o último ponto será apenas uma curva.
                    # Separação gráfica mínima entre todos os elementos:
                    # PENTE -> A -> B -> C.
                    # Evita coincidência de linha, texto e nós de derivação.
                    # Rev.20: cada condutor horizontal recebe um nível
                    # exclusivo calculado a partir do vão físico disponível.
                    # Mantemos estas constantes apenas como fallback para
                    # situações degeneradas sem geometria suficiente.
                    AFASTAMENTO_PENTE_FASE = 0.30
                    AFASTAMENTO_ENTRE_FASES = ESPACAMENTO_BARRAMENTOS_FASE
                    y_fase_grupo = {}
                    pontos_pente_por_fase = {}

                    for fase_grupo in fases_grupo:
                        yy_fase = niveis_horizontais.get(
                            (grupo, fase_grupo),
                            yp + AFASTAMENTO_PENTE_FASE
                        )
                        y_fase_grupo[
                            fase_grupo
                        ] = yy_fase

                        pontos_fase = []

                        for d_item, g_item in itens_grupo:
                            if fase_grupo in _fases_do_texto(
                                d_item.get(
                                    "fase",
                                    ""
                                )
                            ):
                                x_ponto_fase = _polo_para_fase(
                                    d_item,
                                    g_item,
                                    fase_grupo
                                )

                                # Rev.77 — sempre usar o eixo REAL do borne.
                                # Não existe mais deslocamento especial do C08.
                                pontos_fase.append(x_ponto_fase)

                        pontos_fase = sorted(set(pontos_fase))
                        pontos_pente_por_fase[
                            fase_grupo
                        ] = pontos_fase

                        # Rev.79 — a pista horizontal NÃO é mais
                        # desenhada antecipadamente. Ela será criada depois,
                        # quando a fonte e os destinos reais forem conhecidos.

                    # Cada disjuntor recebe cada fase em um polo diferente.
                    # Em grupo unitário, a conexão será feita diretamente
                    # da fonte ao polo; portanto não criamos descida a partir
                    # de uma pista horizontal inexistente.
                    if usar_pente:
                        for d_item, g_item in itens_grupo:
                            polos_circuito = _centros_polos(
                                g_item
                            )
                            fases_circuito = _fases_do_texto(
                                d_item.get(
                                    "fase",
                                    ""
                                )
                            )

                            for fase_item in fases_circuito:
                                yy_fase = y_fase_grupo.get(
                                    fase_item,
                                    yp + AFASTAMENTO_PENTE_FASE
                                )

                                x_polo = _polo_para_fase(
                                    d_item,
                                    g_item,
                                    fase_item
                                )

                                # Rev.77 — entrada sempre vertical e
                                # diretamente alinhada ao borne real do DJ.
                                # Sem retorno, sem "rebarba" horizontal.
                                _line(
                                    msp,
                                    (
                                        x_polo,
                                        yy_fase
                                    ),
                                    (
                                        x_polo,
                                        g_item["y2"]
                                    ),
                                    _layer_por_token(
                                        fase_item
                                    )
                                )
                                # O nó é decidido somente depois de
                                # conhecermos de qual lado chega a fonte.
                                # Isso evita bolinhas no ponto terminal.

                    # Fonte do grupo.
                    fonte_disp = None
                    # Fonte do grupo.
                    fonte_disp = None
                    fonte_geom = dr_geom_por_grupo.get(
                        grupo
                    )

                    if fonte_geom is not None:
                        for d_geral, g_geral in geral_geom:
                            if g_geral is fonte_geom:
                                fonte_disp = d_geral
                                break

                    if (
                        fonte_geom is None
                        and str(
                            grupo
                        ).upper()
                        == "SEM DR"
                        and dg_geoms
                    ):
                        fonte_disp, fonte_geom = dg_geoms[0]

                    if fonte_geom and fonte_disp:
                        polos_fonte = _centros_polos(
                            fonte_geom
                        )

                        if fonte_disp.get("tipo") == "IDR":
                            fases_fonte = [
                                token
                                for token in ("A", "B", "C")
                                if token in (
                                    fonte_disp.get(
                                        "condutores",
                                        []
                                    )
                                    or []
                                )
                            ]
                        else:
                            fases_fonte = _fases_do_texto(
                                fonte_disp.get(
                                    "fase",
                                    ""
                                )
                            )

                        if fonte_disp.get("tipo") == "DG":
                            fases_fonte = _fases_alimentador(
                                mapa
                            )

                        if usar_pente:
                            # Dois ou mais disjuntores:
                            # fonte -> pista específica A/B/C -> derivações.
                            for idx_fase, fase_item in enumerate(
                                fases_fonte
                            ):
                                if fase_item not in y_fase_grupo:
                                    continue

                                x_origem = _polo_para_fase(
                                    fonte_disp,
                                    fonte_geom,
                                    fase_item
                                )
                                yy_destino = y_fase_grupo[
                                    fase_item
                                ]

                                pontos_destino_fase = sorted(
                                    set(
                                        pontos_pente_por_fase.get(
                                            fase_item,
                                            []
                                        )
                                    )
                                )

                                if not pontos_destino_fase:
                                    continue

                                # Rev.53 — prioridade absoluta para o cabo
                                # alinhado com o borne: ele segue RETO.
                                # Somente os demais destinos mudam trajetória.
                                x_destino_reto, pontos_desviados = (
                                    _destino_alinhado_prioritario(
                                        x_origem,
                                        pontos_destino_fase
                                    )
                                )

                                if x_destino_reto is not None:
                                    g_reto = next(
                                        (
                                            g_dest
                                            for d_dest, g_dest in itens_grupo
                                            if abs(
                                                _polo_para_fase(
                                                    d_dest,
                                                    g_dest,
                                                    fase_item
                                                ) - x_destino_reto
                                            ) <= 1e-9
                                        ),
                                        None
                                    )
                                    if g_reto is not None:
                                        _line(
                                            msp,
                                            (x_origem, fonte_geom["y1"]),
                                            (x_destino_reto, g_reto["y2"]),
                                            _layer_por_token(fase_item)
                                        )

                                # Rev.77 — se uma fase da fonte segue RETA
                                # para um DJ e, no mesmo nível, também sai
                                # horizontalmente para outros DJs, o encontro
                                # é uma derivação real:
                                #
                                #   U = fonte
                                #   D = DJ alinhado
                                #   L/R = demais DJs
                                #
                                # Portanto registramos a bolinha nesse ponto.
                                # Rev.81 — distribuição por TOPOLOGIA REAL.
                                #
                                # Separamos os destinos em ramos à esquerda
                                # e à direita da fonte. Cada ramo termina
                                # exatamente no seu último DJ.
                                #
                                # Isso resolve duas coisas de forma determinística:
                                # 1) nenhuma pista horizontal "sobra";
                                # 2) as bolinhas aparecem somente onde a
                                #    própria distribuição realmente deriva.

                                pontos_destino_fase = sorted(
                                    set(
                                        float(xx_rev81)
                                        for xx_rev81 in pontos_desviados
                                    )
                                )

                                # Rev.82 — pivô físico da ramificação.
                                # Havendo um DJ que recebe a fase reta, o ramo
                                # nasce no eixo desse borne, e não além dele.
                                x_pivo_rev82 = (
                                    float(x_destino_reto)
                                    if x_destino_reto is not None
                                    else float(x_origem)
                                )

                                pontos_esquerda_rev81 = [
                                    xx_rev81
                                    for xx_rev81 in pontos_destino_fase
                                    if xx_rev81 < x_pivo_rev82 - 1e-9
                                ]
                                pontos_direita_rev81 = [
                                    xx_rev81
                                    for xx_rev81 in pontos_destino_fase
                                    if xx_rev81 > x_pivo_rev82 + 1e-9
                                ]

                                # Rev.86 — CONTINUIDADE ENTRE FILEIRAS.
                                #
                                # O erro do "resto" acontecia porque, depois de
                                # alimentar uma fileira, o tronco da fase continuava
                                # guardando o X original do polo do DR.
                                #
                                # Na fileira seguinte isso obrigava a pista horizontal
                                # a voltar até o X do DR, mesmo quando a fase já havia
                                # chegado a um DJ da fileira anterior (ex.: C05).
                                #
                                # Agora a continuação para a próxima fileira nasce no
                                # ponto de derivação REAL mais próximo da fonte:
                                # - se existe DJ reto, usa esse borne;
                                # - senão, usa o destino da fileira mais próximo do
                                #   X atual do tronco/fonte.
                                #
                                # Assim:
                                # DR3 -> passa por trás de C05 -> continua dali
                                # para C08, sem prolongamento à direita.
                                pontos_todos_rev86 = sorted(
                                    set(
                                        [float(x_pivo_rev82)]
                                        + [
                                            float(xx_rev86)
                                            for xx_rev86 in pontos_destino_fase
                                        ]
                                    )
                                )

                                if x_destino_reto is not None:
                                    x_continuacao_rev86 = float(
                                        x_destino_reto
                                    )
                                elif pontos_destino_fase:
                                    x_referencia_rev86 = float(x_origem)

                                    chave_tmp_rev86 = (
                                        str(
                                            fonte_disp.get(
                                                "identificador",
                                                ""
                                            )
                                            if fonte_disp
                                            else ""
                                        ).strip().upper(),
                                        str(fase_item).strip().upper(),
                                    )

                                    if chave_tmp_rev86 in troncos_fonte_fase:
                                        x_referencia_rev86 = float(
                                            troncos_fonte_fase[
                                                chave_tmp_rev86
                                            ]["x"]
                                        )

                                    x_continuacao_rev86 = min(
                                        (
                                            float(xx_rev86)
                                            for xx_rev86 in pontos_destino_fase
                                        ),
                                        key=lambda xx_rev86: abs(
                                            xx_rev86
                                            - x_referencia_rev86
                                        )
                                    )
                                else:
                                    x_continuacao_rev86 = float(
                                        x_pivo_rev82
                                    )

                                # ------------------------------------------------
                                # TRONCO VERTICAL DA FONTE
                                # ------------------------------------------------
                                ident_fonte = str(
                                    fonte_disp.get("identificador", "")
                                    if fonte_disp
                                    else ""
                                ).strip().upper()

                                chave_tronco = (
                                    ident_fonte,
                                    str(fase_item).strip().upper()
                                )

                                if chave_tronco not in troncos_fonte_fase:
                                    if x_destino_reto is None:
                                        _line(
                                            msp,
                                            (x_origem, fonte_geom["y1"]),
                                            (x_origem, yy_destino),
                                            _layer_por_token(fase_item)
                                        )

                                    troncos_fonte_fase[chave_tronco] = {
                                        "x": x_origem,
                                        "y": yy_destino,
                                        "layer": _layer_por_token(fase_item),
                                    }

                                else:
                                    tronco = troncos_fonte_fase[chave_tronco]
                                    y_anterior = tronco["y"]

                                    if abs(yy_destino - y_anterior) > 1e-9:
                                        _line(
                                            msp,
                                            (tronco["x"], y_anterior),
                                            (tronco["x"], yy_destino),
                                            tronco["layer"]
                                        )

                                        # Aqui existe, por definição:
                                        # chegada + continuidade vertical +
                                        # saída horizontal da fileira anterior.
                                        if not _ja_existe_no_confirmado(
                                            msp,
                                            tronco["x"],
                                            y_anterior,
                                            fase_item
                                        ):
                                            _registrar_no_logico_rev82(
                                                msp,
                                                tronco["x"],
                                                y_anterior,
                                                fase_item,
                                                0.035
                                            )

                                        tronco["y"] = yy_destino

                                # ------------------------------------------------
                                # PISTAS HORIZONTAIS SEM REBARBA
                                # ------------------------------------------------
                                # Rev.86 — em fileiras inferiores a pista nasce
                                # no X atual do tronco (continuação real da fileira
                                # anterior), e não obrigatoriamente no polo do DR.
                                x_inicio_pista_rev86 = float(
                                    troncos_fonte_fase.get(
                                        chave_tronco,
                                        {"x": x_origem}
                                    )["x"]
                                )

                                # Rev.88 — DJ alinhado pode receber o cabo reto,
                                # mas não muda a origem elétrica do tronco para
                                # as fileiras seguintes.
                                if x_destino_reto is not None:
                                    x_pivo_local_rev88 = float(
                                        x_destino_reto
                                    )
                                else:
                                    x_pivo_local_rev88 = float(
                                        x_inicio_pista_rev86
                                    )

                                # Rev.86 — classificação lateral usa o X REAL
                                # onde a pista nasce nesta fileira.
                                pontos_esquerda_rev81 = [
                                    float(xx_rev86)
                                    for xx_rev86 in pontos_destino_fase
                                    if float(xx_rev86)
                                    < x_pivo_local_rev88 - 1e-9
                                ]
                                pontos_direita_rev81 = [
                                    float(xx_rev86)
                                    for xx_rev86 in pontos_destino_fase
                                    if float(xx_rev86)
                                    > x_pivo_local_rev88 + 1e-9
                                ]

                                if pontos_esquerda_rev81:
                                    _registrar_pista_horizontal_rev85(
                                        msp,
                                        x_pivo_local_rev88,
                                        min(pontos_esquerda_rev81),
                                        yy_destino,
                                        fase_item
                                    )

                                if pontos_direita_rev81:
                                    _registrar_pista_horizontal_rev85(
                                        msp,
                                        x_pivo_local_rev88,
                                        max(pontos_direita_rev81),
                                        yy_destino,
                                        fase_item
                                    )

                                # ------------------------------------------------
                                # NÓ NA FONTE
                                # ------------------------------------------------
                                # Com DJ alinhado:
                                # chegada vertical + continuação reta ao DJ +
                                # pelo menos um ramo lateral = derivação.
                                #
                                # Sem DJ alinhado:
                                # só é derivação se houver ramo para os DOIS lados.
                                fonte_tem_derivacao_rev81 = (
                                    (
                                        x_destino_reto is not None
                                        and (
                                            pontos_esquerda_rev81
                                            or pontos_direita_rev81
                                        )
                                    )
                                    or
                                    (
                                        x_destino_reto is None
                                        and pontos_esquerda_rev81
                                        and pontos_direita_rev81
                                    )
                                )

                                if fonte_tem_derivacao_rev81:
                                    if not _ja_existe_no_confirmado(
                                        msp,
                                        x_pivo_rev82,
                                        yy_destino,
                                        fase_item
                                    ):
                                        _registrar_no_logico_rev82(
                                            msp,
                                            x_pivo_rev82,
                                            yy_destino,
                                            fase_item,
                                            0.035
                                        )

                                # ------------------------------------------------
                                # NÓS NOS DESTINOS À ESQUERDA
                                # ------------------------------------------------
                                # O mais distante à esquerda é o fim do ramo:
                                # curva para baixo, SEM bolinha.
                                #
                                # Todos os outros pontos desse ramo têm:
                                # continuidade horizontal + descida ao DJ,
                                # portanto são derivações reais.
                                if pontos_esquerda_rev81:
                                    x_final_esq_rev81 = min(
                                        pontos_esquerda_rev81
                                    )

                                    for x_no_rev81 in pontos_esquerda_rev81:
                                        if abs(
                                            x_no_rev81 - x_final_esq_rev81
                                        ) <= 1e-9:
                                            continue

                                        if not _ja_existe_no_confirmado(
                                            msp,
                                            x_no_rev81,
                                            yy_destino,
                                            fase_item
                                        ):
                                            _registrar_no_logico_rev82(
                                                msp,
                                                x_no_rev81,
                                                yy_destino,
                                                fase_item,
                                                0.035
                                            )

                                # ------------------------------------------------
                                # NÓS NOS DESTINOS À DIREITA
                                # ------------------------------------------------
                                # O mais distante à direita é o fim do ramo:
                                # curva para baixo, SEM bolinha.
                                #
                                # Os anteriores são derivações reais.
                                if pontos_direita_rev81:
                                    x_final_dir_rev81 = max(
                                        pontos_direita_rev81
                                    )

                                    for x_no_rev81 in pontos_direita_rev81:
                                        if abs(
                                            x_no_rev81 - x_final_dir_rev81
                                        ) <= 1e-9:
                                            continue

                                        if not _ja_existe_no_confirmado(
                                            msp,
                                            x_no_rev81,
                                            yy_destino,
                                            fase_item
                                        ):
                                            _registrar_no_logico_rev82(
                                                msp,
                                                x_no_rev81,
                                                yy_destino,
                                                fase_item,
                                                0.035
                                            )

                                # Rev.88 — IMPORTANTE:
                                # o tronco permanece eletricamente ligado à FONTE
                                # (DG/DR correspondente). Um DJ da fileira anterior
                                # nunca vira fonte do DJ da fileira seguinte.
                                #
                                # Atualizamos apenas o Y já alcançado; o X permanece
                                # no polo da fonte para preservar a origem elétrica.
                                if chave_tronco in troncos_fonte_fase:
                                    troncos_fonte_fase[
                                        chave_tronco
                                    ]["y"] = float(
                                        yy_destino
                                    )

                        else:
                            # Um único disjuntor:
                            # SEM PENTE e SEM pista horizontal.
                            # Cada fase sai do polo correspondente da fonte e
                            # chega diretamente ao polo correspondente do DJ.
                            d_unico, g_unico = itens_grupo[0]
                            fases_destino = _fases_do_texto(
                                d_unico.get(
                                    "fase",
                                    ""
                                )
                            )

                            for idx_fase, fase_item in enumerate(
                                fases_destino
                            ):
                                if fase_item not in fases_fonte:
                                    continue

                                x_origem = _polo_para_fase(
                                    fonte_disp,
                                    fonte_geom,
                                    fase_item
                                )
                                x_destino = _polo_para_fase(
                                    d_unico,
                                    g_unico,
                                    fase_item
                                )

                                # Rev.20: mesmo para grupo com um único
                                # disjuntor, a horizontal ocupa sua faixa
                                # exclusiva na grade dinâmica.
                                y_corredor_direto = niveis_horizontais.get(
                                    (grupo, fase_item),
                                    yp
                                    + AFASTAMENTO_PENTE_FASE
                                    + idx_fase
                                    * AFASTAMENTO_ENTRE_FASES
                                )

                                # Rev.33 — grupo unitário usa o mesmo
                                # tronco compartilhado da fonte/fase.
                                ident_fonte = str(
                                    fonte_disp.get("identificador", "")
                                    if fonte_disp
                                    else ""
                                ).strip().upper()
                                chave_tronco = (
                                    ident_fonte,
                                    str(fase_item).strip().upper()
                                )

                                if chave_tronco not in troncos_fonte_fase:
                                    _line(
                                        msp,
                                        (x_origem, fonte_geom["y1"]),
                                        (x_origem, y_corredor_direto),
                                        _layer_por_token(fase_item)
                                    )
                                    troncos_fonte_fase[chave_tronco] = {
                                        "x": x_origem,
                                        "y": y_corredor_direto,
                                        "layer": _layer_por_token(fase_item),
                                    }
                                else:
                                    tronco = troncos_fonte_fase[chave_tronco]
                                    y_anterior = tronco["y"]
                                    if abs(
                                        y_corredor_direto - y_anterior
                                    ) > 1e-9:
                                        _line(
                                            msp,
                                            (tronco["x"], y_anterior),
                                            (tronco["x"], y_corredor_direto),
                                            tronco["layer"]
                                        )
                                        _no_fase_preenchido(
                                            msp,
                                            tronco["x"],
                                            y_anterior,
                                            fase_item
                                        )
                                        tronco["y"] = y_corredor_direto

                                # Rev.88 — GRUPO UNITÁRIO EM FILEIRA POSTERIOR.
                                #
                                # A origem elétrica permanece no DR/DG correspondente.
                                # O cabo pode passar GRAFICAMENTE por trás de outro DJ,
                                # mas nunca deriva eletricamente da saída desse DJ.
                                tronco_fonte_rev88 = troncos_fonte_fase.get(
                                    chave_tronco
                                )

                                x_inicio_rev88 = float(
                                    tronco_fonte_rev88["x"]
                                    if tronco_fonte_rev88 is not None
                                    else x_origem
                                )

                                # O corredor horizontal é exatamente:
                                # fonte (DR/DG) -> borne do DJ destino.
                                # Não existe extensão depois do destino.
                                _registrar_pista_horizontal_rev85(
                                    msp,
                                    x_inicio_rev88,
                                    x_destino,
                                    y_corredor_direto,
                                    fase_item
                                )

                                # Trecho final reto entrando no borne.
                                _line(
                                    msp,
                                    (x_destino, y_corredor_direto),
                                    (x_destino, g_unico["y2"]),
                                    _layer_por_token(fase_item)
                                )

                                # Mantém somente a altura alcançada.
                                # O X continua sendo o polo da fonte.
                                if chave_tronco in troncos_fonte_fase:
                                    troncos_fonte_fase[
                                        chave_tronco
                                    ]["y"] = float(
                                        y_corredor_direto
                                    )

        y_rail -= 3.15

    # ========================================================
    # FASE 13.6 REV.105 — NEUTROS PELA DIREITA, POR FONTE
    # ========================================================
    # - SEM DR: 3º borne do barramento N;
    # - COM DR: saída N do respectivo DR;
    # - lateral direita = apenas desvio geométrico;
    # - 1 rota individual por circuito 1P.
    neutros_circuitos_rev65 = []

    for d_n65, g_n65 in circuitos_geom:
        fases_n65 = _fases_do_texto(d_n65.get("fase", ""))

        if not (
            len(fases_n65) == 1
            and int(d_n65.get("modulos", 1) or 1) == 1
        ):
            continue

        grupo_n65 = str(
            d_n65.get("grupo", "SEM DR") or "SEM DR"
        ).strip().upper()

        x_fonte_n65 = None
        y_fonte_n65 = None

        if grupo_n65 == "SEM DR":
            x_fonte_n65 = float(neutro["x"])
            y_fonte_n65 = float(
                _y_borne_barramento(neutro, 2)
            )
        else:
            par_dr_n65 = dr_disp_geom_por_grupo.get(grupo_n65)

            if par_dr_n65 is not None:
                disp_dr_n65, geom_dr_n65 = par_dr_n65
                mapa_dr_n65 = _mapa_condutores_polos(
                    disp_dr_n65,
                    geom_dr_n65
                )
                x_n_dr65 = mapa_dr_n65.get("N")

                if x_n_dr65 is not None:
                    x_fonte_n65 = float(x_n_dr65)
                    y_fonte_n65 = float(geom_dr_n65["y1"])

        if x_fonte_n65 is None or y_fonte_n65 is None:
            continue

        x_destino_n65 = float(
            _x_passagem_lateral_disjuntor(
                g_n65,
                "dir",
                0.12
            )
        )

        neutros_circuitos_rev65.append({
            "d": d_n65,
            "g": g_n65,
            "grupo": grupo_n65,
            "x_fonte": x_fonte_n65,
            "y_fonte": y_fonte_n65,
            "x_destino": x_destino_n65,
        })

    if neutros_circuitos_rev65:
        # ====================================================
        # REV.68 — CORREDORES N À DIREITA DO BARRAMENTO
        # ====================================================
        # 1º corredor: exatamente 0,10 após a FACE DIREITA do barramento N.
        # Demais corredores: exatamente 0,08 entre si.
        #
        # Se não existir circuito SEM DR, o primeiro neutro disponível
        # ainda começa a 0,10 do barramento para manter a referência.
        neutros_circuitos_rev65 = sorted(
            neutros_circuitos_rev65,
            key=lambda item: (
                0 if item["grupo"] == "SEM DR" else 1,
                str(item["grupo"]),
                str(item["d"].get("identificador", "") or "")
            )
        )

        # Rev.69 — 0,10 medidos a partir do FIM/FACE DIREITA
        # do desenho do barramento N. O barramento tem meia largura 0,18.
        x_face_direita_barramento_n69 = float(neutro["x"]) + 0.18
        x_primeiro_n68 = x_face_direita_barramento_n69 + 0.10
        passo_x_n68 = 0.08

        # Separa SEM DR dos neutros pós-DR.
        neutros_sem_dr_n68 = [
            item for item in neutros_circuitos_rev65
            if item["grupo"] == "SEM DR"
        ]
        neutros_dr_n68 = [
            item for item in neutros_circuitos_rev65
            if item["grupo"] != "SEM DR"
        ]

        # ----------------------------------------------------
        # SEM DR — REV.69
        # ----------------------------------------------------
        # Todos os neutros SEM DR nascem no 3º borne do barramento N.
        # O borne em si NÃO recebe bolinha.
        #
        # O tronco sai do 3º borne até a direita do barramento e percorre
        # horizontalmente os corredores. Cada descida é uma derivação real.
        # Assim, nos pontos intermediários:
        #   chegada + continuidade + descida = 3 ramos -> bolinha azul.
        if neutros_sem_dr_n68:
            y_borne_sem_n69 = float(neutros_sem_dr_n68[0]["y_fonte"])

            xs_sem_n69 = [
                x_primeiro_n68 + i * passo_x_n68
                for i in range(len(neutros_sem_dr_n68))
            ]

            # Um único tronco desde o 3º borne até o último corredor.
            _line(
                msp,
                (float(neutro["x"]), y_borne_sem_n69),
                (xs_sem_n69[-1], y_borne_sem_n69),
                LN
            )

            for idx_sem_n68, (item_n68, x_corredor_n68) in enumerate(
                zip(neutros_sem_dr_n68, xs_sem_n69)
            ):
                y_retorno_n68 = _nivel_final_rev91(
                    item_n68["d"],
                    "N"
                )

                _polyline(
                    msp,
                    [
                        (x_corredor_n68, y_borne_sem_n69),
                        (x_corredor_n68, y_retorno_n68),
                        (
                            _x_final_rev96(
                                item_n68["d"],
                                "N",
                                item_n68["x_destino"]
                            ),
                            y_retorno_n68
                        ),
                    ],
                    LN
                )

                _registrar_x_handoff_rev91(
                    item_n68["d"],
                    "N",
                    _x_final_rev96(
                        item_n68["d"],
                        "N",
                        item_n68["x_destino"]
                    )
                )

                # Candidato somente em derivação do TRONCO.
                # O último ponto é apenas fim+descida (2 ramos), portanto
                # a regra global não desenhará bolinha nele.
                _no_fase_preenchido(
                    msp,
                    x_corredor_n68,
                    y_borne_sem_n69,
                    "N"
                )

        # ----------------------------------------------------
        # COM DR — REV.69
        # ----------------------------------------------------
        # Cada DR usa sua própria saída N.
        # Para cada DR/grupo existe um único tronco horizontal N no nível Y
        # escolhido. Os circuitos daquele DR derivam desse tronco.
        #
        # Os níveis Y podem coincidir com PE/A/B/C do lado esquerdo,
        # porque aqui os neutros seguem para a DIREITA.
        base_idx_n68 = len(neutros_sem_dr_n68)

        # Agrupa os neutros por DR.
        grupos_neutro_dr_n69 = {}
        for item_n69 in neutros_dr_n68:
            grupos_neutro_dr_n69.setdefault(
                item_n69["grupo"],
                []
            ).append(item_n69)

        y_base_superior_n68 = min(
            float(g_n68["y1"])
            for _d_n68, g_n68 in geral_geom
        )
        y_topo_inferior_n68 = max(
            float(g_n68["y2"])
            for _d_n68, g_n68 in circuitos_geom
        )
        h_n68 = y_base_superior_n68 - y_topo_inferior_n68
        q_grupos_n69 = max(1, len(grupos_neutro_dr_n69))
        e_fallback_n68 = (
            h_n68 / (q_grupos_n69 + 1)
            if h_n68 > 0
            else 0.10
        )

        idx_global_corredor_n69 = base_idx_n68

        for idx_grupo_n69, grupo_n69 in enumerate(
            sorted(grupos_neutro_dr_n69)
        ):
            itens_dr_n69 = sorted(
                grupos_neutro_dr_n69[grupo_n69],
                key=lambda item: str(
                    item["d"].get("identificador", "") or ""
                )
            )

            if idx_grupo_n69 < len(niveis_compartilhados_n68):
                y_horizontal_n69 = niveis_compartilhados_n68[idx_grupo_n69]
            else:
                y_horizontal_n69 = (
                    y_base_superior_n68
                    - (idx_grupo_n69 + 1) * e_fallback_n68
                )

            x_fonte_grupo_n69 = float(itens_dr_n69[0]["x_fonte"])
            y_fonte_grupo_n69 = float(itens_dr_n69[0]["y_fonte"])

            xs_corredores_grupo_n69 = []
            for _ in itens_dr_n69:
                xs_corredores_grupo_n69.append(
                    x_primeiro_n68
                    + idx_global_corredor_n69 * passo_x_n68
                )
                idx_global_corredor_n69 += 1

            # Saída do DR: desce reto até o nível horizontal.
            _line(
                msp,
                (x_fonte_grupo_n69, y_fonte_grupo_n69),
                (x_fonte_grupo_n69, y_horizontal_n69),
                LN
            )

            # Tronco do grupo até o último circuito.
            _line(
                msp,
                (x_fonte_grupo_n69, y_horizontal_n69),
                (xs_corredores_grupo_n69[-1], y_horizontal_n69),
                LN
            )

            for idx_item_n69, (item_n69, x_corredor_n69) in enumerate(
                zip(itens_dr_n69, xs_corredores_grupo_n69)
            ):
                y_retorno_n69 = _nivel_final_rev91(
                    item_n69["d"],
                    "N"
                )

                _polyline(
                    msp,
                    [
                        (x_corredor_n69, y_horizontal_n69),
                        (x_corredor_n69, y_retorno_n69),
                        (
                            _x_final_rev96(
                                item_n69["d"],
                                "N",
                                item_n69["x_destino"]
                            ),
                            y_retorno_n69
                        ),
                    ],
                    LN
                )

                _registrar_x_handoff_rev91(
                    item_n69["d"],
                    "N",
                    _x_final_rev96(
                        item_n69["d"],
                        "N",
                        item_n69["x_destino"]
                    )
                )

                # Nó candidato somente na derivação do tronco.
                _no_fase_preenchido(
                    msp,
                    x_corredor_n69,
                    y_horizontal_n69,
                    "N"
                )

    # ========================================================
    # FASE 13.6 REV.105 — PE INDIVIDUAL POR CIRCUITO
    # ========================================================
    # 1 circuito = 1 cabo PE = 1 borne físico exclusivo no barramento PE.
    #
    # Bornes:
    #   0 -> entrada PE da rede
    #   1 -> PE dos DPS
    #   2 em diante -> circuitos C01, C02, ...
    #
    # O cabo sai de cada borne para a lateral esquerda, desce por um corredor
    # exclusivo e somente abaixo da última fileira segue horizontalmente até
    # a posição final do respectivo circuito.
    if circuitos_geom:
        x_lateral_base_pe = pe["x"] - 0.34
        passo_lateral_pe = 0.08

        for idx_pe_circ, (d_pe, g_pe) in enumerate(circuitos_geom):
            indice_borne_pe = idx_pe_circ + 2
            y_borne_pe_circ = _y_borne_barramento(
                pe,
                indice_borne_pe
            )

            x_corredor_pe_circ = (
                x_lateral_base_pe
                - idx_pe_circ * passo_lateral_pe
            )

            x_saida_pe_circ = _x_passagem_lateral_disjuntor(
                g_pe,
                "esq",
                0.16
            )

            # Rev.91 — o PE entra diretamente no nível E exclusivo
            # do circuito. Não existe mais a escadaria de 0,035 m.
            y_final_pe_circ = _nivel_final_rev91(
                d_pe,
                "PE"
            )

            _polyline(
                msp,
                [
                    (pe["x"], y_borne_pe_circ),
                    (x_corredor_pe_circ, y_borne_pe_circ),
                    (x_corredor_pe_circ, y_final_pe_circ),
                    (
                        _x_final_rev96(
                            d_pe,
                            "PE",
                            x_saida_pe_circ
                        ),
                        y_final_pe_circ
                    ),
                ],
                LPE
            )

            _registrar_x_handoff_rev91(
                d_pe,
                "PE",
                _x_final_rev96(
                    d_pe,
                    "PE",
                    x_saida_pe_circ
                )
            )

    # ========================================================
    # FASE 13.6 REV.105 — SEGMENTO FINAL NÃO DESTRUTIVO
    # ========================================================
    # Regra: nunca apagar/recortar cabos existentes depois do desenho.
    # O segmento final é criado somente entre a origem real e o X final.
    # Assim preservamos integralmente as verticais de F/N/PE e os textos.
    def _linha_horizontal_final_rev95(
        msp_rev95,
        x_origem_rev95,
        x_destino_rev95,
        y_rev95,
        layer_rev95
    ):
        xo95 = float(x_origem_rev95)
        xd95 = float(x_destino_rev95)
        yy95 = float(y_rev95)

        if abs(xd95 - xo95) <= 1e-9:
            return None

        # Não há prolongamento, margem, offset nem "cauda":
        # a entidade nasce e termina exatamente nos dois X informados.
        return _line(
            msp_rev95,
            (xo95, yy95),
            (xd95, yy95),
            layer_rev95
        )

    # FASE 13.6 REV.105 — SAÍDA FINAL PELA MESMA LÓGICA DOS NÍVEIS
    # ========================================================
    # O horizontal já foi desenhado anteriormente, terminando
    # EXATAMENTE no X final do respectivo condutor.
    #
    # Aqui só existem:
    # 1) queda vertical final;
    # 2) identificação do circuito.
    #
    # Portanto não há possibilidade de "sobra" à direita/esquerda
    # causada por um segundo trecho horizontal.
    if circuitos_geom:
        y_final_chicotes = (
            y_limite_inferior_saida_rev91 - 0.35
        )
        y_texto_chicotes = (
            y_final_chicotes - 0.22
        )

        for d_ch, g_ch in circuitos_geom:
            fases_ch = _fases_do_texto(
                d_ch.get("fase", "")
            )

            tokens_ch = list(fases_ch)

            if (
                len(fases_ch) == 1
                and int(d_ch.get("modulos", 1) or 1) == 1
            ):
                tokens_ch.append("N")

            tokens_ch.append("PE")

            ident_ch = str(
                d_ch.get("identificador", "") or ""
            )
            ident_key_ch = ident_ch.strip().upper()

            for token_ch in tokens_ch:
                x_destino_ch = _x_final_rev96(
                    d_ch,
                    token_ch,
                    mapa_centro_circuito_rev96.get(
                        ident_key_ch,
                        (din_x1 + din_x2) / 2.0
                    )
                )

                y_nivel_ch = _nivel_final_rev91(
                    d_ch,
                    token_ch
                )

                # Somente a descida final.
                _line(
                    msp,
                    (x_destino_ch, y_nivel_ch),
                    (x_destino_ch, y_final_chicotes),
                    _layer_por_token(token_ch)
                )

            x_centro_ch = mapa_centro_circuito_rev96.get(
                ident_key_ch,
                (din_x1 + din_x2) / 2.0
            )

            _texto_central(
                msp,
                ident_ch,
                x_centro_ch - 0.18,
                x_centro_ch + 0.18,
                y_texto_chicotes,
                0.085,
                LT
            )

    # ========================================================
    # FASE 13.6 REV.105 — MOLDURA REAL DO DIAGRAMA
    # ========================================================
    # A moldura acompanha a área efetivamente usada pelo desenho.
    # A entrada da rede A/B/C/PE/N fica inteiramente dentro dela,
    # assim como os chicotes e identificações inferiores.
    #
    # Folgas:
    # esquerda/direita = 0,35
    # superior = 0,22 acima da referência superior do QDC
    # inferior = 0,35 abaixo das identificações finais
    margem_moldura_rev97 = 0.35

    # Fase 13.6 Rev.105 — centralização geométrica real.
    # A moldura usa a mesma folga dos dois lados do diagrama.
    # qx1/qx2 são os limites funcionais da vista frontal; portanto
    # não existe mais a grande sobra lateral que deslocava o desenho.
    # Fase 13.6 Rev.105 — limite esquerdo REAL do diagrama.
    # O chicote PE é o elemento mais à esquerda; a moldura deve envolvê-lo.
    if circuitos_geom:
        x_pe_mais_esquerda_rev101 = (
            x_lateral_base_pe
            - max(0, len(circuitos_geom) - 1) * passo_lateral_pe
        )
        x_moldura_esq_rev97 = (
            min(qx1, x_pe_mais_esquerda_rev101)
            - margem_moldura_rev97
        )
    else:
        x_moldura_esq_rev97 = qx1 - margem_moldura_rev97

    # Fase 13.6 Rev.105 — limite direito REAL do diagrama.
    # Mesma lógica aplicada ao PE na esquerda, agora espelhada para o N:
    # a moldura acompanha o corredor de neutro mais à direita e acrescenta
    # a mesma folga de segurança de 0,35 m.
    if circuitos_geom:
        # Os corredores N começam 0,10 m após a face direita do barramento
        # e avançam 0,08 m por neutro efetivamente roteado.
        qtd_neutros_rev103 = sum(
            1
            for d_n103, _g_n103 in circuitos_geom
            if (
                len(_fases_do_texto(d_n103.get("fase", ""))) == 1
                and int(d_n103.get("modulos", 1) or 1) == 1
            )
        )

        if qtd_neutros_rev103 > 0:
            x_n_mais_direita_rev103 = (
                x_primeiro_n68
                + max(0, qtd_neutros_rev103 - 1) * passo_x_n68
            )
            x_moldura_dir_rev97 = (
                max(qx2, x_n_mais_direita_rev103)
                + margem_moldura_rev97
            )
        else:
            x_moldura_dir_rev97 = qx2 + margem_moldura_rev97
    else:
        x_moldura_dir_rev97 = qx2 + margem_moldura_rev97

    # A entrada da rede nasce em qy_top - 0,15 e permanece dentro
    # da moldura com folga superior uniforme.
    y_moldura_top_rev97 = qy_top + margem_moldura_rev97

    if circuitos_geom:
        y_moldura_bottom_rev97 = (
            y_texto_chicotes - margem_moldura_rev97
        )
    else:
        y_moldura_bottom_rev97 = qy_bottom

    _rect(
        msp,
        x_moldura_esq_rev97,
        y_moldura_bottom_rev97,
        x_moldura_dir_rev97,
        y_moldura_top_rev97,
        L
    )

    # -------------------------
    # Painel lateral
    # -------------------------
    # Fase 13.6 Rev.105 — o painel lateral nasce logo após a moldura REAL
    # do diagrama. Isso reproduz a segunda imagem: dois quadros próximos,
    # alinhados no topo e sem faixa vazia desnecessária entre eles.
    px1 = x_moldura_dir_rev97 + folga_painel_real
    px2 = px1 + painel_circuitos_w
    # Fase 13.6 Rev.105 — alinhamento superior exato entre os dois quadros.
    py_top = y_moldura_top_rev97

    # A moldura do painel será desenhada somente depois dos DADOS DO QUADRO,
    # para terminar logo abaixo do último conteúdo em vez de descer até a
    # base da prancha.

    _text(
        msp,
        "LISTA DE CIRCUITOS",
        px1 + 0.22,
        py_top - 0.38,
        0.16,
        LT
    )

    # Tabela executiva:
    # Circuito | Fase | DR | Disj. | Ambientes
    #
    # Fase 13.6 Rev.105:
    # cada célula é desenhada como um retângulo independente.
    # Evita linhas horizontais longas escapando para dentro do diagrama.
    # Fase 13.6 Rev.105 — tabela executiva compacta.
    tabela_x1 = px1 + 0.28
    tabela_largura = min(
        7.10,
        max(
            6.55,
            px2 - tabela_x1 - 0.28
        )
    )
    tabela_x2 = tabela_x1 + tabela_largura
    tabela_y_top = py_top - 0.72

    # Colunas técnicas ficam somente com a largura necessária.
    # O restante é destinado a Ambientes.
    col_circuito = 0.66
    col_fase = 0.50
    col_dr = 0.62
    col_dj = 0.62
    col_ambientes = (
        tabela_largura
        - col_circuito
        - col_fase
        - col_dr
        - col_dj
    )

    x_c1 = tabela_x1
    x_c2 = x_c1 + col_circuito
    x_c3 = x_c2 + col_fase
    x_c4 = x_c3 + col_dr
    x_c5 = x_c4 + col_dj
    x_c6 = tabela_x2

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

        # Fonte de verdade das fases: resultado de balancear_circuitos().
        fase_c = str(
            d.get(
                "fase",
                ""
            )
            or ""
        ).strip()

        grupo_dr_c = str(
            d.get(
                "grupo",
                "SEM DR"
            )
            or "SEM DR"
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
            "dr": grupo_dr_c or "SEM DR",
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
        (x_c3, x_c4, "DR"),
        (x_c4, x_c5, "Disj."),
        (x_c5, x_c6, "Ambientes"),
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
                [item["dr"]],
                0.068
            ),
            (
                x_c4,
                x_c5,
                [item["disjuntor"]],
                0.072
            ),
            (
                x_c5,
                x_c6,
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
                "Fase A",
                LA
            )
        )

    if "B" in fases_reais:
        legendas.append(
            (
                "Fase B",
                LB
            )
        )

    if "C" in fases_reais:
        legendas.append(
            (
                "Fase C",
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

    # Fase 13.6 Rev.105 — dados elétricos que antes ficavam no unifilar
    # passam para o próprio diagrama de montagem.
    # Fase 13.6 Rev.105 — DADOS DO QUADRO logo abaixo da legenda.
    # 'yleg' já é a próxima linha livre após o último item da legenda.
    dados_y = yleg - 0.12
    _text(
        msp,
        "DADOS DO QUADRO",
        px1 + 0.25,
        dados_y,
        0.15,
        LT
    )
    qtd_idr = sum(1 for d in gerais if d.get("tipo") == "IDR")
    qtd_dps_desenho = sum(1 for d in gerais if d.get("tipo") == "DPS")

    tipo_fornecimento_qdc = str(
        parametros_rede.get("tipo_fornecimento", "") or ""
    ).strip()
    tensao_fornecimento_qdc = str(
        parametros_rede.get("tensao_fornecimento", "") or ""
    ).strip()

    cargas_fases_qdc = resumo_balanceamento.get("fases", {}) or {}
    texto_balanceamento_qdc = " | ".join(
        f"{fase}: {float(pot or 0) / 1000:.2f} kW"
        for fase, pot in cargas_fases_qdc.items()
    )

    dados = []
    if tipo_fornecimento_qdc:
        dados.append(f"Fornecimento: {tipo_fornecimento_qdc}")
    if tensao_fornecimento_qdc:
        dados.append(f"Tensao de fornecimento: {tensao_fornecimento_qdc}")
    if texto_balanceamento_qdc:
        dados.append(f"Balanceamento: {texto_balanceamento_qdc}")

    dados.extend([
        f"Posicoes: {int(mapa.get('qdc_posicoes', 0) or 0)}",
        f"Modulos ocupados: {int(mapa.get('modulos_dispositivos', 0) or 0)}",
        f"Posicoes livres: {int(mapa.get('posicoes_livres', 0) or 0)}",
        f"Fileiras DIN: {int(mapa.get('linhas', 0) or 0)}",
        f"IDRs: {qtd_idr}",
        f"DPS: {qtd_dps_desenho}",
    ])
    yy_d = dados_y - 0.32
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

    # Fase 13.6 Rev.105 — fechamento compacto do painel lateral.
    painel_y_bottom_rev99 = yy_d - 0.18
    _rect(
        msp,
        px1,
        painel_y_bottom_rev99,
        px2,
        py_top,
        L
    )

    # Fase 13.6 Rev.105 — moldura geral dinâmica.
    # A esquerda acompanha a moldura do QDC (que já inclui o PE externo);
    # a direita acompanha a Lista de Circuitos; a base acompanha o conteúdo.
    folga_moldura_geral_rev102 = 0.45
    x_geral_esq_rev102 = min(x_moldura_esq_rev97, px1) - folga_moldura_geral_rev102
    x_geral_dir_rev102 = max(x_moldura_dir_rev97, px2) + folga_moldura_geral_rev102
    y_geral_top_rev102 = max(y_moldura_top_rev97, py_top) + 1.05
    y_geral_bottom_rev102 = min(
        y_moldura_bottom_rev97,
        painel_y_bottom_rev99
    ) - folga_moldura_geral_rev102

    _rect(
        msp,
        x_geral_esq_rev102,
        y_geral_bottom_rev102,
        x_geral_dir_rev102,
        y_geral_top_rev102,
        L
    )

    # Rev.76 — 1º DJ da 3ª linha física: entrada do 1º borne sem bolinha.
    if trilhos_circuitos >= 2 and circuitos_geom:
        fileiras_rev75 = {}
        for d_rev75, g_rev75 in circuitos_geom:
            chave_y_rev75 = round(float(g_rev75["y1"]), 5)
            fileiras_rev75.setdefault(chave_y_rev75, []).append((d_rev75, g_rev75))

        lista_fileiras_rev75 = [
            sorted(fileiras_rev75[y_rev75], key=lambda par: float(par[1]["x1"]))
            for y_rev75 in sorted(fileiras_rev75.keys(), reverse=True)
        ]

        if len(lista_fileiras_rev75) >= 2 and lista_fileiras_rev75[1]:
            # Rev.76 — 3ª linha física = 2ª fileira de DJs terminais.
            d3_rev75, g3_rev75 = lista_fileiras_rev75[1][0]
            fases3_rev75 = _fases_do_texto(d3_rev75.get("fase", ""))

            if fases3_rev75:
                fase3_rev75 = fases3_rev75[0]
                x3_rev75 = float(_polo_para_fase(d3_rev75, g3_rev75, fase3_rev75))

                candidatos_rev75 = [
                    cand for cand in _QDC_NODE_CANDIDATES
                    if (
                        cand.get("msp") is msp
                        and str(cand.get("token", "")).upper() == str(fase3_rev75).upper()
                        and abs(float(cand["x"]) - x3_rev75) <= 0.02
                        and float(cand["y"]) >= float(g3_rev75["y2"]) - 0.05
                    )
                ]

                if candidatos_rev75:
                    alvo_rev75 = min(
                        candidatos_rev75,
                        key=lambda cand: abs(float(cand["y"]) - float(g3_rev75["y2"]))
                    )
                    _registrar_supressao_no_rev75(
                        msp,
                        alvo_rev75["x"],
                        alvo_rev75["y"],
                        fase3_rev75,
                        0.03
                    )

    # Rev.57 — agora TODOS os DG/DPS/DR/DJs de TODAS as fileiras
    # já existem. Fazemos o recorte final dos cabos que passam por trás.
    _reclipar_condutores_com_todos_aparelhos(msp)

    # Rev.37 — com toda a fiação pronta, confirmar os nós reais.
    _finalizar_nos_topologicos(msp)

    # Rev.84 — mantém o aparo conservador para demais casos.
    _aparar_sobras_horizontais_fase_rev84(msp)

    # Rev.85 — nos corredores de distribuição conhecidos, a geometria
    # horizontal é reconstruída a partir da TOPOLOGIA registrada.
    # Isto impede que a fase A herde prolongamentos de outro cabo A.
    _normalizar_pistas_horizontais_rev85(msp)

    # As bolinhas continuam sendo desenhadas por último.
    _desenhar_nos_logicos_finais_rev82(msp)

    return {
        "origem": (x0, ybase),
        "largura": largura,
        "altura": altura,
        "qdc_posicoes": mapa.get("qdc_posicoes"),
        "linhas": linhas,
        "colunas": colunas,
        "tipo_desenho": "vista_frontal_executiva",
    }
