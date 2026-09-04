import unicodedata

import os
import tempfile
import math

import ezdxf
import streamlit as st

from dxf_io import ler_elementos
from portas_selecao import portas_do_ambiente
from soleiras_geometria import rotular_p1_p4, distancia_ponto_segmento


def _nome_ambiente_da_poligonal(poly, textos):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]

    return next(
        (
            t["nome"]
            for t in textos
            if min(xs) - 0.5 <= t["x"] <= max(xs) + 0.5
            and min(ys) - 0.5 <= t["y"] <= max(ys) + 0.5
        ),
        None
    )


def _ambientes_geometricos(polilinhas, textos):
    resultado = {}
    usados = {}

    for poly in polilinhas:
        nome = _nome_ambiente_da_poligonal(poly, textos)
        if not nome:
            continue

        if nome in usados:
            usados[nome] += 1
            nome_final = f"{nome} {usados[nome]}"
        else:
            usados[nome] = 1
            nome_final = nome

        resultado[nome_final] = poly

    return resultado



def _distancia(a, b):
    return (
        (float(a[0]) - float(b[0])) ** 2
        + (float(a[1]) - float(b[1])) ** 2
    ) ** 0.5


def _amostrar_arco(entidade, passos=24):
    centro = (
        float(entidade.dxf.center.x),
        float(entidade.dxf.center.y)
    )
    raio = float(entidade.dxf.radius)
    inicio = float(entidade.dxf.start_angle)
    fim = float(entidade.dxf.end_angle)

    while fim < inicio:
        fim += 360.0

    pontos = []

    for i in range(passos + 1):
        ang = inicio + (
            fim - inicio
        ) * i / passos

        rad = math.radians(ang)

        pontos.append((
            centro[0]
            + raio * math.cos(rad),
            centro[1]
            + raio * math.sin(rad)
        ))

    return pontos


def _geometrias_porta_do_dxf(msp):
    """
    Lê a geometria VISUAL real da camada IA_PORTAS.
    Mantém polilinhas/linhas e amostra os ARCOS de abertura.
    """
    geometrias = []

    for ent in msp:
        if (
            str(
                getattr(
                    ent.dxf,
                    "layer",
                    ""
                )
            ).upper().strip()
            != "IA_PORTAS"
        ):
            continue

        tipo = ent.dxftype()
        pontos = []

        try:
            if tipo == "LINE":
                pontos = [
                    (
                        float(ent.dxf.start.x),
                        float(ent.dxf.start.y)
                    ),
                    (
                        float(ent.dxf.end.x),
                        float(ent.dxf.end.y)
                    )
                ]

            elif tipo == "LWPOLYLINE":
                pontos = [
                    (
                        float(x),
                        float(y)
                    )
                    for x, y
                    in ent.get_points("xy")
                ]

                if (
                    getattr(
                        ent,
                        "closed",
                        False
                    )
                    and pontos
                ):
                    pontos = (
                        pontos
                        + [pontos[0]]
                    )

            elif tipo == "POLYLINE":
                pontos = [
                    (
                        float(
                            v.dxf.location.x
                        ),
                        float(
                            v.dxf.location.y
                        )
                    )
                    for v in ent.vertices
                ]

            elif tipo == "ARC":
                pontos = (
                    _amostrar_arco(
                        ent
                    )
                )

        except Exception:
            pontos = []

        if len(pontos) >= 2:
            geometrias.append({
                "tipo": tipo,
                "pontos": pontos
            })

    return geometrias



def _centro_geometria(geometria):
    pontos = geometria.get("pontos") or []

    if not pontos:
        return None

    return (
        sum(float(p[0]) for p in pontos) / len(pontos),
        sum(float(p[1]) for p in pontos) / len(pontos)
    )


