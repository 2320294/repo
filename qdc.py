import os
import tempfile
import unicodedata
import math

import ezdxf
import streamlit as st

from dxf_io import (
    ler_elementos,
    nome_ambiente_para_polilinha
)
from geometria import (
    bbox_poligono
)
from qdc_config import (
    codificar_qdc,
    decodificar_qdc,
    decodificar_qdc_completo
)
from interruptores import (
    analisar_portas_dxf,
    _geometria_visual_porta_por_soleira
)



def _normalizar_nome_ambiente(nome):
    """
    Normaliza nomes como:
    W.C. -> wc
    A.S. -> as
    Área de Serviço -> areadeservico
    """
    texto = unicodedata.normalize(
        "NFKD",
        str(nome or "")
    )

    texto = "".join(
        ch
        for ch in texto
        if not unicodedata.combining(ch)
    )

    return "".join(
        ch
        for ch in texto.casefold()
        if ch.isalnum()
    )


def _ambiente_molhado_qdc(nome):
    """
    Ambientes molhados/serviço não podem aparecer
    como opção para o QDC.
    """
    n = _normalizar_nome_ambiente(
        nome
    )

    if not n:
        return False

    if n in {
        "wc",
        "bwc",
        "as",
        "areadeservico",
        "areaservico",
        "banheiro",
        "sanitario",
        "lavabo",
        "lavanderia",
        "cozinha",
        "servico"
    }:
        return True

    return any(
        termo in n
        for termo in [
            "coz",
            "banh",
            "sanit",
            "lavand",
            "lavabo",
            "servico",
            "areadeserv"
        ]
    )


def _ambiente_circulacao_qdc(nome):
    n = _normalizar_nome_ambiente(
        nome
    )

    return any(
        termo in n
        for termo in [
            "hall",
            "corredor",
            "circul",
            "circ"
        ]
    )



def _amostrar_arco_qdc(entidade, passos=24):
    centro=(float(entidade.dxf.center.x),float(entidade.dxf.center.y))
    raio=float(entidade.dxf.radius)
    inicio=float(entidade.dxf.start_angle)
    fim=float(entidade.dxf.end_angle)
    while fim < inicio:
        fim += 360.0
    pontos=[]
    for i in range(passos+1):
        ang=inicio+(fim-inicio)*i/passos
        rad=math.radians(ang)
        pontos.append((centro[0]+raio*math.cos(rad),centro[1]+raio*math.sin(rad)))
    return pontos


def _geometrias_portas_qdc(msp):
    geometrias=[]
    for ent in msp:
        if str(getattr(ent.dxf,"layer","")).upper().strip() != "IA_PORTAS":
            continue
        tipo=ent.dxftype(); pontos=[]
        try:
            if tipo=="LINE":
                pontos=[(float(ent.dxf.start.x),float(ent.dxf.start.y)),(float(ent.dxf.end.x),float(ent.dxf.end.y))]
            elif tipo=="LWPOLYLINE":
                pontos=[(float(x),float(y)) for x,y in ent.get_points("xy")]
            elif tipo=="POLYLINE":
                pontos=[(float(v.dxf.location.x),float(v.dxf.location.y)) for v in ent.vertices]
            elif tipo=="ARC":
                pontos=_amostrar_arco_qdc(ent)
        except Exception:
            pontos=[]
        if len(pontos)>=2:
            geometrias.append({"tipo":tipo,"pontos":pontos})
    return geometrias


def _distancia_ponto_segmento_qdc(px,py,a,b):
    ax,ay=float(a[0]),float(a[1]); bx,by=float(b[0]),float(b[1])
    vx,vy=bx-ax,by-ay; den=vx*vx+vy*vy
    if den<=1e-12: return math.hypot(px-ax,py-ay)
    t=((px-ax)*vx+(py-ay)*vy)/den; t=max(0.0,min(1.0,t))
    qx,qy=ax+t*vx,ay+t*vy
    return math.hypot(px-qx,py-qy)


