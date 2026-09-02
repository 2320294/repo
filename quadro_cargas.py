import pandas as pd
import streamlit as st


def valor_w(row, campo_w, campo_va, padrao=0):
    """
    Compatibilidade com projetos antigos.
    Se existir campo em W, usa W.
    Caso exista somente VA, converte usando FP=1,0:
        W = VA * 1,0
    """
    if campo_w in row:
        return int(row.get(campo_w, padrao))

    if campo_va in row:
        return int(
            round(
                float(
                    row.get(
                        campo_va,
                        padrao
                    )
                ) * 1.0
            )
        )

    return int(padrao)


def renderizar_edicao_cargas(dados_ambientes):
    """
    Exibe os campos editáveis de iluminação, TUG e TUE.
    Retorna a tabela já normalizada em Watts.
    """
    dados_ambientes = sorted(
        dados_ambientes,
        key=lambda x: str(
            x.get(
                "Ambiente",
                ""
            )
        ).casefold()
    )

    st.divider()
    st.subheader(
        "📊 Quadro de Previsão de Cargas Consolidado"
    )

    tabela_editada = []

    for row in dados_ambientes:
        ambiente = row["Ambiente"]

        with st.container():
            st.markdown(
                f"**Ambiente: {ambiente}** — "
                f"*Área: "
                f"{float(row.get('Área (m²)', 0)):.2f}m² | "
                f"Perímetro: "
                f"{float(row.get('Perímetro (m)', 0)):.2f}m*"
            )

            c1, c2, c3, c4, c5, c6 = st.columns(6)

            with c1:
                q_ilum = st.number_input(
                    "Qtd Ilum",
                    min_value=0,
                    value=int(
                        row.get(
                            "Qtd Ilum.",
                            1
                        )
                    ),
                    key=f"ilum_{ambiente}"
                )

            with c2:
                p_ilum = st.number_input(
                    "Pot Ilum (W)",
                    min_value=0,
                    value=valor_w(
                        row,
                        "Pot. Unit. Ilum (W)",
                        "Pot. Unit. Ilum (VA)",
                        100
                    ),
                    key=f"pilum_{ambiente}"
                )

            with c3:
                qtd_tugs = st.number_input(
                    "Qtd TUG",
                    min_value=0,
                    value=int(
                        row.get(
                            "Qtd TUG",
                            row.get(
                                "TUGs (Qtd)",
                                1
                            )
                        )
                    ),
                    key=f"tugs_{ambiente}"
                )

            with c4:
                pot_tug_unit = st.number_input(
                    "Pot TUG (W)",
                    min_value=0,
                    value=valor_w(
                        row,
                        "Pot. Unit. TUG (W)",
                        "Pot. Unit. TUG (VA)",
                        100
                    ),
                    key=f"ptug_{ambiente}"
                )

            with c5:
                qtd_tue = st.number_input(
                    "Qtd TUE",
                    min_value=0,
                    value=int(
                        row.get(
                            "Qtd TUE",
                            0
                        )
                    ),
                    key=f"tue_{ambiente}"
                )

            with c6:
                pot_tue_unit = st.number_input(
                    "Pot TUE (W)",
                    min_value=0,
                    value=valor_w(
                        row,
                        "Pot. Unit. TUE (W)",
                        "Pot. Unit. TUE (VA)",
                        0
                    ),
                    key=f"ptue_{ambiente}"
                )

            eq_tue = st.text_input(
                f"Equipamento TUE ({ambiente})",
                value=str(
                    row.get(
                        "Equipamento TUE",
                        "-"
                    )
                ),
                key=f"eq_{ambiente}"
            )

            row_modificado = row.copy()

            row_modificado["Qtd Ilum."] = q_ilum
            row_modificado["Pot. Unit. Ilum (W)"] = p_ilum
            row_modificado["Carga Ilum. (W)"] = (
                q_ilum * p_ilum
            )

            row_modificado["Qtd TUG"] = qtd_tugs

            # Mantém compatibilidade temporária com motores.py
            row_modificado["TUGs (Qtd)"] = qtd_tugs

            row_modificado["Pot. Unit. TUG (W)"] = (
                pot_tug_unit
            )
            row_modificado["Carga TUGs (W)"] = (
                qtd_tugs * pot_tug_unit
            )

            row_modificado["Qtd TUE"] = qtd_tue
            row_modificado["Pot. Unit. TUE (W)"] = (
                pot_tue_unit
            )
            row_modificado["Carga TUE (W)"] = (
                qtd_tue * pot_tue_unit
            )

            row_modificado["Equipamento TUE"] = eq_tue

            tabela_editada.append(
                row_modificado
            )

            st.markdown("---")

    return tabela_editada


