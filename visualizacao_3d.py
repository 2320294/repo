"""Visualização 3D da arquitetura a partir do DXF (AutoElétrica 13.6.364)."""
import math
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
LAYER_ROTEAMENTO = "PROJ_ELETRICA_ROTEAMENTO"  # percurso real dos eletrodutos (ARC/LWPOLYLINE)
LAYER_ELETRODUTO = "PROJ_ELETRICA_ELETRODUTO"    # traçado antigo em LINE (reserva)
LAYER_COMANDO = "PROJ_ELETRICA_COMANDO"          # interruptor -> luz
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
COR_COMANDO = "#8a5cf6"

# Tolerâncias para casar extremidades do desenho com pontos (m).
TOL_PONTO_M = 0.45   # tomada/interruptor
TOL_LUZ_M = 0.45     # ponto de luz (o desenho para na borda do símbolo)

COR_DIAMETRO = {16: "#5a93ff", 20: "#2e63e6", 25: "#1f45b8", 32: "#122d80"}
LARG_DIAMETRO = {16: 4, 20: 5, 25: 6, 32: 7}


def _fmt_m(valor):
    """Metros com duas casas e vírgula decimal (padrão do projeto)."""
    return f"{float(valor):.2f}".replace(".", ",")


def _pontos_entidade(ent):
    """Pontos XY (em ordem) do percurso desenhado por uma entidade do CAD."""
    kind = ent.dxftype()
    if kind == "LINE":
        a, b = ent.dxf.start, ent.dxf.end
        return [(float(a.x), float(a.y)), (float(b.x), float(b.y))]
    if kind == "LWPOLYLINE":
        pts = [(float(p[0]), float(p[1])) for p in ent.get_points("xy")]
        if ent.closed and len(pts) >= 2:
            pts.append(pts[0])
        return pts
    if kind == "POLYLINE":
        pts = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in ent.vertices]
        if ent.is_closed and len(pts) >= 2:
            pts.append(pts[0])
        return pts
    if kind == "ARC":
        c = ent.dxf.center
        r = float(ent.dxf.radius)
        ini = float(ent.dxf.start_angle)
        fim = float(ent.dxf.end_angle)
        while fim <= ini:
            fim += 360.0
        passos = max(8, int(math.ceil((fim - ini) / 4.0)))
        return [
            (float(c.x) + r * math.cos(math.radians(ini + (fim - ini) * k / passos)),
             float(c.y) + r * math.sin(math.radians(ini + (fim - ini) * k / passos)))
            for k in range(passos + 1)
        ]
    return []


def _extrair_geometria(modelspace):
    """Separa do DXF gerado: arquitetura, pontos de luz e o percurso real.

    - Segmentos: LINE/LWPOLYLINE/POLYLINE fora das camadas PROJ_ELETRICA*.
    - Pontos de luz: centro do traço horizontal da cruz da camada
      PROJ_ELETRICA_LUZ (coordenada exata do ponto, em metros).
    - Eletrodutos: as MESMAS entidades desenhadas no projeto, na camada
      PROJ_ELETRICA_ROTEAMENTO (arcos e polilinhas que correm pelo eixo das
      paredes), com todos os vértices; reserva: LINEs de PROJ_ELETRICA_ELETRODUTO.
    - Comandos: linhas interruptor -> luz (PROJ_ELETRICA_COMANDO).
    """
    segmentos = []
    luzes = {}
    condutos, condutos_reserva, comandos = [], [], []
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
                elif layer == LAYER_ROTEAMENTO:
                    pts = _pontos_entidade(ent)
                    if len(pts) >= 2:
                        condutos.append({"tipo": kind, "pontos": pts})
                elif layer == LAYER_ELETRODUTO and kind == "LINE":
                    pts = _pontos_entidade(ent)
                    if len(pts) >= 2:
                        condutos_reserva.append({"tipo": kind, "pontos": pts})
                elif layer == LAYER_COMANDO and kind == "LINE":
                    pts = _pontos_entidade(ent)
                    if len(pts) >= 2:
                        comandos.append(pts)
                continue
            if kind in ("LINE", "LWPOLYLINE", "POLYLINE"):
                pts = _pontos_entidade(ent)
                for i in range(len(pts) - 1):
                    segmentos.append((pts[i], pts[i + 1]))
        except (AttributeError, TypeError, ValueError):
            # Ignora entidades com coordenadas incompatíveis, sem abortar o desenho inteiro.
            continue
    return segmentos, list(luzes.values()), (condutos or condutos_reserva), comandos


