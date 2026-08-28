
import math

from geometria import centro_poligono, get_inside_normal
from soleiras_geometria import (
    rotular_p1_p4,
    distancia_ponto_segmento,
)
from portas_selecao import portas_do_ambiente

RAIO_INTERRUPTOR = 0.05  # TODOS os interruptores: Ø10 cm
AFASTAMENTO_APOS_REFERENCIA = 0.10


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
            if (
                min(xs) - 0.5 <= t["x"] <= max(xs) + 0.5
                and min(ys) - 0.5 <= t["y"] <= max(ys) + 0.5
            )
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


def _dist(a, b):
    return math.hypot(
        b[0] - a[0],
        b[1] - a[1]
    )


def _ponto_apos_referencia(
    origem,
    referencia,
    afastamento=AFASTAMENTO_APOS_REFERENCIA
):
    """
    Continua o vetor origem -> referencia por exatamente afastamento.
    """
    dx = referencia[0] - origem[0]
    dy = referencia[1] - origem[1]

    comp = math.hypot(dx, dy)

    if comp <= 1e-12:
        return None

    ux = dx / comp
    uy = dy / comp

    return (
        referencia[0] + ux * afastamento,
        referencia[1] + uy * afastamento
    )


def _lado_ambiente_em_relacao_soleira(
    ambiente,
    rot
):
    """
    Determina qual face longitudinal da soleira pertence ao ambiente.

    Face A: P1 -> P2
    Face B: P4 -> P3

    O centro do ambiente é comparado com os pontos médios das duas faces.
    """
    cx_env, cy_env = centro_poligono(
        ambiente["poly"]
    )

    centro_env = (
        cx_env,
        cy_env
    )

    p1 = rot["p1"]
    p2 = rot["p2"]
    p3 = rot["p3"]
    p4 = rot["p4"]

    meio_a = (
        (p1[0] + p2[0]) / 2.0,
        (p1[1] + p2[1]) / 2.0
    )

    meio_b = (
        (p4[0] + p3[0]) / 2.0,
        (p4[1] + p3[1]) / 2.0
    )

    if _dist(
        centro_env,
        meio_a
    ) <= _dist(
        centro_env,
        meio_b
    ):
        return "P2"

    return "P3"


def _geometria_interruptor(
    ambiente,
    soleira,
    porta_geom
):
    """
    Regra Fase 6.5:

    - lado do ambiente correspondente à face P1-P2:
      ponto de referência = P2;
      direção = P1 -> P2.

    - lado oposto correspondente à face P4-P3:
      ponto de referência = P3;
      direção = P4 -> P3.

    Dessa forma, se os dois ambientes adjacentes selecionarem
    a mesma porta, os dois interruptores ficam separados
    transversalmente exatamente pela distância P2-P3.
    """
    verts = soleira.get(
        "vertices"
    ) or []

    rot = rotular_p1_p4(
        verts,
        porta_geom
    )

    if not rot:
        return None

    lado = (
        _lado_ambiente_em_relacao_soleira(
            ambiente,
            rot
        )
    )

    if lado == "P2":
        origem = rot["p1"]
        referencia = rot["p2"]
    else:
        origem = rot["p4"]
        referencia = rot["p3"]

    ponto_tangencia = (
        _ponto_apos_referencia(
            origem,
            referencia
        )
    )

    if ponto_tangencia is None:
        return None

    dx = (
        referencia[0]
        - origem[0]
    )
    dy = (
        referencia[1]
        - origem[1]
    )

    comp = math.hypot(
        dx,
        dy
    )

    if comp <= 1e-12:
        return None

    ux = dx / comp
    uy = dy / comp

    cx_env, cy_env = (
        centro_poligono(
            ambiente["poly"]
        )
    )

    normal = (
        get_inside_normal(
            ux,
            uy,
            ponto_tangencia[0],
            ponto_tangencia[1],
            cx_env,
            cy_env
        )
    )

    centro = (
        ponto_tangencia[0]
        + normal[0]
        * RAIO_INTERRUPTOR,

        ponto_tangencia[1]
        + normal[1]
        * RAIO_INTERRUPTOR
    )

    return {
        "centro": centro,
        "tangencia":
            ponto_tangencia,
        "rot": rot,
        "lado_referencia": lado,
        "distancia_p2_p3":
            _dist(
                rot["p2"],
                rot["p3"]
            )
    }



