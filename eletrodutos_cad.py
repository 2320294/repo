import math
from collections import defaultdict, deque

from geometria import point_seg_dist


LAYER_ELETRODUTOS = "PROJ_ELETRICA_ELETRODUTO"
LAYER_ELETRODUTOS_TEXTO = "PROJ_ELETRICA_ELETRODUTO_TEXTO"
LAYER_COMANDO = "PROJ_ELETRICA_COMANDO"


def _numero(valor, padrao=0.0):
    try:
        if valor is None:
            return padrao
        return float(valor)
    except (TypeError, ValueError):
        return padrao


def _inteiro(valor, padrao=0):
    try:
        if valor is None:
            return padrao
        return int(float(valor))
    except (TypeError, ValueError):
        return padrao


def montar_circuitos_por_ambiente(dados_editados):
    """Cria a estrutura de circuitos usada pelo CAD.

    Nesta etapa cada ambiente/tipo permanece como circuito independente, como já
    ocorria na Fase 1. O diferencial é que o destino do circuito deixa de ser o
    centro do ambiente e passa a ser o ponto elétrico realmente desenhado.
    """
    circuitos = []
    numero = 1

    for row in dados_editados or []:
        ambiente = str(row.get("Ambiente", "")).strip()
        if not ambiente:
            continue

        qtd_ilum = _inteiro(row.get("Qtd Ilum.", 0))
        qtd_tug = _inteiro(row.get("Qtd TUG", row.get("TUGs (Qtd)", 0)))
        qtd_tue = _inteiro(row.get("Qtd TUE", 0))

        if qtd_ilum > 0:
            circuitos.append({
                "numero": numero,
                "id": f"C{numero}",
                "tipo": "ILUMINACAO",
                "ambiente": ambiente,
                "bitola_mm2": 1.5,
                "quantidade_condutores": 3,
            })
            numero += 1

        if qtd_tug > 0:
            circuitos.append({
                "numero": numero,
                "id": f"C{numero}",
                "tipo": "TUG",
                "ambiente": ambiente,
                "bitola_mm2": 2.5,
                "quantidade_condutores": 3,
            })
            numero += 1

        for indice in range(qtd_tue):
            circuitos.append({
                "numero": numero,
                "id": f"C{numero}",
                "tipo": "TUE",
                "ambiente": ambiente,
                "bitola_mm2": 2.5,
                "quantidade_condutores": 3,
                "indice_tue": indice + 1,
            })
            numero += 1

    return circuitos


def _dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _segmento_valido(p1, p2, tolerancia=1e-6):
    return _dist(p1, p2) > tolerancia


def _segmentos_poligono(poly):
    pts = list(poly or [])
    if len(pts) < 2:
        return []
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return list(zip(pts, pts[1:]))


def _dist_ponto_poligono(ponto, poly):
    segs = _segmentos_poligono(poly)
    if not segs:
        return float("inf")
    return min(
        point_seg_dist(ponto[0], ponto[1], a, b)
        for a, b in segs
    )


def _bbox_perto(ponto, bbox, folga=0.65):
    min_x, max_x, min_y, max_y = bbox
    return (
        min_x - folga <= ponto[0] <= max_x + folga
        and min_y - folga <= ponto[1] <= max_y + folga
    )


def _montar_grafo_ambientes(ambientes_geom, soleiras_raw):
    """Associa cada soleira aos dois ambientes mais próximos.

    A soleira passa a funcionar como um portal construtivo entre ambientes. Isso
    evita que o roteador atravesse paredes aleatoriamente só porque uma reta é
    geometricamente mais curta.
    """
    grafo = defaultdict(list)
    portais = []

    for idx, soleira in enumerate(soleiras_raw or []):
        p1 = soleira.get("p1")
        p2 = soleira.get("p2")
        if not p1 or not p2:
            continue

        meio = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        candidatos = []

        for amb in ambientes_geom:
            if not _bbox_perto(meio, amb["bbox"], folga=0.75):
                continue
            d = _dist_ponto_poligono(meio, amb["polilinha"])
            if d <= 0.75:
                candidatos.append((d, amb["nome"]))

        candidatos.sort(key=lambda item: item[0])
        nomes = []
        for _, nome in candidatos:
            if nome not in nomes:
                nomes.append(nome)
            if len(nomes) == 2:
                break

        if len(nomes) < 2:
            continue

        a, b = nomes
        portal = {
            "id": f"S{idx + 1}",
            "a": a,
            "b": b,
            "ponto": meio,
            "p1": p1,
            "p2": p2,
        }
        portais.append(portal)
        grafo[a].append((b, portal))
        grafo[b].append((a, portal))

    return grafo, portais


