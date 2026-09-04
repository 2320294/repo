import math

# ============================================================
# FASE 8.10 — PADRÃO GEOMÉTRICO DAS TOMADAS
# ============================================================
# Novo padrão:
#   - base total do triângulo: 15 cm
#   - o triângulo NÃO nasce mais sobre a parede;
#   - sua base fica na ponta interna do traço central;
#   - traço central total: 10 cm;
#   - 5 cm do traço ficam para dentro do ambiente;
#   - 5 cm ficam para fora da face interna da parede;
#   - profundidade do triângulo: 15 cm.
TOMADA_MEIA_BASE = 0.075
TOMADA_PROFUNDIDADE = 0.15
TOMADA_TRACO_TOTAL = 0.10
TOMADA_TRACO_MEIO = TOMADA_TRACO_TOTAL / 2.0


from geometria import (
    point_seg_dist,
    get_ponto_perimetro,
    get_inside_normal,
    get_inside_normal_polygon
)




def _geometria_simbolo_tomada(
    px,
    py,
    vx,
    vy,
    nx,
    ny
):
    """
    Fase 13.6 Rev.15.

    px,py continuam sendo o ponto da parede.

    O traço central mede 10 cm e fica atravessando a parede:
      - 5 cm para dentro do ambiente;
      - 5 cm para fora.

    A BASE do triângulo fica na ponta interna desse traço,
    isto é, 5 cm afastada da parede para dentro do ambiente.

    O triângulo tem:
      - base total = 15 cm;
      - profundidade = 15 cm.
    """
    centro_base_x = (
        px
        + nx
        * TOMADA_TRACO_MEIO
    )
    centro_base_y = (
        py
        + ny
        * TOMADA_TRACO_MEIO
    )

    ponto_b1 = (
        centro_base_x
        - vx
        * TOMADA_MEIA_BASE,
        centro_base_y
        - vy
        * TOMADA_MEIA_BASE
    )

    ponto_b2 = (
        centro_base_x
        + vx
        * TOMADA_MEIA_BASE,
        centro_base_y
        + vy
        * TOMADA_MEIA_BASE
    )

    ponto_pt = (
        centro_base_x
        + nx
        * TOMADA_PROFUNDIDADE,
        centro_base_y
        + ny
        * TOMADA_PROFUNDIDADE
    )

    ponto_traco_externo = (
        px
        - nx
        * TOMADA_TRACO_MEIO,
        py
        - ny
        * TOMADA_TRACO_MEIO
    )

    ponto_traco_interno = (
        px
        + nx
        * TOMADA_TRACO_MEIO,
        py
        + ny
        * TOMADA_TRACO_MEIO
    )

    return (
        ponto_b1,
        ponto_b2,
        ponto_pt,
        ponto_traco_externo,
        ponto_traco_interno
    )



