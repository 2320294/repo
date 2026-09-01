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