def _caminho_ambientes(grafo, origem, destino):
    if not origem or not destino:
        return None
    if origem == destino:
        return []

    fila = deque([origem])
    anterior = {origem: None}
    portal_usado = {}

    while fila:
        atual = fila.popleft()
        for vizinho, portal in grafo.get(atual, []):
            if vizinho in anterior:
                continue
            anterior[vizinho] = atual
            portal_usado[vizinho] = portal
            if vizinho == destino:
                fila.clear()
                break
            fila.append(vizinho)

    if destino not in anterior:
        return None

    portais = []
    atual = destino
    while anterior[atual] is not None:
        portais.append(portal_usado[atual])
        atual = anterior[atual]
    portais.reverse()
    return portais


def _normalizar_tipo(tipo):
    return str(tipo or "").strip().upper().replace("Ç", "C").replace("Ã", "A")


def _pontos_do_circuito(circuito, pontos_eletricos):
    ambiente = circuito["ambiente"]
    tipo = circuito["tipo"]

    candidatos = [
        p for p in (pontos_eletricos or [])
        if str(p.get("ambiente", "")).strip() == ambiente
        and _normalizar_tipo(p.get("tipo")) == _normalizar_tipo(tipo)
    ]

    if tipo == "TUE":
        indice = max(1, int(circuito.get("indice_tue", 1))) - 1
        if candidatos:
            return [candidatos[min(indice, len(candidatos) - 1)]]

    return candidatos


def _chave_segmento(p1, p2, casas=4):
    a = (round(p1[0], casas), round(p1[1], casas))
    b = (round(p2[0], casas), round(p2[1], casas))
    return tuple(sorted((a, b)))


def _adicionar_segmento_agregado(agregados, p1, p2, circuito, natureza="ALIMENTACAO", ambiente=None):
    if not _segmento_valido(p1, p2):
        return
    chave = (_chave_segmento(p1, p2), natureza)
    if chave not in agregados:
        agregados[chave] = {
            "p1": tuple(p1),
            "p2": tuple(p2),
            "circuitos": set(),
            "natureza": natureza,
            "ambiente": ambiente,
        }
    agregados[chave]["circuitos"].add(circuito)


def _ordenar_pontos_por_proximidade(inicio, registros):
    restantes = list(registros)
    ordem = []
    atual = inicio
    while restantes:
        prox = min(restantes, key=lambda r: _dist(atual, r["ponto"]))
        ordem.append(prox)
        restantes.remove(prox)
        atual = prox["ponto"]
    return ordem


def _rotulo_trecho(msp, p1, p2, texto):
    if not _segmento_valido(p1, p2):
        return
    mx = (p1[0] + p2[0]) / 2
    my = (p1[1] + p2[1]) / 2
    msp.add_text(
        texto,
        dxfattribs={
            "layer": LAYER_ELETRODUTOS_TEXTO,
            "height": 0.11,
            "insert": (mx + 0.06, my + 0.06),
        },
    )


def _desenhar_comandos_iluminacao(msp, pontos_interruptores, pontos_eletricos):
    luzes_por_ambiente = defaultdict(list)
    for p in pontos_eletricos or []:
        if _normalizar_tipo(p.get("tipo")) == "ILUMINACAO":
            luzes_por_ambiente[p.get("ambiente")].append(p)

    comandos = []
    for interruptor in pontos_interruptores or []:
        ambiente = interruptor.get("ambiente")
        luzes = luzes_por_ambiente.get(ambiente, [])
        if not luzes:
            continue
        origem = interruptor["ponto"]
        alvo = min(luzes, key=lambda p: _dist(origem, p["ponto"]))["ponto"]
        if not _segmento_valido(origem, alvo):
            continue
        msp.add_line(origem, alvo, dxfattribs={"layer": LAYER_COMANDO})
        comandos.append({"ambiente": ambiente, "p1": origem, "p2": alvo})
    return comandos


