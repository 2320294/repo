from geometria import (
    point_seg_dist,
    get_inside_normal
)
from qdc_config import (
    decodificar_qdc_completo
)


def _centro_fallback_parede(
    parede,
    unique_portas
):
    """
    Compatibilidade com projetos antigos:
    quando não existem t0/t1 salvos, procura o maior trecho
    livre de portas na parede escolhida.
    """
    pt1 = parede["p1"]
    pt2 = parede["p2"]

    is_vertical = (
        abs(
            pt1[0] - pt2[0]
        )
        <
        abs(
            pt1[1] - pt2[1]
        )
    )

    cortes_portas = []

    for porta in unique_portas:
        d_p1 = point_seg_dist(
            porta["p1"][0],
            porta["p1"][1],
            pt1,
            pt2
        )

        d_p2 = point_seg_dist(
            porta["p2"][0],
            porta["p2"][1],
            pt1,
            pt2
        )

        if (
            d_p1 < 0.6
            or d_p2 < 0.6
        ):
            if is_vertical:
                cortes_portas.append(
                    (
                        min(
                            porta["p1"][1],
                            porta["p2"][1]
                        ),
                        max(
                            porta["p1"][1],
                            porta["p2"][1]
                        )
                    )
                )
            else:
                cortes_portas.append(
                    (
                        min(
                            porta["p1"][0],
                            porta["p2"][0]
                        ),
                        max(
                            porta["p1"][0],
                            porta["p2"][0]
                        )
                    )
                )

    cortes_portas.sort(
        key=lambda item:
            item[0]
    )

    if is_vertical:
        parede_min = min(
            pt1[1],
            pt2[1]
        )
        parede_max = max(
            pt1[1],
            pt2[1]
        )
    else:
        parede_min = min(
            pt1[0],
            pt2[0]
        )
        parede_max = max(
            pt1[0],
            pt2[0]
        )

    trechos_livres = []
    cursor = parede_min

    for corte_ini, corte_fim in cortes_portas:
        if (
            corte_ini
            > cursor + 0.1
        ):
            trechos_livres.append(
                (
                    cursor,
                    corte_ini
                )
            )

        cursor = max(
            cursor,
            corte_fim
        )

    if (
        cursor
        < parede_max - 0.1
    ):
        trechos_livres.append(
            (
                cursor,
                parede_max
            )
        )

    if trechos_livres:
        melhor = max(
            trechos_livres,
            key=lambda trecho:
                trecho[1]
                - trecho[0]
        )

        meio = (
            melhor[0]
            + melhor[1]
        ) / 2.0

        if is_vertical:
            return (
                pt1[0],
                meio
            )

        return (
            meio,
            pt1[1]
        )

    return (
        (
            pt1[0]
            + pt2[0]
        ) / 2.0,
        (
            pt1[1]
            + pt2[1]
        ) / 2.0
    )


def desenhar_qdc(
    msp,
    logical_walls,
    unique_portas,
    local_qdc,
    nome,
    centro_x,
    centro_y
):
    dados_qdc = (
        decodificar_qdc_completo(
            local_qdc
        )
    )

    ambiente_qdc = (
        dados_qdc[
            "ambiente"
        ]
    )

    parede_numero = (
        dados_qdc[
            "parede_numero"
        ]
    )

    trecho_numero = (
        dados_qdc[
            "trecho_numero"
        ]
    )

    trecho_t0 = (
        dados_qdc[
            "t0"
        ]
    )

    trecho_t1 = (
        dados_qdc[
            "t1"
        ]
    )

    qdc_formatado = (
        str(
            ambiente_qdc
        )
        .replace(
            " (recomendado)",
            ""
        )
        .strip()
        .upper()
    )

    nome_atual_upper = (
        nome.strip().upper()
        if nome
        else ""
    )

    if (
        nome_atual_upper
        != qdc_formatado
        or not logical_walls
    ):
        return None

    qdc_w = 0.4
    qdc_d = 0.15

    if (
        parede_numero is not None
        and 1 <= parede_numero
        <= len(logical_walls)
    ):
        parede = (
            logical_walls[
                parede_numero - 1
            ]
        )
    else:
        # Projeto antigo sem parede salva.
        parede = max(
            logical_walls,
            key=lambda wall:
                wall["length"]
        )

    pt1 = parede["p1"]
    pt2 = parede["p2"]

    # =========================================================
    # FASE 8.0 — CENTRO DO TRECHO ESCOLHIDO
    # =========================================================
    if (
        trecho_t0 is not None
        and trecho_t1 is not None
    ):
        t0 = max(
            0.0,
            min(
                1.0,
                float(
                    trecho_t0
                )
            )
        )

        t1 = max(
            0.0,
            min(
                1.0,
                float(
                    trecho_t1
                )
            )
        )

        if t1 < t0:
            t0, t1 = (
                t1,
                t0
            )

        t_meio = (
            t0 + t1
        ) / 2.0

        mx = (
            pt1[0]
            + (
                pt2[0]
                - pt1[0]
            ) * t_meio
        )

        my = (
            pt1[1]
            + (
                pt2[1]
                - pt1[1]
            ) * t_meio
        )

        criterio_posicao = (
            "TRECHO_SELECIONADO"
        )

    else:
        mx, my = (
            _centro_fallback_parede(
                parede,
                unique_portas
            )
        )

        criterio_posicao = (
            "FALLBACK_AUTOMATICO"
        )

    vx = parede["vx"]
    vy = parede["vy"]

    nx, ny = get_inside_normal(
        vx,
        vy,
        mx,
        my,
        centro_x,
        centro_y
    )

    out_nx = -nx
    out_ny = -ny

    p1_qdc = (
        mx - vx * qdc_w / 2,
        my - vy * qdc_w / 2
    )

    p2_qdc = (
        mx + vx * qdc_w / 2,
        my + vy * qdc_w / 2
    )

    p3_qdc = (
        p2_qdc[0]
        + out_nx * qdc_d,
        p2_qdc[1]
        + out_ny * qdc_d
    )

    p4_qdc = (
        p1_qdc[0]
        + out_nx * qdc_d,
        p1_qdc[1]
        + out_ny * qdc_d
    )

    pts_qdc = [
        p1_qdc,
        p2_qdc,
        p3_qdc,
        p4_qdc
    ]

    msp.add_lwpolyline(
        pts_qdc + [
            pts_qdc[0]
        ],
        dxfattribs={
            "layer":
                "PROJ_ELETRICA_QDC"
        }
    )

    msp.add_solid(
        pts_qdc[:3],
        dxfattribs={
            "layer":
                "PROJ_ELETRICA_QDC"
        }
    )

    # Fase 8.0:
    # somente o símbolo do QDC, sem legenda textual.

    return {
        "centro": (
            mx,
            my
        ),
        "centro_externo": (
            mx
            + out_nx
            * qdc_d / 2,
            my
            + out_ny
            * qdc_d / 2
        ),
        "pontos":
            pts_qdc,
        "ambiente":
            nome,
        "parede_numero":
            parede_numero,
        "trecho_numero":
            trecho_numero,
        "trecho_t0":
            trecho_t0,
        "trecho_t1":
            trecho_t1,
        "criterio_posicao":
            criterio_posicao,
        "parede": {
            "p1":
                pt1,
            "p2":
                pt2,
            "vx":
                vx,
            "vy":
                vy
        }
    }
