import os
import tempfile

import pandas as pd
import streamlit as st

import motores

from database import (
    buscar_projeto,
    salvar_dados_projeto,
    converter_dxf_do_supabase
)


def _valor_w(row, campo_w, campo_va, padrao=0):
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


def _renderizar_tabela_consolidada(
    tabela_editada
):
    # Ordem crescente por nome do ambiente.
    tabela_ordenada = sorted(
        tabela_editada,
        key=lambda x: str(
            x.get("Ambiente", "")
        ).casefold()
    )

    linhas = []

    for row in tabela_ordenada:
        linhas.append({
            "Ambiente":
                row.get("Ambiente", ""),

            "Área (m²)":
                round(
                    float(
                        row.get(
                            "Área (m²)",
                            0
                        )
                    ),
                    2
                ),

            "Perímetro (m)":
                round(
                    float(
                        row.get(
                            "Perímetro (m)",
                            0
                        )
                    ),
                    2
                ),

            "Qtd TUE":
                int(
                    row.get(
                        "Qtd TUE",
                        0
                    )
                ),

            "Potência TUE (W)":
                _valor_w(
                    row,
                    "Pot. Unit. TUE (W)",
                    "Pot. Unit. TUE (VA)",
                    0
                ),

            "Qtd Ilum.":
                int(
                    row.get(
                        "Qtd Ilum.",
                        0
                    )
                ),

            "Potência Ilum. (W)":
                _valor_w(
                    row,
                    "Pot. Unit. Ilum (W)",
                    "Pot. Unit. Ilum (VA)",
                    0
                ),

            "Qtd TUG":
                int(
                    row.get(
                        "Qtd TUG",
                        row.get(
                            "TUGs (Qtd)",
                            0
                        )
                    )
                ),

            "Potência TUG (W)":
                _valor_w(
                    row,
                    "Pot. Unit. TUG (W)",
                    "Pot. Unit. TUG (VA)",
                    0
                ),

            "Equipamento TUE":
                row.get(
                    "Equipamento TUE",
                    "-"
                )
        })

    df = pd.DataFrame(linhas)

    if df.empty:
        return

    linha_total = {
        "Ambiente":
            "TOTAL GERAL",

        "Área (m²)":
            round(
                df["Área (m²)"].sum(),
                2
            ),

        "Perímetro (m)":
            round(
                df["Perímetro (m)"].sum(),
                2
            ),

        "Qtd TUE":
            int(
                df["Qtd TUE"].sum()
            ),

        "Potência TUE (W)":
            int(
                sum(
                    int(r["Qtd TUE"])
                    *
                    int(r["Potência TUE (W)"])
                    for _, r in df.iterrows()
                )
            ),

        "Qtd Ilum.":
            int(
                df["Qtd Ilum."].sum()
            ),

        "Potência Ilum. (W)":
            int(
                sum(
                    int(r["Qtd Ilum."])
                    *
                    int(r["Potência Ilum. (W)"])
                    for _, r in df.iterrows()
                )
            ),

        "Qtd TUG":
            int(
                df["Qtd TUG"].sum()
            ),

        "Potência TUG (W)":
            int(
                sum(
                    int(r["Qtd TUG"])
                    *
                    int(r["Potência TUG (W)"])
                    for _, r in df.iterrows()
                )
            ),

        "Equipamento TUE":
            "-"
    }

    df_total = pd.concat(
        [
            df,
            pd.DataFrame(
                [linha_total]
            )
        ],
        ignore_index=True
    )

    def destacar_total(row):
        if row["Ambiente"] == "TOTAL GERAL":
            return [
                "background-color: #f0f2f6;"
                "font-weight: 600;"
                for _ in row
            ]

        return [
            ""
            for _ in row
        ]

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


