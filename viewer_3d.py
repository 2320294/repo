import math
import tempfile
import os
import ezdxf
import plotly.graph_objects as go

ALTURAS_PADRAO = {
    "BAIXA": 0.30,
    "MEDIA": 1.20,
    "ALTA": 2.20,
    "INTERRUPTOR": 1.20,
    "QDC": 1.50,
}

def _extrair_geometria_direto_dxf(dxf_bytes, pe_direito=2.80):
    paredes = []
    luminarias = []
    tomadas = []
    interruptores = []
    eletrodutos = []
    qdc_pt = None

    if not dxf_bytes:
        return None

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
            tmp.write(bytes(dxf_bytes))
            tmp_path = tmp.name

        doc = ezdxf.readfile(tmp_path)
        msp = doc.modelspace()

        for ent in msp:
            layer = str(getattr(ent.dxf, "layer", "") or "").upper().strip()
            tipo = ent.dxftype()

            if layer == "IA_AMBIENTES" and tipo in ("LWPOLYLINE", "POLYLINE"):
                pts = [(float(p[0]), float(p[1])) for p in ent.get_points()] if tipo == "LWPOLYLINE" else [
                    (float(v.dxf.location.x), float(v.dxf.location.y)) for v in ent.vertices
                ]
                if len(pts) >= 3:
                    if pts[0] != pts[-1]:
                        pts.append(pts[0])
                    paredes.append({"nome": "Ambiente", "polilinha": pts})

            elif layer == "PROJ_ELETRICA_LUZ" and tipo == "CIRCLE":
                c = ent.dxf.center
                luminarias.append({"x": float(c.x), "y": float(c.y), "z": float(pe_direito), "rotulo": "Caixa Octogonal (Teto)"})

            elif layer == "PROJ_ELETRICA_INTERRUPTOR" and tipo == "CIRCLE":
                c = ent.dxf.center
                interruptores.append({"x": float(c.x), "y": float(c.y), "z": ALTURAS_PADRAO["INTERRUPTOR"], "rotulo": "Interruptor 4x2"})

            elif layer == "PROJ_ELETRICA_TOMADA" and tipo == "LWPOLYLINE":
                pts = [(float(p[0]), float(p[1])) for p in ent.get_points()]
                if pts:
                    cx = sum(p[0] for p in pts) / len(pts)
                    cy = sum(p[1] for p in pts) / len(pts)
                    tomadas.append({"x": cx, "y": cy, "z": ALTURAS_PADRAO["BAIXA"], "rotulo": "Tomada 4x2"})

            elif layer == "PROJ_ELETRICA_QDC" and tipo in ("LWPOLYLINE", "POLYLINE"):
                pts = [(float(p[0]), float(p[1])) for p in ent.get_points()]
                if pts:
                    cx = sum(p[0] for p in pts) / len(pts)
                    cy = sum(p[1] for p in pts) / len(pts)
                    qdc_pt = (cx, cy, ALTURAS_PADRAO["QDC"])

            elif layer == "PROJ_ELETRICA_ROTEAMENTO":
                if tipo == "ARC":
                    c = ent.dxf.center
                    r = float(ent.dxf.radius)
                    a1 = math.radians(float(ent.dxf.start_angle))
                    a2 = math.radians(float(ent.dxf.end_angle))
                    if a2 < a1:
                        a2 += 2.0 * math.pi
                    passos = 16
                    arco_pts = [
                        (float(c.x) + r * math.cos(a1 + (a2 - a1) * i / passos),
                         float(c.y) + r * math.sin(a1 + (a2 - a1) * i / passos))
                        for i in range(passos + 1)
                    ]
                    eletrodutos.append(arco_pts)
                elif tipo == "LWPOLYLINE":
                    pts = [(float(p[0]), float(p[1])) for p in ent.get_points()]
                    if len(pts) >= 2:
                        eletrodutos.append(pts)

        return {
            "paredes": paredes,
            "luminarias": luminarias,
            "tomadas": tomadas,
            "interruptores": interruptores,
            "eletrodutos": eletrodutos,
            "qdc": qdc_pt,
        }
    except Exception:
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

