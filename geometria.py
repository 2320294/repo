import math


def ponto_em_poligono(x, y, polilinha):
    if not polilinha:
        return False

    n = len(polilinha)
    dentro = False
    p1x, p1y = polilinha[0]

    for i in range(n + 1):
        p2x, p2y = polilinha[i % n]

        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    xinters = None

                    if p1y != p2y:
                        xinters = (
                            (y - p1y)
                            * (p2x - p1x)
                            / (p2y - p1y)
                        ) + p1x

                    if (
                        p1x == p2x
                        or (
                            xinters is not None
                            and x <= xinters
                        )
                    ):
                        dentro = not dentro

        p1x, p1y = p2x, p2y

    return dentro


def point_seg_dist(px, py, pt1, pt2):
    l2 = (
        (pt1[0] - pt2[0]) ** 2
        +
        (pt1[1] - pt2[1]) ** 2
    )

    if l2 == 0:
        return math.hypot(
            px - pt1[0],
            py - pt1[1]
        )

    t = max(
        0,
        min(
            1,
            (
                (px - pt1[0]) * (pt2[0] - pt1[0])
                +
                (py - pt1[1]) * (pt2[1] - pt1[1])
            ) / l2
        )
    )

    proj_x = pt1[0] + t * (pt2[0] - pt1[0])
    proj_y = pt1[1] + t * (pt2[1] - pt1[1])

    return math.hypot(
        px - proj_x,
        py - proj_y
    )


def get_ponto_perimetro(d, segs):
    acumulado = 0

    for pt1, pt2, dst in segs:
        if (
            acumulado + dst >= d
            or math.isclose(
                acumulado + dst,
                d,
                abs_tol=1e-5
            )
        ):
            if dst == 0:
                return (
                    pt1[0],
                    pt1[1],
                    0,
                    0
                )

            ratio = (d - acumulado) / dst

            x = (
                pt1[0]
                + (pt2[0] - pt1[0]) * ratio
            )

            y = (
                pt1[1]
                + (pt2[1] - pt1[1]) * ratio
            )

            vx = (pt2[0] - pt1[0]) / dst
            vy = (pt2[1] - pt1[1]) / dst

            return x, y, vx, vy

        acumulado += dst

    pt1, pt2, dst = segs[-1]

    if dst == 0:
        return pt2[0], pt2[1], 0, 0

    return (
        pt2[0],
        pt2[1],
        (pt2[0] - pt1[0]) / dst,
        (pt2[1] - pt1[1]) / dst
    )


def get_inside_normal(
    vx,
    vy,
    start_x,
    start_y,
    cx,
    cy
):
    n1x, n1y = -vy, vx
    n2x, n2y = vy, -vx

    d1 = math.hypot(
        cx - (start_x + n1x),
        cy - (start_y + n1y)
    )

    d2 = math.hypot(
        cx - (start_x + n2x),
        cy - (start_y + n2y)
    )

    return (
        (n1x, n1y)
        if d1 < d2
        else (n2x, n2y)
    )


def get_inside_normal_polygon(vx, vy, start_x, start_y, polilinha, probe=0.05, cx=None, cy=None):
    """
    Fase 8.16: retorna a normal que aponta realmente para dentro do polígono.
    Em ambientes côncavos (L/U/T/recuos), não depende do centro global.
    Testa as duas faces da parede com pequenos deslocamentos progressivos.
    """
    n1 = (-vy, vx)
    n2 = (vy, -vx)

    norma1 = math.hypot(n1[0], n1[1]) or 1.0
    norma2 = math.hypot(n2[0], n2[1]) or 1.0
    n1 = (n1[0] / norma1, n1[1] / norma1)
    n2 = (n2[0] / norma2, n2[1] / norma2)

    for d in (probe, 0.02, 0.01, 0.10):
        p1 = (start_x + n1[0] * d, start_y + n1[1] * d)
        p2 = (start_x + n2[0] * d, start_y + n2[1] * d)
        dentro1 = ponto_em_poligono(p1[0], p1[1], polilinha)
        dentro2 = ponto_em_poligono(p2[0], p2[1], polilinha)
        if dentro1 != dentro2:
            return n1 if dentro1 else n2

    # Fallback apenas para geometrias degeneradas/limítrofes.
    if cx is None or cy is None:
        cx, cy = centro_poligono(polilinha)
    return get_inside_normal(vx, vy, start_x, start_y, cx, cy)