def _geometrias_portas_no_ambiente(poly, geometrias, tolerancia=0.35):
    saida=[]
    for geo in geometrias:
        pts=geo.get("pontos") or []
        if not pts: continue
        menor=float("inf")
        for px,py in pts:
            for i in range(len(poly)):
                d=_distancia_ponto_segmento_qdc(px,py,poly[i],poly[(i+1)%len(poly)])
                if d<menor: menor=d
        if menor<=tolerancia: saida.append(geo)
    return saida

def _ambientes_do_dxf(
    dxf_bytes
):
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

        elementos = ler_elementos(
            msp
        )

        geometrias_portas = (
            _geometrias_portas_qdc(
                msp
            )
        )

        polilinhas = elementos[
            "polilinhas"
        ]
        textos = elementos[
            "textos"
        ]

        saida = {}
        usados = {}

        for poly in polilinhas:
            min_x, max_x, min_y, max_y = (
                bbox_poligono(poly)
            )

            if (
                (max_x - min_x)
                * (max_y - min_y)
                < 0.5
            ):
                continue

            nome = (
                nome_ambiente_para_polilinha(
                    poly,
                    textos
                )
            )

            if not nome:
                continue

            if nome in usados:
                usados[nome] += 1
                nome_final = (
                    f"{nome} "
                    f"{usados[nome]}"
                )
            else:
                usados[nome] = 1
                nome_final = nome

            paredes = []

            for indice in range(
                len(poly)
            ):
                p1 = poly[indice]
                p2 = poly[
                    (indice + 1)
                    % len(poly)
                ]

                dx = (
                    float(p2[0])
                    - float(p1[0])
                )
                dy = (
                    float(p2[1])
                    - float(p1[1])
                )

                comp = (
                    dx * dx
                    + dy * dy
                ) ** 0.5

                if comp <= 0.10:
                    continue

                paredes.append({
                    "numero":
                        len(paredes) + 1,
                    "p1": (
                        float(p1[0]),
                        float(p1[1])
                    ),
                    "p2": (
                        float(p2[0]),
                        float(p2[1])
                    ),
                    "comprimento":
                        comp
                })

            saida[nome_final] = {
                "poly":
                    list(poly),
                "paredes":
                    paredes,
                "geometrias_portas":
                    _geometrias_portas_no_ambiente(
                        poly,
                        geometrias_portas
                    )
            }

        return saida

    finally:
        if (
            caminho
            and os.path.exists(
                caminho
            )
        ):
            os.remove(caminho)



def _projecao_na_parede(
    ponto,
    p1,
    p2
):
    x = float(
        ponto[0]
    )
    y = float(
        ponto[1]
    )

    x1 = float(
        p1[0]
    )
    y1 = float(
        p1[1]
    )
    x2 = float(
        p2[0]
    )
    y2 = float(
        p2[1]
    )

    vx = x2 - x1
    vy = y2 - y1

    den = (
        vx * vx
        + vy * vy
    )

    if den <= 1e-12:
        return (
            0.0,
            float("inf")
        )

    t = (
        (x - x1) * vx
        + (y - y1) * vy
    ) / den

    qx = (
        x1 + t * vx
    )
    qy = (
        y1 + t * vy
    )

    dist = math.hypot(
        x - qx,
        y - qy
    )

    return (
        t,
        dist
    )


def _intervalo_porta_na_parede(
    porta,
    parede,
    tolerancia=0.28
):
    """
    Converte a soleira em intervalo t0..t1 da parede.
    Só é aceita quando a soleira realmente encosta na parede.
    """
    soleira = (
        porta.get(
            "soleira"
        )
        or {}
    )

    vertices = (
        soleira.get(
            "vertices"
        )
        or []
    )

    if len(vertices) < 2:
        vertices = [
            p
            for p in (
                soleira.get(
                    "p1"
                ),
                soleira.get(
                    "p2"
                )
            )
            if p is not None
        ]

    if len(vertices) < 2:
        return None

    proj = [
        _projecao_na_parede(
            v,
            parede["p1"],
            parede["p2"]
        )
        for v in vertices
    ]

    if min(
        dist
        for _, dist in proj
    ) > tolerancia:
        return None

    ts = [
        t
        for t, dist in proj
        if dist <= tolerancia
    ]

    if len(ts) < 2:
        ts = [
            t
            for t, _ in proj
        ]

    t0 = max(
        0.0,
        min(ts)
    )
    t1 = min(
        1.0,
        max(ts)
    )

    if (
        t1 - t0
        <= 0.015
    ):
        return None

    return (
        t0,
        t1
    )


