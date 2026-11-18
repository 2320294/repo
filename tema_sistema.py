"""Tema visual do sistema logado e componentes do menu lateral (13.6.354).

Inspirado no layout "Sidebar Dashboard" (Figma Community): cartão de
usuário no topo, seções com títulos em caixa alta, itens de navegação
com destaque no item ativo e rodapé com a ação de sair.

Somente apresentação: nenhuma lógica de cálculo, DXF ou QDC é tocada.
"""

import html

import streamlit as st


CHAVE_CONTAINER_NAVEGACAO = "_ae_nav_container"


def _iniciais(nome):
    partes = [p for p in str(nome or "").replace("@", " ").split() if p]
    if not partes:
        return "AE"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


CHAVE_TEMA_CLARO = "ae_tema_claro"

_VARS_ESCURO = """
            --ae-bg: #151b28;
            --ae-surface: #1f2738;
            --ae-surface-2: #283148;
            --ae-line: rgba(255,255,255,.09);
            --ae-border-right: transparent;
            --ae-text: #e8ecf4;
            --ae-muted: #8d97ab;
            --ae-active-text: #ffffff;
            --ae-blue: #2e63e6;
            --ae-blue-dark: #2050cc;
            --ae-danger: #f0817f;
            --ae-danger-bg: rgba(240,129,127,.12);
            --ae-form-bg: rgba(255,255,255,.02);
            --ae-alert-bg: rgba(255,255,255,.07);
"""

_VARS_CLARO = """
            --ae-bg: #f6f8fc;
            --ae-surface: #e9edf6;
            --ae-surface-2: #dde4f3;
            --ae-line: rgba(27,40,64,.12);
            --ae-border-right: rgba(27,40,64,.10);
            --ae-text: #1b2840;
            --ae-muted: #667389;
            --ae-active-text: #1b2840;
            --ae-blue: #2e63e6;
            --ae-blue-dark: #2050cc;
            --ae-danger: #d64545;
            --ae-danger-bg: rgba(214,69,69,.10);
            --ae-form-bg: #ffffff;
            --ae-alert-bg: #e9edf6;
"""


def tema_claro_ativo():
    return bool(st.session_state.get(CHAVE_TEMA_CLARO, False))


def aplicar_tema_sistema():
    """CSS do sistema logado (menu lateral, itens de navegação)."""
    variaveis = _VARS_CLARO if tema_claro_ativo() else _VARS_ESCURO
    st.markdown(
        _CSS_SISTEMA.replace("__VARS__", variaveis),
        unsafe_allow_html=True,
    )


