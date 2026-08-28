import streamlit as st


def renderizar_interruptores(
    dados_ambientes,
    config_salva
):
    st.divider()

    st.subheader(
        "⚙️ Configuração de Interruptores nas Soleiras"
    )

    st.markdown(
        "Escolha **0, 1 ou 2 interruptores por ambiente**. "
        "Com 2, o motor usará as duas portas/posições disponíveis. "
        "Com 1, escolha qual porta receberá o interruptor."
    )

    nomes_ambientes = sorted(
        [
            r["Ambiente"]
            for r in dados_ambientes
        ],
        key=str.casefold
    )

    config_interruptores_usuario = {}

    # ========================================================
    # DUAS COLUNAS
    # ========================================================

    col_esquerda, col_direita = st.columns(
        2,
        gap="large"
    )

    for indice, amb in enumerate(
        nomes_ambientes
    ):
        coluna = (
            col_esquerda
            if indice % 2 == 0
            else col_direita
        )

        cfg_atual = (
            config_salva.get(
                amb,
                {}
            )
            if isinstance(
                config_salva,
                dict
            )
            else {}
        )

        qtd_salva = max(
            0,
            min(
                2,
                int(
                    cfg_atual.get(
                        "quantidade",
                        0
                    )
                )
            )
        )

        with coluna:

            with st.expander(
                f"🔘 {amb}",
                expanded=False
            ):

                qtd_int = st.selectbox(
                    "Quantidade de interruptores:",
                    [0, 1, 2],
                    index=qtd_salva,
                    key=f"int_qtd_{amb}",
                    format_func=lambda x: {
                        0: "0 — Nenhum",
                        1: "1 — Uma porta",
                        2: "2 — Duas portas"
                    }[x]
                )

                # =================================================
                # 1 INTERRUPTOR
                # =================================================

                if qtd_int == 1:

                    porta_salva = max(
                        1,
                        min(
                            2,
                            int(
                                cfg_atual.get(
                                    "porta",
                                    1
                                )
                            )
                        )
                    )

                    porta_num = st.selectbox(
                        "Porta que recebe o interruptor:",
                        [1, 2],
                        index=porta_salva - 1,
                        key=f"int_porta_{amb}",
                        format_func=lambda x:
                            f"Porta {x}"
                    )

                    config_interruptores_usuario[
                        amb
                    ] = {
                        "quantidade": 1,
                        "porta": porta_num
                    }

                    st.caption(
                        f"1 interruptor será colocado "
                        f"na Porta {porta_num}."
                    )

                # =================================================
                # 2 INTERRUPTORES
                # =================================================

                elif qtd_int == 2:

                    config_interruptores_usuario[
                        amb
                    ] = {
                        "quantidade": 2
                    }

                    st.caption(
                        "2 interruptores serão colocados, "
                        "um em cada porta/posição disponível."
                    )

                # =================================================
                # NENHUM INTERRUPTOR
                # =================================================

                else:

                    config_interruptores_usuario[
                        amb
                    ] = {
                        "quantidade": 0
                    }

                    st.caption(
                        "Nenhum interruptor será gerado "
                        "neste ambiente."
                    )

    return config_interruptores_usuario