def renderizar_tabela_consolidada(tabela_editada):
    """
    Fase 8.1 — ordem definitiva das colunas:

    1. Ambiente
    2. Área (m²)
    3. Perímetro (m)
    4. Qtd Ilum.
    5. Potência Ilum. (W)
    6. Qtd TUG
    7. Potência TUG (W)
    8. Qtd TUE
    9. Potência TUE (W)
    10. Equipamento TUE

    A linha TOTAL GERAL segue exatamente a mesma ordem.
    """
    tabela_ordenada = sorted(
        tabela_editada,
        key=lambda x: str(
            x.get("Ambiente", "")
        ).casefold()
    )

    linhas = []

    for row in tabela_ordenada:
        linhas.append({
            "Ambiente": row.get("Ambiente", ""),

            "Área (m²)": round(
                float(row.get("Área (m²)", 0)),
                2
            ),

            "Perímetro (m)": round(
                float(row.get("Perímetro (m)", 0)),
                2
            ),

            "Qtd Ilum.": int(
                row.get("Qtd Ilum.", 0)
            ),

            "Potência Ilum. (W)": valor_w(
                row,
                "Pot. Unit. Ilum (W)",
                "Pot. Unit. Ilum (VA)",
                0
            ),

            "Qtd TUG": int(
                row.get(
                    "Qtd TUG",
                    row.get("TUGs (Qtd)", 0)
                )
            ),

            "Potência TUG (W)": valor_w(
                row,
                "Pot. Unit. TUG (W)",
                "Pot. Unit. TUG (VA)",
                0
            ),

            "Qtd TUE": int(
                row.get("Qtd TUE", 0)
            ),

            "Potência TUE (W)": valor_w(
                row,
                "Pot. Unit. TUE (W)",
                "Pot. Unit. TUE (VA)",
                0
            ),

            "Equipamento TUE": row.get(
                "Equipamento TUE",
                "-"
            )
        })

    colunas = [
        "Ambiente",
        "Área (m²)",
        "Perímetro (m)",
        "Qtd Ilum.",
        "Potência Ilum. (W)",
        "Qtd TUG",
        "Potência TUG (W)",
        "Qtd TUE",
        "Potência TUE (W)",
        "Equipamento TUE"
    ]

    df = pd.DataFrame(
        linhas,
        columns=colunas
    )

    if df.empty:
        return

    linha_total = {
        "Ambiente": "TOTAL GERAL",

        "Área (m²)": round(
            df["Área (m²)"].sum(),
            2
        ),

        "Perímetro (m)": round(
            df["Perímetro (m)"].sum(),
            2
        ),

        "Qtd Ilum.": int(
            df["Qtd Ilum."].sum()
        ),

        "Potência Ilum. (W)": int(
            sum(
                int(r["Qtd Ilum."])
                * int(r["Potência Ilum. (W)"])
                for _, r in df.iterrows()
            )
        ),

        "Qtd TUG": int(
            df["Qtd TUG"].sum()
        ),

        "Potência TUG (W)": int(
            sum(
                int(r["Qtd TUG"])
                * int(r["Potência TUG (W)"])
                for _, r in df.iterrows()
            )
        ),

        "Qtd TUE": int(
            df["Qtd TUE"].sum()
        ),

        "Potência TUE (W)": int(
            sum(
                int(r["Qtd TUE"])
                * int(r["Potência TUE (W)"])
                for _, r in df.iterrows()
            )
        ),

        "Equipamento TUE": "-"
    }

    df_total = pd.concat(
        [
            df,
            pd.DataFrame(
                [linha_total],
                columns=colunas
            )
        ],
        ignore_index=True
    )

    # Reforço explícito da ordem final mesmo após o concat.
    df_total = df_total[colunas]

    def destacar_total(row):
        if row["Ambiente"] == "TOTAL GERAL":
            return [
                "background-color: #f0f2f6;"
                "font-weight: 600;"
                for _ in row
            ]

        return ["" for _ in row]

    tabela_estilizada = (
        df_total
        .style
        .apply(
            destacar_total,
            axis=1
        )
        .format({
            "Área (m²)": "{:.2f}",
            "Perímetro (m)": "{:.2f}"
        })
    )

    st.dataframe(
        tabela_estilizada,
        use_container_width=True,
        hide_index=True
    )

