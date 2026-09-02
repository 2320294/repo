import math

from geometria import (
    point_seg_dist,
    get_ponto_perimetro,
    get_inside_normal,
    get_inside_normal_polygon
)



def _segmentos_soleira(soleira):
    """
    Retorna todas as arestas conhecidas da soleira.
    Fase 8.2: não valida apenas p1-p2; usa o retângulo inteiro.
    """
    verts = [
        (
            float(p[0]),
            float(p[1])
        )
        for p in (
            soleira.get("vertices")
            or []
        )
    ]

    if len(verts) >= 2:
        return [
            (
                verts[i],
                verts[
                    (i + 1)
                    % len(verts)
                ]
            )
            for i in range(
                len(verts)
            )
        ]

    if (
        soleira.get("p1") is not None
        and soleira.get("p2") is not None
    ):
        return [
            (
                soleira["p1"],
                soleira["p2"]
            )
        ]

    return []


def _distancia_a_soleira(
    px,
    py,
    soleira
):
    segs = _segmentos_soleira(
        soleira
    )

    if not segs:
        return float("inf")

    return min(
        point_seg_dist(
            px,
            py,
            a,
            b
        )
        for a, b in segs
    )

def ponto_tomada_valido(
    px,
    py,
    polilinha,
    portas_raw,
    soleiras_raw,
    distancia_canto=0.35,
    distancia_porta=0.40,
    distancia_soleira=0.40
):
    for vx, vy in polilinha:
        if math.hypot(
            px - vx,
            py - vy
        ) < distancia_canto:
            return False

    for porta in portas_raw:
        if point_seg_dist(
            px,
            py,
            porta["p1"],
            porta["p2"]
        ) < distancia_porta:
            return False

    for soleira in soleiras_raw:
        if _distancia_a_soleira(
            px,
            py,
            soleira
        ) < distancia_soleira:
            return False

    return True


def procurar_ponto_valido_perimetro(
    distancia_original,
    comp_total,
    segmentos_crus,
    polilinha,
    portas_raw,
    soleiras_raw
):
    if comp_total <= 0:
        return None

    px, py, vx, vy = get_ponto_perimetro(
        distancia_original,
        segmentos_crus
    )

    if ponto_tomada_valido(
        px,
        py,
        polilinha,
        portas_raw,
        soleiras_raw
    ):
        return px, py, vx, vy

    passo_busca = min(
        max(
            comp_total * 0.01,
            0.10
        ),
        0.50
    )

    max_busca = min(
        comp_total * 0.20,
        2.00
    )

    deslocamento = passo_busca

    while deslocamento <= max_busca:
        for distancia_teste in [
            distancia_original - deslocamento,
            distancia_original + deslocamento
        ]:
            if (
                distancia_teste <= 0
                or distancia_teste >= comp_total
            ):
                continue

            tx, ty, tvx, tvy = (
                get_ponto_perimetro(
                    distancia_teste,
                    segmentos_crus
                )
            )

            if ponto_tomada_valido(
                tx,
                ty,
                polilinha,
                portas_raw,
                soleiras_raw
            ):
                return (
                    tx,
                    ty,
                    tvx,
                    tvy
                )

        deslocamento += passo_busca

    return None



def _selecao_tomada_alta(
    config_tomadas_altas,
    ambiente,
    indice
):
    if not isinstance(
        config_tomadas_altas,
        dict
    ):
        return None

    lista = (
        config_tomadas_altas.get(
            ambiente
        )
        or []
    )

    if (
        not isinstance(
            lista,
            list
        )
        or indice >= len(
            lista
        )
    ):
        return None

    item = lista[
        indice
    ]

    return (
        item
        if isinstance(
            item,
            dict
        )
        else None
    )