def _mesclar_intervalos(
    intervalos
):
    if not intervalos:
        return []

    intervalos = sorted(
        intervalos,
        key=lambda x:
            x[0]
    )

    saida = [
        [
            intervalos[0][0],
            intervalos[0][1]
        ]
    ]

    for ini, fim in intervalos[1:]:
        atual = saida[
            -1
        ]

        if ini <= atual[1] + 0.015:
            atual[1] = max(
                atual[1],
                fim
            )
        else:
            saida.append(
                [
                    ini,
                    fim
                ]
            )

    return [
        (
            a,
            b
        )
        for a, b in saida
    ]


def _trechos_parede_qdc(
    parede,
    portas,
    margem_porta=0.03,
    comprimento_minimo=0.22
):
    cortes = []

    for porta in (
        portas
        or []
    ):
        intervalo = (
            _intervalo_porta_na_parede(
                porta,
                parede
            )
        )

        if intervalo is None:
            continue

        a, b = intervalo

        comp = max(
            float(
                parede[
                    "comprimento"
                ]
            ),
            1e-9
        )

        folga_t = (
            margem_porta
            / comp
        )

        cortes.append(
            (
                max(
                    0.0,
                    a - folga_t
                ),
                min(
                    1.0,
                    b + folga_t
                )
            )
        )

    cortes = _mesclar_intervalos(
        cortes
    )

    livres = []
    cursor = 0.0

    for ini, fim in cortes:
        if ini > cursor:
            livres.append(
                (
                    cursor,
                    ini
                )
            )

        cursor = max(
            cursor,
            fim
        )

    if cursor < 1.0:
        livres.append(
            (
                cursor,
                1.0
            )
        )

    if not cortes:
        livres = [
            (
                0.0,
                1.0
            )
        ]

    comp_parede = max(
        float(
            parede[
                "comprimento"
            ]
        ),
        1e-9
    )

    livres_validos = [
        (
            a,
            b
        )
        for a, b in livres
        if (
            b - a
        ) * comp_parede
        >= comprimento_minimo
    ]

    if not livres_validos:
        livres_validos = [
            (
                0.0,
                1.0
            )
        ]

    saida = []

    x1, y1 = parede[
        "p1"
    ]
    x2, y2 = parede[
        "p2"
    ]

    total = len(
        livres_validos
    )

    for indice, (
        t0,
        t1
    ) in enumerate(
        livres_validos,
        start=1
    ):
        p0 = (
            x1
            + (
                x2 - x1
            ) * t0,
            y1
            + (
                y2 - y1
            ) * t0
        )

        p1 = (
            x1
            + (
                x2 - x1
            ) * t1,
            y1
            + (
                y2 - y1
            ) * t1
        )

        letra = chr(
            ord("A")
            + indice - 1
        )

        numero = parede[
            "numero"
        ]

        rotulo = (
            f"Parede {numero}"
            if total == 1
            else (
                f"Parede "
                f"{numero}{letra}"
            )
        )

        comprimento = math.hypot(
            p1[0] - p0[0],
            p1[1] - p0[1]
        )

        saida.append({
            "id":
                (
                    f"P{numero}"
                    f"_T{indice}"
                ),
            "parede_numero":
                numero,
            "trecho_numero":
                indice,
            "rotulo":
                rotulo,
            "t0":
                float(
                    t0
                ),
            "t1":
                float(
                    t1
                ),
            "p1":
                p0,
            "p2":
                p1,
            "comprimento":
                comprimento
        })

    return saida


def _todos_trechos_qdc(
    paredes,
    portas
):
    saida = []

    for parede in paredes:
        saida.extend(
            _trechos_parede_qdc(
                parede,
                portas
            )
        )

    return saida


