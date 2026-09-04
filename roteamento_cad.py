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



def _comprimento_entidade_rota(
    entidade,
    tipo_entidade,
    inicio,
    fim
):
    """
    Comprimento geométrico do elemento efetivamente desenhado.
    """
    try:
        if (
            tipo_entidade == "ARC"
            and hasattr(
                entidade,
                "dxf"
            )
        ):
            raio = float(
                entidade.dxf.radius
            )
            a1 = float(
                entidade.dxf.start_angle
            )
            a2 = float(
                entidade.dxf.end_angle
            )

            delta = (
                a2 - a1
            ) % 360.0

            if delta > 180.0:
                delta = 360.0 - delta

            return (
                raio
                * math.radians(
                    delta
                )
            )

        if (
            tipo_entidade == "LWPOLYLINE"
            and hasattr(
                entidade,
                "get_points"
            )
        ):
            pts = [
                (
                    float(p[0]),
                    float(p[1])
                )
                for p in entidade.get_points(
                    "xy"
                )
            ]

            return sum(
                _dist(
                    a,
                    b
                )
                for a, b in zip(
                    pts[:-1],
                    pts[1:]
                )
            )
    except Exception:
        pass

    return _dist(
        inicio,
        fim
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
    Fase 13.3 Rev.2 — rede distribuída por caixas octogonais.

    Além do critério de menor percurso total, força uma quantidade mínima
    de troncos de saída do QDC para evitar concentrar todos os circuitos
    da residência em um único eletroduto inicial.

    Regra preliminar:
    - até 4 circuitos: pelo menos 2 troncos quando houver ambientes suficientes;
    - 5 a 8 circuitos: pelo menos 2 troncos;
    - acima de 8 circuitos: pelo menos 3 troncos;
    - máximo preliminar: 3 troncos nesta fase.

    O dimensionamento definitivo será refinado posteriormente pela ocupação
    real dos eletrodutos e seção dos condutores.
    """
    conectados = [{
        "id": "QDC",
        "ambiente": "QDC",
        "ponto": tuple(qdc),
        "dist_raiz": 0.0,
    }]

    arestas = []

    # Cada ponto de iluminação é tratado como caixa octogonal 4x4
    # com até 8 entradas/saídas de eletroduto. O QDC não usa esse limite.
    grau_caixa = {
        "QDC": 0
    }

    circuitos_unicos = set()
    for no in nos:
        circuitos_unicos.update(
            no.get(
                "circuitos",
                set()
            )
        )

    qtd_circuitos = len(
        circuitos_unicos
    )

    # Fase 13.3 Rev.2:
    # circuitos terminais devem preferencialmente ser distribuídos em
    # troncos menores, evitando concentrar todos em um único eletroduto.
    # Como referência de topologia, procura limitar a aproximadamente
    # 3 circuitos por saída principal do QDC.
    if len(nos) <= 1:
        qtd_troncos_min = 1
    else:
        qtd_troncos_min = min(
            len(nos),
            max(
                2,
                int(
                    math.ceil(
                        qtd_circuitos
                        / 3.0
                    )
                )
            )
        )

    # Escolhe âncoras distribuídas angularmente em torno do QDC.
    # Isso evita que dois troncos forçados saiam para praticamente
    # a mesma direção da planta.
    ordenados_angulo = sorted(
        nos,
        key=lambda n:
            math.atan2(
                float(n["ponto"][1])
                - float(qdc[1]),
                float(n["ponto"][0])
                - float(qdc[0])
            )
    )

    anchors = set()

    if qtd_troncos_min >= 1:
        for k in range(
            qtd_troncos_min
        ):
            inicio = int(
                k
                * len(ordenados_angulo)
                / qtd_troncos_min
            )
            fim = int(
                (k + 1)
                * len(ordenados_angulo)
                / qtd_troncos_min
            )

            grupo = ordenados_angulo[
                inicio:
                max(
                    inicio + 1,
                    fim
                )
            ]

            escolhido = min(
                grupo,
                key=lambda n:
                    float(
                        n.get(
                            "dist_qdc",
                            0.0
                        )
                    )
            )

            anchors.add(
                escolhido["id"]
            )

    for no in nos:
        direto = float(
            no["dist_qdc"]
        )

        melhor_parent = None
        melhor_total = None

        for candidato in conectados:
            if candidato["id"] == "QDC":
                continue

            # Uma conexão já é consumida pelo trecho de entrada da caixa.
            # Não cria novo ramo se as 8 entradas/saídas já estiverem ocupadas.
            if int(
                grau_caixa.get(
                    candidato["id"],
                    1
                )
                or 0
            ) >= 8:
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
                melhor_parent = candidato

        forcar_qdc = (
            no["id"]
            in anchors
        )

        usar_rede = (
            not forcar_qdc
            and melhor_parent is not None
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
            criterio = (
                "TRONCO_QDC_SETORIZADO"
                if forcar_qdc
                else "NOVO_TRONCO_QDC"
            )

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
            "limite_entradas_caixa":
                8,
            "dist_raiz":
                dist_raiz,
            "dist_direta":
                direto,
        })

        if origem["id"] != "QDC":
            grau_caixa[
                origem["id"]
            ] = (
                int(
                    grau_caixa.get(
                        origem["id"],
                        1
                    )
                    or 0
                )
                + 1
            )

        # A caixa de destino passa a ter uma entrada ocupada pelo
        # eletroduto que acabou de chegar.
        grau_caixa[
            no["id"]
        ] = max(
            1,
            int(
                grau_caixa.get(
                    no["id"],
                    0
                )
                or 0
            )
            + 1
        )

        conectado = dict(no)
        conectado[
            "dist_raiz"
        ] = dist_raiz
        conectado[
            "entradas_ocupadas_tronco"
        ] = grau_caixa[
            no["id"]
        ]

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



# ============================================================
# FASE 13.3 REV.2 — REDISTRIBUIÇÃO FÍSICA AUTOMÁTICA
# ============================================================

DIAMETRO_CONDUTOR_REROTA_MM = {
    1.5: 3.0,
    2.5: 3.6,
    4.0: 4.2,
    6.0: 4.8,
    10.0: 6.1,
    16.0: 7.2,
    25.0: 9.0,
    35.0: 10.2,
    50.0: 12.0,
    70.0: 14.0,
}

DIAMETRO_INTERNO_ELETRODUTO_25_MM = 20.5
OCUPACAO_MAX_TERMINAL = 0.40
MAX_ENTRADAS_CAIXA_OCTOGONAL = 8


def _bitola_rota_circuito(circuito):
    try:
        valor = float(circuito.get("bitola", 0.0) or 0.0)
    except Exception:
        valor = 0.0

    if valor > 0:
        return valor

    tipo = str(circuito.get("tipo", "") or "").upper()
    return 1.5 if "ILUM" in tipo else 2.5


def _area_condutor_rota(bitola_mm2):
    bitola = float(bitola_mm2 or 0.0)
    d = DIAMETRO_CONDUTOR_REROTA_MM.get(bitola)

    if d is None:
        d = max(
            3.0,
            math.sqrt(max(bitola, 0.1)) * 1.8
        )

    return math.pi * d * d / 4.0


def _area_circuito_rota(circuito):
    """
    Nesta arquitetura cada circuito terminal é representado por
    três condutores no eletroduto: ativos + PE.
    """
    return 3.0 * _area_condutor_rota(
        _bitola_rota_circuito(circuito)
    )


def _area_maxima_eletroduto_25():
    area_interna = (
        math.pi
        * DIAMETRO_INTERNO_ELETRODUTO_25_MM
        * DIAMETRO_INTERNO_ELETRODUTO_25_MM
        / 4.0
    )
    return area_interna * OCUPACAO_MAX_TERMINAL


def _ocupacao_circuitos_rota(circuitos_nums, circuitos_por_numero):
    area = 0.0

    for numero in set(circuitos_nums or []):
        circuito = circuitos_por_numero.get(int(numero))
        if not circuito:
            continue
        area += _area_circuito_rota(circuito)

    area_interna = (
        math.pi
        * DIAMETRO_INTERNO_ELETRODUTO_25_MM
        * DIAMETRO_INTERNO_ELETRODUTO_25_MM
        / 4.0
    )

    return (
        area / area_interna
        if area_interna > 0
        else 1.0
    )


def _graus_tronco(arestas):
    graus = {}

    for a in arestas:
        origem = a.get("origem_id")
        destino = a.get("destino_id")

        if origem and origem != "QDC":
            graus[origem] = graus.get(origem, 0) + 1

        if destino and destino != "QDC":
            graus[destino] = graus.get(destino, 0) + 1

    return graus


def _estrutura_arvore_tronco(arestas):
    por_destino = {
        a.get("destino_id"): a
        for a in arestas
        if a.get("destino_id")
    }

    filhos = {}

    for a in arestas:
        origem = a.get("origem_id")
        destino = a.get("destino_id")

        if (
            origem
            and destino
            and origem != "QDC"
        ):
            filhos.setdefault(
                origem,
                []
            ).append(
                destino
            )
        elif origem == "QDC" and destino:
            filhos.setdefault(
                "QDC",
                []
            ).append(
                destino
            )

    return por_destino, filhos


def _subarvore_ids(raiz, filhos):
    vistos = set()
    pilha = [raiz]

    while pilha:
        atual = pilha.pop()

        if atual in vistos:
            continue

        vistos.add(atual)

        for filho in filhos.get(atual, []):
            if filho not in vistos:
                pilha.append(filho)

    return vistos


def _caminho_ate_qdc(no_id, por_destino):
    caminho = []
    atual = no_id
    seguranca = 0

    while atual and atual != "QDC" and seguranca < 200:
        aresta = por_destino.get(atual)

        if aresta is None:
            break

        caminho.append(aresta)
        atual = aresta.get("origem_id")
        seguranca += 1

    return caminho


def _selecionar_circuitos_para_desvio(
    aresta,
    subarvore,
    demandas_por_circuito,
    circuitos_por_numero
):
    """
    Só move um circuito se TODOS os nós de demanda desse circuito
    estiverem dentro da subárvore que nasce no trecho crítico.
    Assim não desconectamos cargas que ainda dependam do caminho antigo.
    """
    atuais = set(
        int(n)
        for n in (
            aresta.get("circuitos", set())
            or set()
        )
        if int(n) > 0
    )

    area_max = _area_maxima_eletroduto_25()

    area_atual = sum(
        _area_circuito_rota(
            circuitos_por_numero[n]
        )
        for n in atuais
        if n in circuitos_por_numero
    )

    excesso = max(
        0.0,
        area_atual - area_max
    )

    moveis = []

    for numero in atuais:
        demandas = demandas_por_circuito.get(
            numero,
            set()
        )

        if (
            demandas
            and demandas.issubset(
                subarvore
            )
            and numero in circuitos_por_numero
        ):
            moveis.append(
                (
                    numero,
                    _area_circuito_rota(
                        circuitos_por_numero[numero]
                    )
                )
            )

    moveis.sort(
        key=lambda item:
            item[1],
        reverse=True
    )

    escolhidos = []
    removida = 0.0

    for numero, area in moveis:
        escolhidos.append(numero)
        removida += area

        if removida + 1e-9 >= excesso:
            break

    if removida + 1e-9 < excesso:
        return []

    return escolhidos



def _alinhamento_direcional(qdc, candidato, destino):
    """
    Retorna o cosseno entre QDC->candidato e QDC->destino.
    +1 = mesma direção; 0 = perpendicular; -1 = direção oposta.
    """
    ax = float(candidato[0]) - float(qdc[0])
    ay = float(candidato[1]) - float(qdc[1])
    bx = float(destino[0]) - float(qdc[0])
    by = float(destino[1]) - float(qdc[1])

    na = math.hypot(ax, ay)
    nb = math.hypot(bx, by)

    if na < 1e-9 or nb < 1e-9:
        return 1.0

    return (
        ax * bx + ay * by
    ) / (na * nb)


def _avaliar_caminho_alternativo(
    qdc,
    candidato,
    destino,
    distancia_raiz_candidato
):
    """
    Fase 13.3 Rev.2.

    Compara o percurso total desde o QDC até o destino, e não apenas
    a ligação local candidato->destino.

    Caminhos que saem para o hemisfério oposto ao destino recebem
    uma penalização de custo, evitando situações como QDC -> VARANDA
    -> WC quando existe uma alternativa mais curta na direção do WC.
    """
    direto = _dist(
        qdc,
        destino
    )

    total = (
        float(
            distancia_raiz_candidato
            or 0.0
        )
        + _dist(
            candidato,
            destino
        )
    )

    alinhamento = _alinhamento_direcional(
        qdc,
        candidato,
        destino
    )

    # Não proíbe desvios geométricos: apenas os torna menos atraentes.
    # Quanto mais o candidato estiver "atrás" do QDC em relação ao destino,
    # maior a penalização.
    penalidade_direcao = (
        1.0
        if alinhamento >= 0.0
        else (
            1.0
            + min(
                0.75,
                abs(alinhamento) * 0.75
            )
        )
    )

    custo = total * penalidade_direcao

    desvio_pct = (
        (
            total / direto
            - 1.0
        )
        * 100.0
        if direto > 1e-9
        else 0.0
    )

    return {
        "percurso_total_m":
            float(total),
        "percurso_direto_m":
            float(direto),
        "desvio_vs_direto_pct":
            float(desvio_pct),
        "alinhamento_direcional":
            float(alinhamento),
        "penalidade_direcao":
            float(penalidade_direcao),
        "custo_selecao":
            float(custo),
    }


def _redistribuir_tronco_caixas_octogonais(
    qdc,
    nos,
    arestas,
    circuitos,
    max_iteracoes=12
):
    """
    Fecha o ciclo da Fase 13.3 Rev.2:

    1. calcula a ocupação projetada em Ø25 de cada trecho troncal;
    2. se ultrapassar 40%, procura outra caixa octogonal disponível;
    3. move um conjunto completo de circuitos da subárvore crítica;
    4. cria um caminho físico alternativo via outra caixa;
    5. recalcula e repete.

    A caixa alternativa precisa ter entrada disponível (máx. 8 conexões).
    A rota alternativa também precisa caber em Ø25 nos trechos já existentes.

    Se nenhuma caixa puder receber o desvio, cria uma nova saída direta
    do QDC como fallback técnico, mantendo Ø25 nos circuitos terminais.
    """
    if not arestas:
        return arestas

    circuitos_por_numero = {
        int(c.get("numero", 0) or 0): c
        for c in (circuitos or [])
        if int(c.get("numero", 0) or 0) > 0
    }

    nos_por_id = {
        n.get("id"): n
        for n in (nos or [])
        if n.get("id")
    }

    demandas_por_circuito = {}

    for no in (nos or []):
        no_id = no.get("id")

        for numero in (
            no.get("circuitos", set())
            or set()
        ):
            numero = int(numero)

            if numero <= 0:
                continue

            demandas_por_circuito.setdefault(
                numero,
                set()
            ).add(
                no_id
            )

    # Guardamos a árvore original. As novas ligações são bypasses e não
    # substituem o parent estrutural dos nós.
    por_destino, filhos = _estrutura_arvore_tronco(
        arestas
    )

    for _ in range(max_iteracoes):
        criticas = []

        for a in arestas:
            if a.get("criterio") == "REDISTRIBUICAO_CAIXA_OCTOGONAL":
                continue

            ocup = _ocupacao_circuitos_rota(
                a.get("circuitos", set()),
                circuitos_por_numero
            )

            if ocup > OCUPACAO_MAX_TERMINAL + 1e-9:
                criticas.append(
                    (
                        ocup,
                        a
                    )
                )

        if not criticas:
            break

        # Ataca primeiro o trecho mais carregado.
        criticas.sort(
            key=lambda item:
                item[0],
            reverse=True
        )

        alterou = False

        for _, aresta_critica in criticas:
            destino_id = aresta_critica.get(
                "destino_id"
            )

            if not destino_id:
                continue

            subarvore = _subarvore_ids(
                destino_id,
                filhos
            )

            escolhidos = _selecionar_circuitos_para_desvio(
                aresta_critica,
                subarvore,
                demandas_por_circuito,
                circuitos_por_numero
            )

            if not escolhidos:
                continue

            graus = _graus_tronco(
                arestas
            )

            destino_no = nos_por_id.get(
                destino_id
            )

            if not destino_no:
                continue

            destino_pt = tuple(
                destino_no.get(
                    "ponto"
                )
            )

            if graus.get(destino_id, 0) >= MAX_ENTRADAS_CAIXA_OCTOGONAL:
                continue

            candidatos = []

            for no in (nos or []):
                cand_id = no.get("id")

                if (
                    not cand_id
                    or cand_id == destino_id
                    or cand_id in subarvore
                ):
                    continue

                if graus.get(cand_id, 0) >= MAX_ENTRADAS_CAIXA_OCTOGONAL:
                    continue

                caminho_cand = _caminho_ate_qdc(
                    cand_id,
                    por_destino
                )

                cabe = True

                for a_path in caminho_cand:
                    projetados = set(
                        a_path.get(
                            "circuitos",
                            set()
                        )
                        or set()
                    )
                    projetados.update(
                        escolhidos
                    )

                    if (
                        _ocupacao_circuitos_rota(
                            projetados,
                            circuitos_por_numero
                        )
                        > OCUPACAO_MAX_TERMINAL
                        + 1e-9
                    ):
                        cabe = False
                        break

                if not cabe:
                    continue

                ocup_bypass = _ocupacao_circuitos_rota(
                    escolhidos,
                    circuitos_por_numero
                )

                if ocup_bypass > OCUPACAO_MAX_TERMINAL + 1e-9:
                    continue

                ponto_cand = tuple(
                    no.get("ponto")
                )

                dist_raiz = 0.0

                if caminho_cand:
                    # A aresta que chega ao candidato contém a distância
                    # acumulada desde o QDC.
                    dist_raiz = float(
                        caminho_cand[0].get(
                            "dist_raiz",
                            0.0
                        )
                        or 0.0
                    )
                else:
                    dist_raiz = _dist(
                        qdc,
                        ponto_cand
                    )

                avaliacao = _avaliar_caminho_alternativo(
                    qdc,
                    ponto_cand,
                    destino_pt,
                    dist_raiz
                )

                candidatos.append(
                    (
                        avaliacao[
                            "custo_selecao"
                        ],
                        no,
                        caminho_cand,
                        avaliacao
                    )
                )

            # Remove os circuitos escolhidos do caminho antigo até o QDC.
            caminho_antigo = _caminho_ate_qdc(
                destino_id,
                por_destino
            )

            # A saída direta do QDC participa da comparação SEMPRE.
            # Assim uma caixa alternativa só é usada se o percurso total
            # realmente for melhor que QDC -> destino.
            direto_m = _dist(
                qdc,
                destino_pt
            )

            melhor_caixa = None

            if candidatos:
                candidatos.sort(
                    key=lambda item:
                        item[0]
                )
                melhor_caixa = candidatos[0]

            # Reusar uma caixa pode economizar infraestrutura, então aceitamos
            # um pequeno desvio de percurso. Porém o caminho alternativo não pode
            # ficar muito maior que uma nova saída direta do QDC.
            FATOR_MAX_DESVIO_REROTA = 1.20

            usar_caixa = (
                melhor_caixa is not None
                and float(
                    melhor_caixa[3].get(
                        "custo_selecao",
                        1e99
                    )
                )
                <= direto_m
                * FATOR_MAX_DESVIO_REROTA
            )

            if usar_caixa:
                (
                    _,
                    caixa_alt,
                    caminho_alt,
                    avaliacao_alt
                ) = melhor_caixa

                for a_old in caminho_antigo:
                    for numero in escolhidos:
                        a_old.setdefault(
                            "circuitos",
                            set()
                        ).discard(
                            numero
                        )

                for a_alt in caminho_alt:
                    a_alt.setdefault(
                        "circuitos",
                        set()
                    ).update(
                        escolhidos
                    )

                ponto_alt = tuple(
                    caixa_alt.get(
                        "ponto"
                    )
                )

                arestas.append({
                    "origem_id":
                        caixa_alt.get(
                            "id"
                        ),
                    "destino_id":
                        destino_id,
                    "origem_ambiente":
                        caixa_alt.get(
                            "ambiente",
                            ""
                        ),
                    "destino_ambiente":
                        destino_no.get(
                            "ambiente",
                            ""
                        ),
                    "inicio":
                        ponto_alt,
                    "fim":
                        destino_pt,
                    "circuitos":
                        set(
                            escolhidos
                        ),
                    "criterio":
                        "REDISTRIBUICAO_CAIXA_OCTOGONAL",
                    "limite_entradas_caixa":
                        MAX_ENTRADAS_CAIXA_OCTOGONAL,
                    "dist_raiz":
                        avaliacao_alt[
                            "percurso_total_m"
                        ],
                    "dist_direta":
                        avaliacao_alt[
                            "percurso_direto_m"
                        ],
                    "desvio_vs_direto_pct":
                        round(
                            avaliacao_alt[
                                "desvio_vs_direto_pct"
                            ],
                            1
                        ),
                    "alinhamento_direcional":
                        round(
                            avaliacao_alt[
                                "alinhamento_direcional"
                            ],
                            3
                        ),
                    "criterio_selecao_rerota":
                        "MENOR_CUSTO_TOTAL_DESDE_QDC",
                })

                alterou = True
                break

            # Se nenhuma caixa é melhor que a saída direta, usa o QDC.
            ocup_bypass = _ocupacao_circuitos_rota(
                escolhidos,
                circuitos_por_numero
            )

            if ocup_bypass <= OCUPACAO_MAX_TERMINAL + 1e-9:
                for a_old in caminho_antigo:
                    for numero in escolhidos:
                        a_old.setdefault(
                            "circuitos",
                            set()
                        ).discard(
                            numero
                        )

                arestas.append({
                    "origem_id":
                        "QDC",
                    "destino_id":
                        destino_id,
                    "origem_ambiente":
                        "QDC",
                    "destino_ambiente":
                        destino_no.get(
                            "ambiente",
                            ""
                        ),
                    "inicio":
                        tuple(qdc),
                    "fim":
                        destino_pt,
                    "circuitos":
                        set(
                            escolhidos
                        ),
                    "criterio":
                        "REDISTRIBUICAO_NOVA_SAIDA_QDC",
                    "limite_entradas_caixa":
                        MAX_ENTRADAS_CAIXA_OCTOGONAL,
                    "dist_raiz":
                        _dist(
                            qdc,
                            destino_pt
                        ),
                    "dist_direta":
                        _dist(
                            qdc,
                            destino_pt
                        ),
                    "desvio_vs_direto_pct":
                        0.0,
                    "alinhamento_direcional":
                        1.0,
                    "criterio_selecao_rerota":
                        "MENOR_CUSTO_TOTAL_DESDE_QDC",
                })

                alterou = True
                break

        if not alterou:
            break

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




def _normal_externa_segmento(p1, p2, centro):
    """Normal unitária do segmento apontando para fora do ambiente."""
    x1, y1 = map(float, p1)
    x2, y2 = map(float, p2)
    cx, cy = map(float, centro)
    dx, dy = x2-x1, y2-y1
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return (0.0, 0.0)
    n1 = (-dy/L, dx/L)
    mx, my = (x1+x2)/2.0, (y1+y2)/2.0
    # A normal externa é a que aumenta a distância ao centro do ambiente.
    a = (mx+n1[0]*0.10-cx)**2 + (my+n1[1]*0.10-cy)**2
    b = (mx-n1[0]*0.10-cx)**2 + (my-n1[1]*0.10-cy)**2
    return n1 if a >= b else (-n1[0], -n1[1])


def _intersecao_retas(a1, a2, b1, b2):
    x1,y1=map(float,a1); x2,y2=map(float,a2)
    x3,y3=map(float,b1); x4,y4=map(float,b2)
    den=(x1-x2)*(y3-y4)-(y1-y2)*(x3-x4)
    if abs(den)<1e-10:
        return None
    px=((x1*y2-y1*x2)*(x3-x4)-(x1-x2)*(x3*y4-y3*x4))/den
    py=((x1*y2-y1*x2)*(y3-y4)-(y1-y2)*(x3*y4-y3*x4))/den
    return (px,py)


def _segmentos_eixo_parede(segmentos_crus, centro, afastamento=0.05):
    """Cria linhas paralelas ao perímetro no meio físico da parede."""
    out=[]
    for a,b,L in segmentos_crus or []:
        nx,ny=_normal_externa_segmento(a,b,centro)
        aa=(float(a[0])+nx*afastamento,float(a[1])+ny*afastamento)
        bb=(float(b[0])+nx*afastamento,float(b[1])+ny*afastamento)
        out.append((aa,bb,float(L)))
    return out



def _orientacao(a, b, c):
    return (
        (float(b[0]) - float(a[0]))
        * (float(c[1]) - float(a[1]))
        -
        (float(b[1]) - float(a[1]))
        * (float(c[0]) - float(a[0]))
    )


def _segmentos_intersectam(a, b, c, d, tol=1e-8):
    o1 = _orientacao(a, b, c)
    o2 = _orientacao(a, b, d)
    o3 = _orientacao(c, d, a)
    o4 = _orientacao(c, d, b)

    if (
        ((o1 > tol and o2 < -tol) or (o1 < -tol and o2 > tol))
        and
        ((o3 > tol and o4 < -tol) or (o3 < -tol and o4 > tol))
    ):
        return True

    return False


def _dist_ponto_segmento(p, a, b):
    px, py = map(float, p)
    ax, ay = map(float, a)
    bx, by = map(float, b)
    dx = bx - ax
    dy = by - ay
    l2 = dx * dx + dy * dy

    if l2 <= 1e-12:
        return math.hypot(px - ax, py - ay)

    t = (
        (px - ax) * dx
        + (py - ay) * dy
    ) / l2

    t = max(0.0, min(1.0, t))
    qx = ax + t * dx
    qy = ay + t * dy
    return math.hypot(px - qx, py - qy)


def _segmentos_obstaculo(item):
    """
    Converte porta/soleira em segmentos geométricos utilizáveis.
    """
    verts = item.get("vertices") or []

    if len(verts) >= 2:
        pontos = [
            (float(p[0]), float(p[1]))
            for p in verts
        ]
        return [
            (
                pontos[i],
                pontos[(i + 1) % len(pontos)]
            )
            for i in range(len(pontos))
        ]

    if (
        item.get("p1") is not None
        and item.get("p2") is not None
    ):
        return [
            (
                tuple(item["p1"]),
                tuple(item["p2"])
            )
        ]

    return []


def _rota_encontra_porta_ou_soleira(
    pontos_rota,
    portas_raw,
    soleiras_raw,
    tolerancia=0.10
):
    """
    Retorna True quando o caminho embutido na parede cruza ou passa
    muito próximo de uma porta/soleira.

    A tolerância cobre a diferença entre a face interna e o eixo da parede.
    """
    if len(pontos_rota) < 2:
        return False

    obstaculos = []

    for item in (portas_raw or []):
        obstaculos.extend(
            _segmentos_obstaculo(item)
        )

    for item in (soleiras_raw or []):
        obstaculos.extend(
            _segmentos_obstaculo(item)
        )

    for a, b in zip(
        pontos_rota[:-1],
        pontos_rota[1:]
    ):
        for c, d in obstaculos:
            if _segmentos_intersectam(
                a, b, c, d
            ):
                return True

            # Aproximação suficiente para detectar o vão mesmo quando
            # a linha do conduíte corre no eixo da espessura da parede.
            if min(
                _dist_ponto_segmento(c, a, b),
                _dist_ponto_segmento(d, a, b),
                _dist_ponto_segmento(a, c, d),
                _dist_ponto_segmento(b, c, d),
            ) <= tolerancia:
                return True

    return False


def _pontos_linha_parede_entre_tugs(
    tug_origem,
    tug_destino,
    segmentos_crus=None,
    comp_total=0.0,
    centro_ambiente=None
):
    """
    Calcula os pontos do conduíte TUG -> TUG sem desenhar.
    """
    p1 = (
        tug_origem.get("ponto_conexao_parede")
        or tug_origem.get("ponto")
    )
    p2 = (
        tug_destino.get("ponto_conexao_parede")
        or tug_destino.get("ponto")
    )

    if not p1 or not p2:
        return []

    segs = segmentos_crus or []

    if (
        not segs
        or comp_total <= 0
        or not centro_ambiente
    ):
        return [
            tuple(p1),
            tuple(p2)
        ]

    afast = max(
        0.01,
        min(
            0.25,
            _dist(
                tug_origem.get("ponto"),
                p1
            )
        )
    )

    eixos = _segmentos_eixo_parede(
        segs,
        centro_ambiente,
        afast
    )

    d1 = float(
        tug_origem.get(
            "distancia_perimetro",
            0.0
        )
        or 0.0
    ) % comp_total

    d2 = float(
        tug_destino.get(
            "distancia_perimetro",
            0.0
        )
        or 0.0
    ) % comp_total

    def localizar(d):
        acc = 0.0
        for i, (_, _, L) in enumerate(segs):
            if d <= acc + float(L) + 1e-9:
                return i
            acc += float(L)
        return len(segs) - 1

    i1 = localizar(d1)
    i2 = localizar(d2)

    if i1 == i2:
        pts = [
            tuple(p1),
            tuple(p2)
        ]
    else:
        dm = (d2 - d1) % comp_total
        dn = (d1 - d2) % comp_total
        sentido = 1 if dm <= dn else -1

        pts = [tuple(p1)]
        i = i1
        guard = 0

        while (
            i != i2
            and guard <= len(segs)
        ):
            j = (
                i + sentido
            ) % len(segs)

            inter = _intersecao_retas(
                eixos[i][0],
                eixos[i][1],
                eixos[j][0],
                eixos[j][1]
            )

            if inter is None:
                inter = (
                    eixos[i][1]
                    if sentido > 0
                    else eixos[i][0]
                )

            pts.append(
                tuple(inter)
            )

            i = j
            guard += 1

        pts.append(
            tuple(p2)
        )

    limpos = []

    for pt in pts:
        if (
            not limpos
            or _dist(
                limpos[-1],
                pt
            ) > 1e-7
        ):
            limpos.append(pt)

    return limpos


def _linha_parede_entre_tugs(
    msp,
    tug_origem,
    tug_destino,
    segmentos_crus=None,
    comp_total=0.0,
    centro_ambiente=None,
    layer=LAYER_ROTA
):
    """
    Fase 13.3 Rev.2:
    desenha TUG -> TUG pelo eixo da parede.
    """
    pontos = _pontos_linha_parede_entre_tugs(
        tug_origem,
        tug_destino,
        segmentos_crus=segmentos_crus,
        comp_total=comp_total,
        centro_ambiente=centro_ambiente
    )

    if len(pontos) < 2:
        return None

    return msp.add_lwpolyline(
        pontos,
        dxfattribs={
            "layer": layer
        }
    )


def _arestas_tugs_internas(
    nos,
    pontos_eletricos,
    pontos_interruptores,
    circuitos
):
    """
    Fase 13.3 Rev.2

    - todo interruptor do ambiente recebe ligação;
    - interruptores paralelos não podem ficar soltos;
    - mesmo ambientes sem TUG mantêm luminária -> interruptor;
    - para iniciar a cadeia de TUGs, usa o interruptor mais próximo da TUG 1.
    """
    principal_por_ambiente = {
        n["ambiente"]: tuple(
            n["ponto"]
        )
        for n in nos
    }

    luminarias_por_ambiente = {
        n["ambiente"]: [
            tuple(pt)
            for pt in n.get(
                "luminarias",
                []
            )
        ]
        for n in nos
    }

    tug_por_ambiente = {}

    for p in pontos_eletricos or []:
        if str(
            p.get(
                "tipo",
                ""
            )
        ).upper() != "TUG":
            continue

        amb = _normalizar_nome(
            p.get(
                "ambiente"
            )
        )

        if (
            not amb
            or not p.get(
                "ponto"
            )
        ):
            continue

        tug_por_ambiente.setdefault(
            amb,
            []
        ).append(
            p
        )

    for amb in tug_por_ambiente:
        tug_por_ambiente[
            amb
        ].sort(
            key=lambda p: (
                int(
                    p.get(
                        "ordem_perimetro",
                        9999
                    )
                    or 9999
                ),
                float(
                    p.get(
                        "distancia_perimetro",
                        0.0
                    )
                    or 0.0
                )
            )
        )

    ints_por_ambiente = {}

    for p in pontos_interruptores or []:
        amb = _normalizar_nome(
            p.get(
                "ambiente"
            )
        )

        pt = (
            p.get(
                "ponto_tangencia"
            )
            or p.get(
                "ponto"
            )
        )

        if amb and pt:
            ints_por_ambiente.setdefault(
                amb,
                []
            ).append(
                tuple(pt)
            )

    tug_circuitos = {}
    iluminacao_circuitos = {}

    for c in circuitos or []:
        tipo_c = str(
            c.get(
                "tipo",
                ""
            )
        ).upper()

        if tipo_c == "ILUMINAÇÃO".upper():
            numero = int(
                c.get(
                    "numero",
                    0
                )
                or 0
            )

            for amb in _ambientes_circuito(
                c
            ):
                iluminacao_circuitos.setdefault(
                    _normalizar_nome(
                        amb
                    ),
                    set()
                ).add(
                    numero
                )

        if tipo_c != "TUG":
            continue

        numero = int(
            c.get(
                "numero",
                0
            )
            or 0
        )

        for amb in _ambientes_circuito(
            c
        ):
            tug_circuitos.setdefault(
                _normalizar_nome(
                    amb
                ),
                set()
            ).add(
                numero
            )

    arestas = []

    # Primeiro conecta TODOS os interruptores existentes.
    for ambiente, interruptores in ints_por_ambiente.items():
        luzes = luminarias_por_ambiente.get(
            ambiente,
            []
        )

        principal = principal_por_ambiente.get(
            ambiente
        )

        if not luzes and principal:
            luzes = [principal]

        if not luzes:
            continue

        circuitos_amb = (
            set(
                tug_circuitos.get(
                    ambiente,
                    set()
                )
            )
            |
            set(
                iluminacao_circuitos.get(
                    ambiente,
                    set()
                )
            )
        )

        for indice_int, interruptor in enumerate(
            interruptores,
            start=1
        ):
            origem_luz = min(
                luzes,
                key=lambda pt:
                    _dist(
                        pt,
                        interruptor
                    )
            )

            arestas.append({
                "origem_ambiente":
                    ambiente,
                "destino_ambiente":
                    ambiente,
                "inicio":
                    origem_luz,
                "fim":
                    interruptor,
                "circuitos":
                    circuitos_amb,
                "criterio":
                    (
                        "LUZ_PARA_INTERRUPTOR"
                        if len(interruptores) == 1
                        else "LUZ_PARA_INTERRUPTOR_PARALELO"
                    ),
                "indice_interruptor":
                    indice_int,
            })

    # Depois cria a cadeia das TUGs.
    for ambiente, tugs in tug_por_ambiente.items():
        if not tugs:
            continue

        principal = principal_por_ambiente.get(
            ambiente
        )

        if principal is None:
            continue

        interruptores = ints_por_ambiente.get(
            ambiente,
            []
        )

        circuitos_amb = (
            set(
                tug_circuitos.get(
                    ambiente,
                    set()
                )
            )
            |
            set(
                iluminacao_circuitos.get(
                    ambiente,
                    set()
                )
            )
        )

        primeira_tug = (
            tugs[0].get(
                "ponto_conexao_parede"
            )
            or tugs[0].get(
                "ponto"
            )
        )

        if interruptores:
            interruptor_inicio = min(
                interruptores,
                key=lambda pt:
                    _dist(
                        pt,
                        primeira_tug
                    )
            )
            atual = interruptor_inicio
        else:
            interruptor_inicio = None
            atual = principal

        for indice, tug in enumerate(
            tugs,
            start=1
        ):
            destino = tuple(
                tug.get(
                    "ponto_conexao_parede"
                )
                or tug["ponto"]
            )

            aresta = {
                "origem_ambiente":
                    ambiente,
                "destino_ambiente":
                    ambiente,
                "inicio":
                    atual,
                "fim":
                    destino,
                "circuitos":
                    circuitos_amb,
                "criterio":
                    (
                        "INTERRUPTOR_PARA_TUG1"
                        if indice == 1
                        and interruptor_inicio is not None
                        else (
                            "LUZ_PARA_TUG1"
                            if indice == 1
                            else "CADEIA_TUG"
                        )
                    ),
                "tug_destino":
                    tug,
            }

            if indice > 1:
                aresta[
                    "tug_origem"
                ] = tugs[
                    indice - 2
                ]

            arestas.append(
                aresta
            )

            atual = destino

    return arestas


def _ambiente_sem_interruptor_proprio_rota(
    nome
):
    n = _normalizar_nome(
        nome
    )

    return any(
        termo in n
        for termo in [
            "VARANDA",
            "TERRACO",
            "TERRAÇO",
            "GARAGEM",
        ]
    )


def _ponto_segmento_dist_rota(
    p,
    a,
    b
):
    px, py = map(float, p)
    ax, ay = map(float, a)
    bx, by = map(float, b)

    dx = bx - ax
    dy = by - ay
    l2 = dx*dx + dy*dy

    if l2 <= 1e-12:
        return math.hypot(
            px-ax,
            py-ay
        )

    t = (
        (px-ax)*dx
        + (py-ay)*dy
    ) / l2

    t = max(
        0.0,
        min(
            1.0,
            t
        )
    )

    qx = ax + t*dx
    qy = ay + t*dy

    return math.hypot(
        px-qx,
        py-qy
    )


def _centro_soleira_rota(
    soleira
):
    verts = soleira.get(
        "vertices"
    ) or []

    if verts:
        xs = [
            float(p[0])
            for p in verts
        ]
        ys = [
            float(p[1])
            for p in verts
        ]

        return (
            sum(xs)/len(xs),
            sum(ys)/len(ys)
        )

    p1 = soleira.get(
        "p1"
    )
    p2 = soleira.get(
        "p2"
    )

    if p1 is not None and p2 is not None:
        return (
            (
                float(p1[0])
                + float(p2[0])
            ) / 2.0,
            (
                float(p1[1])
                + float(p2[1])
            ) / 2.0,
        )

    return None


def _distancia_ponto_poligono_rota(
    ponto,
    polilinha
):
    if not ponto or not polilinha:
        return float("inf")

    poly = [
        tuple(p)
        for p in polilinha
    ]

    if (
        len(poly) >= 2
        and poly[0] != poly[-1]
    ):
        poly.append(
            poly[0]
        )

    melhor = float("inf")

    for a, b in zip(
        poly[:-1],
        poly[1:]
    ):
        melhor = min(
            melhor,
            _ponto_segmento_dist_rota(
                ponto,
                a,
                b
            )
        )

    return melhor


def _soleira_compartilhada_controladora(
    ambiente_externo,
    ambientes_geom,
    soleiras_raw
):
    """
    Localiza a soleira/porta que realmente separa o ambiente externo
    de um ambiente interno.

    Retorna:
      (soleira, ambiente_controlador)
    """
    externos = {
        _normalizar_nome(
            ambiente_externo
        )
    }

    geo_ext = None

    for item in (
        ambientes_geom
        or []
    ):
        nome = _normalizar_nome(
            item.get(
                "nome"
            )
            or item.get(
                "ambiente"
            )
        )

        if nome in externos:
            geo_ext = item
            break

    if geo_ext is None:
        return (
            None,
            None
        )

    poly_ext = geo_ext.get(
        "polilinha",
        []
    )

    candidatos = []

    for soleira in (
        soleiras_raw
        or []
    ):
        centro = _centro_soleira_rota(
            soleira
        )

        if centro is None:
            continue

        d_ext = _distancia_ponto_poligono_rota(
            centro,
            poly_ext
        )

        # Soleira precisa efetivamente tocar o ambiente externo.
        if d_ext > 0.35:
            continue

        for item in (
            ambientes_geom
            or []
        ):
            nome = _normalizar_nome(
                item.get(
                    "nome"
                )
                or item.get(
                    "ambiente"
                )
            )

            if (
                not nome
                or nome == ambiente_externo
                or _ambiente_sem_interruptor_proprio_rota(
                    nome
                )
            ):
                continue

            d_int = _distancia_ponto_poligono_rota(
                centro,
                item.get(
                    "polilinha",
                    []
                )
            )

            if d_int <= 0.35:
                candidatos.append((
                    d_ext + d_int,
                    soleira,
                    nome,
                    centro,
                ))

    if not candidatos:
        return (
            None,
            None
        )

    _, soleira, controlador, _ = min(
        candidatos,
        key=lambda x:
            x[0]
    )

    return (
        soleira,
        controlador
    )


def _arestas_iluminacao_ambiente_controlado(
    pontos_eletricos,
    pontos_interruptores,
    ambientes_geom,
    soleiras_raw,
    circuitos=None
):
    """
    Fase 13.3 Rev.2.

    Varanda/terraço/garagem:
    - identifica qual soleira/porta é realmente compartilhada com o
      ambiente interno controlador;
    - liga a iluminação externa ao INTERRUPTOR desse ambiente;
    - se houver mais de um interruptor no controlador, escolhe o mais
      próximo da soleira compartilhada;
    - só usa fallback geométrico para luminária interna se não for
      possível identificar interruptor válido.
    """
    luminarias = _luminarias_por_ambiente(
        pontos_eletricos
    )

    circuitos_ilum = (
        _circuitos_iluminacao_por_ambiente(
            circuitos
        )
    )

    ints_por_ambiente = {}

    for p in (
        pontos_interruptores
        or []
    ):
        amb = _normalizar_nome(
            p.get(
                "ambiente"
            )
        )

        pt = (
            p.get(
                "ponto_tangencia"
            )
            or p.get(
                "ponto"
            )
        )

        if amb and pt:
            ints_por_ambiente.setdefault(
                amb,
                []
            ).append(
                tuple(pt)
            )

    saida = []

    for ambiente, luzes in luminarias.items():
        if not _ambiente_sem_interruptor_proprio_rota(
            ambiente
        ):
            continue

        soleira, controlador = (
            _soleira_compartilhada_controladora(
                ambiente,
                ambientes_geom,
                soleiras_raw
            )
        )

        origem = None
        criterio = None

        if (
            soleira is not None
            and controlador
        ):
            centro_soleira = (
                _centro_soleira_rota(
                    soleira
                )
            )

            candidatos_int = (
                ints_por_ambiente.get(
                    controlador,
                    []
                )
            )

            if candidatos_int:
                origem = min(
                    candidatos_int,
                    key=lambda pt:
                        _dist(
                            pt,
                            centro_soleira
                        )
                )

                criterio = (
                    "INTERRUPTOR_CONTROLADOR_PARA_ILUMINACAO_EXTERNA"
                )

        # Fallback somente se não existir interruptor controlador válido.
        if origem is None:
            candidatos = []

            for outro_ambiente, outras_luzes in luminarias.items():
                if (
                    outro_ambiente == ambiente
                    or _ambiente_sem_interruptor_proprio_rota(
                        outro_ambiente
                    )
                ):
                    continue

                for luz_origem in outras_luzes:
                    for luz_destino in luzes:
                        candidatos.append((
                            _dist(
                                luz_origem,
                                luz_destino
                            ),
                            outro_ambiente,
                            tuple(luz_origem),
                            tuple(luz_destino),
                        ))

            if not candidatos:
                continue

            _, controlador, origem, _ = min(
                candidatos,
                key=lambda item:
                    item[0]
            )

            criterio = (
                "FALLBACK_ILUMINACAO_CONTROLADORA"
            )

        for luz_destino in luzes:
            saida.append({
                "origem_ambiente":
                    controlador
                    or "CONTROLADOR",
                "destino_ambiente":
                    ambiente,
                "inicio":
                    tuple(origem),
                "fim":
                    tuple(luz_destino),
                "circuitos":
                    set(
                        circuitos_ilum.get(
                            ambiente,
                            set()
                        )
                    ),
                "criterio":
                    criterio,
            })

    return saida


def _arestas_tues_dedicadas(
    pontos_eletricos,
    circuitos
):
    """
    Fase 13.3 Rev.2 — ramais dedicados das TUEs.

    Cada TUE parte da luminária mais próxima do mesmo ambiente.
    Não deriva de TUG e não entra na cadeia perimetral das tomadas gerais.
    """
    luminarias = _luminarias_por_ambiente(
        pontos_eletricos
    )

    tues_por_ambiente = {}

    for ponto in (pontos_eletricos or []):
        if str(
            ponto.get(
                "tipo",
                ""
            )
        ).upper() != "TUE":
            continue

        ambiente = _normalizar_nome(
            ponto.get(
                "ambiente"
            )
        )

        if (
            not ambiente
            or not ponto.get(
                "ponto"
            )
        ):
            continue

        tues_por_ambiente.setdefault(
            ambiente,
            []
        ).append(
            ponto
        )

    circuitos_tue = {}

    for circuito in (circuitos or []):
        if str(
            circuito.get(
                "tipo",
                ""
            )
        ).upper() != "TUE":
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

        for ambiente in _ambientes_circuito(
            circuito
        ):
            chave = _normalizar_nome(
                ambiente
            )

            circuitos_tue.setdefault(
                chave,
                []
            ).append(
                numero
            )

    for ambiente in circuitos_tue:
        circuitos_tue[
            ambiente
        ] = sorted(
            set(
                circuitos_tue[
                    ambiente
                ]
            )
        )

    arestas = []

    for ambiente, tues in tues_por_ambiente.items():
        luzes = luminarias.get(
            ambiente,
            []
        )

        if not luzes:
            # Sem ponto de iluminação não inventa origem elétrica.
            continue

        nums = circuitos_tue.get(
            ambiente,
            []
        )

        for indice, tue in enumerate(
            tues
        ):
            destino = (
                tue.get(
                    "ponto_conexao_parede"
                )
                or tue.get(
                    "ponto"
                )
            )

            origem = min(
                luzes,
                key=lambda pt:
                    _dist(
                        pt,
                        destino
                    )
            )

            if nums:
                # TUE é circuito dedicado. Em ambientes com mais de uma,
                # associa em ordem aos circuitos disponíveis.
                numero = nums[
                    min(
                        indice,
                        len(nums) - 1
                    )
                ]
                circuitos_trecho = {
                    numero
                }
            else:
                circuitos_trecho = set()

            arestas.append({
                "origem_ambiente":
                    ambiente,
                "destino_ambiente":
                    ambiente,
                "inicio":
                    tuple(origem),
                "fim":
                    tuple(destino),
                "circuitos":
                    circuitos_trecho,
                "criterio":
                    "LUMINARIA_PARA_TUE",
                "tue_destino":
                    tue,
            })

    return arestas


def desenhar_rotas_qdc_iluminacao(
    msp,
    qdc_info,
    pontos_eletricos,
    circuitos,
    pontos_interruptores=None,
    ambientes_geom=None,
    portas_raw=None,
    soleiras_raw=None,
):
    """
    Fase 13.3 Rev.2

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

    tronco = (
        _redistribuir_tronco_caixas_octogonais(
            qdc,
            nos,
            tronco,
            circuitos
        )
    )

    secundarias = (
        _arestas_luminarias_secundarias(
            nos,
            circuitos_luz
        )
    )

    tugs_internas = (
        _arestas_tugs_internas(
            nos,
            pontos_eletricos,
            pontos_interruptores,
            circuitos
        )
    )

    tues_dedicadas = (
        _arestas_tues_dedicadas(
            pontos_eletricos,
            circuitos
        )
    )

    iluminacao_controlada = (
        _arestas_iluminacao_ambiente_controlado(
            pontos_eletricos,
            pontos_interruptores,
            ambientes_geom,
            soleiras_raw,
            circuitos
        )
    )

    geometria_ambiente = {}
    for item in (ambientes_geom or []):
        chave = _normalizar_nome(
            item.get("nome")
            or item.get("ambiente")
        )
        if chave:
            geometria_ambiente[chave] = item

    luminarias_por_ambiente = (
        _luminarias_por_ambiente(
            pontos_eletricos
        )
    )

    rotas = []

    todas_arestas = (
        tronco
        + secundarias
        + tugs_internas
        + tues_dedicadas
        + iluminacao_controlada
    )

    for indice, trecho in enumerate(
        todas_arestas
    ):
        if (
            trecho.get(
                "criterio"
            )
            == "CADEIA_TUG"
            and trecho.get(
                "tug_origem"
            )
            and trecho.get(
                "tug_destino"
            )
        ):
            geo = geometria_ambiente.get(
                _normalizar_nome(trecho.get("destino_ambiente")),
                {}
            )
            pontos_parede = (
                _pontos_linha_parede_entre_tugs(
                    trecho["tug_origem"],
                    trecho["tug_destino"],
                    segmentos_crus=geo.get(
                        "segmentos_crus",
                        []
                    ),
                    comp_total=geo.get(
                        "comp_total",
                        0.0
                    ),
                    centro_ambiente=geo.get(
                        "centro"
                    )
                )
            )

            encontrou_vao = (
                _rota_encontra_porta_ou_soleira(
                    pontos_parede,
                    portas_raw,
                    soleiras_raw
                )
            )

            if encontrou_vao:
                ambiente_chave = (
                    _normalizar_nome(
                        trecho.get(
                            "destino_ambiente"
                        )
                    )
                )

                destino = (
                    trecho["tug_destino"].get(
                        "ponto_conexao_parede"
                    )
                    or trecho["tug_destino"].get(
                        "ponto"
                    )
                )

                candidatos_luz = (
                    luminarias_por_ambiente.get(
                        ambiente_chave,
                        []
                    )
                )

                if candidatos_luz:
                    origem_luz = min(
                        candidatos_luz,
                        key=lambda pt:
                            _dist(
                                pt,
                                destino
                            )
                    )
                else:
                    origem_luz = (
                        trecho["inicio"]
                    )

                entidade = _arco_suave(
                    msp,
                    origem_luz,
                    destino,
                    indice=indice,
                    layer=LAYER_ROTA
                )

                tipo_entidade = "ARC"
                trecho[
                    "criterio"
                ] = "REINICIO_TUG_APOS_VAO"
                trecho[
                    "inicio"
                ] = origem_luz
                trecho[
                    "fim"
                ] = destino
            else:
                entidade = _linha_parede_entre_tugs(
                    msp,
                    trecho["tug_origem"],
                    trecho["tug_destino"],
                    segmentos_crus=geo.get(
                        "segmentos_crus",
                        []
                    ),
                    comp_total=geo.get(
                        "comp_total",
                        0.0
                    ),
                    centro_ambiente=geo.get(
                        "centro"
                    ),
                    layer=LAYER_ROTA
                )
                tipo_entidade = "LWPOLYLINE"
        else:
            entidade = _arco_suave(
                msp,
                trecho["inicio"],
                trecho["fim"],
                indice=indice,
                layer=LAYER_ROTA
            )
            tipo_entidade = "ARC"

        if entidade is None:
            continue

        comprimento_m = (
            _comprimento_entidade_rota(
                entidade,
                tipo_entidade,
                trecho["inicio"],
                trecho["fim"]
            )
        )

        rotas.append({
            "comprimento_m":
                round(
                    comprimento_m,
                    4
                ),
            "tipo_rede":
                (
                    "LUMINARIA_INTERNA"
                    if trecho.get("criterio")
                    == "LUMINARIA_SECUNDARIA"
                    else (
                        "TUG_INTERNA"
                        if trecho.get("criterio")
                        in {
                            "LUZ_PARA_INTERRUPTOR",
                            "LUZ_PARA_INTERRUPTOR_PARALELO",
                            "INTERRUPTOR_PARA_TUG1",
                            "LUZ_PARA_TUG1",
                            "CADEIA_TUG",
                            "REINICIO_TUG_APOS_VAO",
                        }
                        else (
                            "TUE_DEDICADA"
                            if trecho.get("criterio")
                            == "LUMINARIA_PARA_TUE"
                            else (
                                "ILUMINACAO_CONTROLADA"
                                if trecho.get("criterio")
                                in {
                                    "ILUMINACAO_AMBIENTE_CONTROLADO",
                                    "INTERRUPTOR_CONTROLADOR_PARA_ILUMINACAO_EXTERNA",
                                    "FALLBACK_ILUMINACAO_CONTROLADORA",
                                }
                                else "TRONCAL_HIBRIDA"
                            )
                        )
                    )
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
                tipo_entidade,
        })

    return rotas