_CSS_SISTEMA = (
        """
        <style>
        :root {
__VARS__
        }

        /* ---------- container do menu ---------- */
        section[data-testid="stSidebar"],
        section[data-testid="stSidebar"] > div:first-child,
        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            background: var(--ae-bg) !important;
            border-right: 0 !important;
        }
        section[data-testid="stSidebar"] {
            border-right: 1px solid var(--ae-border-right) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding-top: .5rem;
        }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] small,
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            color: var(--ae-text) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {
            color: var(--ae-muted) !important;
        }
        section[data-testid="stSidebar"] hr {
            border-color: var(--ae-line) !important;
            margin: .9rem 0 !important;
        }
        section[data-testid="stSidebar"] h3 {
            font-size: .95rem !important;
            font-weight: 600 !important;
            margin: 0 0 .4rem 0 !important;
            padding: 0 !important;
        }

        /* ---------- cartão de usuário ---------- */
        .ae-user {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 6px 4px 14px 4px;
            border-bottom: 1px solid var(--ae-line);
            margin-bottom: 4px;
        }
        .ae-avatar {
            flex: 0 0 auto;
            width: 46px;
            height: 46px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 1rem;
            color: #ffffff;
            background: linear-gradient(135deg, #2e63e6, #7b5cf0);
        }
        .ae-user-info { min-width: 0; }
        .ae-user-role {
            font-size: .66rem;
            letter-spacing: .09em;
            text-transform: uppercase;
            color: var(--ae-muted) !important;
            line-height: 1.2;
        }
        .ae-user-name {
            font-size: 1.02rem;
            font-weight: 600;
            color: var(--ae-text) !important;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            line-height: 1.35;
        }
        .ae-user-mail {
            font-size: .74rem;
            color: var(--ae-muted) !important;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        /* ---------- títulos de seção ---------- */
        .ae-secao {
            font-size: .68rem;
            letter-spacing: .1em;
            text-transform: uppercase;
            color: var(--ae-muted) !important;
            margin: 1rem 0 .45rem 6px;
            font-weight: 600;
        }

        /* ---------- navegação por etapas (botões) ---------- */
        section[data-testid="stSidebar"] .st-key-ae_nav [data-testid="stVerticalBlock"] {
            gap: 4px !important;
        }
        section[data-testid="stSidebar"] .st-key-ae_nav [data-testid="stButton"] button {
            width: 100% !important;
            justify-content: flex-start !important;
            text-align: left !important;
            padding: 10px 14px !important;
            border-radius: 10px !important;
            border: 0 !important;
            box-shadow: none !important;
            background: transparent !important;
            font-weight: 500 !important;
        }
        section[data-testid="stSidebar"] .st-key-ae_nav [data-testid="stButton"] button,
        section[data-testid="stSidebar"] .st-key-ae_nav [data-testid="stButton"] button * {
            color: var(--ae-muted) !important;
        }
        section[data-testid="stSidebar"] .st-key-ae_nav [data-testid="stButton"] button:hover {
            background: var(--ae-surface) !important;
        }
        section[data-testid="stSidebar"] .st-key-ae_nav [data-testid="stButton"] button:hover * {
            color: var(--ae-text) !important;
        }
        /* item ativo = botão primary */
        section[data-testid="stSidebar"] .st-key-ae_nav [data-testid="stButton"] button[kind="primary"],
        section[data-testid="stSidebar"] .st-key-ae_nav [data-testid="stButton"] button[data-testid="stBaseButton-primary"] {
            background: var(--ae-surface-2) !important;
            box-shadow: inset 3px 0 0 var(--ae-blue) !important;
            font-weight: 600 !important;
        }
        section[data-testid="stSidebar"] .st-key-ae_nav [data-testid="stButton"] button[kind="primary"] *,
        section[data-testid="stSidebar"] .st-key-ae_nav [data-testid="stButton"] button[data-testid="stBaseButton-primary"] * {
            color: var(--ae-active-text) !important;
        }

        /* ---------- campos e botões ---------- */
        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] textarea,
        section[data-testid="stSidebar"] [data-baseweb="select"] > div {
            background: var(--ae-surface) !important;
            color: var(--ae-text) !important;
            border: 1px solid var(--ae-line) !important;
            border-radius: 10px !important;
        }
        section[data-testid="stSidebar"] input::placeholder,
        section[data-testid="stSidebar"] textarea::placeholder {
            color: var(--ae-muted) !important;
        }
        section[data-testid="stSidebar"] [data-baseweb="select"] svg {
            fill: var(--ae-muted) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stForm"] {
            border: 1px solid var(--ae-line) !important;
            border-radius: 12px !important;
            background: var(--ae-form-bg);
        }
        section[data-testid="stSidebar"] [data-testid="stButton"] button,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button {
            background: linear-gradient(90deg, var(--ae-blue), var(--ae-blue-dark)) !important;
            color: #ffffff !important;
            border: 0 !important;
            border-radius: 10px !important;
            font-weight: 600;
        }
        section[data-testid="stSidebar"] [data-testid="stAlert"] {
            background: var(--ae-alert-bg) !important;
            border: 1px solid var(--ae-line) !important;
            border-radius: 10px !important;
        }
        section[data-testid="stSidebar"] [data-testid="stAlert"] * {
            color: var(--ae-text) !important;
        }

        /* ---------- rodapé: sair ---------- */
        section[data-testid="stSidebar"] .st-key-ae_logout [data-testid="stButton"] button {
            background: transparent !important;
            border: 0 !important;
            justify-content: flex-start !important;
            padding: 10px 14px !important;
            box-shadow: none !important;
        }
        section[data-testid="stSidebar"] .st-key-ae_logout [data-testid="stButton"] button,
        section[data-testid="stSidebar"] .st-key-ae_logout [data-testid="stButton"] button * {
            color: var(--ae-danger) !important;
        }
        section[data-testid="stSidebar"] .st-key-ae_logout [data-testid="stButton"] button:hover {
            background: var(--ae-danger-bg) !important;
        }

        [data-testid="stAppViewContainer"] {
            background: #ffffff !important;
        }
        </style>
        """
)


def renderizar_alternador_tema():
    """Alternador entre menu escuro (padrão) e claro."""
    st.toggle(
        "☀️ Tema claro",
        key=CHAVE_TEMA_CLARO,
        help="Alterna o menu lateral entre o visual escuro e o claro.",
    )


def renderizar_cartao_usuario(nome, email, versao):
    """Cabeçalho do menu: avatar com iniciais, marca e dados do usuário."""
    st.markdown(
        f"""
        <div class="ae-user">
            <div class="ae-avatar">{html.escape(_iniciais(nome))}</div>
            <div class="ae-user-info">
                <div class="ae-user-role">⚡ AutoElétrica Profissional</div>
                <div class="ae-user-name">{html.escape(str(nome or ''))}</div>
                <div class="ae-user-mail">{html.escape(str(email or ''))}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Versão: {versao}")


def titulo_secao(texto):
    st.markdown(
        f'<div class="ae-secao">{html.escape(texto)}</div>',
        unsafe_allow_html=True,
    )


def reservar_container_navegacao():
    """Reserva, na posição atual do menu, o espaço da navegação por etapas.

    O painel principal é executado depois do menu; ele preenche este
    container (ver painel._navegacao_etapas).
    """
    st.session_state[CHAVE_CONTAINER_NAVEGACAO] = st.container()


def container_botoes_navegacao():
    """Container com chave própria para estilizar os botões de etapa."""
    try:
        return st.container(key="ae_nav")
    except TypeError:
        return st.container()


def container_rodape_sair():
    """Container com chave própria para estilizar o botão de sair."""
    try:
        return st.container(key="ae_logout")
    except TypeError:
        # Streamlit antigo, sem suporte a key em container.
        return st.container()
