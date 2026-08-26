import ezdxf
import math
import tempfile
import os


# ============================================================
# CONFIGURAÇÕES DE SEGURANÇA PARA POSICIONAMENTO
# ============================================================

# Distância mínima entre uma tomada e o vértice/canto da parede
MARGEM_CANTO = 0.35

# Distância de segurança em torno de portas e soleiras
MARGEM_VAO = 0.35

# Distância mínima considerada para identificar um elemento
# como pertencente a uma determinada parede
TOLERANCIA_PAREDE = 0.60


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

    qtd_ilum = 1 if area <= 10 else math.ceil(area / 10)

    carga_ilum = (
        100
        if area <= 6
        else 100 + (((area - 6) // 4) * 60)
    )

    nome_lower = nome.lower().strip()
    nome_words = nome_lower.replace('-', ' ').split()

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
        or any(
            w in nome_words
            for w in ["as", "wc", "bwc"]
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

        qtd_tugs = math.ceil(perimetro / 3.5)

        if qtd_tugs <= 3:
            carga_tugs = qtd_tugs * 600
        else:
            carga_tugs = (
                (3 * 600)
                + ((qtd_tugs - 3) * 100)
            )

    elif is_corredor:

        comprimento_estimado = (perimetro / 2) - 1

        if comprimento_estimado <= 3:
            qtd_tugs = 1
        else:
            qtd_tugs = max(
                1,
                math.ceil(comprimento_estimado / 3)
            )

        carga_tugs = qtd_tugs * 100

    else:

        qtd_tugs = math.ceil(perimetro / 5)

        carga_tugs = qtd_tugs * 100

    tue_nome = "-"
    qtd_tue = 0
    carga_tue = 0

    if (
        any(
            x in nome_lower
            for x in ["banh", "sanit"]
        )
        or any(
            w in nome_words
            for w in ["wc", "bwc"]
        )
    ):

        tue_nome = "Chuveiro Elétrico"
        qtd_tue = 1
        carga_tue = 5500

    elif any(
        x in nome_lower
        for x in ["coz"]
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
            for x in ["serv", "lavand"]
        )
        or "as" in nome_words
    ):

        tue_nome = "Máquina de Lavar"
        qtd_tue = 1
        carga_tue = 1000

    return {
        "Qtd Ilum.": qtd_ilum,

        "Pot. Unit. Ilum (VA)":
            round(carga_ilum / qtd_ilum)
            if qtd_ilum > 0 else 0,

        "Carga Ilum. (VA)": carga_ilum,

        "TUGs (Qtd)": qtd_tugs,

        "Pot. Unit. TUG (VA)":
            600 if is_umida else 100,

        "Carga TUGs (VA)": carga_tugs,

        "Equipamento TUE": tue_nome,

        "Qtd TUE": qtd_tue,

        "Pot. Unit. TUE (VA)":
            round(
                carga_tue / max(1, qtd_tue)
            ),

        "Carga TUE (VA)": carga_tue
    }


# ============================================================
# PONTO DENTRO DE POLÍGONO
# ============================================================

def ponto_em_poligono(x, y, polilinha):

    n = len(polilinha)

    if n < 3:
        return False

    dentro = False

    p1x, p1y = polilinha[0]

    for i in range(n + 1):

        p2x, p2y = polilinha[i % n]

        if y > min(p1y, p2y):

            if y <= max(p1y, p2y):

                if x <= max(p1x, p2x):

                    if p1y != p2y:

                        xinters = (
                            (y - p1y)
                            * (p2x - p1x)
                            / (p2y - p1y)
                            + p1x
                        )

                    else:
                        xinters = p1x

                    if (
                        p1x == p2x
                        or x <= xinters
                    ):
                        dentro = not dentro

        p1x, p1y = p2x, p2y

    return dentro


# ============================================================
# PONTO AO LONGO DO PERÍMETRO
# ============================================================

def get_ponto_perimetro(d, segs):

    acumulado = 0

    for pt1, pt2, dst in segs:

        if (
            acumulado + dst >= d
            or math.isclose(
                acumulado + dst,
                d,
                abs_tol=1e-5
            )
        ):

            if dst == 0:
                return (
                    pt1[0],
                    pt1[1],
                    1,
                    0
                )

            ratio = (
                d - acumulado
            ) / dst

            return (
                pt1[0]
                + (pt2[0] - pt1[0]) * ratio,

                pt1[1]
                + (pt2[1] - pt1[1]) * ratio,

                (pt2[0] - pt1[0]) / dst,

                (pt2[1] - pt1[1]) / dst
            )

        acumulado += dst

    pt1, pt2, dst = segs[-1]

    return (
        pt2[0],
        pt2[1],
        (pt2[0] - pt1[0]) / dst,
        (pt2[1] - pt1[1]) / dst
    )


# ============================================================
# NORMAL INTERNA DA PAREDE
# ============================================================

def get_inside_normal(
    vx,
    vy,
    start_x,
    start_y,
    cx,
    cy
):

    n1x, n1y = -vy, vx
    n2x, n2y = vy, -vx

    dist1 = math.hypot(
        cx - (start_x + n1x),
        cy - (start_y + n1y)
    )

    dist2 = math.hypot(
        cx - (start_x + n2x),
        cy - (start_y + n2y)
    )

    if dist1 < dist2:
        return n1x, n1y

    return n2x, n2y


# ============================================================
# DISTÂNCIA DE PONTO A SEGMENTO
# ============================================================

def point_seg_dist(px, py, pt1, pt2):

    l2 = (
        (pt1[0] - pt2[0]) ** 2
        + (pt1[1] - pt2[1]) ** 2
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
                * (pt2[0] - pt1[0])
                +
                (py - pt1[1])
                * (pt2[1] - pt1[1])
            ) / l2
        )
    )

    return math.hypot(
        px - (
            pt1[0]
            + t * (pt2[0] - pt1[0])
        ),
        py - (
            pt1[1]
            + t * (pt2[1] - pt1[1])
        )
    )


