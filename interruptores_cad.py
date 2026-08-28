
import math
from geometria import centro_poligono
from soleiras_geometria import (
    rotular_p1_p4,
    ponto_10cm_apos_p2,
    distancia_ponto_segmento,
)

RAIO_INTERRUPTOR = 0.15
AFASTAMENTO_APOS_P2 = 0.10  # 10 cm exatos


def _vertices_soleira(s):
    vertices = s.get("vertices")
    if vertices and len(vertices) >= 4:
        # remove eventual fechamento repetido
        unicos = []
        for p in vertices:
            q = (float(p[0]), float(p[1]))
            if q not in unicos:
                unicos.append(q)
        return unicos
    return []


def _porta_mais_proxima_da_soleira(s, portas_raw, tolerancia=0.20):
    verts = _vertices_soleira(s)
    if not verts:
        return None

    melhor = None
    melhor_d = float("inf")
    for porta in portas_raw:
        a, b = porta["p1"], porta["p2"]
        d = min(distancia_ponto_segmento(v, a, b) for v in verts)
        if d < melhor_d:
            melhor_d = d
            melhor = porta

    return melhor if melhor_d <= tolerancia else None


def associar_soleiras_portas(soleiras_raw, portas_raw, tolerancia=0.20):
    resultado = []
    for s in soleiras_raw:
        porta = _porta_mais_proxima_da_soleira(s, portas_raw, tolerancia)
        if porta is not None:
            resultado.append({"s": s, "porta": porta})
    return resultado


def desenhar_interruptores(
    msp,
    polilinhas,
    textos,
    soleiras_raw,
    portas_raw,
    config_interruptores
):
    config_interruptores = config_interruptores or {}
    pontos_gerados = []

    def nome_ambiente_da_poligonal(poly):
        xs = [pt[0] for pt in poly]
        ys = [pt[1] for pt in poly]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return next(
            (
                t["nome"] for t in textos
                if min_x - 0.5 <= t["x"] <= max_x + 0.5
                and min_y - 0.5 <= t["y"] <= max_y + 0.5
            ),
            None
        )

    for item in associar_soleiras_portas(soleiras_raw, portas_raw):
        s = item["s"]
        porta = item["porta"]
        vertices = _vertices_soleira(s)
        rot = rotular_p1_p4(vertices, porta)
        if not rot:
            continue

        # REGRA FASE 5.2:
        # centro do interruptor = exatamente 10 cm após P2,
        # continuando o vetor P1 -> P2.
        ponto_interruptor = ponto_10cm_apos_p2(rot, AFASTAMENTO_APOS_P2)
        if ponto_interruptor is None:
            continue

        # Centro geométrico da soleira para localizar ambientes adjacentes.
        sx = sum(v[0] for v in vertices) / len(vertices)
        sy = sum(v[1] for v in vertices) / len(vertices)

        ambientes = []
        vistos = set()
        for poly in polilinhas:
            xs = [pt[0] for pt in poly]
            ys = [pt[1] for pt in poly]
            if (
                min(xs)-0.5 <= sx <= max(xs)+0.5
                and min(ys)-0.5 <= sy <= max(ys)+0.5
            ):
                nome = nome_ambiente_da_poligonal(poly)
                if nome and nome not in vistos:
                    vistos.add(nome)
                    ambientes.append({"poly": poly, "nome": nome})

        for ambiente in ambientes[:2]:
            nome = ambiente["nome"]
            cfg = config_interruptores.get(nome, {})
            if not isinstance(cfg, dict):
                continue

            qtd = max(0, min(2, int(cfg.get("quantidade", 0))))
            if qtd == 0:
                continue

            # Nesta fase o ponto geométrico é único: 10 cm após P2.
            # Se a configuração solicitar 2 teclas/interruptores, desenhamos
            # o mesmo ponto uma única vez; o tratamento do símbolo múltiplo
            # será refinado depois sem alterar a referência geométrica.
            msp.add_circle(
                center=ponto_interruptor,
                radius=RAIO_INTERRUPTOR,
                dxfattribs={"layer": "PROJ_ELETRICA_INTERRUPTOR"}
            )

            pontos_gerados.append({
                "ambiente": nome,
                "tipo": "INTERRUPTOR",
                "ponto": ponto_interruptor,
                "referencia": "10cm_APOS_P2",
                "p1": rot["p1"],
                "p2": rot["p2"],
                "p3": rot["p3"],
                "p4": rot["p4"],
            })

    return pontos_gerados
