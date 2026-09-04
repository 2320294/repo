import unicodedata

import math

from geometria import (
    centro_poligono,
    get_inside_normal,
    point_seg_dist,
    ponto_central_interno,
)
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



def _segmentos_ambiente(poly):
    if not poly or len(poly) < 2:
        return []

    return [
        (
            poly[k],
            poly[
                (k + 1)
                % len(poly)
            ]
        )
        for k in range(
            len(poly)
        )
    ]


def _dist_ponto_borda(
    ponto,
    poly
):
    segs = _segmentos_ambiente(
        poly
    )

    if not segs:
        return float("inf")

    return min(
        point_seg_dist(
            ponto[0],
            ponto[1],
            a,
            b
        )
        for a, b in segs
    )


def _ponto_10cm_com_regra_de_canto(
    poly,
    origem,
    referencia,
    afastamento=0.10,
    tolerancia_parede=0.035
):
    """
    Regra Fase 8.2.

    1) Tenta a regra normal: 10 cm após P2/P3, na continuação
       origem -> referência.
    2) Se esse ponto não cair junto a uma parede do ambiente
       (caso típico de porta muito próxima de um canto),
       procura o canto à frente.
    3) A partir da PRÓXIMA parede, posiciona o ponto a 10 cm do canto.

    Retorna:
      (ponto_tangencia, vetor_tangente, criterio)
    """
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

    candidato = (
        referencia[0]
        + ux * afastamento,
        referencia[1]
        + uy * afastamento
    )

    # Regra normal funciona: candidato permanece sobre/ao lado
    # da parede real do ambiente.
    if _dist_ponto_borda(
        candidato,
        poly
    ) <= tolerancia_parede:
        return (
            candidato,
            (ux, uy),
            "10CM_APOS_REFERENCIA"
        )

    # Há provavelmente um canto antes dos 10 cm.
    # Procura vértice à frente da referência, próximo à linha
    # de continuação da soleira.
    candidatos_canto = []

    for vert in poly:
        rx = (
            vert[0]
            - referencia[0]
        )
        ry = (
            vert[1]
            - referencia[1]
        )

        proj = (
            rx * ux
            + ry * uy
        )

        lateral = abs(
            rx * (-uy)
            + ry * ux
        )

        if (
            -0.02 <= proj <= afastamento + 0.06
            and lateral <= 0.06
        ):
            candidatos_canto.append(
                (
                    max(proj, 0.0),
                    vert
                )
            )

    if not candidatos_canto:
        # Fallback seguro: não inventa posição fora da parede.
        return (
            candidato,
            (ux, uy),
            "10CM_APOS_REFERENCIA_FALLBACK"
        )

    candidatos_canto.sort(
        key=lambda item:
            item[0]
    )

    canto = candidatos_canto[
        -1
    ][1]

    # Segmentos que realmente tocam o canto.
    tocando = []

    for a, b in _segmentos_ambiente(poly):
        if (
            _dist(canto, a) <= 0.04
            or _dist(canto, b) <= 0.04
        ):
            outro = (
                b
                if _dist(canto, a)
                <= _dist(canto, b)
                else a
            )

            vx = (
                outro[0]
                - canto[0]
            )
            vy = (
                outro[1]
                - canto[1]
            )

            lc = math.hypot(
                vx,
                vy
            )

            if lc > 1e-9:
                vx /= lc
                vy /= lc

                # Evita voltar pela mesma direção da porta.
                alinhamento = (
                    vx * (-ux)
                    + vy * (-uy)
                )

                tocando.append(
                    (
                        alinhamento,
                        lc,
                        (vx, vy)
                    )
                )

    if not tocando:
        return (
            candidato,
            (ux, uy),
            "10CM_APOS_REFERENCIA_FALLBACK"
        )

    # Preferimos o segmento que MENOS retorna para a porta,
    # isto é, a próxima parede depois do canto.
    tocando.sort(
        key=lambda item:
            item[0]
    )

    _, comp_parede, vetor = (
        tocando[0]
    )

    distancia = min(
        afastamento,
        max(
            0.02,
            comp_parede * 0.45
        )
    )

    ponto = (
        canto[0]
        + vetor[0] * distancia,
        canto[1]
        + vetor[1] * distancia
    )

    return (
        ponto,
        vetor,
        "10CM_APOS_PROXIMA_PAREDE"
    )

def _geometria_interruptor(
    ambiente,
    soleira,
    porta_geom
):
    """
    Regra Fase 8.2:

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

    ajuste = (
        _ponto_10cm_com_regra_de_canto(
            ambiente["poly"],
            origem,
            referencia,
            afastamento=
                AFASTAMENTO_APOS_REFERENCIA
        )
    )

    if ajuste is None:
        return None

    (
        ponto_tangencia,
        vetor_parede,
        criterio_posicao
    ) = ajuste

    ux, uy = (
        vetor_parede
    )

    cx_env, cy_env = (
        ponto_central_interno(
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
        "criterio_posicao":
            criterio_posicao,
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


def _ambiente_sem_interruptor_proprio(nome):
    txt = unicodedata.normalize("NFKD", str(nome or "")).encode("ascii", "ignore").decode("ascii").casefold()
    compacto = "".join(ch for ch in txt if ch.isalnum())
    return any(chave in compacto for chave in ("varanda", "terraco", "garagem"))


def desenhar_interruptores(
    msp,
    polilinhas,
    textos,
    soleiras_raw,
    portas_raw,
    config_interruptores
):
    """
    Fase 8.2:
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

        # Fase 13.6 Rev.7: varanda, terraço e garagem têm comando de iluminação
        # pelo ambiente interno adjacente; nunca desenhar interruptor próprio,
        # mesmo que exista configuração antiga salva no projeto.
        if _ambiente_sem_interruptor_proprio(nome):
            continue

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
                    geo.get(
                        "criterio_posicao",
                        "10CM_APOS_REFERENCIA"
                    ),
                "diametro_m": 0.10,
                "p1": rot["p1"],
                "p2": rot["p2"],
                "p3": rot["p3"],
                "p4": rot["p4"],
            })

    return pontos_gerados
