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

        p1x, p1y = p2[0], p2[1]

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
    """
    Retorna True somente quando o ponto está em uma posição segura.

    Evita:
      1. vértices/cantos do ambiente;
      2. segmento de porta;
      3. segmento de soleira.
    """

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
        max(comp_total * 0.01, 0.10),
        0.50
    )

    max_busca = min(
        comp_total * 0.20,
        2.00
    )

    deslocamento = passo_busca

    while deslocamento <= max_busca:

        distancias_teste = [
            distancia_original - deslocamento,
            distancia_original + deslocamento
        ]

        for distancia_teste in distancias_teste:

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
    local_qdc,
    config_interruptores=None
):

    tmp_in_path = ""

    try:

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
        # INTERRUPTORES NAS SOLEIRAS
        # ====================================================

        config_interruptores = config_interruptores or {}
        raio_circulo = 0.15

        def nome_ambiente_da_poligonal(poly):

            xs = [pt[0] for pt in poly]
            ys = [pt[1] for pt in poly]

            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)

            return next(
                (
                    t['nome'] for t in textos
                    if min_x - 0.5 <= t['x'] <= max_x + 0.5
                    and min_y - 0.5 <= t['y'] <= max_y + 0.5
                ),
                None
            )

        def centro_poligono(poly):

            return (
                sum(pt[0] for pt in poly) / len(poly),
                sum(pt[1] for pt in poly) / len(poly)
            )

        def desenhar_interruptor_tangente(
            ponto_soleira,
            normal,
            nome_ambiente
        ):

            cx = (
                ponto_soleira[0] +
                normal[0] * raio_circulo
            )

            cy = (
                ponto_soleira[1] +
                normal[1] * raio_circulo
            )

            msp.add_circle(
                center=(cx, cy),
                radius=raio_circulo,
                dxfattribs={
                    'layer':
                        'PROJ_ELETRICA_INTERRUPTOR'
                }
            )

            return (cx, cy)

        for item in soleiras_com_porta:

            s = item['s']
            p_porta = item['porta']

            s_a = s['p1']
            s_b = s['p2']

            sm_x = (
                s_a[0] +
                s_b[0]
            ) / 2

            sm_y = (
                s_a[1] +
                s_b[1]
            ) / 2

            ambientes_adjacentes = []

            for poly in polilinhas:

                xs = [pt[0] for pt in poly]
                ys = [pt[1] for pt in poly]

                if (
                    min(xs) - 0.5 <= sm_x <= max(xs) + 0.5
                    and
                    min(ys) - 0.5 <= sm_y <= max(ys) + 0.5
                ):

                    nome_poly = (
                        nome_ambiente_da_poligonal(
                            poly
                        )
                    )

                    if nome_poly:

                        ambientes_adjacentes.append({
                            'poly': poly,
                            'nome': nome_poly
                        })

            if not ambientes_adjacentes:
                continue

            d_a_hinge = min(
                math.hypot(
                    s_a[0] - p_porta['p1'][0],
                    s_a[1] - p_porta['p1'][1]
                ),
                math.hypot(
                    s_a[0] - p_porta['p2'][0],
                    s_a[1] - p_porta['p2'][1]
                )
            )

            d_b_hinge = min(
                math.hypot(
                    s_b[0] - p_porta['p1'][0],
                    s_b[1] - p_porta['p1'][1]
                ),
                math.hypot(
                    s_b[0] - p_porta['p2'][0],
                    s_b[1] - p_porta['p2'][1]
                )
            )

            if d_a_hinge >= d_b_hinge:

                p2 = s_a
                p3 = s_b

            else:

                p2 = s_b
                p3 = s_a

            ambientes = ambientes_adjacentes[:2]

            nomes_amb = [
                a['nome']
                for a in ambientes
            ]

            cfg_encontradas = []

            for nome in nomes_amb:

                cfg = config_interruptores.get(
                    nome,
                    {}
                )

                if (
                    isinstance(cfg, dict)
                    and
                    int(
                        cfg.get(
                            'quantidade',
                            0
                        )
                    ) > 0
                ):

                    cfg_encontradas.append(
                        (
                            nome,
                            cfg
                        )
                    )

            for nome_cfg, cfg in cfg_encontradas:

                qtd = max(
                    0,
                    min(
                        2,
                        int(
                            cfg.get(
                                'quantidade',
                                0
                            )
                        )
                    )
                )

                if qtd == 0:
                    continue

                ambiente_cfg = next(
                    (
                        a for a in ambientes
                        if a['nome'] == nome_cfg
                    ),
                    None
                )

                if ambiente_cfg is None:
                    continue

                poly_cfg = ambiente_cfg['poly']

                cx_cfg, cy_cfg = (
                    centro_poligono(
                        poly_cfg
                    )
                )

                dx = (
                    p3[0] -
                    p2[0]
                )

                dy = (
                    p3[1] -
                    p2[1]
                )

                comp = math.hypot(
                    dx,
                    dy
                )

                if comp == 0:
                    continue

                vx = dx / comp
                vy = dy / comp

                normal_cfg = get_inside_normal(
                    vx,
                    vy,
                    p2[0],
                    p2[1],
                    cx_cfg,
                    cy_cfg
                )

                pontos_interruptores = []

                if qtd == 2:

                    pontos_interruptores = [
                        p2,
                        p3
                    ]

                elif qtd == 1:

                    porta_escolhida = max(
                        1,
                        min(
                            2,
                            int(
                                cfg.get(
                                    'porta',
                                    1
                                )
                            )
                        )
                    )

                    pontos_interruptores = [
                        p2
                        if porta_escolhida == 1
                        else p3
                    ]

                for ponto_base in pontos_interruptores:

                    centro = (
                        desenhar_interruptor_tangente(
                            ponto_base,
                            normal_cfg,
                            nome_cfg
                        )
                    )

                    msp.add_text(
                        "INT",
                        dxfattribs={
                            'layer':
                                'PROJ_ELETRICA_TEXTO',
                            'height': 0.10,
                            'insert': (
                                centro[0] + 0.18,
                                centro[1] - 0.04
                            )
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
                    pt2[0] -
                    pt1[0]
                ) / dst

                vy = (
                    pt2[1] -
                    pt1[1]
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
                                (
                                    qtd_ilum + 1
                                )
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
                                (
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
                                        min_y +
                                        step * i
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

                    if (
                        cursor <
                        parede_max - 0.1
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

                    if (
                        cursor <
                        parede_max - 0.1
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
                    pts_qdc + [
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
                        key=lambda w:
                        w['length']
                    )

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

                        px = (
                            pt1[0] +
                            (
                                pt2[0] -
                                pt1[0]
                            ) * fator
                        )

                        py = (
                            pt1[1] +
                            (
                                pt2[1] -
                                pt1[1]
                            ) * fator
                        )

                        if not ponto_tomada_valido(
                            px,
                            py,
                            polilinha,
                            portas_raw,
                            soleiras_raw
                        ):

                            tentativas = [
                                0.25,
                                0.35,
                                0.65,
                                0.75
                            ]

                            encontrado = None

                            for fator_alt in tentativas:

                                tx = (
                                    pt1[0] +
                                    (
                                        pt2[0] -
                                        pt1[0]
                                    ) *
                                    fator_alt
                                )

                                ty = (
                                    pt1[1] +
                                    (
                                        pt2[1] -
                                        pt1[1]
                                    ) *
                                    fator_alt
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

                        vx = p_alvo['vx']
                        vy = p_alvo['vy']

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

                    distancias_usadas = []

                    for i in range(
                        total_tugs
                    ):

                        distancia_desejada = (
                            inicio_offset +
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

                        for d_usada in distancias_usadas:

                            diferenca = abs(
                                distancia_desejada -
                                d_usada
                            )

                            if diferenca < 0.60:

                                distancia_muito_proxima = True
                                break

                        if distancia_muito_proxima:

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
                                ) = (
                                    alternativa_encontrada
                                )

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
