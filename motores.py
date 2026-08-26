import ezdxf
import math
import tempfile
import os


# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

APPID = "PROJ_ELETRICA"

TOLERANCIA_PORTA = 0.15
RAIO_DEBUG = 0.15


# ============================================================
# 1. DIMENSIONAMENTO DAS CARGAS
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

    # --------------------------------------------------------
    # ILUMINAÇÃO
    # --------------------------------------------------------

    qtd_ilum = 1 if area <= 10 else math.ceil(area / 10)

    if area <= 6:
        carga_ilum = 100
    else:
        carga_ilum = 100 + (((area - 6) // 4) * 60)

    nome_lower = nome.lower().strip()

    nome_words = (
        nome_lower
        .replace("-", " ")
        .split()
    )

    # --------------------------------------------------------
    # IDENTIFICA AMBIENTE MOLHADO
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # IDENTIFICA CORREDOR / HALL
    # --------------------------------------------------------

    is_corredor = any(
        x in nome_lower
        for x in [
            "hall",
            "corredor",
            "circulação",
            "circulacao"
        ]
    )

    # --------------------------------------------------------
    # TUG
    # --------------------------------------------------------

    if is_umida:

        qtd_tugs = math.ceil(perimetro / 3.5)

        if qtd_tugs <= 3:
            carga_tugs = qtd_tugs * 600
        else:
            carga_tugs = (
                (3 * 600)
                +
                ((qtd_tugs - 3) * 100)
            )

        pot_tug_unit = 600

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

        carga_tugs = qtd_tugs * 100
        pot_tug_unit = 100

    else:

        qtd_tugs = math.ceil(
            perimetro / 5
        )

        carga_tugs = qtd_tugs * 100
        pot_tug_unit = 100

    # --------------------------------------------------------
    # TUE
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # RETORNO
    # --------------------------------------------------------

    return {

        "Qtd Ilum.": qtd_ilum,

        "Pot. Unit. Ilum (VA)": (
            round(
                carga_ilum / qtd_ilum
            )
            if qtd_ilum > 0
            else 0
        ),

        "Carga Ilum. (VA)": carga_ilum,

        "TUGs (Qtd)": qtd_tugs,

        "Pot. Unit. TUG (VA)": pot_tug_unit,

        "Carga TUGs (VA)": carga_tugs,

        "Equipamento TUE": tue_nome,

        "Qtd TUE": qtd_tue,

        "Pot. Unit. TUE (VA)": (
            round(
                carga_tue / max(
                    1,
                    qtd_tue
                )
            )
        ),

        "Carga TUE (VA)": carga_tue
    }


# ============================================================
# 2. PONTO DENTRO DO POLÍGONO
# ============================================================

def ponto_em_poligono(x, y, polilinha):

    if not polilinha:
        return False

    n = len(polilinha)

    dentro = False

    p1x, p1y = polilinha[0]

    for i in range(n + 1):

        p2x, p2y = polilinha[i % n]

        if (
            y > min(p1y, p2y)
            and
            y <= max(p1y, p2y)
            and
            x <= max(p1x, p2x)
        ):

            if p1y != p2y:

                xinters = (
                    (y - p1y)
                    *
                    (p2x - p1x)
                    /
                    (p2y - p1y)
                    +
                    p1x
                )

            else:

                xinters = x

            if (
                p1x == p2x
                or
                x <= xinters
            ):
                dentro = not dentro

        p1x, p1y = p2x, p2y

    return dentro


# ============================================================
# 3. LEITURA ROBUSTA DOS PONTOS DE UMA POLILINE
# ============================================================

def obter_pontos_polilinha(entity):

    pontos = []

    try:

        tipo = entity.dxftype()

        if tipo == "LWPOLYLINE":

            for p in entity.get_points(
                format="xy"
            ):
                pontos.append(
                    (
                        float(p[0]),
                        float(p[1])
                    )
                )

        elif tipo == "POLYLINE":

            for vertex in entity.vertices:

                pontos.append(
                    (
                        float(
                            vertex.dxf.location.x
                        ),
                        float(
                            vertex.dxf.location.y
                        )
                    )
                )

    except Exception:

        return []

    return pontos


# ============================================================
# 4. PONTO NO PERÍMETRO
# ============================================================

def get_ponto_perimetro(
    d,
    segs
):

    acumulado = 0

    if not segs:
        return (
            0,
            0,
            1,
            0
        )

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
                    1,
                    0
                )

            ratio = (
                d - acumulado
            ) / dst

            return (

                pt1[0]
                +
                (
                    pt2[0] - pt1[0]
                )
                *
                ratio,

                pt1[1]
                +
                (
                    pt2[1] - pt1[1]
                )
                *
                ratio,

                (
                    pt2[0] - pt1[0]
                ) / dst,

                (
                    pt2[1] - pt1[1]
                ) / dst
            )

        acumulado += dst

    pt1, pt2, dst = segs[-1]

    if dst == 0:
        return (
            pt2[0],
            pt2[1],
            1,
            0
        )

    return (
        pt2[0],
        pt2[1],
        (
            pt2[0] - pt1[0]
        ) / dst,
        (
            pt2[1] - pt1[1]
        ) / dst
    )


# ============================================================
# 5. DISTÂNCIA DE PONTO PARA SEGMENTO
# ============================================================

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

    return math.hypot(

        px
        -
        (
            pt1[0]
            +
            t *
            (
                pt2[0] - pt1[0]
            )
        ),

        py
        -
        (
            pt1[1]
            +
            t *
            (
                pt2[1] - pt1[1]
            )
        )
    )


# ============================================================
# 6. NORMAL INTERNA DA PAREDE
# ============================================================

def get_inside_normal(
    vx,
    vy,
    start_x,
    start_y,
    cx,
    cy
):

    n1x = -vy
    n1y = vx

    n2x = vy
    n2y = -vx

    d1 = math.hypot(
        cx
        -
        (
            start_x + n1x
        ),
        cy
        -
        (
            start_y + n1y
        )
    )

    d2 = math.hypot(
        cx
        -
        (
            start_x + n2x
        ),
        cy
        -
        (
            start_y + n2y
        )
    )

    if d1 < d2:
        return (
            n1x,
            n1y
        )

    return (
        n2x,
        n2y
    )


# ============================================================
# 7. LEITURA DAS CAMADAS OBRIGATÓRIAS
# ============================================================

def validar_camadas_entrada(doc):

    msp = doc.modelspace()

    contagem = {

        "IA_AMBIENTES": 0,
        "IA_TEXTOS": 0,
        "IA_PORTAS": 0,
        "IA_SOLEIRAS": 0
    }

    for entity in msp:

        if not hasattr(
            entity.dxf,
            "layer"
        ):
            continue

        layer = str(
            entity.dxf.layer
        ).upper().strip()

        if layer in contagem:
            contagem[layer] += 1

    vazias = [
        cam
        for cam, qtd in contagem.items()
        if qtd == 0
    ]

    if vazias:

        raise ValueError(

            "❌ Erro de Validação do DXF:\n\n"

            "As seguintes camadas obrigatórias "
            "estão vazias ou ausentes:\n\n"

            +
            "\n".join(
                f"• {cam}"
                for cam in vazias
            )

            +
            "\n\n"
            "Certifique-se de desenhar os elementos "
            "nos respectivos layers."
        )

    return contagem


# ============================================================
# 8. CRIAÇÃO DAS CAMADAS DO PROJETO
# ============================================================

def criar_camadas_projeto(doc):

    camadas = {

        "PROJ_ELETRICA_LUZ": 2,

        "PROJ_ELETRICA_QDC": 1,

        "PROJ_ELETRICA_TEXTO": 2,

        "PROJ_ELETRICA_TOMADA": 4,

        "PROJ_ELETRICA_INTERRUPTOR": 5,

        "PROJ_ELETRICA_DEBUG": 6
    }

    for nome_layer, cor in camadas.items():

        if nome_layer not in doc.layers:

            doc.layers.add(
                name=nome_layer,
                color=cor
            )

        else:

            doc.layers.get(
                nome_layer
            ).color = cor


# ============================================================
# 9. REGISTRA APPID PARA XDATA
# ============================================================

def registrar_appid(doc):

    if APPID not in doc.appids:

        doc.appids.add(
            APPID
        )


# ============================================================
# 10. MARCA ENTIDADE COM XDATA
# ============================================================

def marcar_entidade(
    entity,
    tipo,
    ambiente,
    indice,
    potencia=0
):

    entity.set_xdata(
        APPID,
        [

            (1000, str(tipo)),

            (1000, str(ambiente)),

            (1071, int(indice)),

            (1071, int(potencia))
        ]
    )


# ============================================================
# 11. CRIA TUG/TUE
# ============================================================

def adicionar_tomada(
    msp,
    tipo,
    ambiente,
    indice,
    px,
    py,
    seg_vx,
    seg_vy,
    nx,
    ny,
    potencia,
    is_molhado=False,
    is_chuveiro_ou_ac=False
):

    # --------------------------------------------------------
    # GEOMETRIA DO SÍMBOLO
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # SÍMBOLO PRINCIPAL
    # --------------------------------------------------------

    simbolo = msp.add_lwpolyline(

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

    # --------------------------------------------------------
    # XDATA
    # --------------------------------------------------------

    marcar_entidade(

        simbolo,

        tipo=tipo,

        ambiente=ambiente,

        indice=indice,

        potencia=potencia
    )

    # --------------------------------------------------------
    # PREENCHIMENTO TUE
    # --------------------------------------------------------

    if (
        tipo == "TUE"
        and
        is_chuveiro_ou_ac
    ):

        solid = msp.add_solid(

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

        marcar_entidade(

            solid,

            tipo="TUE_SOLID",

            ambiente=ambiente,

            indice=indice,

            potencia=potencia
        )

    # --------------------------------------------------------
    # PREENCHIMENTO TUG EM AMBIENTE MOLHADO
    # --------------------------------------------------------

    elif (
        tipo == "TUG"
        and
        is_molhado
    ):

        ponto_medio_base = (
            px,
            py
        )

        solid = msp.add_solid(

            [
                ponto_b1,
                ponto_medio_base,
                ponto_pt
            ],

            dxfattribs={
                "layer":
                    "PROJ_ELETRICA_TOMADA"
            }
        )

        marcar_entidade(

            solid,

            tipo="TUG_SOLID",

            ambiente=ambiente,

            indice=indice,

            potencia=potencia
        )

    # --------------------------------------------------------
    # TEXTO DA POTÊNCIA
    # --------------------------------------------------------

    texto = msp.add_text(

        f"{potencia}VA",

        dxfattribs={

            "layer":
                "PROJ_ELETRICA_TEXTO",

            "height":
                0.12,

            "color":
                2,

            "insert": (

                px
                +
                nx * 0.35,

                py
                +
                ny * 0.35
            )
        }
    )

    marcar_entidade(

        texto,

        tipo=f"{tipo}_TEXTO",

        ambiente=ambiente,

        indice=indice,

        potencia=potencia
    )

    return simbolo


# ============================================================
# 12. IDENTIFICA AMBIENTES DO DXF
# ============================================================

def ler_ambientes(
    msp
):

    polilinhas = []
    textos = []

    # --------------------------------------------------------
    # PRIMEIRO: POLÍGONOS
    # --------------------------------------------------------

    for entity in msp:

        tipo = entity.dxftype()

        if not hasattr(
            entity.dxf,
            "layer"
        ):
            continue

        layer = str(
            entity.dxf.layer
        ).upper().strip()

        if (
            tipo in [
                "LWPOLYLINE",
                "POLYLINE"
            ]
            and
            layer == "IA_AMBIENTES"
        ):

            pontos = obter_pontos_polilinha(
                entity
            )

            if pontos:

                polilinhas.append(
                    pontos
                )

    # --------------------------------------------------------
    # SEGUNDO: TEXTOS
    # --------------------------------------------------------

    for entity in msp:

        tipo = entity.dxftype()

        if tipo not in [
            "TEXT",
            "MTEXT"
        ]:
            continue

        if not hasattr(
            entity.dxf,
            "layer"
        ):
            continue

        layer = str(
            entity.dxf.layer
        ).upper().strip()

        if layer != "IA_TEXTOS":
            continue

        try:

            if tipo == "MTEXT":

                texto_str = (
                    entity.text
                    .strip()
                )

            else:

                texto_str = (
                    entity.dxf.text
                    .strip()
                )

            if not texto_str:
                continue

            textos.append({

                "nome":
                    texto_str,

                "x":
                    float(
                        entity.dxf.insert.x
                    ),

                "y":
                    float(
                        entity.dxf.insert.y
                    )
            })

        except Exception:
            continue

    # --------------------------------------------------------
    # ASSOCIA TEXTO AO POLÍGONO
    # --------------------------------------------------------

    ambientes = []

    contador_nomes = {}

    for polilinha in polilinhas:

        xs = [
            p[0]
            for p in polilinha
        ]

        ys = [
            p[1]
            for p in polilinha
        ]

        if not xs or not ys:
            continue

        min_x = min(xs)
        max_x = max(xs)

        min_y = min(ys)
        max_y = max(ys)

        area_bbox = (
            max_x - min_x
        ) * (
            max_y - min_y
        )

        if area_bbox < 0.5:
            continue

        # ----------------------------------------------------
        # PROCURA TEXTO REALMENTE DENTRO DO POLÍGONO
        # ----------------------------------------------------

        candidatos = [

            t
            for t in textos

            if ponto_em_poligono(
                t["x"],
                t["y"],
                polilinha
            )
        ]

        if not candidatos:

            # Fallback para desenho com pequenas
            # diferenças de coordenada
            candidatos = [

                t
                for t in textos

                if (
                    min_x - 0.5
                    <=
                    t["x"]
                    <=
                    max_x + 0.5
                )
                and
                (
                    min_y - 0.5
                    <=
                    t["y"]
                    <=
                    max_y + 0.5
                )
            ]

        if not candidatos:
            continue

        nome_original = (
            candidatos[0]["nome"]
            .strip()
        )

        contador_nomes.setdefault(
            nome_original,
            0
        )

        contador_nomes[
            nome_original
        ] += 1

        numero = contador_nomes[
            nome_original
        ]

        if numero == 1:

            nome = nome_original

        else:

            nome = (
                f"{nome_original} "
                f"{numero}"
            )

        largura = (
            max_x - min_x
        )

        comprimento = (
            max_y - min_y
        )

        perimetro = (
            largura * 2
            +
            comprimento * 2
        )

        ambientes.append({

            "nome":
                nome,

            "nome_original":
                nome_original,

            "poligono":
                polilinha,

            "area":
                area_bbox,

            "perimetro":
                perimetro,

            "min_x":
                min_x,

            "max_x":
                max_x,

            "min_y":
                min_y,

            "max_y":
                max_y,

            "centro_x":
                (
                    min_x + max_x
                ) / 2,

            "centro_y":
                (
                    min_y + max_y
                ) / 2
        })

    return ambientes


# ============================================================
# 13. LÊ PORTAS E SOLEIRAS
# ============================================================

def ler_portas_soleiras(msp):

    portas_raw = []
    soleiras_raw = []

    for entity in msp:

        tipo = entity.dxftype()

        if not hasattr(
            entity.dxf,
            "layer"
        ):
            continue

        layer = str(
            entity.dxf.layer
        ).upper().strip()

        # ----------------------------------------------------
        # PORTAS
        # ----------------------------------------------------

        if layer == "IA_PORTAS":

            if tipo == "LINE":

                portas_raw.append({

                    "p1": (
                        float(
                            entity.dxf.start.x
                        ),
                        float(
                            entity.dxf.start.y
                        )
                    ),

                    "p2": (
                        float(
                            entity.dxf.end.x
                        ),
                        float(
                            entity.dxf.end.y
                        )
                    )
                })

            elif tipo in [
                "LWPOLYLINE",
                "POLYLINE"
            ]:

                pts = obter_pontos_polilinha(
                    entity
                )

                if len(pts) >= 2:

                    portas_raw.append({

                        "p1":
                            pts[0],

                        "p2":
                            pts[-1]
                    })

        # ----------------------------------------------------
        # SOLEIRAS
        # ----------------------------------------------------

        elif layer == "IA_SOLEIRAS":

            if tipo == "LINE":

                soleiras_raw.append({

                    "p1": (
                        float(
                            entity.dxf.start.x
                        ),
                        float(
                            entity.dxf.start.y
                        )
                    ),

                    "p2": (
                        float(
                            entity.dxf.end.x
                        ),
                        float(
                            entity.dxf.end.y
                        )
                    )
                })

            elif tipo in [
                "LWPOLYLINE",
                "POLYLINE"
            ]:

                pts = obter_pontos_polilinha(
                    entity
                )

                if len(pts) >= 2:

                    soleiras_raw.append({

                        "p1":
                            pts[0],

                        "p2":
                            pts[-1]
                    })

    return (
        portas_raw,
        soleiras_raw
    )


# ============================================================
# 14. PROCESSA O DXF PARA A TABELA
# ============================================================

def processar_dxf(
    caminho_arquivo
):

    doc = ezdxf.readfile(
        caminho_arquivo
    )

    msp = doc.modelspace()

    validar_camadas_entrada(
        doc
    )

    ambientes = ler_ambientes(
        msp
    )

    resultados = []

    for ambiente in ambientes:

        nome = ambiente[
            "nome"
        ]

        area = ambiente[
            "area"
        ]

        perimetro = ambiente[
            "perimetro"
        ]

        cargas = dimensionar_cargas(
            nome,
            area,
            perimetro
        )

        resultados.append({

            "Ambiente":
                nome,

            "Centro_X":
                ambiente[
                    "centro_x"
                ],

            "Centro_Y":
                ambiente[
                    "centro_y"
                ],

            "Área (m²)":
                area,

            "Perímetro (m)":
                perimetro,

            "Qtd Ilum.":
                int(
                    cargas[
                        "Qtd Ilum."
                    ]
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
# 15. ENCONTRA DADOS DA TABELA
# ============================================================

def obter_dados_ambiente(
    dict_dados,
    nome
):

    # Primeiro tenta o nome exato
    if nome in dict_dados:

        return dict_dados[
            nome
        ]

    # Depois tenta comparação sem espaços
    nome_normalizado = (
        nome.strip().upper()
    )

    for chave, valor in dict_dados.items():

        if (
            str(chave)
            .strip()
            .upper()
            ==
            nome_normalizado
        ):

            return valor

    # Por último tenta nome original
    # antes do sufixo 2, 3...
    partes = nome.rsplit(
        " ",
        1
    )

    if (
        len(partes) == 2
        and
        partes[1].isdigit()
    ):

        nome_base = partes[0]

        if nome_base in dict_dados:

            return dict_dados[
                nome_base
            ]

    return None


# ============================================================
# 16. IDENTIFICA SE PONTO ESTÁ PRÓXIMO DE PORTA
# ============================================================

def ponto_proximo_de_porta(
    px,
    py,
    portas,
    tolerancia=0.35
):

    for p in portas:

        pmx = (
            p["p1"][0]
            +
            p["p2"][0]
        ) / 2

        pmy = (
            p["p1"][1]
            +
            p["p2"][1]
        ) / 2

        if math.hypot(
            px - pmx,
            py - pmy
        ) < tolerancia:

            return True

    return False


# ============================================================
# 17. EXTRAI DADOS XDATA
# ============================================================

def obter_xdata_tomada(
    entity
):

    if not entity.has_xdata(
        APPID
    ):
        return None

    try:

        tags = entity.get_xdata(
            APPID
        )

    except Exception:

        return None

    valores_string = []

    valores_int = []

    for tag in tags:

        if tag.code == 1000:

            valores_string.append(
                str(tag.value)
            )

        elif tag.code == 1071:

            valores_int.append(
                int(tag.value)
            )

    if len(valores_string) < 2:

        return None

    tipo = valores_string[0]

    ambiente = valores_string[1]

    indice = (
        valores_int[0]
        if len(valores_int) >= 1
        else 0
    )

    potencia = (
        valores_int[1]
        if len(valores_int) >= 2
        else 0
    )

    return {

        "tipo":
            tipo,

        "ambiente":
            ambiente,

        "indice":
            indice,

        "potencia":
            potencia
    }


# ============================================================
# 18. VALIDA QUANTITATIVOS DO CAD
# ============================================================

def validar_quantitativos(
    doc,
    dados_editados
):

    msp = doc.modelspace()

    # --------------------------------------------------------
    # ESPERADO PELA TABELA
    # --------------------------------------------------------

    esperado = {}

    for row in dados_editados:

        ambiente = str(
            row.get(
                "Ambiente",
                ""
            )
        ).strip()

        if not ambiente:
            continue

        esperado[
            ambiente
        ] = {

            "TUG":
                int(
                    row.get(
                        "TUGs (Qtd)",
                        0
                    )
                ),

            "TUE":
                int(
                    row.get(
                        "Qtd TUE",
                        0
                    )
                )
        }

    # --------------------------------------------------------
    # ENCONTRADO NO CAD
    # --------------------------------------------------------

    encontrado = {}

    for entity in msp:

        dados = obter_xdata_tomada(
            entity
        )

        if dados is None:
            continue

        tipo = dados[
            "tipo"
        ]

        # Somente símbolos principais
        if tipo not in [
            "TUG",
            "TUE"
        ]:
            continue

        ambiente = dados[
            "ambiente"
        ]

        if ambiente not in encontrado:

            encontrado[
                ambiente
            ] = {

                "TUG": 0,
                "TUE": 0
            }

        encontrado[
            ambiente
        ][tipo] += 1

    # --------------------------------------------------------
    # COMPARAÇÃO
    # --------------------------------------------------------

    erros = []

    linhas_relatorio = []

    total_esperado_tug = 0
    total_encontrado_tug = 0

    total_esperado_tue = 0
    total_encontrado_tue = 0

    todos_ambientes = sorted(
        set(
            esperado.keys()
        )
        |
        set(
            encontrado.keys()
        )
    )

    for ambiente in todos_ambientes:

        exp = esperado.get(

            ambiente,

            {
                "TUG": 0,
                "TUE": 0
            }
        )

        enc = encontrado.get(

            ambiente,

            {
                "TUG": 0,
                "TUE": 0
            }
        )

        total_esperado_tug += exp[
            "TUG"
        ]

        total_encontrado_tug += enc[
            "TUG"
        ]

        total_esperado_tue += exp[
            "TUE"
        ]

        total_encontrado_tue += enc[
            "TUE"
        ]

        status_tug = (
            "OK"
            if exp["TUG"] == enc["TUG"]
            else "ERRO"
        )

        status_tue = (
            "OK"
            if exp["TUE"] == enc["TUE"]
            else "ERRO"
        )

        linhas_relatorio.append(

            f"{ambiente}: "
            f"TUG {enc['TUG']}/{exp['TUG']} "
            f"[{status_tug}] | "
            f"TUE {enc['TUE']}/{exp['TUE']} "
            f"[{status_tue}]"
        )

        if exp["TUG"] != enc["TUG"]:

            erros.append(

                f"{ambiente}: "
                f"TUG esperadas = {exp['TUG']}, "
                f"encontradas = {enc['TUG']}"
            )

        if exp["TUE"] != enc["TUE"]:

            erros.append(

                f"{ambiente}: "
                f"TUE esperadas = {exp['TUE']}, "
                f"encontradas = {enc['TUE']}"
            )

    # --------------------------------------------------------
    # VALIDA TOTAL
    # --------------------------------------------------------

    if (
        total_esperado_tug
        !=
        total_encontrado_tug
    ):

        erros.append(

            "TOTAL TUG: "
            f"esperadas = {total_esperado_tug}, "
            f"encontradas = {total_encontrado_tug}"
        )

    if (
        total_esperado_tue
        !=
        total_encontrado_tue
    ):

        erros.append(

            "TOTAL TUE: "
            f"esperadas = {total_esperado_tue}, "
            f"encontradas = {total_encontrado_tue}"
        )

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    relatorio = (
        "\n"
        "================================================\n"
        "VALIDAÇÃO DO QUANTITATIVO ELÉTRICO\n"
        "================================================\n\n"
        +
        "\n".join(
            linhas_relatorio
        )
        +
        "\n\n"
        "TOTAL TUG: "
        f"{total_encontrado_tug}/"
        f"{total_esperado_tug}\n"
        "TOTAL TUE: "
        f"{total_encontrado_tue}/"
        f"{total_esperado_tue}\n"
        "================================================\n"
    )

    if erros:

        raise ValueError(

            "❌ O PROJETO NÃO FOI VALIDADO.\n\n"

            +
            "\n".join(
                erros
            )

            +
            "\n\n"
            +
            relatorio
        )

    return {

        "ok": True,

        "total_tug":
            total_encontrado_tug,

        "total_tue":
            total_encontrado_tue,

        "relatorio":
            relatorio
    }


# ============================================================
# 19. GERAÇÃO PRINCIPAL DO CAD
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

        # ----------------------------------------------------
        # ABRE DXF
        # ----------------------------------------------------

        doc = ezdxf.readfile(
            tmp_in_path
        )

        msp = doc.modelspace()

        # ----------------------------------------------------
        # VALIDA ENTRADA
        # ----------------------------------------------------

        validar_camadas_entrada(
            doc
        )

        # ----------------------------------------------------
        # REGISTRA XDATA
        # ----------------------------------------------------

        registrar_appid(
            doc
        )

        # ----------------------------------------------------
        # CRIA CAMADAS
        # ----------------------------------------------------

        criar_camadas_projeto(
            doc
        )

        # ----------------------------------------------------
        # LÊ AMBIENTES
        # ----------------------------------------------------

        ambientes = ler_ambientes(
            msp
        )

        # ----------------------------------------------------
        # LÊ PORTAS E SOLEIRAS
        # ----------------------------------------------------

        portas_raw, soleiras_raw = (
            ler_portas_soleiras(
                msp
            )
        )

        # ----------------------------------------------------
        # IGNORA SOLEIRAS SEM PORTA
        # ----------------------------------------------------

        soleiras_com_porta = []

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

                pm_porta_x = (
                    p["p1"][0]
                    +
                    p["p2"][0]
                ) / 2

                pm_porta_y = (
                    p["p1"][1]
                    +
                    p["p2"][1]
                ) / 2

                d3 = point_seg_dist(

                    pm_porta_x,
                    pm_porta_y,

                    s_p1,
                    s_p2
                )

                if (
                    d1 < TOLERANCIA_PORTA
                    or
                    d2 < TOLERANCIA_PORTA
                    or
                    d3 < TOLERANCIA_PORTA
                ):

                    porta_encostada = p

                    break

            if (
                porta_encostada
                is not None
            ):

                soleiras_com_porta.append({

                    "s":
                        s,

                    "porta":
                        porta_encostada
                })

        # ----------------------------------------------------
        # DESENHA DEBUG DAS SOLEIRAS/PORTAS
        # ----------------------------------------------------

        for item in soleiras_com_porta:

            s = item["s"]
            p_porta = item["porta"]

            s_pA = s["p1"]
            s_pB = s["p2"]

            sm_x = (
                s_pA[0]
                +
                s_pB[0]
            ) / 2

            sm_y = (
                s_pA[1]
                +
                s_pB[1]
            ) / 2

            d_p1_sA = math.hypot(

                p_porta["p1"][0]
                -
                s_pA[0],

                p_porta["p1"][1]
                -
                s_pA[1]
            )

            d_p1_sB = math.hypot(

                p_porta["p1"][0]
                -
                s_pB[0],

                p_porta["p1"][1]
                -
                s_pB[1]
            )

            dobradica_pt = (

                p_porta["p1"]
                if d_p1_sA < d_p1_sB
                else
                p_porta["p2"]
            )

            d_sA_dob = math.hypot(

                s_pA[0]
                -
                dobradica_pt[0],

                s_pA[1]
                -
                dobradica_pt[1]
            )

            d_sB_dob = math.hypot(

                s_pB[0]
                -
                dobradica_pt[0],

                s_pB[1]
                -
                dobradica_pt[1]
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

            for ambiente in ambientes:

                poly = ambiente[
                    "poligono"
                ]

                if (
                    ambiente["min_x"]
                    - 0.5
                    <=
                    sm_x
                    <=
                    ambiente["max_x"]
                    + 0.5
                ) and (
                    ambiente["min_y"]
                    - 0.5
                    <=
                    sm_y
                    <=
                    ambiente["max_y"]
                    + 0.5
                ):

                    ambientes_adjacentes.append(
                        poly
                    )

            # ------------------------------------------------
            # DOIS AMBIENTES
            # ------------------------------------------------

            if len(
                ambientes_adjacentes
            ) >= 2:

                poly_a = (
                    ambientes_adjacentes[0]
                )

                poly_b = (
                    ambientes_adjacentes[1]
                )

                cx_a = sum(
                    pt[0]
                    for pt in poly_a
                ) / len(poly_a)

                cy_a = sum(
                    pt[1]
                    for pt in poly_a
                ) / len(poly_a)

                nx_1, ny_1 = (
                    get_inside_normal(

                        vx,
                        vy,

                        p1[0],
                        p1[1],

                        cx_a,
                        cy_a
                    )
                )

                c_test_p2 = (

                    p1[0]
                    +
                    nx_1 * RAIO_DEBUG,

                    p1[1]
                    +
                    ny_1 * RAIO_DEBUG
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

                cx_p2 = sum(
                    pt[0]
                    for pt in target_poly_p2
                ) / len(
                    target_poly_p2
                )

                cy_p2 = sum(
                    pt[1]
                    for pt in target_poly_p2
                ) / len(
                    target_poly_p2
                )

                nx_p2, ny_p2 = (
                    get_inside_normal(

                        vx,
                        vy,

                        p1[0],
                        p1[1],

                        cx_p2,
                        cy_p2
                    )
                )

                center_p2 = (

                    p1[0]
                    +
                    nx_p2 * RAIO_DEBUG,

                    p1[1]
                    +
                    ny_p2 * RAIO_DEBUG
                )

                cx_p3 = sum(
                    pt[0]
                    for pt in target_poly_p3
                ) / len(
                    target_poly_p3
                )

                cy_p3 = sum(
                    pt[1]
                    for pt in target_poly_p3
                ) / len(
                    target_poly_p3
                )

                nx_p3, ny_p3 = (
                    get_inside_normal(

                        vx,
                        vy,

                        p4[0],
                        p4[1],

                        cx_p3,
                        cy_p3
                    )
                )

                center_p3 = (

                    p4[0]
                    +
                    nx_p3 * RAIO_DEBUG,

                    p4[1]
                    +
                    ny_p3 * RAIO_DEBUG
                )

                if ponto_em_poligono(

                    center_p2[0],
                    center_p2[1],
                    target_poly_p2
                ):

                    msp.add_circle(

                        center=center_p2,

                        radius=RAIO_DEBUG,

                        dxfattribs={
                            "layer":
                                "PROJ_ELETRICA_DEBUG",
                            "color":
                                6
                        }
                    )

                if ponto_em_poligono(

                    center_p3[0],
                    center_p3[1],
                    target_poly_p3
                ):

                    msp.add_circle(

                        center=center_p3,

                        radius=RAIO_DEBUG,

                        dxfattribs={
                            "layer":
                                "PROJ_ELETRICA_DEBUG",
                            "color":
                                6
                        }
                    )

            # ------------------------------------------------
            # UM AMBIENTE
            # ------------------------------------------------

            elif len(
                ambientes_adjacentes
            ) == 1:

                poly = (
                    ambientes_adjacentes[0]
                )

                cx = sum(
                    pt[0]
                    for pt in poly
                ) / len(poly)

                cy = sum(
                    pt[1]
                    for pt in poly
                ) / len(poly)

                nx, ny = (
                    get_inside_normal(

                        vx,
                        vy,

                        p1[0],
                        p1[1],

                        cx,
                        cy
                    )
                )

                center_p2 = (

                    p1[0]
                    +
                    nx * RAIO_DEBUG,

                    p1[1]
                    +
                    ny * RAIO_DEBUG
                )

                if ponto_em_poligono(

                    center_p2[0],
                    center_p2[1],
                    poly
                ):

                    msp.add_circle(

                        center=center_p2,

                        radius=RAIO_DEBUG,

                        dxfattribs={
                            "layer":
                                "PROJ_ELETRICA_DEBUG",
                            "color":
                                6
                        }
                    )

        # ====================================================
        # DADOS EDITADOS DA TABELA
        # ====================================================

        dict_dados = {

            str(row["Ambiente"])
            .strip():
                row

            for row in dados_editados
        }

        # ====================================================
        # PROCESSA CADA AMBIENTE
        # ====================================================

        for ambiente in ambientes:

            nome = ambiente[
                "nome"
            ]

            polilinha = ambiente[
                "poligono"
            ]

            min_x = ambiente[
                "min_x"
            ]

            max_x = ambiente[
                "max_x"
            ]

            min_y = ambiente[
                "min_y"
            ]

            max_y = ambiente[
                "max_y"
            ]

            centro_x = ambiente[
                "centro_x"
            ]

            centro_y = ambiente[
                "centro_y"
            ]

            largura = (
                max_x - min_x
            )

            comprimento = (
                max_y - min_y
            )

            # ------------------------------------------------
            # BUSCA DADOS DA TABELA
            # ------------------------------------------------

            row_data = obter_dados_ambiente(

                dict_dados,

                nome
            )

            if row_data is None:

                raise ValueError(

                    "❌ Ambiente encontrado no DXF "
                    "mas não encontrado na tabela:\n\n"
                    f"'{nome}'\n\n"
                    "Verifique o nome do ambiente."
                )

            # ------------------------------------------------
            # MONTA PAREDES
            # ------------------------------------------------

            segmentos_crus = []

            comp_total = 0

            poly_fechado = (
                list(polilinha)
                +
                [polilinha[0]]
            )

            for i in range(
                len(poly_fechado) - 1
            ):

                pt1 = (
                    poly_fechado[i]
                )

                pt2 = (
                    poly_fechado[i + 1]
                )

                dst = math.hypot(

                    pt2[0] - pt1[0],

                    pt2[1] - pt1[1]
                )

                if dst > 0.1:

                    segmentos_crus.append(
                        (
                            pt1,
                            pt2,
                            dst
                        )
                    )

                    comp_total += dst

            if not segmentos_crus:
                continue

            logical_walls = []

            for pt1, pt2, dst in segmentos_crus:

                vx = (
                    pt2[0] - pt1[0]
                ) / dst

                vy = (
                    pt2[1] - pt1[1]
                ) / dst

                logical_walls.append({

                    "p1":
                        pt1,

                    "p2":
                        pt2,

                    "length":
                        dst,

                    "vx":
                        vx,

                    "vy":
                        vy
                })

            # ------------------------------------------------
            # PORTAS DO AMBIENTE
            # ------------------------------------------------

            unique_portas = [

                p

                for p in portas_raw

                if (
                    min_x - 0.8
                    <=
                    (
                        p["p1"][0]
                        +
                        p["p2"][0]
                    ) / 2
                    <=
                    max_x + 0.8
                )
                and
                (
                    min_y - 0.8
                    <=
                    (
                        p["p1"][1]
                        +
                        p["p2"][1]
                    ) / 2
                    <=
                    max_y + 0.8
                )
            ]

            # =================================================
            # ILUMINAÇÃO
            # =================================================

            qtd_ilum = int(
                row_data.get(
                    "Qtd Ilum.",
                    0
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
                            /
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
                                    min_x
                                    +
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
                            comprimento
                            /
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

                                    min_y
                                    +
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
                            "layer":
                                "PROJ_ELETRICA_LUZ"
                        }
                    )

                    msp.add_text(

                        f"{pot_ilum_unit}VA",

                        dxfattribs={

                            "layer":
                                "PROJ_ELETRICA_TEXTO",

                            "height":
                                0.15,

                            "insert": (

                                lx + 0.3,

                                ly - 0.07
                            )
                        }
                    )

                    msp.add_text(

                        "a",

                        dxfattribs={

                            "layer":
                                "PROJ_ELETRICA_TEXTO",

                            "height":
                                0.15,

                            "color":
                                2,

                            "insert": (

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
                nome
                .strip()
                .upper()
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
                        w["length"]
                )

                pt1 = maior_parede[
                    "p1"
                ]

                pt2 = maior_parede[
                    "p2"
                ]

                is_vertical = (

                    abs(
                        pt1[0]
                        -
                        pt2[0]
                    )
                    <
                    abs(
                        pt1[1]
                        -
                        pt2[1]
                    )
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

                    if (
                        d_p1 < 0.6
                        or
                        d_p2 < 0.6
                    ):

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

                cortes_portas.sort(
                    key=lambda x: x[0]
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

                    trechos_livres = []

                    cursor = parede_min

                    for c_inf, c_sup in cortes_portas:

                        if c_inf > (
                            cursor + 0.1
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

                    if cursor < (
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

                    trechos_livres = []

                    cursor = parede_min

                    for c_inf, c_sup in cortes_portas:

                        if c_inf > (
                            cursor + 0.1
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

                    if cursor < (
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

                vx = maior_parede[
                    "vx"
                ]

                vy = maior_parede[
                    "vy"
                ]

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
                    [pts_qdc[0]],

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

            # =================================================
            # TUG / TUE
            # =================================================

            qtd_tugs = int(
                row_data.get(
                    "TUGs (Qtd)",
                    0
                )
            )

            pot_tug_val = int(
                row_data.get(
                    "Pot. Unit. TUG (VA)",
                    100
                )
            )

            qtd_tue = int(
                row_data.get(
                    "Qtd TUE",
                    0
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
                    "Pot. Unit. TUE (VA)",
                    0
                )
            )

            # ------------------------------------------------
            # CORREÇÃO DE POTÊNCIA TUE
            # ------------------------------------------------

            if pot_tue_val == 0:

                eq_lower = (
                    eq_tue_nome
                    .lower()
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
                eq_tue_nome
                .lower()
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
                nome
                .lower()
                .strip()
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
            # =================================================

            if (
                qtd_tue > 0
                and
                logical_walls
            ):

                # ---------------------------------------------
                # PRIORIZA PAREDES SEM PORTA
                # ---------------------------------------------

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

                # ---------------------------------------------
                # GERA EXATAMENTE qtd_tue
                # ---------------------------------------------

                for idx_tue in range(
                    qtd_tue
                ):

                    p_alvo = (

                        paredes_finais[
                            idx_tue
                            %
                            len(paredes_finais)
                        ]
                    )

                    pt1 = p_alvo[
                        "p1"
                    ]

                    pt2 = p_alvo[
                        "p2"
                    ]

                    if qtd_tue == 1:

                        fator = 0.5

                    else:

                        fator = (
                            idx_tue + 1
                        ) / (
                            qtd_tue + 1
                        )

                    px = (

                        pt1[0]
                        +
                        (
                            pt2[0]
                            -
                            pt1[0]
                        )
                        *
                        fator
                    )

                    py = (

                        pt1[1]
                        +
                        (
                            pt2[1]
                            -
                            pt1[1]
                        )
                        *
                        fator
                    )

                    vx = p_alvo[
                        "vx"
                    ]

                    vy = p_alvo[
                        "vy"
                    ]

                    nx, ny = (
                        get_inside_normal(

                            vx,
                            vy,

                            px,
                            py,

                            centro_x,
                            centro_y
                        )
                    )

                    # -----------------------------------------
                    # GERA TUE
                    # -----------------------------------------

                    adicionar_tomada(

                        msp=msp,

                        tipo="TUE",

                        ambiente=nome,

                        indice=idx_tue + 1,

                        px=px,
                        py=py,

                        seg_vx=vx,
                        seg_vy=vy,

                        nx=nx,
                        ny=ny,

                        potencia=pot_tue_val,

                        is_molhado=
                            is_ambiente_molhado,

                        is_chuveiro_ou_ac=
                            is_chuveiro_ou_ac
                    )

            # =================================================
            # TUGs
            # =================================================

            if (
                qtd_tugs > 0
                and
                comp_total > 0
            ):

                # ---------------------------------------------
                # FOLGA DOS CANTOS
                # ---------------------------------------------

                margem_inicial = 0.25

                comprimento_util = (

                    comp_total
                    -
                    (
                        2
                        *
                        margem_inicial
                    )
                )

                if (
                    comprimento_util > 0
                    and
                    qtd_tugs > 0
                ):

                    passo = (
                        comprimento_util
                        /
                        qtd_tugs
                    )

                    inicio_offset = (

                        margem_inicial
                        +
                        (
                            passo / 2
                        )
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

                # ---------------------------------------------
                # GERA EXATAMENTE qtd_tugs
                # ---------------------------------------------

                for i in range(
                    qtd_tugs
                ):

                    dist_atual = (

                        inicio_offset
                        +
                        (
                            i * passo
                        )
                    )

                    px, py, seg_vx, seg_vy = (
                        get_ponto_perimetro(

                            dist_atual,

                            segmentos_crus
                        )
                    )

                    # -----------------------------------------
                    # EVITA CENTRO DA PORTA
                    # -----------------------------------------

                    perto_de_vao = (
                        ponto_proximo_de_porta(

                            px,
                            py,

                            portas_raw,

                            tolerancia=0.35
                        )
                    )

                    if perto_de_vao:

                        # Primeiro tenta deslocar no sentido
                        # da parede
                        px += (
                            seg_vx * 0.30
                        )

                        py += (
                            seg_vy * 0.30
                        )

                    # -----------------------------------------
                    # NORMAL INTERNA
                    # -----------------------------------------

                    nx, ny = (
                        get_inside_normal(

                            seg_vx,
                            seg_vy,

                            px,
                            py,

                            centro_x,
                            centro_y
                        )
                    )

                    # -----------------------------------------
                    # GARANTE PONTO DENTRO DO AMBIENTE
                    # -----------------------------------------

                    if not ponto_em_poligono(

                        px,
                        py,
                        polilinha
                    ):

                        px -= (
                            seg_vx * 0.30
                        )

                        py -= (
                            seg_vy * 0.30
                        )

                    # -----------------------------------------
                    # GERA TUG
                    # -----------------------------------------

                    adicionar_tomada(

                        msp=msp,

                        tipo="TUG",

                        ambiente=nome,

                        indice=i + 1,

                        px=px,
                        py=py,

                        seg_vx=seg_vx,
                        seg_vy=seg_vy,

                        nx=nx,
                        ny=ny,

                        potencia=pot_tug_val,

                        is_molhado=
                            is_ambiente_molhado,

                        is_chuveiro_ou_ac=False
                    )

        # ====================================================
        # VALIDAÇÃO FINAL
        # ====================================================

        resultado_validacao = (
            validar_quantitativos(

                doc,

                dados_editados
            )
        )

        # ====================================================
        # SALVA SOMENTE SE ESTIVER CORRETO
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