def _porta_mais_proxima_da_geometria(
    geometria,
    portas,
    tolerancia=0.22
):
    """
    Associa cada geometria visual de IA_PORTAS a UMA única porta.

    Isso evita que a mesma folha/arco seja desenhada mais de uma vez
    em soleiras vizinhas.
    """
    if not portas:
        return None

    melhor = None
    menor = float("inf")

    for porta in portas:
        referencias = (
            porta["soleira"].get(
                "vertices",
                []
            )
            or []
        )

        if not referencias:
            continue

        d = min(
            _distancia(
                ponto,
                ref
            )
            for ponto in geometria["pontos"]
            for ref in referencias
        )

        if d < menor:
            menor = d
            melhor = porta

    if menor <= tolerancia:
        return melhor

    return None

def analisar_portas_dxf(dxf_bytes):
    """
    Além das portas selecionáveis, guarda a geometria arquitetônica
    da folha e dos arcos de abertura para a mini planta.
    """
    if not dxf_bytes:
        return {}

    caminho = None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".dxf"
        ) as tmp:
            tmp.write(dxf_bytes)
            caminho = tmp.name

        doc = ezdxf.readfile(
            caminho
        )

        msp = doc.modelspace()

        elementos = (
            ler_elementos(
                msp
            )
        )

        ambientes = (
            _ambientes_geometricos(
                elementos[
                    "polilinhas"
                ],
                elementos[
                    "textos"
                ]
            )
        )

        todas_geometrias = (
            _geometrias_porta_do_dxf(
                msp
            )
        )

        saida = {}

        for nome, poly in ambientes.items():

            portas = (
                portas_do_ambiente(
                    nome,
                    poly,
                    elementos[
                        "soleiras_raw"
                    ]
                )
            )

            geometrias = []

            for geometria in todas_geometrias:
                porta_associada = (
                    _porta_mais_proxima_da_geometria(
                        geometria,
                        portas
                    )
                )

                if porta_associada is None:
                    continue

                # Cada geometria recebe o ID da única porta
                # à qual foi associada.
                geometrias.append({
                    "tipo":
                        geometria["tipo"],
                    "pontos":
                        geometria["pontos"],
                    "porta_id":
                        porta_associada["id"]
                })

            saida[nome] = {
                "poly": poly,
                "portas": portas,
                "geometrias_portas":
                    geometrias
            }

        return saida

    finally:
        if (
            caminho
            and os.path.exists(
                caminho
            )
        ):
            os.remove(
                caminho
            )



def _maior_lado_soleira(verts):
    if not verts or len(verts) < 2:
        return None
    arestas=[]
    for i in range(len(verts)):
        a=(float(verts[i][0]),float(verts[i][1]))
        b=(float(verts[(i+1)%len(verts)][0]),float(verts[(i+1)%len(verts)][1]))
        comp=_distancia(a,b)
        if comp>1e-9:
            arestas.append((comp,a,b))
    return max(arestas,key=lambda item:item[0]) if arestas else None


def _porta_geom_mais_proxima_da_soleira(soleira, geometrias_portas):
    verts=soleira.get("vertices") or []
    if not verts or not geometrias_portas:
        return None
    melhor=None
    menor=float("inf")
    for geometria in geometrias_portas:
        pontos=geometria.get("pontos",[])
        if not pontos:
            continue
        d=min(_distancia(ponto,ref) for ponto in pontos for ref in verts)
        if d<menor:
            menor=d
            melhor=geometria
    return melhor


def _arco_quarto_circulo(centro,inicio,sentido,raio,passos=20):
    pontos=[]
    for i in range(passos+1):
        ang=inicio+sentido*90.0*i/passos
        rad=math.radians(ang)
        pontos.append((centro[0]+raio*math.cos(rad),centro[1]+raio*math.sin(rad)))
    return pontos


