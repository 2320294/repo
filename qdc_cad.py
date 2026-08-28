from geometria import (
    point_seg_dist,
    get_inside_normal
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
    qdc_formatado = str(
        local_qdc
    ).replace(
        " (recomendado)",
        ""
    ).strip().upper()

    nome_atual_upper = (
        nome.strip().upper()
        if nome
        else ""
    )

    if (
        nome_atual_upper != qdc_formatado
        or not logical_walls
    ):
        return None

    qdc_w = 0.4
    qdc_d = 0.15

    maior_parede = max(
        logical_walls,
        key=lambda w:
        w["length"]
    )

    pt1 = maior_parede["p1"]
    pt2 = maior_parede["p2"]

    is_vertical = (
        abs(pt1[0] - pt2[0])
        <
        abs(pt1[1] - pt2[1])
    )

    cortes_portas = []

    for p in unique_portas:
        d_p1 = point_seg_dist(
            p["p1"][0],
            p["p1"][1],
            pt1,
            pt2
        )

        d_p2 = point_seg_dist(
            p["p2"][0],
            p["p2"][1],
            pt1,
            pt2
        )

        if d_p1 < 0.6 or d_p2 < 0.6:
            if is_vertical:
                cortes_portas.append(
                    (
                        min(
                            p["p1"][1],
                            p["p2"][1]
                        ),
                        max(
                            p["p1"][1],
                            p["p2"][1]
                        )
                    )
                )
            else:
                cortes_portas.append(
                    (
                        min(
                            p["p1"][0],
                            p["p2"][0]
                        ),
                        max(
                            p["p1"][0],
                            p["p2"][0]
                        )
                    )
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

        cortes_portas.sort(
            key=lambda x:
            x[0]
        )

        trechos_livres = []
        cursor = parede_min

        for c_inf, c_sup in cortes_portas:
            if c_inf > cursor + 0.1:
                trechos_livres.append(
                    (
                        cursor,
                        c_inf
                    )
                )

            cursor = max(
                cursor,
                c_sup
            )

        if cursor < parede_max - 0.1:
            trechos_livres.append(
                (
                    cursor,
                    parede_max
                )
            )

        if trechos_livres:
            melhor_trecho = max(
                trechos_livres,
                key=lambda t:
                t[1] - t[0]
            )

            my = (
                melhor_trecho[0]
                +
                melhor_trecho[1]
            ) / 2

            mx = pt1[0]

        else:
            mx = (
                pt1[0] + pt2[0]
            ) / 2

            my = (
                pt1[1] + pt2[1]
            ) / 2

    else:
        parede_min = min(
            pt1[0],
            pt2[0]
        )

        parede_max = max(
            pt1[0],
            pt2[0]
        )

        cortes_portas.sort(
            key=lambda x:
            x[0]
        )

        trechos_livres = []
        cursor = parede_min

        for c_inf, c_sup in cortes_portas:
            if c_inf > cursor + 0.1:
                trechos_livres.append(
                    (
                        cursor,
                        c_inf
                    )
                )

            cursor = max(
                cursor,
                c_sup
            )

        if cursor < parede_max - 0.1:
            trechos_livres.append(
                (
                    cursor,
                    parede_max
                )
            )

        if trechos_livres:
            melhor_trecho = max(
                trechos_livres,
                key=lambda t:
                t[1] - t[0]
            )

            mx = (
                melhor_trecho[0]
                +
                melhor_trecho[1]
            ) / 2

            my = pt1[1]

        else:
            mx = (
                pt1[0] + pt2[0]
            ) / 2

            my = (
                pt1[1] + pt2[1]
            ) / 2

    vx = maior_parede["vx"]
    vy = maior_parede["vy"]

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
        pts_qdc + [pts_qdc[0]],
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

    # Identificação gráfica explícita do quadro. O ponto de origem dos
    # circuitos continua sendo (mx, my), isto é, exatamente a posição
    # calculada na parede do ambiente escolhido pelo usuário.
    msp.add_text(
        "QDC",
        dxfattribs={
            "layer": "PROJ_ELETRICA_TEXTO",
            "height": 0.12,
            "insert": (
                mx + out_nx * (qdc_d + 0.10),
                my + out_ny * (qdc_d + 0.10),
            ),
        },
    )

    return {
        "centro": (mx, my),
        "centro_externo": (
            mx + out_nx * qdc_d / 2,
            my + out_ny * qdc_d / 2
        ),
        "pontos": pts_qdc,
        "ambiente": nome,
        "parede": {
            "p1": pt1,
            "p2": pt2,
            "vx": vx,
            "vy": vy,
        },
    }

