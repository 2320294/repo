
import math

from geometria import centro_poligono, get_inside_normal
from soleiras_geometria import (
    rotular_p1_p4,
    ponto_10cm_apos_p2,
    distancia_ponto_segmento,
)

RAIO_INTERRUPTOR = 0.025
AFASTAMENTO_APOS_P2 = 0.10
TOLERANCIA_SOLEIRA_AMBIENTE = 0.03


def _vertices_soleira(s):
    out=[]
    for p in (s.get("vertices") or []):
        q=(float(p[0]),float(p[1]))
        if q not in out: out.append(q)
    return out


def _segmentos(poly):
    return [(poly[i],poly[(i+1)%len(poly)]) for i in range(len(poly))] if len(poly)>=2 else []


def _soleira_toca_ambiente(s,poly):
    verts=_vertices_soleira(s)
    segs=_segmentos(poly)
    if not verts or not segs:
        return False
    return min(
        distancia_ponto_segmento(v,a,b)
        for v in verts
        for a,b in segs
    ) <= TOLERANCIA_SOLEIRA_AMBIENTE


def _porta_mais_proxima(s,portas_raw):
    verts=_vertices_soleira(s)
    if not verts or not portas_raw:
        return None
    melhor=None
    menor=float("inf")
    for porta in portas_raw:
        a,b=porta["p1"],porta["p2"]
        d=min(distancia_ponto_segmento(v,a,b) for v in verts)
        if d<menor:
            menor=d
            melhor=porta
    return melhor


def _nome_ambiente(poly,textos):
    xs=[p[0] for p in poly]
    ys=[p[1] for p in poly]
    return next(
        (
            t["nome"] for t in textos
            if min(xs)-0.5 <= t["x"] <= max(xs)+0.5
            and min(ys)-0.5 <= t["y"] <= max(ys)+0.5
        ),
        None
    )


def _ambientes(polilinhas,textos):
    usados={}
    out=[]
    for poly in polilinhas:
        nome=_nome_ambiente(poly,textos)
        if not nome: continue
        if nome in usados:
            usados[nome]+=1
            nome=f"{nome} {usados[nome]}"
        else:
            usados[nome]=1
        out.append({"nome":nome,"poly":poly})
    return out


def _candidato(amb,s,porta):
    verts=_vertices_soleira(s)
    rot=rotular_p1_p4(verts,porta)
    if not rot:
        return None

    tang=ponto_10cm_apos_p2(rot,AFASTAMENTO_APOS_P2)
    if tang is None:
        return None

    p1,p2=rot["p1"],rot["p2"]
    dx,dy=p2[0]-p1[0],p2[1]-p1[1]
    comp=math.hypot(dx,dy)
    if comp<=1e-12:
        return None

    ux,uy=dx/comp,dy/comp
    cx,cy=centro_poligono(amb["poly"])
    normal=get_inside_normal(
        ux,uy,tang[0],tang[1],cx,cy
    )

    centro=(
        tang[0]+normal[0]*RAIO_INTERRUPTOR,
        tang[1]+normal[1]*RAIO_INTERRUPTOR
    )

    return {
        "centro":centro,
        "tangencia":tang,
        "rot":rot
    }


def desenhar_interruptores(
    msp,
    polilinhas,
    textos,
    soleiras_raw,
    portas_raw,
    config_interruptores
):
    config_interruptores=config_interruptores or {}
    resultado=[]

    for amb in _ambientes(polilinhas,textos):
        candidatos=[]

        for s in soleiras_raw:
            if not _soleira_toca_ambiente(s,amb["poly"]):
                continue

            porta=_porta_mais_proxima(s,portas_raw)
            if porta is None:
                continue

            c=_candidato(amb,s,porta)
            if c is None:
                continue

            chave=(
                round(c["tangencia"][0],5),
                round(c["tangencia"][1],5)
            )
            if any(x["chave"]==chave for x in candidatos):
                continue

            c["chave"]=chave
            candidatos.append(c)

        candidatos.sort(
            key=lambda c:(
                round(c["tangencia"][0],6),
                round(c["tangencia"][1],6)
            )
        )

        qtd_portas=len(candidatos)
        if qtd_portas==0:
            continue

        if qtd_portas==1:
            qtd=1
        else:
            cfg=config_interruptores.get(amb["nome"],{})
            if not isinstance(cfg,dict):
                cfg={}
            qtd=max(1,min(qtd_portas,int(cfg.get("quantidade",1))))

        for c in candidatos[:qtd]:
            msp.add_circle(
                center=c["centro"],
                radius=RAIO_INTERRUPTOR,
                dxfattribs={"layer":"PROJ_ELETRICA_INTERRUPTOR"}
            )

            rot=c["rot"]
            resultado.append({
                "ambiente":amb["nome"],
                "tipo":"INTERRUPTOR",
                "ponto":c["centro"],
                "ponto_tangencia":c["tangencia"],
                "referencia":"TANGENTE_10cm_APOS_P2",
                "diametro_m":0.05,
                "p1":rot["p1"],
                "p2":rot["p2"],
                "p3":rot["p3"],
                "p4":rot["p4"],
            })

    return resultado
