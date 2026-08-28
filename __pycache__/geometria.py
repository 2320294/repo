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
