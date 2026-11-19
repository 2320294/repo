"""Visualização 3D da arquitetura a partir do DXF (AutoElétrica 13.6.362)."""
import os
import tempfile

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
    """Carrega DXF ASCII ou binário sem modificar o arquivo de origem.

    O parser oficial do ezdxf detecta a codificação e o formato binário
    quando recebe um caminho de arquivo. Em caso de estrutura danificada,
    tenta a rotina de recuperação, sempre trabalhando sobre uma cópia
    temporária dos bytes recebidos.
    """
    import ezdxf
    from ezdxf import recover

    raw = _normalizar_dxf_bytes(dxf_data)
    caminho_temporario = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="autoeletrica_3d_",
            suffix=".dxf",
            delete=False
        ) as arquivo:
            arquivo.write(raw)
            caminho_temporario = arquivo.name

        try:
            return ezdxf.readfile(caminho_temporario)
        except Exception as erro_leitura:
            try:
                documento, auditoria = recover.readfile(caminho_temporario)
                return documento
            except Exception as erro_recuperacao:
                raise ValueError(
                    "Não foi possível interpretar o DXF como arquivo ASCII "
                    "ou binário, nem recuperar sua estrutura. "
                    f"Leitura: {erro_leitura}. Recuperação: {erro_recuperacao}"
                ) from erro_recuperacao
    finally:
        if caminho_temporario and os.path.exists(caminho_temporario):
            try:
                os.remove(caminho_temporario)
            except OSError:
                pass


PREFIXO_LAYER_ELETRICO = "PROJ_ELETRICA"
LAYER_LUZ = "PROJ_ELETRICA_LUZ"
TIPOS_ILUMINACAO = ("ILUMINACAO", "ILUMINAÇÃO")

# Caixa 4x2 (retangular): nominal 4" x 2" = 101,6 x 50,8 mm. A profundidade é
# uma premissa editável (depende do fabricante) e deve ser confirmada.
CAIXA_4X2_PADRAO_MM = {"altura": 102.0, "largura": 51.0, "profundidade": 50.0}

COR_PAREDE = "#9aa5b8"
COR_ELETRODUTO = "#2e63e6"
COR_DESCIDA = "#0f9fb0"
COR_LUZ = "#f2a900"
COR_INTERRUPTOR = "#1f9d55"
COR_TOMADA = "#e0562b"
COR_QDC = "#1b2840"


def _fmt_m(valor):
    """Metros com duas casas e vírgula decimal (padrão do projeto)."""
    return f"{float(valor):.2f}".replace(".", ",")


def _extrair_geometria(modelspace):
    """Separa a arquitetura (segmentos) dos pontos de luz do DXF gerado.

    - Segmentos: LINE/LWPOLYLINE/POLYLINE fora das camadas PROJ_ELETRICA*.
    - Pontos de luz: centro do traço horizontal da cruz da camada
      PROJ_ELETRICA_LUZ (coordenada exata do ponto, em metros).
    """
    segmentos = []
    luzes = {}
    for ent in modelspace:
        kind = ent.dxftype()
        layer = str(getattr(ent.dxf, "layer", "") or "").upper()
        try:
            if layer.startswith(PREFIXO_LAYER_ELETRICO):
                if layer == LAYER_LUZ and kind == "LINE":
                    a, b = ent.dxf.start, ent.dxf.end
                    if abs(float(a.y) - float(b.y)) < 1e-9 and abs(float(a.x) - float(b.x)) > 1e-9:
                        cx = (float(a.x) + float(b.x)) / 2.0
                        luzes[(round(cx, 4), round(float(a.y), 4))] = (cx, float(a.y))
                continue
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
    return segmentos, list(luzes.values())


def _xy(ponto):
    return float(ponto[0]), float(ponto[1])


def _chave_circuito(valor):
    texto = str(valor)
    return (0, int(texto), texto) if texto.isdigit() else (1, 0, texto)


def _orientacao_parede(x, y, segmentos):
    """Direção (u) e normal (n) da parede mais próxima do ponto."""
    melhor, dist_min = None, None
    for (x1, y1), (x2, y2) in segmentos:
        dx, dy = x2 - x1, y2 - y1
        tam2 = dx * dx + dy * dy
        if tam2 <= 1e-12:
            continue
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / tam2))
        d = ((x - (x1 + t * dx)) ** 2 + (y - (y1 + t * dy)) ** 2) ** 0.5
        if dist_min is None or d < dist_min:
            tam = tam2 ** 0.5
            melhor, dist_min = (dx / tam, dy / tam), d
    u = melhor or (1.0, 0.0)
    return u, (-u[1], u[0])


