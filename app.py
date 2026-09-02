import streamlit as st

from config import (
    configurar_pagina,
    obter_supabase,
)

from auth import (
    inicializar_estado_sessao,
    renderizar_pagina_login,
    fazer_logout,
    sincronizar_login_google,
)

from projetos import renderizar_gerenciador_projetos
from painel import renderizar_painel_principal
from tema_login import aplicar_fundo_login
from versao import VERSAO_SISTEMA


def aplicar_tema_sistema():
    """Aplica o tema do sistema logado sem depender de outra função importada."""
    st.markdown(
        """
        <style>
        :root {
            --ae-navy: #1b2840;
            --ae-blue: #2e63e6;
            --ae-blue-dark: #2050cc;
        }

        section[data-testid="stSidebar"] {
            background: var(--ae-navy) !important;
            border-right: 0 !important;
        }
        section[data-testid="stSidebar"] > div:first-child,
        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            background: var(--ae-navy) !important;
        }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] small,
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            color: #f4f7fd !important;
        }
        section[data-testid="stSidebar"] hr {
            border-color: rgba(255,255,255,.18) !important;
        }
        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] textarea,
        section[data-testid="stSidebar"] [data-baseweb="select"] > div {
            background: #ffffff !important;
            color: #1b2840 !important;
        }
        section[data-testid="stSidebar"] input::placeholder,
        section[data-testid="stSidebar"] textarea::placeholder {
            color: #77839a !important;
        }
        section[data-testid="stSidebar"] [data-testid="stButton"] button,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button {
            background: linear-gradient(90deg, var(--ae-blue), var(--ae-blue-dark)) !important;
            color: #ffffff !important;
            border: 1px solid rgba(255,255,255,.12) !important;
            border-radius: 9px !important;
        }
        section[data-testid="stSidebar"] [data-testid="stAlert"] {
            background: rgba(255,255,255,.10) !important;
            border: 1px solid rgba(255,255,255,.13) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stAlert"] * {
            color: #f4f7fd !important;
        }
        [data-testid="stAppViewContainer"] {
            background: #ffffff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# CONFIGURAÇÃO INICIAL
# ============================================================

configurar_pagina()
inicializar_estado_sessao()
sincronizar_login_google()


# ============================================================
# TESTA CONEXÃO COM SUPABASE
# ============================================================

try:
    obter_supabase()
except Exception as e:
    st.error(f"❌ Não foi possível conectar ao Supabase: {e}")
    st.stop()


# ============================================================
# TELA DE LOGIN
# ============================================================

if not st.session_state.logged_in:
    aplicar_fundo_login()
    renderizar_pagina_login()
    st.stop()


# ============================================================
# SISTEMA APÓS LOGIN
# ============================================================

aplicar_tema_sistema()

with st.sidebar:
    st.markdown("## ⚡ AutoElétrica Profissional")
    st.caption(f"🔖 Sistema: {VERSAO_SISTEMA}")
    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        f"👤 **Olá, {st.session_state.user_name}!**"
    )
    st.caption(f"📧 `{st.session_state.user_email}`")

    if st.button(
        "🚪 Sair / Logout",
        use_container_width=True,
    ):
        fazer_logout()
        st.rerun()

    renderizar_gerenciador_projetos()

renderizar_painel_principal()