def centro_poligono(poly):
    return (
        sum(pt[0] for pt in poly) / len(poly),
        sum(pt[1] for pt in poly) / len(poly)
    )


def bbox_poligono(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]

    return (
        min(xs),
        max(xs),
        min(ys),
        max(ys)
    )


def distancia_borda_poligono(x, y, poly):
    """
    Menor distância de um ponto a qualquer aresta do polígono.
    """
    if not poly or len(poly) < 2:
        return 0.0

    melhor = float("inf")

    for i in range(len(poly)):
        a = poly[i]
        b = poly[(i + 1) % len(poly)]

        d = point_seg_dist(
            x,
            y,
            a,
            b
        )

        if d < melhor:
            melhor = d

    return (
        0.0
        if melhor == float("inf")
        else melhor
    )


def centroide_area_poligono(poly):
    """
    Centroide geométrico por área (shoelace).
    Pode ficar fora em alguns polígonos côncavos; por isso é apenas
    um candidato para ponto_central_interno().
    """
    if not poly or len(poly) < 3:
        return centro_poligono(poly)

    area2 = 0.0
    cx = 0.0
    cy = 0.0

    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]

        cruz = (
            x1 * y2
            - x2 * y1
        )

        area2 += cruz
        cx += (x1 + x2) * cruz
        cy += (y1 + y2) * cruz

    if abs(area2) <= 1e-12:
        return centro_poligono(poly)

    return (
        cx / (3.0 * area2),
        cy / (3.0 * area2)
    )


def ponto_central_interno(
    poly,
    grade=28,
    refinamentos=4
):
    """
    Retorna um ponto visualmente central E garantidamente interno.

    Estratégia semelhante a um "pole of inaccessibility":
    escolhe, entre pontos internos, o que tem maior distância da borda.
    Isso funciona bem em WC em L, corredores irregulares e outros
    ambientes côncavos onde o centro da bounding box pode cair fora.

    O resultado é usado para:
    - ponto principal de iluminação;
    - referência de normal interna;
    - centro geométrico operacional do ambiente.
    """
    if not poly:
        return (0.0, 0.0)

    min_x, max_x, min_y, max_y = bbox_poligono(poly)

    largura = max(
        max_x - min_x,
        1e-6
    )
    altura = max(
        max_y - min_y,
        1e-6
    )

    alvo = (
        (min_x + max_x) / 2.0,
        (min_y + max_y) / 2.0
    )

    candidatos = [
        alvo,
        centroide_area_poligono(poly),
        centro_poligono(poly),
    ]

    melhor = None
    melhor_score = -1.0
    melhor_dist_alvo = float("inf")

    def testar(x, y):
        nonlocal melhor, melhor_score, melhor_dist_alvo

        if not ponto_em_poligono(
            x,
            y,
            poly
        ):
            return

        score = distancia_borda_poligono(
            x,
            y,
            poly
        )

        dist_alvo = math.hypot(
            x - alvo[0],
            y - alvo[1]
        )

        if (
            score > melhor_score + 1e-9
            or (
                abs(score - melhor_score) <= 1e-9
                and dist_alvo < melhor_dist_alvo
            )
        ):
            melhor = (x, y)
            melhor_score = score
            melhor_dist_alvo = dist_alvo

    for cand in candidatos:
        testar(
            float(cand[0]),
            float(cand[1])
        )

    nx = max(
        8,
        int(grade)
    )
    ny = nx

    for ix in range(nx + 1):
        x = (
            min_x
            + largura * ix / nx
        )

        for iy in range(ny + 1):
            y = (
                min_y
                + altura * iy / ny
            )
            testar(x, y)

    if melhor is None:
        # Último fallback: primeiro ponto ligeiramente para dentro
        # a partir do centro médio dos vértices.
        return centro_poligono(poly)

    passo_x = largura / nx
    passo_y = altura / ny

    for _ in range(max(0, int(refinamentos))):
        bx, by = melhor

        for dx in (-passo_x, -passo_x / 2.0, 0.0, passo_x / 2.0, passo_x):
            for dy in (-passo_y, -passo_y / 2.0, 0.0, passo_y / 2.0, passo_y):
                testar(
                    bx + dx,
                    by + dy
                )

        passo_x /= 3.0
        passo_y /= 3.0

    return melhor