def renderizar_painel_principal():

    st.title(
        f"⚡ Painel de Projetos Elétricos — "
        f"Olá, {st.session_state.user_name}!"
    )

    if (
        st.session_state.projeto_ativo
        == "Selecione um projeto..."
    ):
        st.info(
            "👈 Selecione um projeto na barra lateral "
            "ou cadastre um novo."
        )
        st.stop()

    st.info(
        f"📁 **Projeto Ativo:** "
        f"{st.session_state.projeto_ativo}"
    )

    try:
        projeto_obj, dados_obj = buscar_projeto(
            st.session_state.user_email,
            st.session_state.projeto_ativo
        )

    except Exception as e:
        st.error(
            f"❌ Erro ao carregar o projeto "
            f"do Supabase: {e}"
        )
        st.stop()

    if not projeto_obj:
        st.error(
            "❌ O projeto selecionado não foi "
            "encontrado no Supabase."
        )
        st.stop()

    if dados_obj is None:
        try:
            salvar_dados_projeto(
                st.session_state.user_email,
                st.session_state.projeto_ativo,
                tabela_editada=[],
                config_interruptores={}
            )

            _, dados_obj = buscar_projeto(
                st.session_state.user_email,
                st.session_state.projeto_ativo
            )

        except Exception as e:
            st.error(
                f"❌ Não foi possível criar "
                f"os dados do projeto: {e}"
            )
            st.stop()

    dxf_bytes = converter_dxf_do_supabase(
        dados_obj.get("dxf_bytes")
    )

    dados_ambientes = (
        dados_obj.get(
            "tabela_editada"
        )
        or []
    )

    config_salva = (
        dados_obj.get(
            "config_interruptores"
        )
        or {}
    )

    local_qdc_salvo = (
        dados_obj.get(
            "local_qdc"
        )
    )

    # ========================================================
    # UPLOAD / REENVIO DXF
    # ========================================================

    tem_dxf_salvo = (
        dxf_bytes is not None
        and len(dados_ambientes) > 0
    )

    if not tem_dxf_salvo:
        st.subheader(
            "📁 Enviar Planta Base (Formato DXF)"
        )

        uploaded_file = st.file_uploader(
            "Envie o arquivo DXF para iniciar "
            "o dimensionamento:",
            type=["dxf"],
            key="upload_inicial"
        )

        if uploaded_file is not None:
            novo_dxf = uploaded_file.read()

            try:
                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".dxf"
                ) as tmp:
                    tmp.write(novo_dxf)
                    tmp_path = tmp.name

                try:
                    novos_dados = (
                        motores.processar_dxf(
                            tmp_path
                        )
                    )

                finally:
                    if os.path.exists(
                        tmp_path
                    ):
                        os.remove(tmp_path)

                salvar_dados_projeto(
                    st.session_state.user_email,
                    st.session_state.projeto_ativo,
                    dxf_bytes=novo_dxf,
                    tabela_editada=novos_dados,
                    config_interruptores=config_salva
                )

                st.success(
                    "✅ Planta baixa processada e "
                    "salva no Supabase!"
                )

                st.rerun()

            except Exception as e:
                st.error(
                    f"❌ Erro ao processar/salvar "
                    f"o DXF: {e}"
                )

        return

    else:
        with st.expander(
            "🔄 Reenviar / Substituir Planta Baixa (DXF)"
        ):
            st.markdown(
                "Envie um novo DXF caso a geometria "
                "tenha sido alterada."
            )

            novo_uploaded_file = st.file_uploader(
                "Envie a nova planta base (.dxf):",
                type=["dxf"],
                key="upload_substituicao"
            )

            if novo_uploaded_file is not None:
                novo_dxf = (
                    novo_uploaded_file.read()
                )

                try:
                    with tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=".dxf"
                    ) as tmp:
                        tmp.write(novo_dxf)
                        tmp_path = tmp.name

                    try:
                        novos_dados = (
                            motores.processar_dxf(
                                tmp_path
                            )
                        )
                    finally:
                        if os.path.exists(
                            tmp_path
                        ):
                            os.remove(tmp_path)

                    salvar_dados_projeto(
                        st.session_state.user_email,
                        st.session_state.projeto_ativo,
                        dxf_bytes=novo_dxf,
                        tabela_editada=novos_dados,
                        config_interruptores=config_salva
                    )

                    st.success(
                        "✅ Nova planta baixa "
                        "substituída no Supabase!"
                    )

                    st.rerun()

                except Exception as e:
                    st.error(
                        f"❌ Erro ao substituir "
                        f"o DXF: {e}"
                    )

    # ========================================================
    # QUADRO DE CARGAS
    # ========================================================

    if not dados_ambientes:
        return

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
                    value=_valor_w(
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
                    value=_valor_w(
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
                    value=_valor_w(
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

            row_modificado[
                "Qtd Ilum."
            ] = q_ilum

            row_modificado[
                "Pot. Unit. Ilum (W)"
            ] = p_ilum

            row_modificado[
                "Carga Ilum. (W)"
            ] = q_ilum * p_ilum

            row_modificado[
                "Qtd TUG"
            ] = qtd_tugs

            # Compatibilidade enquanto motores.py ainda
            # usa o nome antigo.
            row_modificado[
                "TUGs (Qtd)"
            ] = qtd_tugs

            row_modificado[
                "Pot. Unit. TUG (W)"
            ] = pot_tug_unit

            row_modificado[
                "Carga TUGs (W)"
            ] = qtd_tugs * pot_tug_unit

            row_modificado[
                "Qtd TUE"
            ] = qtd_tue

            row_modificado[
                "Pot. Unit. TUE (W)"
            ] = pot_tue_unit

            row_modificado[
                "Carga TUE (W)"
            ] = qtd_tue * pot_tue_unit

            row_modificado[
                "Equipamento TUE"
            ] = eq_tue

            tabela_editada.append(
                row_modificado
            )

            st.markdown("---")

    _renderizar_tabela_consolidada(
        tabela_editada
    )

    # ========================================================
    # QDC
    # ========================================================

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

    local_qdc = (
        local_qdc_selecionado
        .split(" (Recomendado")[0]
        .strip()
    )

    # ========================================================
    # CONFIGURAÇÃO DE INTERRUPTORES
    # ========================================================

    st.divider()

    st.subheader(
        "⚙️ Configuração de Interruptores nas Soleiras"
    )

    st.markdown(
        "Escolha **0, 1 ou 2 interruptores por ambiente**. "
        "Com 2, o motor usará as duas portas/posições disponíveis. "
        "Com 1, escolha qual porta receberá o interruptor."
    )

    nomes_ambientes = [
        r["Ambiente"]
        for r in dados_ambientes
    ]

    config_interruptores_usuario = {}

    for amb in nomes_ambientes:
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

        with st.expander(
            f"Interruptores — {amb}"
        ):
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
                        int(
                            cfg_atual.get(
                                "porta",
                                1
                            )
                        )
                    )
                )

                porta_num = st.selectbox(
                    f"Qual porta recebe o interruptor — {amb}",
                    [1, 2],
                    index=porta_salva - 1,
                    key=f"int_porta_{amb}"
                )

                config_interruptores_usuario[
                    amb
                ] = {
                    "quantidade": 1,
                    "porta": porta_num
                }

            elif qtd_int == 2:
                config_interruptores_usuario[
                    amb
                ] = {
                    "quantidade": 2
                }

            else:
                config_interruptores_usuario[
                    amb
                ] = {
                    "quantidade": 0
                }

    # ========================================================
    # MATERIAIS
    # ========================================================

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

    # ========================================================
    # SALVAR / CAD
    # ========================================================

    st.divider()

    st.subheader(
        "🖨️ Exportação e Relatórios"
    )

    if st.button(
        "💾 Salvar Alterações do Projeto",
        use_container_width=True
    ):
        try:
            salvar_dados_projeto(
                st.session_state.user_email,
                st.session_state.projeto_ativo,
                tabela_editada=tabela_editada,
                local_qdc=local_qdc,
                config_interruptores=(
                    config_interruptores_usuario
                )
            )

            st.success(
                "✅ Alterações salvas no "
                "Supabase com sucesso!"
            )

            st.rerun()

        except Exception as e:
            st.error(
                f"❌ Erro ao salvar alterações: {e}"
            )

    st.markdown(
        "### Projeto Unifilar (DXF)"
    )

    if st.button(
        "🚀 Gerar CAD (Atualizado)",
        type="primary",
        use_container_width=True
    ):
        if not dxf_bytes:
            st.error(
                "❌ Nenhum arquivo DXF associado."
            )

        else:
            try:
                salvar_dados_projeto(
                    st.session_state.user_email,
                    st.session_state.projeto_ativo,
                    tabela_editada=tabela_editada,
                    local_qdc=local_qdc,
                    config_interruptores=(
                        config_interruptores_usuario
                    )
                )

                cad_bytes_out = (
                    motores.gerar_cad_unifilar(
                        dxf_bytes=dxf_bytes,
                        dados_editados=tabela_editada,
                        local_qdc=local_qdc,
                        config_interruptores=(
                            config_interruptores_usuario
                        )
                    )
                )

                st.success(
                    "✅ Projeto CAD gerado com sucesso!"
                )

                st.download_button(
                    label=
                        "📥 Baixar Projeto DXF Atualizado",
                    data=
                        cad_bytes_out,
                    file_name=
                        "Projeto_Eletrico.dxf",
                    mime=
                        "application/dxf",
                    use_container_width=True
                )

            except Exception as e:
                st.error(
                    f"❌ Erro ao gerar o arquivo CAD: {e}"
                )
