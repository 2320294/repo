
import math

LAYER = "DEBUG_SOLEIRA_VERTICES"
COR = 1
ALTURA_TEXTO = 0.14
OFFSET_TEXTO = 0.10
RAIO = 0.035

def _xy(v):
    if hasattr(v, "x") and hasattr(v, "y"):
        return (float(v.x), float(v.y))
    return (float(v[0]), float(v[1]))

def _vertices(ent):
    if ent.dxftype() == "LWPOLYLINE":
        return [(float(x), float(y)) for x, y, *_ in ent.get_points()]
    if ent.dxftype() == "POLYLINE":
        return [_xy(v.dxf.location) for v in ent.vertices]
    return []

def _dist(a,b):
    return math.hypot(b[0]-a[0], b[1]-a[1])

def _ordenar_quatro(vertices):
    pts = list(dict.fromkeys((round(x,8), round(y,8)) for x,y in vertices))
    if len(pts) < 4:
        return []
    if len(pts) > 4:
        cx = sum(x for x,y in pts)/len(pts)
        cy = sum(y for x,y in pts)/len(pts)
        pts = sorted(pts, key=lambda p: -_dist(p,(cx,cy)))[:4]
    cx = sum(x for x,y in pts)/4
    cy = sum(y for x,y in pts)/4
    circ = sorted(pts, key=lambda p: math.atan2(p[1]-cy, p[0]-cx))
    start = min(range(4), key=lambda i: (circ[i][1], circ[i][0]))
    return circ[start:] + circ[:start]

def desenhar_debug_soleiras(doc, msp, layer_soleira="IA_SOLEIRAS"):
    if LAYER not in doc.layers:
        doc.layers.new(LAYER, dxfattribs={"color": COR})
    qtd = 0
    for ent in list(msp):
        if ent.dxf.layer != layer_soleira:
            continue
        ordem = _ordenar_quatro(_vertices(ent))
        if len(ordem) != 4:
            continue
        cx = sum(p[0] for p in ordem)/4
        cy = sum(p[1] for p in ordem)/4
        for i,p in enumerate(ordem, start=1):
            vx, vy = p[0]-cx, p[1]-cy
            d = math.hypot(vx,vy) or 1
            tp = (p[0] + OFFSET_TEXTO*vx/d, p[1] + OFFSET_TEXTO*vy/d)
            msp.add_circle(p, radius=RAIO, dxfattribs={"layer":LAYER,"color":COR})
            txt = msp.add_text(
                f"P{i}",
                dxfattribs={"layer":LAYER,"height":ALTURA_TEXTO,"color":COR}
            )
            txt.dxf.insert = tp
        qtd += 1
    return qtd