def ponto_interno_proximo(
    poly,
    alvo,
    grade=22
):
    """
    Retorna o ponto interno mais próximo de um alvo.
    Útil para múltiplos pontos de iluminação quando o alvo teórico
    cai fora de um polígono côncavo.
    """
    ax, ay = alvo

    if ponto_em_poligono(
        ax,
        ay,
        poly
    ):
        return (ax, ay)

    min_x, max_x, min_y, max_y = bbox_poligono(poly)
    largura = max(max_x - min_x, 1e-6)
    altura = max(max_y - min_y, 1e-6)

    melhor = None
    menor = float("inf")

    n = max(10, int(grade))

    for ix in range(n + 1):
        x = min_x + largura * ix / n

        for iy in range(n + 1):
            y = min_y + altura * iy / n

            if not ponto_em_poligono(
                x,
                y,
                poly
            ):
                continue

            d = math.hypot(
                x - ax,
                y - ay
            )

            # pequena preferência por não encostar em parede
            folga = distancia_borda_poligono(
                x,
                y,
                poly
            )

            score = (
                d
                - min(folga, 0.20) * 0.05
            )

            if score < menor:
                menor = score
                melhor = (x, y)

    return (
        melhor
        if melhor is not None
        else ponto_central_interno(poly)
    )


def pontos_iluminacao_internos(
    poly,
    quantidade,
    afastamento_minimo=0.35,
    grade=36
):
    """
    Distribui pontos de iluminação no interior real do polígono.

    - nunca aceita ponto fora do ambiente;
    - prefere pelo menos afastamento_minimo das paredes;
    - para vários pontos, espalha os pontos pelo interior útil;
    - em ambientes estreitos relaxa a folga, mas continua interno.
    """
    quantidade = max(
        0,
        int(
            quantidade or 0
        )
    )

    if quantidade <= 0:
        return []

    if not poly or len(poly) < 3:
        return []

    if quantidade == 1:
        return [
            ponto_central_interno(
                poly
            )
        ]

    min_x, max_x, min_y, max_y = (
        bbox_poligono(
            poly
        )
    )

    largura = max(
        max_x - min_x,
        1e-9
    )

    altura = max(
        max_y - min_y,
        1e-9
    )

    n = max(
        18,
        int(
            grade
        )
    )

    centro = (
        ponto_central_interno(
            poly
        )
    )

    def gerar_candidatos(
        folga
    ):
        candidatos = []

        for ix in range(
            n + 1
        ):
            x = (
                min_x
                + largura
                * ix / n
            )

            for iy in range(
                n + 1
            ):
                y = (
                    min_y
                    + altura
                    * iy / n
                )

                if not ponto_em_poligono(
                    x,
                    y,
                    poly
                ):
                    continue

                dist_borda = (
                    distancia_borda_poligono(
                        x,
                        y,
                        poly
                    )
                )

                if (
                    dist_borda
                    + 1e-9
                    < folga
                ):
                    continue

                candidatos.append(
                    (
                        x,
                        y,
                        dist_borda
                    )
                )

        return candidatos

    folgas = [
        float(
            afastamento_minimo
        ),
        float(
            afastamento_minimo
        ) * 0.80,
        float(
            afastamento_minimo
        ) * 0.60,
        float(
            afastamento_minimo
        ) * 0.40,
        0.10,
        0.05,
        0.0
    ]

    candidatos = []

    for folga in folgas:
        candidatos = (
            gerar_candidatos(
                max(
                    0.0,
                    folga
                )
            )
        )

        if (
            len(
                candidatos
            )
            >= quantidade
        ):
            break

    if not candidatos:
        return [
            ponto_central_interno(
                poly
            )
        ]

    def score_primeiro(
        cand
    ):
        x, y, dist_borda = (
            cand
        )

        dist_centro = math.hypot(
            x - centro[0],
            y - centro[1]
        )

        return (
            dist_borda * 4.0
            - dist_centro * 0.25
        )

    primeiro = max(
        candidatos,
        key=score_primeiro
    )

    escolhidos = [
        (
            primeiro[0],
            primeiro[1]
        )
    ]

    restantes = [
        c
        for c in candidatos
        if (
            abs(
                c[0]
                - primeiro[0]
            )
            > 1e-9
            or abs(
                c[1]
                - primeiro[1]
            )
            > 1e-9
        )
    ]

    while (
        len(
            escolhidos
        )
        < quantidade
        and restantes
    ):
        melhor = None
        melhor_score = (
            -float(
                "inf"
            )
        )

        for cand in restantes:
            x, y, dist_borda = (
                cand
            )

            dist_outros = min(
                math.hypot(
                    x - ex,
                    y - ey
                )
                for ex, ey
                in escolhidos
            )

            score = (
                dist_outros
                + dist_borda * 1.25
            )

            if (
                score
                > melhor_score
            ):
                melhor_score = (
                    score
                )
                melhor = cand

        if melhor is None:
            break

        escolhidos.append(
            (
                melhor[0],
                melhor[1]
            )
        )

        restantes = [
            c
            for c in restantes
            if not (
                abs(
                    c[0]
                    - melhor[0]
                )
                <= 1e-9
                and abs(
                    c[1]
                    - melhor[1]
                )
                <= 1e-9
            )
        ]

    while (
        len(
            escolhidos
        )
        < quantidade
    ):
        escolhidos.append(
            ponto_central_interno(
                poly
            )
        )

    return (
        escolhidos[
            :quantidade
        ]
    )