def _figura_paredes_qdc(
    nome,
    poly,
    paredes,
    selecionada=None,
    portas=None,
    geometrias_portas=None,
    trechos=None
):
    xs = [
        float(p[0])
        for p in poly
    ]
    ys = [
        float(p[1])
        for p in poly
    ]

    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)

    largura_real = max(
        max_x - min_x,
        0.01
    )
    altura_real = max(
        max_y - min_y,
        0.01
    )

    largura_grafico = 430
    altura_grafico = 330
    margem = 0.10

    fator = min(
        (
            largura_grafico
            * (1 - 2 * margem)
        )
        / largura_real,
        (
            altura_grafico
            * (1 - 2 * margem)
        )
        / altura_real
    )

    cx_real = (
        min_x + max_x
    ) / 2.0
    cy_real = (
        min_y + max_y
    ) / 2.0

    cx_canvas = (
        largura_grafico / 2.0
    )
    cy_canvas = (
        altura_grafico / 2.0
    )

    def tr(p):
        return (
            cx_canvas
            + (
                float(p[0])
                - cx_real
            ) * fator,
            cy_canvas
            + (
                float(p[1])
                - cy_real
            ) * fator
        )

    contorno = []

    for ordem, p in enumerate(
        list(poly)
        + [poly[0]]
    ):
        x, y = tr(p)

        contorno.append({
            "x": x,
            "y": y,
            "ordem": ordem
        })

    # Fase 8.2: mesmas portas da mini planta dos interruptores.
    dados_portas = []

    for indice, porta in enumerate(portas or []):
        visual = _geometria_visual_porta_por_soleira(
            porta, poly, geometrias_portas or []
        )
        if visual is None:
            continue
        for tipo_visual in ("folha", "arco"):
            pontos = visual.get(tipo_visual) or []
            grupo = f"QDC_PORTA_{indice}_{tipo_visual.upper()}"
            for ordem, ponto in enumerate(pontos):
                x, y = tr(ponto)
                dados_portas.append({
                    "grupo": grupo, "ordem": ordem, "x": x, "y": y
                })

    dados_paredes = []
    marcadores = []

    trechos = (
        trechos
        if trechos is not None
        else _todos_trechos_qdc(
            paredes,
            portas or []
        )
    )

    for trecho in trechos:
        trecho_id = trecho[
            "id"
        ]

        p1 = tr(
            trecho["p1"]
        )
        p2 = tr(
            trecho["p2"]
        )

        escolhida = (
            trecho_id
            == selecionada
        )

        for ordem, p in enumerate(
            [
                p1,
                p2
            ]
        ):
            dados_paredes.append({
                "parede_id":
                    trecho_id,
                "rotulo":
                    trecho[
                        "rotulo"
                    ],
                "ordem":
                    ordem,
                "x":
                    p[0],
                "y":
                    p[1],
                "selecionada":
                    (
                        "SIM"
                        if escolhida
                        else "NAO"
                    )
            })

        marcadores.append({
            "parede_id":
                trecho_id,
            "rotulo":
                trecho[
                    "rotulo"
                ],
            "x":
                (
                    p1[0]
                    + p2[0]
                ) / 2.0,
            "y":
                (
                    p1[1]
                    + p2[1]
                ) / 2.0,
            "selecionada":
                (
                    "SIM"
                    if escolhida
                    else "NAO"
                )
        })

    sx = {
        "domain": [
            0,
            largura_grafico
        ],
        "nice": False,
        "zero": False
    }

    sy = {
        "domain": [
            0,
            altura_grafico
        ],
        "nice": False,
        "zero": False
    }

    return {
        "$schema":
            (
                "https://vega.github.io/"
                "schema/vega-lite/v5.json"
            ),
        "width":
            largura_grafico,
        "height":
            altura_grafico,
        "background":
            "#ffffff",
        "config": {
            "view": {
                "stroke":
                    "#e5e7eb"
            },
            "axis": {
                "grid":
                    False
            }
        },
        "layer": [
            {
                "data": {
                    "values":
                        contorno
                },
                "mark": {
                    "type":
                        "line",
                    "stroke":
                        "#111827",
                    "strokeWidth":
                        7
                },
                "encoding": {
                    "x": {
                        "field":
                            "x",
                        "type":
                            "quantitative",
                        "axis": None,
                        "scale": sx
                    },
                    "y": {
                        "field":
                            "y",
                        "type":
                            "quantitative",
                        "axis": None,
                        "scale": sy
                    },
                    "order": {
                        "field":
                            "ordem"
                    }
                }
            },
            {
                "data": {
                    "values":
                        contorno
                },
                "mark": {
                    "type":
                        "line",
                    "stroke":
                        "#ffffff",
                    "strokeWidth":
                        3
                },
                "encoding": {
                    "x": {
                        "field":
                            "x",
                        "type":
                            "quantitative",
                        "axis": None,
                        "scale": sx
                    },
                    "y": {
                        "field":
                            "y",
                        "type":
                            "quantitative",
                        "axis": None,
                        "scale": sy
                    },
                    "order": {
                        "field":
                            "ordem"
                    }
                }
            },
            {
                "data": {
                    "values":
                        dados_portas
                },
                "mark": {
                    "type": "line",
                    "stroke": "#111827",
                    "strokeWidth": 2.2
                },
                "encoding": {
                    "x": {"field":"x","type":"quantitative","axis":None,"scale":sx},
                    "y": {"field":"y","type":"quantitative","axis":None,"scale":sy},
                    "detail": {"field":"grupo"},
                    "order": {"field":"ordem"}
                }
            },
            {
                "data": {
                    "values":
                        dados_paredes
                },
                # Mesma estratégia estável usada nas mini plantas
                # dos interruptores: o parâmetro fica DENTRO da layer.
                "params": [
                    {
                        "name":
                            "parede",
                        "select": {
                            "type":
                                "point",
                            "fields": [
                                "parede_id"
                            ],
                            "on":
                                "click",
                            "toggle":
                                "false",
                            "clear":
                                False
                        }
                    }
                ],
                "mark": {
                    "type":
                        "line",
                    "strokeWidth":
                        14,
                    "opacity":
                        0.40
                },
                "encoding": {
                    "x": {
                        "field":
                            "x",
                        "type":
                            "quantitative",
                        "axis": None,
                        "scale": sx
                    },
                    "y": {
                        "field":
                            "y",
                        "type":
                            "quantitative",
                        "axis": None,
                        "scale": sy
                    },
                    "detail": {
                        "field":
                            "parede_id"
                    },
                    "order": {
                        "field":
                            "ordem"
                    },
                    "color": {
                        "condition": [
                            
                            {
                                "test":
                                    (
                                        "datum."
                                        "selecionada "
                                        "=== 'SIM'"
                                    ),
                                "value":
                                    "#16a34a"
                            }
                        ],
                        "value":
                            "#2563eb"
                    },
                    "tooltip": [
                        {
                            "field":
                                "rotulo",
                            "title":
                                "QDC"
                        }
                    ]
                }
            },
            {
                "data": {
                    "values":
                        marcadores
                },
                "mark": {
                    "type":
                        "point",
                    "filled":
                        True,
                    "size":
                        280,
                    "stroke":
                        "#ffffff",
                    "strokeWidth":
                        2
                },
                "encoding": {
                    "x": {
                        "field":
                            "x",
                        "type":
                            "quantitative",
                        "axis": None,
                        "scale": sx
                    },
                    "y": {
                        "field":
                            "y",
                        "type":
                            "quantitative",
                        "axis": None,
                        "scale": sy
                    },
                    "color": {
                        "condition": [
                            
                            {
                                "test":
                                    (
                                        "datum."
                                        "selecionada "
                                        "=== 'SIM'"
                                    ),
                                "value":
                                    "#16a34a"
                            }
                        ],
                        "value":
                            "#2563eb"
                    },
                    "tooltip": [
                        {
                            "field":
                                "rotulo",
                            "title":
                                "Clique para selecionar"
                        }
                    ]
                }
            },
            {
                "data": {
                    "values":
                        marcadores
                },
                "mark": {
                    "type":
                        "text",
                    "dy":
                        -17,
                    "fontSize":
                        11,
                    "fontWeight":
                        "bold"
                },
                "encoding": {
                    "x": {
                        "field":
                            "x",
                        "type":
                            "quantitative",
                        "axis": None,
                        "scale": sx
                    },
                    "y": {
                        "field":
                            "y",
                        "type":
                            "quantitative",
                        "axis": None,
                        "scale": sy
                    },
                    "text": {
                        "field":
                            "rotulo"
                    }
                }
            },
            {
                "data": {
                    "values": [
                        {
                            "x":
                                cx_canvas,
                            "y":
                                cy_canvas,
                            "nome":
                                nome
                        }
                    ]
                },
                "mark": {
                    "type":
                        "text",
                    "fontSize":
                        17,
                    "fontWeight":
                        "bold",
                    "opacity":
                        0.35
                },
                "encoding": {
                    "x": {
                        "field":
                            "x",
                        "type":
                            "quantitative",
                        "axis": None,
                        "scale": sx
                    },
                    "y": {
                        "field":
                            "y",
                        "type":
                            "quantitative",
                        "axis": None,
                        "scale": sy
                    },
                    "text": {
                        "field":
                            "nome"
                    }
                }
            }
        ]
    }



