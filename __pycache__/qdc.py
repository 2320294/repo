import streamlit as st


def renderizar_qdc(
    dados_ambientes,
    local_qdc_salvo=None
):
    st.divider()

    ambientes_validos_qdc = []
    ambientes_recomendados_qdc = []

    for r in dados_ambientes:
        nome_amb = r["Ambiente"]
        nome_lower = nome_amb.lower()

        is_molhado = any(
            x in nome_lower
            for x in [
                "coz",
                "serv",
                "banh",
                "lav",
                "sanit",
                "wc",
                "as",
                "área",
                "area"
            ]
        )

        if is_molhado:
            continue

        is_circulacao = any(
            x in nome_lower
            for x in [
                "hall",
                "corredor",
                "circul",
                "circ"
            ]
        )

        if is_circulacao:
            ambientes_recomendados_qdc.append(
                f"{nome_amb} (Recomendado)"
            )
        else:
            ambientes_validos_qdc.append(
                nome_amb
            )

    opcoes_qdc = (
        ambientes_recomendados_qdc
        +
        ambientes_validos_qdc
    )

    if not opcoes_qdc:
        opcoes_qdc = [
            r["Ambiente"]
            for r in dados_ambientes
        ]

    indice_qdc = 0

    if local_qdc_salvo:
        candidatos = [
            local_qdc_salvo,
            f"{local_qdc_salvo} (Recomendado)"
        ]

        for candidato in candidatos:
            if candidato in opcoes_qdc:
                indice_qdc = (
                    opcoes_qdc.index(
                        candidato
                    )
                )
                break

    local_qdc_selecionado = st.selectbox(
        "⚡ Selecione o ambiente onde ficará "
        "instalado o QDC:",
        opcoes_qdc,
        index=indice_qdc,
        key="select_qdc"
    )

    return (
        local_qdc_selecionado
        .split(" (Recomendado")[0]
        .strip()
    )
