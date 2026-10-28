import plotly.graph_objects as go
import math

def gerar_visualizacao_3d_pro(tabela_editada, pe_direito=2.80, local_qdc=None, camadas=None):
    if camadas is None:
        camadas = {"paredes": True, "eletrodutos": True, "caixas": True, "qdc": True}
        
    fig = go.Figure()
    ALTURAS = {"Tomada Baixa": 0.30, "Interruptor": 1.10, "Chuveiro": 2.20, "QDC": 1.50}
    
    # 1. Paredes translúcidas (contorno da edificação em 3D)
    if camadas.get("paredes", True):
        # Caixa perímetro da residência simulada / extraída do DXF
        p_x = [-3.0, 3.0, 3.0, -3.0, -3.0]
        p_y = [-2.5, -2.5, 2.5, 2.5, -2.5]
        # Base e topo
        for z_val in [0.0, pe_direito]:
            fig.add_trace(go.Scatter3d(
                x=p_x, y=p_y, z=[z_val]*len(p_x),
                mode='lines', line=dict(color='rgba(100, 150, 255, 0.4)', width=3),
                showlegend=False
            ))
        # Pilares verticais dos cantos
        for px, py in zip([-3.0, 3.0, 3.0, -3.0], [-2.5, -2.5, 2.5, 2.5]):
            fig.add_trace(go.Scatter3d(
                x=[px, px], y=[py, py], z=[0.0, pe_direito],
                mode='lines', line=dict(color='rgba(100, 150, 255, 0.3)', width=2),
                showlegend=False
            ))

    px_pts, py_pts, pz_pts, textos, cores = [], [], [], [], []
    
    # QDC
    qx, qy = 0.0, 0.0
    if isinstance(local_qdc, dict):
        qx = float(local_qdc.get("x", 0.0) or 0.0)
        qy = float(local_qdc.get("y", 0.0) or 0.0)
        
    if camadas.get("qdc", True):
        px_pts.append(qx); py_pts.append(qy); pz_pts.append(ALTURAS["QDC"])
        textos.append("QDC (Quadro de Distribuição)"); cores.append("red")
        
    # Caixas e Eletrodutos
    for idx, row in enumerate(tabela_editada or []):
        amb = row.get("Ambiente", f"Cômodo {idx+1}")
        ang = idx * (2 * math.pi / max(1, len(tabela_editada)))
        r = 2.0 + (idx % 2) * 1.0
        x, y = r * math.cos(ang), r * math.sin(ang)
        
        # Luminária teto
        if camadas.get("caixas", True):
            px_pts.append(x); py_pts.append(y); pz_pts.append(pe_direito - 0.10)
            textos.append(f"Ponto de Luz — {amb}"); cores.append("gold")
            
        tugs = int(row.get("TUGs (Qtd)", 0) or 0)
        if tugs > 0 and camadas.get("caixas", True):
            px_pts.append(x + 0.6); py_pts.append(y + 0.6); pz_pts.append(ALTURAS["Tomada Baixa"])
            textos.append(f"Tomada 4x2 (TUG) — {amb}"); cores.append("dodgerblue")
            
        # Eletrodutos simulados subindo até o teto
        if camadas.get("eletrodutos", True) and tugs > 0:
            fig.add_trace(go.Scatter3d(
                x=[x + 0.6, x + 0.6, x], y=[y + 0.6, y + 0.6, y], z=[ALTURAS["Tomada Baixa"], pe_direito - 0.10, pe_direito - 0.10],
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
        title="<b>AutoElétrica 3D — Visualizador Profissional de Eletrodutos e Caixas</b>",
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
