
import math

def distancia(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def distancia_ponto_segmento(p, a, b):
    vx, vy = b[0]-a[0], b[1]-a[1]
    wx, wy = p[0]-a[0], p[1]-a[1]
    den = vx*vx + vy*vy
    if den <= 1e-15:
        return distancia(p, a)
    t = max(0.0, min(1.0, (wx*vx + wy*vy)/den))
    q = (a[0] + t*vx, a[1] + t*vy)
    return distancia(p, q)

def ordenar_circular_quatro(vertices):
    pts = []
    for x, y in vertices:
        q = (round(float(x), 8), round(float(y), 8))
        if q not in pts:
            pts.append(q)
    if len(pts) != 4:
        return []
    cx = sum(x for x, y in pts) / 4.0
    cy = sum(y for x, y in pts) / 4.0
    return sorted(pts, key=lambda p: math.atan2(p[1]-cy, p[0]-cx))

def segmentos_porta(porta):
    # dxf_io currently represents each door by its principal segment.
    if not porta:
        return []
    return [(porta["p1"], porta["p2"])]

def rotular_p1_p4(vertices, porta):
    """
    Regra fixa AutoElétrica:
      P1 = vértice da soleira no encontro com a porta;
      P2 = adjacente a P1 pelo MAIOR lado;
      P3 = vértice seguinte;
      P4 = restante.
    """
    circ = ordenar_circular_quatro(vertices)
    if len(circ) != 4:
        return None

    segs = segmentos_porta(porta)
    if not segs:
        return None

    p1 = min(
        circ,
        key=lambda p: min(distancia_ponto_segmento(p, a, b) for a, b in segs)
    )
    i = circ.index(p1)
    ant = circ[(i-1) % 4]
    prox = circ[(i+1) % 4]

    if distancia(p1, ant) >= distancia(p1, prox):
        p2, p4 = ant, prox
    else:
        p2, p4 = prox, ant

    p3 = next(p for p in circ if p not in (p1, p2, p4))
    return {"p1": p1, "p2": p2, "p3": p3, "p4": p4}

def ponto_10cm_apos_p2(rotulos, afastamento=0.10):
    """
    Continua a direção P1 -> P2 por exatamente 'afastamento'.
    O ponto resultante é o centro/inserção do interruptor.
    """
    p1 = rotulos["p1"]
    p2 = rotulos["p2"]
    dx, dy = p2[0]-p1[0], p2[1]-p1[1]
    comp = math.hypot(dx, dy)
    if comp <= 1e-12:
        return None
    ux, uy = dx/comp, dy/comp
    return (p2[0] + ux*afastamento, p2[1] + uy*afastamento)