def montar_modelo(segmentos, luzes, resumo, pe_direito, caixa_mm=None):
    """Monta, sem depender de Streamlit/Plotly, tudo o que a Etapa 8 exibe.

    Todas as medidas vêm do roteamento físico gerado com o CAD (mesma fonte do
    Quantitativo de Materiais): trechos horizontais, descidas/subidas
    verticais, alturas confirmadas e pontos de luz do DXF. Nada é estimado.
    """
    caixa = {**CAIXA_4X2_PADRAO_MM, **(caixa_mm or {})}
    resumo = resumo or {}
    aud = resumo.get("auditoria_vertical") or {}
    alturas_ok = bool(aud.get("aplicado"))
    params = aud.get("parametros") or {}
    percurso = params.get("percurso", "Teto") if alturas_ok else "Teto"
    pe = float(pe_direito)
    nivel = 0.0 if percurso == "Piso" else pe

    horizontais = []
    for i, rota in enumerate(resumo.get("rotas") or [], 1):
        p1, p2 = rota.get("inicio"), rota.get("fim")
        if not p1 or not p2:
            continue
        a, b = _xy(p1), _xy(p2)
        geo = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        quant = rota.get("comprimento_m")
        horizontais.append({
            "id": rota.get("trecho_id", i), "p1": a, "p2": b, "z": nivel,
            "geometrico_m": geo,
            "quantitativo_m": None if quant is None else float(quant),
            "diametro_mm": rota.get("diametro_eletroduto_mm"),
            "circuitos": sorted([str(c) for c in (rota.get("circuitos") or [])], key=_chave_circuito),
            "de": rota.get("origem_ambiente"), "para": rota.get("destino_ambiente"),
        })

    verticais, caixas, qdc = [], [], None
    vistos = set()
    if alturas_ok:
        for t in aud.get("trechos") or []:
            if not t.get("ponto"):
                continue
            x, y = _xy(t["ponto"])
            tipo = str(t.get("tipo", "")).upper()
            altura = float(t.get("altura_m", 0.0))
            verticais.append({
                "ponto": (x, y), "tipo": tipo, "altura_m": altura, "nivel_m": nivel,
                "comprimento_m": float(t.get("comprimento_m", abs(nivel - altura))),
                "diametro_mm": t.get("diametro_mm"),
            })
            if tipo == "QDC":
                qdc = {"ponto": (x, y), "altura_m": altura}
            elif tipo not in TIPOS_ILUMINACAO:
                vistos.add((round(x, 4), round(y, 4)))
                caixas.append({"tipo": tipo, "ponto": (x, y), "altura_m": altura})
        # Interruptores gerados que não apareceram nas descidas (ex.: sem cabos).
        altura_int = params.get("interruptor_m")
        for it in resumo.get("interruptores_gerados") or []:
            if not it.get("ponto") or altura_int is None:
                continue
            x, y = _xy(it["ponto"])
            if (round(x, 4), round(y, 4)) not in vistos:
                caixas.append({"tipo": "INTERRUPTOR", "ponto": (x, y), "altura_m": float(altura_int)})

    for cx in caixas:
        x, y = cx["ponto"]
        cx["u"], cx["n"] = _orientacao_parede(x, y, segmentos)

    total_h = sum((h["quantitativo_m"] if h["quantitativo_m"] is not None else h["geometrico_m"])
                  for h in horizontais)
    total_v = sum(v["comprimento_m"] for v in verticais)
    return {
        "pe_direito": pe, "nivel": nivel, "percurso": percurso, "alturas_ok": alturas_ok,
        "caixa_mm": caixa, "horizontais": horizontais, "verticais": verticais,
        "caixas": caixas, "luzes": [(float(x), float(y)) for x, y in luzes],
        "qdc": qdc, "total_horizontal_m": total_h, "total_vertical_m": total_v,
    }