def _preencher_circulo_interruptor(
    msp,
    centro,
    raio
):
    """
    Cria preenchimento sólido circular para representar
    interruptor paralelo.

    O contorno CIRCLE continua sendo desenhado normalmente;
    o HATCH SOLID fica na mesma camada.
    """
    try:
        hatch = msp.add_hatch(
            color=256,
            dxfattribs={
                "layer":
                    "PROJ_ELETRICA_INTERRUPTOR"
            }
        )

        hatch.set_solid_fill(
            color=256
        )

        caminho = (
            hatch.paths.add_edge_path()
        )

        caminho.add_arc(
            center=centro,
            radius=raio,
            start_angle=0,
            end_angle=360,
            ccw=True
        )

        return hatch

    except Exception:
        # O contorno do interruptor permanece mesmo que
        # algum visualizador não aceite o hatch circular.
        return None


def desenhar_interruptores(
    msp,
    polilinhas,
    textos,
    soleiras_raw,
    portas_raw,
    config_interruptores
):
    """
    Fase 6.5:
    - 1 porta: automático.
    - 2+ portas: somente IDs selecionados.
    - mesma porta selecionada pelos dois ambientes:
      interruptores usam faces opostas da soleira,
      separados pela distância P2-P3.
    """
    config_interruptores = (
        config_interruptores
        or {}
    )

    pontos_gerados = []

    for ambiente in (
        _ambientes_nomeados(
            polilinhas,
            textos
        )
    ):
        nome = ambiente["nome"]

        portas = portas_do_ambiente(
            nome,
            ambiente["poly"],
            soleiras_raw
        )

        if not portas:
            continue

        cfg = (
            config_interruptores.get(
                nome,
                {}
            )
        )

        if not isinstance(
            cfg,
            dict
        ):
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

            if (
                not ids_escolhidos
                and
                "portas_ids"
                not in cfg
            ):
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
                    for p
                    in portas[:qtd_antiga]
                }

        # REGRA FASE 6.3:
        # TODOS os interruptores têm Ø10 cm.
        # Se o ambiente possui dois ou mais interruptores,
        # eles são PARALELOS e recebem hachura sólida interna.
        # Com apenas um interruptor, mantém somente o contorno.
        interruptor_paralelo = (
            len(ids_escolhidos) >= 2
        )

        for item_porta in portas:
            if (
                item_porta["id"]
                not in ids_escolhidos
            ):
                continue

            soleira = (
                item_porta["soleira"]
            )

            porta_geom = (
                _porta_mais_proxima_da_soleira(
                    soleira,
                    portas_raw
                )
            )

            if porta_geom is None:
                continue

            geo = _geometria_interruptor(
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

            if interruptor_paralelo:
                _preencher_circulo_interruptor(
                    msp,
                    geo["centro"],
                    RAIO_INTERRUPTOR
                )

            rot = geo["rot"]

            pontos_gerados.append({
                "ambiente": nome,
                "tipo":
                    "INTERRUPTOR",
                "paralelo":
                    interruptor_paralelo,
                "porta_id":
                    item_porta["id"],
                "porta_numero":
                    item_porta["numero"],
                "ponto":
                    geo["centro"],
                "ponto_tangencia":
                    geo["tangencia"],
                "lado_referencia":
                    geo["lado_referencia"],
                "distancia_p2_p3":
                    geo["distancia_p2_p3"],
                "referencia":
                    "10cm_APOS_P2_OU_P3",
                "diametro_m": 0.10,
                "p1": rot["p1"],
                "p2": rot["p2"],
                "p3": rot["p3"],
                "p4": rot["p4"],
            })

    return pontos_gerados
