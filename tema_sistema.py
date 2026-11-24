"""Tema visual do sistema logado e componentes do menu lateral (13.6.369).

Inspirado no layout "Sidebar Dashboard" (Figma Community): cartão de
usuário no topo, seções com títulos em caixa alta, itens de navegação
com destaque no item ativo e rodapé com a ação de sair.

Somente apresentação: nenhuma lógica de cálculo, DXF ou QDC é tocada.
"""

import html
import re

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


CHAVE_MENU_RECOLHIDO = "ae_menu_recolhido"

# Containers (chaves) cujos botões seguem o visual de item de navegação.
_CONTAINERS_NAV = ("ae_nav", "ae_tema", "ae_recolher", "ae_obras_ic")

_ICONES_ETAPAS = (
    ("parâmetro", "settings"),
    ("parametro", "settings"),
    ("carga", "table_chart"),
    ("qdc", "bolt"),
    ("interruptor", "lightbulb"),
    ("tomada", "electrical_services"),
    ("materia", "inventory_2"),
    ("gerar", "architecture"),
    ("3d", "view_in_ar"),
    ("visualiza", "view_in_ar"),
)


def tema_claro_ativo():
    return bool(st.session_state.get(CHAVE_TEMA_CLARO, False))


def menu_recolhido():
    return bool(st.session_state.get(CHAVE_MENU_RECOLHIDO, False))


def rotulo_etapa(nome):
    """Nome da etapa sem o emoji inicial (o valor da etapa não muda)."""
    return re.sub(r"^[^\w]+", "", str(nome or "")).strip() or str(nome)


def icone_etapa(nome):
    """Ícone Material (uma cor só) para a etapa."""
    baixo = rotulo_etapa(nome).lower()
    for trecho, icone in _ICONES_ETAPAS:
        if trecho in baixo:
            return f":material/{icone}:"
    return ":material/chevron_right:"


def _regras_navegacao():
    css = []
    for c in _CONTAINERS_NAV:
        base = f'section[data-testid="stSidebar"] .st-key-{c} [data-testid="stButton"] button'
        css.append(f"""
        section[data-testid="stSidebar"] .st-key-{c} [data-testid="stVerticalBlock"] {{
            gap: 4px !important;
        }}
        {base} {{
            width: 100% !important;
            justify-content: flex-start !important;
            text-align: left !important;
            padding: 10px 14px !important;
            border-radius: 10px !important;
            border: 0 !important;
            box-shadow: none !important;
            background: transparent !important;
            font-weight: 500 !important;
        }}
        {base}, {base} * {{
            color: var(--ae-muted) !important;
        }}
        {base}:hover {{
            background: var(--ae-surface) !important;
        }}
        {base}:hover * {{
            color: var(--ae-text) !important;
        }}
        {base}[kind="primary"],
        {base}[data-testid="stBaseButton-primary"] {{
            background: var(--ae-surface-2) !important;
            box-shadow: inset 3px 0 0 var(--ae-blue) !important;
            font-weight: 600 !important;
        }}
        {base}[kind="primary"] *,
        {base}[data-testid="stBaseButton-primary"] * {{
            color: var(--ae-active-text) !important;
        }}""")
    return "\n".join(css)


_CSS_SAIR_BASE = """
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
"""

_CSS_SAIR = _CSS_SAIR_BASE + _CSS_SAIR_BASE.replace("ae_logout", "ae_apagar")

# Botão "Cadastrar projeto" (formulário do Gerenciador de Obras): discreto,
# no mesmo estilo dos itens do menu.
_CSS_OBRAS = """
        section[data-testid="stSidebar"] .st-key-ae_obras [data-testid="stFormSubmitButton"] button {
            width: 100% !important;
            justify-content: flex-start !important;
            padding: 10px 14px !important;
            background: transparent !important;
            border: 1px solid var(--ae-line) !important;
            border-radius: 10px !important;
            box-shadow: none !important;
            font-weight: 500 !important;
        }
        section[data-testid="stSidebar"] .st-key-ae_obras [data-testid="stFormSubmitButton"] button,
        section[data-testid="stSidebar"] .st-key-ae_obras [data-testid="stFormSubmitButton"] button * {
            color: var(--ae-text) !important;
        }
        section[data-testid="stSidebar"] .st-key-ae_obras [data-testid="stFormSubmitButton"] button:hover {
            background: var(--ae-surface) !important;
        }
"""