def _pontos_iluminacao_por_ambiente(pontos_eletricos):
    grupos = defaultdict(list)
    for p in pontos_eletricos or []:
        if _normalizar_tipo(p.get("tipo")) != "ILUMINACAO":
            continue
        ambiente = str(p.get("ambiente", "")).strip()
        ponto = p.get("ponto")
        if ambiente and ponto:
            grupos[ambiente].append(p)
    return grupos


def _escolher_pontos_distribuicao(ambientes_geom, pontos_eletricos):
    """Escolhe um ponto de iluminação real como distribuição de cada ambiente.

    A soleira/porta nunca é ponto de distribuição. Quando há mais de uma
    luminária no ambiente, é escolhida a mais próxima do centro geométrico do
    cômodo, produzindo um nó estável e normalmente central para os ramais.
    """
    luzes = _pontos_iluminacao_por_ambiente(pontos_eletricos)
    geom_por_nome = {
        str(a.get("nome", "")).strip(): a
        for a in (ambientes_geom or [])
        if str(a.get("nome", "")).strip()
    }

    distribuicao = {}
    for ambiente, registros in luzes.items():
        if not registros:
            continue
        geom = geom_por_nome.get(ambiente)
        if geom and geom.get("centro"):
            referencia = tuple(geom["centro"])
        else:
            xs = [r["ponto"][0] for r in registros]
            ys = [r["ponto"][1] for r in registros]
            referencia = (sum(xs) / len(xs), sum(ys) / len(ys))

        escolhido = min(registros, key=lambda r: _dist(referencia, r["ponto"]))
        distribuicao[ambiente] = {
            "ambiente": ambiente,
            "ponto": tuple(escolhido["ponto"]),
            "registro": escolhido,
            "criterio": "PONTO_ILUMINACAO_CENTRAL",
        }

    return distribuicao


def _construir_arvore_distribuicao(qdc, ambiente_qdc, pontos_distribuicao, economia_minima=0.18, profundidade_max=2):
    """Monta uma árvore QDC -> luminárias sem usar portas/soleiras.

    Regra conservadora: o QDC é a raiz. Um ambiente só deriva através da
    luminária de outro ambiente quando isso reduz de forma relevante o caminho
    geométrico em relação à saída direta do QDC. A profundidade é limitada para
    evitar cadeias excessivas e manter a planta legível.
    """
    hubs = {nome: tuple(d["ponto"]) for nome, d in pontos_distribuicao.items()}
    pais = {}
    profundidade = {}

    # O ambiente do QDC, quando possui luminária, é o primeiro nó natural.
    if ambiente_qdc in hubs:
        pais[ambiente_qdc] = "__QDC__"
        profundidade[ambiente_qdc] = 1

    restantes = [n for n in hubs if n != ambiente_qdc]
    # Ambientes mais próximos do quadro são decididos primeiro e podem servir
    # como nós de passagem para ambientes mais distantes.
    restantes.sort(key=lambda n: _dist(qdc, hubs[n]))

    for nome in restantes:
        direto = _dist(qdc, hubs[nome])
        melhor_pai = "__QDC__"
        melhor_custo = direto

        for candidato, ponto_candidato in hubs.items():
            if candidato == nome or candidato not in profundidade:
                continue
            if profundidade[candidato] >= profundidade_max:
                continue
            custo = _dist(qdc, ponto_candidato) + _dist(ponto_candidato, hubs[nome])
            # Derivação só é aceita quando o novo ramal, medido a partir de um
            # nó já alimentado, representa economia local relevante frente à
            # nova saída independente do QDC.
            ramal = _dist(ponto_candidato, hubs[nome])
            if ramal <= direto * (1.0 - economia_minima) and custo < melhor_custo * 1.35:
                melhor_pai = candidato
                melhor_custo = custo

        pais[nome] = melhor_pai
        profundidade[nome] = 1 if melhor_pai == "__QDC__" else profundidade[melhor_pai] + 1

    return pais, profundidade


def _caminho_nos_ate_qdc(ambiente, pais):
    caminho = []
    atual = ambiente
    vistos = set()
    while atual and atual != "__QDC__":
        if atual in vistos:
            return []
        vistos.add(atual)
        caminho.append(atual)
        atual = pais.get(atual, "__QDC__")
    caminho.reverse()
    return caminho