def _geometria_visual_porta_por_soleira(porta,poly,geometrias_portas):
    soleira=porta["soleira"]
    verts=soleira.get("vertices") or []
    maior=_maior_lado_soleira(verts)
    if maior is None:
        return None
    comprimento,a,b=maior

    arestas=[]
    for i in range(len(verts)):
        p=(float(verts[i][0]),float(verts[i][1]))
        q=(float(verts[(i+1)%len(verts)][0]),float(verts[(i+1)%len(verts)][1]))
        comp=_distancia(p,q)
        if comp>1e-9:
            arestas.append((comp,p,q))
    arestas.sort(key=lambda item:item[0],reverse=True)
    face=arestas[0]
    pA,pB=face[1],face[2]

    cx=sum(float(p[0]) for p in poly)/len(poly)
    cy=sum(float(p[1]) for p in poly)/len(poly)
    centro_amb=(cx,cy)

    original=_porta_geom_mais_proxima_da_soleira(soleira,geometrias_portas)
    if original and original.get("pontos"):
        primeiro=original["pontos"][0]
        if _distancia(primeiro,pA)<=_distancia(primeiro,pB):
            dobradica,outro=pA,pB
        else:
            dobradica,outro=pB,pA
    else:
        dobradica,outro=((pA,pB) if (pA[0],pA[1])<=(pB[0],pB[1]) else (pB,pA))

    vx=outro[0]-dobradica[0]
    vy=outro[1]-dobradica[1]
    comp=math.hypot(vx,vy)
    if comp<=1e-12:
        return None
    ux,uy=vx/comp,vy/comp
    n1=(-uy,ux)
    n2=(uy,-ux)

    probe1=(dobradica[0]+n1[0]*0.05,dobradica[1]+n1[1]*0.05)
    probe2=(dobradica[0]+n2[0]*0.05,dobradica[1]+n2[1]*0.05)
    normal=n1 if _distancia(probe1,centro_amb)<=_distancia(probe2,centro_amb) else n2

    folha_fim=(dobradica[0]+normal[0]*comprimento,dobradica[1]+normal[1]*comprimento)
    ang_inicio=math.degrees(math.atan2(outro[1]-dobradica[1],outro[0]-dobradica[0]))
    ang_folha=math.degrees(math.atan2(folha_fim[1]-dobradica[1],folha_fim[0]-dobradica[0]))
    delta_ccw=(ang_folha-ang_inicio)%360.0
    sentido=1.0 if delta_ccw<=180.0 else -1.0
    arco=_arco_quarto_circulo(dobradica,ang_inicio,sentido,comprimento)

    return {"folha":[dobradica,folha_fim],"arco":arco,"raio":comprimento,"dobradica":dobradica}

