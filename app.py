import streamlit as st

from config import (
    configurar_pagina,
    obter_supabase
)

from auth import (
    inicializar_estado_sessao,
    renderizar_autenticacao,
    fazer_logout
)

from projetos import (
    renderizar_gerenciador_projetos
)

from painel import (
    renderizar_painel_principal
)


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
    st.error(
        f"❌ Não foi possível conectar ao Supabase: {e}"
    )
    st.stop()


# ============================================================
# BARRA LATERAL
# ============================================================

with st.sidebar:

    st.markdown(
        "## ⚡ AutoElétrica Profissional"
    )

    st.divider()

    if not st.session_state.logged_in:

        renderizar_autenticacao()

    else:

        st.markdown(
            f"👤 **Olá, "
            f"{st.session_state.user_name}!**"
        )

        st.caption(
            f"📧 `{st.session_state.user_email}`"
        )

        if st.button(
            "🚪 Sair / Logout",
            use_container_width=True
        ):
            fazer_logout()
            st.rerun()

        renderizar_gerenciador_projetos()


# ============================================================
# BLOQUEIO
# ============================================================

if not st.session_state.logged_in:

    st.warning(
        "⚠️ Faça login ou cadastre-se na barra lateral "
        "para acessar o painel."
    )

    st.stop()


# ============================================================
# PAINEL PRINCIPAL
# ============================================================

renderizar_painel_principal()