def _xy(ponto):
    return float(ponto[0]), float(ponto[1])


def _chave_circuito(valor):
    texto = str(valor)
    return (0, int(texto), texto) if texto.isdigit() else (1, 0, texto)


def _no_mais_proximo(ponto, nos, tolerancia_m):
    """Nó (x, y, ...) mais próximo do ponto dentro da tolerância, ou None."""
    melhor, dmin = None, None
    for no in nos:
        d = math.hypot(no[0] - ponto[0], no[1] - ponto[1])
        if d <= tolerancia_m and (dmin is None or d < dmin):
            melhor, dmin = no, d
    return melhor


def malha_paredes(segmentos, altura, comprimento_min=0.10, limite=8000):
    """Painéis verticais (Mesh3d) das paredes; segmentos duplicados são unidos."""
    unicos = {}
    for (x1, y1), (x2, y2) in segmentos:
        comp = math.hypot(x2 - x1, y2 - y1)
        if comp < comprimento_min:
            continue
        a, b = (round(x1, 3), round(y1, 3)), (round(x2, 3), round(y2, 3))
        unicos[(min(a, b), max(a, b))] = comp
    chaves = sorted(unicos, key=lambda k: -unicos[k])[:limite]
    X, Y, Z, I, J, K = [], [], [], [], [], []
    for (a, b) in chaves:
        base = len(X)
        X += [a[0], b[0], b[0], a[0]]
        Y += [a[1], b[1], b[1], a[1]]
        Z += [0.0, 0.0, altura, altura]
        I += [base, base]; J += [base + 1, base + 2]; K += [base + 2, base + 3]
    return X, Y, Z, I, J, K


def retangulo_piso(segmentos, folga=0.3):
    """Retângulo (x0, y0, x1, y1) que envolve a arquitetura, ou None."""
    if not segmentos:
        return None
    xs = [p[0] for seg in segmentos for p in seg]
    ys = [p[1] for seg in segmentos for p in seg]
    return (min(xs) - folga, min(ys) - folga, max(xs) + folga, max(ys) + folga)


def comprimento_percurso(pontos):
    return sum(math.hypot(pontos[i + 1][0] - pontos[i][0], pontos[i + 1][1] - pontos[i][1])
               for i in range(len(pontos) - 1))


def ponto_no_meio(pontos):
    """Ponto situado na metade do comprimento do percurso (para a cota)."""
    total = comprimento_percurso(pontos)
    alvo, acum = total / 2.0, 0.0
    for i in range(len(pontos) - 1):
        seg = math.hypot(pontos[i + 1][0] - pontos[i][0], pontos[i + 1][1] - pontos[i][1])
        if seg > 0 and acum + seg >= alvo:
            t = (alvo - acum) / seg
            return (pontos[i][0] + t * (pontos[i + 1][0] - pontos[i][0]),
                    pontos[i][1] + t * (pontos[i + 1][1] - pontos[i][1]))
        acum += seg
    return pontos[0]