# Confirmação de exclusão: "Sim, apagar" (vermelho) e "Cancelar" (neutro),
# no mesmo padrão ghost do menu (as chaves começam com esses prefixos).
_CSS_CONFIRMAR = """
        section[data-testid="stSidebar"] [class*="st-key-confirmar_apagar_"] [data-testid="stButton"] button,
        section[data-testid="stSidebar"] [class*="st-key-cancelar_apagar_"] [data-testid="stButton"] button {
            width: 100% !important;
            padding: 10px 8px !important;
            background: transparent !important;
            border-radius: 10px !important;
            box-shadow: none !important;
            font-weight: 500 !important;
        }
        section[data-testid="stSidebar"] [class*="st-key-confirmar_apagar_"] [data-testid="stButton"] button {
            border: 1px solid var(--ae-danger) !important;
        }
        section[data-testid="stSidebar"] [class*="st-key-confirmar_apagar_"] [data-testid="stButton"] button,
        section[data-testid="stSidebar"] [class*="st-key-confirmar_apagar_"] [data-testid="stButton"] button * {
            color: var(--ae-danger) !important;
        }
        section[data-testid="stSidebar"] [class*="st-key-confirmar_apagar_"] [data-testid="stButton"] button:hover {
            background: var(--ae-danger-bg) !important;
        }
        section[data-testid="stSidebar"] [class*="st-key-cancelar_apagar_"] [data-testid="stButton"] button {
            border: 1px solid var(--ae-line) !important;
        }
        section[data-testid="stSidebar"] [class*="st-key-cancelar_apagar_"] [data-testid="stButton"] button,
        section[data-testid="stSidebar"] [class*="st-key-cancelar_apagar_"] [data-testid="stButton"] button * {
            color: var(--ae-text) !important;
        }
        section[data-testid="stSidebar"] [class*="st-key-cancelar_apagar_"] [data-testid="stButton"] button:hover {
            background: var(--ae-surface) !important;
        }
        section[data-testid="stSidebar"] .st-key-ae_obras [data-testid="stFormSubmitButton"] {
            width: 100% !important;
        }
"""

# Ícones sólidos, de uma cor só (herdam a cor do texto do botão).
_CSS_ICONES = """
        section[data-testid="stSidebar"] [data-testid="stIconMaterial"] {
            font-variation-settings: 'FILL' 1, 'wght' 500 !important;
            font-size: 1.4rem !important;
            color: inherit !important;
        }
"""