# ============================================================
# PROJEÇÃO DE PONTO EM PAREDE
# ============================================================

def projetar_ponto_na_parede(px, py, pt1, pt2):

    vx = pt2[0] - pt1[0]
    vy = pt2[1] - pt1[1]

    comprimento = math.hypot(vx, vy)

    if comprimento == 0:
        return 0.0

    return (
        (
            (px - pt1[0]) * vx
            +
            (py - pt1[1]) * vy
        )
        / (comprimento ** 2)
    )


# ============================================================
# INTERVALOS LIVRES DE UMA PAREDE
#
# Aqui está a principal alteração.
#
# A parede é dividida em:
#
# [ canto ] [ trecho livre ] [ porta ] [ trecho livre ] [ canto ]
#
# As tomadas somente podem ser colocadas nos trechos livres.
# ============================================================

def obter_intervalos_livres_parede(
    parede,
    portas,
    soleiras,
    margem_canto=MARGEM_CANTO,
    margem_vao=MARGEM_VAO
):

    pt1 = parede['p1']
    pt2 = parede['p2']

    comprimento = parede['length']

    if comprimento <= (
        2 * margem_canto
    ):

        return []

    intervalos_proibidos = []

    # --------------------------------------------------------
    # CANTOS DA PAREDE
    # --------------------------------------------------------

    intervalos_proibidos.append(
        (
            0,
            margem_canto
        )
    )

    intervalos_proibidos.append(
        (
            comprimento - margem_canto,
            comprimento
        )
    )

    # --------------------------------------------------------
    # PORTAS
    # --------------------------------------------------------

    for porta in portas:

        d1 = point_seg_dist(
            porta['p1'][0],
            porta['p1'][1],
            pt1,
            pt2
        )

        d2 = point_seg_dist(
            porta['p2'][0],
            porta['p2'][1],
            pt1,
            pt2
        )

        distancia_porta = min(d1, d2)

        if distancia_porta > TOLERANCIA_PAREDE:
            continue

        t1 = projetar_ponto_na_parede(
            porta['p1'][0],
            porta['p1'][1],
            pt1,
            pt2
        )

        t2 = projetar_ponto_na_parede(
            porta['p2'][0],
            porta['p2'][1],
            pt1,
            pt2
        )

        pos1 = max(
            0,
            min(
                comprimento,
                t1 * comprimento
            )
        )

        pos2 = max(
            0,
            min(
                comprimento,
                t2 * comprimento
            )
        )

        inicio = min(pos1, pos2)
        fim = max(pos1, pos2)

        # Expande a área proibida
        inicio -= margem_vao
        fim += margem_vao

        inicio = max(0, inicio)
        fim = min(comprimento, fim)

        intervalos_proibidos.append(
            (inicio, fim)
        )

    # --------------------------------------------------------
    # SOLEIRAS
    # --------------------------------------------------------

    for soleira in soleiras:

        d1 = point_seg_dist(
            soleira['p1'][0],
            soleira['p1'][1],
            pt1,
            pt2
        )

        d2 = point_seg_dist(
            soleira['p2'][0],
            soleira['p2'][1],
            pt1,
            pt2
        )

        distancia_soleira = min(d1, d2)

        if distancia_soleira > TOLERANCIA_PAREDE:
            continue

        t1 = projetar_ponto_na_parede(
            soleira['p1'][0],
            soleira['p1'][1],
            pt1,
            pt2
        )

        t2 = projetar_ponto_na_parede(
            soleira['p2'][0],
            soleira['p2'][1],
            pt1,
            pt2
        )

        pos1 = max(
            0,
            min(
                comprimento,
                t1 * comprimento
            )
        )

        pos2 = max(
            0,
            min(
                comprimento,
                t2 * comprimento
            )
        )

        inicio = min(pos1, pos2)
        fim = max(pos1, pos2)

        inicio -= margem_vao
        fim += margem_vao

        inicio = max(0, inicio)
        fim = min(comprimento, fim)

        intervalos_proibidos.append(
            (inicio, fim)
        )

    # --------------------------------------------------------
    # ORDENA OS INTERVALOS PROIBIDOS
    # --------------------------------------------------------

    intervalos_proibidos.sort(
        key=lambda x: x[0]
    )

    # --------------------------------------------------------
    # UNE INTERVALOS SOBREPOSTOS
    # --------------------------------------------------------

    proibidos_unidos = []

    for inicio, fim in intervalos_proibidos:

        if not proibidos_unidos:

            proibidos_unidos.append(
                [inicio, fim]
            )

        else:

            ultimo = proibidos_unidos[-1]

            if inicio <= ultimo[1]:

                ultimo[1] = max(
                    ultimo[1],
                    fim
                )

            else:

                proibidos_unidos.append(
                    [inicio, fim]
                )

    # --------------------------------------------------------
    # CALCULA OS TRECHOS LIVRES
    # --------------------------------------------------------

    livres = []

    cursor = 0

    for inicio, fim in proibidos_unidos:

        if inicio > cursor:

            if (
                inicio - cursor
                >= 0.15
            ):

                livres.append(
                    (
                        cursor,
                        inicio
                    )
                )

        cursor = max(
            cursor,
            fim
        )

    if cursor < comprimento:

        if (
            comprimento - cursor
            >= 0.15
        ):

            livres.append(
                (
                    cursor,
                    comprimento
                )
            )

    return livres