def malha_caixas(caixas, caixa_mm):
    """Vértices/triângulos (Mesh3d) das caixas 4x2 na escala real, em metros."""
    larg = caixa_mm["largura"] / 1000.0
    alt = caixa_mm["altura"] / 1000.0
    prof = caixa_mm["profundidade"] / 1000.0
    X, Y, Z, I, J, K = [], [], [], [], [], []
    faces = ((0, 1, 3), (0, 3, 2), (4, 5, 7), (4, 7, 6), (0, 1, 5), (0, 5, 4),
             (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 3, 7), (1, 7, 5))
    for cx in caixas:
        x0, y0 = cx["ponto"]
        z0 = cx["altura_m"]
        u, n = cx["u"], cx["n"]
        base = len(X)
        for sz in (-1, 1):
            for sn in (-1, 1):
                for su in (-1, 1):
                    X.append(x0 + su * larg / 2 * u[0] + sn * prof / 2 * n[0])
                    Y.append(y0 + su * larg / 2 * u[1] + sn * prof / 2 * n[1])
                    Z.append(z0 + sz * alt / 2)
        for a, b, c in faces:
            I.append(base + a); J.append(base + b); K.append(base + c)
    return X, Y, Z, I, J, K


def _rotulo_tipo(tipo):
    t = str(tipo).upper()
    return {"INTERRUPTOR": "Interruptor", "TUG": "Tomada TUG", "TUE": "Tomada TUE"}.get(t, t.title())