def _adicionar_traco_base_tomada(
    msp,
    ponto_traco_externo,
    ponto_traco_interno
):
    """
    Traço total de 10 cm cruzando a parede:
    5 cm para dentro e 5 cm para fora.
    A ponta interna coincide com o centro da base do triângulo.
    """
    msp.add_line(
        ponto_traco_externo,
        ponto_traco_interno,
        dxfattribs={
            "layer":
                "PROJ_ELETRICA_TOMADA"
        }
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

    # Fase 13.6 Rev.15:
    # prioridade absoluta para o identificador único (ex.: "WC 2").
    # Compatibilidade somente para projetos antigos que tenham salvo
    # a configuração usando o nome-base.
    if not lista:
        import re

        nome_base = re.sub(
            r"\s+\d+$",
            "",
            str(
                ambiente
            ).strip()
        )

        if nome_base != ambiente:
            lista = (
                config_tomadas_altas.get(
                    nome_base
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



def _distancia_perimetro_do_ponto(
    ponto,
    segmentos_crus
):
    """
    Projeta um ponto no segmento de perímetro mais próximo e retorna
    a distância acumulada nesse perímetro.
    """
    if not ponto or not segmentos_crus:
        return None

    px, py = map(float, ponto)
    acumulada = 0.0
    melhor = None

    for p1, p2, comprimento in segmentos_crus:
        x1, y1 = map(float, p1)
        x2, y2 = map(float, p2)
        dx = x2 - x1
        dy = y2 - y1
        l2 = dx*dx + dy*dy

        if l2 <= 1e-12:
            acumulada += float(comprimento)
            continue

        t = (
            (px-x1)*dx
            + (py-y1)*dy
        ) / l2

        t = max(
            0.0,
            min(
                1.0,
                t
            )
        )

        qx = x1 + t*dx
        qy = y1 + t*dy
        d = math.hypot(
            px-qx,
            py-qy
        )

        candidato = (
            d,
            acumulada
            + t
            * float(comprimento)
        )

        if (
            melhor is None
            or candidato[0]
            < melhor[0]
        ):
            melhor = candidato

        acumulada += float(
            comprimento
        )

    return (
        melhor[1]
        if melhor
        else None
    )


def _interruptor_referencia_ambiente(
    nome,
    pontos_interruptores
):
    """
    Seleciona o interruptor do próprio ambiente.
    Se houver paralelos, usa o primeiro encontrado no sentido
    de cadastro; as TUGs continuam uma única sequência perimetral.
    """
    chave = str(
        nome or ""
    ).casefold().strip()

    candidatos = [
        p
        for p in (
            pontos_interruptores
            or []
        )
        if (
            str(
                p.get(
                    "ambiente",
                    ""
                )
            ).casefold().strip()
            == chave
            and p.get(
                "ponto_tangencia"
                or p.get(
                    "ponto"
                )
            )
        )
    ]

    if not candidatos:
        return None

    return candidatos[0]


def _ponto_valido_no_sentido(
    distancia_inicial,
    sentido,
    comp_total,
    segmentos_crus,
    polilinha,
    portas_raw,
    soleiras_raw,
    max_busca=None
):
    """
    Busca um ponto válido exclusivamente no sentido escolhido
    (+1 ou -1) ao longo do perímetro.
    """
    if comp_total <= 0:
        return None

    sentido = 1 if sentido >= 0 else -1
    passo = 0.05
    limite = (
        float(max_busca)
        if max_busca is not None
        else float(comp_total)
    )

    desloc = 0.0

    while desloc <= limite + 1e-9:
        d = (
            float(distancia_inicial)
            + sentido * desloc
        ) % float(comp_total)

        px, py, vx, vy = get_ponto_perimetro(
            d,
            segmentos_crus
        )

        if ponto_tomada_valido(
            px,
            py,
            polilinha,
            portas_raw,
            soleiras_raw
        ):
            return (
                d,
                px,
                py,
                vx,
                vy
            )

        desloc += passo

    return None


def _avaliar_sentido_saida_interruptor(
    d_int,
    sentido,
    comp_total,
    segmentos_crus,
    polilinha,
    portas_raw,
    soleiras_raw
):
    """
    Avalia qual lado do interruptor é o lado útil da parede.

    Prioridades:
    - conseguir a primeira TUG o mais próximo possível dos 20 cm;
    - não atravessar imediatamente porta/soleira;
    - manter maior trecho livre contínuo após o interruptor.
    """
    sentido = 1 if sentido >= 0 else -1

    primeira = _ponto_valido_no_sentido(
        d_int + sentido * 0.20,
        sentido,
        comp_total,
        segmentos_crus,
        polilinha,
        portas_raw,
        soleiras_raw,
        max_busca=min(
            comp_total,
            2.50
        )
    )

    if primeira is None:
        return None

    # Distância efetiva percorrida desde o interruptor até a primeira TUG.
    delta = (
        (primeira[0] - d_int)
        if sentido > 0
        else (d_int - primeira[0])
    ) % comp_total

    # Mede quanto do caminho logo após o interruptor permanece utilizável.
    # Quanto maior, melhor o lado para iniciar a distribuição.
    amostras_validas = 0
    for k in range(1, 17):
        d = (
            d_int
            + sentido * (
                0.20
                + k * 0.20
            )
        ) % comp_total

        px, py, _, _ = get_ponto_perimetro(
            d,
            segmentos_crus
        )

        if ponto_tomada_valido(
            px,
            py,
            polilinha,
            portas_raw,
            soleiras_raw
        ):
            amostras_validas += 1
        else:
            # Obstáculo cedo reduz fortemente a preferência por este lado.
            break

    return {
        "sentido": sentido,
        "primeira": primeira,
        "delta_primeira": delta,
        "trecho_livre": amostras_validas,
    }


def _distancias_tugs_desde_interruptor(
    qtd_tugs,
    comp_total,
    segmentos_crus,
    polilinha,
    portas_raw,
    soleiras_raw,
    ponto_interruptor
):
    """
    Fase 13.6 Rev.15

    O sistema testa os DOIS lados do interruptor.
    Escolhe o lado que oferece saída útil pela parede, evitando começar
    pelo lado da soleira/porta.

    A primeira TUG fica a 20 cm quando esse ponto é válido.
    Se houver obstáculo, desloca somente no sentido escolhido.
    As demais continuam nesse mesmo sentido.
    """
    if (
        qtd_tugs <= 0
        or comp_total <= 0
        or not ponto_interruptor
    ):
        return []

    d_int = _distancia_perimetro_do_ponto(
        ponto_interruptor,
        segmentos_crus
    )

    if d_int is None:
        return []

    opcoes = []

    for sentido in (1, -1):
        avaliacao = _avaliar_sentido_saida_interruptor(
            d_int,
            sentido,
            comp_total,
            segmentos_crus,
            polilinha,
            portas_raw,
            soleiras_raw
        )
        if avaliacao:
            opcoes.append(avaliacao)

    if not opcoes:
        return []

    # Primeiro privilegia o maior corredor livre.
    # Em empate, privilegia a TUG mais próxima dos 20 cm.
    melhor = max(
        opcoes,
        key=lambda a: (
            a["trecho_livre"],
            -abs(
                a["delta_primeira"]
                - 0.20
            )
        )
    )

    sentido = melhor["sentido"]
    primeira = melhor["primeira"]

    resultados = [primeira]

    if qtd_tugs == 1:
        return resultados

    d_primeira = primeira[0]
    reserva_final = 0.35

    comprimento_restante = max(
        0.0,
        comp_total
        - melhor["delta_primeira"]
        - reserva_final
    )

    passo_base = (
        comprimento_restante
        / qtd_tugs
    )

    usados = [d_primeira]

    for i in range(1, qtd_tugs):
        alvo = (
            d_primeira
            + sentido * i * passo_base
        ) % comp_total

        achado = _ponto_valido_no_sentido(
            alvo,
            sentido,
            comp_total,
            segmentos_crus,
            polilinha,
            portas_raw,
            soleiras_raw,
            max_busca=max(
                0.60,
                passo_base
            )
        )

        if achado is None:
            continue

        d = achado[0]

        if any(
            min(
                abs(d-u),
                comp_total-abs(d-u)
            ) < 0.35
            for u in usados
        ):
            achado = _ponto_valido_no_sentido(
                d + sentido * 0.35,
                sentido,
                comp_total,
                segmentos_crus,
                polilinha,
                portas_raw,
                soleiras_raw,
                max_busca=max(
                    0.60,
                    passo_base
                )
            )

            if achado is None:
                continue

            d = achado[0]

        usados.append(d)
        resultados.append(achado)

    return resultados


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
    config_tomadas_altas=None,
    pontos_interruptores=None
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

    # Fase 13.6 Rev.15 — classificação por altura preservada da Fase 8.3.
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
            # Fase 13.6 Rev.15:
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

            (
                ponto_b1,
                ponto_b2,
                ponto_pt,
                ponto_traco_externo,
                ponto_traco_interno
            ) = _geometria_simbolo_tomada(
                px,
                py,
                vx,
                vy,
                nx,
                ny
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

            _adicionar_traco_base_tomada(
                msp,
                ponto_traco_externo,
                ponto_traco_interno
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
                        ponto_traco_interno,
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
                # Fase 13.6 Rev.15: o ramal dedicado chega no extremo do
                # traço central que fica embutido na parede.
                "ponto_conexao_parede":
                    ponto_traco_externo,
                "ponto_conexao_ambiente":
                    ponto_traco_interno,
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

    # TUG — FASE 13.6 REV.1
    if qtd_tugs > 0 and comp_total > 0:
        interruptor_ref = (
            _interruptor_referencia_ambiente(
                nome,
                pontos_interruptores
            )
        )

        resultados_tug = []

        if interruptor_ref:
            ponto_ref = (
                interruptor_ref.get(
                    "ponto_tangencia"
                )
                or interruptor_ref.get(
                    "ponto"
                )
            )

            resultados_tug = (
                _distancias_tugs_desde_interruptor(
                    qtd_tugs,
                    comp_total,
                    segmentos_crus,
                    polilinha,
                    portas_raw,
                    soleiras_raw,
                    ponto_ref
                )
            )

        # Ambientes sem interruptor próprio ou eventual fallback geométrico
        # preservam a distribuição anterior para não perder tomadas.
        if not resultados_tug:
            margem_inicial = 0.35
            comprimento_util = (
                comp_total
                - 2 * margem_inicial
            )

            if comprimento_util > 0:
                passo = (
                    comprimento_util
                    / qtd_tugs
                )
                inicio_offset = (
                    margem_inicial
                    + passo / 2
                )
            else:
                passo = (
                    comp_total
                    / qtd_tugs
                )
                inicio_offset = (
                    passo / 2
                )

            for i in range(
                qtd_tugs
            ):
                distancia_desejada = (
                    inicio_offset
                    + i * passo
                )

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

                px, py, seg_vx, seg_vy = resultado

                resultados_tug.append(
                    (
                        distancia_desejada,
                        px,
                        py,
                        seg_vx,
                        seg_vy
                    )
                )

        # Desenha na ordem perimetral calculada.
        for ordem_tug, resultado in enumerate(
            resultados_tug[:qtd_tugs],
            start=1
        ):
            (
                distancia_perimetro,
                px,
                py,
                seg_vx,
                seg_vy
            ) = resultado

            if not ponto_tomada_valido(
                px,
                py,
                polilinha,
                portas_raw,
                soleiras_raw
            ):
                continue

            nx, ny = get_inside_normal_polygon(
                seg_vx,
                seg_vy,
                px,
                py,
                polilinha,
                probe=0.05,
                cx=centro_x,
                cy=centro_y
            )

            (
                ponto_b1,
                ponto_b2,
                ponto_pt,
                ponto_traco_externo,
                ponto_traco_interno
            ) = _geometria_simbolo_tomada(
                px,
                py,
                seg_vx,
                seg_vy,
                nx,
                ny
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

            _adicionar_traco_base_tomada(
                msp,
                ponto_traco_externo,
                ponto_traco_interno
            )

            if is_ambiente_molhado:
                msp.add_solid(
                    [
                        ponto_b1,
                        ponto_traco_interno,
                        ponto_pt
                    ],
                    dxfattribs={
                        "layer":
                            "PROJ_ELETRICA_TOMADA"
                    }
                )

            pontos_gerados.append({
                "ambiente":
                    nome,
                "tipo":
                    "TUG",
                "ponto":
                    (px, py),
                "ponto_conexao_parede":
                    ponto_traco_externo
                ,
                "ponto_conexao_ambiente":
                    ponto_traco_interno,
                "potencia":
                    (
                        600
                        if is_ambiente_molhado
                        else 100
                    ),
                "altura":
                    (
                        "MEDIA"
                        if is_ambiente_molhado
                        else "BAIXA"
                    ),
                "grupo_distribuicao":
                    (
                        "TOMADA_MEDIA"
                        if is_ambiente_molhado
                        else "TOMADA_BAIXA"
                    ),
                "ordem_perimetro":
                    ordem_tug,
                "distancia_perimetro":
                    float(
                        distancia_perimetro
                    ),
                "origem_distribuicao":
                    (
                        "20CM_APOS_INTERRUPTOR"
                        if interruptor_ref
                        else "FALLBACK_DISTRIBUICAO"
                    ),
            })

    return pontos_gerados
