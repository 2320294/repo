import plotly.graph_objects as go
import math

def gerar_visualizacao_3d_pro(tabela_editada, pe_direito=2.80, local_qdc=None, camadas=None, dados_ambientes=None):
    if camadas is None:
        camadas = {"paredes": True, "eletrodutos": True, "caixas": True, "qdc": True}
        
    fig = go.Figure()
    ALTURAS = {"Tomada Baixa": 0.30, "Interruptor": 1.10, "Chuveiro": 2.20, "QDC": 1.50}
    
    qx, qy = 0.0, 0.0
    if isinstance(local_qdc, dict):
        qx = float(local_qdc.get("x", 0.0) or 0.0)
        qy = float(local_qdc.get("y", 0.0) or 0.0)

    ambientes_coords = {}
    if isinstance(dados_ambientes, list):
        for amb in dados_ambientes:
            nome = str(amb.get("nome", "") or "").strip()
            centro = amb.get("centro")
            if centro and len(centro) >= 2:
                ambientes_coords[nome.casefold()] = (float(centro[0]), float(centro[1]))

    if camadas.get("paredes", True):
        all_x = [qx]
        all_y = [qy]
        for coord in ambientes_coords.values():
            all_x.append(coord[0])
            all_y.append(coord[1])
            
        min_x, max_x = min(all_x) - 1.5, max(all_x) + 1.5
        min_y, max_y = min(all_y) - 1.5, max(all_y) + 1.5
        
        p_x = [min_x, max_x, max_x, min_x, min_x]
        p_y = [min_y, min_y, max_y, max_y, min_y]
        
        for z_val in [0.0, pe_direito]:
            fig.add_trace(go.Scatter3d(
                x=p_x, y=p_y, z=[z_val]*len(p_x),
                mode='lines', line=dict(color='rgba(100, 150, 255, 0.4)', width=3),
                showlegend=False
            ))
        for px, py in zip([min_x, max_x, max_x, min_x], [min_y, min_y, max_y, max_y]):
            fig.add_trace(go.Scatter3d(
                x=[px, px], y=[py, py], z=[0.0, pe_direito],
                mode='lines', line=dict(color='rgba(100, 150, 255, 0.3)', width=2),
                showlegend=False
            ))

    px_pts, py_pts, pz_pts, textos, cores = [], [], [], [], []
    
    if camadas.get("qdc", True):
        px_pts.append(qx); py_pts.append(qy); pz_pts.append(ALTURAS["QDC"])
        textos.append("QDC (Quadro de Distribuição)"); cores.append("red")

    for idx, row in enumerate(tabela_editada or []):
        amb_nome = str(row.get("Ambiente", f"Cômodo {idx+1}")).strip()
        
        if amb_nome.casefold() in ambientes_coords:
            x, y = ambientes_coords[amb_nome.casefold()]
        else:
            ang = idx * (2 * math.pi / max(1, len(tabela_editada)))
            r = 2.0 + (idx % 2) * 1.0
            x, y = qx + r * math.cos(ang), qy + r * math.sin(ang)
        
        if camadas.get("caixas", True):
            px_pts.append(x); py_pts.append(y); pz_pts.append(pe_direito - 0.10)
            textos.append(f"Ponto de Luz — {amb_nome}"); cores.append("gold")
            
        tugs = int(row.get("TUGs (Qtd)", 0) or 0)
        if tugs > 0 and camadas.get("caixas", True):
            px_pts.append(x + 0.5); py_pts.append(y + 0.5); pz_pts.append(ALTURAS["Tomada Baixa"])
            textos.append(f"Tomada 4x2 (TUG) — {amb_nome}"); cores.append("dodgerblue")
            
        if camadas.get("eletrodutos", True) and tugs > 0:
            fig.add_trace(go.Scatter3d(
                x=[qx, x, x + 0.5], y=[qy, y, y + 0.5], z=[ALTURAS["QDC"], pe_direito - 0.10, ALTURAS["Tomada Baixa"]],
                mode='lines', line=dict(color='orange', width=4),
                showlegend=False
            ))

    if px_pts:
        fig.add_trace(go.Scatter3d(
            x=px_pts, y=py_pts, z=pz_pts,
            mode='markers+text',
            marker=dict(size=7, color=cores, opacity=0.9),
            text=textos, textposition="top center",
            showlegend=False
        ))

    fig.update_layout(
        title="<b>AutoElétrica 3D — Visualizador Tridimensional Baseado no DXF Real</b>",
        scene=dict(
            xaxis_title="Eixo X (m)", yaxis_title="Eixo Y (m)", zaxis_title="Altura Z (m)",
            zaxis=dict(range=[0, pe_direito + 0.5]),
            aspectmode='data',
            bgcolor='rgba(15, 23, 42, 0.9)'
        ),
        paper_bgcolor='rgba(15, 23, 42, 0.9)',
        font=dict(color='white'),
        margin=dict(l=0, r=0, b=0, t=40)
    )
    return fig
