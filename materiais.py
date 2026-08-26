import pandas as pd
import streamlit as st


def renderizar_materiais(
    tabela_editada,
    config_interruptores_usuario
):
    st.divider()

    st.subheader(
        "📦 Tabela Quantitativa de Materiais"
    )

    total_caixas_luz = sum(
        int(
            r.get(
                "Qtd Ilum.",
                0
            )
        )
        for r in tabela_editada
    )

    total_tugs_geral = sum(
        int(
            r.get(
                "Qtd TUG",
                r.get(
                    "TUGs (Qtd)",
                    0
                )
            )
        )
        for r in tabela_editada
    )

    total_tues_geral = sum(
        int(
            r.get(
                "Qtd TUE",
                0
            )
        )
        for r in tabela_editada
    )

    total_tomadas_geral = (
        total_tugs_geral
        +
        total_tues_geral
    )

    total_interruptores = sum(
        int(
            cfg.get(
                "quantidade",
                0
            )
        )
        for cfg
        in config_interruptores_usuario.values()
    )

    materiais_df = pd.DataFrame([
        {
            "Material":
                'Caixa Octogonal de teto 4x4" (Plástico)',
            "Unidade":
                "pç",
            "Quantidade":
                total_caixas_luz
        },
        {
            "Material":
                'Caixa de Embutir de Parede 4x2" (Plástico) — Tomadas',
            "Unidade":
                "pç",
            "Quantidade":
                total_tomadas_geral
        },
        {
            "Material":
                'Caixa de Embutir de Parede 4x2" (Plástico) — Interruptores',
            "Unidade":
                "pç",
            "Quantidade":
                total_interruptores
        }
    ])

    st.dataframe(
        materiais_df,
        use_container_width=True,
        hide_index=True
    )
