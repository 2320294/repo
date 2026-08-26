# ========================================================
# CONFIGURAÇÃO DE INTERRUPTORES
# ========================================================
st.divider()
st.subheader("⚙️ Configuração de Interruptores nas Soleiras")
st.markdown(
    "Escolha **0, 1 ou 2 interruptores por ambiente**. "
    "Com 2, o motor usará as duas portas/posições disponíveis da soleira. "
    "Com 1, escolha qual porta deverá receber o interruptor."
)

nomes_ambientes = sorted(
    [r["Ambiente"] for r in dados_ambientes],
    key=str.casefold
)

config_interruptores_usuario = {}

# Divide os ambientes em duas colunas
col_esquerda, col_direita = st.columns(2)

for indice, amb in enumerate(nomes_ambientes):

    # Alterna os ambientes entre as duas colunas
    coluna = col_esquerda if indice % 2 == 0 else col_direita

    cfg_atual = (
        config_salva.get(amb, {})
        if isinstance(config_salva, dict)
        else {}
    )

    qtd_salva = max(
        0,
        min(
            2,
            int(cfg_atual.get("quantidade", 0))
        )
    )

    with coluna:

        with st.expander(f"Interruptores — {amb}"):

            qtd_int = st.selectbox(
                f"Quantidade de interruptores em {amb}",
                [0, 1, 2],
                index=qtd_salva,
                key=f"int_qtd_{amb}"
            )

            if qtd_int == 1:

                porta_salva = max(
                    1,
                    min(
                        2,
                        int(cfg_atual.get("porta", 1))
                    )
                )

                porta_num = st.selectbox(
                    f"Qual porta recebe o interruptor — {amb}",
                    [1, 2],
                    index=porta_salva - 1,
                    key=f"int_porta_{amb}"
                )

                config_interruptores_usuario[amb] = {
                    "quantidade": 1,
                    "porta": porta_num
                }

                st.caption(
                    f"Será desenhado 1 círculo tangente "
                    f"à posição da porta {porta_num}."
                )

            elif qtd_int == 2:

                config_interruptores_usuario[amb] = {
                    "quantidade": 2
                }

                st.caption(
                    "Serão desenhados 2 círculos: "
                    "um em cada porta/posição disponível."
                )

            else:

                config_interruptores_usuario[amb] = {
                    "quantidade": 0
                }