def _extrair_parede_evento(
    evento,
    ids_validos
):
    try:
        sel = (
            evento
            .selection
            .parede
        )
    except Exception:
        try:
            sel = (
                evento[
                    "selection"
                ][
                    "parede"
                ]
            )
        except Exception:
            sel = None

    if sel is None:
        return (
            False,
            None
        )

    if hasattr(
        sel,
        "to_dict"
    ):
        try:
            sel = sel.to_dict()
        except Exception:
            pass

    brutos = []
    recebeu = False

    if isinstance(
        sel,
        dict
    ):
        if "parede_id" in sel:
            bruto = sel.get(
                "parede_id"
            )

            if isinstance(
                bruto,
                (list, tuple)
            ):
                brutos.extend(
                    bruto
                )
            elif bruto is not None:
                brutos.append(
                    bruto
                )

            recebeu = True

        elif "values" in sel:
            for item in (
                sel.get(
                    "values"
                )
                or []
            ):
                if isinstance(
                    item,
                    dict
                ):
                    pid = item.get(
                        "parede_id"
                    )

                    if pid is not None:
                        brutos.append(
                            pid
                        )

            recebeu = True

    elif isinstance(
        sel,
        (list, tuple)
    ):
        for item in sel:
            if isinstance(
                item,
                dict
            ):
                pid = item.get(
                    "parede_id"
                )

                if pid is not None:
                    brutos.append(
                        pid
                    )
            else:
                brutos.append(
                    item
                )

        recebeu = True

    elif isinstance(
        sel,
        str
    ):
        brutos.append(
            sel
        )
        recebeu = True

    if not recebeu:
        return (
            False,
            None
        )

    for bruto in reversed(
        brutos
    ):
        texto = str(
            bruto
        ).strip()

        if texto in ids_validos:
            return (
                True,
                texto
            )

    return (
        True,
        None
    )