def _adicionar_rota_arvore(agregados, circuito_id, qdc, destino_ambiente, pais, pontos_distribuicao):
    caminho = _caminho_nos_ate_qdc(destino_ambiente, pais)
    if not caminho:
        return False
    atual = tuple(qdc)
    for ambiente in caminho:
        hub = tuple(pontos_distribuicao[ambiente]["ponto"])
        _adicionar_segmento_agregado(
            agregados, atual, hub, circuito_id,
            natureza="TRONCO_DISTRIBUICAO" if atual == tuple(qdc) else "DERIVACAO_ENTRE_LUMINARIAS",
            ambiente=ambiente,
        )
        atual = hub
    return True

def desenhar_rede_eletrodutos(
    msp,
    dados_editados,
    ambientes_geom,
    qdc_info,
    pontos_eletricos=None,
    soleiras_raw=None,
    pontos_interruptores=None,
):
    """Fase 4: rede elétrica independente de portas e soleiras.

    QDC = raiz fixa escolhida pelo usuário.
    Luminária principal = nó de distribuição de cada ambiente.
    Ambientes podem receber circuitos diretamente do QDC ou por derivação em
    luminária de outro ambiente. Soleiras/portas não participam da topologia.
    """
    if not qdc_info or not qdc_info.get("centro"):
        return {"circuitos": [], "trechos": [], "comandos": [], "pontos_distribuicao": []}

    qdc = tuple(qdc_info["centro"])
    ambiente_qdc = str(qdc_info.get("ambiente", "")).strip()
    circuitos = montar_circuitos_por_ambiente(dados_editados)
    pontos_distribuicao = _escolher_pontos_distribuicao(ambientes_geom, pontos_eletricos or [])
    pais, profundidade = _construir_arvore_distribuicao(qdc, ambiente_qdc, pontos_distribuicao)

    agregados = {}
    alocados = []
    for circuito in circuitos:
        destino = circuito["ambiente"]
        registros = _pontos_do_circuito(circuito, pontos_eletricos or [])
        hub_destino = pontos_distribuicao.get(destino)
        if not hub_destino:
            item = dict(circuito); item["status"] = "SEM_PONTO_ILUMINACAO_DISTRIBUICAO"; alocados.append(item); continue
        if not registros:
            item = dict(circuito); item["status"] = "SEM_PONTO_ELETRICO"; alocados.append(item); continue

        if not _adicionar_rota_arvore(agregados, circuito["id"], qdc, destino, pais, pontos_distribuicao):
            item = dict(circuito); item["status"] = "SEM_ROTA_DISTRIBUICAO"; alocados.append(item); continue

        hub = tuple(hub_destino["ponto"])
        for registro in registros:
            p = tuple(registro["ponto"])
            if _segmento_valido(hub, p):
                _adicionar_segmento_agregado(agregados, hub, p, circuito["id"], natureza="RAMAL_DO_PONTO_DE_LUZ", ambiente=destino)

        item = dict(circuito)
        item.update({
            "status": "ROTEADO", "ponto_distribuicao": hub,
            "tipo_ponto_distribuicao": "ILUMINACAO",
            "quantidade_pontos": len(registros),
            "pai_distribuicao": pais.get(destino, "__QDC__"),
            "profundidade_distribuicao": profundidade.get(destino, 1),
        })
        alocados.append(item)

    trechos = []
    for item in agregados.values():
        p1, p2 = item["p1"], item["p2"]
        ids = sorted(item["circuitos"], key=lambda x: int(x[1:]) if x[1:].isdigit() else 9999)
        msp.add_line(p1, p2, dxfattribs={"layer": LAYER_ELETRODUTOS})
        _rotulo_trecho(msp, p1, p2, "-".join(ids))
        trechos.append({"tipo": item["natureza"], "p1": p1, "p2": p2, "circuitos": ids, "comprimento": _dist(p1,p2), "ambiente": item.get("ambiente")})

    comandos = _desenhar_comandos_iluminacao(msp, pontos_interruptores or [], pontos_eletricos or [])
    return {
        "circuitos": alocados, "trechos": trechos, "comandos": comandos,
        "ambiente_qdc": ambiente_qdc, "qdc": qdc,
        "arvore_distribuicao": [{"ambiente": n, "pai": pais.get(n), "profundidade": profundidade.get(n)} for n in sorted(pais)],
        "pontos_distribuicao": [{"ambiente": n, "ponto": d["ponto"], "tipo": "ILUMINACAO"} for n,d in sorted(pontos_distribuicao.items())],
    }
