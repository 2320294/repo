import math


LAYER_ROTA = "PROJ_ELETRICA_ROTEAMENTO"
LAYER_ROTA_TEXTO = "PROJ_ELETRICA_ROTEAMENTO_TEXTO"

# Se o caminho pela rede existente ultrapassar este fator em relação
# à ligação direta QDC -> ambiente, abre-se um novo tronco a partir do QDC.
FATOR_MAX_DESVIO_REDE = 1.28


def _dist(a, b):
    return math.hypot(
        float(b[0]) - float(a[0]),
        float(b[1]) - float(a[1])
    )


def _angulo(cx, cy, p):
    return math.degrees(
        math.atan2(
            float(p[1]) - cy,
            float(p[0]) - cx
        )
    ) % 360.0


def _arco_suave(
    msp,
    p1,
    p2,
    indice=0,
    layer=LAYER_ROTA
):
    """
    Desenha ARC circular real, de baixa curvatura.
    Não usa LINE.
    """
    x1, y1 = map(float, p1)
    x2, y2 = map(float, p2)

    dx = x2 - x1
    dy = y2 - y1
    corda = math.hypot(dx, dy)

    if corda < 0.05:
        return None

    # Curvatura discreta: quase direto, mas sem virar segmento reto.
    flecha = min(
        0.22,
        max(
            0.055,
            corda * 0.030
        )
    )

    sinal = (
        1.0
        if int(indice) % 2 == 0
        else -1.0
    )

    nx = -dy / corda
    ny = dx / corda

    mx = (x1 + x2) / 2.0
    my = (y1 + y2) / 2.0

    raio = (
        (corda * corda)
        / (8.0 * flecha)
        + flecha / 2.0
    )

    centro_offset = raio - flecha

    cx = (
        mx
        - sinal
        * nx
        * centro_offset
    )

    cy = (
        my
        - sinal
        * ny
        * centro_offset
    )

    a1 = _angulo(
        cx,
        cy,
        (x1, y1)
    )

    a2 = _angulo(
        cx,
        cy,
        (x2, y2)
    )

    delta = (
        a2 - a1
    ) % 360.0

    # add_arc percorre CCW: escolhe sempre o arco menor.
    if delta <= 180.0:
        inicio = a1
        fim = a2
    else:
        inicio = a2
        fim = a1

    return msp.add_arc(
        center=(cx, cy),
        radius=raio,
        start_angle=inicio,
        end_angle=fim,
        dxfattribs={
            "layer": layer
        }
    )


def _normalizar_nome(nome):
    return " ".join(
        str(nome or "")
        .upper()
        .strip()
        .split()
    )


def _ambientes_circuito(circuito):
    lista = circuito.get(
        "ambientes"
    )

    if (
        isinstance(
            lista,
            (list, tuple)
        )
        and lista
    ):
        return [
            str(x).strip()
            for x in lista
            if str(x).strip()
        ]

    ambiente = str(
        circuito.get(
            "ambiente",
            ""
        )
        or ""
    )

    if not ambiente:
        return []

    return [
        x.strip()
        for x in ambiente.split("+")
        if x.strip()
    ]


def _luminarias_por_ambiente(
    pontos_eletricos
):
    saida = {}

    for ponto in (
        pontos_eletricos
        or []
    ):
        if (
            str(
                ponto.get(
                    "tipo",
                    ""
                )
            ).upper()
            != "ILUMINACAO"
        ):
            continue

        ambiente = (
            _normalizar_nome(
                ponto.get(
                    "ambiente"
                )
            )
        )

        xy = ponto.get(
            "ponto"
        )

        if (
            not ambiente
            or not xy
        ):
            continue

        saida.setdefault(
            ambiente,
            []
        ).append(
            tuple(xy)
        )

    return saida


def _circuitos_por_ambiente(
    circuitos
):
    """
    Retorna todos os circuitos que precisam chegar ao nó
    de distribuição de cada ambiente.
    """
    mapa = {}

    for circuito in (
        circuitos
        or []
    ):
        numero = int(
            circuito.get(
                "numero",
                0
            )
            or 0
        )

        if numero <= 0:
            continue

        for ambiente in (
            _ambientes_circuito(
                circuito
            )
        ):
            chave = (
                _normalizar_nome(
                    ambiente
                )
            )

            mapa.setdefault(
                chave,
                set()
            ).add(
                numero
            )

    return mapa


