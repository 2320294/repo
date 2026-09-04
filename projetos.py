import streamlit as st

from database import (
    listar_projetos,
    criar_projeto,
    apagar_projeto
)


def _ativar_projeto_selecionado():
    """
    Aplica imediatamente a seleção da barra lateral e invalida somente
    caches globais derivados do projeto anterior.

    Os estados editáveis isolados por projeto permanecem preservados.
    """
    novo_projeto = st.session_state.get(
        "selectbox_projeto_ativo",
        "Selecione um projeto..."
    )

    projeto_anterior = st.session_state.get(
        "projeto_ativo",
        "Selecione um projeto..."
    )

    if novo_projeto == projeto_anterior:
        return

    st.session_state["projeto_ativo"] = novo_projeto

    # Caches/derivados não isolados por nome do projeto.
    chaves_invalidar = (
        "dimensionamento_rotas",
        "dimensionamento_rotas_projeto",
        "dimensionamento_rotas_versao",
        "resultado_cad",
        "dxf_gerado",
        "dxf_gerado_bytes",
        "arquivo_dxf_gerado",
        "excel_gerado",
        "pdf_gerado",
        "memorial_pdf",
    )

    for chave in chaves_invalidar:
        st.session_state.pop(
            chave,
            None
        )


    # Remove widgets legados globais da tela de parâmetros.
    # A partir desta revisão, novos widgets usam chave por projeto.
    chaves_widgets_legados = (
        "param_pe_direito",
        "param_rede_uf",
        "param_rede_municipio",
        "param_rede_concessionaria",
        "param_rede_concessionaria_manual",
        "param_rede_tipo_fornecimento",
        "param_rede_tensao_fornecimento",
        "param_rede_metodo_demanda",
        "param_rede_fator_demanda_manual",

        "param_qdc_icc_ka",
        "param_qdc_cap_dg_ka",
        "param_qdc_cap_terminais_ka",
        "param_qdc_fabricante_protecao",
        "param_qdc_referencia_seletividade",
        "param_qdc_seletividade_validada_rt",
        "param_qdc_dps_tipo",
        "param_qdc_dps_uc_v",
        "param_qdc_dps_up_kv",
        "param_qdc_dps_in_ka",
        "param_qdc_dps_imax_ka",
        "param_qdc_esquema_aterramento",
        "param_qdc_arranjo_dps",
        "param_qdc_arranjo_dps_validado_rt",
        "param_qdc_norma_concessionaria_ref",
        "param_qdc_concessionaria_validada_rt",
    )

    for chave in chaves_widgets_legados:
        st.session_state.pop(
            chave,
            None
        )


def renderizar_gerenciador_projetos():
    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        "### 📂 Gerenciador de Obras"
    )

    with st.form(
        "form_novo_projeto",
        clear_on_submit=True
    ):
        novo_proj_nome = st.text_input(
            "Nome do Novo Projeto / Pavimento"
        )

        btn_criar_proj = (
            st.form_submit_button(
                "➕ Cadastrar Projeto"
            )
        )

    if btn_criar_proj:
        if not novo_proj_nome.strip():
            st.warning(
                "Digite o nome do projeto."
            )
        else:
            try:
                ok, mensagem = criar_projeto(
                    st.session_state.user_email,
                    novo_proj_nome
                )

                if ok:
                    st.session_state.projeto_ativo = (
                        novo_proj_nome.strip()
                    )
                    st.success(mensagem)
                    st.rerun()
                else:
                    st.warning(mensagem)

            except Exception as e:
                st.error(
                    f"❌ Erro ao criar projeto "
                    f"no Supabase: {e}"
                )

    try:
        projetos_usuario = listar_projetos(
            st.session_state.user_email
        )
    except Exception as e:
        st.error(
            f"❌ Erro ao listar projetos: {e}"
        )
        projetos_usuario = []

    st.markdown(
        "### 📋 Seus Projetos Salvos:"
    )

    if not projetos_usuario:
        st.info(
            "Nenhum projeto cadastrado ainda."
        )
        st.session_state.projeto_ativo = (
            "Selecione um projeto..."
        )
        return

    nomes_projetos = [
        p["nome_projeto"]
        for p in projetos_usuario
    ]

    opcoes_selectbox = [
        "Selecione um projeto..."
    ] + nomes_projetos

    indice_atual = (
        opcoes_selectbox.index(
            st.session_state.projeto_ativo
        )
        if (
            st.session_state.projeto_ativo
            in opcoes_selectbox
        )
        else 0
    )

    projeto_selecionado = st.selectbox(
        "Selecione o projeto ativo:",
        opcoes_selectbox,
        index=indice_atual,
        key="selectbox_projeto_ativo",
        on_change=_ativar_projeto_selecionado
    )

    if (
        projeto_selecionado
        != "Selecione um projeto..."
    ):
        chave_confirmacao = (
            "confirmar_exclusao_projeto"
        )

        if chave_confirmacao not in st.session_state:
            st.session_state[
                chave_confirmacao
            ] = None

        if st.button(
            "🗑️ Apagar Projeto Selecionado",
            type="secondary",
            use_container_width=True
        ):
            st.session_state[
                chave_confirmacao
            ] = projeto_selecionado

        if (
            st.session_state[
                chave_confirmacao
            ]
            == projeto_selecionado
        ):
            st.warning(
                f"⚠️ Tem certeza que deseja apagar o projeto "
                f"**'{projeto_selecionado}'**? "
                "Esta ação não poderá ser desfeita."
            )

            col_confirmar, col_cancelar = (
                st.columns(2)
            )

            with col_confirmar:
                confirmar = st.button(
                    "✅ Sim, apagar",
                    type="primary",
                    use_container_width=True,
                    key=(
                        "confirmar_apagar_"
                        f"{projeto_selecionado}"
                    )
                )

            with col_cancelar:
                cancelar = st.button(
                    "❌ Cancelar",
                    use_container_width=True,
                    key=(
                        "cancelar_apagar_"
                        f"{projeto_selecionado}"
                    )
                )

            if cancelar:
                st.session_state[
                    chave_confirmacao
                ] = None
                st.rerun()

            if confirmar:
                try:
                    apagar_projeto(
                        st.session_state.user_email,
                        projeto_selecionado
                    )

                    st.session_state.projeto_ativo = (
                        "Selecione um projeto..."
                    )

                    st.session_state[
                        chave_confirmacao
                    ] = None

                    st.success(
                        f"Projeto '{projeto_selecionado}' "
                        f"apagado!"
                    )

                    st.rerun()

                except Exception as e:
                    st.error(
                        f"❌ Erro ao apagar projeto: {e}"
                    )
