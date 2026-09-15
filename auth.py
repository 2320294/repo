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
    # Rev.124: somente a página "Sobre o sistema" deixa de usar a coluna
    # central estreita. Login/cadastro permanecem exatamente com o layout
    # aprovado. O card passa a ocupar a largura útil disponível e, em telas
    # menores, permite rolagem vertical sem comprimir o conteúdo.
    st.markdown(
        """
        <style>
        [data-testid="stMainBlockContainer"]:has(.ae-about-page) {
            height: auto !important;
            min-height: calc(100vh - 2px) !important;
            overflow-y: auto !important;
            overflow-x: hidden !important;
        }

        [data-testid="stMainBlockContainer"] > div:first-child:has(.ae-about-page) {
            height: auto !important;
            min-height: calc(100vh - 2px) !important;
            justify-content: center !important;
            padding-top: 1.5rem !important;
            padding-bottom: 1.5rem !important;
            box-sizing: border-box !important;
        }

        .ae-about-page {
            width: 100%;
            max-width: none;
            margin: 0;
            padding: 0;
        }

        .ae-about-page .ae-info-card {
            width: 100%;
            max-width: none;
            margin: 0;
            box-sizing: border-box;
        }

        @media (max-width: 900px) {
            [data-testid="stMainBlockContainer"] > div:first-child:has(.ae-about-page) {
                justify-content: flex-start !important;
                padding-top: 1rem !important;
                padding-bottom: 1rem !important;
            }

            .ae-about-page .ae-info-card {
                padding: 24px 22px;
                border-radius: 16px;
            }
        }
        </style>
        <div class="ae-about-page">
            <div class="ae-info-card">
                <div class="ae-info-icon">i</div>
                <h2>Sobre o AutoElétrica</h2>
                <div class="ae-info-lead">
                    O <b>AutoElétrica</b> é uma plataforma desenvolvida para auxiliar na elaboração,
                    análise e documentação de projetos elétricos residenciais, integrando automação,
                    critérios técnicos e desenho em CAD em um único ambiente.
                </div>
                <p>
                    A partir da importação da planta baixa em <b>DXF</b>, o sistema identifica os
                    ambientes e utiliza suas características geométricas para auxiliar no
                    dimensionamento e na distribuição dos principais elementos da instalação elétrica.
                </p>
                <p>
                    O AutoElétrica reúne recursos para <b>dimensionamento de cargas, iluminação,
                    tomadas de uso geral e específico, circuitos, quadro de distribuição, dispositivos
                    de proteção e eletrodutos</b>, mantendo as informações do projeto integradas durante
                    todo o processo.
                </p>
                <p>
                    A plataforma também auxilia na <b>organização dos circuitos, balanceamento de fases,
                    cálculo de demanda, definição das proteções, representação do QDC e geração do
                    diagrama unifilar</b>, além da produção de tabelas, quantitativos e documentação
                    técnica do projeto.
                </p>
                <p>
                    O objetivo é <b>reduzir tarefas repetitivas e minimizar inconsistências entre cálculo,
                    desenho e documentação</b>, sem retirar do profissional a responsabilidade pelas
                    decisões técnicas. O projetista permanece no controle das informações e pode revisar
                    as definições antes da geração final do projeto.
                </p>
                <p><b>AutoElétrica — automação aplicada ao desenvolvimento de projetos elétricos.</b></p>
                <div class="ae-info-highlight">
                    Comece um novo projeto ou continue um projeto salvo. Para acessar a plataforma,
                    selecione <b>Login</b> no menu lateral.
                </div>
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

        # Rev.125: inicia o OIDC no callback do botão. Isso evita misturar a
        # navegação externa do st.login() com a fase normal de renderização da
        # página e segue o fluxo recomendado pelo Streamlit para widgets.
        def _iniciar_login_google():
            try:
                # Pré-validação mínima da configuração publicada. Não expõe
                # valores secretos e impede uma chamada OIDC incompleta.
                auth_cfg = st.secrets.get("auth", {})
                obrigatorios = (
                    "redirect_uri",
                    "cookie_secret",
                    "client_id",
                    "client_secret",
                    "server_metadata_url",
                )
                if not all(str(auth_cfg.get(chave, "") or "").strip() for chave in obrigatorios):
                    raise RuntimeError("Configuração OIDC incompleta")

                st.session_state.pop("erro_login_google", None)
                st.login()
            except Exception:
                # Nunca mostrar Secrets, stack trace ou mensagem do provedor.
                st.session_state.erro_login_google = True

        st.button(
            "Entrar com Google",
            key="entrar_google",
            use_container_width=True,
            on_click=_iniciar_login_google,
        )

        if st.session_state.pop("erro_login_google", False):
            st.error(
                "Login com Google temporariamente indisponível. "
                "Utilize seu e-mail e senha para acessar o sistema."
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
