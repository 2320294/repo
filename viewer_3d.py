import plotly.graph_objects as go
import math

def gerar_visualizacao_3d(tabela_editada, pe_direito=2.80, local_qdc=None):
    """
    Gera uma figura 3D interativa com Plotly representando o ambiente,
    as caixas elétricas (tomadas, interruptores, TUEs) e o QDC nas suas respectivas alturas.
    """
    fig = go.Figure()

    ALTURAS = {
        "Tomada Baixa": 0.30,
        "Tomada Média": 0.60,
        "Interruptor": 1.10,
        "Tomada Alta / Especial": 2.00,
        "Chuveiro / TUE": 2.20,
        "QDC": 1.50
    }

    pontos_x = []
    pontos_y = []
    pontos_z = []
    textos = []
    cores = []

    qdc_x, qdc_y = 0.0, 0.0
    if isinstance(local_qdc, dict):
        qdc_x = float(local_qdc.get("x", 0.0) or 0.0)
        qdc_y = float(local_qdc.get("y", 0.0) or 0.0)
    
    pontos_x.append(qdc_x)
    pontos_y.append(qdc_y)
    pontos_z.append(ALTURAS["QDC"])
    textos.append("Quadro de Distribuição de Cargas (QDC)")
    cores.append("red")

    idx = 0
    for row in tabela_editada or []:
        ambiente = row.get("Ambiente", f"Cômodo {idx+1}")
        angulo = idx * (2 * math.pi / max(1, len(tabela_editada)))
        raio = 3.0 + (idx % 2) * 1.5
        x = raio * math.cos(angulo)
        y = raio * math.sin(angulo)

        qtd_ilum = int(row.get("Qtd Ilum.", 1) or 1)
        for i in range(qtd_ilum):
            pontos_x.append(x + (i * 0.5))
            pontos_y.append(y)
            pontos_z.append(pe_direito - 0.10)
            textos.append(f"Luminária ({ambiente})")
            cores.append("yellow")

        qtd_tugs = int(row.get("TUGs (Qtd)", 0) or 0)
        for i in range(min(qtd_tugs, 4)):
            tx = x + (1.0 if i < 2 else -1.0)
            ty = y + (1.0 if i % 2 == 0 else -1.0)
            pontos_x.append(tx)
            pontos_y.append(ty)
            pontos_z.append(ALTURAS["Tomada Baixa"])
            textos.append(f"TUG 30cm ({ambiente})")
            cores.append("blue")

        tue_nome = row.get("Equipamento TUE", "-")
        if tue_nome and tue_nome != "-":
            pontos_x.append(x)
            pontos_y.append(y + 1.2)
            z_tue = ALTURAS["Chuveiro / TUE"] if "chuveiro" in tue_nome.lower() else ALTURAS["Tomada Alta / Especial"]
            pontos_z.append(z_tue)
            cores.append("orange")
            textos.append(f"TUE: {tue_nome} ({ambiente})")

        idx += 1

    fig.add_trace(go.Scatter3d(
        x=pontos_x,
        y=pontos_y,
        z=pontos_z,
        mode='markers+text',
        marker=dict(size=8, color=cores, opacity=0.9),
        text=textos,
        textposition="top center",
        name="Dispositivos Elétricos"
    ))

    for i in range(1, len(pontos_x)):
        fig.add_trace(go.Scatter3d(
            x=[qdc_x, pontos_x[i]],
            y=[qdc_y, pontos_y[i]],
            z=[ALTURAS["QDC"], pontos_z[i]],
            mode='lines',
            line=dict(color='gray', width=2),
            showlegend=False
        ))

    fig.update_layout(
        title="<b>Visualização 3D da Instalação Elétrica</b>",
        scene=dict(
            xaxis_title="Eixo X (m)",
            yaxis_title="Eixo Y (m)",
            zaxis_title="Altura Z (m)",
            zaxis=dict(range=[0, pe_direito + 0.5]),
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=40)
    )

    return fig
