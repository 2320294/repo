import streamlit as st

from database import (
    buscar_usuario,
    cadastrar_usuario,
)
from tema_login import obter_logo_base64


def inicializar_estado_sessao():
    valores_padrao = {
        "logged_in": False,
        "user_email": "",
        "user_name": "",
        "projeto_ativo": "Selecione um projeto...",
        "menu_login": "🔒  Login",
    }

    for chave, valor in valores_padrao.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def fazer_logout():
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
    st.session_state.projeto_ativo = "Selecione um projeto..."
    st.session_state.menu_login = "🔒  Login"


def renderizar_menu_login():
    logo_b64 = obter_logo_base64()

    if logo_b64:
        st.markdown(
            f"""
            <div class="ae-brand">
                <img src="data:image/png;base64,{logo_b64}" alt="AutoElétrica">
                <div class="ae-brand-subtitle">Projetos Elétricos</div>
            </div>
            <div class="ae-sidebar-separator"></div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="ae-brand">
                <h2 style="color:white;margin:0">⚡ AutoElétrica</h2>
                <div class="ae-brand-subtitle">Projetos Elétricos</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    menu = st.radio(
        "Navegação",
        [
            "🔒  Login",
            "ⓘ  Sobre o sistema",
            "❔  Ajuda",
        ],
        key="menu_login",
        label_visibility="collapsed",
    )

    st.markdown(
        """
        <div class="ae-sidebar-footer">
            <div>© 2026 AutoElétrica</div>
            <div>Todos os direitos reservados.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return menu


def _processar_login(login_email, login_senha):
    if not login_email or not login_senha:
        st.warning("Preencha o e-mail e a senha.")
        return

    try:
        usuario = buscar_usuario(login_email, login_senha)

        if usuario:
            st.session_state.logged_in = True
            st.session_state.user_email = usuario["email"]
            st.session_state.user_name = usuario["nome"]
            st.session_state.projeto_ativo = "Selecione um projeto..."
            st.rerun()
        else:
            st.error("E-mail ou senha incorretos.")

    except Exception as e:
        st.error(f"❌ Erro ao consultar o Supabase: {e}")


def _renderizar_cadastro():
    with st.expander("Ainda não tem conta? Cadastre-se"):
        with st.form("form_cadastro", clear_on_submit=False):
            cad_nome = st.text_input("Nome completo", key="cad_nome")
            cad_email = st.text_input("E-mail", key="cad_email")
            cad_senha = st.text_input(
                "Senha",
                type="password",
                key="cad_senha",
            )

            enviar_cadastro = st.form_submit_button(
                "Criar conta",
                use_container_width=True,
            )

        if enviar_cadastro:
            if not cad_nome or not cad_email or not cad_senha:
                st.warning("Preencha todos os campos.")
                return

            try:
                ok, mensagem = cadastrar_usuario(
                    cad_nome,
                    cad_email,
                    cad_senha,
                )
                if ok:
                    st.success(mensagem)
                else:
                    st.error(mensagem)
            except Exception as e:
                st.error(f"❌ Erro ao cadastrar no Supabase: {e}")


def renderizar_pagina_login():
    menu = renderizar_menu_login()

    if menu == "ⓘ  Sobre o sistema":
        _, centro, _ = st.columns([1.0, 1.7, 1.0])
        with centro:
            st.markdown(
                """
                <div class="ae-info-card">
                    <h2 style="margin-top:0">Sobre o AutoElétrica</h2>
                    <p>
                        Plataforma para desenvolvimento e organização de projetos
                        elétricos, com recursos de dimensionamento, processamento de
                        arquivos CAD e geração de documentação técnica.
                    </p>
                    <p style="color:#697386;margin-bottom:0">
                        Acesse o menu <b>Login</b> para entrar no sistema.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return

    if menu == "❔  Ajuda":
        _, centro, _ = st.columns([1.0, 1.7, 1.0])
        with centro:
            st.markdown(
                """
                <div class="ae-info-card">
                    <h2 style="margin-top:0">Ajuda</h2>
                    <p>Para acessar, informe o e-mail e a senha cadastrados.</p>
                    <p>
                        Caso ainda não possua uma conta, abra a opção
                        <b>“Ainda não tem conta? Cadastre-se”</b> na tela de login.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return

    esquerda, centro, direita = st.columns([1.2, 1.55, 1.2])

    with centro:
        with st.container(border=True):
            st.markdown(
                """
                <div class="ae-lock">🔒</div>
                <h1 class="ae-login-title">Bem-vindo!</h1>
                <div class="ae-login-subtitle">
                    Faça login para acessar o sistema
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.form("form_login", clear_on_submit=False):
                login_email = st.text_input(
                    "E-mail",
                    placeholder="seu@email.com",
                    key="login_email",
                )

                login_senha = st.text_input(
                    "Senha",
                    type="password",
                    placeholder="Sua senha",
                    key="login_senha",
                )

                enviar_login = st.form_submit_button(
                    "⇥  Entrar",
                    use_container_width=True,
                )

            if enviar_login:
                _processar_login(login_email, login_senha)

            st.markdown('<div class="ae-ou">ou</div>', unsafe_allow_html=True)

            st.button(
                "🇬  Entrar com Google",
                use_container_width=True,
                disabled=True,
                help="Integração com Google ainda não configurada.",
            )

            _renderizar_cadastro()


def renderizar_autenticacao():
    """Compatibilidade com chamadas antigas."""
    renderizar_pagina_login()
