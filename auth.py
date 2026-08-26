import streamlit as st

from database import (
    buscar_usuario,
    cadastrar_usuario
)


def inicializar_estado_sessao():
    valores_padrao = {
        "logged_in": False,
        "user_email": "",
        "user_name": "",
        "projeto_ativo": "Selecione um projeto..."
    }

    for chave, valor in valores_padrao.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def fazer_logout():
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
    st.session_state.projeto_ativo = (
        "Selecione um projeto..."
    )


def renderizar_autenticacao():
    """
    Login e cadastro usando st.form.

    Com isso, ao preencher os campos e pressionar ENTER,
    o formulário é enviado normalmente.
    """
    aba_auth = st.radio(
        "Acesso ao Sistema",
        [
            "Entrar (Login)",
            "Cadastrar-se"
        ],
        horizontal=True
    )

    if aba_auth == "Entrar (Login)":
        st.subheader("🔐 Fazer Login")

        with st.form(
            "form_login",
            clear_on_submit=False
        ):
            login_email = st.text_input(
                "E-mail / Login",
                key="login_email"
            )

            login_senha = st.text_input(
                "Senha",
                type="password",
                key="login_senha"
            )

            enviar_login = st.form_submit_button(
                "Entrar",
                use_container_width=True
            )

        if enviar_login:
            if not login_email or not login_senha:
                st.warning(
                    "Preencha o e-mail e a senha."
                )
                return

            try:
                usuario = buscar_usuario(
                    login_email,
                    login_senha
                )

                if usuario:
                    st.session_state.logged_in = True
                    st.session_state.user_email = (
                        usuario["email"]
                    )
                    st.session_state.user_name = (
                        usuario["nome"]
                    )
                    st.session_state.projeto_ativo = (
                        "Selecione um projeto..."
                    )
                    st.rerun()

                else:
                    st.error(
                        "E-mail ou senha incorretos."
                    )

            except Exception as e:
                st.error(
                    f"❌ Erro ao consultar o Supabase: {e}"
                )

    else:
        st.subheader("📝 Novo Cadastro")

        with st.form(
            "form_cadastro",
            clear_on_submit=False
        ):
            cad_nome = st.text_input(
                "Nome Completo",
                key="cad_nome"
            )

            cad_email = st.text_input(
                "E-mail (Login)",
                key="cad_email"
            )

            cad_senha = st.text_input(
                "Senha",
                type="password",
                key="cad_senha"
            )

            enviar_cadastro = st.form_submit_button(
                "Criar Conta",
                use_container_width=True
            )

        if enviar_cadastro:
            if (
                not cad_nome
                or not cad_email
                or not cad_senha
            ):
                st.warning(
                    "Preencha todos os campos."
                )
                return

            try:
                ok, mensagem = cadastrar_usuario(
                    cad_nome,
                    cad_email,
                    cad_senha
                )

                if ok:
                    st.success(mensagem)
                else:
                    st.error(mensagem)

            except Exception as e:
                st.error(
                    f"❌ Erro ao cadastrar no Supabase: {e}"
                )