def _poligono_ortogonal(
    poly,
    tolerancia=1e-8
):
    """
    True quando todas as arestas são horizontais ou verticais.
    """
    if not poly or len(poly) < 4:
        return False

    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[
            (i + 1)
            % len(poly)
        ]

        dx = abs(
            float(x2)
            - float(x1)
        )
        dy = abs(
            float(y2)
            - float(y1)
        )

        if (
            dx > tolerancia
            and dy > tolerancia
        ):
            return False

    return True


def _celulas_ortogonais_internas(
    poly
):
    """
    Cria a grade mínima definida pelos X/Y dos vértices e retorna
    somente células retangulares cujo centro está dentro do polígono.

    Para um ambiente em L, isso naturalmente produz os blocos internos
    que formam o L.
    """
    xs = sorted(
        {
            float(p[0])
            for p in poly
        }
    )

    ys = sorted(
        {
            float(p[1])
            for p in poly
        }
    )

    celulas = []

    for ix in range(
        len(xs) - 1
    ):
        x0 = xs[ix]
        x1 = xs[
            ix + 1
        ]

        if (
            x1 - x0
            <= 1e-9
        ):
            continue

        for iy in range(
            len(ys) - 1
        ):
            y0 = ys[iy]
            y1 = ys[
                iy + 1
            ]

            if (
                y1 - y0
                <= 1e-9
            ):
                continue

            cx = (
                x0 + x1
            ) / 2.0

            cy = (
                y0 + y1
            ) / 2.0

            if ponto_em_poligono(
                cx,
                cy,
                poly
            ):
                celulas.append({
                    "ix":
                        ix,
                    "iy":
                        iy,
                    "x0":
                        x0,
                    "x1":
                        x1,
                    "y0":
                        y0,
                    "y1":
                        y1,
                    "area":
                        (
                            x1 - x0
                        )
                        * (
                            y1 - y0
                        )
                })

    return (
        celulas,
        xs,
        ys
    )


def _retangulo_bbox_de_indices(
    indices,
    xs,
    ys
):
    ixs = [
        p[0]
        for p in indices
    ]
    iys = [
        p[1]
        for p in indices
    ]

    ix0 = min(ixs)
    ix1 = max(ixs)
    iy0 = min(iys)
    iy1 = max(iys)

    return {
        "ix0":
            ix0,
        "ix1":
            ix1,
        "iy0":
            iy0,
        "iy1":
            iy1,
        "x0":
            xs[ix0],
        "x1":
            xs[
                ix1 + 1
            ],
        "y0":
            ys[iy0],
        "y1":
            ys[
                iy1 + 1
            ]
    }


