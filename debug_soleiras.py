
import math

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
        return [(float(x),float(y)) for x,y,*_ in ent.get_points()]
    if ent.dxftype() == "POLYLINE":
        return [_xy(v.dxf.location) for v in ent.vertices]
    if ent.dxftype() == "LINE":
        return [_xy(ent.dxf.start), _xy(ent.dxf.end)]
    return []

def _dist(a,b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def _dist_ponto_segmento(p,a,b):
    vx,vy=b[0]-a[0],b[1]-a[1]
    wx,wy=p[0]-a[0],p[1]-a[1]
    den=vx*vx+vy*vy
    if den <= 1e-15: return _dist(p,a)
    t=max(0.0,min(1.0,(wx*vx+wy*vy)/den))
    q=(a[0]+t*vx,a[1]+t*vy)
    return _dist(p,q)

def _quatro_vertices(ent):
    pts=[]
    for p in _vertices(ent):
        q=(round(p[0],8),round(p[1],8))
        if q not in pts: pts.append(q)
    if len(pts)==5 and pts[0]==pts[-1]: pts.pop()
    if len(pts)!=4: return []
    # ordem circular estável apenas para determinar adjacência física
    cx=sum(x for x,y in pts)/4; cy=sum(y for x,y in pts)/4
    return sorted(pts,key=lambda p:math.atan2(p[1]-cy,p[0]-cx))

def _segmentos_portas(msp, layer="IA_PORTAS"):
    segs=[]
    for ent in msp:
        if ent.dxf.layer != layer: continue
        pts=_vertices(ent)
        if ent.dxftype()=="LINE" and len(pts)==2:
            segs.append((pts[0],pts[1]))
        elif len(pts)>=2:
            for i in range(len(pts)-1):
                segs.append((pts[i],pts[i+1]))
    return segs

def _p1_por_porta(circ, segmentos_porta):
    # P1 = vértice da soleira geometricamente mais próximo de qualquer geometria da porta.
    return min(circ, key=lambda p:min((_dist_ponto_segmento(p,a,b) for a,b in segmentos_porta), default=1e99))

def _rotular(circ, segmentos_porta):
    if len(circ)!=4: return []
    p1=_p1_por_porta(circ,segmentos_porta)
    i=circ.index(p1)
    ant=circ[(i-1)%4]; prox=circ[(i+1)%4]
    # Regra fixa do projeto: a partir de P1, o adjacente pelo MAIOR lado é P2.
    if _dist(p1,ant) >= _dist(p1,prox):
        p2, p4 = ant, prox
    else:
        p2, p4 = prox, ant
    # P3 é o único vértice restante.
    p3=next(p for p in circ if p not in (p1,p2,p4))
    return [p1,p2,p3,p4]

def desenhar_debug_soleiras(doc,msp,layer_soleira="IA_SOLEIRAS",layer_porta="IA_PORTAS"):
    if LAYER not in doc.layers:
        doc.layers.new(LAYER,dxfattribs={"color":COR})
    portas=_segmentos_portas(msp,layer_porta)
    qtd=0
    for ent in list(msp):
        if ent.dxf.layer != layer_soleira: continue
        circ=_quatro_vertices(ent)
        ordem=_rotular(circ,portas)
        if len(ordem)!=4: continue
        cx=sum(p[0] for p in ordem)/4; cy=sum(p[1] for p in ordem)/4
        for i,p in enumerate(ordem,1):
            vx,vy=p[0]-cx,p[1]-cy
            d=math.hypot(vx,vy) or 1
            tp=(p[0]+OFFSET_TEXTO*vx/d,p[1]+OFFSET_TEXTO*vy/d)
            msp.add_circle(p,radius=RAIO,dxfattribs={"layer":LAYER,"color":COR})
            txt=msp.add_text(f"P{i}",dxfattribs={"layer":LAYER,"height":ALTURA_TEXTO,"color":COR})
            txt.dxf.insert=tp
        qtd+=1
    return qtd
