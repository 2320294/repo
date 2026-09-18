import os
import streamlit as st


def configurar_pagina():
    st.set_page_config(
        page_title="AutoElétrica Profissional",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )


def obter_credenciais_supabase():
    """
    Lê primeiro o formato usado no Streamlit Cloud:

    [supabase]
    url = "..."
    key = "..."

    Se não encontrar, tenta variáveis de ambiente.
    """
    try:
        bloco = st.secrets["supabase"]

        url = str(
            bloco.get("url", "")
        ).strip()

        key = str(
            bloco.get("key", "")
        ).strip()

        if url and key:
            return url, key

    except Exception:
        pass

    url = os.getenv(
        "SUPABASE_URL",
        ""
    ).strip()

    key = (
        os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY",
            ""
        ).strip()
        or os.getenv(
            "SUPABASE_KEY",
            ""
        ).strip()
        or os.getenv(
            "SUPABASE_ANON_KEY",
            ""
        ).strip()
    )

    return url, key


@st.cache_resource
def obter_supabase():
    # Rev.90 — importação tardia do Supabase.
    #
    # Evita que uma incompatibilidade momentânea do pacote derrube
    # a aplicação inteira ainda no "from config import ...".
    # A importação passa a ocorrer dentro da função, protegida pelo
    # tratamento de erro já existente no app.py.
    try:
        from supabase import create_client
    except Exception as exc:
        raise RuntimeError(
            "Falha ao carregar o cliente Supabase. "
            "Verifique a instalação das dependências."
        ) from exc

    url, key = obter_credenciais_supabase()

    if not url or not key:
        raise RuntimeError(
            "As credenciais do Supabase não foram encontradas. "
            "No Streamlit Cloud configure:\n\n"
            "[supabase]\n"
            'url = "SUA_URL"\n'
            'key = "SUA_CHAVE"'
        )

    return create_client(
        url,
        key
    )


def obter_credencial_supabase_admin():
    """Retorna exclusivamente a Service Role Key para operações administrativas.

    Rev.188: não há fallback para a chave pública/anon. Perfis normativos são
    gravados apenas pelo backend Streamlit após a checagem de ADMIN.
    """
    try:
        bloco = st.secrets["supabase"]
        for nome in ("service_role_key", "service_key"):
            valor = str(bloco.get(nome, "") or "").strip()
            if valor:
                return valor
    except Exception:
        pass

    return str(os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or "").strip()


@st.cache_resource
def obter_supabase_admin():
    """Cliente servidor para a área ADMIN. Nunca expor a chave ao navegador."""
    try:
        from supabase import create_client
    except Exception as exc:
        raise RuntimeError(
            "Falha ao carregar o cliente Supabase para a área administrativa."
        ) from exc

    url, _ = obter_credenciais_supabase()
    service_key = obter_credencial_supabase_admin()
    if not url or not service_key:
        raise RuntimeError(
            "A área administrativa precisa da Service Role Key do Supabase. "
            "No Streamlit Cloud, adicione em [supabase] a entrada "
            "service_role_key = \"SUA_SERVICE_ROLE_KEY\". "
            "Não substitua a chave pública existente."
        )
    return create_client(url, service_key)