def _circuitos_iluminacao_por_ambiente(
    circuitos
):
    """
    Nas derivações entre luminárias do mesmo ambiente
    transitam somente os circuitos de iluminação daquele ambiente.
    """
    mapa = {}

    for circuito in (
        circuitos
        or []
    ):
        if (
            str(
                circuito.get(
                    "tipo",
                    ""
                )
            ).upper()
            != "ILUMINAÇÃO".upper()
        ):
            continue

        numero = int(
            circuito.get(
                "numero",
                0
            )
            or 0
        )

        if numero <= 0:
            continue

        for ambiente in (
            _ambientes_circuito(
                circuito
            )
        ):
            chave = (
                _normalizar_nome(
                    ambiente
                )
            )

            mapa.setdefault(
                chave,
                set()
            ).add(
                numero
            )

    return mapa


def _selecionar_luminaria_principal(
    luminarias,
    qdc
):
    """
    Escolhe como nó principal do ambiente a luminária
    geometricamente mais próxima do QDC.
    """
    return min(
        luminarias,
        key=lambda pt:
            _dist(
                qdc,
                pt
            )
    )


def _nos_principais(
    qdc,
    luminarias_por_ambiente,
    circuitos_por_ambiente
):
    nos = []

    for ambiente, nums in (
        circuitos_por_ambiente.items()
    ):
        luminarias = (
            luminarias_por_ambiente.get(
                ambiente,
                []
            )
        )

        if not luminarias:
            continue

        principal = (
            _selecionar_luminaria_principal(
                luminarias,
                qdc
            )
        )

        nos.append({
            "id":
                f"AMB_{len(nos)+1}",
            "ambiente":
                ambiente,
            "ponto":
                tuple(principal),
            "luminarias":
                list(luminarias),
            "circuitos":
                set(nums),
            "dist_qdc":
                _dist(
                    qdc,
                    principal
                ),
        })

    # Mais próximos primeiro. Assim o tronco cresce da origem para fora.
    nos.sort(
        key=lambda n: (
            n["dist_qdc"],
            n["ambiente"]
        )
    )

    return nos


def _construir_rede_hibrida(
    qdc,
    nos
):
    """
    Fase 11.3 — rede híbrida.

    Para cada ambiente compara:
    1) caminho direto QDC -> ambiente;
    2) melhor caminho usando um nó já pertencente à rede.

    A conexão pela rede só é aceita se o percurso total desde o QDC
    não exceder FATOR_MAX_DESVIO_REDE vezes o caminho direto.

    Isso permite vários troncos saindo do QDC quando necessário,
    evitando a volta excessiva observada na Fase 11.3.
    """
    conectados = [{
        "id": "QDC",
        "ambiente": "QDC",
        "ponto": tuple(qdc),
        "dist_raiz": 0.0,
    }]

    arestas = []

    for no in nos:
        direto = float(
            no["dist_qdc"]
        )

        melhor_parent = None
        melhor_total = None
        melhor_trecho = None

        # Procura a melhor alternativa pela REDE EXISTENTE.
        # O QDC é comparado separadamente como caminho direto; se ele
        # participar desta busca, pela desigualdade triangular sempre
        # venceria e impediria qualquer compartilhamento.
        for candidato in conectados:
            if candidato["id"] == "QDC":
                continue

            trecho = _dist(
                candidato["ponto"],
                no["ponto"]
            )

            total = (
                float(
                    candidato.get(
                        "dist_raiz",
                        0.0
                    )
                )
                + trecho
            )

            if (
                melhor_total is None
                or total < melhor_total
            ):
                melhor_total = total
                melhor_trecho = trecho
                melhor_parent = candidato

        # Evita "pegar carona" numa rede que torne o percurso total
        # significativamente maior que sair diretamente do QDC.
        usar_rede = (
            melhor_parent is not None
            and melhor_parent["id"] != "QDC"
            and melhor_total
                <= direto
                * FATOR_MAX_DESVIO_REDE
        )

        if usar_rede:
            origem = melhor_parent
            dist_raiz = melhor_total
            criterio = "REDE_EXISTENTE"
        else:
            origem = conectados[0]
            dist_raiz = direto
            criterio = "NOVO_TRONCO_QDC"

        arestas.append({
            "origem_id":
                origem["id"],
            "destino_id":
                no["id"],
            "origem_ambiente":
                origem["ambiente"],
            "destino_ambiente":
                no["ambiente"],
            "inicio":
                origem["ponto"],
            "fim":
                no["ponto"],
            "circuitos":
                set(
                    no["circuitos"]
                ),
            "criterio":
                criterio,
            "dist_raiz":
                dist_raiz,
            "dist_direta":
                direto,
        })

        conectado = dict(no)
        conectado[
            "dist_raiz"
        ] = dist_raiz

        conectados.append(
            conectado
        )

    return arestas


