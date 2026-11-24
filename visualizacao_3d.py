"""Visualização 3D da arquitetura a partir do DXF (AutoElétrica 13.6.367)."""
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
TOL_QDC_M = 0.60     # eletrodutos que saem do QDC
TOL_INT_TOMADA_M = 0.60  # tomada vizinha a um interruptor (alimentada por ele)

# QDC desenhado como caixa: cresce conforme o número de eletrodutos, para que
# cada um tenha sua própria saída (sem sobreposição). Parâmetros fixos do sistema.
QDC_LARGURA_MIN_M = 0.40
QDC_ALTURA_CAIXA_M = 0.50
QDC_PROF_M = 0.12
QDC_ESPACAMENTO_M = 0.06   # distância entre eletrodutos vizinhos na saída do QDC

# Parâmetro fixo do sistema: altura livre do vão de porta (sem parede abaixo dela).
ALTURA_VAO_PORTA_M = 2.10
LAYER_PORTAS = "IA_PORTAS"      # folha/giro da porta: não é parede
LAYER_SOLEIRAS = "IA_SOLEIRAS"  # vão de porta (soleira)

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
    - Soleiras (vãos de porta, IA_SOLEIRAS) ficam à parte; a camada IA_PORTAS
      (folha da porta) não entra como parede.
    """
    segmentos = []
    luzes = {}
    condutos, condutos_reserva, comandos, soleiras = [], [], [], []
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
            if layer == LAYER_PORTAS:
                continue
            if layer == LAYER_SOLEIRAS:
                pts = _pontos_entidade(ent)
                if len(pts) >= 2:
                    soleiras.append(pts)
                continue
            if kind in ("LINE", "LWPOLYLINE", "POLYLINE"):
                pts = _pontos_entidade(ent)
                for i in range(len(pts) - 1):
                    segmentos.append((pts[i], pts[i + 1]))
        except (AttributeError, TypeError, ValueError):
            # Ignora entidades com coordenadas incompatíveis, sem abortar o desenho inteiro.
            continue
    return segmentos, list(luzes.values()), (condutos or condutos_reserva), comandos, soleiras


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


def _retangulo_vao(pontos):
    """Retângulo orientado (4 cantos, anti-horário) que cobre o vão da soleira.

    Cobre o comprimento do vão e a espessura da parede (a soleira pode ser uma
    simples linha); serve para recortar a parede abaixo da altura do vão.
    """
    pts = []
    for x, y in pontos:
        q = (float(x), float(y))
        if not pts or math.hypot(q[0] - pts[-1][0], q[1] - pts[-1][1]) > 1e-6:
            pts.append(q)
    if len(pts) < 2:
        return None
    # Direção do vão: a maior aresta do desenho da soleira.
    arestas = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    if len(pts) >= 3:
        arestas.append((pts[-1], pts[0]))
    p0, p1 = max(arestas, key=lambda e: math.hypot(e[1][0] - e[0][0], e[1][1] - e[0][1]))
    comp = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    if comp < 1e-6:
        return None
    ux, uy = (p1[0] - p0[0]) / comp, (p1[1] - p0[1]) / comp
    nx, ny = -uy, ux
    pu = [(q[0] - p0[0]) * ux + (q[1] - p0[1]) * uy for q in pts]
    pn = [(q[0] - p0[0]) * nx + (q[1] - p0[1]) * ny for q in pts]
    t0, t1 = min(pu), max(pu)  # o vão tem exatamente a largura da soleira
    espessura = max(pn) - min(pn)
    meio = (max(pn) + min(pn)) / 2.0
    meia = max(espessura / 2.0 + 0.03, 0.22)

    def canto(t, n):
        return (p0[0] + ux * t + nx * n, p0[1] + uy * t + ny * n)

    return [canto(t0, meio - meia), canto(t1, meio - meia),
            canto(t1, meio + meia), canto(t0, meio + meia)]


def _intervalo_no_retangulo(p, q, ret):
    """Parte (t0, t1) do segmento p->q dentro do retângulo convexo, ou None."""
    t0, t1 = 0.0, 1.0
    dx, dy = q[0] - p[0], q[1] - p[1]
    for i in range(4):
        ax, ay = ret[i]
        bx, by = ret[(i + 1) % 4]
        ex, ey = bx - ax, by - ay
        # meio-plano à esquerda da aresta (interior, pois o retângulo é anti-horário)
        num = ex * (p[1] - ay) - ey * (p[0] - ax)
        den = ex * dy - ey * dx
        if abs(den) < 1e-12:
            if num < 0:
                return None
            continue
        t = -num / den
        if den > 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return (t0, t1) if t1 - t0 > 1e-9 else None


def malha_paredes(segmentos, altura, soleiras=None, altura_vao=ALTURA_VAO_PORTA_M,
                  comprimento_min=0.10, limite=12000):
    """Painéis verticais (Mesh3d) das paredes, com os vãos de porta livres.

    Nos vãos (soleiras) não há parede até `altura_vao`; acima dela a parede
    continua (verga). Segmentos duplicados são unidos.
    """
    soleiras = soleiras or []
    vaos = [r for r in (_retangulo_vao(pts) for pts in soleiras) if r]
    pecas = {}

    def _add(a, b, z0, z1):
        if z1 - z0 < 1e-6 or math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-3:
            return
        ka, kb = (round(a[0], 3), round(a[1], 3)), (round(b[0], 3), round(b[1], 3))
        pecas[(min(ka, kb), max(ka, kb), round(z0, 3))] = (a, b, z0, z1)

    for p, q in segmentos:
        comp = math.hypot(q[0] - p[0], q[1] - p[1])
        if comp < comprimento_min:
            continue
        dentro = sorted(iv for iv in (_intervalo_no_retangulo(p, q, r) for r in vaos) if iv)
        fundidos = []
        for t0, t1 in dentro:
            if fundidos and t0 <= fundidos[-1][1] + 1e-9:
                fundidos[-1] = (fundidos[-1][0], max(fundidos[-1][1], t1))
            else:
                fundidos.append((t0, t1))

        def ponto(t):
            return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))

        cursor = 0.0
        for t0, t1 in fundidos:
            if t0 > cursor:
                _add(ponto(cursor), ponto(t0), 0.0, altura)       # parede inteira
            _add(ponto(t0), ponto(t1), altura_vao, altura)         # verga sobre o vão
            cursor = t1
        if cursor < 1.0:
            _add(ponto(cursor), ponto(1.0), 0.0, altura)

    # A própria soleira: somente a verga (acima do vão).
    for pts in soleiras:
        for i in range(len(pts) - 1):
            _add(pts[i], pts[i + 1], altura_vao, altura)

    itens = sorted(pecas.values(), key=lambda it: -math.hypot(it[1][0] - it[0][0], it[1][1] - it[0][1]))[:limite]
    X, Y, Z, I, J, K = [], [], [], [], [], []
    for a, b, z0, z1 in itens:
        base = len(X)
        X += [a[0], b[0], b[0], a[0]]
        Y += [a[1], b[1], b[1], a[1]]
        Z += [z0, z0, z1, z1]
        I += [base, base]; J += [base + 1, base + 2]; K += [base + 2, base + 3]
    return X, Y, Z, I, J, K


def retangulo_piso(segmentos, folga=0.3):
    """Retângulo (x0, y0, x1, y1) que envolve a arquitetura, ou None."""
    if not segmentos:
        return None
    xs = [p[0] for seg in segmentos for p in seg]
    ys = [p[1] for seg in segmentos for p in seg]
    return (min(xs) - folga, min(ys) - folga, max(xs) + folga, max(ys) + folga)


def curva_ligacao(p0, p1, passos=24):
    """Arco suave (Bézier cúbica) entre duas caixas, saindo e chegando na vertical.

    p0 e p1 são (x, y, z). Sem diferença de altura, vira uma reta.
    """
    dz = p1[2] - p0[2]
    if abs(dz) < 1e-9:
        return [p0, p1]
    k = abs(dz) * 0.5
    sinal = 1.0 if dz > 0 else -1.0
    c1 = (p0[0], p0[1], p0[2] + sinal * k)
    c2 = (p1[0], p1[1], p1[2] - sinal * k)
    pts = []
    for i in range(passos + 1):
        t = i / passos
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        pts.append(tuple(a * p0[j] + b * c1[j] + c * c2[j] + d * p1[j] for j in range(3)))
    return pts


def comprimento_3d(pontos):
    return sum(math.dist(pontos[i], pontos[i + 1]) for i in range(len(pontos) - 1))


def malha_qdc(qdc):
    """Vértices/triângulos do QDC (caixa centrada na altura de entrada)."""
    cx, cy = qdc["ponto"]
    cz = qdc["altura_m"]
    u, n = qdc["u"], qdc["n"]
    hl, hp, hh = qdc["largura_m"] / 2, qdc["prof_m"] / 2, qdc["altura_caixa_m"] / 2
    X, Y, Z = [], [], []
    for sz in (-1, 1):
        for sn in (-1, 1):
            for su in (-1, 1):
                X.append(cx + su * hl * u[0] + sn * hp * n[0])
                Y.append(cy + su * hl * u[1] + sn * hp * n[1])
                Z.append(cz + sz * hh)
    faces = ((0, 1, 3), (0, 3, 2), (4, 5, 7), (4, 7, 6), (0, 1, 5), (0, 5, 4),
             (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 3, 7), (1, 7, 5))
    return X, Y, Z, [f[0] for f in faces], [f[1] for f in faces], [f[2] for f in faces]


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

    # Descidas verticais -----------------------------------------------------
    # - Tomada ligada a ponto de luz: descida a partir do teto/percurso.
    # - Tomada vizinha a um interruptor (ou ligada a ele pelo desenho): é
    #   alimentada por ele, com um eletroduto vertical próprio entre a altura do
    #   interruptor e a da tomada (o do teto vai só até o interruptor).
    # - Demais tomadas: sem descida (alimentadas pelo eletroduto horizontal).
    # - Cada eletroduto que sai do QDC tem a sua vertical, da entrada do QDC
    #   até a altura em que o trecho corre na horizontal.
    trechos_pts = [c["pontos"] for c in condutos] if condutos else [h["pontos"] for h in horizontais]
    nos_pt = [(c["ponto"][0], c["ponto"][1], c["altura_m"], c["tipo"] == "INTERRUPTOR") for c in caixas]

    def _chave(no):
        return (round(no[0], 4), round(no[1], 4))

    ligadas, via_int = set(), {}
    for pts in trechos_pts:
        for ext, outra in ((pts[0], pts[-1]), (pts[-1], pts[0])):
            n_ext = _no_mais_proximo(ext, nos_pt, TOL_PONTO_M)      # nó mais próximo de verdade
            n_out = _no_mais_proximo(outra, nos_pt, TOL_PONTO_M)
            if _no_mais_proximo(ext, luzes_xy, TOL_LUZ_M) is not None and n_out is not None and not n_out[3]:
                ligadas.add(_chave(n_out))
            if n_ext is not None and n_out is not None and n_ext[3] and not n_out[3]:
                via_int.setdefault(_chave(n_out), n_ext)
    interruptores_pt = [n for n in nos_pt if n[3]]
    for n in nos_pt:
        if n[3] or _chave(n) in ligadas or _chave(n) in via_int:
            continue
        it = _no_mais_proximo((n[0], n[1]), interruptores_pt, TOL_INT_TOMADA_M)
        if it is not None:
            via_int[_chave(n)] = it

    sem_descida = 0
    if alturas_ok:
        novas = []
        for v in verticais:
            if v["tipo"] == "QDC":
                continue
            eh_tomada = v["tipo"] not in TIPOS_ILUMINACAO and v["tipo"] != "INTERRUPTOR"
            if not eh_tomada:
                novas.append(v)
                continue
            k = (round(v["ponto"][0], 4), round(v["ponto"][1], 4))
            if k in ligadas:
                novas.append(v)
            elif k in via_int:
                it = via_int[k]
                curva = curva_ligacao((it[0], it[1], it[2]),
                                      (v["ponto"][0], v["ponto"][1], v["altura_m"]))
                comp = comprimento_3d(curva)
                if comp > 1e-6:
                    novas.append({**v, "nivel_m": it[2], "comprimento_m": comp, "origem": "INTERRUPTOR",
                                  "curva": curva, "ponto_origem": (it[0], it[1])})
            else:
                sem_descida += 1

        qdc_verticais = []
        if qdc is not None:
            qx, qy = qdc["ponto"]
            qz = qdc["altura_m"]
            u_q, n_q = _orientacao_parede(qx, qy, segmentos)
            cand = []
            for hi, h in enumerate(horizontais):
                pts = h["pontos"]
                for fim_do_trecho in (False, True):
                    pt = pts[-1] if fim_do_trecho else pts[0]
                    if math.hypot(pt[0] - qx, pt[1] - qy) > TOL_QDC_M:
                        continue
                    z_ext = (h["altura_fim_m"] if (fim_do_trecho and h["altura_fim_m"] is not None) else h["z"])
                    if abs(qz - z_ext) > 1e-6:
                        proj = (pt[0] - qx) * u_q[0] + (pt[1] - qy) * u_q[1]
                        cand.append((proj, hi, fim_do_trecho, z_ext))
                    break
            cand.sort(key=lambda c: c[0])   # ordem ao longo do QDC: evita cruzamentos
            total_saidas = len(cand)
            for k, (proj, hi, fim_do_trecho, z_ext) in enumerate(cand):
                desloc = (k - (total_saidas - 1) / 2.0) * QDC_ESPACAMENTO_M
                sx, sy = qx + u_q[0] * desloc, qy + u_q[1] * desloc
                h = horizontais[hi]
                # o trecho passa a nascer na saída própria dele no QDC
                if fim_do_trecho:
                    h["pontos3d"].append((sx, sy, z_ext))
                else:
                    h["pontos3d"].insert(0, (sx, sy, z_ext))
                qdc_verticais.append({
                    "ponto": (sx, sy), "tipo": "QDC", "altura_m": z_ext, "nivel_m": qz,
                    "comprimento_m": abs(qz - z_ext), "diametro_mm": h["diametro_mm"],
                    "origem": "QDC", "circuitos": h["circuitos"], "trecho": h["id"],
                })
            qdc = {**qdc, "u": u_q, "n": n_q, "prof_m": QDC_PROF_M, "altura_caixa_m": QDC_ALTURA_CAIXA_M,
                   "largura_m": max(QDC_LARGURA_MIN_M, (total_saidas + 1) * QDC_ESPACAMENTO_M),
                   "saidas": total_saidas}
            if not qdc_verticais:
                qdc_verticais = [v for v in verticais if v["tipo"] == "QDC"]
        verticais = novas + qdc_verticais

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
        "caixas": caixas, "tomadas_sem_descida": sem_descida, "luzes": [(float(x), float(y)) for x, y in luzes],
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
        segmentos, luzes, condutos, comandos, soleiras = _extrair_geometria(doc.modelspace())

        modelo = montar_modelo(
            segmentos, luzes, resumo_rotas, z_height, None,
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
            X, Y, Z, I, J, K = malha_paredes(segmentos, z_height, soleiras)
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
                if v.get("curva"):
                    for (cx_, cy_, cz_) in v["curva"]:
                        xs.append(cx_); ys.append(cy_); zs.append(cz_)
                    xs.append(None); ys.append(None); zs.append(None)
                    cm_ = v["curva"][len(v["curva"]) // 2]
                    mx.append(cm_[0]); my.append(cm_[1]); mz.append(cm_[2])
                else:
                    xs.extend([x, x, None]); ys.extend([y, y, None]); zs.extend([v["nivel_m"], v["altura_m"], None])
                    mx.append(x); my.append(y); mz.append((v["nivel_m"] + v["altura_m"]) / 2)
                diam = f' Ø{int(v["diametro_mm"])} mm' if v["diametro_mm"] else ""
                textos.append(f"{_fmt_m(v['comprimento_m'])} m" if m_cotas else "")
                if v.get("origem") == "QDC":
                    hovers.append(f"Saída do QDC (trecho {v.get('trecho', '—')})"
                                  f"<br>Do QDC ({_fmt_m(v['nivel_m'])} m) até {_fmt_m(v['altura_m'])} m"
                                  f"<br>Vertical: {_fmt_m(v['comprimento_m'])} m<br>Eletroduto:{diam or ' —'}"
                                  f"<br>Circuitos: {', '.join(v.get('circuitos') or []) or '—'}")
                elif v.get("origem") == "INTERRUPTOR":
                    hovers.append(f"Ligação interruptor → {_rotulo_tipo(v['tipo']).lower()} (arco)"
                                  f"<br>Do interruptor ({_fmt_m(v['nivel_m'])} m) até {_fmt_m(v['altura_m'])} m"
                                  f"<br>Comprimento do arco: {_fmt_m(v['comprimento_m'])} m<br>Eletroduto:{diam or ' —'}")
                else:
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
            if "largura_m" in q:
                X, Y, Z, I, J, K = malha_qdc(q)
                fig.add_trace(go.Mesh3d(
                    x=X, y=Y, z=Z, i=I, j=J, k=K, color=COR_QDC, opacity=0.45, flatshading=True,
                    name="QDC", showlegend=True, hoverinfo="text",
                    hovertext=(f"QDC — {q['largura_m'] * 100:.0f} × {q['altura_caixa_m'] * 100:.0f} × "
                               f"{q['prof_m'] * 100:.0f} cm<br>Entrada dos eletrodutos: {_fmt_m(q['altura_m'])} m"
                               f"<br>{q['saidas']} saída(s) com {QDC_ESPACAMENTO_M * 100:.0f} cm entre elas")))
            else:
                fig.add_trace(go.Scatter3d(x=[q["ponto"][0]], y=[q["ponto"][1]], z=[q["altura_m"]], mode="markers",
                                           name="QDC", marker=dict(size=9, color=COR_QDC, symbol="square"),
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
            "Trechos que correm pelas paredes ficam na altura das tomadas a que pertencem; vãos de "
            f"porta ficam livres até {_fmt_m(ALTURA_VAO_PORTA_M)} m."
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Eletroduto horizontal", f"{_fmt_m(modelo['total_horizontal_m'])} m",
                   help=f"Soma do Quantitativo de Materiais. Percurso desenhado no CAD: {_fmt_m(modelo['total_desenhado_m'])} m.")
        m2.metric("Descidas verticais", f"{_fmt_m(modelo['total_vertical_m'])} m",
                   help=f"{modelo['tomadas_sem_descida']} tomada(s) sem ligação com luz ou interruptor não têm descida: são alimentadas pelo eletroduto horizontal.")
        m3.metric("Caixas 4x2", len(modelo["caixas"]))
        m4.metric("Pontos de iluminação", len(modelo["luzes"]))

        aba_h, aba_v, aba_c = st.tabs(["Trechos horizontais", "Descidas e ligações", "Caixas 4x2"])
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
                {"Ponto": _rotulo_tipo(v["tipo"]),
                 "Parte de": {"QDC": "QDC", "INTERRUPTOR": "Interruptor (arco)"}.get(v.get("origem"), "Percurso (teto/piso)"),
                 "X (m)": round(v["ponto"][0], 3), "Y (m)": round(v["ponto"][1], 3),
                 "De (m)": round(v["nivel_m"], 2), "Até (m)": round(v["altura_m"], 2),
                 "Comprimento (m)": round(v["comprimento_m"], 2), "Ø (mm)": v["diametro_mm"]}
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