# Menu recolhido: somente ícones.
_CSS_RECOLHIDO = """
        section[data-testid="stSidebar"] {
            width: 84px !important;
            min-width: 84px !important;
            max-width: 84px !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding-left: 0 !important;
            padding-right: 0 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            padding-left: 10px !important;
            padding-right: 10px !important;
        }
        section[data-testid="stSidebar"] .ae-secao,
        section[data-testid="stSidebar"] .st-key-ae_obras,
        section[data-testid="stSidebar"] .st-key-ae_admin,
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            display: none !important;
        }
        section[data-testid="stSidebar"] .ae-user {
            justify-content: center;
            padding-left: 0;
            padding-right: 0;
        }
        section[data-testid="stSidebar"] .ae-user-info {
            display: none;
        }
        section[data-testid="stSidebar"] .ae-versao-mini {
            display: block !important;
        }
        section[data-testid="stSidebar"] .st-key-ae_nav [data-testid="stButton"] button,
        section[data-testid="stSidebar"] .st-key-ae_tema [data-testid="stButton"] button,
        section[data-testid="stSidebar"] .st-key-ae_recolher [data-testid="stButton"] button,
        section[data-testid="stSidebar"] .st-key-ae_obras_ic [data-testid="stButton"] button,
        section[data-testid="stSidebar"] .st-key-ae_logout [data-testid="stButton"] button {
            justify-content: center !important;
            padding: 12px 0 !important;
        }
        section[data-testid="stSidebar"] .st-key-ae_nav button [data-testid="stMarkdownContainer"],
        section[data-testid="stSidebar"] .st-key-ae_tema button [data-testid="stMarkdownContainer"],
        section[data-testid="stSidebar"] .st-key-ae_recolher button [data-testid="stMarkdownContainer"],
        section[data-testid="stSidebar"] .st-key-ae_obras_ic button [data-testid="stMarkdownContainer"],
        section[data-testid="stSidebar"] .st-key-ae_logout button [data-testid="stMarkdownContainer"] {
            display: none !important;
        }
"""


