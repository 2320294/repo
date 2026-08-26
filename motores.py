import ezdxf
import math
import tempfile
import os


# ============================================================
# CONFIGURAÇÃO DOS INTERRUPTORES / CÍRCULOS
# ============================================================
#
# Para cada ambiente:
#
# "quantidade": 1
#     -> coloca somente 1 círculo
#     -> "porta": define qual porta será utilizada
#
# "quantidade": 2
#     -> coloca 2 círculos
#     -> um em cada porta do ambiente
#     -> nesse caso "porta" não é necessário
#
# EXEMPLO:
#
# CONFIG_INTERRUPTores = {
#     "Sala": {
#         "quantidade": 1,
#         "porta": 1
#     },
#
#     "Cozinha": {
#         "quantidade": 2
#     },
#
#     "Quarto": {
#         "quantidade": 1,
#         "porta": 2
#     }
# }
#
# Se um ambiente NÃO estiver nessa lista, nenhum círculo será
# criado para ele.
#
# A numeração das portas será determinada pela ordem em que
# elas forem identificadas dentro do ambiente.
#
# ============================================================

CONFIG_INTERRUPTores = {

    # EXEMPLOS PARA TESTE:
    #
    # "Sala": {
    #     "quantidade": 1,
    #     "porta": 1
    # },
    #
    # "Cozinha": {
    #     "quantidade": 2
    # },

}


# ============================================================
# CONFIGURAÇÕES GEOMÉTRICAS
# ============================================================

RAIO_CIRCULO_INTERRUPT = 0.15


# ============================================================
# DIMENSIONAMENTO DAS CARGAS
# ============================================================