def renderizar_visualizacao_3d(dxf_data, pe_direito, resumo_rotas=None):
    st.subheader(":material/view_in_ar: Visualização 3D da planta")
    st.caption(
        "Planta com eletrodutos, descidas verticais, pontos de iluminação e caixas 4x2. "
        "Comprimentos, diâmetros e alturas vêm do mesmo roteamento do Quantitativo de "
        "Materiais e das alturas confirmadas no projeto; a planta original não é alterada."
    )
    try:
        z_height = float(pe_direito)
        if z_height <= 0:
            raise ValueError("O pé-direito configurado em Parâmetros deve ser maior que zero.")

        doc = _carregar_documento(dxf_data)
        segmentos, luzes = _extrair_geometria(doc.modelspace())

        with st.expander("Dimensões da caixa 4x2 (mm)"):
            c1, c2, c3 = st.columns(3)
            with c1:
                alt_cx = st.number_input("Altura", min_value=10.0, value=CAIXA_4X2_PADRAO_MM["altura"],
                                         step=1.0, key="ae362_cx_altura")
            with c2:
                larg_cx = st.number_input("Largura", min_value=10.0, value=CAIXA_4X2_PADRAO_MM["largura"],
                                          step=1.0, key="ae362_cx_largura")
            with c3:
                prof_cx = st.number_input("Profundidade", min_value=10.0, value=CAIXA_4X2_PADRAO_MM["profundidade"],
                                          step=1.0, key="ae362_cx_prof")
            st.caption("Nominal 4″ × 2″ (101,6 × 50,8 mm), instalada em pé. A profundidade depende do "
                       "fabricante: confirme o valor antes de usar estas medidas em obra.")

        modelo = montar_modelo(
            segmentos, luzes, resumo_rotas, z_height,
            {"altura": alt_cx, "largura": larg_cx, "profundidade": prof_cx},
        )

        if not resumo_rotas or not modelo["horizontais"]:
            st.warning("Os dados de roteamento deste projeto não estão disponíveis. Gere o Projeto CAD "
                       "novamente na última etapa para exibir os eletrodutos.")
        elif not modelo["alturas_ok"]:
            st.warning("Alturas e percurso da instalação ainda não confirmados: os eletrodutos aparecem no "
                       "teto, mas as descidas verticais e as caixas 4x2 só são exibidas após confirmar "
                       "as alturas na etapa QDC (\"Alturas e percurso da instalação\") e gerar o CAD de novo.")

        cols = st.columns(6)
        with cols[0]:
            m_paredes = st.checkbox("Paredes", value=True, key="ae362_3d_paredes")
        with cols[1]:
            m_horiz = st.checkbox("Eletrodutos", value=True, key="ae362_3d_horiz")
        with cols[2]:
            m_vert = st.checkbox("Descidas", value=True, key="ae362_3d_vert")
        with cols[3]:
            m_luz = st.checkbox("Iluminação", value=True, key="ae362_3d_luz")
        with cols[4]:
            m_caixas = st.checkbox("Caixas 4x2", value=True, key="ae362_3d_caixas")
        with cols[5]:
            m_cotas = st.checkbox("Cotas (m)", value=True, key="ae362_3d_cotas")

        import plotly.graph_objects as go
        fig = go.Figure()

        if m_paredes and segmentos:
            xs, ys, zs_b, zs_t, vx, vy, vz = [], [], [], [], [], [], []
            for p1, p2 in segmentos:
                xs.extend([p1[0], p2[0], None]); ys.extend([p1[1], p2[1], None])
                zs_b.extend([0, 0, None]); zs_t.extend([z_height, z_height, None])
                for p in (p1, p2):
                    vx.extend([p[0], p[0], None]); vy.extend([p[1], p[1], None]); vz.extend([0, z_height, None])
            for z_lista, nome in ((zs_b, "Paredes — piso"), (zs_t, "Paredes — topo")):
                fig.add_trace(go.Scatter3d(x=xs, y=ys, z=z_lista, mode="lines", name=nome,
                                           line=dict(width=2, color=COR_PAREDE), hoverinfo="skip"))
            fig.add_trace(go.Scatter3d(x=vx, y=vy, z=vz, mode="lines", name="Altura das paredes",
                                       line=dict(width=1, color=COR_PAREDE), hoverinfo="skip",
                                       showlegend=False))

        if m_horiz and modelo["horizontais"]:
            xs, ys, zs = [], [], []
            mx, my, mz, textos, hovers = [], [], [], [], []
            for h in modelo["horizontais"]:
                (x1, y1), (x2, y2) = h["p1"], h["p2"]
                xs.extend([x1, x2, None]); ys.extend([y1, y2, None]); zs.extend([h["z"], h["z"], None])
                comp = h["quantitativo_m"] if h["quantitativo_m"] is not None else h["geometrico_m"]
                diam = f' Ø{int(h["diametro_mm"])} mm' if h["diametro_mm"] else ""
                mx.append((x1 + x2) / 2); my.append((y1 + y2) / 2); mz.append(h["z"])
                textos.append(f"{_fmt_m(comp)} m{diam}" if m_cotas else "")
                hovers.append(
                    f"Trecho {h['id']}<br>Comprimento: {_fmt_m(comp)} m"
                    f"<br>Eletroduto:{diam or ' —'}<br>Circuitos: {', '.join(h['circuitos']) or '—'}"
                    f"<br>{h['de'] or '—'} → {h['para'] or '—'}"
                )
            fig.add_trace(go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", name="Eletrodutos (horizontal)",
                                       line=dict(width=6, color=COR_ELETRODUTO), hoverinfo="skip"))
            fig.add_trace(go.Scatter3d(x=mx, y=my, z=mz, mode="markers+text", text=textos,
                                       textposition="top center", textfont=dict(size=10, color=COR_ELETRODUTO),
                                       marker=dict(size=3, color=COR_ELETRODUTO), hovertext=hovers,
                                       hoverinfo="text", name="Trechos", showlegend=False))

        if m_vert and modelo["verticais"]:
            xs, ys, zs = [], [], []
            mx, my, mz, textos, hovers = [], [], [], [], []
            for v in modelo["verticais"]:
                x, y = v["ponto"]
                xs.extend([x, x, None]); ys.extend([y, y, None]); zs.extend([v["nivel_m"], v["altura_m"], None])
                diam = f' Ø{int(v["diametro_mm"])} mm' if v["diametro_mm"] else ""
                mx.append(x); my.append(y); mz.append((v["nivel_m"] + v["altura_m"]) / 2)
                textos.append(f"{_fmt_m(v['comprimento_m'])} m" if m_cotas else "")
                hovers.append(f"{_rotulo_tipo(v['tipo'])}<br>Altura do ponto: {_fmt_m(v['altura_m'])} m"
                              f"<br>Descida: {_fmt_m(v['comprimento_m'])} m<br>Eletroduto:{diam or ' —'}")
            fig.add_trace(go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", name="Descidas verticais",
                                       line=dict(width=5, color=COR_DESCIDA), hoverinfo="skip"))
            fig.add_trace(go.Scatter3d(x=mx, y=my, z=mz, mode="markers+text", text=textos,
                                       textposition="middle right", textfont=dict(size=10, color=COR_DESCIDA),
                                       marker=dict(size=3, color=COR_DESCIDA), hovertext=hovers,
                                       hoverinfo="text", name="Descidas", showlegend=False))

        if m_luz and modelo["luzes"]:
            fig.add_trace(go.Scatter3d(
                x=[p[0] for p in modelo["luzes"]], y=[p[1] for p in modelo["luzes"]],
                z=[z_height] * len(modelo["luzes"]), mode="markers", name="Pontos de iluminação",
                marker=dict(size=6, color=COR_LUZ, symbol="circle", line=dict(width=1, color="#7a5600")),
                hovertext=[f"Ponto de iluminação<br>Altura: {_fmt_m(z_height)} m<br>X {p[0]:.3f} · Y {p[1]:.3f}"
                           for p in modelo["luzes"]], hoverinfo="text"))

        if m_caixas and modelo["caixas"]:
            X, Y, Z, I, J, K = malha_caixas(modelo["caixas"], modelo["caixa_mm"])
            fig.add_trace(go.Mesh3d(x=X, y=Y, z=Z, i=I, j=J, k=K, color=COR_TOMADA, opacity=1.0,
                                    name="Caixas 4x2 (escala real)", hoverinfo="skip", showlegend=True))
            cm = modelo["caixa_mm"]
            fig.add_trace(go.Scatter3d(
                x=[c["ponto"][0] for c in modelo["caixas"]], y=[c["ponto"][1] for c in modelo["caixas"]],
                z=[c["altura_m"] for c in modelo["caixas"]], mode="markers", name="Caixas 4x2",
                marker=dict(size=5, symbol="diamond",
                            color=[COR_INTERRUPTOR if c["tipo"] == "INTERRUPTOR" else COR_TOMADA
                                   for c in modelo["caixas"]]),
                hovertext=[f"Caixa 4x2 — {_rotulo_tipo(c['tipo'])}<br>Altura (centro): {_fmt_m(c['altura_m'])} m"
                           f"<br>{cm['altura']:.0f} × {cm['largura']:.0f} × {cm['profundidade']:.0f} mm"
                           for c in modelo["caixas"]], hoverinfo="text"))

        if modelo["qdc"]:
            q = modelo["qdc"]
            fig.add_trace(go.Scatter3d(x=[q["ponto"][0]], y=[q["ponto"][1]], z=[q["altura_m"]], mode="markers",
                                       name="QDC (entrada dos eletrodutos)",
                                       marker=dict(size=8, color=COR_QDC, symbol="square"),
                                       hovertext=[f"QDC<br>Entrada dos eletrodutos: {_fmt_m(q['altura_m'])} m"],
                                       hoverinfo="text"))

        fig.update_layout(
            height=680, margin=dict(l=0, r=0, t=30, b=0),
            scene=dict(aspectmode="data", xaxis_title="X (m)", yaxis_title="Y (m)", zaxis_title="Z (m)"),
            legend=dict(orientation="h"),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            f"Pé-direito: {_fmt_m(z_height)} m | Percurso horizontal: "
            f"{'teto' if modelo['percurso'] != 'Piso' else 'piso'} ({_fmt_m(modelo['nivel'])} m). "
            "A espessura das linhas é ilustrativa; as caixas 4x2 estão na escala real."
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Eletroduto horizontal", f"{_fmt_m(modelo['total_horizontal_m'])} m")
        m2.metric("Descidas verticais", f"{_fmt_m(modelo['total_vertical_m'])} m")
        m3.metric("Caixas 4x2", len(modelo["caixas"]))
        m4.metric("Pontos de iluminação", len(modelo["luzes"]))

        aba_h, aba_v, aba_c = st.tabs(["Trechos horizontais", "Descidas verticais", "Caixas 4x2"])
        with aba_h:
            st.dataframe([
                {"Trecho": h["id"], "De": h["de"], "Para": h["para"],
                 "Ø (mm)": h["diametro_mm"], "Circuitos": ", ".join(h["circuitos"]),
                 "Comprimento (m)": round(h["quantitativo_m"] if h["quantitativo_m"] is not None else h["geometrico_m"], 2),
                 "Geométrico (m)": round(h["geometrico_m"], 3)}
                for h in modelo["horizontais"]], use_container_width=True, hide_index=True)
        with aba_v:
            st.dataframe([
                {"Ponto": _rotulo_tipo(v["tipo"]), "X (m)": round(v["ponto"][0], 3), "Y (m)": round(v["ponto"][1], 3),
                 "Altura (m)": round(v["altura_m"], 2), "Descida (m)": round(v["comprimento_m"], 2),
                 "Ø (mm)": v["diametro_mm"]}
                for v in modelo["verticais"]], use_container_width=True, hide_index=True)
        with aba_c:
            cm = modelo["caixa_mm"]
            st.dataframe([
                {"Uso": _rotulo_tipo(c["tipo"]), "X (m)": round(c["ponto"][0], 3), "Y (m)": round(c["ponto"][1], 3),
                 "Altura do centro (m)": round(c["altura_m"], 2),
                 "Caixa (mm)": f"{cm['altura']:.0f} × {cm['largura']:.0f} × {cm['profundidade']:.0f}"}
                for c in modelo["caixas"]], use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error(f"Falha ao montar a visualização 3D: {exc}")
