import math


LAYER_ROTA = "PROJ_ELETRICA_ROTEAMENTO"
LAYER_ROTA_TEXTO = "PROJ_ELETRICA_ROTEAMENTO_TEXTO"


def _dist(a, b):
    return math.hypot(float(b[0])-float(a[0]), float(b[1])-float(a[1]))


def _angulo(cx, cy, p):
    return math.degrees(math.atan2(float(p[1])-cy, float(p[0])-cx)) % 360.0


def _arco_suave(msp, p1, p2, indice=0, layer=LAYER_ROTA):
    """
    Desenha um ARC circular real entre p1 e p2.
    A flecha é pequena (aprox. 4,5% da corda), apenas para evitar linha reta.
    """
    x1, y1 = map(float, p1)
    x2, y2 = map(float, p2)
    dx, dy = x2-x1, y2-y1
    corda = math.hypot(dx, dy)
    if corda < 0.05:
        return None

    # Curvatura discreta, limitada para não gerar "barriga" exagerada.
    flecha = min(0.32, max(0.08, corda * 0.045))
    sinal = 1.0 if int(indice) % 2 == 0 else -1.0

    nx, ny = -dy/corda, dx/corda
    mx, my = (x1+x2)/2.0, (y1+y2)/2.0

    raio = (corda*corda)/(8.0*flecha) + flecha/2.0
    centro_offset = raio - flecha

    # Centro fica no lado oposto à "barriga" desejada.
    cx = mx - sinal * nx * centro_offset
    cy = my - sinal * ny * centro_offset

    a1 = _angulo(cx, cy, (x1, y1))
    a2 = _angulo(cx, cy, (x2, y2))
    delta = (a2-a1) % 360.0

    # add_arc é CCW: sempre escolhemos o arco menor.
    if delta <= 180.0:
        inicio, fim = a1, a2
    else:
        inicio, fim = a2, a1

    return msp.add_arc(
        center=(cx, cy),
        radius=raio,
        start_angle=inicio,
        end_angle=fim,
        dxfattribs={"layer": layer}
    )


def _ponto_medio_visual(p1, p2):
    return (
        (float(p1[0])+float(p2[0]))/2.0,
        (float(p1[1])+float(p2[1]))/2.0,
    )


def _normalizar_nome(nome):
    return " ".join(str(nome or "").upper().strip().split())


def _no_luz_por_ambiente(pontos_eletricos, qdc):
    candidatos = {}
    for p in pontos_eletricos or []:
        if str(p.get("tipo", "")).upper() != "ILUMINACAO":
            continue
        amb = _normalizar_nome(p.get("ambiente"))
        pt = p.get("ponto")
        if not amb or not pt:
            continue
        candidatos.setdefault(amb, []).append(tuple(pt))

    # Um único ponto de distribuição por ambiente nesta fase:
    # escolhe a luminária mais próxima do QDC.
    saida = {}
    for amb, pts in candidatos.items():
        saida[amb] = min(pts, key=lambda pt: _dist(qdc, pt))
    return saida


def _ambientes_circuito(c):
    lista = c.get("ambientes")
    if isinstance(lista, (list, tuple)) and lista:
        return [str(x) for x in lista if str(x).strip()]
    amb = str(c.get("ambiente", "") or "")
    if not amb:
        return []
    # Compatibilidade com consolidação textual.
    return [x.strip() for x in amb.split("+") if x.strip()]


def _ordenar_nos_vizinho_mais_proximo(origem, nos):
    restantes = list(nos)
    atual = origem
    ordem = []
    while restantes:
        prox = min(restantes, key=lambda p: _dist(atual, p[1]))
        ordem.append(prox)
        atual = prox[1]
        restantes.remove(prox)
    return ordem


def desenhar_rotas_qdc_iluminacao(
    msp,
    qdc_info,
    pontos_eletricos,
    circuitos,
):
    """
    Fase 11.1:
    - QDC continua no local escolhido pelo usuário.
    - O nó de distribuição do ambiente é uma luminária.
    - Soleiras/portas não são nós.
    - Cada circuito percorre os ambientes associados usando ARC suave.
    - Não usa LINE para representar o eletroduto.
    """
    if not qdc_info or not circuitos:
        return []

    qdc = tuple(qdc_info.get("centro_externo") or qdc_info.get("centro") or ())
    if len(qdc) < 2:
        return []

    por_ambiente = _no_luz_por_ambiente(pontos_eletricos, qdc)
    rotas = []

    for idx, c in enumerate(circuitos, start=1):
        numero = int(c.get("numero", idx) or idx)
        ambientes = _ambientes_circuito(c)
        nos = []
        for amb in ambientes:
            pt = por_ambiente.get(_normalizar_nome(amb))
            if pt is not None:
                nos.append((amb, pt))

        if not nos:
            continue

        ordem = _ordenar_nos_vizinho_mais_proximo(qdc, nos)
        atual = qdc
        primeiro_trecho = True

        for trecho_idx, (amb, destino) in enumerate(ordem):
            ent = _arco_suave(
                msp,
                atual,
                destino,
                indice=numero + trecho_idx,
                layer=LAYER_ROTA
            )
            if ent is not None:
                rotas.append({
                    "circuito": numero,
                    "ambiente_destino": amb,
                    "inicio": atual,
                    "fim": destino,
                    "entidade": "ARC",
                })

                # Identifica o circuito apenas no primeiro trecho para não poluir.
                if primeiro_trecho:
                    tx, ty = _ponto_medio_visual(atual, destino)
                    msp.add_text(
                        f"C{numero:02d}",
                        dxfattribs={
                            "layer": LAYER_ROTA_TEXTO,
                            "height": 0.12,
                            "insert": (tx + 0.08, ty + 0.08),
                        }
                    )
                    primeiro_trecho = False

            atual = destino

    return rotas
