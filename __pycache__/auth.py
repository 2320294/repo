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
        "auth_view": "login",
        "ultimo_menu_login": "🔒  Login",
        "auth_provider": "",
    }

    for chave, valor in valores_padrao.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def sincronizar_login_google():
    """Sincroniza uma sessão autenticada pelo Google/OIDC com o estado do app."""
    try:
        usuario_google = st.user
    except Exception:
        return False

    try:
        autenticado = bool(usuario_google.is_logged_in)
    except Exception:
        autenticado = False

    if not autenticado:
        return False

    email = str(usuario_google.get("email", "") or "").strip()
    nome = str(usuario_google.get("name", "") or "").strip()

    if not email:
        # O Google normalmente fornece e-mail; sem ele o sistema não consegue
        # associar os projetos ao usuário.
        return False

    if not nome:
        nome = email.split("@", 1)[0]

    st.session_state.logged_in = True
    st.session_state.user_email = email
    st.session_state.user_name = nome
    st.session_state.auth_provider = "google"

    if not st.session_state.get("projeto_ativo"):
        st.session_state.projeto_ativo = "Selecione um projeto..."

    return True


def fazer_logout():
    """Encerra login local e, quando aplicável, também a sessão OIDC/Google."""
    login_google_ativo = False
    try:
        login_google_ativo = bool(st.user.is_logged_in)
    except Exception:
        pass

    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
    st.session_state.projeto_ativo = "Selecione um projeto..."
    st.session_state.menu_login = "🔒  Login"
    st.session_state.auth_view = "login"
    st.session_state.ultimo_menu_login = "🔒  Login"
    st.session_state.auth_provider = ""

    if login_google_ativo:
        st.logout()


