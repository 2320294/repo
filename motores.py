import ezdxf
import math
import tempfile
import os


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
    carga_ilum = 100 if area <= 6 else 100 + (((area - 6) // 4) * 60)

    nome_lower = nome.lower().strip()
    nome_words = nome_lower.replace('-', ' ').split()

    is_umida = (
        any(x in nome_lower for x in [
            "coz", "serv", "banh", "lav", "sanit", "área", "area"
        ])
        or any(w in nome_words for w in ["as", "wc", "bwc"])
    )

    is_corredor = any(x in nome_lower for x in [
        "hall", "corredor", "circulação", "circulacao"
    ])

    if is_umida:
        qtd_tugs = math.ceil(perimetro / 3.5)
        carga_tugs = (
            qtd_tugs * 600
            if qtd_tugs <= 3
            else (3 * 600) + ((qtd_tugs - 3) * 100)
        )

    elif is_corredor:
        comprimento_estimado = (perimetro / 2) - 1

        if comprimento_estimado <= 3:
            qtd_tugs = 1
        else:
            qtd_tugs = max(1, math.ceil(comprimento_estimado / 3))

        carga_tugs = qtd_tugs * 100

    else:
        qtd_tugs = math.ceil(perimetro / 5)
        carga_tugs = qtd_tugs * 100

    tue_nome = "-"
    qtd_tue = 0
    carga_tue = 0

    if any(x in nome_lower for x in ["banh", "sanit"]) or \
       any(w in nome_words for w in ["wc", "bwc"]):

        tue_nome = "Chuveiro Elétrico"
        qtd_tue = 1
        carga_tue = 5500

    elif any(x in nome_lower for x in ["coz"]):
        tue_nome = "Micro-ondas/Forno"
        qtd_tue = 1
        carga_tue = 2000

    elif any(x in nome_lower for x in ["quarto", "dorm", "suite"]):
        tue_nome = "Ar-Condicionado"
        qtd_tue = 1
        carga_tue = 1200

    elif any(x in nome_lower for x in ["serv", "lavand"]) or \
         "as" in nome_words:

        tue_nome = "Máquina de Lavar"
        qtd_tue = 1
        carga_tue = 1000

    return {
        "Qtd Ilum.": qtd_ilum,
        "Pot. Unit. Ilum (VA)": round(carga_ilum / qtd_ilum)
            if qtd_ilum > 0 else 0,
        "Carga Ilum. (VA)": carga_ilum,

        "TUGs (Qtd)": qtd_tugs,
        "Pot. Unit. TUG (VA)": 600 if is_umida else 100,
        "Carga TUGs (VA)": carga_tugs,

        "Equipamento TUE": tue_nome,
        "Qtd TUE": qtd_tue,
        "Pot. Unit. TUE (VA)": round(
            carga_tue / max(1, qtd_tue)
        ),
        "Carga TUE (VA)": carga_tue
    }


# ============================================================
# GEOMETRIA
# ============================================================

def ponto_em_poligono(x, y, polilinha):
    if not polilinha:
        return False

    n = len(polilinha)
    dentro = False

    p1x, p1y = polilinha[0]

    for i in range(n + 1):
        p2x, p2y = polilinha[i % n]

        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):

                    xinters = None

                    if p1y != p2y:
                        xinters = (
                            (y - p1y) *
                            (p2x - p1x) /
                            (p2y - p1y)
                        ) + p1x

                    if p1x == p2x or (
                        xinters is not None and x <= xinters
                    ):
                        dentro = not dentro

        p1x, p1y = p2x, p2y

    return dentro


def point_seg_dist(px, py, pt1, pt2):
    l2 = (
        (pt1[0] - pt2[0]) ** 2 +
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
                (px - pt1[0]) * (pt2[0] - pt1[0]) +
                (py - pt1[1]) * (pt2[1] - pt1[1])
            ) / l2
        )
    )

    proj_x = pt1[0] + t * (pt2[0] - pt1[0])
    proj_y = pt1[1] + t * (pt2[1] - pt1[1])

    return math.hypot(
        px - proj_x,
        py - proj_y
    )


