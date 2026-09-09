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
    Fase 13.6 Rev.57:
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
# FASE 13.6 REV.57 — PASSAGENS "POR TRÁS" DE TODOS OS APARELHOS
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


def _finalizar_nos_topologicos(msp):
    """
    Regra ÚNICA para todos os cabos do QDC:
    bolinha somente quando o ponto tiver 3 ou mais ramos reais; raio 0,035.
    """
    vistos = set()

    for cand in list(_QDC_NODE_CANDIDATES):
        if cand.get("msp") is not msp:
            continue

        chave = (
            round(float(cand["x"]), 7),
            round(float(cand["y"]), 7),
            str(cand["token"]),
        )
        if chave in vistos:
            continue
        vistos.add(chave)

        ramos = _ramos_reais_no_ponto(
            msp,
            cand["x"],
            cand["y"],
            cand["token"]
        )

        if len(ramos) >= 3:
            _desenhar_no_confirmado(
                msp,
                cand["x"],
                cand["y"],
                cand["token"],
                cand["raio"]
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

    # Fase 13.6 Rev.57:
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

    # Fase 13.6 Rev.57:
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
        # Fase 13.6 Rev.57:
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
    polilinhas_ambientes
):
    """
    Fase 13.6 Rev.57 — QDC executivo no CAD.

    O desenho passa a se aproximar de um diagrama de montagem real:
    trilhos DIN, dispositivos frontais, barramento pente, barramentos
    N/PE, condutores por função/fase e quadro lateral de circuitos.
    """
    mapa = dict(mapa or {})
    if mapa.get("status") != "ok":
        return None

    _QDC_DJ_RECTS.clear()
    _QDC_TERMINAL_RECTS.clear()
    _QDC_NODE_CANDIDATES.clear()

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

    # Fase 13.6 Rev.57:
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

    # Fase 13.6 Rev.57 — padrão modular do QDC.
    # Cada polo ocupa exatamente 0,45 unidade CAD:
    # 1P=0,45 | 2P=0,90 | 3P=1,35 | 4P=1,80.
    # A mesma regra vale para DJ/DG, IDR/DR e DPS.
    modulo_w = 0.45
    disp_h = 1.60
    margem_x = 1.15
    painel_circuitos_w = 10.20
    separacao_painel = 1.60
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
    largura = (
        area_din_w
        + separacao_painel
        + painel_circuitos_w
        + 1.00
    )

    # Fase 13.6 Rev.57:
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
        "VISTA FRONTAL - DIAGRAMA DE MONTAGEM E LIGACOES | FASE 13.6 REV.57",
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

    # Fase 13.6 Rev.57:
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

    # Fase 13.6 Rev.57 — eixo geométrico único do "miolo" do QDC.
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
    # Fase 13.6 Rev.57:
    # corredores exclusivos para A/B/C. O afastamento é propositalmente
    # maior para impedir que uma derivação vertical coincida visualmente
    # com o barramento horizontal de outra fase.
    ESPACAMENTO_BARRAMENTOS_FASE = 0.30
    # Fase 13.6 Rev.57 — grade vertical equidistante das seis linhas
    # As seis linhas/cabos principais do QDC passam a ocupar níveis paralelos
    # com passo único. Isso evita a sensação de linhas comprimidas em uma
    # região e abertas em outra, mantendo A/B/C alinhadas aos bornes do DG.
    # Fase 13.6 Rev.57:
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
        # FASE 13.6 REV.57 — ENTRADA DA REDE
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

        # Fase 13.6 Rev.57:
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
        # FASE 13.6 REV.57 — CONVENÇÃO DE NÓS DE DERIVAÇÃO
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
    # FASE 13.6 REV.57 — NEUTRO DOS IDRs PELO 2º BORNE
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

        # Fase 13.6 Rev.57 — SAÍDAS DOS CIRCUITOS
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

                    # Rev.27: saída terminal absolutamente simples.
                    # O condutor permanece no mesmo eixo do borne até a
                    # saída inferior do QDC — nenhuma curva intermediária.
                    x_fase_saida = x_borne_fase

                    _line(
                        msp,
                        (x_borne_fase, g_saida["y1"]),
                        (x_borne_fase, y_saida_circuito),
                        _layer_por_token(fase_saida)
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
                # Fase 13.6 Rev.57 — GRADE VERTICAL DINÂMICA DA FILEIRA
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

                    # Neutro
                    itens_n_grade = [
                        (d_grade, g_grade)
                        for d_grade, g_grade in itens_grade
                        if g_grade.get("tem_neutro")
                    ]

                    if len(itens_n_grade) >= 2:
                        condutores_horizontais.append(
                            (grupo_grade, "N")
                        )
                    elif len(itens_n_grade) == 1:
                        _, g_n_grade = itens_n_grade[0]
                        x_destino_n_grade = _x_passagem_lateral_disjuntor(
                            g_n_grade,
                            "dir",
                            0.12
                        )

                        if (
                            disp_fonte_grade
                            and geom_fonte_grade
                            and disp_fonte_grade.get("tipo") == "IDR"
                        ):
                            x_origem_n_grade = _mapa_condutores_polos(
                                disp_fonte_grade,
                                geom_fonte_grade
                            ).get("N")
                        else:
                            x_origem_n_grade = neutro["x"]

                        if (
                            x_origem_n_grade is not None
                            and abs(
                                x_origem_n_grade - x_destino_n_grade
                            ) > 1e-9
                        ):
                            condutores_horizontais.append(
                                (grupo_grade, "N")
                            )

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

                        # Nó de derivação no ponto real da saída DG.
                        _no_fase_preenchido(
                            msp,
                            x_polo_dg,
                            y_saida_dg,
                            token_dg
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

                        # Rev.42 — PE dos DPS corre por fora do barramento
                        # e só entra horizontalmente na altura do 2º borne.
                        x_pe_externo = pe["x"] - 0.28

                        _polyline(
                            msp,
                            [
                                (x_ultimo_pe_dps, y_pe_dps),
                                (x_pe_externo, y_pe_dps),
                                (x_pe_externo, y_borne_pe_distribuicao),
                                (pe["x"], y_borne_pe_distribuicao),
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
                    # NEUTRO DO GRUPO
                    # --------------------------------------------------
                    # Somente circuitos monopolares utilizam neutro.
                    # Se houver IDR, o neutro obrigatoriamente entra no
                    # IDR e SAI do IDR antes de alimentar esses circuitos.
                    itens_com_neutro = [
                        (
                            d_item,
                            g_item
                        )
                        for d_item, g_item
                        in itens_grupo
                        if g_item.get(
                            "tem_neutro"
                        )
                    ]

                    if itens_com_neutro:
                        y_n_grupo = niveis_horizontais.get(
                            (grupo, "N"),
                            y_corredor_n
                        )

                        x_n_primeiro = _x_passagem_lateral_disjuntor(
                            itens_com_neutro[0][1],
                            "dir",
                            0.12
                        )

                        x_n_ultimo = _x_passagem_lateral_disjuntor(
                            itens_com_neutro[-1][1],
                            "dir",
                            0.12
                        )

                        # Segmento de neutro exclusivo deste grupo.
                        _line(
                            msp,
                            (
                                min(
                                    x_n_primeiro,
                                    x_n_ultimo
                                ),
                                y_n_grupo
                            ),
                            (
                                max(
                                    x_n_primeiro,
                                    x_n_ultimo
                                ),
                                y_n_grupo
                            ),
                            LN
                        )

                        # Derivações N para os circuitos do grupo.
                        # A passagem fica fora do corpo do disjuntor e cada
                        # ponto onde a horizontal continua recebe bolinha azul.
                        xs_neutro_grupo = [
                            _x_passagem_lateral_disjuntor(
                                g_n,
                                "dir",
                                0.12
                            )
                            for d_n, g_n in itens_com_neutro
                        ]

                        # Rev.32 — primeiro identificamos de que lado o neutro
                        # entra no grupo. O extremo mais distante da fonte é a
                        # CURVA FINAL e não recebe bolinha.
                        par_idr = dr_disp_geom_por_grupo.get(
                            grupo
                        )

                        x_fonte_neutro = neutro["x"]
                        x_n_idr = None
                        geom_idr = None

                        if par_idr is not None:
                            disp_idr, geom_idr = par_idr
                            mapa_polos_idr = _mapa_condutores_polos(
                                disp_idr,
                                geom_idr
                            )
                            x_n_idr = mapa_polos_idr.get("N")
                            if x_n_idr is not None:
                                x_fonte_neutro = x_n_idr

                        if xs_neutro_grupo:
                            x_entrada_neutro = min(
                                xs_neutro_grupo,
                                key=lambda xx: abs(xx - x_fonte_neutro)
                            )
                            x_terminal_neutro = max(
                                xs_neutro_grupo,
                                key=lambda xx: abs(xx - x_fonte_neutro)
                            )
                        else:
                            x_entrada_neutro = x_n_primeiro
                            x_terminal_neutro = x_n_ultimo

                        for d_n, g_n in itens_com_neutro:
                            x_n_saida = _x_passagem_lateral_disjuntor(
                                g_n,
                                "dir",
                                0.12
                            )

                            _line(
                                msp,
                                (
                                    x_n_saida,
                                    y_n_grupo
                                ),
                                (
                                    x_n_saida,
                                    y_saida_circuito
                                ),
                                LN
                            )

                            # Bolinha azul SOMENTE em ramificação real.
                            # O extremo mais distante da fonte é apenas a
                            # última curva horizontal -> vertical.
                            if (
                                xs_neutro_grupo
                                and abs(
                                    x_n_saida - x_terminal_neutro
                                ) > 1e-9
                            ):
                                _no_fase_preenchido(
                                    msp,
                                    x_n_saida,
                                    y_n_grupo,
                                    "N"
                                )

                        if par_idr is not None:
                            # Se o grupo usa neutro, o IDR precisa possuir
                            # polo N disponível. A saída permanece reta.
                            if x_n_idr is not None:
                                _polyline(
                                    msp,
                                    [
                                        (
                                            x_n_idr,
                                            geom_idr["y1"]
                                        ),
                                        (
                                            x_n_idr,
                                            y_n_grupo
                                        ),
                                        (
                                            x_entrada_neutro,
                                            y_n_grupo
                                        ),
                                    ],
                                    LN
                                )
                        else:
                            # Grupo SEM DR: neutro vem diretamente do
                            # barramento principal N até o extremo mais próximo.
                            _polyline(
                                msp,
                                [
                                    (
                                        neutro["x"],
                                        neutro["y_bottom"]
                                    ),
                                    (
                                        neutro["x"],
                                        y_n_grupo
                                    ),
                                    (
                                        x_entrada_neutro,
                                        y_n_grupo
                                    ),
                                ],
                                LN
                            )

                    # Fase 13.6 Rev.57:
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

                                # Rev.32 — ajuste EXATAMENTE no final correto:
                                # DR3 / fase A / C08.
                                # A pista horizontal termina 0,105 à esquerda
                                # do borne do C08, portanto a curva para vertical
                                # não coincide com a entrada do disjuntor.
                                if (
                                    str(grupo).strip().upper() == "DR3"
                                    and str(fase_grupo).strip().upper() == "A"
                                    and str(
                                        d_item.get("identificador", "")
                                        or ""
                                    ).strip().upper() == "C08"
                                ):
                                    x_ponto_fase -= 0.105

                                pontos_fase.append(x_ponto_fase)

                        pontos_fase = sorted(set(pontos_fase))
                        pontos_pente_por_fase[
                            fase_grupo
                        ] = pontos_fase

                        if (
                            pontos_fase
                            and usar_pente
                        ):
                            # Rev.20: a pista existe SOMENTE entre os
                            # polos extremos efetivamente atendidos.
                            # Não há prolongamento antes/depois da curva.
                            x_inicio_pista = min(pontos_fase)
                            x_fim_pista = max(pontos_fase)

                            _line(
                                msp,
                                (
                                    x_inicio_pista,
                                    yy_fase
                                ),
                                (
                                    x_fim_pista,
                                    yy_fase
                                ),
                                _layer_por_token(
                                    fase_grupo
                                )
                            )

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

                                eh_final_dr3_a_c08 = (
                                    str(grupo).strip().upper() == "DR3"
                                    and str(fase_item).strip().upper() == "A"
                                    and str(
                                        d_item.get("identificador", "")
                                        or ""
                                    ).strip().upper() == "C08"
                                )

                                if eh_final_dr3_a_c08:
                                    x_descida = x_polo - 0.105
                                    y_aproximacao_borne = g_item["y2"] + 0.08

                                    # A curva horizontal -> vertical ocorre no
                                    # eixo deslocado. Só perto do C08 voltamos
                                    # ao eixo real do borne, sem sobreposição.
                                    _polyline(
                                        msp,
                                        [
                                            (x_descida, yy_fase),
                                            (x_descida, y_aproximacao_borne),
                                            (x_polo, y_aproximacao_borne),
                                            (x_polo, g_item["y2"]),
                                        ],
                                        _layer_por_token(fase_item)
                                    )
                                else:
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

                                pontos_destino_fase = pontos_desviados
                                if not pontos_destino_fase:
                                    continue

                                # A alimentação entra pelo extremo mais
                                # próximo da fonte. A pista permanece limitada
                                # aos polos extremos. Na Rev.34, nenhum dos dois
                                # extremos recebe bolinha de derivação.
                                x_min_fase = min(pontos_destino_fase)
                                x_max_fase = max(pontos_destino_fase)

                                if abs(x_origem - x_min_fase) <= abs(
                                    x_origem - x_max_fase
                                ):
                                    x_destino_fase = x_min_fase
                                    x_terminal_final = x_max_fase
                                else:
                                    x_destino_fase = x_max_fase
                                    x_terminal_final = x_min_fase

                                # Rev.33 — uma única saída por fase da fonte.
                                # Se a mesma fase do mesmo DR/DG alimentar outra
                                # fileira, prolongamos o tronco existente e
                                # marcamos a ramificação anterior com bolinha.
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
                                    # Se já existe a entrada reta, o mesmo
                                    # eixo vertical é o tronco da derivação.
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

                                        # O ponto anterior passa a ser uma
                                        # derivação real: tronco continua e
                                        # também sai horizontalmente.
                                        _no_fase_preenchido(
                                            msp,
                                            tronco["x"],
                                            y_anterior,
                                            fase_item
                                        )

                                        tronco["y"] = yy_destino

                                _line(
                                    msp,
                                    (x_origem, yy_destino),
                                    (x_destino_fase, yy_destino),
                                    _layer_por_token(fase_item)
                                )

                                # Rev.37 — registra candidatos; decisão final é global.
                                #
                                # Ponto intermediário:
                                # horizontal existe nos dois sentidos e há
                                # descida para DJ -> derivação real.
                                #
                                # Ponto extremo alimentado:
                                # só recebe bolinha se a alimentação chegar
                                # pelo lado OPOSTO ao sentido em que a pista
                                # continua. Nesse caso existem três ramos:
                                # entrada horizontal + continuação horizontal
                                # + descida vertical.
                                #
                                # Se a alimentação chegar pelo mesmo lado em
                                # que a pista continua, o ponto é apenas uma
                                # curva horizontal -> vertical e NÃO é nó.
                                for x_no in pontos_destino_fase:
                                    eh_extremo_esquerdo = (
                                        abs(x_no - x_min_fase) <= 1e-9
                                    )
                                    eh_extremo_direito = (
                                        abs(x_no - x_max_fase) <= 1e-9
                                    )
                                    eh_extremo = (
                                        eh_extremo_esquerdo
                                        or eh_extremo_direito
                                    )

                                    eh_intermediario = not eh_extremo

                                    eh_extremo_alimentado = (
                                        eh_extremo
                                        and abs(
                                            x_no - x_destino_fase
                                        ) <= 1e-9
                                    )

                                    # Na extremidade esquerda a pista segue
                                    # para a direita. Para haver derivação real,
                                    # a fonte precisa chegar pela esquerda.
                                    fonte_chega_lado_oposto_esq = (
                                        eh_extremo_esquerdo
                                        and x_origem < x_no - 1e-9
                                    )

                                    # Na extremidade direita a pista segue
                                    # para a esquerda. Para haver derivação real,
                                    # a fonte precisa chegar pela direita.
                                    fonte_chega_lado_oposto_dir = (
                                        eh_extremo_direito
                                        and x_origem > x_no + 1e-9
                                    )

                                    eh_derivacao_no_extremo = (
                                        eh_extremo_alimentado
                                        and (
                                            fonte_chega_lado_oposto_esq
                                            or fonte_chega_lado_oposto_dir
                                        )
                                    )

                                    if (
                                        eh_intermediario
                                        or eh_derivacao_no_extremo
                                    ):
                                        _no_fase_preenchido(
                                            msp,
                                            x_no,
                                            yy_destino,
                                            fase_item
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

                                # Rev.56 — o trecho final que entra no
                                # próprio DJ tem prioridade para ficar RETO.
                                # Apenas o trecho de passagem/origem pode ser
                                # deslocado se cruzar outro DJ.
                                x_passagem = _x_desvio_para_nao_invadir_dj(
                                    x_origem,
                                    fonte_geom["y1"],
                                    y_corredor_direto,
                                    dj_destino_geom=g_unico,
                                )

                                pontos_rota = [
                                    (x_origem, y_corredor_direto),
                                ]
                                if abs(x_passagem - x_origem) > 1e-9:
                                    pontos_rota.extend([
                                        (x_passagem, y_corredor_direto),
                                    ])
                                pontos_rota.extend([
                                    (x_destino, y_corredor_direto),
                                    (x_destino, g_unico["y2"]),
                                ])

                                _polyline(
                                    msp,
                                    pontos_rota,
                                    _layer_por_token(fase_item)
                                )

        y_rail -= 3.15

    # ========================================================
    # FASE 13.6 REV.57 — PE INDIVIDUAL POR CIRCUITO
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

            # Nível individual logo acima da ponta final global.
            y_final_pe_circ = (
                y_saida_circuito_global
                + 0.10
                + idx_pe_circ * 0.035
            )

            _polyline(
                msp,
                [
                    (pe["x"], y_borne_pe_circ),
                    (x_corredor_pe_circ, y_borne_pe_circ),
                    (x_corredor_pe_circ, y_final_pe_circ),
                    (x_saida_pe_circ, y_final_pe_circ),
                    (x_saida_pe_circ, y_saida_circuito_global),
                ],
                LPE
            )

    # ========================================================
    # FASE 13.6 REV.57 — CHICOTES FINAIS AGRUPADOS POR CIRCUITO
    # ========================================================
    # Regras visuais:
    # - cabos do MESMO circuito ficam próximos;
    # - entre circuitos existe um afastamento maior;
    # - C01, C02... ficam centralizados sob o respectivo grupo;
    # - não voltam as inscrições F/N/PE.
    #
    # As conexões acima já chegam à cota y_saida_circuito_global.
    # A partir daí organizamos apenas a apresentação final.
    if circuitos_geom:
        qtd_circuitos_saida = len(circuitos_geom)

        # Composição real de cada chicote.
        dados_chicotes = []
        for d_ch, g_ch in circuitos_geom:
            fases_ch = _fases_do_texto(
                d_ch.get("fase", "")
            )

            tokens_ch = list(fases_ch)

            tem_neutro_ch = (
                len(fases_ch) == 1
                and int(d_ch.get("modulos", 1) or 1) == 1
            )
            if tem_neutro_ch:
                tokens_ch.append("N")

            tokens_ch.append("PE")

            dados_chicotes.append(
                (d_ch, g_ch, tokens_ch)
            )

        # Espaçamento interno menor e espaço entre circuitos maior.
        espaco_interno = 0.10
        espaco_entre_circuitos = 0.42

        larguras = [
            max(
                0.12,
                (len(tokens_ch) - 1) * espaco_interno
            )
            for _, _, tokens_ch in dados_chicotes
        ]

        largura_necessaria = (
            sum(larguras)
            + max(
                0,
                qtd_circuitos_saida - 1
            ) * espaco_entre_circuitos
        )

        largura_disponivel_saida = max(
            1.0,
            din_x2 - din_x1 - 0.60
        )

        # Se houver muitos circuitos, reduz somente o espaço ENTRE grupos
        # antes de tocar no afastamento interno do mesmo circuito.
        if (
            qtd_circuitos_saida > 1
            and largura_necessaria > largura_disponivel_saida
        ):
            espaco_entre_circuitos = max(
                0.18,
                (
                    largura_disponivel_saida
                    - sum(larguras)
                )
                / (qtd_circuitos_saida - 1)
            )

            largura_necessaria = (
                sum(larguras)
                + (qtd_circuitos_saida - 1)
                * espaco_entre_circuitos
            )

        # Último fallback para quadros excepcionalmente carregados.
        if largura_necessaria > largura_disponivel_saida:
            fator = max(
                0.65,
                largura_disponivel_saida
                / largura_necessaria
            )
            espaco_interno *= fator
            espaco_entre_circuitos *= fator

            larguras = [
                max(
                    0.10,
                    (len(tokens_ch) - 1)
                    * espaco_interno
                )
                for _, _, tokens_ch in dados_chicotes
            ]

            largura_necessaria = (
                sum(larguras)
                + max(
                    0,
                    qtd_circuitos_saida - 1
                )
                * espaco_entre_circuitos
            )

        x_inicio_chicotes = (
            (din_x1 + din_x2) / 2.0
            - largura_necessaria / 2.0
        )

        # Zona final abaixo das rotas individuais de PE.
        y_final_chicotes = y_saida_circuito_global - 0.82
        y_texto_chicotes = y_final_chicotes - 0.20

        x_cursor_chicote = x_inicio_chicotes

        for idx_ch, (d_ch, g_ch, tokens_ch) in enumerate(
            dados_chicotes
        ):
            largura_ch = larguras[idx_ch]

            x_centro_ch = (
                x_cursor_chicote
                + largura_ch / 2.0
            )

            if len(tokens_ch) <= 1:
                xs_destinos_ch = [x_centro_ch]
            else:
                x_primeiro_ch = (
                    x_centro_ch
                    - (len(tokens_ch) - 1)
                    * espaco_interno / 2.0
                )
                xs_destinos_ch = [
                    x_primeiro_ch
                    + i_ch * espaco_interno
                    for i_ch in range(len(tokens_ch))
                ]

            fases_ch = _fases_do_texto(
                d_ch.get("fase", "")
            )

            # Fonte inferior já existente para cada tipo de condutor.
            fontes_ch = []

            for fase_ch in fases_ch:
                fontes_ch.append(
                    (
                        fase_ch,
                        _polo_para_fase(
                            d_ch,
                            g_ch,
                            fase_ch
                        )
                    )
                )

            if "N" in tokens_ch:
                fontes_ch.append(
                    (
                        "N",
                        _x_passagem_lateral_disjuntor(
                            g_ch,
                            "dir",
                            0.12
                        )
                    )
                )

            fontes_ch.append(
                (
                    "PE",
                    _x_passagem_lateral_disjuntor(
                        g_ch,
                        "esq",
                        0.16
                    )
                )
            )

            # Cada circuito recebe uma pequena faixa de transição própria.
            # Os cabos do mesmo circuito permanecem próximos.
            y_faixa_ch = (
                y_saida_circuito_global
                - 0.10
                - idx_ch * 0.045
            )

            for idx_cond_ch, ((token_ch, x_origem_ch), x_destino_ch) in enumerate(
                zip(fontes_ch, xs_destinos_ch)
            ):
                # Dentro do mesmo circuito, níveis quase coincidentes.
                y_cond_ch = (
                    y_faixa_ch
                    - idx_cond_ch * 0.012
                )

                _polyline(
                    msp,
                    [
                        (
                            x_origem_ch,
                            y_saida_circuito_global
                        ),
                        (
                            x_origem_ch,
                            y_cond_ch
                        ),
                        (
                            x_destino_ch,
                            y_cond_ch
                        ),
                        (
                            x_destino_ch,
                            y_final_chicotes
                        ),
                    ],
                    _layer_por_token(token_ch)
                )

            ident_ch = str(
                d_ch.get(
                    "identificador",
                    ""
                )
                or ""
            )

            _texto_central(
                msp,
                ident_ch,
                x_centro_ch - max(0.20, largura_ch / 2.0),
                x_centro_ch + max(0.20, largura_ch / 2.0),
                y_texto_chicotes,
                0.085,
                LT
            )

            x_cursor_chicote += (
                largura_ch
                + espaco_entre_circuitos
            )

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
    # Fase 13.6 Rev.57:
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

        # Fonte de verdade das fases: resultado de balancear_circuitos().
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

    # Rev.57 — agora TODOS os DG/DPS/DR/DJs de TODAS as fileiras
    # já existem. Fazemos o recorte final dos cabos que passam por trás.
    _reclipar_condutores_com_todos_aparelhos(msp)

    # Rev.37 — com toda a fiação pronta, confirmar os nós reais.
    _finalizar_nos_topologicos(msp)

    return {
        "origem": (x0, ybase),
        "largura": largura,
        "altura": altura,
        "qdc_posicoes": mapa.get("qdc_posicoes"),
        "linhas": linhas,
        "colunas": colunas,
        "tipo_desenho": "vista_frontal_executiva",
    }