def renderizar_menu_login():
    logo_b64 = obter_logo_base64()

    # IMPORTANTE: todo o menu de autenticação precisa ser renderizado
    # dentro do st.sidebar. Sem isso, o Streamlit coloca logo/menu na
    # área principal, que foi o problema visual da versão anterior.
    with st.sidebar:
        if logo_b64:
            st.markdown(
                f"""
                <div class="ae-brand">
                    <img src="data:image/png;base64,{logo_b64}" alt="AutoElétrica">
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="ae-brand ae-brand-fallback">
                    ⚡ AutoElétrica
                </div>
                """,
                unsafe_allow_html=True,
            )

        menu = st.radio(
            "Navegação",
            [
                "🔒  Login",
                "ⓘ  Sobre o sistema",
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
            st.session_state.auth_provider = "senha"
            st.session_state.projeto_ativo = "Selecione um projeto..."
            st.rerun()
        else:
            st.error("E-mail ou senha incorretos.")

    except Exception as e:
        st.error(f"❌ Erro ao consultar o Supabase: {e}")


def _renderizar_cadastro():
    st.markdown('<div class="ae-main-spacer"></div>', unsafe_allow_html=True)
    esquerda, centro, direita = st.columns([1.12, 1.58, 1.12])

    with centro:
        st.markdown(
            """
            <div class="ae-user-icon">
                <div class="ae-user-head"></div>
                <div class="ae-user-body"></div>
                <div class="ae-user-plus">+</div>
            </div>
            <h1 class="ae-login-title">Crie sua conta</h1>
            <div class="ae-login-subtitle">
                Cadastre-se para começar a usar o AutoElétrica
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("form_cadastro", clear_on_submit=False):
            cad_nome = st.text_input(
                "Nome completo",
                placeholder="Seu nome",
                key="cad_nome",
            )
            cad_email = st.text_input(
                "E-mail",
                placeholder="seu@email.com",
                key="cad_email",
            )
            cad_senha = st.text_input(
                "Senha",
                type="password",
                placeholder="Crie uma senha",
                key="cad_senha",
            )
            cad_confirmar = st.text_input(
                "Confirmar senha",
                type="password",
                placeholder="Repita a senha",
                key="cad_confirmar_senha",
            )

            enviar_cadastro = st.form_submit_button(
                "＋  Criar conta",
                use_container_width=True,
            )

        if enviar_cadastro:
            if not cad_nome or not cad_email or not cad_senha or not cad_confirmar:
                st.warning("Preencha todos os campos.")
                return

            if cad_senha != cad_confirmar:
                st.error("As senhas não coincidem.")
                return

            if len(cad_senha) < 6:
                st.warning("A senha deve ter pelo menos 6 caracteres.")
                return

            try:
                ok, mensagem = cadastrar_usuario(
                    cad_nome,
                    cad_email,
                    cad_senha,
                )
                if ok:
                    st.success(mensagem)
                    st.info("Cadastro concluído. Volte ao login e entre com sua nova conta.")
                else:
                    st.error(mensagem)
            except Exception as e:
                st.error(f"❌ Erro ao cadastrar no Supabase: {e}")

        st.markdown('<div class="ae-auth-switch-label">Já possui uma conta?</div>', unsafe_allow_html=True)
        if st.button(
            "Voltar para o login",
            key="voltar_login_cadastro",
            use_container_width=True,
        ):
            st.session_state.auth_view = "login"
            st.rerun()

def _renderizar_sobre_o_sistema():
    st.markdown('<div class="ae-main-spacer"></div>', unsafe_allow_html=True)
    esquerda, centro, direita = st.columns([1.0, 1.72, 1.0])

    with centro:
        st.markdown(
            """
            <div class="ae-info-card">
                <div class="ae-info-icon">i</div>
                <h2>Sobre o AutoElétrica</h2>
                <div class="ae-info-lead">
                    Uma plataforma desenvolvida para apoiar a elaboração de
                    projetos elétricos residenciais de forma organizada,
                    prática e automatizada.
                </div>
                <p>
                    O <b>AutoElétrica</b> reúne em um único ambiente ferramentas
                    para leitura e processamento de desenhos em CAD, identificação
                    de ambientes, dimensionamento de cargas, tomadas, iluminação e
                    equipamentos de uso específico.
                </p>
                <p>
                    A proposta do sistema é reduzir tarefas repetitivas durante o
                    desenvolvimento do projeto, mantendo o profissional no controle
                    das informações e permitindo revisar os dados antes da geração
                    final do desenho elétrico e da documentação do projeto.
                </p>
                <p>
                    O sistema também organiza projetos e parâmetros técnicos para
                    facilitar a continuidade do trabalho e futuras revisões.
                </p>
                <div class="ae-info-highlight">
                    Para iniciar, selecione <b>Login</b> no menu lateral e informe
                    suas credenciais de acesso.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _renderizar_formulario_login():
    st.markdown('<div class="ae-main-spacer"></div>', unsafe_allow_html=True)
    esquerda, centro, direita = st.columns([1.12, 1.58, 1.12])

    with centro:
        st.markdown(
            """
            <div class="ae-lock">
                <div class="ae-lock-body"></div>
            </div>
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

        if st.button(
            "Entrar com Google",
            key="entrar_google",
            use_container_width=True,
        ):
            try:
                st.login()
            except Exception as e:
                st.error(
                    "Não foi possível iniciar o login com Google. "
                    "Confira os Secrets de autenticação do Streamlit. "
                    f"Detalhes: {e}"
                )

        st.markdown(
            '<div class="ae-auth-switch-label">Ainda não possui uma conta?</div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "Criar cadastro",
            key="abrir_cadastro_login",
            use_container_width=True,
        ):
            st.session_state.auth_view = "cadastro"
            st.rerun()

def renderizar_pagina_login():
    menu = renderizar_menu_login()

    # Se o usuário saiu de "Sobre o sistema" e clicou novamente em Login,
    # volta sempre ao formulário de login principal.
    menu_anterior = st.session_state.get("ultimo_menu_login", "🔒  Login")
    if menu != menu_anterior:
        if menu == "🔒  Login":
            st.session_state.auth_view = "login"
        st.session_state.ultimo_menu_login = menu

    if menu == "ⓘ  Sobre o sistema":
        _renderizar_sobre_o_sistema()
        return

    # O cadastro não aparece mais na barra lateral. Ele é acessado
    # a partir do próprio card de login, como na primeira versão.
    if st.session_state.get("auth_view", "login") == "cadastro":
        _renderizar_cadastro()
        return

    _renderizar_formulario_login()


def renderizar_autenticacao():
    """Compatibilidade com chamadas antigas."""
    renderizar_pagina_login()