def _parede_e_posicao_selecionados(
    logical_walls,
    selecao
):
    if not selecao:
        return None

    try:
        numero = int(
            selecao.get(
                "parede_numero"
            )
        )

        t0 = float(
            selecao.get(
                "t0"
            )
        )

        t1 = float(
            selecao.get(
                "t1"
            )
        )
    except Exception:
        return None

    if not (
        1 <= numero
        <= len(
            logical_walls
        )
    ):
        return None

    parede = (
        logical_walls[
            numero - 1
        ]
    )

    t0 = max(
        0.0,
        min(
            1.0,
            t0
        )
    )

    t1 = max(
        0.0,
        min(
            1.0,
            t1
        )
    )

    if t1 < t0:
        t0, t1 = (
            t1,
            t0
        )

    posicao_t = (
        selecao.get(
            "posicao_t"
        )
    )

    try:
        tm = float(
            posicao_t
        )
    except Exception:
        tm = (
            t0 + t1
        ) / 2.0

    tm = max(
        t0,
        min(
            t1,
            tm
        )
    )

    pt1 = parede[
        "p1"
    ]
    pt2 = parede[
        "p2"
    ]

    px = (
        pt1[0]
        + (
            pt2[0]
            - pt1[0]
        ) * tm
    )

    py = (
        pt1[1]
        + (
            pt2[1]
            - pt1[1]
        ) * tm
    )

    return (
        parede,
        px,
        py
    )


