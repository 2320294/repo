import streamlit as st

from database import (
    listar_projetos,
    criar_projeto,
    apagar_projeto
)


def renderizar_gerenciador_projetos():
    st.divider()

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
        key="selectbox_projeto_ativo"
    )

    if (
        projeto_selecionado
        != st.session_state.projeto_ativo
    ):
        st.session_state.projeto_ativo = (
            projeto_selecionado
        )
        st.rerun()

    if (
        projeto_selecionado
        != "Selecione um projeto..."
        and st.button(
            "🗑️ Apagar Projeto Selecionado",
            type="secondary"
        )
    ):
        try:
            apagar_projeto(
                st.session_state.user_email,
                projeto_selecionado
            )

            st.session_state.projeto_ativo = (
                "Selecione um projeto..."
            )

            st.success(
                f"Projeto '{projeto_selecionado}' "
                f"apagado!"
            )

            st.rerun()

        except Exception as e:
            st.error(
                f"❌ Erro ao apagar projeto: {e}"
            )
