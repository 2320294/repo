
import math

from geometria import centro_poligono, get_inside_normal
from soleiras_geometria import (
    rotular_p1_p4,
    ponto_10cm_apos_p2,
    distancia_ponto_segmento,
)
from portas_selecao import (
    portas_do_ambiente,
)

RAIO_INTERRUPTOR = 0.025
AFASTAMENTO_APOS_P2 = 0.10


def _porta_mais_proxima_da_soleira(s, portas_raw):
    verts = s.get("vertices") or []
    if not verts or not portas_raw:
        return None

    melhor = None
    melhor_d = float("inf")

    for porta in portas_raw:
        a, b = porta["p1"], porta["p2"]
        d = min(
            distancia_ponto_segmento(v, a, b)
            for v in verts
        )

        if d < melhor_d:
            melhor_d = d
            melhor = porta

    return melhor


def _nome_ambiente_da_poligonal(poly, textos):
    xs = [pt[0] for pt in poly]
    ys = [pt[1] for pt in poly]

    return next(
        (
            t["nome"]
            for t in textos
            if min(xs)-0.5 <= t["x"] <= max(xs)+0.5
            and min(ys)-0.5 <= t["y"] <= max(ys)+0.5
        ),
        None
    )


def _ambientes_nomeados(polilinhas, textos):
    resultado = []
    usados = {}

    for poly in polilinhas:
        nome = _nome_ambiente_da_poligonal(
            poly,
            textos
        )

        if not nome:
            continue

        if nome in usados:
            usados[nome] += 1
            nome_final = (
                f"{nome} {usados[nome]}"
            )
        else:
            usados[nome] = 1
            nome_final = nome

        resultado.append({
            "nome": nome_final,
            "poly": poly
        })

    return resultado


def _centro_interruptor(ambiente, soleira, porta):
    verts = soleira.get("vertices") or []

    rot = rotular_p1_p4(
        verts,
        porta
    )

    if not rot:
        return None

    tang = ponto_10cm_apos_p2(
        rot,
        AFASTAMENTO_APOS_P2
    )

    if tang is None:
        return None

    p1 = rot["p1"]
    p2 = rot["p2"]

    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    comp = math.hypot(dx, dy)

    if comp <= 1e-12:
        return None

    ux = dx / comp
    uy = dy / comp

    cx_env, cy_env = centro_poligono(
        ambiente["poly"]
    )

    normal = get_inside_normal(
        ux,
        uy,
        tang[0],
        tang[1],
        cx_env,
        cy_env
    )

    centro = (
        tang[0]
        + normal[0] * RAIO_INTERRUPTOR,
        tang[1]
        + normal[1] * RAIO_INTERRUPTOR
    )

    return {
        "centro": centro,
        "tangencia": tang,
        "rot": rot
    }


def desenhar_interruptores(
    msp,
    polilinhas,
    textos,
    soleiras_raw,
    portas_raw,
    config_interruptores
):
    """
    Fase 5.6:
    - Ambiente com uma porta: interruptor automático.
    - Ambiente com 2+ portas: somente IDs selecionados
      graficamente pelo usuário recebem interruptores.
    """
    config_interruptores = (
        config_interruptores
        or {}
    )

    pontos_gerados = []

    for ambiente in _ambientes_nomeados(
        polilinhas,
        textos
    ):
        nome = ambiente["nome"]

        portas = portas_do_ambiente(
            nome,
            ambiente["poly"],
            soleiras_raw
        )

        if not portas:
            continue

        cfg = config_interruptores.get(
            nome,
            {}
        )

        if not isinstance(cfg, dict):
            cfg = {}

        if len(portas) == 1:
            ids_escolhidos = {
                portas[0]["id"]
            }
        else:
            ids_escolhidos = set(
                cfg.get(
                    "portas_ids",
                    []
                )
                or []
            )

            # Compatibilidade com configuração antiga:
            # se não houver IDs salvos, respeita a quantidade antiga
            # em ordem estável.
            if not ids_escolhidos and "portas_ids" not in cfg:
                qtd_antiga = max(
                    0,
                    min(
                        len(portas),
                        int(
                            cfg.get(
                                "quantidade",
                                0
                            )
                        )
                    )
                )

                ids_escolhidos = {
                    p["id"]
                    for p in portas[:qtd_antiga]
                }

        for item_porta in portas:
            if item_porta["id"] not in ids_escolhidos:
                continue

            soleira = item_porta["soleira"]

            porta_geom = (
                _porta_mais_proxima_da_soleira(
                    soleira,
                    portas_raw
                )
            )

            if porta_geom is None:
                continue

            geo = _centro_interruptor(
                ambiente,
                soleira,
                porta_geom
            )

            if geo is None:
                continue

            msp.add_circle(
                center=geo["centro"],
                radius=RAIO_INTERRUPTOR,
                dxfattribs={
                    "layer":
                    "PROJ_ELETRICA_INTERRUPTOR"
                }
            )

            rot = geo["rot"]

            pontos_gerados.append({
                "ambiente": nome,
                "tipo": "INTERRUPTOR",
                "porta_id": item_porta["id"],
                "porta_numero":
                    item_porta["numero"],
                "ponto": geo["centro"],
                "ponto_tangencia":
                    geo["tangencia"],
                "referencia":
                    "TANGENTE_10cm_APOS_P2",
                "diametro_m": 0.05,
                "p1": rot["p1"],
                "p2": rot["p2"],
                "p3": rot["p3"],
                "p4": rot["p4"],
            })

    return pontos_gerados
