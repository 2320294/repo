
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


def renderizar_tomadas_altas(
    dados_ambientes,
    config_salva,
    dxf_bytes=None
):
    """
    Fase 8.5:
    posicionamento interativo das TUEs altas.

    A seleção é feita diretamente na mini planta, por trecho de parede.
    Portas dividem a parede em trechos independentes, como no QDC.
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
        "Escolha na mini planta o **trecho de parede** onde cada "
        "tomada alta será instalada. A tomada será centralizada no "
        "trecho escolhido e ficará voltada para dentro do ambiente."
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
                        "fase8_5_tomada_alta_"
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
                            "fase8_5_grafico_tomada_alta_"
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

                    st.success(
                        f"{equipamento}: {trecho['rotulo']}"
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
                            )
                    })

    return resultado