def decompor_poligono_ortogonal_em_retangulos(
    poly
):
    """
    Decompõe ambiente ortogonal (L, T, U, recortado etc.) em retângulos.

    Estratégia:
    1. cria células internas pela grade dos vértices;
    2. cresce retângulos máximos a partir de cada célula livre;
    3. escolhe sempre o maior retângulo disponível;
    4. repete até cobrir todas as células.

    Não desenha nada no DXF: é apenas geometria interna de cálculo.
    """
    if not _poligono_ortogonal(
        poly
    ):
        return []

    celulas, xs, ys = (
        _celulas_ortogonais_internas(
            poly
        )
    )

    if not celulas:
        return []

    livres = {
        (
            c["ix"],
            c["iy"]
        )
        for c in celulas
    }

    def area_indices(
        ix0,
        ix1,
        iy0,
        iy1
    ):
        return (
            xs[ix1 + 1]
            - xs[ix0]
        ) * (
            ys[iy1 + 1]
            - ys[iy0]
        )

    retangulos = []

    while livres:
        melhor = None
        melhor_area = -1.0

        # Procura maior retângulo totalmente formado por células livres.
        ix_values = sorted(
            {
                p[0]
                for p in livres
            }
        )

        iy_values = sorted(
            {
                p[1]
                for p in livres
            }
        )

        for ix0 in ix_values:
            for ix1 in ix_values:
                if ix1 < ix0:
                    continue

                for iy0 in iy_values:
                    for iy1 in iy_values:
                        if iy1 < iy0:
                            continue

                        bloco = {
                            (
                                ix,
                                iy
                            )
                            for ix in range(
                                ix0,
                                ix1 + 1
                            )
                            for iy in range(
                                iy0,
                                iy1 + 1
                            )
                        }

                        if not bloco:
                            continue

                        if not bloco.issubset(
                            livres
                        ):
                            continue

                        area = area_indices(
                            ix0,
                            ix1,
                            iy0,
                            iy1
                        )

                        if (
                            area
                            > melhor_area
                            + 1e-9
                        ):
                            melhor_area = area
                            melhor = (
                                ix0,
                                ix1,
                                iy0,
                                iy1,
                                bloco
                            )

        if melhor is None:
            # segurança: consome uma célula isolada
            ix, iy = next(
                iter(
                    livres
                )
            )

            melhor = (
                ix,
                ix,
                iy,
                iy,
                {
                    (
                        ix,
                        iy
                    )
                }
            )

        (
            ix0,
            ix1,
            iy0,
            iy1,
            bloco
        ) = melhor

        ret = {
            "x0":
                xs[ix0],
            "x1":
                xs[
                    ix1 + 1
                ],
            "y0":
                ys[iy0],
            "y1":
                ys[
                    iy1 + 1
                ]
        }

        ret["largura"] = (
            ret["x1"]
            - ret["x0"]
        )

        ret["altura"] = (
            ret["y1"]
            - ret["y0"]
        )

        ret["area"] = (
            ret["largura"]
            * ret["altura"]
        )

        ret["centro"] = (
            (
                ret["x0"]
                + ret["x1"]
            ) / 2.0,
            (
                ret["y0"]
                + ret["y1"]
            ) / 2.0
        )

        retangulos.append(
            ret
        )

        livres -= bloco

    # Maiores primeiro: em um L simples teremos os 2 blocos principais.
    retangulos.sort(
        key=lambda r:
            r["area"],
        reverse=True
    )

    return retangulos


