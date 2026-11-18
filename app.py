import streamlit as st
import streamlit.components.v1 as components

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
from tema_sistema import (
    aplicar_tema_sistema,
    renderizar_cartao_usuario,
    titulo_secao,
    reservar_container_navegacao,
    container_rodape_sair,
)
from versao import VERSAO_SISTEMA
from admin_normativos import usuario_e_admin, renderizar_admin_normativos


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
    renderizar_cartao_usuario(
        st.session_state.user_name,
        st.session_state.user_email,
        VERSAO_SISTEMA,
    )

    # Navegação por etapas: o painel principal preenche este espaço.
    reservar_container_navegacao()

    titulo_secao("Obras")
    renderizar_gerenciador_projetos()

    if usuario_e_admin(st.session_state.user_email):
        titulo_secao("Administração")
        st.session_state["admin_normativos_aberto"] = st.toggle(
            "⚙️ Administração",
            value=bool(st.session_state.get("admin_normativos_aberto", False)),
            help="Cadastro e liberação de perfis normativos.",
        )

    titulo_secao("Conta")
    with container_rodape_sair():
        if st.button(
            "🚪 Sair / Logout",
            use_container_width=True,
        ):
            fazer_logout()
            st.rerun()

# Rev.84 — quando o usuário troca o projeto no dropdown, o Streamlit
# rerenderiza a página, mas o navegador pode manter a posição vertical.
# Executamos o scroll depois da barra lateral já ter processado a troca.
if st.session_state.pop("rev84_scroll_topo_projeto", False):
    components.html(
        """
        <script>
        (function () {
            const doc = window.parent.document;

            const candidatos = [
                doc.querySelector('[data-testid="stMain"]'),
                doc.querySelector('[data-testid="stAppViewContainer"]'),
                doc.querySelector('section.main'),
                doc.scrollingElement,
                doc.documentElement,
                doc.body
            ];

            candidatos.forEach((el) => {
                if (!el) return;
                try {
                    el.scrollTo({top: 0, left: 0, behavior: 'instant'});
                } catch (e) {
                    try { el.scrollTop = 0; } catch (_) {}
                }
            });

            try {
                window.parent.scrollTo({top: 0, left: 0, behavior: 'instant'});
            } catch (e) {
                window.parent.scrollTo(0, 0);
            }
        })();
        </script>
        """,
        height=0,
        width=0,
    )

if usuario_e_admin(st.session_state.user_email) and st.session_state.get("admin_normativos_aberto", False):
    renderizar_admin_normativos(st.session_state.user_email)
else:
    renderizar_painel_principal()