def _figura_ambiente(
    nome,
    poly,
    portas,
    selecionadas,
    geometrias_portas=None
):
    """
    Mini planta Fase 8.2:
    visual arquitetônico inspirado na referência do usuário.
    """
    geometrias_portas = (
        geometrias_portas
        or []
    )

    if not poly:
        return {}

    xs_poly = [
        float(p[0])
        for p in poly
    ]

    ys_poly = [
        float(p[1])
        for p in poly
    ]

    xs_todos = list(
        xs_poly
    )

    ys_todos = list(
        ys_poly
    )

    for porta in portas:
        for ponto in (
            porta["soleira"].get(
                "vertices",
                []
            )
            or []
        ):
            xs_todos.append(
                float(
                    ponto[0]
                )
            )
            ys_todos.append(
                float(
                    ponto[1]
                )
            )

    for geometria in geometrias_portas:
        for ponto in geometria[
            "pontos"
        ]:
            xs_todos.append(
                float(
                    ponto[0]
                )
            )
            ys_todos.append(
                float(
                    ponto[1]
                )
            )

    min_x = min(
        xs_todos
    )
    max_x = max(
        xs_todos
    )
    min_y = min(
        ys_todos
    )
    max_y = max(
        ys_todos
    )

    largura = max(
        max_x - min_x,
        0.50
    )

    altura = max(
        max_y - min_y,
        0.50
    )

    margem_x = max(
        largura * 0.14,
        0.22
    )

    margem_y = max(
        altura * 0.14,
        0.22
    )

    dominio_x = [
        min_x - margem_x,
        max_x + margem_x
    ]

    dominio_y = [
        min_y - margem_y,
        max_y + margem_y
    ]

    # Fase 8.2:
    # Quadro fixo para as duas colunas.
    # O ambiente inteiro recebe UM ÚNICO fator percentual,
    # igual em X e Y, até caber no quadro (fit/contain).
    largura_grafico = 430
    altura_grafico = 330
    margem_percentual = 0.08

    largura_util = (
        largura_grafico
        * (1.0 - 2.0 * margem_percentual)
    )
    altura_util = (
        altura_grafico
        * (1.0 - 2.0 * margem_percentual)
    )

    largura_real = max(
        max_x - min_x,
        0.01
    )
    altura_real = max(
        max_y - min_y,
        0.01
    )

    fator_escala = min(
        largura_util / largura_real,
        altura_util / altura_real
    )

    centro_real_x = (
        min_x + max_x
    ) / 2.0
    centro_real_y = (
        min_y + max_y
    ) / 2.0

    centro_canvas_x = (
        largura_grafico / 2.0
    )
    centro_canvas_y = (
        altura_grafico / 2.0
    )

    # Fase 8.2:
    # A orientação visual é EXATAMENTE a mesma do DXF original.
    # Não há rotação, espelhamento ou escala diferente entre X e Y.
    #
    # O ambiente inteiro recebe apenas UM fator uniforme de escala
    # ("fit/contain") para caber dentro do quadro fixo.
    fator_escala = min(
        largura_util / largura_real,
        altura_util / altura_real
    )

    def _transformar_visual(ponto):
        dx = (
            float(ponto[0])
            - centro_real_x
        )
        dy = (
            float(ponto[1])
            - centro_real_y
        )

        return (
            centro_canvas_x
            + dx * fator_escala,
            centro_canvas_y
            + dy * fator_escala
        )

    dominio_x = [
        0.0,
        float(largura_grafico)
    ]
    dominio_y = [
        0.0,
        float(altura_grafico)
    ]

    # =========================================================
    # PAREDES
    # Duas linhas visuais são simuladas com traço preto grosso
    # e uma linha branca mais fina sobre ele.
    # =========================================================
    contorno = []

    pontos_contorno = (
        list(poly)
        + [poly[0]]
    )

    for ordem, ponto in enumerate(
        pontos_contorno
    ):
        contorno.append({
            "x":
                float(
                    ponto[0]
                ),
            "y":
                float(
                    ponto[1]
                ),
            "ordem":
                ordem
        })

    # =========================================================
    # ABERTURAS DAS PORTAS
    # A soleira recebe uma linha branca grossa que apaga a
    # parede visual naquele trecho.
    # =========================================================
    aberturas = []

    for porta in portas:
        verts = list(
            porta[
                "soleira"
            ].get(
                "vertices"
            )
            or []
        )

        if len(verts) < 4:
            continue

        # Maior aresta da soleira = largura do vão.
        arestas = []

        for i in range(
            len(verts)
        ):
            a = verts[i]
            b = verts[
                (i + 1)
                % len(verts)
            ]

            comp = _distancia(
                a,
                b
            )

            arestas.append(
                (
                    comp,
                    a,
                    b
                )
            )

        arestas.sort(
            key=lambda x:
                x[0],
            reverse=True
        )

        # As duas maiores são faces paralelas.
        for grupo, (_, a, b) in enumerate(
            arestas[:2]
        ):
            aberturas.extend([
                {
                    "porta_id":
                        porta["id"],
                    "grupo":
                        (
                            f"{porta['id']}"
                            f"_{grupo}"
                        ),
                    "ordem": 0,
                    "x":
                        float(
                            a[0]
                        ),
                    "y":
                        float(
                            a[1]
                        )
                },
                {
                    "porta_id":
                        porta["id"],
                    "grupo":
                        (
                            f"{porta['id']}"
                            f"_{grupo}"
                        ),
                    "ordem": 1,
                    "x":
                        float(
                            b[0]
                        ),
                    "y":
                        float(
                            b[1]
                        )
                }
            ])

    # =========================================================
    # FOLHAS E ARCOS REAIS DO DXF
    # =========================================================
    linhas_porta = []

    for indice, porta in enumerate(portas):
        visual=_geometria_visual_porta_por_soleira(
            porta,poly,geometrias_portas
        )
        if visual is None:
            continue

        for ordem,ponto in enumerate(visual["folha"]):
            linhas_porta.append({
                "grupo":f"FOLHA_{porta['id']}",
                "tipo":"FOLHA",
                "ordem":ordem,
                "x":float(ponto[0]),
                "y":float(ponto[1])
            })

        for ordem,ponto in enumerate(visual["arco"]):
            linhas_porta.append({
                "grupo":f"ARCO_{porta['id']}",
                "tipo":"ARCO",
                "ordem":ordem,
                "x":float(ponto[0]),
                "y":float(ponto[1])
            })

    # =========================================================
    # MARCADORES
    # =========================================================
    dados_portas = []

    for porta in portas:
        selecionada = (
            porta["id"]
            in selecionadas
        )

        dados_portas.append({
            "x":
                float(
                    porta[
                        "centro"
                    ][0]
                ),
            "y":
                float(
                    porta[
                        "centro"
                    ][1]
                ),
            "porta_id":
                porta["id"],
            "rotulo":
                porta["rotulo"],
            "estado":
                (
                    "Selecionada"
                    if selecionada
                    else
                    "Sem interruptor"
                ),
            "selecionada":
                (
                    "SIM"
                    if selecionada
                    else "NAO"
                ),
            "tamanho":
                (
                    310
                    if selecionada
                    else 260
                )
        })

    # Fase 8.2 — aplica o MESMO percentual em todos os elementos.
    for item in contorno:
        item["x"], item["y"] = _transformar_visual(
            (item["x"], item["y"])
        )

    for item in aberturas:
        item["x"], item["y"] = _transformar_visual(
            (item["x"], item["y"])
        )

    for item in linhas_porta:
        item["x"], item["y"] = _transformar_visual(
            (item["x"], item["y"])
        )

    for item in dados_portas:
        item["x"], item["y"] = _transformar_visual(
            (item["x"], item["y"])
        )

    centro_nome = _transformar_visual(
        (
            (min(xs_poly) + max(xs_poly)) / 2.0,
            (min(ys_poly) + max(ys_poly)) / 2.0
        )
    )

    escala_x = {
        "domain":
            dominio_x,
        "nice":
            False,
        "zero":
            False
    }

    escala_y = {
        "domain":
            dominio_y,
        "nice":
            False,
        "zero":
            False
    }

    layers = [
        # Parede externa preta grossa
        {
            "data": {
                "values":
                    contorno
            },
            "mark": {
                "type": "line",
                "stroke":
                    "#111827",
                "strokeWidth":
                    9,
                "strokeJoin":
                    "miter"
            },
            "encoding": {
                "x": {
                    "field": "x",
                    "type":
                        "quantitative",
                    "axis": None,
                    "scale":
                        escala_x
                },
                "y": {
                    "field": "y",
                    "type":
                        "quantitative",
                    "axis": None,
                    "scale":
                        escala_y
                },
                "order": {
                    "field":
                        "ordem",
                    "type":
                        "quantitative"
                }
            }
        },

        # Linha branca interna cria efeito de parede dupla
        {
            "data": {
                "values":
                    contorno
            },
            "mark": {
                "type": "line",
                "stroke":
                    "#ffffff",
                "strokeWidth":
                    4,
                "strokeJoin":
                    "miter"
            },
            "encoding": {
                "x": {
                    "field": "x",
                    "type":
                        "quantitative",
                    "axis": None,
                    "scale":
                        escala_x
                },
                "y": {
                    "field": "y",
                    "type":
                        "quantitative",
                    "axis": None,
                    "scale":
                        escala_y
                },
                "order": {
                    "field":
                        "ordem",
                    "type":
                        "quantitative"
                }
            }
        },

        # Aberturas brancas sobre a parede
        {
            "data": {
                "values":
                    aberturas
            },
            "mark": {
                "type": "line",
                "stroke":
                    "#ffffff",
                "strokeWidth":
                    13
            },
            "encoding": {
                "x": {
                    "field": "x",
                    "type":
                        "quantitative",
                    "axis": None,
                    "scale":
                        escala_x
                },
                "y": {
                    "field": "y",
                    "type":
                        "quantitative",
                    "axis": None,
                    "scale":
                        escala_y
                },
                "detail": {
                    "field":
                        "grupo",
                    "type":
                        "nominal"
                },
                "order": {
                    "field":
                        "ordem",
                    "type":
                        "quantitative"
                }
            }
        }
    ]

    if linhas_porta:
        layers.append({
            "data": {
                "values":
                    linhas_porta
            },
            "mark": {
                "type": "line",
                "stroke":
                    "#111827",
                "strokeWidth":
                    1.6
            },
            "encoding": {
                "x": {
                    "field": "x",
                    "type":
                        "quantitative",
                    "axis": None,
                    "scale":
                        escala_x
                },
                "y": {
                    "field": "y",
                    "type":
                        "quantitative",
                    "axis": None,
                    "scale":
                        escala_y
                },
                "detail": {
                    "field":
                        "grupo",
                    "type":
                        "nominal"
                },
                "order": {
                    "field":
                        "ordem",
                    "type":
                        "quantitative"
                }
            }
        })

    layers.extend([
        # Marcador clicável
        {
            "data": {
                "values":
                    dados_portas
            },
            "params": [
                {
                    "name":
                        "porta",
                    "select": {
                        "type":
                            "point",
                        "fields": [
                            "porta_id"
                        ],
                        "on":
                            "click",
                            "toggle": "true",
                        "clear":
                            False
                    }
                }
            ],
            "mark": {
                "type":
                    "point",
                "filled":
                    True,
                "stroke":
                    "#ffffff",
                "strokeWidth":
                    1.6
            },
            "encoding": {
                "x": {
                    "field": "x",
                    "type":
                        "quantitative",
                    "axis": None,
                    "scale":
                        escala_x
                },
                "y": {
                    "field": "y",
                    "type":
                        "quantitative",
                    "axis": None,
                    "scale":
                        escala_y
                },
                "size": {
                    "field":
                        "tamanho",
                    "type":
                        "quantitative",
                    "scale": None,
                    "legend": None
                },
                "color": {
                    "condition": {
                        "test":
                            (
                                "datum."
                                "selecionada "
                                "=== 'SIM'"
                            ),
                        "value":
                            "#34a853"
                    },
                    "value":
                        "#ef5350"
                },
                "tooltip": [
                    {
                        "field":
                            "rotulo",
                        "type":
                            "nominal",
                        "title":
                            "Porta"
                    },
                    {
                        "field":
                            "estado",
                        "type":
                            "nominal",
                        "title":
                            "Interruptor"
                    }
                ]
            }
        },

        # Porta 1, Porta 2...
        {
            "data": {
                "values":
                    dados_portas
            },
            "mark": {
                "type":
                    "text",
                "dy":
                    -17,
                "fontSize":
                    11,
                "fontWeight":
                    "bold",
                "color":
                    "#111827"
            },
            "encoding": {
                "x": {
                    "field": "x",
                    "type":
                        "quantitative",
                    "axis": None,
                    "scale":
                        escala_x
                },
                "y": {
                    "field": "y",
                    "type":
                        "quantitative",
                    "axis": None,
                    "scale":
                        escala_y
                },
                "text": {
                    "field":
                        "rotulo",
                    "type":
                        "nominal"
                }
            }
        },

        # Nome do ambiente forte e central
        {
            "data": {
                "values": [{
                    "x":
                        centro_nome[0],
                    "y":
                        centro_nome[1],
                    "nome":
                        nome
                }]
            },
            "mark": {
                "type":
                    "text",
                "fontSize":
                    17,
                "fontWeight":
                    "bold",
                "color":
                    "#111827"
            },
            "encoding": {
                "x": {
                    "field": "x",
                    "type":
                        "quantitative",
                    "axis": None,
                    "scale":
                        escala_x
                },
                "y": {
                    "field": "y",
                    "type":
                        "quantitative",
                    "axis": None,
                    "scale":
                        escala_y
                },
                "text": {
                    "field":
                        "nome",
                    "type":
                        "nominal"
                }
            }
        }
    ])

    return {
        "$schema": (
            "https://vega.github.io/"
            "schema/vega-lite/v5.json"
        ),
        "width":
            largura_grafico,
        "height":
            altura_grafico,
        "background":
            "#ffffff",
        "autosize": {
            "type":
                "fit",
            "contains":
                "padding",
            "resize":
                True
        },
        "padding": {
            "left": 14,
            "right": 14,
            "top": 14,
            "bottom": 14
        },
        "config": {
            "view": {
                "stroke":
                    "#e5e7eb",
                "strokeWidth":
                    1
            },
            "axis": {
                "grid":
                    False
            }
        },
        "layer":
            layers
    }