def gerar_visualizacao_3d_pro(
    tabela_editada=None,
    pe_direito=2.80,
    local_qdc=None,
    camadas=None,
    dados_ambientes=None,
    resumo_rotas=None,
    dxf_bytes=None,
    **kwargs
):
    if camadas is None:
        camadas = {"paredes": True, "eletrodutos": True, "caixas": True, "qdc": True}

    pe_direito = float(pe_direito or 2.80)
    fig = go.Figure()
    geo_dxf = _extrair_geometria_direto_dxf(dxf_bytes, pe_direito=pe_direito) if dxf_bytes else None

    # 1. Paredes translúcidas
    if camadas.get("paredes", True):
        paredes_lista = (geo_dxf or {}).get("paredes") or []
        for amb in paredes_lista:
            poly = amb.get("polilinha") or []
            if len(poly) < 2:
                continue
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]

            for z_nivel in (0.0, pe_direito):
                fig.add_trace(go.Scatter3d(
                    x=xs, y=ys, z=[z_nivel] * len(xs),
                    mode="lines",
                    line=dict(color="rgba(148, 163, 184, 0.55)", width=3),
                    hoverinfo="skip",
                    showlegend=False,
                ))

            v_x, v_y, v_z = [], [], []
            for px, py in poly[:-1]:
                v_x.extend([px, px, None])
                v_y.extend([py, py, None])
                v_z.extend([0.0, pe_direito, None])

            fig.add_trace(go.Scatter3d(
                x=v_x, y=v_y, z=v_z,
                mode="lines",
                line=dict(color="rgba(148, 163, 184, 0.30)", width=2),
                hoverinfo="skip",
                showlegend=False,
            ))

    # 2. Eletrodutos
    if camadas.get("eletrodutos", True) and geo_dxf:
        rotas_2d = geo_dxf.get("eletrodutos") or []
        el_x, el_y, el_z = [], [], []
        for arco_pts in rotas_2d:
            for px, py in arco_pts:
                el_x.append(px)
                el_y.append(py)
                el_z.append(pe_direito)
            el_x.append(None)
            el_y.append(None)
            el_z.append(None)

        for item in (geo_dxf.get("tomadas") or []) + (geo_dxf.get("interruptores") or []):
            el_x.extend([item["x"], item["x"], None])
            el_y.extend([item["y"], item["y"], None])
            el_z.extend([pe_direito, item["z"], None])
            
        if geo_dxf.get("qdc"):
            qx, qy, qz = geo_dxf["qdc"]
            el_x.extend([qx, qx, None])
            el_y.extend([qy, qy, None])
            el_z.extend([pe_direito, qz, None])

        if el_x:
            fig.add_trace(go.Scatter3d(
                x=el_x, y=el_y, z=el_z,
                mode="lines",
                line=dict(color="#f59e0b", width=4),
                name="Eletrodutos",
                hoverinfo="name",
                showlegend=False,
            ))

    # 3. Caixas
    if camadas.get("caixas", True) and geo_dxf:
        lums = geo_dxf.get("luminarias") or []
        if lums:
            fig.add_trace(go.Scatter3d(
                x=[p["x"] for p in lums],
                y=[p["y"] for p in lums],
                z=[p["z"] for p in lums],
                mode="markers",
                marker=dict(size=7, color="#fde047", symbol="diamond", line=dict(color="#ca8a04", width=1)),
                text=[p["rotulo"] for p in lums],
                hoverinfo="text",
                name="Caixas Octogonais (Teto)",
            ))

        toms = geo_dxf.get("tomadas") or []
        if toms:
            fig.add_trace(go.Scatter3d(
                x=[p["x"] for p in toms],
                y=[p["y"] for p in toms],
                z=[p["z"] for p in toms],
                mode="markers",
                marker=dict(size=6, color="#38bdf8", symbol="square"),
                text=[p["rotulo"] for p in toms],
                hoverinfo="text",
                name="Tomadas 4x2",
            ))

        ints = geo_dxf.get("interruptores") or []
        if ints:
            fig.add_trace(go.Scatter3d(
                x=[p["x"] for p in ints],
                y=[p["y"] for p in ints],
                z=[p["z"] for p in ints],
                mode="markers",
                marker=dict(size=6, color="#4ade80", symbol="circle"),
                text=[p["rotulo"] for p in ints],
                hoverinfo="text",
                name="Interruptores 4x2",
            ))

    if camadas.get("qdc", True):
        qdc_coord = (geo_dxf or {}).get("qdc")
        if qdc_coord:
            qx, qy, qz = qdc_coord
            fig.add_trace(go.Scatter3d(
                x=[qx], y=[qy], z=[qz],
                mode="markers+text",
                marker=dict(size=10, color="#ef4444", symbol="square"),
                text=["QDC"],
                textposition="top center",
                hoverinfo="text",
                name="QDC (Quadro de Distribuição)",
            ))

    fig.update_layout(
        title="<b>AutoElétrica 3D — Visualização de Instalação Elétrica</b>",
        scene=dict(
            xaxis_title="X (m)",
            yaxis_title="Y (m)",
            zaxis_title="Altura Z (m)",
            zaxis=dict(range=[0.0, pe_direito + 0.4]),
            aspectmode="data",
            bgcolor="rgb(15, 23, 42)",
            xaxis=dict(gridcolor="rgba(255,255,255,0.1)", zerolinecolor="rgba(255,255,255,0.2)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.1)", zerolinecolor="rgba(255,255,255,0.2)"),
        ),
        paper_bgcolor="rgb(15, 23, 42)",
        font=dict(color="white"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1.0,
            bgcolor="rgba(15, 23, 42, 0.7)"
        ),
        margin=dict(l=0, r=0, b=0, t=50),
        height=650,
    )
    return fig

def gerar_visualizacao_3d(*args, **kwargs):
    return gerar_visualizacao_3d_pro(*args, **kwargs)
