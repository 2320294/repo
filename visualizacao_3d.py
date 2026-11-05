"""Visualização 3D inicial da planta DXF (Fase 13.6 Rev.349)."""
import io
import math
import os

import ezdxf
import plotly.graph_objects as go
import streamlit as st


def _abrir_dxf(dxf_origem):
    """Aceita bytes, arquivo-like ou caminho DXF (o painel pode fornecer str)."""
    if isinstance(dxf_origem, (bytes, bytearray, memoryview)):
        return ezdxf.read(io.BytesIO(bytes(dxf_origem)))
    if isinstance(dxf_origem, str):
        if os.path.isfile(dxf_origem):
            return ezdxf.readfile(dxf_origem)
        # Se for conteúdo textual DXF, tenta codificação compatível.
        return ezdxf.read(io.StringIO(dxf_origem))
    if hasattr(dxf_origem, "read"):
        return ezdxf.read(dxf_origem)
    raise TypeError(f"Origem DXF não suportada: {type(dxf_origem).__name__}")


def _coords_entidade(ent):
    tipo = ent.dxftype()
    try:
        if tipo == "LINE":
            return [tuple(ent.dxf.start[:2]), tuple(ent.dxf.end[:2])], False
        if tipo == "LWPOLYLINE":
            pts = [(float(p[0]), float(p[1])) for p in ent.get_points()]
            return pts, bool(ent.closed)
        if tipo == "POLYLINE":
            pts = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in ent.vertices]
            return pts, bool(ent.is_closed)
        if tipo == "CIRCLE":
            c = ent.dxf.center
            r = float(ent.dxf.radius)
            pts = [(c.x+r*math.cos(2*math.pi*i/48), c.y+r*math.sin(2*math.pi*i/48)) for i in range(49)]
            return pts, True
        if tipo == "ARC":
            c=ent.dxf.center; r=float(ent.dxf.radius)
            a=float(ent.dxf.start_angle); b=float(ent.dxf.end_angle)
            while b<a: b+=360
            n=max(8,int((b-a)/7.5))
            pts=[(c.x+r*math.cos(math.radians(a+(b-a)*i/n)),
                  c.y+r*math.sin(math.radians(a+(b-a)*i/n))) for i in range(n+1)]
            return pts, False
    except Exception:
        return [], False
    return [], False


def renderizar_visualizacao_3d(dxf_bytes, pe_direito=2.80):
    st.subheader("🏗️ Visualização 3D da planta")
    st.caption("Prévia tridimensional da arquitetura extraída do DXF. A altura é a mesma definida em Parâmetros (Etapa 1); a planta original permanece intacta.")
    if dxf_bytes is None or dxf_bytes == b"" or dxf_bytes == "":
        st.info("Processe/import uma planta DXF na etapa Parâmetros para visualizar em 3D.")
        return

    # Altura fixa conforme Etapa 1 — sem controle independente nesta tela.
    try:
        altura = float(pe_direito or 2.80)
    except (TypeError, ValueError):
        altura = 2.80
    c1,c2=st.columns(2)
    mostrar_piso=c1.checkbox("Mostrar contornos no piso",True,key="ae3d_piso")
    mostrar_topo=c2.checkbox("Mostrar contornos superiores",True,key="ae3d_topo")
    try:
        doc=_abrir_dxf(dxf_bytes)
        msp=doc.modelspace()
        fig=go.Figure()
        layers={}
        entidades=0
        for ent in msp:
            pts,closed=_coords_entidade(ent)
            if len(pts)<2: continue
            layer=str(ent.dxf.layer or "0")
            layers.setdefault(layer,[]).append((pts,closed))
            entidades+=1

        for layer,items in layers.items():
            xs=[];ys=[];zs=[]
            for pts,closed in items:
                sequencia=pts+([pts[0]] if closed and pts[-1]!=pts[0] else [])
                if mostrar_piso:
                    xs.extend([p[0] for p in sequencia]+[None])
                    ys.extend([p[1] for p in sequencia]+[None])
                    zs.extend([0.0]*len(sequencia)+[None])
                if closed and len(pts)>=3:
                    for x,y in pts:
                        xs.extend([x,x,None]); ys.extend([y,y,None]); zs.extend([0.0,altura,None])
                    if mostrar_topo:
                        xs.extend([p[0] for p in sequencia]+[None])
                        ys.extend([p[1] for p in sequencia]+[None])
                        zs.extend([altura]*len(sequencia)+[None])
            if xs:
                fig.add_trace(go.Scatter3d(x=xs,y=ys,z=zs,mode="lines",name=layer,
                    line=dict(width=2),hovertemplate=f"Layer: {layer}<extra></extra>"))
        if not entidades:
            st.warning("Não foram encontradas entidades lineares/circulares compatíveis no DXF.")
            return
        fig.update_layout(height=680,margin=dict(l=0,r=0,t=25,b=0),
            scene=dict(xaxis_title="X (unidade DXF)",yaxis_title="Y (unidade DXF)",zaxis_title="Altura (m)",
                      aspectmode="data",camera=dict(eye=dict(x=1.55,y=1.55,z=1.15))),
            legend=dict(orientation="h",y=1.02))
        st.plotly_chart(fig,use_container_width=True,config={"scrollZoom":True,"displaylogo":False})
        st.caption(f"Prévia gerada a partir de {entidades} entidades DXF. Altura: {altura:.2f} m (Parâmetros/Etapa 1). Gire e aproxime com o mouse.")
    except Exception as e:
        st.error(f"Falha ao montar a visualização 3D: {e}")
