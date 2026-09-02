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
    Fase 11.5 — rede híbrida.

    Para cada ambiente compara:
    1) caminho direto QDC -> ambiente;
    2) melhor caminho usando um nó já pertencente à rede.

    A conexão pela rede só é aceita se o percurso total desde o QDC
    não exceder FATOR_MAX_DESVIO_REDE vezes o caminho direto.

    Isso permite vários troncos saindo do QDC quando necessário,
    evitando a volta excessiva observada na Fase 11.5.
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
    Fase 11.5:
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
    Liga:
      luminária principal -> interruptor -> TUG 1 -> TUG 2 -> ...

    As TUGs já chegam ordenadas pelo perímetro na Fase 11.5.
    Para ambientes sem interruptor próprio, liga a luminária principal
    diretamente à primeira TUG.
    """
    principal_por_ambiente = {
        n["ambiente"]: tuple(
            n["ponto"]
        )
        for n in nos
    }

    tug_por_ambiente = {}
    for p in pontos_eletricos or []:
        if str(p.get("tipo", "")).upper() != "TUG":
            continue
        amb = _normalizar_nome(
            p.get("ambiente")
        )
        if not amb or not p.get("ponto"):
            continue
        tug_por_ambiente.setdefault(
            amb,
            []
        ).append(p)

    for amb in tug_por_ambiente:
        tug_por_ambiente[amb].sort(
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

    int_por_ambiente = {}
    for p in pontos_interruptores or []:
        amb = _normalizar_nome(
            p.get("ambiente")
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
            int_por_ambiente.setdefault(
                amb,
                tuple(pt)
            )

    tug_circuitos = {}
    for c in circuitos or []:
        if str(c.get("tipo", "")).upper() != "TUG":
            continue
        numero = int(
            c.get(
                "numero",
                0
            )
            or 0
        )
        for amb in _ambientes_circuito(c):
            tug_circuitos.setdefault(
                _normalizar_nome(amb),
                set()
            ).add(numero)

    arestas = []

    for ambiente, tugs in tug_por_ambiente.items():
        if not tugs:
            continue

        principal = (
            principal_por_ambiente.get(
                ambiente
            )
        )
        if principal is None:
            continue

        interruptor = (
            int_por_ambiente.get(
                ambiente
            )
        )

        circuitos_amb = set(
            tug_circuitos.get(
                ambiente,
                set()
            )
        )

        atual = principal

        if interruptor is not None:
            arestas.append({
                "origem_ambiente":
                    ambiente,
                "destino_ambiente":
                    ambiente,
                "inicio":
                    atual,
                "fim":
                    interruptor,
                "circuitos":
                    circuitos_amb,
                "criterio":
                    "LUZ_PARA_INTERRUPTOR",
            })
            atual = interruptor

        for indice, tug in enumerate(
            tugs,
            start=1
        ):
            destino = tuple(
                tug.get("ponto_conexao_parede")
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
                        and interruptor is not None
                        else "CADEIA_TUG"
                    ),
                "tug_destino":
                    tug,
            }

            if (
                indice > 1
                and tugs[
                    indice - 2
                ]
            ):
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



def _arestas_tues_dedicadas(
    pontos_eletricos,
    circuitos
):
    """
    Fase 11.5 — ramais dedicados das TUEs.

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
    Fase 11.5

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

        rotas.append({
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
                            "INTERRUPTOR_PARA_TUG1",
                            "CADEIA_TUG",
                            "REINICIO_TUG_APOS_VAO",
                        }
                        else (
                            "TUE_DEDICADA"
                            if trecho.get("criterio")
                            == "LUMINARIA_PARA_TUE"
                            else "TRONCAL_HIBRIDA"
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
