
import math
from soleiras_geometria import rotular_p1_p4, distancia_ponto_segmento

LAYER = "DEBUG_SOLEIRA_VERTICES"
COR = 1
ALTURA_TEXTO = 0.14
OFFSET_TEXTO = 0.10
RAIO = 0.035

def _xy(v):
    if hasattr(v, "x") and hasattr(v, "y"):
        return float(v.x), float(v.y)
    return float(v[0]), float(v[1])

def _vertices(ent):
    if ent.dxftype() == "LWPOLYLINE":
        return [(float(x), float(y)) for x, y, *_ in ent.get_points()]
    if ent.dxftype() == "POLYLINE":
        return [_xy(v.dxf.location) for v in ent.vertices]
    return []

def _portas(msp, layer="IA_PORTAS"):
    portas = []
    for ent in msp:
        if ent.dxf.layer != layer:
            continue
        if ent.dxftype() == "LINE":
            portas.append({"p1": _xy(ent.dxf.start), "p2": _xy(ent.dxf.end)})
        elif ent.dxftype() in ("LWPOLYLINE", "POLYLINE"):
            pts = _vertices(ent)
            if len(pts) >= 2:
                portas.append({"p1": pts[0], "p2": pts[-1]})
    return portas

def _porta_mais_proxima(vertices, portas):
    if not vertices or not portas:
        return None
    def score(porta):
        a, b = porta["p1"], porta["p2"]
        return min(distancia_ponto_segmento(v, a, b) for v in vertices)
    return min(portas, key=score)

def desenhar_debug_soleiras(doc, msp, layer_soleira="IA_SOLEIRAS", layer_porta="IA_PORTAS"):
    if LAYER not in doc.layers:
        doc.layers.new(LAYER, dxfattribs={"color": COR})

    portas = _portas(msp, layer_porta)
    qtd = 0

    for ent in list(msp):
        if ent.dxf.layer != layer_soleira:
            continue
        vertices = _vertices(ent)
        porta = _porta_mais_proxima(vertices, portas)
        rot = rotular_p1_p4(vertices, porta)
        if not rot:
            continue

        ordem = [rot["p1"], rot["p2"], rot["p3"], rot["p4"]]
        cx = sum(p[0] for p in ordem)/4
        cy = sum(p[1] for p in ordem)/4

        for i, p in enumerate(ordem, 1):
            vx, vy = p[0]-cx, p[1]-cy
            d = math.hypot(vx, vy) or 1
            tp = (p[0] + OFFSET_TEXTO*vx/d, p[1] + OFFSET_TEXTO*vy/d)
            msp.add_circle(p, radius=RAIO, dxfattribs={"layer": LAYER, "color": COR})
            texto = msp.add_text(
                f"P{i}",
                dxfattribs={"layer": LAYER, "height": ALTURA_TEXTO, "color": COR}
            )
            texto.dxf.insert = tp
        qtd += 1
    return qtd