def _ids_salvos_ambiente(config_salva, amb, portas):
    """
    Fase 8.2:
    restaura apenas escolhas gráficas reais já salvas por ID.
    Configurações antigas baseadas somente em quantidade NÃO
    selecionam portas automaticamente.
    """
    ids_validos = {
        p["id"]
        for p in portas
    }

    cfg = (
        config_salva.get(amb, {})
        if isinstance(config_salva, dict)
        else {}
    )

    if not isinstance(cfg, dict):
        return []

    salvos = cfg.get(
        "portas_ids",
        []
    )

    if not isinstance(salvos, list):
        return []

    return [
        pid
        for pid in salvos
        if pid in ids_validos
    ]

def _ambiente_sem_interruptor_proprio(nome):
    """Fase 13.0: iluminação comandada pelo ambiente interno adjacente."""
    txt = unicodedata.normalize("NFKD", str(nome or "")).encode("ascii", "ignore").decode("ascii").casefold()
    compacto = "".join(ch for ch in txt if ch.isalnum())
    return any(chave in compacto for chave in ("varanda", "terraco", "garagem"))


def _token_projeto_ui():
    import hashlib
    projeto = str(st.session_state.get("projeto_ativo", "SEM_PROJETO"))
    return hashlib.sha1(projeto.encode("utf-8")).hexdigest()[:10]

