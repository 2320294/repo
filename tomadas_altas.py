
import streamlit as st

from qdc import (
    _ambientes_do_dxf,
    _figura_paredes_qdc,
    _extrair_parede_evento,
    _todos_trechos_qdc
)
from interruptores import (
    analisar_portas_dxf
)


CHAVE_CONFIG = "__tomadas_altas__"


def _eh_tomada_alta(
    row
):
    eq = str(
        row.get(
            "Equipamento TUE",
            ""
        )
    ).casefold()

    qtd = int(
        row.get(
            "Qtd TUE",
            row.get(
                "TUE",
                0
            )
        )
        or 0
    )

    alta = any(
        termo in eq
        for termo in [
            "chuveiro",
            "ar-condicionado",
            "ar condicionado"
        ]
    )

    return (
        qtd > 0
        and alta
    )


def _config_salva_altas(
    config_salva
):
    if not isinstance(
        config_salva,
        dict
    ):
        return {}

    cfg = config_salva.get(
        CHAVE_CONFIG,
        {}
    )

    return (
        cfg
        if isinstance(
            cfg,
            dict
        )
        else {}
    )



def _eh_chuveiro(
    equipamento
):
    return (
        "chuveiro"
        in str(
            equipamento
        ).casefold()
    )


def _figura_pontos_chuveiro(
    figura_base,
    trecho,
    posicao_selecionada=None
):
    """
    Reaproveita a mini planta do trecho e acrescenta pontos clicáveis
    ao longo da parede. A posição é armazenada como fração t da parede
    lógica original, mantendo estabilidade se o DXF for redesenhado.
    """
    fig = dict(
        figura_base
    )
    fig["layer"] = list(
        figura_base.get(
            "layer",
            []
        )
    )

    # A layer de paredes contém as coordenadas já transformadas
    # para o canvas. Localizamos os dois extremos do trecho escolhido.
    dados = []
    for layer in figura_base.get(
        "layer",
        []
    ):
        values = (
            layer.get(
                "data",
                {}
            ).get(
                "values",
                []
            )
        )
        candidatos = [
            v
            for v in values
            if isinstance(v, dict)
            and v.get("parede_id")
            == trecho["id"]
            and "ordem" in v
            and "x" in v
            and "y" in v
        ]
        if len(candidatos) >= 2:
            dados = sorted(
                candidatos,
                key=lambda v: v[
                    "ordem"
                ]
            )[:2]
            break

    if len(dados) < 2:
        return fig

    a, b = dados
    t0 = float(
        trecho["t0"]
    )
    t1 = float(
        trecho["t1"]
    )

    # 21 posições = incrementos de 5% dentro do trecho livre.
    # Evitamos exatamente as extremidades.
    pontos = []
    for i in range(
        1,
        20
    ):
        u = i / 20.0
        t = (
            t0
            + (
                t1 - t0
            ) * u
        )
        pid = (
            f"{trecho['id']}"
            f"_P{i:02d}"
        )

        pontos.append({
            "ponto_id":
                pid,
            "x":
                float(a["x"])
                + (
                    float(b["x"])
                    - float(a["x"])
                ) * u,
            "y":
                float(a["y"])
                + (
                    float(b["y"])
                    - float(a["y"])
                ) * u,
            "t":
                t,
            "percentual":
                round(
                    u * 100
                ),
            "selecionado":
                (
                    "SIM"
                    if (
                        posicao_selecionada
                        is not None
                        and abs(
                            float(
                                posicao_selecionada
                            )
                            - t
                        )
                        < (
                            abs(
                                t1 - t0
                            )
                            / 40.0
                            + 1e-9
                        )
                    )
                    else "NAO"
                )
        })

    if not pontos:
        return fig

    # Usa as mesmas escalas do gráfico-base.
    primeira = fig[
        "layer"
    ][0]
    sx = primeira[
        "encoding"
    ]["x"]["scale"]
    sy = primeira[
        "encoding"
    ]["y"]["scale"]

    fig["layer"].append({
        "data": {
            "values":
                pontos
        },
        "params": [
            {
                "name":
                    "ponto_chuveiro",
                "select": {
                    "type":
                        "point",
                    "fields": [
                        "ponto_id",
                        "t"
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
                "point",
            "filled":
                True,
            "size":
                150,
            "stroke":
                "#ffffff",
            "strokeWidth":
                1.5
        },
        "encoding": {
            "x": {
                "field":
                    "x",
                "type":
                    "quantitative",
                "axis":
                    None,
                "scale":
                    sx
            },
            "y": {
                "field":
                    "y",
                "type":
                    "quantitative",
                "axis":
                    None,
                "scale":
                    sy
            },
            "color": {
                "condition": [
                    {
                        "param":
                            "ponto_chuveiro",
                        "value":
                            "#16a34a"
                    },
                    {
                        "test":
                            (
                                "datum."
                                "selecionado "
                                "=== 'SIM'"
                            ),
                        "value":
                            "#16a34a"
                    }
                ],
                "value":
                    "#f59e0b"
            },
            "tooltip": [
                {
                    "field":
                        "percentual",
                    "title":
                        "Posição no trecho (%)"
                }
            ]
        }
    })

    return fig


def _extrair_ponto_chuveiro(
    evento
):
    try:
        sel = (
            evento
            .selection
            .ponto_chuveiro
        )
    except Exception:
        try:
            sel = (
                evento[
                    "selection"
                ][
                    "ponto_chuveiro"
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

    if isinstance(
        sel,
        dict
    ):
        valor = sel.get(
            "t"
        )

        if isinstance(
            valor,
            (list, tuple)
        ):
            valor = (
                valor[0]
                if valor
                else None
            )

        if valor is None:
            for item in (
                sel.get(
                    "values"
                )
                or []
            ):
                if isinstance(
                    item,
                    dict
                ) and "t" in item:
                    valor = item[
                        "t"
                    ]
                    break

        if valor is not None:
            try:
                return (
                    True,
                    float(
                        valor
                    )
                )
            except Exception:
                pass

        return (
            True,
            None
        )

    return (
        False,
        None
    )


def renderizar_tomadas_altas(
    dados_ambientes,
    config_salva,
    dxf_bytes=None
):
    """
    Fase 8.6:
    posicionamento interativo das TUEs altas.

    Ar-condicionado: seleção do trecho e centralização automática.\n    Chuveiro: seleção do trecho e depois de um ponto específico na parede.\n    Portas dividem a parede em trechos independentes, como no QDC.
    """
    altas = [
        row
        for row in dados_ambientes
        if _eh_tomada_alta(
            row
        )
    ]

    if not altas:
        return {}

    st.divider()
    st.subheader(
        "🔌 Posicionamento das Tomadas Altas"
    )

    st.markdown(
        "Escolha na mini planta onde cada tomada alta será instalada. "
        "**Ar-condicionado** permanece centralizado no trecho escolhido. "
        "Para **chuveiro**, depois escolha também o ponto desejado na parede."
    )

    if not dxf_bytes:
        st.info(
            "A mini planta será liberada quando houver um DXF processado."
        )
        return {}

    ambientes_geom = (
        _ambientes_do_dxf(
            dxf_bytes
        )
    )

    portas_geom = (
        analisar_portas_dxf(
            dxf_bytes
        )
    )

    salvas = (
        _config_salva_altas(
            config_salva
        )
    )

    resultado = {}

    colunas = st.columns(
        2,
        gap="medium"
    )

    for indice_amb, row in enumerate(
        altas
    ):
        ambiente = str(
            row.get(
                "Ambiente",
                ""
            )
        )

        equipamento = str(
            row.get(
                "Equipamento TUE",
                "Tomada alta"
            )
        )

        potencia = int(
            row.get(
                "Pot. Unit. TUE (W)",
                row.get(
                    "Pot. Unit. TUE (VA)",
                    0
                )
            )
            or 0
        )

        qtd = int(
            row.get(
                "Qtd TUE",
                row.get(
                    "TUE",
                    0
                )
            )
            or 0
        )

        item = ambientes_geom.get(
            ambiente
        )

        item_portas = (
            portas_geom.get(
                ambiente
            )
            or {}
        )

        if not item:
            continue

        paredes = item[
            "paredes"
        ]

        portas = item_portas.get(
            "portas",
            []
        )

        trechos = (
            _todos_trechos_qdc(
                paredes,
                portas
            )
        )

        if not trechos:
            continue

        resultado[
            ambiente
        ] = []

        coluna = colunas[
            indice_amb % 2
        ]

        with coluna:
            with st.expander(
                f"🔌 {ambiente} — {equipamento}",
                expanded=True
            ):
                if potencia:
                    st.caption(
                        f"{equipamento} — {potencia} W"
                    )
                else:
                    st.caption(
                        equipamento
                    )

                for idx in range(
                    qtd
                ):
                    salvo_lista = (
                        salvas.get(
                            ambiente,
                            []
                        )
                    )

                    salvo = (
                        salvo_lista[idx]
                        if (
                            isinstance(
                                salvo_lista,
                                list
                            )
                            and idx
                            < len(
                                salvo_lista
                            )
                            and isinstance(
                                salvo_lista[idx],
                                dict
                            )
                        )
                        else {}
                    )

                    chave = (
                        "fase8_6_tomada_alta_"
                        f"{ambiente}_{idx}"
                    )

                    if chave not in st.session_state:
                        parede_salva = salvo.get(
                            "parede_numero"
                        )

                        trecho_salvo = salvo.get(
                            "trecho_numero"
                        )

                        candidato = None

                        if (
                            parede_salva is not None
                            and trecho_salvo is not None
                        ):
                            candidato = (
                                f"P{int(parede_salva)}"
                                f"_T{int(trecho_salvo)}"
                            )

                        if not any(
                            t["id"]
                            == candidato
                            for t in trechos
                        ):
                            candidato = None

                        st.session_state[
                            chave
                        ] = candidato

                    chave_posicao = (
                        "fase8_6_posicao_chuveiro_"
                        f"{ambiente}_{idx}"
                    )

                    if chave_posicao not in st.session_state:
                        pos_salva = salvo.get(
                            "posicao_t"
                        )
                        try:
                            pos_salva = (
                                float(
                                    pos_salva
                                )
                                if pos_salva is not None
                                else None
                            )
                        except Exception:
                            pos_salva = None

                        st.session_state[
                            chave_posicao
                        ] = pos_salva

                    selecionada = (
                        st.session_state[
                            chave
                        ]
                    )

                    titulo = (
                        "Tomada alta"
                        if qtd == 1
                        else (
                            f"Tomada alta {idx + 1}"
                        )
                    )

                    st.markdown(
                        f"**{titulo}**"
                    )

                    st.caption(
                        "Clique no trecho desejado. "
                        "🔵 disponível | 🟢 selecionado"
                    )

                    fig = (
                        _figura_paredes_qdc(
                            ambiente,
                            item["poly"],
                            paredes,
                            selecionada,
                            portas=portas,
                            geometrias_portas=
                                item_portas.get(
                                    "geometrias_portas",
                                    []
                                ),
                            trechos=trechos
                        )
                    )

                    evento = st.vega_lite_chart(
                        fig,
                        use_container_width=False,
                        key=(
                            "fase8_6_grafico_tomada_alta_"
                            f"{ambiente}_{idx}"
                        ),
                        on_select="rerun"
                    )

                    ids_validos = {
                        t["id"]
                        for t in trechos
                    }

                    recebeu, nova = (
                        _extrair_parede_evento(
                            evento,
                            ids_validos
                        )
                    )

                    if (
                        recebeu
                        and nova is not None
                        and nova != selecionada
                    ):
                        st.session_state[
                            chave
                        ] = nova

                        if _eh_chuveiro(
                            equipamento
                        ):
                            st.session_state[
                                chave_posicao
                            ] = None

                        st.rerun()

                    selecionada = (
                        st.session_state[
                            chave
                        ]
                    )

                    trecho = next(
                        (
                            t
                            for t in trechos
                            if t["id"]
                            == selecionada
                        ),
                        None
                    )

                    if trecho is None:
                        st.warning(
                            "Selecione a parede desta tomada alta."
                        )
                        continue

                    posicao_t = None

                    if _eh_chuveiro(
                        equipamento
                    ):
                        posicao_t = (
                            st.session_state[
                                chave_posicao
                            ]
                        )

                        st.caption(
                            "Agora clique no ponto desejado da parede. "
                            "🟠 posições disponíveis | 🟢 posição escolhida"
                        )

                        fig_pontos = (
                            _figura_pontos_chuveiro(
                                fig,
                                trecho,
                                posicao_t
                            )
                        )

                        evento_ponto = (
                            st.vega_lite_chart(
                                fig_pontos,
                                use_container_width=False,
                                key=(
                                    "fase8_6_grafico_ponto_chuveiro_"
                                    f"{ambiente}_{idx}"
                                ),
                                on_select="rerun"
                            )
                        )

                        recebeu_ponto, novo_t = (
                            _extrair_ponto_chuveiro(
                                evento_ponto
                            )
                        )

                        if (
                            recebeu_ponto
                            and novo_t is not None
                            and (
                                posicao_t is None
                                or abs(
                                    float(
                                        novo_t
                                    )
                                    - float(
                                        posicao_t
                                    )
                                ) > 1e-9
                            )
                        ):
                            st.session_state[
                                chave_posicao
                            ] = float(
                                novo_t
                            )
                            st.rerun()

                        posicao_t = (
                            st.session_state[
                                chave_posicao
                            ]
                        )

                        if posicao_t is None:
                            st.warning(
                                "Selecione também o ponto do chuveiro na parede."
                            )
                            continue

                        percentual = (
                            (
                                float(
                                    posicao_t
                                )
                                - float(
                                    trecho["t0"]
                                )
                            )
                            / max(
                                float(
                                    trecho["t1"]
                                )
                                - float(
                                    trecho["t0"]
                                ),
                                1e-9
                            )
                            * 100.0
                        )

                        st.success(
                            f"{equipamento}: {trecho['rotulo']} — "
                            f"posição {percentual:.0f}% do trecho"
                        )
                    else:
                        st.success(
                            f"{equipamento}: {trecho['rotulo']} — "
                            "centralizado no trecho"
                        )

                    resultado[
                        ambiente
                    ].append({
                        "indice":
                            idx,
                        "equipamento":
                            equipamento,
                        "parede_numero":
                            trecho[
                                "parede_numero"
                            ],
                        "trecho_numero":
                            trecho[
                                "trecho_numero"
                            ],
                        "t0":
                            float(
                                trecho[
                                    "t0"
                                ]
                            ),
                        "t1":
                            float(
                                trecho[
                                    "t1"
                                ]
                            ),
                        "posicao_t":
                            (
                                float(
                                    posicao_t
                                )
                                if posicao_t is not None
                                else None
                            )
                    })

    return resultado
