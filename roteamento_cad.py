import math


LAYER_ROTA = "PROJ_ELETRICA_ROTEAMENTO"
LAYER_ROTA_TEXTO = "PROJ_ELETRICA_ROTEAMENTO_TEXTO"


def _dist(a, b):
    return math.hypot(float(b[0])-float(a[0]), float(b[1])-float(a[1]))


def _angulo(cx, cy, p):
    return math.degrees(
        math.atan2(float(p[1])-cy, float(p[0])-cx)
    ) % 360.0


def _arco_suave(msp, p1, p2, indice=0, layer=LAYER_ROTA):
    """
    ARC circular real, de baixa curvatura.
    Não cria LINE.

    A flecha é pequena para o traçado continuar visualmente quase direto,
    porém reconhecível como eletroduto em arco.
    """
    x1, y1 = map(float, p1)
    x2, y2 = map(float, p2)
    dx, dy = x2-x1, y2-y1
    corda = math.hypot(dx, dy)

    if corda < 0.05:
        return None

    # Fase 11.2: ainda mais discreto que na 11.1.
    flecha = min(0.24, max(0.06, corda * 0.032))
    sinal = 1.0 if int(indice) % 2 == 0 else -1.0

    nx, ny = -dy/corda, dx/corda
    mx, my = (x1+x2)/2.0, (y1+y2)/2.0

    raio = (corda*corda)/(8.0*flecha) + flecha/2.0
    centro_offset = raio - flecha

    cx = mx - sinal * nx * centro_offset
    cy = my - sinal * ny * centro_offset

    a1 = _angulo(cx, cy, (x1, y1))
    a2 = _angulo(cx, cy, (x2, y2))
    delta = (a2-a1) % 360.0

    # add_arc percorre CCW; escolhe sempre o arco menor.
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


def _normalizar_nome(nome):
    return " ".join(str(nome or "").upper().strip().split())


def _ambientes_circuito(circuito):
    lista = circuito.get("ambientes")
    if isinstance(lista, (list, tuple)) and lista:
        return [
            str(x).strip()
            for x in lista
            if str(x).strip()
        ]

    amb = str(circuito.get("ambiente", "") or "")
    if not amb:
        return []

    return [
        x.strip()
        for x in amb.split("+")
        if x.strip()
    ]


def _ponto_distribuicao_por_ambiente(pontos_eletricos, qdc):
    """
    O nó de distribuição de cada ambiente continua sendo uma luminária.
    Se houver mais de uma luminária, usa a que fica mais próxima do QDC
    como ponto de entrada/distribuição do ambiente nesta fase.
    """
    candidatos = {}

    for p in pontos_eletricos or []:
        if str(p.get("tipo", "")).upper() != "ILUMINACAO":
            continue

        ambiente = _normalizar_nome(p.get("ambiente"))
        ponto = p.get("ponto")

        if not ambiente or not ponto:
            continue

        candidatos.setdefault(
            ambiente,
            []
        ).append(tuple(ponto))

    saida = {}

    for ambiente, pts in candidatos.items():
        saida[ambiente] = min(
            pts,
            key=lambda pt: _dist(qdc, pt)
        )

    return saida


def _nos_necessarios(circuitos, pontos_por_ambiente):
    """
    Reúne cada ambiente apenas uma vez, independentemente da quantidade
    de circuitos que o atravessarão. Isto é o que elimina o efeito
    'estrela' da Fase 11.2.
    """
    usados = {}

    for circuito in circuitos or []:
        numero = int(
            circuito.get("numero", 0)
            or 0
        )

        for ambiente in _ambientes_circuito(circuito):
            chave = _normalizar_nome(ambiente)
            ponto = pontos_por_ambiente.get(chave)

            if ponto is None:
                continue

            if chave not in usados:
                usados[chave] = {
                    "ambiente": ambiente,
                    "ponto": ponto,
                    "circuitos": set(),
                }

            if numero > 0:
                usados[chave]["circuitos"].add(numero)

    return list(usados.values())


def _montar_arvore_troncal(qdc, nos):
    """
    Constrói uma árvore física compartilhada enraizada no QDC.

    Estratégia:
    - começa no QDC;
    - a cada passo conecta o nó ainda não atendido ao ponto já pertencente
      à rede que produza o menor novo trecho;
    - cada ambiente entra na rede uma única vez.

    É uma árvore de expansão incremental (estilo Prim), portanto reduz
    drasticamente duplicidade de trajetos e cruzamentos quando comparada
    ao modelo estrela QDC -> cada carga.
    """
    if not nos:
        return []

    conectados = [{
        "id": "QDC",
        "ambiente": "QDC",
        "ponto": tuple(qdc),
    }]

    restantes = [
        {
            "id": f"A{i}",
            "ambiente": n["ambiente"],
            "ponto": tuple(n["ponto"]),
            "circuitos": set(n.get("circuitos", set())),
        }
        for i, n in enumerate(nos, start=1)
    ]

    arestas = []

    while restantes:
        melhor = None

        for origem in conectados:
            for destino in restantes:
                d = _dist(
                    origem["ponto"],
                    destino["ponto"]
                )

                candidato = (
                    d,
                    origem["id"],
                    destino["id"],
                    origem,
                    destino
                )

                if (
                    melhor is None
                    or candidato[:3] < melhor[:3]
                ):
                    melhor = candidato

        _, _, _, origem, destino = melhor

        arestas.append({
            "origem_id": origem["id"],
            "destino_id": destino["id"],
            "origem_ambiente": origem["ambiente"],
            "destino_ambiente": destino["ambiente"],
            "inicio": origem["ponto"],
            "fim": destino["ponto"],
        })

        conectados.append(destino)
        restantes.remove(destino)

    return arestas


