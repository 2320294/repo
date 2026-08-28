import math

from geometria import (
    point_seg_dist,
    get_inside_normal,
    centro_poligono
)

RAIO_INTERRUPTOR = 0.15


def associar_soleiras_portas(
    soleiras_raw,
    portas_raw,
    tolerancia=0.15
):
    resultado = []

    for s in soleiras_raw:
        s_p1 = s["p1"]
        s_p2 = s["p2"]

        porta_encostada = None

        for p in portas_raw:
            d1 = point_seg_dist(
                p["p1"][0],
                p["p1"][1],
                s_p1,
                s_p2
            )

            d2 = point_seg_dist(
                p["p2"][0],
                p["p2"][1],
                s_p1,
                s_p2
            )

            pm_porta = (
                (
                    p["p1"][0]
                    +
                    p["p2"][0]
                ) / 2,
                (
                    p["p1"][1]
                    +
                    p["p2"][1]
                ) / 2
            )

            d3 = point_seg_dist(
                pm_porta[0],
                pm_porta[1],
                s_p1,
                s_p2
            )

            if (
                d1 < tolerancia
                or d2 < tolerancia
                or d3 < tolerancia
            ):
                porta_encostada = p
                break

        if porta_encostada is not None:
            resultado.append({
                "s": s,
                "porta": porta_encostada
            })

    return resultado


def desenhar_interruptores(
    msp,
    polilinhas,
    textos,
    soleiras_raw,
    portas_raw,
    config_interruptores
):
    config_interruptores = (
        config_interruptores
        or {}
    )

    pontos_gerados = []

    soleiras_com_porta = (
        associar_soleiras_portas(
            soleiras_raw,
            portas_raw
        )
    )

    def nome_ambiente_da_poligonal(poly):
        xs = [pt[0] for pt in poly]
        ys = [pt[1] for pt in poly]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        return next(
            (
                t["nome"]
                for t in textos
                if (
                    min_x - 0.5
                    <= t["x"]
                    <= max_x + 0.5
                    and
                    min_y - 0.5
                    <= t["y"]
                    <= max_y + 0.5
                )
            ),
            None
        )

    for item in soleiras_com_porta:
        s = item["s"]
        p_porta = item["porta"]

        s_a = s["p1"]
        s_b = s["p2"]

        sm_x = (
            s_a[0] + s_b[0]
        ) / 2

        sm_y = (
            s_a[1] + s_b[1]
        ) / 2

        ambientes = []

        for poly in polilinhas:
            xs = [pt[0] for pt in poly]
            ys = [pt[1] for pt in poly]

            if (
                min(xs) - 0.5
                <= sm_x
                <= max(xs) + 0.5
                and
                min(ys) - 0.5
                <= sm_y
                <= max(ys) + 0.5
            ):
                nome = (
                    nome_ambiente_da_poligonal(
                        poly
                    )
                )

                if nome:
                    ambientes.append({
                        "poly": poly,
                        "nome": nome
                    })

        if not ambientes:
            continue

        d_a = min(
            math.hypot(
                s_a[0] - p_porta["p1"][0],
                s_a[1] - p_porta["p1"][1]
            ),
            math.hypot(
                s_a[0] - p_porta["p2"][0],
                s_a[1] - p_porta["p2"][1]
            )
        )

        d_b = min(
            math.hypot(
                s_b[0] - p_porta["p1"][0],
                s_b[1] - p_porta["p1"][1]
            ),
            math.hypot(
                s_b[0] - p_porta["p2"][0],
                s_b[1] - p_porta["p2"][1]
            )
        )

        if d_a >= d_b:
            p2 = s_a
            p3 = s_b
        else:
            p2 = s_b
            p3 = s_a

        for ambiente in ambientes[:2]:
            nome = ambiente["nome"]
            cfg = config_interruptores.get(
                nome,
                {}
            )

            if not isinstance(cfg, dict):
                continue

            qtd = max(
                0,
                min(
                    2,
                    int(
                        cfg.get(
                            "quantidade",
                            0
                        )
                    )
                )
            )

            if qtd == 0:
                continue

            poly = ambiente["poly"]

            cx_env, cy_env = (
                centro_poligono(poly)
            )

            dx = p3[0] - p2[0]
            dy = p3[1] - p2[1]

            comp = math.hypot(
                dx,
                dy
            )

            if comp == 0:
                continue

            vx = dx / comp
            vy = dy / comp

            normal = get_inside_normal(
                vx,
                vy,
                p2[0],
                p2[1],
                cx_env,
                cy_env
            )

            if qtd == 2:
                pontos = [p2, p3]

            else:
                porta_escolhida = max(
                    1,
                    min(
                        2,
                        int(
                            cfg.get(
                                "porta",
                                1
                            )
                        )
                    )
                )

                pontos = [
                    p2
                    if porta_escolhida == 1
                    else p3
                ]

            for ponto in pontos:
                centro = (
                    ponto[0]
                    + normal[0] * RAIO_INTERRUPTOR,
                    ponto[1]
                    + normal[1] * RAIO_INTERRUPTOR
                )

                msp.add_circle(
                    center=centro,
                    radius=RAIO_INTERRUPTOR,
                    dxfattribs={
                        "layer":
                            "PROJ_ELETRICA_INTERRUPTOR"
                    }
                )

                pontos_gerados.append({
                    "ambiente": nome,
                    "tipo": "INTERRUPTOR",
                    "ponto": centro,
                })

    return pontos_gerados
