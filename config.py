import os
import streamlit as st
from supabase import create_client, Client


def configurar_pagina():
    st.set_page_config(
        page_title="AutoElétrica Profissional",
        page_icon="⚡",
        layout="wide"
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
def obter_supabase() -> Client:
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