def renderizar_interruptores(
    dados_ambientes,
    config_salva,
    dxf_bytes=None
):
    analise = analisar_portas_dxf(dxf_bytes)

    nomes = sorted(
        [r["Ambiente"] for r in dados_ambientes],
        key=str.casefold
    )

    config = {}
    multiplos = []

    for amb in nomes:
        portas = analise.get(amb, {}).get("portas", [])
        qtd = len(portas)

        if _ambiente_sem_interruptor_proprio(amb):
            config[amb] = {
                "quantidade": 0,
                "portas_ids": [],
                "portas_detectadas": qtd,
                "automatico": True,
                "comando_externo": True
            }
            continue

        if qtd == 0:
            config[amb] = {
                "quantidade": 0,
                "portas_ids": [],
                "portas_detectadas": 0,
                "automatico": True
            }

        elif qtd == 1:
            # Uma porta: sempre automática.
            config[amb] = {
                "quantidade": 1,
                "portas_ids": [portas[0]["id"]],
                "portas_detectadas": 1,
                "automatico": True
            }

        else:
            multiplos.append(amb)

    if not multiplos:
        st.info(
            "Nenhum ambiente possui duas ou mais portas. "
            "Ambientes com uma única porta recebem "
            "1 interruptor automaticamente."
        )
        return config

    st.markdown(
        "Nos ambientes abaixo, organizados em **duas colunas**, escolha **diretamente na mini planta** "
        "quais portas receberão interruptores. "
        "Clique em uma porta para selecionar ou retirar a seleção."
    )

    col_esquerda, col_direita = st.columns(2, gap="medium")

    for indice_amb, amb in enumerate(multiplos):
        coluna = (
            col_esquerda
            if indice_amb % 2 == 0
            else col_direita
        )

        with coluna:
            portas = analise[amb]["portas"]
            poly = analise[amb]["poly"]
    
            token_projeto = _token_projeto_ui()


    
            chave_estado = (

    
                "fase8_13_portas_interruptor_"

    
                f"{token_projeto}_{amb}"

    
            )


    
            if chave_estado not in st.session_state:

    
                st.session_state[chave_estado] = _ids_salvos_ambiente(

    
                    config_salva,

    
                    amb,

    
                    portas

    
                )
    
            # Remove IDs que deixaram de existir após troca do DXF.
            ids_validos = {p["id"] for p in portas}
            st.session_state[chave_estado] = [
                pid
                for pid in st.session_state[chave_estado]
                if pid in ids_validos
            ]
    
            selecionadas = list(st.session_state[chave_estado])
    
            with st.expander(
                f"🚪 {amb} — {len(portas)} portas",
                expanded=True
            ):
                st.caption(
                    "Clique diretamente no círculo da porta. "
                    "🔴 Vermelho = sem interruptor   |   "
                    "🟢 Verde = selecionada"
                )
    
                fig = _figura_ambiente(
                    amb,
                    poly,
                    portas,
                    selecionadas,
                    analise[amb].get(
                        "geometrias_portas",
                        []
                    )
                )
    
                evento = st.vega_lite_chart(
                    fig,
                    use_container_width=False,
                    key=f"fase8_13_planta_portas_{token_projeto}_{amb}",
                    on_select="rerun"
                )
    
                # Fase 8.2:
                # O parâmetro Vega usa toggle="true":
                # cada clique comum adiciona/remove uma porta,
                # sem necessidade de Shift.
                ids_evento = []
                selecao_recebida = False

                try:
                    sel = evento.selection.porta
                except Exception:
                    try:
                        sel = evento[
                            "selection"
                        ]["porta"]
                    except Exception:
                        sel = None

                if sel is not None:
                    if hasattr(
                        sel,
                        "to_dict"
                    ):
                        try:
                            sel = sel.to_dict()
                        except Exception:
                            pass

                    if isinstance(
                        sel,
                        dict
                    ):
                        if "porta_id" in sel:
                            bruto = sel.get(
                                "porta_id"
                            )

                            if isinstance(
                                bruto,
                                str
                            ):
                                ids_evento = [
                                    bruto
                                ]

                            elif isinstance(
                                bruto,
                                (list, tuple)
                            ):
                                ids_evento = list(
                                    bruto
                                )

                            elif bruto is None:
                                ids_evento = []

                            selecao_recebida = True

                        elif "values" in sel:
                            valores = (
                                sel.get(
                                    "values"
                                )
                                or []
                            )

                            for item in valores:
                                if isinstance(
                                    item,
                                    dict
                                ):
                                    pid = (
                                        item.get(
                                            "porta_id"
                                        )
                                    )

                                    if pid:
                                        ids_evento.append(
                                            pid
                                        )

                            selecao_recebida = True

                    elif isinstance(
                        sel,
                        (list, tuple)
                    ):
                        for item in sel:
                            if isinstance(
                                item,
                                dict
                            ):
                                pid = (
                                    item.get(
                                        "porta_id"
                                    )
                                )

                                if pid:
                                    ids_evento.append(
                                        pid
                                    )

                        selecao_recebida = True

                ids_evento = list(
                    dict.fromkeys(
                        pid
                        for pid
                        in ids_evento
                        if pid
                        in ids_validos
                    )
                )

                if selecao_recebida:
                    estado_atual = list(
                        st.session_state[
                            chave_estado
                        ]
                    )

                    if set(
                        ids_evento
                    ) != set(
                        estado_atual
                    ):
                        st.session_state[
                            chave_estado
                        ] = ids_evento

                        # on_select já executou o primeiro rerun.
                        # Este segundo serve apenas para refletir
                        # imediatamente as cores e a contagem.
                        st.rerun()

                # Fase 8.2:
                # a escolha é feita diretamente na mini planta.
                # Não há mais dropdown/multiselect.
                selecionadas = list(
                    st.session_state[
                        chave_estado
                    ]
                )

                if selecionadas:
                    st.success(
                        f"{len(selecionadas)} "
                        + (
                            "porta selecionada."
                            if len(selecionadas) == 1
                            else "portas selecionadas."
                        )
                    )
                else:
                    st.warning(
                        "Nenhuma porta selecionada: "
                        "este ambiente ficará sem interruptor."
                    )

                config[amb] = {
                    "quantidade": len(selecionadas),
                    "portas_ids": selecionadas,
                    "portas_detectadas": len(portas),
                    "automatico": False
                }

    return config
