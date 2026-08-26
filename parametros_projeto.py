import streamlit as st


def renderizar_parametros_projeto(
    tensao_salva=None,
    pe_direito_salvo=None
):
    """
    Parâmetros gerais do pavimento/projeto.

    - Tensão escolhida pelo usuário: 110 V ou 220 V
    - Pé-direito editável, padrão 2,80 m
    """

    st.divider()
    st.subheader("🏗️ Parâmetros Gerais do Projeto")

    col_tensao, col_pe = st.columns(2)

    with col_tensao:
        opcoes_tensao = [110, 220]

        try:
            tensao_atual = int(
                tensao_salva
                if tensao_salva is not None
                else 110
            )
        except Exception:
            tensao_atual = 110

        if tensao_atual == 127:
            tensao_atual = 110

        if tensao_atual not in opcoes_tensao:
            tensao_atual = 110

        tensao_projeto = st.selectbox(
            "Tensão do quadro:",
            options=opcoes_tensao,
            index=opcoes_tensao.index(tensao_atual),
            format_func=lambda valor: f"{valor} V",
            key="param_tensao_projeto"
        )

        st.caption(
            "Escolha entre 110 V e 220 V para os cálculos "
            "preliminares de corrente, proteção e materiais."
        )

    with col_pe:
        try:
            pe_atual = float(
                pe_direito_salvo
                if pe_direito_salvo is not None
                else 2.80
            )
        except Exception:
            pe_atual = 2.80

        if pe_atual < 2.00 or pe_atual > 10.00:
            pe_atual = 2.80

        pe_direito = st.number_input(
            "Pé-direito do pavimento (m):",
            min_value=2.00,
            max_value=10.00,
            value=pe_atual,
            step=0.05,
            format="%.2f",
            key="param_pe_direito"
        )

        st.caption(
            "Valor padrão: 2,80 m. "
            "O usuário pode editar livremente."
        )

    return {
        "tensao_projeto": int(tensao_projeto),
        "pe_direito": float(pe_direito)
    }