def desenhar_tomadas(
    msp,
    row_data,
    nome,
    polilinha,
    logical_walls,
    segmentos_crus,
    comp_total,
    unique_portas,
    portas_raw,
    soleiras_raw,
    centro_x,
    centro_y,
    config_tomadas_altas=None
):
    if not row_data:
        return []

    pontos_gerados = []

    qtd_tugs = int(
        row_data.get(
            "Qtd TUG",
            row_data.get(
                "TUGs (Qtd)",
                row_data.get(
                    "TUGs",
                    0
                )
            )
        )
    )

    qtd_tue = int(
        row_data.get(
            "Qtd TUE",
            row_data.get(
                "TUE",
                0
            )
        )
    )

    eq_tue_nome = str(
        row_data.get(
            "Equipamento TUE",
            "-"
        )
    )

    pot_tue_val = int(
        row_data.get(
            "Pot. Unit. TUE (W)",
            row_data.get(
                "Pot. Unit. TUE (VA)",
                0
            )
        )
    )

    if pot_tue_val == 0:
        eq_lower = (
            eq_tue_nome.lower()
        )

        if "chuveiro" in eq_lower:
            pot_tue_val = 5500

        elif "ar" in eq_lower:
            pot_tue_val = 1200

        elif (
            "micro" in eq_lower
            or "forno" in eq_lower
        ):
            pot_tue_val = 2000

        elif (
            "máquina" in eq_lower
            or "lavar" in eq_lower
        ):
            pot_tue_val = 1000

        else:
            pot_tue_val = 1000

    eq_lower = (
        eq_tue_nome.lower()
    )

    is_chuveiro_ou_ac = any(
        x in eq_lower
        for x in [
            "chuveiro",
            "ar-condicionado",
            "ar condicionado"
        ]
    )

    # Fase 8.6 — classificação por altura preservada da Fase 8.3.
    # ALTA: pontos dedicados de chuveiro e ar-condicionado.
    # MEDIA: demais TUEs (micro-ondas/forno, máquina etc.).
    # As TUGs são classificadas mais abaixo conforme o ambiente.
    altura_tue = "ALTA" if is_chuveiro_ou_ac else "MEDIA"

    nome_lower_env = (
        nome.casefold().strip()
    )

    # Remove pontuação/espaços para reconhecer, por exemplo,
    # "A.S.", "A S", "AS" e "Área de Serviço".
    nome_compacto = "".join(
        ch
        for ch in nome_lower_env
        if ch.isalnum()
    )

    is_ambiente_molhado = (
        any(
            x in nome_compacto
            for x in [
                "coz",
                "serv",
                "banh",
                "lav",
                "sanit",
                "wc"
            ]
        )
        or nome_compacto in {
            "as",
            "areadeservico",
            "areaservico"
        }
    )

    # TUE
    if qtd_tue > 0 and logical_walls:
        paredes_candidatas = sorted(
            logical_walls,
            key=lambda w:
            w["length"]
        )

        paredes_sem_porta = [
            w
            for w in paredes_candidatas
            if not any(
                point_seg_dist(
                    (
                        p["p1"][0]
                        +
                        p["p2"][0]
                    ) / 2,
                    (
                        p["p1"][1]
                        +
                        p["p2"][1]
                    ) / 2,
                    w["p1"],
                    w["p2"]
                ) < 0.6
                for p in unique_portas
            )
        ]

        paredes_finais = (
            paredes_sem_porta
            if paredes_sem_porta
            else paredes_candidatas
        )

        for idx_tue in range(
            qtd_tue
        ):
            # Fase 8.6:
            # TUE ALTA usa exatamente o trecho escolhido pelo usuário.
            selecao_alta = (
                _selecao_tomada_alta(
                    config_tomadas_altas,
                    nome,
                    idx_tue
                )
                if altura_tue
                == "ALTA"
                else None
            )

            escolhido = (
                _parede_e_posicao_selecionados(
                    logical_walls,
                    selecao_alta
                )
            )

            if escolhido is not None:
                p_alvo, px, py = (
                    escolhido
                )
                posicao_interativa = True
            else:
                p_alvo = paredes_finais[
                    idx_tue
                    %
                    len(paredes_finais)
                ]

                pt1 = p_alvo["p1"]
                pt2 = p_alvo["p2"]

                fator = (
                    0.5
                    if qtd_tue == 1
                    else (
                        idx_tue + 1
                    ) / (
                        qtd_tue + 1
                    )
                )

                px = (
                    pt1[0]
                    +
                    (
                        pt2[0]
                        - pt1[0]
                    )
                    * fator
                )

                py = (
                    pt1[1]
                    +
                    (
                        pt2[1]
                        - pt1[1]
                    )
                    * fator
                )

                posicao_interativa = False

            # Se o usuário escolheu explicitamente um trecho livre,
            # não deslocamos a tomada para outra parede. O centro do
            # trecho já foi calculado descontando as portas.
            if (
                not posicao_interativa
                and not ponto_tomada_valido(
                px,
                py,
                polilinha,
                portas_raw,
                    soleiras_raw
                )
            ):
                encontrado = None

                for fator_alt in [
                    0.25,
                    0.35,
                    0.65,
                    0.75
                ]:
                    tx = (
                        pt1[0]
                        +
                        (pt2[0] - pt1[0])
                        * fator_alt
                    )

                    ty = (
                        pt1[1]
                        +
                        (pt2[1] - pt1[1])
                        * fator_alt
                    )

                    if ponto_tomada_valido(
                        tx,
                        ty,
                        polilinha,
                        portas_raw,
                        soleiras_raw
                    ):
                        encontrado = (
                            tx,
                            ty
                        )
                        break

                if encontrado:
                    px, py = encontrado
                else:
                    continue

            vx = p_alvo["vx"]
            vy = p_alvo["vy"]

            nx, ny = get_inside_normal_polygon(
                vx, vy, px, py, polilinha,
                probe=0.05, cx=centro_x, cy=centro_y
            )

            ponto_b1 = (
                px - vx * 0.10,
                py - vy * 0.10
            )

            ponto_b2 = (
                px + vx * 0.10,
                py + vy * 0.10
            )

            ponto_pt = (
                px + nx * 0.20,
                py + ny * 0.20
            )

            msp.add_lwpolyline(
                [
                    ponto_b1,
                    ponto_b2,
                    ponto_pt,
                    ponto_b1
                ],
                close=True,
                dxfattribs={
                    "layer":
                        "PROJ_ELETRICA_TOMADA"
                }
            )

            if is_chuveiro_ou_ac:
                msp.add_solid(
                    [
                        ponto_b1,
                        ponto_b2,
                        ponto_pt
                    ],
                    dxfattribs={
                        "layer":
                            "PROJ_ELETRICA_TOMADA"
                    }
                )

            elif is_ambiente_molhado:
                msp.add_solid(
                    [
                        ponto_b1,
                        (px, py),
                        ponto_pt
                    ],
                    dxfattribs={
                        "layer":
                            "PROJ_ELETRICA_TOMADA"
                    }
                )

            msp.add_text(
                f"{pot_tue_val}W",
                dxfattribs={
                    "layer":
                        "PROJ_ELETRICA_TEXTO",
                    "height":
                        0.12,
                    "color":
                        2,
                    "insert":
                        (
                            px + nx * 0.35,
                            py + ny * 0.35
                        )
                }
            )


            pontos_gerados.append({
                "ambiente": nome,
                "tipo": "TUE",
                "ponto": (px, py),
                "potencia": pot_tue_val,
                "equipamento": eq_tue_nome,
                "altura": altura_tue,
                "grupo_distribuicao": f"TOMADA_{altura_tue}",
                "posicionamento_interativo": (
                    bool(
                        posicao_interativa
                    )
                ),
            })

    # TUG
    if qtd_tugs > 0 and comp_total > 0:
        margem_inicial = 0.35

        comprimento_util = (
            comp_total
            -
            2 * margem_inicial
        )

        if comprimento_util > 0:
            passo = (
                comprimento_util
                /
                qtd_tugs
            )

            inicio_offset = (
                margem_inicial
                +
                passo / 2
            )

        else:
            passo = (
                comp_total
                /
                qtd_tugs
            )

            inicio_offset = (
                passo / 2
            )

        distancias_usadas = []

        for i in range(
            qtd_tugs
        ):
            distancia_desejada = (
                inicio_offset
                +
                i * passo
            )

            if (
                distancia_desejada <= 0
                or distancia_desejada >= comp_total
            ):
                continue

            resultado = (
                procurar_ponto_valido_perimetro(
                    distancia_desejada,
                    comp_total,
                    segmentos_crus,
                    polilinha,
                    portas_raw,
                    soleiras_raw
                )
            )

            if resultado is None:
                continue

            px, py, seg_vx, seg_vy = (
                resultado
            )

            if any(
                abs(
                    distancia_desejada - d
                ) < 0.60
                for d in distancias_usadas
            ):
                continue

            if not ponto_tomada_valido(
                px,
                py,
                polilinha,
                portas_raw,
                soleiras_raw
            ):
                continue

            distancias_usadas.append(
                distancia_desejada
            )

            nx, ny = get_inside_normal_polygon(
                seg_vx, seg_vy, px, py, polilinha,
                probe=0.05, cx=centro_x, cy=centro_y
            )

            ponto_b1 = (
                px - seg_vx * 0.10,
                py - seg_vy * 0.10
            )

            ponto_b2 = (
                px + seg_vx * 0.10,
                py + seg_vy * 0.10
            )

            ponto_pt = (
                px + nx * 0.20,
                py + ny * 0.20
            )

            msp.add_lwpolyline(
                [
                    ponto_b1,
                    ponto_b2,
                    ponto_pt,
                    ponto_b1
                ],
                close=True,
                dxfattribs={
                    "layer":
                        "PROJ_ELETRICA_TOMADA"
                }
            )

            if is_ambiente_molhado:
                msp.add_solid(
                    [
                        ponto_b1,
                        (px, py),
                        ponto_pt
                    ],
                    dxfattribs={
                        "layer":
                            "PROJ_ELETRICA_TOMADA"
                    }
                )

            pontos_gerados.append({
                "ambiente": nome,
                "tipo": "TUG",
                "ponto": (px, py),
                "potencia": 600 if is_ambiente_molhado else 100,
                "altura": "MEDIA" if is_ambiente_molhado else "BAIXA",
                "grupo_distribuicao": (
                    "TOMADA_MEDIA" if is_ambiente_molhado else "TOMADA_BAIXA"
                ),
            })

    return pontos_gerados