def _acumular_circuitos_ate_qdc(
    arestas
):
    """
    Um circuito que atende um ambiente deve aparecer em todos
    os trechos ancestrais até o QDC.
    """
    por_destino = {
        a["destino_id"]: a
        for a in arestas
    }

    parent = {
        a["destino_id"]:
            a["origem_id"]
        for a in arestas
    }

    cargas_finais = {
        a["destino_id"]:
            set(
                a.get(
                    "circuitos",
                    set()
                )
            )
        for a in arestas
    }

    for destino_id, circuitos in list(
        cargas_finais.items()
    ):
        atual = destino_id

        while (
            atual
            and atual != "QDC"
        ):
            aresta = (
                por_destino.get(
                    atual
                )
            )

            if aresta is None:
                break

            aresta[
                "circuitos"
            ].update(
                circuitos
            )

            atual = parent.get(
                atual
            )

    return arestas


def _arestas_luminarias_secundarias(
    nos,
    circuitos_iluminacao
):
    """
    Liga TODAS as luminárias de cada ambiente.

    A luminária principal já recebe a rede troncal.
    As demais são conectadas internamente por uma pequena árvore
    incremental, sempre em ARC, evitando deixar ponto de luz solto.
    """
    saida = []

    for no in nos:
        ambiente = no[
            "ambiente"
        ]

        principal = tuple(
            no["ponto"]
        )

        restantes = [
            tuple(pt)
            for pt in no.get(
                "luminarias",
                []
            )
            if _dist(
                pt,
                principal
            ) > 1e-6
        ]

        conectados = [
            principal
        ]

        while restantes:
            melhor = None

            for origem in conectados:
                for destino in restantes:
                    d = _dist(
                        origem,
                        destino
                    )

                    candidato = (
                        d,
                        origem,
                        destino
                    )

                    if (
                        melhor is None
                        or candidato[0]
                            < melhor[0]
                    ):
                        melhor = candidato

            _, origem, destino = melhor

            saida.append({
                "origem_ambiente":
                    ambiente,
                "destino_ambiente":
                    ambiente,
                "inicio":
                    origem,
                "fim":
                    destino,
                "circuitos":
                    set(
                        circuitos_iluminacao.get(
                            ambiente,
                            set()
                        )
                    ),
                "criterio":
                    "LUMINARIA_SECUNDARIA",
            })

            conectados.append(
                destino
            )

            restantes.remove(
                destino
            )

    return saida


def desenhar_rotas_qdc_iluminacao(
    msp,
    qdc_info,
    pontos_eletricos,
    circuitos,
):
    """
    Fase 11.3

    - Rede troncal híbrida.
    - Pode criar mais de uma saída no QDC quando a rede existente
      causaria percurso excessivo.
    - Considera comprimento acumulado desde o QDC.
    - Liga todas as luminárias do ambiente.
    - Soleiras e portas não são nós.
    - Somente ARC; nenhuma LINE.
    """
    if (
        not qdc_info
        or not circuitos
    ):
        return []

    qdc = tuple(
        qdc_info.get(
            "centro_externo"
        )
        or qdc_info.get(
            "centro"
        )
        or ()
    )

    if len(qdc) < 2:
        return []

    luminarias = (
        _luminarias_por_ambiente(
            pontos_eletricos
        )
    )

    circuitos_ambiente = (
        _circuitos_por_ambiente(
            circuitos
        )
    )

    circuitos_luz = (
        _circuitos_iluminacao_por_ambiente(
            circuitos
        )
    )

    nos = _nos_principais(
        qdc,
        luminarias,
        circuitos_ambiente
    )

    if not nos:
        return []

    tronco = (
        _construir_rede_hibrida(
            qdc,
            nos
        )
    )

    tronco = (
        _acumular_circuitos_ate_qdc(
            tronco
        )
    )

    secundarias = (
        _arestas_luminarias_secundarias(
            nos,
            circuitos_luz
        )
    )

    rotas = []

    todas_arestas = (
        tronco
        + secundarias
    )

    for indice, trecho in enumerate(
        todas_arestas
    ):
        entidade = _arco_suave(
            msp,
            trecho["inicio"],
            trecho["fim"],
            indice=indice,
            layer=LAYER_ROTA
        )

        if entidade is None:
            continue

        rotas.append({
            "tipo_rede":
                (
                    "LUMINARIA_INTERNA"
                    if trecho.get(
                        "criterio"
                    )
                    == "LUMINARIA_SECUNDARIA"
                    else "TRONCAL_HIBRIDA"
                ),
            "origem_ambiente":
                trecho[
                    "origem_ambiente"
                ],
            "destino_ambiente":
                trecho[
                    "destino_ambiente"
                ],
            "inicio":
                trecho[
                    "inicio"
                ],
            "fim":
                trecho[
                    "fim"
                ],
            "circuitos":
                sorted(
                    trecho.get(
                        "circuitos",
                        set()
                    )
                ),
            "criterio":
                trecho.get(
                    "criterio",
                    ""
                ),
            "entidade":
                "ARC",
        })

    return rotas
