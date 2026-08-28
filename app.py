import streamlit as st

from config import (
    configurar_pagina,
    obter_supabase,
)

from auth import (
    inicializar_estado_sessao,
    renderizar_pagina_login,
    fazer_logout,
)

from projetos import renderizar_gerenciador_projetos
from painel import renderizar_painel_principal
from tema_login import aplicar_fundo_login, aplicar_tema_sistema


# ============================================================
# CONFIGURAÇÃO INICIAL
# ============================================================

configurar_pagina()
inicializar_estado_sessao()


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
    st.divider()

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