def _casar_condutos_rotas(condutos, rotas, tolerancia_m=0.8):
    """Associa cada eletroduto desenhado à rota do quantitativo (1 para 1).

    O critério é a soma das distâncias entre as extremidades do desenho e o
    início/fim da rota (nos dois sentidos), aceita até a tolerância.
    """
    candidatos = []
    for i, c in enumerate(condutos):
        a, b = c["pontos"][0], c["pontos"][-1]
        for j, r in enumerate(rotas):
            if not r.get("inicio") or not r.get("fim"):
                continue
            p, q = _xy(r["inicio"]), _xy(r["fim"])
            d1 = math.hypot(a[0] - p[0], a[1] - p[1]) + math.hypot(b[0] - q[0], b[1] - q[1])
            d2 = math.hypot(a[0] - q[0], a[1] - q[1]) + math.hypot(b[0] - p[0], b[1] - p[1])
            custo = min(d1, d2)
            if custo <= tolerancia_m:
                candidatos.append((custo, i, j))
    candidatos.sort()
    usados_c, usados_r, par = set(), set(), {}
    for custo, i, j in candidatos:
        if i in usados_c or j in usados_r:
            continue
        usados_c.add(i); usados_r.add(j); par[i] = j
    return par


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


def montar_modelo(segmentos, luzes, resumo, pe_direito, caixa_mm=None, condutos=None, comandos=None):
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

    rotas = resumo.get("rotas") or []
    horizontais = []

    def _dados_rota(rota, i):
        quant = rota.get("comprimento_m")
        return {
            "id": rota.get("trecho_id", i),
            "quantitativo_m": None if quant is None else float(quant),
            "diametro_mm": rota.get("diametro_eletroduto_mm"),
            "circuitos": sorted([str(c) for c in (rota.get("circuitos") or [])], key=_chave_circuito),
            "de": rota.get("origem_ambiente"), "para": rota.get("destino_ambiente"),
        }

    if condutos:
        # Percurso EXATO desenhado no projeto (arcos e polilinhas pelas paredes).
        par = _casar_condutos_rotas(condutos, rotas)
        for i, c in enumerate(condutos):
            item = {"id": "—", "quantitativo_m": None, "diametro_mm": None,
                    "circuitos": [], "de": None, "para": None}
            if i in par:
                item.update(_dados_rota(rotas[par[i]], par[i] + 1))
            item.update({
                "pontos": c["pontos"], "z": nivel, "desenho": c["tipo"],
                "geometrico_m": comprimento_percurso(c["pontos"]),
            })
            horizontais.append(item)
    else:
        # Sem o desenho do projeto: usa as rotas do quantitativo (retas entre caixas).
        for i, rota in enumerate(rotas, 1):
            p1, p2 = rota.get("inicio"), rota.get("fim")
            if not p1 or not p2:
                continue
            pts = [_xy(p1), _xy(p2)]
            item = _dados_rota(rota, i)
            item.update({"pontos": pts, "z": nivel, "desenho": "RETA",
                         "geometrico_m": comprimento_percurso(pts)})
            horizontais.append(item)

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

    # Altura de cada trecho e ligação aos pontos de luz --------------------
    # - Trechos que correm pelas paredes ficam na altura da(s) tomada(s) a que
    #   pertencem (extremidades casadas com os pontos de tomada/interruptor).
    # - Trechos no teto chegam até o centro do ponto de iluminação (o desenho
    #   do CAD termina na borda do símbolo).
    nos_altura = [(c["ponto"][0], c["ponto"][1], c["altura_m"]) for c in caixas]
    luzes_xy = [(float(x), float(y)) for x, y in luzes]
    for h in horizontais:
        pts = list(h["pontos"])
        z_h, z_fim = nivel, None
        if alturas_ok and str(h["desenho"]).upper() in ("LWPOLYLINE", "POLYLINE"):
            no_a = _no_mais_proximo(pts[0], nos_altura, TOL_PONTO_M)
            no_b = _no_mais_proximo(pts[-1], nos_altura, TOL_PONTO_M)
            if no_a is not None or no_b is not None:
                z_h = no_a[2] if no_a is not None else no_b[2]
                if no_a is not None and no_b is not None:
                    z_fim = no_b[2]
        p3 = [(px, py, z_h) for px, py in pts]
        if z_fim is not None and abs(z_fim - z_h) > 1e-6:
            p3.append((pts[-1][0], pts[-1][1], z_fim))
        else:
            z_fim = None
        if abs(z_h - pe) < 1e-6:
            luz_a = _no_mais_proximo(pts[0], luzes_xy, TOL_LUZ_M)
            if luz_a is not None and math.hypot(luz_a[0] - pts[0][0], luz_a[1] - pts[0][1]) > 1e-6:
                p3.insert(0, (luz_a[0], luz_a[1], pe))
            if z_fim is None:
                luz_b = _no_mais_proximo(pts[-1], luzes_xy, TOL_LUZ_M)
                if luz_b is not None and math.hypot(luz_b[0] - pts[-1][0], luz_b[1] - pts[-1][1]) > 1e-6:
                    p3.append((luz_b[0], luz_b[1], pe))
        h["pontos3d"], h["z"], h["altura_fim_m"] = p3, z_h, z_fim

    total_desenhado = sum(h["geometrico_m"] for h in horizontais)
    if rotas:
        # Mesma soma do Quantitativo de Materiais.
        total_h = sum(float(r.get("comprimento_m") or 0.0) for r in rotas)
    else:
        total_h = total_desenhado
    total_v = sum(v["comprimento_m"] for v in verticais)
    return {
        "pe_direito": pe, "nivel": nivel, "percurso": percurso, "alturas_ok": alturas_ok,
        "caixa_mm": caixa, "horizontais": horizontais, "verticais": verticais,
        "caixas": caixas, "luzes": [(float(x), float(y)) for x, y in luzes],
        "qdc": qdc, "total_horizontal_m": total_h, "total_desenhado_m": total_desenhado,
        "total_vertical_m": total_v,
        "comandos": [list(c) for c in (comandos or [])],
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


def _rotulo_desenho(tipo):
    return {"LWPOLYLINE": "pela parede", "ARC": "arco", "LINE": "reta", "RETA": "reta",
            "POLYLINE": "pela parede"}.get(str(tipo).upper(), str(tipo).lower())


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
        segmentos, luzes, condutos, comandos = _extrair_geometria(doc.modelspace())

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
            condutos=condutos, comandos=comandos,
        )

        if not modelo["horizontais"]:
            st.warning("Os dados de roteamento deste projeto não estão disponíveis. Gere o Projeto CAD "
                       "novamente na última etapa para exibir os eletrodutos.")
        elif not modelo["alturas_ok"]:
            st.warning("Alturas e percurso da instalação ainda não confirmados: os eletrodutos aparecem no "
                       "teto, mas as descidas verticais e as caixas 4x2 só são exibidas após confirmar "
                       "as alturas na etapa QDC (\"Alturas e percurso da instalação\") e gerar o CAD de novo.")

        cols = st.columns(7)
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
            m_comando = st.checkbox("Comandos", value=True, key="ae362_3d_comando")
        with cols[6]:
            m_cotas = st.checkbox("Cotas (m)", value=True, key="ae362_3d_cotas")
        opac = st.slider("Opacidade das paredes", min_value=0.04, max_value=0.60, value=0.14,
                         step=0.02, key="ae364_3d_opac",
                         help="Quanto menor, mais transparentes ficam as paredes e melhor se vê a instalação.")

        import plotly.graph_objects as go
        fig = go.Figure()

        if m_paredes and segmentos:
            X, Y, Z, I, J, K = malha_paredes(segmentos, z_height)
            if X:
                fig.add_trace(go.Mesh3d(x=X, y=Y, z=Z, i=I, j=J, k=K, color="#8ea4c7", opacity=opac,
                                        flatshading=True, name="Paredes", showlegend=True, hoverinfo="skip",
                                        lighting=dict(ambient=0.85, diffuse=0.35, specular=0.05)))
            piso = retangulo_piso(segmentos)
            if piso:
                x0, y0, x1, y1 = piso
                fig.add_trace(go.Mesh3d(x=[x0, x1, x1, x0], y=[y0, y0, y1, y1], z=[0, 0, 0, 0],
                                        i=[0, 0], j=[1, 2], k=[2, 3], color="#dbe3f1", opacity=0.35,
                                        name="Piso", showlegend=True, hoverinfo="skip"))
            bx, by, tz, bz = [], [], [], []
            for p1, p2 in segmentos:
                if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) < 0.10:
                    continue
                bx.extend([p1[0], p2[0], None]); by.extend([p1[1], p2[1], None])
            if bx:
                for zc in (0.0, z_height):
                    fig.add_trace(go.Scatter3d(x=bx, y=by, z=[None if v is None else zc for v in bx],
                                               mode="lines", line=dict(width=1.5, color="#6f84a6"),
                                               hoverinfo="skip", showlegend=False))

        if m_horiz and modelo["horizontais"]:
            grupos = {}
            for h in modelo["horizontais"]:
                grupos.setdefault(h["diametro_mm"], []).append(h)
            mx, my, mz, textos, hovers = [], [], [], [], []
            for diam in sorted(grupos, key=lambda d: (d is None, d or 0)):
                xs, ys, zs = [], [], []
                for h in grupos[diam]:
                    for (px, py, pz) in h["pontos3d"]:
                        xs.append(px); ys.append(py); zs.append(pz)
                    xs.append(None); ys.append(None); zs.append(None)
                    comp = h["quantitativo_m"] if h["quantitativo_m"] is not None else h["geometrico_m"]
                    d_txt = f' Ø{int(h["diametro_mm"])} mm' if h["diametro_mm"] else ""
                    meio = ponto_no_meio(h["pontos"])
                    mx.append(meio[0]); my.append(meio[1]); mz.append(h["z"])
                    textos.append(f"{_fmt_m(comp)} m{d_txt}" if m_cotas else "")
                    alt_txt = (f"<br>Altura do traçado: {_fmt_m(h['z'])} m"
                               if abs(h["z"] - modelo["nivel"]) > 1e-6 else "")
                    hovers.append(
                        f"Trecho {h['id']} ({_rotulo_desenho(h['desenho'])})"
                        f"<br>Comprimento: {_fmt_m(comp)} m (desenhado: {_fmt_m(h['geometrico_m'])} m)"
                        f"<br>Eletroduto:{d_txt or ' —'}{alt_txt}"
                        f"<br>Circuitos: {', '.join(h['circuitos']) or '—'}"
                        f"<br>{h['de'] or '—'} → {h['para'] or '—'}"
                    )
                d_int = int(diam) if diam else None
                fig.add_trace(go.Scatter3d(
                    x=xs, y=ys, z=zs, mode="lines",
                    name=f"Eletroduto Ø{d_int} mm" if d_int else "Eletroduto",
                    line=dict(width=LARG_DIAMETRO.get(d_int, 5), color=COR_DIAMETRO.get(d_int, COR_ELETRODUTO)),
                    hoverinfo="skip"))
            fig.add_trace(go.Scatter3d(x=mx, y=my, z=mz, mode="markers+text", text=textos,
                                       textposition="top center", textfont=dict(size=10, color="#1f45b8"),
                                       marker=dict(size=3, color="#1f45b8"), hovertext=hovers,
                                       hoverinfo="text", name="Trechos", showlegend=False))

        if m_comando and modelo["comandos"]:
            xs, ys, zs = [], [], []
            for pts in modelo["comandos"]:
                for (px, py) in pts:
                    xs.append(px); ys.append(py); zs.append(modelo["nivel"])
                xs.append(None); ys.append(None); zs.append(None)
            fig.add_trace(go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", name="Comandos (interruptor → luz)",
                                       line=dict(width=3, color=COR_COMANDO, dash="dash"), hoverinfo="skip"))

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
                                       line=dict(width=4, color=COR_DESCIDA), hoverinfo="skip"))
            fig.add_trace(go.Scatter3d(x=mx, y=my, z=mz, mode="markers+text", text=textos,
                                       textposition="middle right", textfont=dict(size=10, color=COR_DESCIDA),
                                       marker=dict(size=3, color=COR_DESCIDA), hovertext=hovers,
                                       hoverinfo="text", name="Descidas", showlegend=False))

        if m_luz and modelo["luzes"]:
            fig.add_trace(go.Scatter3d(
                x=[p[0] for p in modelo["luzes"]], y=[p[1] for p in modelo["luzes"]],
                z=[z_height] * len(modelo["luzes"]), mode="markers", name="Pontos de iluminação",
                marker=dict(size=8, color=COR_LUZ, symbol="circle", line=dict(width=2, color="#ffffff")),
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
                marker=dict(size=5, symbol="diamond", line=dict(width=1, color="#ffffff"),
                            color=[COR_INTERRUPTOR if c["tipo"] == "INTERRUPTOR" else COR_TOMADA
                                   for c in modelo["caixas"]]),
                hovertext=[f"Caixa 4x2 — {_rotulo_tipo(c['tipo'])}<br>Altura (centro): {_fmt_m(c['altura_m'])} m"
                           f"<br>{cm['altura']:.0f} × {cm['largura']:.0f} × {cm['profundidade']:.0f} mm"
                           for c in modelo["caixas"]], hoverinfo="text"))

        if modelo["qdc"]:
            q = modelo["qdc"]
            fig.add_trace(go.Scatter3d(x=[q["ponto"][0]], y=[q["ponto"][1]], z=[q["altura_m"]], mode="markers",
                                       name="QDC (entrada dos eletrodutos)",
                                       marker=dict(size=9, color=COR_QDC, symbol="square",
                                                   line=dict(width=1, color="#ffffff")),
                                       hovertext=[f"QDC<br>Entrada dos eletrodutos: {_fmt_m(q['altura_m'])} m"],
                                       hoverinfo="text"))

        eixo = dict(showbackground=False, showgrid=True, gridcolor="#dde4f0", zeroline=False,
                    showspikes=False, color="#667389", tickfont=dict(size=10))
        fig.update_layout(
            height=720, margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, Segoe UI, Roboto, sans-serif", color="#1b2840"),
            hoverlabel=dict(bgcolor="#1b2840", font=dict(color="#ffffff", size=12)),
            legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                        bgcolor="rgba(255,255,255,.75)", font=dict(size=11)),
            scene=dict(aspectmode="data", bgcolor="#f4f7fc",
                       xaxis=dict(title="X (m)", **eixo), yaxis=dict(title="Y (m)", **eixo),
                       zaxis=dict(title="Z (m)", **eixo),
                       camera=dict(eye=dict(x=1.45, y=-1.65, z=0.95))),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            f"Pé-direito: {_fmt_m(z_height)} m | Percurso horizontal: "
            f"{'teto' if modelo['percurso'] != 'Piso' else 'piso'} ({_fmt_m(modelo['nivel'])} m). "
            "A espessura das linhas é ilustrativa; as caixas 4x2 estão na escala real. "
            "Trechos que correm pelas paredes ficam na altura das tomadas a que pertencem."
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Eletroduto horizontal", f"{_fmt_m(modelo['total_horizontal_m'])} m",
                   help=f"Soma do Quantitativo de Materiais. Percurso desenhado no CAD: {_fmt_m(modelo['total_desenhado_m'])} m.")
        m2.metric("Descidas verticais", f"{_fmt_m(modelo['total_vertical_m'])} m")
        m3.metric("Caixas 4x2", len(modelo["caixas"]))
        m4.metric("Pontos de iluminação", len(modelo["luzes"]))

        aba_h, aba_v, aba_c = st.tabs(["Trechos horizontais", "Descidas verticais", "Caixas 4x2"])
        with aba_h:
            st.dataframe([
                {"Trecho": h["id"], "Percurso": _rotulo_desenho(h["desenho"]),
                 "De": h["de"], "Para": h["para"],
                 "Ø (mm)": h["diametro_mm"], "Circuitos": ", ".join(h["circuitos"]),
                 "Altura (m)": round(h["z"], 2),
                 "Comprimento (m)": round(h["quantitativo_m"] if h["quantitativo_m"] is not None else h["geometrico_m"], 2),
                 "Desenhado (m)": round(h["geometrico_m"], 3)}
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