# Área principal: mesmo padrão visual do menu, sempre no tema claro
# (independe do alternador de tema do menu). Somente apresentação.
_CSS_PRINCIPAL = """
        :root {
            --ae-m-card: #ffffff;
            --ae-m-line: rgba(27,40,64,.12);
            --ae-m-line-strong: rgba(27,40,64,.22);
            --ae-m-ink: #1b2840;
            --ae-m-muted: #667389;
            --ae-m-surface: #eef2fa;
            --ae-m-blue: #2e63e6;
            --ae-m-blue-dark: #2050cc;
        }

        /* ---------- ícones Material (uma cor só, herdam a cor do texto) ---------- */
        [data-testid="stMain"] [data-testid="stIconMaterial"] {
            font-variation-settings: 'FILL' 1, 'wght' 500 !important;
            color: inherit !important;
        }

        /* ---------- títulos e textos ---------- */
        [data-testid="stMain"] h1,
        [data-testid="stMain"] h2,
        [data-testid="stMain"] h3,
        [data-testid="stMain"] h4 {
            color: var(--ae-m-ink) !important;
            letter-spacing: -0.01em;
        }
        [data-testid="stMain"] h1 { font-weight: 800 !important; }
        [data-testid="stMain"] h2,
        [data-testid="stMain"] h3 { font-weight: 700 !important; }
        [data-testid="stMain"] [data-testid="stCaptionContainer"],
        [data-testid="stMain"] [data-testid="stCaptionContainer"] * {
            color: var(--ae-m-muted) !important;
        }
        [data-testid="stMain"] [data-testid="stWidgetLabel"] p {
            color: var(--ae-m-ink) !important;
            font-weight: 500 !important;
            font-size: .9rem !important;
        }
        [data-testid="stMain"] hr {
            border-color: var(--ae-m-line) !important;
        }

        /* ---------- campos: caixa única, branca, cantos arredondados ---------- */
        [data-testid="stMain"] [data-testid="stTextInputRootElement"],
        [data-testid="stMain"] [data-testid="stNumberInputContainer"],
        [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"],
        [data-testid="stMain"] [data-baseweb="textarea"] {
            background: var(--ae-m-card) !important;
            border: 1px solid var(--ae-m-line) !important;
            border-radius: 10px !important;
            box-shadow: none !important;
            color: var(--ae-m-ink) !important;
        }
        [data-testid="stMain"] [data-testid="stTextInputRootElement"] *,
        [data-testid="stMain"] [data-testid="stNumberInputContainer"] *,
        [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] *,
        [data-testid="stMain"] [data-baseweb="textarea"] * {
            background: transparent !important;
            border-color: transparent !important;
            box-shadow: none !important;
            color: var(--ae-m-ink) !important;
        }
        [data-testid="stMain"] [data-testid="stTextInputRootElement"]:focus-within,
        [data-testid="stMain"] [data-testid="stNumberInputContainer"]:focus-within,
        [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"]:focus-within,
        [data-testid="stMain"] [data-baseweb="textarea"]:focus-within {
            border-color: var(--ae-m-blue) !important;
            box-shadow: 0 0 0 3px rgba(46,99,230,.15) !important;
        }
        [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] svg {
            fill: var(--ae-m-muted) !important;
        }

        /* ---------- botões ---------- */
        [data-testid="stMain"] [data-testid="stButton"] button,
        [data-testid="stMain"] [data-testid="stFormSubmitButton"] button,
        [data-testid="stMain"] [data-testid="stDownloadButton"] button {
            border-radius: 10px !important;
            font-weight: 600 !important;
            box-shadow: none !important;
            background: var(--ae-m-card) !important;
            border: 1px solid var(--ae-m-line) !important;
        }
        [data-testid="stMain"] [data-testid="stButton"] button,
        [data-testid="stMain"] [data-testid="stButton"] button *,
        [data-testid="stMain"] [data-testid="stFormSubmitButton"] button,
        [data-testid="stMain"] [data-testid="stFormSubmitButton"] button *,
        [data-testid="stMain"] [data-testid="stDownloadButton"] button,
        [data-testid="stMain"] [data-testid="stDownloadButton"] button * {
            color: var(--ae-m-ink) !important;
        }
        [data-testid="stMain"] [data-testid="stButton"] button:hover,
        [data-testid="stMain"] [data-testid="stFormSubmitButton"] button:hover,
        [data-testid="stMain"] [data-testid="stDownloadButton"] button:hover {
            background: var(--ae-m-surface) !important;
            border-color: var(--ae-m-line-strong) !important;
        }
        /* botões principais (primary): azul do sistema */
        [data-testid="stMain"] button[kind="primary"],
        [data-testid="stMain"] button[data-testid="stBaseButton-primary"],
        [data-testid="stMain"] button[data-testid="stBaseButton-primaryFormSubmit"] {
            background: linear-gradient(90deg, var(--ae-m-blue), var(--ae-m-blue-dark)) !important;
            border: 0 !important;
        }
        [data-testid="stMain"] button[kind="primary"],
        [data-testid="stMain"] button[kind="primary"] *,
        [data-testid="stMain"] button[data-testid="stBaseButton-primary"],
        [data-testid="stMain"] button[data-testid="stBaseButton-primary"] *,
        [data-testid="stMain"] button[data-testid="stBaseButton-primaryFormSubmit"],
        [data-testid="stMain"] button[data-testid="stBaseButton-primaryFormSubmit"] * {
            color: #ffffff !important;
        }
        [data-testid="stMain"] button[kind="primary"]:hover,
        [data-testid="stMain"] button[data-testid="stBaseButton-primary"]:hover,
        [data-testid="stMain"] button[data-testid="stBaseButton-primaryFormSubmit"]:hover {
            background: linear-gradient(90deg, var(--ae-m-blue-dark), var(--ae-m-blue-dark)) !important;
        }

        /* ---------- cartões: expanders, formulários, tabelas, upload ---------- */
        [data-testid="stMain"] [data-testid="stExpander"] {
            background: var(--ae-m-card) !important;
            border: 1px solid var(--ae-m-line) !important;
            border-radius: 14px !important;
            overflow: hidden;
        }
        [data-testid="stMain"] [data-testid="stExpander"] details {
            border: 0 !important;
        }
        [data-testid="stMain"] [data-testid="stExpander"] summary,
        [data-testid="stMain"] [data-testid="stExpander"] summary * {
            color: var(--ae-m-ink) !important;
            font-weight: 600;
        }
        [data-testid="stMain"] [data-testid="stForm"] {
            background: var(--ae-m-card) !important;
            border: 1px solid var(--ae-m-line) !important;
            border-radius: 14px !important;
        }
        [data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 14px !important;
            border-color: var(--ae-m-line) !important;
        }
        [data-testid="stMain"] [data-testid="stDataFrame"] {
            border: 1px solid var(--ae-m-line);
            border-radius: 12px;
            overflow: hidden;
        }
        [data-testid="stMain"] [data-testid="stFileUploaderDropzone"] {
            background: var(--ae-m-card) !important;
            border: 1px dashed var(--ae-m-line-strong) !important;
            border-radius: 14px !important;
        }
        [data-testid="stMain"] [data-testid="stAlert"] {
            border-radius: 12px !important;
        }

        /* ---------- abas ---------- */
        [data-testid="stMain"] [data-baseweb="tab-list"] {
            gap: 6px;
            border-bottom: 1px solid var(--ae-m-line);
        }
        [data-testid="stMain"] [data-baseweb="tab"] {
            font-weight: 600 !important;
        }
        [data-testid="stMain"] [data-baseweb="tab-highlight"] {
            background-color: var(--ae-m-blue) !important;
        }
"""