def renderizar_qdc(
    dados_ambientes,
    local_qdc_salvo=None,
    dxf_bytes=None
):
    st.divider()

    validos = []
    recomendados = []

    for r in dados_ambientes:
        nome = r[
            "Ambiente"
        ]

        # Fase 8.2:
        # filtro normalizado. Ex.: W.C. -> wc e A.S. -> as.
        if _ambiente_molhado_qdc(
            nome
        ):
            continue

        circulacao = (
            _ambiente_circulacao_qdc(
                nome
            )
        )

        if circulacao:
            recomendados.append(
                f"{nome} (Recomendado)"
            )
        else:
            validos.append(
                nome
            )

    opcoes = (
        recomendados
        + validos
    )

    if not opcoes:
        opcoes = [
            r["Ambiente"]
            for r in dados_ambientes
        ]

    dados_qdc_salvos = (
        decodificar_qdc_completo(
            local_qdc_salvo
        )
    )

    ambiente_salvo = (
        dados_qdc_salvos[
            "ambiente"
        ]
    )

    parede_salva = (
        dados_qdc_salvos[
            "parede_numero"
        ]
    )

    trecho_salvo = (
        dados_qdc_salvos[
            "trecho_numero"
        ]
    )

    indice = 0

    for n, opcao in enumerate(
        opcoes
    ):
        base = (
            opcao
            .split(
                " (Recomendado"
            )[0]
            .strip()
        )

        if (
            ambiente_salvo
            and base.casefold()
            == ambiente_salvo.casefold()
        ):
            indice = n
            break

    escolha = st.selectbox(
        "Selecione o ambiente onde ficará "
        "instalado o QDC:",
        opcoes,
        index=indice,
        key="fase8_0_select_qdc"
    )

    ambiente = (
        escolha
        .split(
            " (Recomendado"
        )[0]
        .strip()
    )

    if not dxf_bytes:
        return codificar_qdc(
            ambiente,
            parede_salva
        )

    analise = (
        _ambientes_do_dxf(
            dxf_bytes
        )
    )

    analise_portas = analisar_portas_dxf(
        dxf_bytes
    )

    item = analise.get(
        ambiente
    )

    item_portas = (
        analise_portas.get(ambiente)
        or {}
    )

    if not item:
        st.info(
            "Não foi possível localizar a geometria "
            "desse ambiente no DXF."
        )
        return codificar_qdc(
            ambiente,
            parede_salva
        )

    paredes = item[
        "paredes"
    ]

    portas_ambiente = (
        item_portas.get(
            "portas",
            []
        )
    )

    trechos = _todos_trechos_qdc(
        paredes,
        portas_ambiente
    )

    chave = (
        "fase8_0_qdc_parede_"
        + ambiente
    )

    if chave not in st.session_state:
        id_salvo = None

        if (
            ambiente_salvo
            and ambiente.casefold()
            == ambiente_salvo.casefold()
            and parede_salva is not None
        ):
            if trecho_salvo is not None:
                candidato = (
                    f"P{parede_salva}"
                    f"_T{trecho_salvo}"
                )

                if any(
                    t["id"]
                    == candidato
                    for t in trechos
                ):
                    id_salvo = (
                        candidato
                    )

            if id_salvo is None:
                candidatos = [
                    t
                    for t in trechos
                    if t[
                        "parede_numero"
                    ]
                    == parede_salva
                ]

                if candidatos:
                    id_salvo = (
                        candidatos[0][
                            "id"
                        ]
                    )

        st.session_state[
            chave
        ] = id_salvo

    selecionada = (
        st.session_state[
            chave
        ]
    )

    st.caption(
        "📍 Clique no trecho da parede onde o QDC será instalado. "
        "Se uma porta dividir a parede, os lados ficam independentes. "
        "🔵 disponível | 🟢 selecionado"
    )

    st.markdown(
        f"**Mini planta — {ambiente}**"
    )

    fig = _figura_paredes_qdc(
        ambiente,
        item["poly"],
        paredes,
        selecionada,
        portas=
            portas_ambiente,
        geometrias_portas=
            item_portas.get(
                "geometrias_portas",
                []
            ),
        trechos=
            trechos
    )

    evento = st.vega_lite_chart(
        fig,
        use_container_width=False,
        key=(
            "fase8_0_qdc_grafico_"
            + ambiente
        ),
        on_select="rerun"
    )

    ids_validos = {
        t["id"]
        for t in trechos
    }

    recebeu, nova = _extrair_parede_evento(
        evento,
        ids_validos
    )

    if recebeu and nova is not None and nova != selecionada:
        st.session_state[chave] = nova
        st.rerun()

    selecionada = (
        st.session_state[
            chave
        ]
    )

    if selecionada is None:
        st.warning(
            "Selecione um trecho de parede para definir "
            "a posição do QDC."
        )

        return codificar_qdc(
            ambiente,
            None
        )

    trecho_escolhido = next(
        (
            t
            for t in trechos
            if t["id"]
            == selecionada
        ),
        None
    )

    if trecho_escolhido is None:
        st.warning(
            "O trecho anteriormente selecionado não existe "
            "mais nesta geometria."
        )

        return codificar_qdc(
            ambiente,
            None
        )

    st.success(
        f"QDC: {ambiente} — "
        f"{trecho_escolhido['rotulo']}."
    )

    return codificar_qdc(
        ambiente,
        trecho_escolhido[
            "parede_numero"
        ],
        trecho_numero=
            trecho_escolhido[
                "trecho_numero"
            ],
        t0=
            trecho_escolhido[
                "t0"
            ],
        t1=
            trecho_escolhido[
                "t1"
            ]
    )