def dimensionar_cargas(nome, area, perimetro):

    if area <= 0 or perimetro <= 0:

        return {
            "Qtd Ilum.": 0,
            "Pot. Unit. Ilum (VA)": 0,
            "Carga Ilum. (VA)": 0,
            "TUGs (Qtd)": 0,
            "Pot. Unit. TUG (VA)": 0,
            "Carga TUGs (VA)": 0,
            "Equipamento TUE": "-",
            "Qtd TUE": 0,
            "Pot. Unit. TUE (VA)": 0,
            "Carga TUE (VA)": 0
        }

    qtd_ilum = (
        1
        if area <= 10
        else math.ceil(area / 10)
    )

    carga_ilum = (
        100
        if area <= 6
        else
        100 + (((area - 6) // 4) * 60)
    )

    nome_lower = nome.lower().strip()

    nome_words = (
        nome_lower
        .replace('-', ' ')
        .split()
    )

    is_umida = (

        any(
            x in nome_lower
            for x in [
                "coz",
                "serv",
                "banh",
                "lav",
                "sanit",
                "área",
                "area"
            ]
        )

        or

        any(
            w in nome_words
            for w in [
                "as",
                "wc",
                "bwc"
            ]
        )
    )

    is_corredor = any(
        x in nome_lower
        for x in [
            "hall",
            "corredor",
            "circulação",
            "circulacao"
        ]
    )

    if is_umida:

        qtd_tugs = math.ceil(
            perimetro / 3.5
        )

        carga_tugs = (

            qtd_tugs * 600

            if qtd_tugs <= 3

            else

            (3 * 600)
            +
            ((qtd_tugs - 3) * 100)
        )

    elif is_corredor:

        comprimento_estimado = (
            perimetro / 2
        ) - 1

        if comprimento_estimado <= 3:

            qtd_tugs = 1

        else:

            qtd_tugs = max(
                1,
                math.ceil(
                    comprimento_estimado / 3
                )
            )

        carga_tugs = (
            qtd_tugs * 100
        )

    else:

        qtd_tugs = math.ceil(
            perimetro / 5
        )

        carga_tugs = (
            qtd_tugs * 100
        )

    tue_nome = "-"
    qtd_tue = 0
    carga_tue = 0

    if (
        any(
            x in nome_lower
            for x in [
                "banh",
                "sanit"
            ]
        )

        or

        any(
            w in nome_words
            for w in [
                "wc",
                "bwc"
            ]
        )
    ):

        tue_nome = "Chuveiro Elétrico"
        qtd_tue = 1
        carga_tue = 5500

    elif any(
        x in nome_lower
        for x in [
            "coz"
        ]
    ):

        tue_nome = "Micro-ondas/Forno"
        qtd_tue = 1
        carga_tue = 2000

    elif any(
        x in nome_lower
        for x in [
            "quarto",
            "dorm",
            "suite"
        ]
    ):

        tue_nome = "Ar-Condicionado"
        qtd_tue = 1
        carga_tue = 1200

    elif (
        any(
            x in nome_lower
            for x in [
                "serv",
                "lavand"
            ]
        )

        or

        "as" in nome_words
    ):

        tue_nome = "Máquina de Lavar"
        qtd_tue = 1
        carga_tue = 1000

    return {

        "Qtd Ilum.":
            qtd_ilum,

        "Pot. Unit. Ilum (VA)":
            round(
                carga_ilum / qtd_ilum
            )
            if qtd_ilum > 0
            else 0,

        "Carga Ilum. (VA)":
            carga_ilum,

        "TUGs (Qtd)":
            qtd_tugs,

        "Pot. Unit. TUG (VA)":
            600
            if is_umida
            else 100,

        "Carga TUGs (VA)":
            carga_tugs,

        "Equipamento TUE":
            tue_nome,

        "Qtd TUE":
            qtd_tue,

        "Pot. Unit. TUE (VA)":
            round(
                carga_tue /
                max(1, qtd_tue)
            ),

        "Carga TUE (VA)":
            carga_tue
    }


# ============================================================
# GEOMETRIA
# ============================================================

def ponto_em_poligono(
    x,
    y,
    polilinha
):

    if not polilinha:
        return False

    n = len(polilinha)

    dentro = False

    p1x, p1y = polilinha[0]

    for i in range(n + 1):

        p2x, p2y = (
            polilinha[i % n]
        )

        if y > min(p1y, p2y):

            if y <= max(p1y, p2y):

                if x <= max(p1x, p2x):

                    xinters = None

                    if p1y != p2y:

                        xinters = (
                            (y - p1y)
                            *
                            (p2x - p1x)
                            /
                            (p2y - p1y)
                        ) + p1x

                    if (
                        p1x == p2x
                        or
                        (
                            xinters is not None
                            and
                            x <= xinters
                        )
                    ):

                        dentro = not dentro

        p1x, p1y = (
            p2x,
            p2y
        )

    return dentro


def point_seg_dist(
    px,
    py,
    pt1,
    pt2
):

    l2 = (
        (pt1[0] - pt2[0]) ** 2
        +
        (pt1[1] - pt2[1]) ** 2
    )

    if l2 == 0:

        return math.hypot(
            px - pt1[0],
            py - pt1[1]
        )

    t = max(
        0,
        min(
            1,
            (
                (px - pt1[0])
                *
                (pt2[0] - pt1[0])
                +
                (py - pt1[1])
                *
                (pt2[1] - pt1[1])
            )
            /
            l2
        )
    )

    proj_x = (
        pt1[0]
        +
        t *
        (pt2[0] - pt1[0])
    )

    proj_y = (
        pt1[1]
        +
        t *
        (pt2[1] - pt1[1])
    )

    return math.hypot(
        px - proj_x,
        py - proj_y
    )


def get_ponto_perimetro(
    d,
    segs
):

    acumulado = 0

    for pt1, pt2, dst in segs:

        if (
            acumulado + dst >= d
            or
            math.isclose(
                acumulado + dst,
                d,
                abs_tol=1e-5
            )
        ):

            if dst == 0:

                return (
                    pt1[0],
                    pt1[1],
                    0,
                    0
                )

            ratio = (
                d - acumulado
            ) / dst

            x = (
                pt1[0]
                +
                (
                    pt2[0]
                    -
                    pt1[0]
                )
                *
                ratio
            )

            y = (
                pt1[1]
                +
                (
                    pt2[1]
                    -
                    pt1[1]
                )
                *
                ratio
            )

            vx = (
                pt2[0]
                -
                pt1[0]
            ) / dst

            vy = (
                pt2[1]
                -
                pt1[1]
            ) / dst

            return (
                x,
                y,
                vx,
                vy
            )

        acumulado += dst

    pt1, pt2, dst = segs[-1]

    if dst == 0:

        return (
            pt2[0],
            pt2[1],
            0,
            0
        )

    return (

        pt2[0],

        pt2[1],

        (
            pt2[0]
            -
            pt1[0]
        ) / dst,

        (
            pt2[1]
            -
            pt1[1]
        ) / dst
    )


def get_inside_normal(
    vx,
    vy,
    start_x,
    start_y,
    cx,
    cy
):

    n1x, n1y = (
        -vy,
        vx
    )

    n2x, n2y = (
        vy,
        -vx
    )

    d1 = math.hypot(
        cx -
        (
            start_x + n1x
        ),
        cy -
        (
            start_y + n1y
        )
    )

    d2 = math.hypot(
        cx -
        (
            start_x + n2x
        ),
        cy -
        (
            start_y + n2y
        )
    )

    return (

        (
            n1x,
            n1y
        )

        if d1 < d2

        else

        (
            n2x,
            n2y
        )
    )


# ============================================================
# REGRAS DE SEGURANÇA PARA TOMADAS
# ============================================================

DISTANCIA_MINIMA_CANTO_TOMADA = 0.50

DISTANCIA_MINIMA_PORTA_TOMADA = 0.40

DISTANCIA_MINIMA_SOLEIRA_TOMADA = 0.40


# ============================================================
# VERIFICA SE UMA TOMADA ESTÁ EM LOCAL PROIBIDO
# ============================================================

def ponto_tomada_valido(
    px,
    py,
    polilinha,
    portas_raw,
    soleiras_raw,
    distancia_canto=DISTANCIA_MINIMA_CANTO_TOMADA,
    distancia_porta=DISTANCIA_MINIMA_PORTA_TOMADA,
    distancia_soleira=DISTANCIA_MINIMA_SOLEIRA_TOMADA
):

    for vx, vy in polilinha:

        distancia = math.hypot(
            px - vx,
            py - vy
        )

        if distancia < distancia_canto:
            return False

    for porta in portas_raw:

        d = point_seg_dist(
            px,
            py,
            porta['p1'],
            porta['p2']
        )

        if d < distancia_porta:
            return False

    for soleira in soleiras_raw:

        d = point_seg_dist(
            px,
            py,
            soleira['p1'],
            soleira['p2']
        )

        if d < distancia_soleira:
            return False

    return True


# ============================================================
# PROCURA UMA NOVA POSIÇÃO VÁLIDA NO PERÍMETRO
# ============================================================

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

    px, py, vx, vy = (
        get_ponto_perimetro(
            distancia_original,
            segmentos_crus
        )
    )

    if ponto_tomada_valido(
        px,
        py,
        polilinha,
        portas_raw,
        soleiras_raw
    ):

        return (
            px,
            py,
            vx,
            vy
        )

    passo_busca = 0.10

    max_busca = min(
        comp_total * 0.25,
        2.00
    )

    deslocamento = passo_busca

    while deslocamento <= max_busca:

        distancias_teste = [

            distancia_original
            -
            deslocamento,

            distancia_original
            +
            deslocamento
        ]

        for distancia_teste in distancias_teste:

            if distancia_teste <= 0:
                continue

            if distancia_teste >= comp_total:
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


# ============================================================
# PROCURA UMA POSIÇÃO VÁLIDA DENTRO DE UMA PAREDE
# ============================================================

def procurar_ponto_valido_na_parede(
    pt1,
    pt2,
    fator_original,
    polilinha,
    portas_raw,
    soleiras_raw,
    distancia_canto=DISTANCIA_MINIMA_CANTO_TOMADA
):

    dx = (
        pt2[0]
        -
        pt1[0]
    )

    dy = (
        pt2[1]
        -
        pt1[1]
    )

    comprimento = math.hypot(
        dx,
        dy
    )

    if comprimento <= (
        2 *
        distancia_canto
    ):

        return None

    fator_min = (
        distancia_canto
        /
        comprimento
    )

    fator_max = (
        1.0
        -
        distancia_canto
        /
        comprimento
    )

    fator_original = max(
        fator_min,
        min(
            fator_max,
            fator_original
        )
    )

    fatores = [
        fator_original
    ]

    passo_fator = (
        0.10
        /
        comprimento
    )

    deslocamento = passo_fator

    while (
        deslocamento <= 0.50
        and
        deslocamento < 1.0
    ):

        fator_esquerda = (
            fator_original
            -
            deslocamento
        )

        fator_direita = (
            fator_original
            +
            deslocamento
        )

        if fator_esquerda >= fator_min:

            fatores.append(
                fator_esquerda
            )

        if fator_direita <= fator_max:

            fatores.append(
                fator_direita
            )

        deslocamento += passo_fator

    for fator in fatores:

        px = (
            pt1[0]
            +
            dx * fator
        )

        py = (
            pt1[1]
            +
            dy * fator
        )

        if ponto_tomada_valido(
            px,
            py,
            polilinha,
            portas_raw,
            soleiras_raw,
            distancia_canto=distancia_canto
        ):

            vx = (
                dx /
                comprimento
            )

            vy = (
                dy /
                comprimento
            )

            return (
                px,
                py,
                vx,
                vy
            )

    return None


# ============================================================
# PROCESSAMENTO DO DXF
# ============================================================

def processar_dxf(
    caminho_arquivo
):

    doc = ezdxf.readfile(
        caminho_arquivo
    )

    msp = doc.modelspace()

    contagem_camadas = {

        'IA_AMBIENTES': 0,

        'IA_TEXTOS': 0,

        'IA_PORTAS': 0,

        'IA_SOLEIRAS': 0
    }

    for entity in msp:

        if hasattr(
            entity.dxf,
            'layer'
        ):

            l = str(
                entity.dxf.layer
            ).upper().strip()

            if l in contagem_camadas:

                contagem_camadas[l] += 1

    camadas_vazias = [

        cam

        for cam, qtd
        in contagem_camadas.items()

        if qtd == 0
    ]

    if camadas_vazias:

        raise ValueError(

            "❌ Erro de Validação do DXF: "

            f"A(s) seguinte(s) camada(s) "
            f"obrigatória(s) está(ão) vazia(s) "
            f"ou ausente(s): "
            f"{', '.join(camadas_vazias)}. "

            "Certifique-se de desenhar os elementos "
            "nos respectivos layers "
            "(IA_AMBIENTES, IA_TEXTOS, IA_PORTAS, "
            "IA_SOLEIRAS) antes de gerar o projeto."
        )

    polilinhas = []

    textos = []

    for entity in msp:

        tipo = entity.dxftype()

        layer = str(
            entity.dxf.layer
        ).upper().strip()

        if tipo in [
            'LWPOLYLINE',
            'POLYLINE'
        ] and layer == 'IA_AMBIENTES':

            try:

                if tipo == 'LWPOLYLINE':

                    pontos = [

                        (p[0], p[1])

                        for p
                        in entity.get_points(
                            format='xy'
                        )
                    ]

                else:

                    pontos = [

                        (
                            v.dxf.location.x,
                            v.dxf.location.y
                        )

                        for v
                        in entity.vertices
                    ]

                if pontos:

                    polilinhas.append(
                        pontos
                    )

            except:

                pass

        elif tipo in [
            'TEXT',
            'MTEXT'
        ] and layer == 'IA_TEXTOS':

            try:

                texto_str = (

                    entity.text

                    if tipo == 'MTEXT'

                    else entity.dxf.text

                ).strip()

                if texto_str:

                    textos.append({

                        'nome':
                            texto_str,

                        'x':
                            entity.dxf.insert.x,

                        'y':
                            entity.dxf.insert.y
                    })

            except:

                pass

    resultados = []

    ambientes_processados = {}

    for polilinha in polilinhas:

        xs = [
            p[0]
            for p in polilinha
        ]

        ys = [
            p[1]
            for p in polilinha
        ]

        min_x = min(xs)
        max_x = max(xs)

        min_y = min(ys)
        max_y = max(ys)

        area = (

            max_x -
            min_x

        ) * (

            max_y -
            min_y
        )

        perimetro = (

            (max_x - min_x)
            * 2

        ) + (

            (max_y - min_y)
            * 2
        )

        if area < 0.5:
            continue

        nome_ambiente = next(

            (

                t['nome']

                for t in textos

                if (

                    min_x - 0.5
                    <= t['x']
                    <= max_x + 0.5

                    and

                    min_y - 0.5
                    <= t['y']
                    <= max_y + 0.5
                )
            ),

            None
        )

        if not nome_ambiente:
            continue

        if nome_ambiente in ambientes_processados:

            ambientes_processados[
                nome_ambiente
            ] += 1

            nome_ambiente = (

                f"{nome_ambiente} "
                f"{ambientes_processados[nome_ambiente]}"
            )

        else:

            ambientes_processados[
                nome_ambiente
            ] = 1

        cargas = dimensionar_cargas(
            nome_ambiente,
            area,
            perimetro
        )

        resultados.append({

            "Ambiente":
                nome_ambiente,

            "Centro_X":
                (
                    min_x +
                    max_x
                ) / 2,

            "Centro_Y":
                (
                    min_y +
                    max_y
                ) / 2,

            "Área (m²)":
                area,

            "Perímetro (m)":
                perimetro,

            "Qtd Ilum.":
                int(
                    cargas["Qtd Ilum."]
                ),

            "Pot. Unit. Ilum (VA)":
                int(
                    cargas[
                        "Pot. Unit. Ilum (VA)"
                    ]
                ),

            "Carga Ilum. (VA)":
                int(
                    cargas[
                        "Carga Ilum. (VA)"
                    ]
                ),

            "TUGs (Qtd)":
                int(
                    cargas[
                        "TUGs (Qtd)"
                    ]
                ),

            "Pot. Unit. TUG (VA)":
                int(
                    cargas[
                        "Pot. Unit. TUG (VA)"
                    ]
                ),

            "Carga TUGs (VA)":
                int(
                    cargas[
                        "Carga TUGs (VA)"
                    ]
                ),

            "Equipamento TUE":
                cargas[
                    "Equipamento TUE"
                ],

            "Qtd TUE":
                int(
                    cargas[
                        "Qtd TUE"
                    ]
                ),

            "Pot. Unit. TUE (VA)":
                int(
                    cargas[
                        "Pot. Unit. TUE (VA)"
                    ]
                ),

            "Carga TUE (VA)":
                int(
                    cargas[
                        "Carga TUE (VA)"
                    ]
                )
        })

    return resultados


# ============================================================
# FUNÇÕES AUXILIARES DOS INTERRUPTORES
# ============================================================

def normalizar_nome_ambiente(nome):

    if nome is None:
        return ""

    return (
        str(nome)
        .strip()
        .lower()
    )


def obter_config_interruptores(
    nome_ambiente
):

    nome_normalizado = (
        normalizar_nome_ambiente(
            nome_ambiente
        )
    )

    for nome_config, config in (
        CONFIG_INTERRUPTores.items()
    ):

        if (
            normalizar_nome_ambiente(
                nome_config
            )
            ==
            nome_normalizado
        ):

            return config

    return None


def encontrar_portas_do_ambiente(
    polilinha,
    portas_raw
):

    if not polilinha:
        return []

    xs = [
        p[0]
        for p in polilinha
    ]

    ys = [
        p[1]
        for p in polilinha
    ]

    min_x = min(xs)
    max_x = max(xs)

    min_y = min(ys)
    max_y = max(ys)

    portas_ambiente = []

    for porta in portas_raw:

        cx = (
            porta['p1'][0]
            +
            porta['p2'][0]
        ) / 2

        cy = (
            porta['p1'][1]
            +
            porta['p2'][1]
        ) / 2

        if (

            min_x - 0.8
            <= cx
            <= max_x + 0.8

            and

            min_y - 0.8
            <= cy
            <= max_y + 0.8
        ):

            distancia_minima = float(
                'inf'
            )

            for i in range(
                len(polilinha)
            ):

                a = polilinha[i]

                b = polilinha[
                    (i + 1)
                    %
                    len(polilinha)
                ]

                d = min(

                    point_seg_dist(
                        porta['p1'][0],
                        porta['p1'][1],
                        a,
                        b
                    ),

                    point_seg_dist(
                        porta['p2'][0],
                        porta['p2'][1],
                        a,
                        b
                    )
                )

                if d < distancia_minima:

                    distancia_minima = d

            if distancia_minima <= 0.80:

                portas_ambiente.append(
                    porta
                )

    return portas_ambiente


def criar_geometria_circulo_soleira(
    soleira,
    porta,
    polilinha,
    polilinhas
):

    s_p1 = soleira['p1']
    s_p2 = soleira['p2']

    # --------------------------------------------------------
    # IDENTIFICA O EXTREMO DA PORTA QUE ENCOSTA NA SOLEIRA
    # --------------------------------------------------------

    d_porta_1 = point_seg_dist(

        porta['p1'][0],
        porta['p1'][1],

        s_p1,
        s_p2
    )

    d_porta_2 = point_seg_dist(

        porta['p2'][0],
        porta['p2'][1],

        s_p1,
        s_p2
    )

    if d_porta_1 <= d_porta_2:

        extremo_porta_encostado = (
            porta['p1']
        )

        p4 = porta['p2']

    else:

        extremo_porta_encostado = (
            porta['p2']
        )

        p4 = porta['p1']

    # --------------------------------------------------------
    # PROJEÇÃO EXATA DO PONTO P1 SOBRE A SOLEIRA
    # --------------------------------------------------------

    sx = (
        s_p2[0]
        -
        s_p1[0]
    )

    sy = (
        s_p2[1]
        -
        s_p1[1]
    )

    s2 = (
        sx * sx
        +
        sy * sy
    )

    if s2 == 0:
        return None

    t = (

        (
            extremo_porta_encostado[0]
            -
            s_p1[0]
        )
        *
        sx

        +

        (
            extremo_porta_encostado[1]
            -
            s_p1[1]
        )
        *
        sy

    ) / s2

    t = max(
        0.0,
        min(
            1.0,
            t
        )
    )

    p1 = (

        s_p1[0]
        +
        t * sx,

        s_p1[1]
        +
        t * sy
    )

    # --------------------------------------------------------
    # P2 = OUTRA EXTREMIDADE DA SOLEIRA
    # --------------------------------------------------------

    d_p1_s1 = math.hypot(

        p1[0]
        -
        s_p1[0],

        p1[1]
        -
        s_p1[1]
    )

    d_p1_s2 = math.hypot(

        p1[0]
        -
        s_p2[0],

        p1[1]
        -
        s_p2[1]
    )

    if d_p1_s1 <= d_p1_s2:

        p2 = s_p2

    else:

        p2 = s_p1

    # --------------------------------------------------------
    # P3 = QUARTO PONTO
    # --------------------------------------------------------

    vetor_x = (
        p2[0]
        -
        p1[0]
    )

    vetor_y = (
        p2[1]
        -
        p1[1]
    )

    p3 = (

        p4[0]
        +
        vetor_x,

        p4[1]
        +
        vetor_y
    )

    # --------------------------------------------------------
    # VETOR DA SOLEIRA
    # --------------------------------------------------------

    soleira_vx = (
        p2[0]
        -
        p1[0]
    )

    soleira_vy = (
        p2[1]
        -
        p1[1]
    )

    soleira_len = math.hypot(

        soleira_vx,
        soleira_vy
    )

    if soleira_len == 0:
        return None

    soleira_vx /= soleira_len
    soleira_vy /= soleira_len

    # --------------------------------------------------------
    # ENCONTRA OS DOIS AMBIENTES ADJACENTES
    # --------------------------------------------------------

    sm_x = (
        s_p1[0]
        +
        s_p2[0]
    ) / 2

    sm_y = (
        s_p1[1]
        +
        s_p2[1]
    ) / 2

    ambientes_adjacentes = []

    for poly in polilinhas:

        distancia_poly = float(
            'inf'
        )

        for i in range(
            len(poly)
        ):

            a = poly[i]

            b = poly[
                (i + 1)
                %
                len(poly)
            ]

            d = point_seg_dist(

                sm_x,
                sm_y,

                a,
                b
            )

            if d < distancia_poly:

                distancia_poly = d

        if distancia_poly <= 0.60:

            ambientes_adjacentes.append(
                poly
            )

    return {

        'p1': p1,

        'p2': p2,

        'p3': p3,

        'p4': p4,

        'soleira_vx':
            soleira_vx,

        'soleira_vy':
            soleira_vy,

        'ambientes':
            ambientes_adjacentes
    }


def encontrar_soleiras_da_porta(
    porta,
    soleiras_com_porta
):

    resultado = []

    for item in soleiras_com_porta:

        mesma_porta = (
            item['porta']
            is porta
        )

        if mesma_porta:

            resultado.append(
                item['s']
            )

    return resultado


# ============================================================
# DESENHA O CÍRCULO TANGENTE À SOLEIRA
# ============================================================
#
# ESTA É A PARTE MAIS IMPORTANTE DA NOVA LÓGICA.
#
# O ponto de tangência permanece EXATAMENTE em P2 ou P3.
#
# O centro é deslocado exatamente pelo RAIO.
#
# Não existe arco.
#
# Não existe aproximação.
#
# Não é utilizado P2 -> P3 para definir a direção.
#
# A direção é perpendicular à soleira.
#
# ============================================================

def desenhar_circulo_tangente_soleira(
    msp,
    ponto_tangencia,
    soleira_vx,
    soleira_vy,
    polilinha,
    raio=RAIO_CIRCULO_INTERRUPT
):

    # --------------------------------------------------------
    # CENTRO GEOMÉTRICO DA PAREDE/AMBIENTE
    # --------------------------------------------------------

    cx_ambiente = (
        sum(
            pt[0]
            for pt in polilinha
        )
        /
        len(polilinha)
    )

    cy_ambiente = (
        sum(
            pt[1]
            for pt in polilinha
        )
        /
        len(polilinha)
    )

    # --------------------------------------------------------
    # NORMAL PARA DENTRO DO AMBIENTE
    # --------------------------------------------------------

    nx, ny = get_inside_normal(

        soleira_vx,
        soleira_vy,

        ponto_tangencia[0],
        ponto_tangencia[1],

        cx_ambiente,
        cy_ambiente
    )

    # --------------------------------------------------------
    # REGRA DE TANGENCIAMENTO
    #
    # O centro fica EXATAMENTE UM RAIO distante de P2/P3.
    #
    # centro = P2/P3 + normal * raio
    #
    # Portanto:
    #
    # distância(P2, centro) = raio
    #
    # distância(P3, centro) = raio
    #
    # --------------------------------------------------------

    centro = (

        ponto_tangencia[0]
        +
        nx * raio,

        ponto_tangencia[1]
        +
        ny * raio
    )

    # --------------------------------------------------------
    # CONFIRMA QUE O CENTRO ESTÁ DENTRO DO AMBIENTE.
    #
    # Se a orientação da polilinha estiver invertida,
    # inverte a normal.
    # --------------------------------------------------------

    if not ponto_em_poligono(

        centro[0],
        centro[1],
        polilinha

    ):

        centro = (

            ponto_tangencia[0]
            -
            nx * raio,

            ponto_tangencia[1]
            -
            ny * raio
        )

    # --------------------------------------------------------
    # CONFIRMAÇÃO FINAL
    # --------------------------------------------------------

    if not ponto_em_poligono(

        centro[0],
        centro[1],
        polilinha

    ):

        return False

    # --------------------------------------------------------
    # DESENHA O CÍRCULO
    # --------------------------------------------------------

    msp.add_circle(

        center=centro,

        radius=raio,

        dxfattribs={

            'layer':
                'PROJ_ELETRICA_DEBUG',

            'color':
                6
        }
    )

    return True


# ============================================================
# PROCESSAMENTO DOS CÍRCULOS / INTERRUPTORES
# ============================================================

def processar_interruptores(
    msp,
    polilinhas,
    portas_raw,
    soleiras_raw,
    soleiras_com_porta,
    nome_ambiente,
    polilinha
):

    config = obter_config_interruptores(
        nome_ambiente
    )

    # --------------------------------------------------------
    # SE NÃO HOUVER CONFIGURAÇÃO PARA O AMBIENTE,
    # NÃO FAZ NADA.
    # --------------------------------------------------------

    if not config:

        return

    quantidade = int(
        config.get(
            'quantidade',
            0
        )
    )

    # --------------------------------------------------------
    # SOMENTE 1 OU 2 SÃO PERMITIDOS
    # --------------------------------------------------------

    if quantidade not in [1, 2]:

        raise ValueError(

            f"❌ Configuração inválida para "
            f"o ambiente '{nome_ambiente}'. "

            "A quantidade de círculos deve ser "
            "somente 1 ou 2."
        )

    # --------------------------------------------------------
    # PORTAS DO AMBIENTE
    # --------------------------------------------------------

    portas_ambiente = (
        encontrar_portas_do_ambiente(
            polilinha,
            portas_raw
        )
    )

    if not portas_ambiente:

        return

    # --------------------------------------------------------
    # MAPEIA AS PORTAS ÀS SOLEIRAS
    # --------------------------------------------------------

    portas_com_soleira = []

    for porta in portas_ambiente:

        soleiras_porta = (
            encontrar_soleiras_da_porta(
                porta,
                soleiras_com_porta
            )
        )

        if soleiras_porta:

            portas_com_soleira.append({

                'porta':
                    porta,

                'soleiras':
                    soleiras_porta
            })

    if not portas_com_soleira:

        return

    # ========================================================
    # QUANTIDADE = 1
    # ========================================================

    if quantidade == 1:

        porta_escolhida = config.get(
            'porta',
            1
        )

        try:

            porta_escolhida = int(
                porta_escolhida
            )

        except:

            porta_escolhida = 1

        # ----------------------------------------------------
        # A NUMERAÇÃO COMEÇA EM 1.
        # ----------------------------------------------------

        indice = (
            porta_escolhida - 1
        )

        if (
            indice < 0
            or
            indice >= len(
                portas_com_soleira
            )
        ):

            raise ValueError(

                f"❌ O ambiente "
                f"'{nome_ambiente}' "
                f"foi configurado com a porta "
                f"{porta_escolhida}, mas foram "
                f"encontradas apenas "
                f"{len(portas_com_soleira)} "
                f"porta(s) com soleira."
            )

        item_porta = (
            portas_com_soleira[
                indice
            ]
        )

        # ----------------------------------------------------
        # NORMALMENTE UMA PORTA TEM UMA SOLEIRA.
        # SE HOUVER MAIS DE UMA, UTILIZA A PRIMEIRA.
        # ----------------------------------------------------

        soleira = (
            item_porta[
                'soleiras'
            ][0]
        )

        geometria = (
            criar_geometria_circulo_soleira(

                soleira,

                item_porta['porta'],

                polilinha,

                polilinhas
            )
        )

        if geometria is None:

            return

        # ----------------------------------------------------
        # VERIFICA QUAL DOS PONTOS P2/P3 PERTENCE
        # AO AMBIENTE ATUAL.
        # ----------------------------------------------------

        p2 = geometria['p2']

        p3 = geometria['p3']

        ponto_tangencia = None

        # ----------------------------------------------------
        # TESTA P2
        # ----------------------------------------------------

        nx, ny = get_inside_normal(

            geometria[
                'soleira_vx'
            ],

            geometria[
                'soleira_vy'
            ],

            p2[0],
            p2[1],

            (
                sum(
                    pt[0]
                    for pt in polilinha
                )
                /
                len(polilinha)
            ),

            (
                sum(
                    pt[1]
                    for pt in polilinha
                )
                /
                len(polilinha)
            )
        )

        teste_p2 = (

            p2[0]
            +
            nx *
            RAIO_CIRCULO_INTERRUPT,

            p2[1]
            +
            ny *
            RAIO_CIRCULO_INTERRUPT
        )

        if ponto_em_poligono(

            teste_p2[0],
            teste_p2[1],
            polilinha

        ):

            ponto_tangencia = p2

        else:

            # ------------------------------------------------
            # TESTA P3
            # ------------------------------------------------

            nx, ny = get_inside_normal(

                geometria[
                    'soleira_vx'
                ],

                geometria[
                    'soleira_vy'
                ],

                p3[0],
                p3[1],

                (
                    sum(
                        pt[0]
                        for pt in polilinha
                    )
                    /
                    len(polilinha)
                ),

                (
                    sum(
                        pt[1]
                        for pt in polilinha
                    )
                    /
                    len(polilinha)
                )
            )

            teste_p3 = (

                p3[0]
                +
                nx *
                RAIO_CIRCULO_INTERRUPT,

                p3[1]
                +
                ny *
                RAIO_CIRCULO_INTERRUPT
            )

            if ponto_em_poligono(

                teste_p3[0],
                teste_p3[1],
                polilinha

            ):

                ponto_tangencia = p3

        if ponto_tangencia is None:

            return

        desenhar_circulo_tangente_soleira(

            msp,

            ponto_tangencia,

            geometria[
                'soleira_vx'
            ],

            geometria[
                'soleira_vy'
            ],

            polilinha,

            RAIO_CIRCULO_INTERRUPT
        )

    # ========================================================
    # QUANTIDADE = 2
    # ========================================================

    elif quantidade == 2:

        # ----------------------------------------------------
        # PEGA AS DUAS PRIMEIRAS PORTAS COM SOLEIRA.
        # ----------------------------------------------------

        portas_utilizadas = (
            portas_com_soleira[:2]
        )

        for item_porta in (
            portas_utilizadas
        ):

            soleira = (
                item_porta[
                    'soleiras'
                ][0]
            )

            geometria = (
                criar_geometria_circulo_soleira(

                    soleira,

                    item_porta['porta'],

                    polilinha,

                    polilinhas
                )
            )

            if geometria is None:
                continue

            p2 = geometria['p2']

            p3 = geometria['p3']

            ponto_tangencia = None

            # ------------------------------------------------
            # TENTA P2
            # ------------------------------------------------

            nx, ny = get_inside_normal(

                geometria[
                    'soleira_vx'
                ],

                geometria[
                    'soleira_vy'
                ],

                p2[0],
                p2[1],

                (
                    sum(
                        pt[0]
                        for pt in polilinha
                    )
                    /
                    len(polilinha)
                ),

                (
                    sum(
                        pt[1]
                        for pt in polilinha
                    )
                    /
                    len(polilinha)
                )
            )

            teste_p2 = (

                p2[0]
                +
                nx *
                RAIO_CIRCULO_INTERRUPT,

                p2[1]
                +
                ny *
                RAIO_CIRCULO_INTERRUPT
            )

            if ponto_em_poligono(

                teste_p2[0],
                teste_p2[1],
                polilinha

            ):

                ponto_tangencia = p2

            else:

                # ------------------------------------------------
                # TENTA P3
                # ------------------------------------------------

                nx, ny = get_inside_normal(

                    geometria[
                        'soleira_vx'
                    ],

                    geometria[
                        'soleira_vy'
                    ],

                    p3[0],
                    p3[1],

                    (
                        sum(
                            pt[0]
                            for pt in polilinha
                        )
                        /
                        len(polilinha)
                    ),

                    (
                        sum(
                            pt[1]
                            for pt in polilinha
                        )
                        /
                        len(polilinha)
                    )
                )

                teste_p3 = (

                    p3[0]
                    +
                    nx *
                    RAIO_CIRCULO_INTERRUPT,

                    p3[1]
                    +
                    ny *
                    RAIO_CIRCULO_INTERRUPT
                )

                if ponto_em_poligono(

                    teste_p3[0],
                    teste_p3[1],
                    polilinha

                ):

                    ponto_tangencia = p3

            if ponto_tangencia is None:

                continue

            desenhar_circulo_tangente_soleira(

                msp,

                ponto_tangencia,

                geometria[
                    'soleira_vx'
                ],

                geometria[
                    'soleira_vy'
                ],

                polilinha,

                RAIO_CIRCULO_INTERRUPT
            )


# ============================================================
# GERAÇÃO DO CAD
# ============================================================

def gerar_cad_unifilar(
    dxf_bytes,
    dados_editados,
    local_qdc
):

    tmp_in_path = ""

    try:

        # ----------------------------------------------------
        # CRIA ARQUIVO TEMPORÁRIO
        # ----------------------------------------------------

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".dxf"
        ) as tmp_in:

            tmp_in.write(
                dxf_bytes
            )

            tmp_in_path = (
                tmp_in.name
            )

        doc = ezdxf.readfile(
            tmp_in_path
        )

        msp = doc.modelspace()

        # ----------------------------------------------------
        # VALIDA CAMADAS
        # ----------------------------------------------------

        contagem_camadas = {

            'IA_AMBIENTES': 0,

            'IA_TEXTOS': 0,

            'IA_PORTAS': 0,

            'IA_SOLEIRAS': 0
        }

        for entity in msp:

            if hasattr(
                entity.dxf,
                'layer'
            ):

                l = str(
                    entity.dxf.layer
                ).upper().strip()

                if l in contagem_camadas:

                    contagem_camadas[l] += 1

        camadas_vazias = [

            cam

            for cam, qtd
            in contagem_camadas.items()

            if qtd == 0
        ]

        if camadas_vazias:

            raise ValueError(

                "❌ Erro de Geração do CAD: "

                f"A(s) seguinte(s) camada(s) "
                f"obrigatória(s) está(ão) "
                f"vazia(s) ou ausente(s): "
                f"{', '.join(camadas_vazias)}. "

                "Verifique se os elementos estão "
                "corretamente posicionados em suas "
                "camadas antes de processar."
            )

        # ----------------------------------------------------
        # CAMADAS DO PROJETO
        # ----------------------------------------------------

        camadas = {

            "PROJ_ELETRICA_LUZ":
                2,

            "PROJ_ELETRICA_QDC":
                1,

            "PROJ_ELETRICA_TEXTO":
                2,

            "PROJ_ELETRICA_TOMADA":
                4,

            "PROJ_ELETRICA_INTERRUPTOR":
                5,

            "PROJ_ELETRICA_DEBUG":
                6
        }

        for nome_l, cor_l in (
            camadas.items()
        ):

            if nome_l not in doc.layers:

                doc.layers.add(
                    name=nome_l,
                    color=cor_l
                )

            else:

                doc.layers.get(
                    nome_l
                ).color = cor_l

        # ----------------------------------------------------
        # LEITURA DOS ELEMENTOS
        # ----------------------------------------------------

        polilinhas = []

        textos = []

        portas_raw = []

        soleiras_raw = []

        for entity in msp:

            tipo = entity.dxftype()

            if hasattr(
                entity.dxf,
                'layer'
            ):

                layer = str(
                    entity.dxf.layer
                ).upper().strip()

            else:

                continue

            # -----------------------------------------------
            # AMBIENTES
            # -----------------------------------------------

            if tipo in [
                'LWPOLYLINE',
                'POLYLINE'
            ] and layer == 'IA_AMBIENTES':

                try:

                    if tipo == 'LWPOLYLINE':

                        pontos = [

                            (p[0], p[1])

                            for p
                            in entity.get_points(
                                format='xy'
                            )
                        ]

                    else:

                        pontos = [

                            (
                                v.dxf.location.x,
                                v.dxf.location.y
                            )

                            for v
                            in entity.vertices
                        ]

                    if pontos:

                        polilinhas.append(
                            pontos
                        )

                except:

                    pass

            # -----------------------------------------------
            # TEXTOS
            # -----------------------------------------------

            elif tipo in [
                'TEXT',
                'MTEXT'
            ] and layer == 'IA_TEXTOS':

                try:

                    texto_str = (

                        entity.text

                        if tipo == 'MTEXT'

                        else entity.dxf.text

                    ).strip()

                    if texto_str:

                        textos.append({

                            'nome':
                                texto_str,

                            'x':
                                entity.dxf.insert.x,

                            'y':
                                entity.dxf.insert.y
                        })

                except:

                    pass

            # -----------------------------------------------
            # PORTAS
            # -----------------------------------------------

            elif layer == 'IA_PORTAS':

                if tipo == 'LINE':

                    portas_raw.append({

                        'p1': (

                            entity.dxf.start.x,
                            entity.dxf.start.y
                        ),

                        'p2': (

                            entity.dxf.end.x,
                            entity.dxf.end.y
                        )
                    })

                elif tipo in [
                    'LWPOLYLINE',
                    'POLYLINE'
                ]:

                    try:

                        if tipo == 'LWPOLYLINE':

                            pts = [

                                (p[0], p[1])

                                for p
                                in entity.get_points(
                                    format='xy'
                                )
                            ]

                        else:

                            pts = [

                                (
                                    v.dxf.location.x,
                                    v.dxf.location.y
                                )

                                for v
                                in entity.vertices
                            ]

                        if len(pts) >= 2:

                            portas_raw.append({

                                'p1':
                                    pts[0],

                                'p2':
                                    pts[-1]
                            })

                    except:

                        pass

            # -----------------------------------------------
            # SOLEIRAS
            # -----------------------------------------------

            elif layer == 'IA_SOLEIRAS':

                if tipo == 'LINE':

                    soleiras_raw.append({

                        'p1': (

                            entity.dxf.start.x,
                            entity.dxf.start.y
                        ),

                        'p2': (

                            entity.dxf.end.x,
                            entity.dxf.end.y
                        )
                    })

                elif tipo in [
                    'LWPOLYLINE',
                    'POLYLINE'
                ]:

                    try:

                        if tipo == 'LWPOLYLINE':

                            pts = [

                                (p[0], p[1])

                                for p
                                in entity.get_points(
                                    format='xy'
                                )
                            ]

                        else:

                            pts = [

                                (
                                    v.dxf.location.x,
                                    v.dxf.location.y
                                )

                                for v
                                in entity.vertices
                            ]

                        if len(pts) >= 2:

                            soleiras_raw.append({

                                'p1':
                                    pts[0],

                                'p2':
                                    pts[-1]
                            })

                    except:

                        pass

        # ====================================================
        # IDENTIFICA SOLEIRAS ASSOCIADAS ÀS PORTAS
        # ====================================================

        soleiras_com_porta = []

        tolerancia_porta_soleira = 0.30

        for s in soleiras_raw:

            s_p1 = s['p1']

            s_p2 = s['p2']

            melhor_porta = None

            menor_distancia = float(
                'inf'
            )

            for p in portas_raw:

                d1 = point_seg_dist(

                    p['p1'][0],
                    p['p1'][1],

                    s_p1,
                    s_p2
                )

                d2 = point_seg_dist(

                    p['p2'][0],
                    p['p2'][1],

                    s_p1,
                    s_p2
                )

                pm_porta = (

                    (
                        p['p1'][0]
                        +
                        p['p2'][0]
                    ) / 2,

                    (
                        p['p1'][1]
                        +
                        p['p2'][1]
                    ) / 2
                )

                d3 = point_seg_dist(

                    pm_porta[0],
                    pm_porta[1],

                    s_p1,
                    s_p2
                )

                distancia = min(
                    d1,
                    d2,
                    d3
                )

                if (

                    distancia
                    <=
                    tolerancia_porta_soleira

                    and

                    distancia
                    <
                    menor_distancia
                ):

                    menor_distancia = (
                        distancia
                    )

                    melhor_porta = p

            if melhor_porta is not None:

                soleiras_com_porta.append({

                    's':
                        s,

                    'porta':
                        melhor_porta
                })

        # ====================================================
        # LIMPA DEBUG ANTIGO
        # ====================================================

        for entidade_debug in list(msp):

            try:

                if (

                    str(
                        entidade_debug.dxf.layer
                    )
                    .upper()
                    .strip()

                    ==

                    'PROJ_ELETRICA_DEBUG'
                ):

                    msp.delete_entity(
                        entidade_debug
                    )

            except Exception:

                pass

        # ====================================================
        # PROCESSAMENTO DOS INTERRUPTORES
        # ====================================================
        #
        # Agora os círculos NÃO são mais criados
        # automaticamente para todas as soleiras.
        #
        # Somente os ambientes configurados em
        # CONFIG_INTERRUPTores receberão círculos.
        #
        # ====================================================

        ambientes_processados_interruptores = {}

        for polilinha in polilinhas:

            xs = [
                p[0]
                for p in polilinha
            ]

            ys = [
                p[1]
                for p in polilinha
            ]

            min_x = min(xs)
            max_x = max(xs)

            min_y = min(ys)
            max_y = max(ys)

            area = (

                max_x -
                min_x

            ) * (

                max_y -
                min_y
            )

            if area < 0.5:

                continue

            nome_ambiente = next(

                (

                    t['nome']

                    for t in textos

                    if (

                        min_x - 0.5
                        <= t['x']
                        <= max_x + 0.5

                        and

                        min_y - 0.5
                        <= t['y']
                        <= max_y + 0.5
                    )
                ),

                None
            )

            if not nome_ambiente:

                continue

            if (
                nome_ambiente
                in
                ambientes_processados_interruptores
            ):

                ambientes_processados_interruptores[
                    nome_ambiente
                ] += 1

                nome_busca_interruptor = (

                    f"{nome_ambiente} "
                    f"{ambientes_processados_interruptores[nome_ambiente]}"
                )

            else:

                ambientes_processados_interruptores[
                    nome_ambiente
                ] = 1

                nome_busca_interruptor = (
                    nome_ambiente
                )

            processar_interruptores(

                msp,

                polilinhas,

                portas_raw,

                soleiras_raw,

                soleiras_com_porta,

                nome_busca_interruptor,

                polilinha
            )

        # ====================================================
        # DADOS DA TABELA
        # ====================================================

        ambientes_processados = {}

        dict_dados = {

            row['Ambiente']:
                row

            for row
            in dados_editados
        }

        # ====================================================
        # PROCESSAMENTO DOS AMBIENTES
        # ====================================================

        for polilinha in polilinhas:

            xs = [
                p[0]
                for p in polilinha
            ]

            ys = [
                p[1]
                for p in polilinha
            ]

            min_x = min(xs)
            max_x = max(xs)

            min_y = min(ys)
            max_y = max(ys)

            area = (

                max_x -
                min_x

            ) * (

                max_y -
                min_y
            )

            perimetro = (

                (max_x - min_x)
                * 2

            ) + (

                (max_y - min_y)
                * 2
            )

            if area < 0.5:

                continue

            nome = next(

                (

                    t['nome']

                    for t in textos

                    if (

                        min_x - 0.5
                        <= t['x']
                        <= max_x + 0.5

                        and

                        min_y - 0.5
                        <= t['y']
                        <= max_y + 0.5
                    )
                ),

                None
            )

            if not nome:

                continue

            if nome in ambientes_processados:

                ambientes_processados[
                    nome
                ] += 1

                nome_busca = (

                    f"{nome} "
                    f"{ambientes_processados[nome]}"
                )

            else:

                ambientes_processados[
                    nome
                ] = 1

                nome_busca = nome

            row_data = dict_dados.get(

                nome_busca,

                dict_dados.get(
                    nome,
                    None
                )
            )

            centro_x = (
                min_x +
                max_x
            ) / 2

            centro_y = (
                min_y +
                max_y
            ) / 2

            largura = (
                max_x -
                min_x
            )

            comprimento = (
                max_y -
                min_y
            )

            # =================================================
            # SEGMENTOS DA PAREDE
            # =================================================

            segmentos_crus = []

            comp_total = 0

            poly = list(
                polilinha
            )

            if poly[0] != poly[-1]:

                poly.append(
                    poly[0]
                )

            for i in range(
                len(poly) - 1
            ):

                dst = math.hypot(

                    poly[i + 1][0]
                    -
                    poly[i][0],

                    poly[i + 1][1]
                    -
                    poly[i][1]
                )

                if dst > 0.1:

                    segmentos_crus.append((

                        poly[i],

                        poly[i + 1],

                        dst
                    ))

                    comp_total += dst

            # =================================================
            # PAREDES LÓGICAS
            # =================================================

            logical_walls = []

            for pt1, pt2, dst in (
                segmentos_crus
            ):

                vx = (

                    pt2[0]
                    -
                    pt1[0]

                ) / dst

                vy = (

                    pt2[1]
                    -
                    pt1[1]

                ) / dst

                logical_walls.append({

                    'p1':
                        pt1,

                    'p2':
                        pt2,

                    'length':
                        dst,

                    'vx':
                        vx,

                    'vy':
                        vy
                })

            # =================================================
            # PORTAS DO AMBIENTE
            # =================================================

            unique_portas = [

                p

                for p in portas_raw

                if (

                    min_x - 0.8

                    <=

                    (
                        p['p1'][0]
                        +
                        p['p2'][0]
                    ) / 2

                    <=

                    max_x + 0.8

                    and

                    min_y - 0.8

                    <=

                    (
                        p['p1'][1]
                        +
                        p['p2'][1]
                    ) / 2

                    <=

                    max_y + 0.8
                )
            ]

            # =================================================
            # ILUMINAÇÃO
            # =================================================

            if row_data:

                qtd_ilum = int(

                    row_data.get(
                        'Qtd Ilum.',
                        1
                    )
                )

                pot_ilum_unit = int(

                    row_data.get(
                        'Pot. Unit. Ilum (VA)',
                        100
                    )
                )

                if qtd_ilum > 0:

                    pontos_luz = []

                    if largura >= comprimento:

                        if qtd_ilum == 1:

                            pontos_luz.append((

                                centro_x,
                                centro_y
                            ))

                        else:

                            step = (

                                largura
                                /
                                (
                                    qtd_ilum
                                    +
                                    1
                                )
                            )

                            for i in range(

                                1,
                                qtd_ilum + 1
                            ):

                                pontos_luz.append((

                                    min_x
                                    +
                                    step * i,

                                    centro_y
                                ))

                    else:

                        if qtd_ilum == 1:

                            pontos_luz.append((

                                centro_x,
                                centro_y
                            ))

                        else:

                            step = (

                                comprimento
                                /
                                (
                                    qtd_ilum
                                    +
                                    1
                                )
                            )

                            for i in range(

                                1,
                                qtd_ilum + 1
                            ):

                                pontos_luz.append((

                                    centro_x,

                                    min_y
                                    +
                                    step * i
                                ))

                    for lx, ly in (
                        pontos_luz
                    ):

                        msp.add_circle(

                            center=(
                                lx,
                                ly
                            ),

                            radius=0.25,

                            dxfattribs={

                                'layer':
                                    'PROJ_ELETRICA_LUZ'
                            }
                        )

                        msp.add_text(

                            f"{pot_ilum_unit}VA",

                            dxfattribs={

                                'layer':
                                    'PROJ_ELETRICA_TEXTO',

                                'height':
                                    0.15,

                                'insert': (

                                    lx + 0.3,
                                    ly - 0.07
                                )
                            }
                        )

                        msp.add_text(

                            "a",

                            dxfattribs={

                                'layer':
                                    'PROJ_ELETRICA_TEXTO',

                                'height':
                                    0.15,

                                'color':
                                    2,

                                'insert': (

                                    lx + 0.3,
                                    ly + 0.15
                                )
                            }
                        )

            # =================================================
            # QDC
            # =================================================

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

            is_ambiente_qdc = (

                nome_atual_upper
                ==
                qdc_formatado
            )

            if (
                is_ambiente_qdc
                and
                logical_walls
            ):

                qdc_w = 0.4

                qdc_d = 0.15

                maior_parede = max(

                    logical_walls,

                    key=lambda w:
                    w['length']
                )

                pt1 = maior_parede['p1']

                pt2 = maior_parede['p2']

                is_vertical = (

                    abs(
                        pt1[0] -
                        pt2[0]
                    )

                    <

                    abs(
                        pt1[1] -
                        pt2[1]
                    )
                )

                cortes_portas = []

                for p in unique_portas:

                    d_p1 = point_seg_dist(

                        p['p1'][0],
                        p['p1'][1],

                        pt1,
                        pt2
                    )

                    d_p2 = point_seg_dist(

                        p['p2'][0],
                        p['p2'][1],

                        pt1,
                        pt2
                    )

                    if (
                        d_p1 < 0.6
                        or
                        d_p2 < 0.6
                    ):

                        if is_vertical:

                            cortes_portas.append((

                                min(
                                    p['p1'][1],
                                    p['p2'][1]
                                ),

                                max(
                                    p['p1'][1],
                                    p['p2'][1]
                                )
                            ))

                        else:

                            cortes_portas.append((

                                min(
                                    p['p1'][0],
                                    p['p2'][0]
                                ),

                                max(
                                    p['p1'][0],
                                    p['p2'][0]
                                )
                            ))

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

                    for c_inf, c_sup in (
                        cortes_portas
                    ):

                        if (
                            c_inf
                            >
                            cursor + 0.1
                        ):

                            trechos_livres.append((

                                cursor,
                                c_inf
                            ))

                        cursor = max(

                            cursor,
                            c_sup
                        )

                    if (
                        cursor
                        <
                        parede_max - 0.1
                    ):

                        trechos_livres.append((

                            cursor,
                            parede_max
                        ))

                    if trechos_livres:

                        melhor_trecho = max(

                            trechos_livres,

                            key=lambda t:
                            t[1] - t[0]
                        )

                        mid_y = (

                            melhor_trecho[0]
                            +
                            melhor_trecho[1]
                        ) / 2

                        mx = pt1[0]

                        my = mid_y

                    else:

                        mx = (

                            pt1[0]
                            +
                            pt2[0]
                        ) / 2

                        my = (

                            pt1[1]
                            +
                            pt2[1]
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

                    for c_inf, c_sup in (
                        cortes_portas
                    ):

                        if (
                            c_inf
                            >
                            cursor + 0.1
                        ):

                            trechos_livres.append((

                                cursor,
                                c_inf
                            ))

                        cursor = max(

                            cursor,
                            c_sup
                        )

                    if (
                        cursor
                        <
                        parede_max - 0.1
                    ):

                        trechos_livres.append((

                            cursor,
                            parede_max
                        ))

                    if trechos_livres:

                        melhor_trecho = max(

                            trechos_livres,

                            key=lambda t:
                            t[1] - t[0]
                        )

                        mid_x = (

                            melhor_trecho[0]
                            +
                            melhor_trecho[1]
                        ) / 2

                        mx = mid_x

                        my = pt1[1]

                    else:

                        mx = (

                            pt1[0]
                            +
                            pt2[0]
                        ) / 2

                        my = (

                            pt1[1]
                            +
                            pt2[1]
                        ) / 2

                vx = maior_parede['vx']

                vy = maior_parede['vy']

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

                    mx
                    -
                    vx * qdc_w / 2,

                    my
                    -
                    vy * qdc_w / 2
                )

                p2_qdc = (

                    mx
                    +
                    vx * qdc_w / 2,

                    my
                    +
                    vy * qdc_w / 2
                )

                p3_qdc = (

                    p2_qdc[0]
                    +
                    out_nx * qdc_d,

                    p2_qdc[1]
                    +
                    out_ny * qdc_d
                )

                p4_qdc = (

                    p1_qdc[0]
                    +
                    out_nx * qdc_d,

                    p1_qdc[1]
                    +
                    out_ny * qdc_d
                )

                pts_qdc = [

                    p1_qdc,

                    p2_qdc,

                    p3_qdc,

                    p4_qdc
                ]

                msp.add_lwpolyline(

                    pts_qdc
                    +
                    [
                        pts_qdc[0]
                    ],

                    dxfattribs={

                        'layer':
                            'PROJ_ELETRICA_QDC'
                    }
                )

                msp.add_solid(

                    pts_qdc[:3],

                    dxfattribs={

                        'layer':
                            'PROJ_ELETRICA_QDC'
                    }
                )

            # =================================================
            # TOMADAS TUG / TUE
            # =================================================

            if row_data:

                qtd_tugs = int(

                    row_data.get(

                        'TUGs (Qtd)',

                        row_data.get(
                            'TUGs',
                            0
                        )
                    )
                )

                qtd_tue = int(

                    row_data.get(

                        'Qtd TUE',

                        row_data.get(
                            'TUE',
                            0
                        )
                    )
                )

                eq_tue_nome = str(

                    row_data.get(

                        'Equipamento TUE',

                        '-'
                    )
                )

                pot_tue_val = int(

                    row_data.get(

                        'Pot. Unit. TUE (VA)',

                        0
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
                        "micro"
                        in eq_lower

                        or

                        "forno"
                        in eq_lower
                    ):

                        pot_tue_val = 2000

                    elif (
                        "máquina"
                        in eq_lower

                        or

                        "lavar"
                        in eq_lower
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

                nome_lower_env = (
                    nome.lower().strip()
                )

                is_ambiente_molhado = any(

                    x in nome_lower_env

                    for x in [

                        "coz",
                        "serv",
                        "banh",
                        "lav",
                        "sanit",
                        "wc",
                        "as"
                    ]
                )

                # =================================================
                # TUE
                # =================================================

                if (
                    qtd_tue > 0
                    and
                    logical_walls
                ):

                    paredes_candidatas = sorted(

                        logical_walls,

                        key=lambda w:
                        w['length']
                    )

                    paredes_sem_porta = [

                        w

                        for w
                        in paredes_candidatas

                        if not any(

                            point_seg_dist(

                                (
                                    p['p1'][0]
                                    +
                                    p['p2'][0]
                                ) / 2,

                                (
                                    p['p1'][1]
                                    +
                                    p['p2'][1]
                                ) / 2,

                                w['p1'],
                                w['p2']

                            ) < 0.6

                            for p
                            in unique_portas
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

                        p_alvo = paredes_finais[

                            idx_tue
                            %
                            len(
                                paredes_finais
                            )
                        ]

                        pt1 = p_alvo['p1']

                        pt2 = p_alvo['p2']

                        fator = (

                            0.5

                            if qtd_tue == 1

                            else

                            (
                                idx_tue + 1
                            )
                            /
                            (
                                qtd_tue + 1
                            )
                        )

                        resultado_tue = (

                            procurar_ponto_valido_na_parede(

                                pt1,
                                pt2,
                                fator,
                                polilinha,
                                portas_raw,
                                soleiras_raw
                            )
                        )

                        if resultado_tue is None:

                            continue

                        (

                            px,
                            py,
                            vx,
                            vy

                        ) = resultado_tue

                        nx, ny = get_inside_normal(

                            vx,
                            vy,

                            px,
                            py,

                            centro_x,
                            centro_y
                        )

                        ponto_b1 = (

                            px
                            -
                            vx * 0.10,

                            py
                            -
                            vy * 0.10
                        )

                        ponto_b2 = (

                            px
                            +
                            vx * 0.10,

                            py
                            +
                            vy * 0.10
                        )

                        ponto_pt = (

                            px
                            +
                            nx * 0.20,

                            py
                            +
                            ny * 0.20
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

                                'layer':
                                    'PROJ_ELETRICA_TOMADA'
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

                                    'layer':
                                        'PROJ_ELETRICA_TOMADA'
                                }
                            )

                        elif is_ambiente_molhado:

                            ponto_medio_base = (

                                px,
                                py
                            )

                            msp.add_solid(

                                [

                                    ponto_b1,

                                    ponto_medio_base,

                                    ponto_pt
                                ],

                                dxfattribs={

                                    'layer':
                                        'PROJ_ELETRICA_TOMADA'
                                }
                            )

                        msp.add_text(

                            f"{pot_tue_val}W",

                            dxfattribs={

                                'layer':
                                    'PROJ_ELETRICA_TEXTO',

                                'height':
                                    0.12,

                                'color':
                                    2,

                                'insert': (

                                    px
                                    +
                                    nx * 0.35,

                                    py
                                    +
                                    ny * 0.35
                                )
                            }
                        )

                # =================================================
                # TUGs
                # =================================================

                total_tugs = qtd_tugs

                if (
                    total_tugs > 0
                    and
                    comp_total > 0
                ):

                    margem_inicial = 0.35

                    comprimento_util = (

                        comp_total
                        -
                        (
                            2 *
                            margem_inicial
                        )
                    )

                    if comprimento_util > 0:

                        passo = (

                            comprimento_util
                            /
                            total_tugs
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
                            total_tugs
                        )

                        inicio_offset = (

                            passo / 2
                        )

                    tomadas_colocadas = 0

                    distancias_usadas = []

                    for i in range(
                        total_tugs
                    ):

                        distancia_desejada = (

                            inicio_offset
                            +
                            i * passo
                        )

                        if distancia_desejada <= 0:

                            continue

                        if distancia_desejada >= comp_total:

                            continue

                        resultado_ponto = (

                            procurar_ponto_valido_perimetro(

                                distancia_desejada,

                                comp_total,

                                segmentos_crus,

                                polilinha,

                                portas_raw,

                                soleiras_raw
                            )
                        )

                        if resultado_ponto is None:

                            continue

                        px, py, seg_vx, seg_vy = (

                            resultado_ponto
                        )

                        distancia_muito_proxima = False

                        for d_usada in (
                            distancias_usadas
                        ):

                            diferenca = abs(

                                distancia_desejada
                                -
                                d_usada
                            )

                            if diferenca < 0.60:

                                distancia_muito_proxima = True

                                break

                        if distancia_muito_proxima:

                            alternativas = [

                                distancia_desejada
                                -
                                0.75,

                                distancia_desejada
                                +
                                0.75,

                                distancia_desejada
                                -
                                1.00,

                                distancia_desejada
                                +
                                1.00
                            ]

                            alternativa_encontrada = None

                            for dist_alt in alternativas:

                                if (
                                    dist_alt <= 0
                                    or
                                    dist_alt >= comp_total
                                ):

                                    continue

                                alt_result = (

                                    procurar_ponto_valido_perimetro(

                                        dist_alt,

                                        comp_total,

                                        segmentos_crus,

                                        polilinha,

                                        portas_raw,

                                        soleiras_raw
                                    )
                                )

                                if alt_result is None:

                                    continue

                                ax, ay, avx, avy = (

                                    alt_result
                                )

                                muito_perto = any(

                                    abs(

                                        dist_alt
                                        -
                                        d
                                    ) < 0.60

                                    for d
                                    in distancias_usadas
                                )

                                if not muito_perto:

                                    alternativa_encontrada = (

                                        dist_alt,
                                        ax,
                                        ay,
                                        avx,
                                        avy
                                    )

                                    break

                            if alternativa_encontrada:

                                (

                                    distancia_desejada,
                                    px,
                                    py,
                                    seg_vx,
                                    seg_vy

                                ) = alternativa_encontrada

                            else:

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

                        tomadas_colocadas += 1

                        nx, ny = get_inside_normal(

                            seg_vx,
                            seg_vy,

                            px,
                            py,

                            centro_x,
                            centro_y
                        )

                        ponto_b1 = (

                            px
                            -
                            seg_vx * 0.10,

                            py
                            -
                            seg_vy * 0.10
                        )

                        ponto_b2 = (

                            px
                            +
                            seg_vx * 0.10,

                            py
                            +
                            seg_vy * 0.10
                        )

                        ponto_pt = (

                            px
                            +
                            nx * 0.20,

                            py
                            +
                            ny * 0.20
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

                                'layer':
                                    'PROJ_ELETRICA_TOMADA'
                            }
                        )

                        if is_ambiente_molhado:

                            ponto_medio_base = (

                                px,
                                py
                            )

                            msp.add_solid(

                                [

                                    ponto_b1,

                                    ponto_medio_base,

                                    ponto_pt
                                ],

                                dxfattribs={

                                    'layer':
                                        'PROJ_ELETRICA_TOMADA'
                                }
                            )

        # ====================================================
        # SALVA O DXF
        # ====================================================

        doc.saveas(
            tmp_in_path
        )

        with open(
            tmp_in_path,
            "rb"
        ) as f:

            out_bytes = f.read()

        return out_bytes

    except Exception as e:

        raise e

    finally:

        if (

            tmp_in_path

            and

            os.path.exists(
                tmp_in_path
            )
        ):

            os.remove(
                tmp_in_path
            )