def _alocar_quantidades_por_area(
    retangulos,
    quantidade
):
    """
    Distribui a quantidade de luminárias entre retângulos.
    Se quantidade >= nº de retângulos, garante pelo menos 1 em cada.
    """
    quantidade = int(
        quantidade
    )

    n = len(
        retangulos
    )

    if (
        quantidade <= 0
        or n == 0
    ):
        return [
            0
            for _ in retangulos
        ]

    # Menos luminárias que regiões: prioriza maiores regiões.
    if quantidade < n:
        saida = [
            0
            for _ in retangulos
        ]

        for i in range(
            quantidade
        ):
            saida[i] = 1

        return saida

    saida = [
        1
        for _ in retangulos
    ]

    restantes = (
        quantidade
        - n
    )

    if restantes <= 0:
        return saida

    areas = [
        max(
            0.0,
            r["area"]
        )
        for r in retangulos
    ]

    total = sum(
        areas
    )

    if total <= 1e-12:
        for i in range(
            restantes
        ):
            saida[
                i % n
            ] += 1

        return saida

    quotas = [
        restantes
        * area / total
        for area in areas
    ]

    inteiros = [
        int(
            math.floor(
                q
            )
        )
        for q in quotas
    ]

    for i, valor in enumerate(
        inteiros
    ):
        saida[i] += valor

    faltam = (
        restantes
        - sum(
            inteiros
        )
    )

    ordem = sorted(
        range(n),
        key=lambda i:
            (
                quotas[i]
                - inteiros[i],
                areas[i]
            ),
        reverse=True
    )

    for i in range(
        faltam
    ):
        saida[
            ordem[
                i % n
            ]
        ] += 1

    return saida


def _pontos_em_retangulo(
    retangulo,
    quantidade,
    afastamento_minimo=0.35
):
    """
    Distribui pontos dentro de um único retângulo.
    1 ponto -> centro.
    vários -> ao longo do maior eixo.
    """
    quantidade = int(
        quantidade
    )

    if quantidade <= 0:
        return []

    x0 = retangulo[
        "x0"
    ]
    x1 = retangulo[
        "x1"
    ]
    y0 = retangulo[
        "y0"
    ]
    y1 = retangulo[
        "y1"
    ]

    largura = (
        x1 - x0
    )

    altura = (
        y1 - y0
    )

    if quantidade == 1:
        return [
            (
                (
                    x0 + x1
                ) / 2.0,
                (
                    y0 + y1
                ) / 2.0
            )
        ]

    # Folga nunca pode consumir o retângulo inteiro.
    folga_x = min(
        afastamento_minimo,
        largura * 0.20
    )

    folga_y = min(
        afastamento_minimo,
        altura * 0.20
    )

    pontos = []

    if largura >= altura:
        ini = (
            x0 + folga_x
        )
        fim = (
            x1 - folga_x
        )

        passo = (
            fim - ini
        ) / (
            quantidade + 1
        )

        cy = (
            y0 + y1
        ) / 2.0

        for i in range(
            1,
            quantidade + 1
        ):
            pontos.append(
                (
                    ini
                    + passo * i,
                    cy
                )
            )

    else:
        ini = (
            y0 + folga_y
        )
        fim = (
            y1 - folga_y
        )

        passo = (
            fim - ini
        ) / (
            quantidade + 1
        )

        cx = (
            x0 + x1
        ) / 2.0

        for i in range(
            1,
            quantidade + 1
        ):
            pontos.append(
                (
                    cx,
                    ini
                    + passo * i
                )
            )

    return pontos


def pontos_iluminacao_por_decomposicao(
    poly,
    quantidade,
    afastamento_minimo=0.35
):
    """
    Regra Fase 8.2.

    Para ambientes ortogonais:
    - retângulo/quadrado -> distribuição normal no próprio retângulo;
    - L/T/U/recortados -> decompõe em retângulos e distribui por região.

    Para geometrias não ortogonais, retorna [] para permitir fallback
    à rotina genérica pontos_iluminacao_internos().
    """
    quantidade = max(
        0,
        int(
            quantidade or 0
        )
    )

    if quantidade <= 0:
        return []

    retangulos = (
        decompor_poligono_ortogonal_em_retangulos(
            poly
        )
    )

    if not retangulos:
        return []

    alocacao = (
        _alocar_quantidades_por_area(
            retangulos,
            quantidade
        )
    )

    pontos = []

    for retangulo, qtd in zip(
        retangulos,
        alocacao
    ):
        pontos.extend(
            _pontos_em_retangulo(
                retangulo,
                qtd,
                afastamento_minimo=
                    afastamento_minimo
            )
        )

    # Segurança geométrica final.
    pontos_validos = []

    for ponto in pontos:
        if ponto_em_poligono(
            ponto[0],
            ponto[1],
            poly
        ):
            pontos_validos.append(
                ponto
            )

    if len(
        pontos_validos
    ) == quantidade:
        return pontos_validos

    return []