# ============================================================
# CONVERTE POSIÇÃO DA PAREDE EM COORDENADA
# ============================================================

def ponto_na_parede_por_distancia(
    parede,
    distancia
):

    pt1 = parede['p1']

    vx = parede['vx']
    vy = parede['vy']

    return (
        pt1[0] + vx * distancia,
        pt1[1] + vy * distancia
    )


# ============================================================
# GERA PONTOS DE TOMADAS EM UMA PAREDE
# ============================================================

def gerar_pontos_em_intervalo(
    parede,
    intervalo,
    quantidade
):

    if quantidade <= 0:
        return []

    inicio, fim = intervalo

    comprimento = fim - inicio

    if comprimento <= 0:
        return []

    pontos = []

    # Distribuição uniforme dentro do trecho.
    # Nunca toca nas extremidades.
    passo = comprimento / quantidade

    for i in range(quantidade):

        distancia = (
            inicio
            + passo * (i + 0.5)
        )

        pontos.append(
            ponto_na_parede_por_distancia(
                parede,
                distancia
            )
        )

    return pontos


# ============================================================
# ESCOLHE PONTOS SEGUROS PARA UMA QUANTIDADE EXATA
#
# IMPORTANTE:
# Esta função SEMPRE tenta retornar exatamente "quantidade".
# ============================================================

def escolher_pontos_tomadas(
    paredes,
    portas,
    soleiras,
    quantidade
):

    if quantidade <= 0:
        return []

    candidatos = []

    # --------------------------------------------------------
    # MONTA TODOS OS TRECHOS LIVRES DAS PAREDES
    # --------------------------------------------------------

    for indice, parede in enumerate(paredes):

        intervalos = obter_intervalos_livres_parede(
            parede,
            portas,
            soleiras
        )

        for intervalo in intervalos:

            inicio, fim = intervalo

            comprimento = fim - inicio

            if comprimento > 0.15:

                candidatos.append(
                    {
                        'parede': parede,
                        'intervalo': intervalo,
                        'comprimento': comprimento,
                        'indice_parede': indice
                    }
                )

    if not candidatos:
        return []

    # --------------------------------------------------------
    # ORDENA PELOS TRECHOS MAIORES
    # --------------------------------------------------------

    candidatos.sort(
        key=lambda x: x['comprimento'],
        reverse=True
    )

    # --------------------------------------------------------
    # PRIMEIRA DISTRIBUIÇÃO:
    # UMA TOMADA POR TRECHO QUANDO POSSÍVEL
    #
    # Isso evita concentrar todas as tomadas em uma única parede.
    # --------------------------------------------------------

    pontos = []

    quantidade_restante = quantidade

    for candidato in candidatos:

        if quantidade_restante <= 0:
            break

        ponto = gerar_pontos_em_intervalo(
            candidato['parede'],
            candidato['intervalo'],
            1
        )[0]

        pontos.append(
            {
                'ponto': ponto,
                'parede': candidato['parede'],
                'intervalo': candidato['intervalo']
            }
        )

        quantidade_restante -= 1

    # --------------------------------------------------------
    # SE AINDA FALTAM TOMADAS:
    # DISTRIBUI NOVAMENTE NOS TRECHOS
    # --------------------------------------------------------

    rodada = 0

    while quantidade_restante > 0:

        houve_insercao = False

        for candidato in candidatos:

            if quantidade_restante <= 0:
                break

            # Verifica quantas tomadas já existem
            # neste mesmo trecho
            tomadas_no_trecho = [
                p
                for p in pontos
                if (
                    p['parede'] is candidato['parede']
                    and p['intervalo']
                    == candidato['intervalo']
                )
            ]

            qtd_atual = len(
                tomadas_no_trecho
            )

            nova_qtd = qtd_atual + 1

            novos_pontos = gerar_pontos_em_intervalo(
                candidato['parede'],
                candidato['intervalo'],
                nova_qtd
            )

            # Remove os pontos antigos deste trecho
            pontos = [
                p
                for p in pontos
                if not (
                    p['parede'] is candidato['parede']
                    and p['intervalo']
                    == candidato['intervalo']
                )
            ]

            # Adiciona os novos pontos
            for ponto in novos_pontos:

                pontos.append(
                    {
                        'ponto': ponto,
                        'parede': candidato['parede'],
                        'intervalo': candidato['intervalo']
                    }
                )

            quantidade_restante -= 1

            houve_insercao = True

        rodada += 1

        if not houve_insercao:
            break

        # Segurança
        if rodada > quantidade + 5:
            break

    # --------------------------------------------------------
    # RETORNA SOMENTE COORDENADAS
    # --------------------------------------------------------

    return [
        item['ponto']
        for item in pontos
    ][:quantidade]


# ============================================================
# PROCESSAMENTO DO DXF
# ============================================================

