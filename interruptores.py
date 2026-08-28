
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
    Fase 5.8:
    - mostra o ambiente inteiro;
    - mantém a proporção geométrica aproximada;
    - desenha todas as soleiras/portas;
    - identifica Porta 1, Porta 2...;
    - permite clicar diretamente nos marcadores.
    """
    if not poly:
        return {}

    xs_poly = [float(p[0]) for p in poly]
    ys_poly = [float(p[1]) for p in poly]

    # Inclui também as soleiras nos limites visuais.
    xs_todos = list(xs_poly)
    ys_todos = list(ys_poly)

    for porta in portas:
        for p in (porta["soleira"].get("vertices") or []):
            xs_todos.append(float(p[0]))
            ys_todos.append(float(p[1]))

    min_x = min(xs_todos)
    max_x = max(xs_todos)
    min_y = min(ys_todos)
    max_y = max(ys_todos)

    largura = max(max_x - min_x, 0.50)
    altura = max(max_y - min_y, 0.50)

    # Margem de 12% para não cortar números/marcadores.
    margem_x = max(largura * 0.12, 0.20)
    margem_y = max(altura * 0.12, 0.20)

    dominio_x = [
        min_x - margem_x,
        max_x + margem_x
    ]
    dominio_y = [
        min_y - margem_y,
        max_y + margem_y
    ]

    # Mantém o aspecto visual do ambiente.
    proporcao = largura / altura
    largura_grafico = 720

    if proporcao >= 1:
        altura_grafico = int(
            max(
                320,
                min(
                    560,
                    largura_grafico / max(proporcao, 0.01)
                )
            )
        )
    else:
        altura_grafico = 520
        largura_grafico = int(
            max(
                420,
                min(
                    720,
                    altura_grafico * proporcao
                )
            )
        )

    # -------------------------------------------------------------
    # CONTORNO COMPLETO DO AMBIENTE
    # -------------------------------------------------------------
    contorno = []
    pontos_contorno = list(poly) + [poly[0]]

    for ordem, p in enumerate(pontos_contorno):
        contorno.append({
            "x": float(p[0]),
            "y": float(p[1]),
            "ordem": ordem
        })

    # -------------------------------------------------------------
    # SOLEIRAS / PORTAS
    # -------------------------------------------------------------
    segmentos_portas = []

    for porta in portas:
        verts = list(
            porta["soleira"].get("vertices")
            or []
        )

        if len(verts) < 2:
            continue

        verts_fechados = verts + [verts[0]]

        for ordem, p in enumerate(verts_fechados):
            segmentos_portas.append({
                "porta_id": porta["id"],
                "x": float(p[0]),
                "y": float(p[1]),
                "ordem": ordem,
                "selecionada": (
                    "SIM"
                    if porta["id"] in selecionadas
                    else "NAO"
                )
            })

    # -------------------------------------------------------------
    # MARCADORES CLICÁVEIS
    # -------------------------------------------------------------
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
                else "Clique para selecionar"
            ),
            "selecionada": (
                "SIM"
                if selecionada
                else "NAO"
            ),
            "tamanho": (
                650
                if selecionada
                else 450
            )
        })

    escala_x = {
        "domain": dominio_x,
        "nice": False,
        "zero": False
    }

    escala_y = {
        "domain": dominio_y,
        "nice": False,
        "zero": False
    }

    return {
        "$schema": (
            "https://vega.github.io/schema/"
            "vega-lite/v5.json"
        ),
        "title": {
            "text": f"{nome} — clique nas portas que terão interruptor",
            "anchor": "middle",
            "fontSize": 16
        },
        "width": largura_grafico,
        "height": altura_grafico,
        "autosize": {
            "type": "fit",
            "contains": "padding",
            "resize": True
        },
        "padding": {
            "left": 15,
            "right": 15,
            "top": 15,
            "bottom": 15
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
            # Contorno do ambiente
            {
                "data": {
                    "values": contorno
                },
                "mark": {
                    "type": "line",
                    "stroke": "#1f2937",
                    "strokeWidth": 4
                },
                "encoding": {
                    "x": {
                        "field": "x",
                        "type": "quantitative",
                        "axis": None,
                        "scale": escala_x
                    },
                    "y": {
                        "field": "y",
                        "type": "quantitative",
                        "axis": None,
                        "scale": escala_y
                    },
                    "order": {
                        "field": "ordem",
                        "type": "quantitative"
                    }
                }
            },

            # Soleiras / portas
            {
                "data": {
                    "values": segmentos_portas
                },
                "mark": {
                    "type": "line",
                    "strokeWidth": 7
                },
                "encoding": {
                    "x": {
                        "field": "x",
                        "type": "quantitative",
                        "axis": None,
                        "scale": escala_x
                    },
                    "y": {
                        "field": "y",
                        "type": "quantitative",
                        "axis": None,
                        "scale": escala_y
                    },
                    "detail": {
                        "field": "porta_id",
                        "type": "nominal"
                    },
                    "order": {
                        "field": "ordem",
                        "type": "quantitative"
                    },
                    "color": {
                        "condition": {
                            "test": (
                                "datum.selecionada === 'SIM'"
                            ),
                            "value": "#16a34a"
                        },
                        "value": "#dc2626"
                    }
                }
            },

            # Seleção clicável
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
                    "stroke": "#111827",
                    "strokeWidth": 2
                },
                "encoding": {
                    "x": {
                        "field": "x",
                        "type": "quantitative",
                        "axis": None,
                        "scale": escala_x
                    },
                    "y": {
                        "field": "y",
                        "type": "quantitative",
                        "axis": None,
                        "scale": escala_y
                    },
                    "size": {
                        "field": "tamanho",
                        "type": "quantitative",
                        "scale": None,
                        "legend": None
                    },
                    "shape": {
                        "condition": {
                            "test": (
                                "datum.selecionada === 'SIM'"
                            ),
                            "value": "diamond"
                        },
                        "value": "circle"
                    },
                    "color": {
                        "condition": {
                            "test": (
                                "datum.selecionada === 'SIM'"
                            ),
                            "value": "#16a34a"
                        },
                        "value": "#ef4444"
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
                            "title": "Interruptor"
                        }
                    ]
                }
            },

            # Números das portas
            {
                "data": {
                    "values": dados_portas
                },
                "mark": {
                    "type": "text",
                    "dy": -24,
                    "fontSize": 15,
                    "fontWeight": "bold",
                    "color": "#111827"
                },
                "encoding": {
                    "x": {
                        "field": "x",
                        "type": "quantitative",
                        "axis": None,
                        "scale": escala_x
                    },
                    "y": {
                        "field": "y",
                        "type": "quantitative",
                        "axis": None,
                        "scale": escala_y
                    },
                    "text": {
                        "field": "rotulo",
                        "type": "nominal"
                    }
                }
            },

            # Nome do ambiente no centro visual
            {
                "data": {
                    "values": [{
                        "x": (
                            min(xs_poly)
                            + max(xs_poly)
                        ) / 2.0,
                        "y": (
                            min(ys_poly)
                            + max(ys_poly)
                        ) / 2.0,
                        "nome": nome
                    }]
                },
                "mark": {
                    "type": "text",
                    "fontSize": 22,
                    "fontWeight": "bold",
                    "opacity": 0.25
                },
                "encoding": {
                    "x": {
                        "field": "x",
                        "type": "quantitative",
                        "axis": None,
                        "scale": escala_x
                    },
                    "y": {
                        "field": "y",
                        "type": "quantitative",
                        "axis": None,
                        "scale": escala_y
                    },
                    "text": {
                        "field": "nome",
                        "type": "nominal"
                    }
                }
            }
        ]
    }


def _ids_salvos_ambiente(config_salva, amb, portas):
    """
    Fase 5.8:
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

        chave_estado = f"fase5_8_portas_interruptor_selecionadas_{amb}"

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
                "🔴 Vermelho = sem interruptor   |   "
                "🟢 Verde = porta selecionada para interruptor"
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
                key=f"fase5_8_planta_portas_{amb}",
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
                    f"fase5_8_ultima_porta_evento_{amb}"
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
                key=f"fase5_8_lista_portas_{amb}",
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
