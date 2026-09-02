import os
import tempfile
import unicodedata

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
    decodificar_qdc
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

        elementos = ler_elementos(
            doc.modelspace()
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
                    paredes
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


def _figura_paredes_qdc(
    nome,
    poly,
    paredes,
    selecionada=None
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

    dados_paredes = []
    marcadores = []

    for parede in paredes:
        numero = parede[
            "numero"
        ]

        p1 = tr(
            parede["p1"]
        )
        p2 = tr(
            parede["p2"]
        )

        escolhida = (
            numero
            == selecionada
        )

        for ordem, p in enumerate(
            [p1, p2]
        ):
            dados_paredes.append({
                "parede_id":
                    numero,
                "rotulo":
                    f"Parede {numero}",
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
                numero,
            "rotulo":
                f"Parede {numero}",
            "x":
                (
                    p1[0] + p2[0]
                ) / 2.0,
            "y":
                (
                    p1[1] + p2[1]
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
                                "param":
                                    "parede",
                                "value":
                                    "#16a34a"
                            },
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
                                "param":
                                    "parede",
                                "value":
                                    "#16a34a"
                            },
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

        # Fase 7.7:
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

    ambiente_salvo, parede_salva = (
        decodificar_qdc(
            local_qdc_salvo
        )
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
        "⚡ Selecione o ambiente onde ficará "
        "instalado o QDC:",
        opcoes,
        index=indice,
        key="fase7_7_select_qdc"
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

    item = analise.get(
        ambiente
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

    chave = (
        "fase7_7_qdc_parede_"
        + ambiente
    )

    if chave not in st.session_state:
        st.session_state[
            chave
        ] = (
            parede_salva
            if (
                ambiente_salvo
                and ambiente.casefold()
                == ambiente_salvo.casefold()
                and any(
                    p["numero"]
                    == parede_salva
                    for p in paredes
                )
            )
            else None
        )

    selecionada = (
        st.session_state[
            chave
        ]
    )

    st.caption(
        "📍 Clique na parede onde o QDC será instalado. "
        "🔵 disponível | 🟢 selecionada"
    )

    st.markdown(
        f"**Mini planta — {ambiente}**"
    )

    fig = _figura_paredes_qdc(
        ambiente,
        item["poly"],
        paredes,
        selecionada
    )

    evento = st.vega_lite_chart(
        fig,
        use_container_width=False,
        key=(
            "fase7_7_qdc_grafico_"
            + ambiente
        ),
        on_select="rerun"
    )

    ids = []
    recebeu = False

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
            if "parede_id" in sel:
                bruto = (
                    sel.get(
                        "parede_id"
                    )
                )

                if isinstance(
                    bruto,
                    (list, tuple)
                ):
                    ids = list(
                        bruto
                    )
                elif bruto is not None:
                    ids = [
                        bruto
                    ]

                recebeu = True

            elif "values" in sel:
                for dado in (
                    sel.get(
                        "values"
                    )
                    or []
                ):
                    if isinstance(
                        dado,
                        dict
                    ):
                        pid = dado.get(
                            "parede_id"
                        )

                        if pid is not None:
                            ids.append(
                                pid
                            )

                recebeu = True

    if (
        recebeu
        and ids
    ):
        try:
            nova = int(
                ids[-1]
            )
        except Exception:
            nova = None

        if (
            nova is not None
            and nova != selecionada
        ):
            st.session_state[
                chave
            ] = nova

            st.rerun()

    selecionada = (
        st.session_state[
            chave
        ]
    )

    if selecionada is None:
        st.warning(
            "Selecione uma parede para definir "
            "a posição do QDC."
        )
    else:
        st.success(
            f"QDC: {ambiente} — "
            f"Parede {selecionada}."
        )

    return codificar_qdc(
        ambiente,
        selecionada
    )