def processar_dxf(caminho_arquivo):

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

        if hasattr(entity.dxf, 'layer'):

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
            "A(s) seguinte(s) camada(s) obrigatória(s) "
            "está(ão) vazia(s) ou ausente(s): "
            + ", ".join(camadas_vazias)
            + ". Certifique-se de desenhar os elementos "
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

        if (
            tipo in [
                'LWPOLYLINE',
                'POLYLINE'
            ]
            and layer == 'IA_AMBIENTES'
        ):

            try:

                if tipo == 'LWPOLYLINE':

                    pontos = [
                        (p[0], p[1])
                        for p in entity.get_points(
                            format='xy'
                        )
                    ]

                else:

                    pontos = [
                        (
                            v.dxf.location.x,
                            v.dxf.location.y
                        )
                        for v in entity.vertices
                    ]

                if pontos:
                    polilinhas.append(
                        pontos
                    )

            except:
                pass

        elif (
            tipo in ['TEXT', 'MTEXT']
            and layer == 'IA_TEXTOS'
        ):

            try:

                texto_str = (
                    entity.text
                    if tipo == 'MTEXT'
                    else entity.dxf.text
                ).strip()

                if texto_str:

                    textos.append(
                        {
                            'nome': texto_str,
                            'x': entity.dxf.insert.x,
                            'y': entity.dxf.insert.y
                        }
                    )

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
            max_x - min_x
        ) * (
            max_y - min_y
        )

        perimetro = (
            (max_x - min_x) * 2
        ) + (
            (max_y - min_y) * 2
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

        resultados.append(
            {
                "Ambiente": nome_ambiente,

                "Centro_X":
                    (min_x + max_x) / 2,

                "Centro_Y":
                    (min_y + max_y) / 2,

                "Área (m²)": area,

                "Perímetro (m)":
                    perimetro,

                "Qtd Ilum.":
                    int(cargas["Qtd Ilum."]),

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
            }
        )

    return resultados


# ============================================================
# GERA CAD UNIFILAR
# ============================================================

def gerar_cad_unifilar(
    dxf_bytes,
    dados_editados,
    local_qdc
):

    tmp_in_path = ""

    try:

        # ----------------------------------------------------
        # SALVA DXF TEMPORÁRIO
        # ----------------------------------------------------

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".dxf"
        ) as tmp_in:

            tmp_in.write(dxf_bytes)

            tmp_in_path = tmp_in.name

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

            if hasattr(entity.dxf, 'layer'):

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
                "A(s) seguinte(s) camada(s) "
                "obrigatória(s) está(ão) vazia(s) "
                "ou ausente(s): "
                + ", ".join(camadas_vazias)
                + ". Verifique se os elementos "
                "estão corretamente posicionados "
                "em suas camadas antes de processar."
            )

        # ----------------------------------------------------
        # CAMADAS DO PROJETO
        # ----------------------------------------------------

        camadas = {

            "PROJ_ELETRICA_LUZ": 2,

            "PROJ_ELETRICA_QDC": 1,

            "PROJ_ELETRICA_TEXTO": 2,

            "PROJ_ELETRICA_TOMADA": 4,

            "PROJ_ELETRICA_INTERRUPTOR": 5,

            "PROJ_ELETRICA_DEBUG": 6
        }

        for nome_l, cor_l in camadas.items():

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
        # LEITURA DOS ELEMENTOS DO DXF
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

            # ------------------------------------------------
            # AMBIENTES
            # ------------------------------------------------

            if (
                tipo in [
                    'LWPOLYLINE',
                    'POLYLINE'
                ]
                and layer == 'IA_AMBIENTES'
            ):

                try:

                    if tipo == 'LWPOLYLINE':

                        pontos = [
                            (p[0], p[1])
                            for p in entity.get_points(
                                format='xy'
                            )
                        ]

                    else:

                        pontos = [
                            (
                                v.dxf.location.x,
                                v.dxf.location.y
                            )
                            for v in entity.vertices
                        ]

                    if pontos:

                        polilinhas.append(
                            pontos
                        )

                except:

                    pass

            # ------------------------------------------------
            # TEXTOS
            # ------------------------------------------------

            elif (
                tipo in ['TEXT', 'MTEXT']
                and layer == 'IA_TEXTOS'
            ):

                try:

                    texto_str = (
                        entity.text
                        if tipo == 'MTEXT'
                        else entity.dxf.text
                    ).strip()

                    if texto_str:

                        textos.append(
                            {
                                'nome': texto_str,
                                'x': entity.dxf.insert.x,
                                'y': entity.dxf.insert.y
                            }
                        )

                except:

                    pass

            # ------------------------------------------------
            # PORTAS
            # ------------------------------------------------

            elif layer == 'IA_PORTAS':

                if tipo == 'LINE':

                    portas_raw.append(
                        {
                            'p1': (
                                entity.dxf.start.x,
                                entity.dxf.start.y
                            ),

                            'p2': (
                                entity.dxf.end.x,
                                entity.dxf.end.y
                            )
                        }
                    )

                elif tipo in [
                    'LWPOLYLINE',
                    'POLYLINE'
                ]:

                    try:

                        pts = [
                            (p[0], p[1])
                            for p in entity.get_points(
                                format='xy'
                            )
                        ]

                        if len(pts) >= 2:

                            portas_raw.append(
                                {
                                    'p1': pts[0],
                                    'p2': pts[-1]
                                }
                            )

                    except:

                        pass

            # ------------------------------------------------
            # SOLEIRAS
            # ------------------------------------------------

            elif layer == 'IA_SOLEIRAS':

                if tipo == 'LINE':

                    soleiras_raw.append(
                        {
                            'p1': (
                                entity.dxf.start.x,
                                entity.dxf.start.y
                            ),

                            'p2': (
                                entity.dxf.end.x,
                                entity.dxf.end.y
                            )
                        }
                    )

                elif tipo in [
                    'LWPOLYLINE',
                    'POLYLINE'
                ]:

                    try:

                        pts = [
                            (p[0], p[1])
                            for p in entity.get_points(
                                format='xy'
                            )
                        ]

                        if len(pts) >= 2:

                            soleiras_raw.append(
                                {
                                    'p1': pts[0],
                                    'p2': pts[-1]
                                }
                            )

                    except:

                        pass

        # ====================================================
        # DEBUG DAS SOLEIRAS COM PORTAS
        # ====================================================

        raio_circulo = 0.15

        soleiras_com_porta = []

        for s in soleiras_raw:

            s_p1 = s['p1']
            s_p2 = s['p2']

            porta_encostada = None

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

                pm_porta_x = (
                    p['p1'][0]
                    + p['p2'][0]
                ) / 2

                pm_porta_y = (
                    p['p1'][1]
                    + p['p2'][1]
                ) / 2

                d3 = point_seg_dist(
                    pm_porta_x,
                    pm_porta_y,
                    s_p1,
                    s_p2
                )

                if (
                    d1 < 0.15
                    or d2 < 0.15
                    or d3 < 0.15
                ):

                    porta_encostada = p
                    break

            if porta_encostada is not None:

                soleiras_com_porta.append(
                    {
                        's': s,
                        'porta': porta_encostada
                    }
                )

        # ====================================================
        # PROCESSAMENTO VISUAL DAS SOLEIRAS
        # ====================================================

        for item in soleiras_com_porta:

            s = item['s']
            p_porta = item['porta']

            s_pA = s['p1']
            s_pB = s['p2']

            sm_x = (
                s_pA[0] + s_pB[0]
            ) / 2

            sm_y = (
                s_pA[1] + s_pB[1]
            ) / 2

            d_p1_sA = math.hypot(
                p_porta['p1'][0] - s_pA[0],
                p_porta['p1'][1] - s_pA[1]
            )

            d_p1_sB = math.hypot(
                p_porta['p1'][0] - s_pB[0],
                p_porta['p1'][1] - s_pB[1]
            )

            dobradiça_pt = (
                p_porta['p1']
                if d_p1_sA < d_p1_sB
                else p_porta['p2']
            )

            d_sA_dob = math.hypot(
                s_pA[0] - dobradiça_pt[0],
                s_pA[1] - dobradiça_pt[1]
            )

            d_sB_dob = math.hypot(
                s_pB[0] - dobradiça_pt[0],
                s_pB[1] - dobradiça_pt[1]
            )

            p1 = (
                s_pA
                if d_sA_dob > d_sB_dob
                else s_pB
            )

            p4 = (
                s_pB
                if d_sA_dob > d_sB_dob
                else s_pA
            )

            s_len = math.hypot(
                p4[0] - p1[0],
                p4[1] - p1[1]
            )

            if s_len == 0:
                continue

            vx = (
                p4[0] - p1[0]
            ) / s_len

            vy = (
                p4[1] - p1[1]
            ) / s_len

            ambientes_adjacentes = []

            for poly in polilinhas:

                xs = [
                    pt[0]
                    for pt in poly
                ]

                ys = [
                    pt[1]
                    for pt in poly
                ]

                if (
                    min(xs) - 0.5
                    <= sm_x
                    <= max(xs) + 0.5
                    and
                    min(ys) - 0.5
                    <= sm_y
                    <= max(ys) + 0.5
                ):

                    ambientes_adjacentes.append(
                        poly
                    )

            if len(ambientes_adjacentes) >= 2:

                poly_a = ambientes_adjacentes[0]
                poly_b = ambientes_adjacentes[1]

                cx_a = (
                    sum(
                        pt[0]
                        for pt in poly_a
                    )
                    / len(poly_a)
                )

                cy_a = (
                    sum(
                        pt[1]
                        for pt in poly_a
                    )
                    / len(poly_a)
                )

                nx_1, ny_1 = get_inside_normal(
                    vx,
                    vy,
                    p1[0],
                    p1[1],
                    cx_a,
                    cy_a
                )

                c_test_p2 = (
                    p1[0] + nx_1 * raio_circulo,
                    p1[1] + ny_1 * raio_circulo
                )

                target_poly_p2 = (
                    poly_a
                    if ponto_em_poligono(
                        c_test_p2[0],
                        c_test_p2[1],
                        poly_a
                    )
                    else poly_b
                )

                target_poly_p3 = (
                    poly_b
                    if target_poly_p2 == poly_a
                    else poly_a
                )

                cx_p2 = (
                    sum(
                        pt[0]
                        for pt in target_poly_p2
                    )
                    / len(target_poly_p2)
                )

                cy_p2 = (
                    sum(
                        pt[1]
                        for pt in target_poly_p2
                    )
                    / len(target_poly_p2)
                )

                nx_p2, ny_p2 = get_inside_normal(
                    vx,
                    vy,
                    p1[0],
                    p1[1],
                    cx_p2,
                    cy_p2
                )

                center_p2 = (
                    p1[0] + nx_p2 * raio_circulo,
                    p1[1] + ny_p2 * raio_circulo
                )

                cx_p3 = (
                    sum(
                        pt[0]
                        for pt in target_poly_p3
                    )
                    / len(target_poly_p3)
                )

                cy_p3 = (
                    sum(
                        pt[1]
                        for pt in target_poly_p3
                    )
                    / len(target_poly_p3)
                )

                nx_p3, ny_p3 = get_inside_normal(
                    vx,
                    vy,
                    p4[0],
                    p4[1],
                    cx_p3,
                    cy_p3
                )

                center_p3 = (
                    p4[0] + nx_p3 * raio_circulo,
                    p4[1] + ny_p3 * raio_circulo
                )

                if ponto_em_poligono(
                    center_p2[0],
                    center_p2[1],
                    target_poly_p2
                ):

                    msp.add_circle(
                        center=center_p2,
                        radius=raio_circulo,
                        dxfattribs={
                            'layer':
                                'PROJ_ELETRICA_DEBUG',
                            'color': 6
                        }
                    )

                if ponto_em_poligono(
                    center_p3[0],
                    center_p3[1],
                    target_poly_p3
                ):

                    msp.add_circle(
                        center=center_p3,
                        radius=raio_circulo,
                        dxfattribs={
                            'layer':
                                'PROJ_ELETRICA_DEBUG',
                            'color': 6
                        }
                    )

            elif len(ambientes_adjacentes) == 1:

                poly = ambientes_adjacentes[0]

                cx = (
                    sum(
                        pt[0]
                        for pt in poly
                    )
                    / len(poly)
                )

                cy = (
                    sum(
                        pt[1]
                        for pt in poly
                    )
                    / len(poly)
                )

                nx, ny = get_inside_normal(
                    vx,
                    vy,
                    p1[0],
                    p1[1],
                    cx,
                    cy
                )

                center_p2 = (
                    p1[0] + nx * raio_circulo,
                    p1[1] + ny * raio_circulo
                )

                if ponto_em_poligono(
                    center_p2[0],
                    center_p2[1],
                    poly
                ):

                    msp.add_circle(
                        center=center_p2,
                        radius=raio_circulo,
                        dxfattribs={
                            'layer':
                                'PROJ_ELETRICA_DEBUG',
                            'color': 6
                        }
                    )

        # ====================================================
        # DADOS DA TABELA
        # ====================================================

        ambientes_processados = {}

        dict_dados = {
            row['Ambiente']: row
            for row in dados_editados
        }

        # ====================================================
        # PROCESSA CADA AMBIENTE
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
                max_x - min_x
            ) * (
                max_y - min_y
            )

            perimetro = (
                (max_x - min_x) * 2
            ) + (
                (max_y - min_y) * 2
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

                ambientes_processados[nome] += 1

                nome_busca = (
                    f"{nome} "
                    f"{ambientes_processados[nome]}"
                )

            else:

                ambientes_processados[nome] = 1

                nome_busca = nome

            row_data = dict_dados.get(
                nome_busca,
                dict_dados.get(
                    nome,
                    None
                )
            )

            centro_x = (
                min_x + max_x
            ) / 2

            centro_y = (
                min_y + max_y
            ) / 2

            largura = max_x - min_x
            comprimento = max_y - min_y

            # =================================================
            # PAREDES DO AMBIENTE
            # =================================================

            segmentos_crus = []
            comp_total = 0

            poly = list(polilinha)

            if (
                len(poly) > 1
                and poly[0] != poly[-1]
            ):
                poly.append(
                    poly[0]
                )

            for i in range(
                len(poly) - 1
            ):

                dst = math.hypot(
                    poly[i + 1][0]
                    - poly[i][0],

                    poly[i + 1][1]
                    - poly[i][1]
                )

                if dst > 0.1:

                    segmentos_crus.append(
                        (
                            poly[i],
                            poly[i + 1],
                            dst
                        )
                    )

                    comp_total += dst

            logical_walls = []

            for pt1, pt2, dst in segmentos_crus:

                vx = (
                    pt2[0] - pt1[0]
                ) / dst

                vy = (
                    pt2[1] - pt1[1]
                ) / dst

                logical_walls.append(
                    {
                        'p1': pt1,
                        'p2': pt2,
                        'length': dst,
                        'vx': vx,
                        'vy': vy
                    }
                )

            # =================================================
            # PORTAS DESTE AMBIENTE
            # =================================================

            unique_portas = [
                p
                for p in portas_raw
                if (
                    min_x - 0.8
                    <= (
                        p['p1'][0]
                        + p['p2'][0]
                    ) / 2
                    <= max_x + 0.8
                    and
                    min_y - 0.8
                    <= (
                        p['p1'][1]
                        + p['p2'][1]
                    ) / 2
                    <= max_y + 0.8
                )
            ]

            # =================================================
            # SOLEIRAS DESTE AMBIENTE
            # =================================================

            unique_soleiras = [
                s
                for s in soleiras_raw
                if (
                    min_x - 0.8
                    <= (
                        s['p1'][0]
                        + s['p2'][0]
                    ) / 2
                    <= max_x + 0.8
                    and
                    min_y - 0.8
                    <= (
                        s['p1'][1]
                        + s['p2'][1]
                    ) / 2
                    <= max_y + 0.8
                )
            ]

            # =================================================
            # ILUMINAÇÃO
            # =================================================

            if row_data:

                qtd_ilum = int(
                    row_data.get(
                        "Qtd Ilum.",
                        1
                    )
                )

                pot_ilum_unit = int(
                    row_data.get(
                        "Pot. Unit. Ilum (VA)",
                        100
                    )
                )

                if qtd_ilum > 0:

                    pontos_luz = []

                    if largura >= comprimento:

                        if qtd_ilum == 1:

                            pontos_luz.append(
                                (
                                    centro_x,
                                    centro_y
                                )
                            )

                        else:

                            step = (
                                largura
                                / (
                                    qtd_ilum + 1
                                )
                            )

                            for i in range(
                                1,
                                qtd_ilum + 1
                            ):

                                pontos_luz.append(
                                    (
                                        min_x
                                        + step * i,
                                        centro_y
                                    )
                                )

                    else:

                        if qtd_ilum == 1:

                            pontos_luz.append(
                                (
                                    centro_x,
                                    centro_y
                                )
                            )

                        else:

                            step = (
                                comprimento
                                / (
                                    qtd_ilum + 1
                                )
                            )

                            for i in range(
                                1,
                                qtd_ilum + 1
                            ):

                                pontos_luz.append(
                                    (
                                        centro_x,
                                        min_y
                                        + step * i
                                    )
                                )

                    for lx, ly in pontos_luz:

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
                                'height': 0.15,
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
                                'height': 0.15,
                                'color': 2,
                                'insert': (
                                    lx + 0.3,
                                    ly + 0.15
                                )
                            }
                        )

            # =================================================
            # QDC
            # =================================================

            qdc_formatado = (
                str(local_qdc)
                .replace(
                    " (recomendado)",
                    ""
                )
                .strip()
                .upper()
            )

            nome_atual_upper = (
                nome.strip().upper()
            )

            is_ambiente_qdc = (
                nome_atual_upper
                == qdc_formatado
            )

            if (
                is_ambiente_qdc
                and logical_walls
            ):

                qdc_w = 0.4
                qdc_d = 0.15

                maior_parede = max(
                    logical_walls,
                    key=lambda w: w['length']
                )

                pt1 = maior_parede['p1']
                pt2 = maior_parede['p2']

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
                        or d_p2 < 0.6
                    ):

                        if is_vertical:

                            cortes_portas.append(
                                (
                                    min(
                                        p['p1'][1],
                                        p['p2'][1]
                                    ),
                                    max(
                                        p['p1'][1],
                                        p['p2'][1]
                                    )
                                )
                            )

                        else:

                            cortes_portas.append(
                                (
                                    min(
                                        p['p1'][0],
                                        p['p2'][0]
                                    ),
                                    max(
                                        p['p1'][0],
                                        p['p2'][0]
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
                        key=lambda x: x[0]
                    )

                    trechos_livres = []
                    cursor = parede_min

                    for c_inf, c_sup in cortes_portas:

                        if (
                            c_inf
                            > cursor + 0.1
                        ):

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

                        melhor_trecho = max(
                            trechos_livres,
                            key=lambda t:
                                t[1] - t[0]
                        )

                        mid_y = (
                            melhor_trecho[0]
                            + melhor_trecho[1]
                        ) / 2

                        mx = pt1[0]
                        my = mid_y

                    else:

                        mx = (
                            pt1[0]
                            + pt2[0]
                        ) / 2

                        my = (
                            pt1[1]
                            + pt2[1]
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
                        key=lambda x: x[0]
                    )

                    trechos_livres = []
                    cursor = parede_min

                    for c_inf, c_sup in cortes_portas:

                        if (
                            c_inf
                            > cursor + 0.1
                        ):

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

                        melhor_trecho = max(
                            trechos_livres,
                            key=lambda t:
                                t[1] - t[0]
                        )

                        mid_x = (
                            melhor_trecho[0]
                            + melhor_trecho[1]
                        ) / 2

                        mx = mid_x
                        my = pt1[1]

                    else:

                        mx = (
                            pt1[0]
                            + pt2[0]
                        ) / 2

                        my = (
                            pt1[1]
                            + pt2[1]
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
                # TUEs
                #
                # AGORA TAMBÉM UTILIZAM OS TRECHOS SEGUROS.
                # =================================================

                if qtd_tue > 0:

                    pontos_tue = escolher_pontos_tomadas(
                        logical_walls,
                        unique_portas,
                        unique_soleiras,
                        qtd_tue
                    )

                    # -------------------------------------------------
                    # GARANTIA EXTRA DE QUANTIDADE
                    #
                    # Se por alguma geometria extremamente pequena
                    # a função retornar menos pontos, usamos uma
                    # distribuição alternativa nas paredes.
                    # -------------------------------------------------

                    if len(pontos_tue) < qtd_tue:

                        pontos_tue = []

                        paredes_ordenadas = sorted(
                            logical_walls,
                            key=lambda w: w['length'],
                            reverse=True
                        )

                        for parede in paredes_ordenadas:

                            if len(pontos_tue) >= qtd_tue:
                                break

                            intervalo = (
                                MARGEM_CANTO,
                                parede['length']
                                - MARGEM_CANTO
                            )

                            if (
                                intervalo[1]
                                > intervalo[0]
                            ):

                                ponto = (
                                    gerar_pontos_em_intervalo(
                                        parede,
                                        intervalo,
                                        1
                                    )[0]
                                )

                                pontos_tue.append(
                                    ponto
                                )

                        # Se ainda faltar, repete nas paredes
                        # mantendo a margem dos cantos.
                        indice = 0

                        while (
                            len(pontos_tue)
                            < qtd_tue
                            and paredes_ordenadas
                        ):

                            parede = (
                                paredes_ordenadas[
                                    indice
                                    % len(
                                        paredes_ordenadas
                                    )
                                ]
                            )

                            intervalo = (
                                MARGEM_CANTO,
                                parede['length']
                                - MARGEM_CANTO
                            )

                            if (
                                intervalo[1]
                                > intervalo[0]
                            ):

                                qtd_local = 2 + (
                                    indice
                                    // len(
                                        paredes_ordenadas
                                    )
                                )

                                pts = (
                                    gerar_pontos_em_intervalo(
                                        parede,
                                        intervalo,
                                        qtd_local
                                    )
                                )

                                for pt in pts:

                                    if (
                                        len(pontos_tue)
                                        >= qtd_tue
                                    ):
                                        break

                                    pontos_tue.append(
                                        pt
                                    )

                            indice += 1

                            if indice > (
                                qtd_tue * 10
                            ):
                                break

                    # -------------------------------------------------
                    # DESENHA TUE
                    # -------------------------------------------------

                    for px, py in pontos_tue:

                        # Descobre parede mais próxima
                        parede = min(
                            logical_walls,
                            key=lambda w:
                                point_seg_dist(
                                    px,
                                    py,
                                    w['p1'],
                                    w['p2']
                                )
                        )

                        vx = parede['vx']
                        vy = parede['vy']

                        nx, ny = get_inside_normal(
                            vx,
                            vy,
                            px,
                            py,
                            centro_x,
                            centro_y
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
                                'height': 0.12,
                                'color': 2,
                                'insert': (
                                    px + nx * 0.35,
                                    py + ny * 0.35
                                )
                            }
                        )

                # =================================================
                # TUGs
                #
                # ESTA É A PRINCIPAL ALTERAÇÃO.
                # =================================================

                if qtd_tugs > 0:

                    pontos_tug = escolher_pontos_tomadas(
                        logical_walls,
                        unique_portas,
                        unique_soleiras,
                        qtd_tugs
                    )

                    # -------------------------------------------------
                    # GARANTIA EXTRA DE QUANTIDADE
                    # -------------------------------------------------

                    if len(pontos_tug) < qtd_tugs:

                        pontos_tug = []

                        paredes_ordenadas = sorted(
                            logical_walls,
                            key=lambda w: w['length'],
                            reverse=True
                        )

                        # Primeiro tenta uma tomada em cada parede
                        for parede in paredes_ordenadas:

                            if len(pontos_tug) >= qtd_tugs:
                                break

                            intervalo = (
                                MARGEM_CANTO,
                                parede['length']
                                - MARGEM_CANTO
                            )

                            if (
                                intervalo[1]
                                > intervalo[0]
                            ):

                                ponto = (
                                    gerar_pontos_em_intervalo(
                                        parede,
                                        intervalo,
                                        1
                                    )[0]
                                )

                                pontos_tug.append(
                                    ponto
                                )

                        # Depois completa a quantidade
                        indice = 0

                        while (
                            len(pontos_tug)
                            < qtd_tugs
                            and paredes_ordenadas
                        ):

                            parede = (
                                paredes_ordenadas[
                                    indice
                                    % len(
                                        paredes_ordenadas
                                    )
                                ]
                            )

                            intervalo = (
                                MARGEM_CANTO,
                                parede['length']
                                - MARGEM_CANTO
                            )

                            if (
                                intervalo[1]
                                > intervalo[0]
                            ):

                                qtd_local = 2 + (
                                    indice
                                    // len(
                                        paredes_ordenadas
                                    )
                                )

                                pts = (
                                    gerar_pontos_em_intervalo(
                                        parede,
                                        intervalo,
                                        qtd_local
                                    )
                                )

                                for pt in pts:

                                    if (
                                        len(pontos_tug)
                                        >= qtd_tugs
                                    ):
                                        break

                                    pontos_tug.append(
                                        pt
                                    )

                            indice += 1

                            if indice > (
                                qtd_tugs * 10
                            ):
                                break

                    # -------------------------------------------------
                    # DESENHA TODAS AS TUGs
                    # -------------------------------------------------

                    for px, py in pontos_tug:

                        # Identifica a parede onde o ponto foi criado
                        parede = min(
                            logical_walls,
                            key=lambda w:
                                point_seg_dist(
                                    px,
                                    py,
                                    w['p1'],
                                    w['p2']
                                )
                        )

                        seg_vx = parede['vx']
                        seg_vy = parede['vy']

                        nx, ny = get_inside_normal(
                            seg_vx,
                            seg_vy,
                            px,
                            py,
                            centro_x,
                            centro_y
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

                        # -------------------------------------------------
                        # SÍMBOLO DA TUG
                        # -------------------------------------------------

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

                        # -------------------------------------------------
                        # TOMADA EM AMBIENTE MOLHADO
                        # -------------------------------------------------

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
            and os.path.exists(
                tmp_in_path
            )
        ):

            os.remove(
                tmp_in_path
            )
