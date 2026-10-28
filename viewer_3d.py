import plotly.graph_objects as go
import math

def gerar_visualizacao_3d(tabela_editada, pe_direito=2.80, local_qdc=None):
    fig = go.Figure()
    ALTURAS = {"Tomada Baixa": 0.30, "Interruptor": 1.10, "Chuveiro": 2.20, "QDC": 1.50}
    px, py, pz, textos, cores = [], [], [], [], []
    
    qx, qy = 0.0, 0.0
    if isinstance(local_qdc, dict):
        qx = float(local_qdc.get("x", 0.0) or 0.0)
        qy = float(local_qdc.get("y", 0.0) or 0.0)
    
    px.append(qx); py.append(qy); pz.append(ALTURAS["QDC"]); textos.append("Quadro de Distribuição (QDC)"); cores.append("red")
    
    for idx, row in enumerate(tabela_editada or []):
        amb = row.get("Ambiente", f"Cômodo {idx+1}")
        ang = idx * (2 * math.pi / max(1, len(tabela_editada)))
        r = 3.0 + (idx % 2) * 1.5
        x, y = r * math.cos(ang), r * math.sin(ang)
        
        px.append(x); py.append(y); pz.append(pe_direito - 0.10); textos.append(f"Iluminação ({amb})"); cores.append("yellow")
        tugs = int(row.get("TUGs (Qtd)", 0) or 0)
        if tugs > 0:
            px.append(x + 0.8); py.append(y + 0.8); pz.append(ALTURAS["Tomada Baixa"]); textos.append(f"TUG ({amb})"); cores.append("blue")
            
    fig.add_trace(go.Scatter3d(x=px, y=py, z=pz, mode='markers+text', marker=dict(size=8, color=cores), text=textos, textposition="top center"))
    fig.update_layout(title="<b>Visualização 3D da Instalação Elétrica</b>", scene=dict(zaxis=dict(range=[0, pe_direito + 0.5]), aspectmode='data'))
    return fig