def aplicar_tema_sistema():
    """CSS do sistema logado (menu lateral, itens de navegação)."""
    variaveis = _VARS_CLARO if tema_claro_ativo() else _VARS_ESCURO
    css = (
        _CSS_SISTEMA
        .replace("__VARS__", variaveis)
        .replace("__NAVCSS__", _regras_navegacao())
        .replace("__SAIRCSS__", _CSS_SAIR)
        .replace("__ICONCSS__", _CSS_ICONES + _CSS_OBRAS + _CSS_CONFIRMAR)
    )
    css = css.replace("</style>", _CSS_PRINCIPAL + "\n        </style>")
    if menu_recolhido():
        css = css.replace("</style>", _CSS_RECOLHIDO + "\n        </style>")
    st.markdown(css, unsafe_allow_html=True)


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

        /* ---------- sem o "<<" nativo (o recolhimento é pelo botão do menu) ---------- */
        section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
        section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {
            display: none !important;
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

        __NAVCSS__

        /* ---------- campos e botões ---------- */
        section[data-testid="stSidebar"] [data-testid="stTextInputRootElement"],
        section[data-testid="stSidebar"] [data-testid="stNumberInputContainer"],
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"],
        section[data-testid="stSidebar"] [data-baseweb="textarea"] {
            background: var(--ae-surface) !important;
            border: 1px solid var(--ae-line) !important;
            border-radius: 10px !important;
            box-shadow: none !important;
            color: var(--ae-text) !important;
        }
        /* tudo dentro da caixa fica transparente: sem anel branco duplo */
        section[data-testid="stSidebar"] [data-testid="stTextInputRootElement"] *,
        section[data-testid="stSidebar"] [data-testid="stNumberInputContainer"] *,
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] *,
        section[data-testid="stSidebar"] [data-baseweb="textarea"] * {
            background: transparent !important;
            border-color: transparent !important;
            box-shadow: none !important;
            color: var(--ae-text) !important;
        }
        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] textarea {
            background: transparent !important;
            color: var(--ae-text) !important;
            border: 0 !important;
            -webkit-text-fill-color: var(--ae-text) !important;
        }
        section[data-testid="stSidebar"] input::placeholder,
        section[data-testid="stSidebar"] textarea::placeholder {
            color: var(--ae-muted) !important;
        }
        section[data-testid="stSidebar"] [data-baseweb="select"] svg {
            fill: var(--ae-muted) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
            font-size: .8rem !important;
            color: var(--ae-muted) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stForm"] {
            border: 0 !important;
            padding: 0 !important;
            background: transparent !important;
        }
        section[data-testid="stSidebar"] [data-testid="stButton"] button,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button {
            background: linear-gradient(90deg, var(--ae-blue), var(--ae-blue-dark)) !important;
            color: #ffffff !important;
            border: 0 !important;
            border-radius: 10px !important;
            font-weight: 600;
        }
        section[data-testid="stSidebar"] [data-testid="stAlert"],
        section[data-testid="stSidebar"] [data-testid="stAlertContainer"],
        section[data-testid="stSidebar"] [data-testid="stAlert"] > div {
            background: var(--ae-alert-bg) !important;
            border: 0 !important;
            border-radius: 10px !important;
            box-shadow: none !important;
        }
        section[data-testid="stSidebar"] [data-testid="stAlert"] {
            border: 1px solid var(--ae-line) !important;
            box-shadow: inset 3px 0 0 var(--ae-danger) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stAlert"] * {
            color: var(--ae-text) !important;
            font-size: .85rem !important;
        }

        __SAIRCSS__

        __ICONCSS__

        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {
            background: #f6f8fc !important;
        }
        [data-testid="stHeader"] {
            background: transparent !important;
        }
        </style>
        """
)


def renderizar_cartao_usuario(nome, email, versao):
    """Cabeçalho do menu: avatar com iniciais, marca e dados do usuário."""
    st.markdown(
        f"""
        <div class="ae-user">
            <div class="ae-avatar">{html.escape(_iniciais(nome))}</div>
            <div class="ae-user-info">
                <div class="ae-user-role"><svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-1px;margin-right:4px"><path d="M11 21h-1l1-7H7.5c-.58 0-.57-.32-.38-.66.19-.34.05-.08.07-.12C8.48 10.94 10.42 7.54 13 3h1l-1 7h3.5c.49 0 .56.33.47.51l-.07.15C12.96 17.55 11 21 11 21z"/></svg>AutoElétrica Profissional</div>
                <div class="ae-user-name">{html.escape(str(nome or ''))}</div>
                <div class="ae-user-mail">{html.escape(str(email or ''))}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if menu_recolhido():
        # Menu estreito: a versão continua visível, em formato curto.
        st.markdown(
            f'<div class="ae-versao-mini" style="text-align:center;'
            f'font-size:.62rem;color:var(--ae-muted)">{html.escape(str(versao))}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption(f"Versão: {versao}")


def _alternar_menu():
    st.session_state[CHAVE_MENU_RECOLHIDO] = not menu_recolhido()


def _expandir_menu():
    st.session_state[CHAVE_MENU_RECOLHIDO] = False


def _alternar_tema():
    st.session_state[CHAVE_TEMA_CLARO] = not tema_claro_ativo()


def _container(chave):
    try:
        return st.container(key=chave)
    except TypeError:
        return st.container()


def renderizar_botao_recolher():
    recolhido = menu_recolhido()
    with _container("ae_recolher"):
        st.button(
            "Recolher menu" if not recolhido else "Expandir menu",
            icon=":material/chevron_right:" if recolhido else ":material/chevron_left:",
            key="ae_btn_recolher",
            help="Expandir menu" if recolhido else None,
            use_container_width=True,
            on_click=_alternar_menu,
        )


def renderizar_botao_obras_recolhido():
    """Com o menu estreito: ícone de pasta que reabre o menu (Obras)."""
    if not menu_recolhido():
        return
    with _container("ae_obras_ic"):
        st.button(
            "Obras",
            icon=":material/folder_open:",
            key="ae_btn_obras_ic",
            help="Obras (expandir menu)",
            use_container_width=True,
            on_click=_expandir_menu,
        )


def renderizar_botao_tema():
    claro = tema_claro_ativo()
    with _container("ae_tema"):
        st.button(
            "Tema escuro" if claro else "Tema claro",
            icon=":material/dark_mode:" if claro else ":material/light_mode:",
            key="ae_btn_tema",
            help=(
                ("Tema escuro" if claro else "Tema claro")
                if menu_recolhido()
                else None
            ),
            use_container_width=True,
            on_click=_alternar_tema,
        )


def container_obras():
    return _container("ae_obras")


def container_admin():
    return _container("ae_admin")


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