def _indexar_arvore(qdc, nos, arestas):
    """
    Cria parent map para sabermos quais circuitos utilizam cada trecho.
    Isso ainda não é desenhado como texto, mas já prepara a Fase 11.3.
    """
    nodes = {
        "QDC": {
            "ambiente": "QDC",
            "ponto": tuple(qdc),
        }
    }

    for i, n in enumerate(nos, start=1):
        nodes[f"A{i}"] = {
            "ambiente": n["ambiente"],
            "ponto": tuple(n["ponto"]),
            "circuitos": set(n.get("circuitos", set())),
        }

    parent = {}
    edge_by_child = {}

    for idx, a in enumerate(arestas):
        child = a["destino_id"]
        parent[child] = a["origem_id"]
        edge_by_child[child] = idx

    return nodes, parent, edge_by_child


def _atribuir_circuitos_aos_trechos(
    circuitos,
    nos,
    arestas,
    parent,
    edge_by_child
):
    """
    Para cada circuito, sobe de cada ambiente atendido até o QDC,
    marcando os trechos físicos usados. Assim um mesmo ARC pode transportar
    vários circuitos sem ser desenhado várias vezes.
    """
    ambiente_para_id = {}

    for i, n in enumerate(nos, start=1):
        ambiente_para_id[
            _normalizar_nome(
                n["ambiente"]
            )
        ] = f"A{i}"

    for a in arestas:
        a["circuitos"] = set()

    for circuito in circuitos or []:
        numero = int(
            circuito.get("numero", 0)
            or 0
        )

        if numero <= 0:
            continue

        for ambiente in _ambientes_circuito(circuito):
            atual = ambiente_para_id.get(
                _normalizar_nome(ambiente)
            )

            while atual and atual != "QDC":
                edge_idx = edge_by_child.get(atual)

                if edge_idx is None:
                    break

                arestas[edge_idx]["circuitos"].add(
                    numero
                )

                atual = parent.get(atual)

    return arestas


def desenhar_rotas_qdc_iluminacao(
    msp,
    qdc_info,
    pontos_eletricos,
    circuitos,
):
    """
    Fase 11.2 — REDE TRONCAL COMPARTILHADA

    Diferenças fundamentais em relação à 11.1:
    - não desenha uma rota independente para cada circuito;
    - cada ponto de distribuição entra na rede apenas uma vez;
    - um único ARC físico pode transportar vários circuitos;
    - o primeiro trecho sai do QDC e os demais derivam da própria rede;
    - não desenha etiquetas C01/C02 no meio da planta;
    - não usa LINE.
    """
    if not qdc_info or not circuitos:
        return []

    qdc = tuple(
        qdc_info.get("centro_externo")
        or qdc_info.get("centro")
        or ()
    )

    if len(qdc) < 2:
        return []

    pontos_por_ambiente = (
        _ponto_distribuicao_por_ambiente(
            pontos_eletricos,
            qdc
        )
    )

    nos = _nos_necessarios(
        circuitos,
        pontos_por_ambiente
    )

    if not nos:
        return []

    arestas = _montar_arvore_troncal(
        qdc,
        nos
    )

    _, parent, edge_by_child = (
        _indexar_arvore(
            qdc,
            nos,
            arestas
        )
    )

    arestas = _atribuir_circuitos_aos_trechos(
        circuitos,
        nos,
        arestas,
        parent,
        edge_by_child
    )

    rotas = []

    for idx, trecho in enumerate(arestas):
        entidade = _arco_suave(
            msp,
            trecho["inicio"],
            trecho["fim"],
            indice=idx,
            layer=LAYER_ROTA
        )

        if entidade is None:
            continue

        rotas.append({
            "tipo_rede": "TRONCAL_COMPARTILHADA",
            "origem_ambiente":
                trecho["origem_ambiente"],
            "destino_ambiente":
                trecho["destino_ambiente"],
            "inicio":
                trecho["inicio"],
            "fim":
                trecho["fim"],
            "circuitos":
                sorted(trecho["circuitos"]),
            "entidade":
                "ARC",
        })

    return rotas
