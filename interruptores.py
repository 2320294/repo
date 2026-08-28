
import os
import tempfile

import ezdxf
import streamlit as st

from dxf_io import ler_elementos
from portas_selecao import portas_do_ambiente


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


def analisar_portas_dxf(dxf_bytes):
    """
    Retorna:
      {
        ambiente: {
          "poly": [...],
          "portas": [
             {"id", "numero", "rotulo", "centro", "soleira"}
          ]
        }
      }
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

        doc = ezdxf.readfile(caminho)
        elementos = ler_elementos(doc.modelspace())

        ambientes = _ambientes_geometricos(
            elementos["polilinhas"],
            elementos["textos"]
        )

        saida = {}

        for nome, poly in ambientes.items():
            saida[nome] = {
                "poly": poly,
                "portas": portas_do_ambiente(
                    nome,
                    poly,
                    elementos["soleiras_raw"]
                )
            }

        return saida

    finally:
        if caminho and os.path.exists(caminho):
            os.remove(caminho)




def _figura_ambiente(nome, poly, portas, selecionadas):
    """
    Retorna uma especificação Vega-Lite pura.
    Não depende de Plotly nem de Altair importado.
    """

    contorno = []
    pontos_contorno = list(poly) + [poly[0]]

    for ordem, p in enumerate(pontos_contorno):
        contorno.append({
            "x": float(p[0]),
            "y": float(p[1]),
            "ordem": ordem
        })

    dados_portas = []

    for porta in portas:
        selecionada = (
            porta["id"] in selecionadas
        )

        dados_portas.append({
            "x": float(porta["centro"][0]),
            "y": float(porta["centro"][1]),
            "porta_id": porta["id"],
            "rotulo": porta["rotulo"],
            "estado": (
                "Selecionada"
                if selecionada
                else "Não selecionada"
            ),
            "tamanho": (
                420
                if selecionada
                else 250
            ),
            "forma": (
                "diamond"
                if selecionada
                else "circle"
            )
        })

    return {
        "$schema": (
            "https://vega.github.io/schema/"
            "vega-lite/v5.json"
        ),
        "title": (
            f"Selecione as portas — {nome}"
        ),
        "height": 400,
        "autosize": {
            "type": "fit",
            "contains": "padding"
        },
        "config": {
            "view": {
                "stroke": None
            },
            "axis": {
                "grid": False
            }
        },
        "layer": [
            {
                "data": {
                    "values": contorno
                },
                "mark": {
                    "type": "line",
                    "strokeWidth": 3
                },
                "encoding": {
                    "x": {
                        "field": "x",
                        "type": "quantitative",
                        "axis": None
                    },
                    "y": {
                        "field": "y",
                        "type": "quantitative",
                        "axis": None
                    },
                    "order": {
                        "field": "ordem",
                        "type": "quantitative"
                    }
                }
            },
            {
                "data": {
                    "values": dados_portas
                },
                "params": [
                    {
                        "name": "porta",
                        "select": {
                            "type": "point",
                            "fields": [
                                "porta_id"
                            ],
                            "on": "click",
                            "clear": False
                        }
                    }
                ],
                "mark": {
                    "type": "point",
                    "filled": True,
                    "strokeWidth": 2
                },
                "encoding": {
                    "x": {
                        "field": "x",
                        "type": "quantitative",
                        "axis": None
                    },
                    "y": {
                        "field": "y",
                        "type": "quantitative",
                        "axis": None
                    },
                    "size": {
                        "field": "tamanho",
                        "type": "quantitative",
                        "scale": None,
                        "legend": None
                    },
                    "shape": {
                        "field": "forma",
                        "type": "nominal",
                        "scale": None,
                        "legend": None
                    },
                    "opacity": {
                        "condition": {
                            "test": (
                                "datum.estado === "
                                "'Selecionada'"
                            ),
                            "value": 1.0
                        },
                        "value": 0.55
                    },
                    "tooltip": [
                        {
                            "field": "rotulo",
                            "type": "nominal",
                            "title": "Porta"
                        },
                        {
                            "field": "estado",
                            "type": "nominal",
                            "title": "Estado"
                        }
                    ]
                }
            },
            {
                "data": {
                    "values": dados_portas
                },
                "mark": {
                    "type": "text",
                    "dy": -18,
                    "fontSize": 13,
                    "fontWeight": "bold"
                },
                "encoding": {
                    "x": {
                        "field": "x",
                        "type": "quantitative",
                        "axis": None
                    },
                    "y": {
                        "field": "y",
                        "type": "quantitative",
                        "axis": None
                    },
                    "text": {
                        "field": "rotulo",
                        "type": "nominal"
                    }
                }
            }
        ]
    }

def _ids_salvos_ambiente(config_salva, amb, portas):
    ids_validos = {p["id"] for p in portas}

    cfg = (
        config_salva.get(amb, {})
        if isinstance(config_salva, dict)
        else {}
    )

    if not isinstance(cfg, dict):
        cfg = {}

    salvos = cfg.get("portas_ids", [])
    if isinstance(salvos, list):
        filtrados = [
            pid for pid in salvos
            if pid in ids_validos
        ]
        if filtrados:
            return filtrados

    # Compatibilidade com configurações das fases anteriores:
    # se só havia quantidade, seleciona determinísticamente as primeiras.
    qtd_antiga = max(
        0,
        min(
            len(portas),
            int(cfg.get("quantidade", 0))
        )
    )

    return [
        p["id"]
        for p in portas[:qtd_antiga]
    ]


def renderizar_interruptores(
    dados_ambientes,
    config_salva,
    dxf_bytes=None
):
    st.divider()
    st.subheader("⚙️ Configuração de Interruptores")

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
        "Nos ambientes abaixo, escolha **diretamente na mini planta** "
        "quais portas receberão interruptores. "
        "Clique em uma porta para selecionar ou retirar a seleção."
    )

    for amb in multiplos:
        portas = analise[amb]["portas"]
        poly = analise[amb]["poly"]

        chave_estado = f"portas_interruptor_selecionadas_{amb}"

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
                "● círculo = não selecionada   |   "
                "◆ losango = selecionada"
            )

            fig = _figura_ambiente(
                amb,
                poly,
                portas,
                selecionadas
            )

            evento = st.vega_lite_chart(
                fig,
                use_container_width=True,
                key=f"planta_portas_{amb}",
                on_select="rerun"
            )

            # Streamlit retorna os valores selecionados pelo Vega-Lite.
            # Usamos o ID geométrico da porta para alternar a seleção.
            ids_evento = []

            try:
                ids_evento = (
                    evento.selection.porta.get(
                        "porta_id",
                        []
                    )
                )
            except Exception:
                try:
                    ids_evento = (
                        evento["selection"]
                        ["porta"]
                        .get("porta_id", [])
                    )
                except Exception:
                    ids_evento = []

            if isinstance(ids_evento, str):
                ids_evento = [ids_evento]

            if ids_evento:
                pid = ids_evento[-1]

                chave_ultimo = (
                    f"ultima_porta_evento_{amb}"
                )

                if (
                    pid in ids_validos
                    and st.session_state.get(
                        chave_ultimo
                    ) != pid
                ):
                    atual = list(
                        st.session_state[
                            chave_estado
                        ]
                    )

                    if pid in atual:
                        atual.remove(pid)
                    else:
                        atual.append(pid)

                    st.session_state[
                        chave_estado
                    ] = atual

                    st.session_state[
                        chave_ultimo
                    ] = pid

                    st.rerun()

            # Alternativa acessível/precisa abaixo do desenho.
            opcoes = {
                p["rotulo"]: p["id"]
                for p in portas
            }
            rotulos_selecionados = [
                p["rotulo"]
                for p in portas
                if p["id"] in selecionadas
            ]

            escolhidas_lista = st.multiselect(
                "Portas selecionadas:",
                options=list(opcoes.keys()),
                default=rotulos_selecionados,
                key=f"lista_portas_{amb}",
                help=(
                    "Você pode clicar na mini planta ou "
                    "usar esta lista. As duas formas representam "
                    "a mesma seleção."
                )
            )

            ids_lista = [
                opcoes[rotulo]
                for rotulo in escolhidas_lista
            ]

            if set(ids_lista) != set(selecionadas):
                st.session_state[chave_estado] = ids_lista
                selecionadas = ids_lista

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