def get_ponto_perimetro(d, segs):
    acumulado = 0

    for pt1, pt2, dst in segs:

        if acumulado + dst >= d or math.isclose(
            acumulado + dst,
            d,
            abs_tol=1e-5
        ):

            if dst == 0:
                return (
                    pt1[0],
                    pt1[1],
                    0,
                    0
                )

            ratio = (d - acumulado) / dst

            x = pt1[0] + (
                pt2[0] - pt1[0]
            ) * ratio

            y = pt1[1] + (
                pt2[1] - pt1[1]
            ) * ratio

            vx = (pt2[0] - pt1[0]) / dst
            vy = (pt2[1] - pt1[1]) / dst

            return x, y, vx, vy

        acumulado += dst

    pt1, pt2, dst = segs[-1]

    if dst == 0:
        return pt2[0], pt2[1], 0, 0

    return (
        pt2[0],
        pt2[1],
        (pt2[0] - pt1[0]) / dst,
        (pt2[1] - pt1[1]) / dst
    )


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

    d1 = math.hypot(
        cx - (start_x + n1x),
        cy - (start_y + n1y)
    )

    d2 = math.hypot(
        cx - (start_x + n2x),
        cy - (start_y + n2y)
    )

    return (
        (n1x, n1y)
        if d1 < d2
        else (n2x, n2y)
    )


# ============================================================
# NOVA FUNÇÃO:
# VERIFICA SE UMA TOMADA ESTÁ EM LOCAL PROIBIDO
# ============================================================

# ============================================================
# REGRAS DE SEGURANÇA PARA TOMADAS
# ============================================================

# Distância mínima entre o ponto da tomada e qualquer vértice
# (canto) do ambiente.
#
# 0.50 m = 50 cm.
#
# Isso impede que TUG/TUE sejam desenhadas exatamente nos
# cantos ou muito próximas deles.
DISTANCIA_MINIMA_CANTO_TOMADA = 0.50

