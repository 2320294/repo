"""Visualização 3D inicial da arquitetura a partir do DXF (AutoElétrica 13.6.350)."""
from io import StringIO

import streamlit as st


def _normalizar_dxf_bytes(dxf_data):
    """Converte entradas compatíveis em bytes sem passar strings ao ezdxf."""
    if dxf_data is None:
        raise ValueError("O projeto não possui DXF armazenado.")
    if isinstance(dxf_data, bytes):
        raw = dxf_data
    elif isinstance(dxf_data, bytearray):
        raw = bytes(dxf_data)
    elif isinstance(dxf_data, memoryview):
        raw = dxf_data.tobytes()
    elif isinstance(dxf_data, list):
        try:
            raw = bytes(dxf_data)
        except (TypeError, ValueError) as exc:
            raise ValueError("O DXF armazenado em lista não contém bytes válidos.") from exc
    elif isinstance(dxf_data, str):
        # Compatibilidade com serializações hex do Supabase.
        txt = dxf_data.strip()
        if txt.startswith("\\x"):
            txt = txt[2:]
        try:
            raw = bytes.fromhex(txt)
        except ValueError as exc:
            raise ValueError("O DXF foi recebido como texto, mas não está em formato hexadecimal válido.") from exc
    else:
        raise TypeError(f"Tipo de DXF não suportado: {type(dxf_data).__name__}.")
    if not raw:
        raise ValueError("O conteúdo DXF está vazio.")
    return raw


def _carregar_documento(dxf_data):
    import ezdxf
    raw = _normalizar_dxf_bytes(dxf_data)
    # ezdxf.read espera um stream de texto (não BytesIO). O DXF é um formato
    # textual; decodificamos o conteúdo antes de entregá-lo ao parser.
    try:
        texto = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = raw.decode("cp1252", errors="replace")
    return ezdxf.read(StringIO(texto))


def _extrair_segmentos(modelspace):
    """Extrai segmentos XY de entidades lineares usuais do modelspace."""
    segmentos = []
    for ent in modelspace:
        kind = ent.dxftype()
        try:
            if kind == "LINE":
                a, b = ent.dxf.start, ent.dxf.end
                segmentos.append(((float(a.x), float(a.y)), (float(b.x), float(b.y))))
            elif kind == "LWPOLYLINE":
                pts = [(float(p[0]), float(p[1])) for p in ent.get_points("xy")]
                if len(pts) >= 2:
                    for i in range(len(pts) - 1):
                        segmentos.append((pts[i], pts[i + 1]))
                    if ent.closed:
                        segmentos.append((pts[-1], pts[0]))
            elif kind == "POLYLINE":
                pts = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in ent.vertices]
                if len(pts) >= 2:
                    for i in range(len(pts) - 1):
                        segmentos.append((pts[i], pts[i + 1]))
                    if ent.is_closed:
                        segmentos.append((pts[-1], pts[0]))
        except (AttributeError, TypeError, ValueError):
            # Ignora entidades com coordenadas incompatíveis, sem abortar o desenho inteiro.
            continue
    return segmentos


def renderizar_visualizacao_3d(dxf_data, pe_direito):
    st.subheader("🏗️ Visualização 3D da planta")
    st.caption(
        "Prévia tridimensional da arquitetura extraída do DXF. "
        "O pé-direito é o configurado em Parâmetros (Etapa 1); "
        "esta visualização não altera a planta original."
    )
    col_a, col_b = st.columns(2)
    with col_a:
        mostrar_piso = st.checkbox("Mostrar contornos no piso", value=True, key="ae350_3d_floor")
    with col_b:
        mostrar_topo = st.checkbox("Mostrar contornos superiores", value=True, key="ae350_3d_top")

    try:
        doc = _carregar_documento(dxf_data)
        segmentos = _extrair_segmentos(doc.modelspace())
        if not segmentos:
            st.warning("Não foram encontradas entidades LINE ou polilinhas no modelspace do DXF.")
            return

        import plotly.graph_objects as go
        fig = go.Figure()
        xs, ys = [], []
        for p1, p2 in segmentos:
            xs.extend([p1[0], p2[0], None])
            ys.extend([p1[1], p2[1], None])
        z_height = float(pe_direito)
        if z_height <= 0:
            raise ValueError("O pé-direito configurado em Parâmetros deve ser maior que zero.")

        if mostrar_piso:
            fig.add_trace(go.Scatter3d(x=xs, y=ys, z=[0 if v is not None else None for v in xs],
                                      mode="lines", name="Contornos do piso", line=dict(width=2)))
        if mostrar_topo:
            fig.add_trace(go.Scatter3d(x=xs, y=ys, z=[z_height if v is not None else None for v in xs],
                                      mode="lines", name="Contornos superiores", line=dict(width=2)))
        # Montantes verticais nas extremidades de cada segmento, formando wireframe.
        if mostrar_piso and mostrar_topo:
            vx, vy, vz = [], [], []
            for p1, p2 in segmentos:
                for p in (p1, p2):
                    vx.extend([p[0], p[0], None]); vy.extend([p[1], p[1], None]); vz.extend([0, z_height, None])
            fig.add_trace(go.Scatter3d(x=vx, y=vy, z=vz, mode="lines", name="Altura das paredes", line=dict(width=1)))

        fig.update_layout(
            height=680, margin=dict(l=0, r=0, t=30, b=0),
            scene=dict(aspectmode="data", xaxis_title="X", yaxis_title="Y", zaxis_title="Z (m)"),
            legend=dict(orientation="h"),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Pé-direito aplicado: {z_height:.2f} m | Segmentos geométricos: {len(segmentos)}")
    except Exception as exc:
        st.error(f"Falha ao montar a visualização 3D: {exc}")