# Distâncias mínimas de outros elementos.
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
    """
    Retorna True somente quando o ponto está em uma posição segura.

    A tomada NÃO pode:
      1. ficar sobre um vértice/canto;
      2. ficar a menos de 0.50 m de qualquer vértice/canto;
      3. ficar sobre ou muito perto de uma porta;
      4. ficar sobre ou muito perto de uma soleira.
    """

    # --------------------------------------------------------
    # 1. NÃO PERMITIR PRÓXIMO DOS VÉRTICES
    # --------------------------------------------------------

    for vx, vy in polilinha:

        distancia = math.hypot(
            px - vx,
            py - vy
        )

        if distancia < distancia_canto:
            return False

    # --------------------------------------------------------
    # 2. NÃO PERMITIR SOBRE / PERTO DE PORTAS
    # --------------------------------------------------------

    for porta in portas_raw:

        d = point_seg_dist(
            px,
            py,
            porta['p1'],
            porta['p2']
        )

        if d < distancia_porta:
            return False

    # --------------------------------------------------------
    # 3. NÃO PERMITIR SOBRE / PERTO DE SOLEIRAS
    # --------------------------------------------------------

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
    """
    Procura uma posição válida ao longo do perímetro.

    Regra importante:
    mesmo que a posição calculada originalmente caia exatamente
    em um vértice, ela é rejeitada e o algoritmo procura uma nova
    posição afastada do canto.

    A busca é feita para os dois lados da posição desejada.
    """

    if comp_total <= 0:
        return None

    # --------------------------------------------------------
    # 1. TESTA A POSIÇÃO ORIGINAL
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 2. SE NÃO FOR VÁLIDA, AFASTA DO PONTO ORIGINAL
    #
    # O passo é de no máximo 10 cm.
    # Assim, se a posição original cair em um vértice,
    # a busca continuará até encontrar pelo menos 50 cm
    # de afastamento do canto.
    # --------------------------------------------------------

    passo_busca = 0.10

    # Nunca precisamos procurar indefinidamente.
    # 2,00 m é suficiente para contornar cantos, portas e soleiras
    # na maioria dos ambientes.
    max_busca = min(
        comp_total * 0.25,
        2.00
    )

    deslocamento = passo_busca

    while deslocamento <= max_busca:

        # Primeiro tenta para um lado e depois para o outro.
        distancias_teste = [
            distancia_original - deslocamento,
            distancia_original + deslocamento
        ]

        for distancia_teste in distancias_teste:

            # Não deixa sair do perímetro.
            if distancia_teste <= 0:
                continue

            if distancia_teste >= comp_total:
                continue

            tx, ty, tvx, tvy = get_ponto_perimetro(
                distancia_teste,
                segmentos_crus
            )

            if ponto_tomada_valido(
                tx,
                ty,
                polilinha,
                portas_raw,
                soleiras_raw
            ):
                return tx, ty, tvx, tvy

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
    """
    Procura uma posição válida em uma parede específica.

    Usada principalmente para TUE.

    A posição nunca é aceita se estiver próxima de um dos
    extremos da parede. Isso evita que uma tomada TUE seja
    desenhada no vértice do ambiente.

    Também procura outras posições da mesma parede caso a posição
    inicial esteja ocupada por porta, soleira ou esteja muito
    próxima de um canto.
    """

    dx = pt2[0] - pt1[0]
    dy = pt2[1] - pt1[1]

    comprimento = math.hypot(
        dx,
        dy
    )

    if comprimento <= 2 * distancia_canto:
        return None

    # --------------------------------------------------------
    # LIMITES FÍSICOS DA PAREDE
    #
    # A tomada precisa ficar pelo menos 0.50 m de cada extremo.
    # --------------------------------------------------------

    fator_min = (
        distancia_canto / comprimento
    )

    fator_max = (
        1.0 -
        distancia_canto / comprimento
    )

    fator_original = max(
        fator_min,
        min(
            fator_max,
            fator_original
        )
    )

    # --------------------------------------------------------
    # MONTA UMA LISTA DE FATORES A TESTAR.
    #
    # Começa pelo ponto desejado e vai se afastando dele.
    # --------------------------------------------------------

    fatores = [fator_original]

    passo_fator = 0.10 / comprimento
    deslocamento = passo_fator

    while (
        deslocamento <= 0.50
        and
        deslocamento < 1.0
    ):

        fator_esquerda = (
            fator_original -
            deslocamento
        )

        fator_direita = (
            fator_original +
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

    # --------------------------------------------------------
    # TESTA CADA POSIÇÃO
    # --------------------------------------------------------

    for fator in fatores:

        px = (
            pt1[0] +
            dx * fator
        )

        py = (
            pt1[1] +
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
            vx = dx / comprimento
            vy = dy / comprimento

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

def processar_dxf(caminho_arquivo):

    doc = ezdxf.readfile(caminho_arquivo)
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
        for cam, qtd in contagem_camadas.items()
        if qtd == 0
    ]

    if camadas_vazias:
        raise ValueError(
            "❌ Erro de Validação do DXF: "
            f"A(s) seguinte(s) camada(s) obrigatória(s) "
            f"está(ão) vazia(s) ou ausente(s): "
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
                    polilinhas.append(pontos)

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
                        'nome': texto_str,
                        'x': entity.dxf.insert.x,
                        'y': entity.dxf.insert.y
                    })

            except:
                pass

    resultados = []
    ambientes_processados = {}

    for polilinha in polilinhas:

        xs = [p[0] for p in polilinha]
        ys = [p[1] for p in polilinha]

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

        resultados.append({

            "Ambiente": nome_ambiente,

            "Centro_X":
                (min_x + max_x) / 2,

            "Centro_Y":
                (min_y + max_y) / 2,

            "Área (m²)": area,

            "Perímetro (m)": perimetro,

            "Qtd Ilum.":
                int(cargas["Qtd Ilum."]),

            "Pot. Unit. Ilum (VA)":
                int(cargas["Pot. Unit. Ilum (VA)"]),

            "Carga Ilum. (VA)":
                int(cargas["Carga Ilum. (VA)"]),

            "TUGs (Qtd)":
                int(cargas["TUGs (Qtd)"]),

            "Pot. Unit. TUG (VA)":
                int(cargas["Pot. Unit. TUG (VA)"]),

            "Carga TUGs (VA)":
                int(cargas["Carga TUGs (VA)"]),

            "Equipamento TUE":
                cargas["Equipamento TUE"],

            "Qtd TUE":
                int(cargas["Qtd TUE"]),

            "Pot. Unit. TUE (VA)":
                int(cargas["Pot. Unit. TUE (VA)"]),

            "Carga TUE (VA)":
                int(cargas["Carga TUE (VA)"])
        })

    return resultados


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
            for cam, qtd in contagem_camadas.items()
            if qtd == 0
        ]

        if camadas_vazias:

            raise ValueError(
                "❌ Erro de Geração do CAD: "
                f"A(s) seguinte(s) camada(s) obrigatória(s) "
                f"está(ão) vazia(s) ou ausente(s): "
                f"{', '.join(camadas_vazias)}. "
                "Verifique se os elementos estão "
                "corretamente posicionados em suas camadas "
                "antes de processar."
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
        # LEITURA DOS ELEMENTOS
        # ----------------------------------------------------

        polilinhas = []
        textos = []
        portas_raw = []
        soleiras_raw = []

        for entity in msp:

            tipo = entity.dxftype()

            if hasattr(entity.dxf, 'layer'):

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
                        polilinhas.append(pontos)

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
                            'nome': texto_str,
                            'x': entity.dxf.insert.x,
                            'y': entity.dxf.insert.y
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
                                for p in entity.get_points(
                                    format='xy'
                                )
                            ]

                        else:

                            pts = [
                                (
                                    v.dxf.location.x,
                                    v.dxf.location.y
                                )
                                for v in entity.vertices
                            ]

                        if len(pts) >= 2:

                            portas_raw.append({
                                'p1': pts[0],
                                'p2': pts[-1]
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
                                for p in entity.get_points(
                                    format='xy'
                                )
                            ]

                        else:

                            pts = [
                                (
                                    v.dxf.location.x,
                                    v.dxf.location.y
                                )
                                for v in entity.vertices
                            ]

                        if len(pts) >= 2:

                            soleiras_raw.append({
                                'p1': pts[0],
                                'p2': pts[-1]
                            })

                    except:
                        pass

        # ====================================================
        # IDENTIFICA SOLEIRAS ASSOCIADAS A PORTAS
        # ====================================================

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
                    p['p1'][0] +
                    p['p2'][0]
                ) / 2

                pm_porta_y = (
                    p['p1'][1] +
                    p['p2'][1]
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

                soleiras_com_porta.append({
                    's': s,
                    'porta': porta_encostada
                })

        # ====================================================
        # LIMPA DEBUG ANTIGO
        # ====================================================
        # O usuário pode executar o script sobre um DXF que já foi
        # gerado anteriormente. Nesse caso, os círculos magenta
        # antigos continuam dentro do arquivo e podem dar a impressão
        # de que P1 e P4 também estão sendo desenhados.
        #
        # Antes de gerar os novos pontos, remove TODOS os elementos
        # existentes no layer de DEBUG. Assim, somente P2 e P3 da
        # execução atual permanecerão no desenho.
        for entidade_debug in list(msp):
            try:
                if (
                    str(entidade_debug.dxf.layer)
                    .upper()
                    .strip()
                    == 'PROJ_ELETRICA_DEBUG'
                ):
                    msp.delete_entity(entidade_debug)
            except Exception:
                pass

        # ====================================================
        # DESENHO DOS PONTOS DEBUG DAS SOLEIRAS
        # REGRA DOS PONTOS DA PORTA: P1 -> P2 -> P3 -> P4
        #
        # P1 = encontro da porta com a soleira
        # P2 = segunda extremidade da porta / ponto superior esquerdo
        # P4 = extremidade oposta da soleira
        # P3 = quarto vértice, correspondente a P2 no outro lado
        #       da abertura.
        #
        # Os círculos DEBUG são permitidos SOMENTE em P2 e P3.
        # ====================================================

        raio_circulo = 0.15

        for item in soleiras_com_porta:

            s = item['s']
            p_porta = item['porta']

            s_pA = s['p1']
            s_pB = s['p2']

            # ------------------------------------------------
            # P1 = endpoint da porta que realmente encosta na
            # soleira. P2 = o outro endpoint da porta.
            # ------------------------------------------------
            d_porta_1 = point_seg_dist(
                p_porta['p1'][0],
                p_porta['p1'][1],
                s_pA,
                s_pB
            )

            d_porta_2 = point_seg_dist(
                p_porta['p2'][0],
                p_porta['p2'][1],
                s_pA,
                s_pB
            )

            if d_porta_1 <= d_porta_2:
                p1 = p_porta['p1']
                p2 = p_porta['p2']
            else:
                p1 = p_porta['p2']
                p2 = p_porta['p1']

            # ------------------------------------------------
            # P4 = extremidade da soleira que não é P1.
            # ------------------------------------------------
            d_p1_sA = math.hypot(
                p1[0] - s_pA[0],
                p1[1] - s_pA[1]
            )

            d_p1_sB = math.hypot(
                p1[0] - s_pB[0],
                p1[1] - s_pB[1]
            )

            p4 = (
                s_pA
                if d_p1_sB < d_p1_sA
                else s_pB
            )

            # ------------------------------------------------
            # Vetor P1 -> P4 = direção da soleira.
            # P3 é o quarto ponto do retângulo P1-P2-P3-P4.
            # ------------------------------------------------
            vx = p4[0] - p1[0]
            vy = p4[1] - p1[1]

            s_len = math.hypot(vx, vy)

            if s_len == 0:
                continue

            vx /= s_len
            vy /= s_len

            p3 = (
                p2[0] + (p4[0] - p1[0]),
                p2[1] + (p4[1] - p1[1])
            )

            # ------------------------------------------------
            # Centro aproximado da soleira.
            # ------------------------------------------------
            sm_x = (
                s_pA[0] + s_pB[0]
            ) / 2

            sm_y = (
                s_pA[1] + s_pB[1]
            ) / 2

            # ------------------------------------------------
            # Descobre os ambientes adjacentes à abertura.
            # ------------------------------------------------
            ambientes_adjacentes = []

            for poly in polilinhas:

                xs = [pt[0] for pt in poly]
                ys = [pt[1] for pt in poly]

                if (
                    min(xs) - 0.5 <= sm_x <= max(xs) + 0.5
                    and
                    min(ys) - 0.5 <= sm_y <= max(ys) + 0.5
                ):
                    ambientes_adjacentes.append(poly)

            # ------------------------------------------------
            # Função local para desenhar círculo somente se o
            # ponto deslocado estiver realmente dentro do ambiente.
            # ------------------------------------------------
            def desenhar_circulo_porta(ponto, poly):

                cx = sum(pt[0] for pt in poly) / len(poly)
                cy = sum(pt[1] for pt in poly) / len(poly)

                nx, ny = get_inside_normal(
                    vx,
                    vy,
                    ponto[0],
                    ponto[1],
                    cx,
                    cy
                )

                centro = (
                    ponto[0] + nx * raio_circulo,
                    ponto[1] + ny * raio_circulo
                )

                if ponto_em_poligono(
                    centro[0],
                    centro[1],
                    poly
                ):
                    msp.add_circle(
                        center=centro,
                        radius=raio_circulo,
                        dxfattribs={
                            'layer':
                                'PROJ_ELETRICA_DEBUG',
                            'color': 6
                        }
                    )

            # ------------------------------------------------
            # Os círculos são permitidos APENAS em P2 e P3.
            # Nunca desenhar círculo em P1 ou P4.
            # ------------------------------------------------
            if len(ambientes_adjacentes) >= 2:

                poly_a = ambientes_adjacentes[0]
                poly_b = ambientes_adjacentes[1]

                # Descobre qual ambiente está de cada lado da
                # linha P2-P3.
                cx_a = sum(
                    pt[0] for pt in poly_a
                ) / len(poly_a)

                cy_a = sum(
                    pt[1] for pt in poly_a
                ) / len(poly_a)

                nx_a, ny_a = get_inside_normal(
                    vx,
                    vy,
                    p2[0],
                    p2[1],
                    cx_a,
                    cy_a
                )

                teste_a = (
                    p2[0] + nx_a * raio_circulo,
                    p2[1] + ny_a * raio_circulo
                )

                if ponto_em_poligono(
                    teste_a[0],
                    teste_a[1],
                    poly_a
                ):
                    poly_p2 = poly_a
                    poly_p3 = poly_b
                else:
                    poly_p2 = poly_b
                    poly_p3 = poly_a

                desenhar_circulo_porta(
                    p2,
                    poly_p2
                )

                desenhar_circulo_porta(
                    p3,
                    poly_p3
                )

            elif len(ambientes_adjacentes) == 1:

                # Em abertura encostada em apenas um ambiente,
                # somente P2 recebe círculo. P1 e P4 jamais recebem.
                poly = ambientes_adjacentes[0]

                desenhar_circulo_porta(
                    p2,
                    poly
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
        # PROCESSAMENTO DOS AMBIENTES
        # ====================================================

        for polilinha in polilinhas:

            xs = [p[0] for p in polilinha]
            ys = [p[1] for p in polilinha]

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
                dict_dados.get(nome, None)
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
            # SEGMENTOS DA PAREDE
            # =================================================

            segmentos_crus = []
            comp_total = 0

            poly = list(polilinha)

            if poly[0] != poly[-1]:
                poly.append(poly[0])

            for i in range(
                len(poly) - 1
            ):

                dst = math.hypot(
                    poly[i + 1][0] - poly[i][0],
                    poly[i + 1][1] - poly[i][1]
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

            # =================================================
            # PAREDES LÓGICAS
            # =================================================

            logical_walls = []

            for pt1, pt2, dst in segmentos_crus:

                vx = (
                    pt2[0] - pt1[0]
                ) / dst

                vy = (
                    pt2[1] - pt1[1]
                ) / dst

                logical_walls.append({

                    'p1': pt1,

                    'p2': pt2,

                    'length': dst,

                    'vx': vx,

                    'vy': vy
                })

            # =================================================
            # PORTAS DO AMBIENTE
            # =================================================

            unique_portas = [

                p for p in portas_raw

                if (
                    min_x - 0.8
                    <= (
                        p['p1'][0] +
                        p['p2'][0]
                    ) / 2
                    <= max_x + 0.8

                    and

                    min_y - 0.8
                    <= (
                        p['p1'][1] +
                        p['p2'][1]
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

                            pontos_luz.append(
                                (
                                    centro_x,
                                    centro_y
                                )
                            )

                        else:

                            step = (
                                largura /
                                (qtd_ilum + 1)
                            )

                            for i in range(
                                1,
                                qtd_ilum + 1
                            ):

                                pontos_luz.append(
                                    (
                                        min_x +
                                        step * i,
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
                                comprimento /
                                (qtd_ilum + 1)
                            )

                            for i in range(
                                1,
                                qtd_ilum + 1
                            ):

                                pontos_luz.append(
                                    (
                                        centro_x,
                                        min_y +
                                        step * i
                                    )
                                )

                    for lx, ly in pontos_luz:

                        msp.add_circle(
                            center=(lx, ly),
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
                nome_atual_upper ==
                qdc_formatado
            )

            if is_ambiente_qdc and logical_walls:

                qdc_w = 0.4
                qdc_d = 0.15

                maior_parede = max(
                    logical_walls,
                    key=lambda w: w['length']
                )

                pt1 = maior_parede['p1']
                pt2 = maior_parede['p2']

                is_vertical = (
                    abs(pt1[0] - pt2[0])
                    <
                    abs(pt1[1] - pt2[1])
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

                    if d_p1 < 0.6 or d_p2 < 0.6:

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

                        mid_y = (
                            melhor_trecho[0] +
                            melhor_trecho[1]
                        ) / 2

                        mx = pt1[0]
                        my = mid_y

                    else:

                        mx = (
                            pt1[0] +
                            pt2[0]
                        ) / 2

                        my = (
                            pt1[1] +
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
                        key=lambda x: x[0]
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

                        mid_x = (
                            melhor_trecho[0] +
                            melhor_trecho[1]
                        ) / 2

                        mx = mid_x
                        my = pt1[1]

                    else:

                        mx = (
                            pt1[0] +
                            pt2[0]
                        ) / 2

                        my = (
                            pt1[1] +
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
                    mx - vx * qdc_w / 2,
                    my - vy * qdc_w / 2
                )

                p2_qdc = (
                    mx + vx * qdc_w / 2,
                    my + vy * qdc_w / 2
                )

                p3_qdc = (
                    p2_qdc[0] +
                    out_nx * qdc_d,

                    p2_qdc[1] +
                    out_ny * qdc_d
                )

                p4_qdc = (
                    p1_qdc[0] +
                    out_nx * qdc_d,

                    p1_qdc[1] +
                    out_ny * qdc_d
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
                        or
                        "forno" in eq_lower
                    ):
                        pot_tue_val = 2000

                    elif (
                        "máquina" in eq_lower
                        or
                        "lavar" in eq_lower
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

                if qtd_tue > 0 and logical_walls:

                    paredes_candidatas = sorted(
                        logical_walls,
                        key=lambda w: w['length']
                    )

                    # ---------------------------------------------
                    # PRIMEIRO TENTA PAREDES SEM PORTA
                    # ---------------------------------------------

                    paredes_sem_porta = [

                        w for w in paredes_candidatas

                        if not any(

                            point_seg_dist(

                                (
                                    p['p1'][0] +
                                    p['p2'][0]
                                ) / 2,

                                (
                                    p['p1'][1] +
                                    p['p2'][1]
                                ) / 2,

                                w['p1'],
                                w['p2']

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

                        p_alvo = paredes_finais[
                            idx_tue %
                            len(paredes_finais)
                        ]

                        pt1 = p_alvo['p1']
                        pt2 = p_alvo['p2']

                        # -----------------------------------------
                        # POSIÇÃO DESEJADA
                        #
                        # Para uma única TUE, começa no centro.
                        # Para várias TUEs, distribui ao longo da
                        # parede.
                        # -----------------------------------------

                        fator = (
                            0.5
                            if qtd_tue == 1
                            else
                            (
                                idx_tue + 1
                            ) /
                            (
                                qtd_tue + 1
                            )
                        )

                        # -----------------------------------------
                        # PROCURA UMA POSIÇÃO REALMENTE VÁLIDA
                        #
                        # Esta função garante afastamento mínimo
                        # de 50 cm dos cantos da parede.
                        # -----------------------------------------

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

                        # -----------------------------------------
                        # NORMAL PARA DENTRO DO AMBIENTE
                        # -----------------------------------------

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
                # =================================================

                total_tugs = qtd_tugs

                if total_tugs > 0 and comp_total > 0:

                    # -------------------------------------------------
                    # MARGEM MAIOR NOS CANTOS
                    # -------------------------------------------------

                    margem_inicial = 0.35

                    comprimento_util = (
                        comp_total -
                        (
                            2 *
                            margem_inicial
                        )
                    )

                    if comprimento_util > 0:

                        passo = (
                            comprimento_util /
                            total_tugs
                        )

                        inicio_offset = (
                            margem_inicial +
                            passo / 2
                        )

                    else:

                        passo = (
                            comp_total /
                            total_tugs
                        )

                        inicio_offset = (
                            passo / 2
                        )

                    tomadas_colocadas = 0

                    # -------------------------------------------------
                    # REGISTRA AS DISTÂNCIAS JÁ UTILIZADAS
                    # -------------------------------------------------

                    distancias_usadas = []

                    for i in range(total_tugs):

                        distancia_desejada = (
                            inicio_offset +
                            i * passo
                        )

                        if distancia_desejada <= 0:
                            continue

                        if distancia_desejada >= comp_total:
                            continue

                        # -------------------------------------------------
                        # PROCURA UMA POSIÇÃO REALMENTE LIVRE
                        # -------------------------------------------------

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

                        # -------------------------------------------------
                        # NÃO DEIXA DUAS TOMADAS MUITO PRÓXIMAS
                        # -------------------------------------------------

                        distancia_muito_proxima = False

                        for d_usada in distancias_usadas:

                            diferenca = abs(
                                distancia_desejada -
                                d_usada
                            )

                            if diferenca < 0.60:

                                distancia_muito_proxima = True
                                break

                        if distancia_muito_proxima:

                            # tenta outros pontos
                            alternativas = [
                                distancia_desejada - 0.75,
                                distancia_desejada + 0.75,
                                distancia_desejada - 1.00,
                                distancia_desejada + 1.00
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
                                        dist_alt -
                                        d
                                    ) < 0.60
                                    for d in distancias_usadas
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

                        # -------------------------------------------------
                        # VALIDAÇÃO FINAL
                        # -------------------------------------------------

                        if not ponto_tomada_valido(
                            px,
                            py,
                            polilinha,
                            portas_raw,
                            soleiras_raw
                        ):
                            continue

                        # -------------------------------------------------
                        # GUARDA A POSIÇÃO
                        # -------------------------------------------------

                        distancias_usadas.append(
                            distancia_desejada
                        )

                        tomadas_colocadas += 1

                        # -------------------------------------------------
                        # NORMAL PARA DENTRO DO AMBIENTE
                        # -------------------------------------------------

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
                        # DESENHA TUG
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
                        # TUG EM ÁREA MOLHADA
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
            and
            os.path.exists(tmp_in_path)
        ):

            os.remove(
                tmp_in_path
            )
