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
    """Retorna exclusivamente uma chave administrativa do Supabase.

    Rev.189: aceita a Secret Key atual (sb_secret_...) ou a legacy service_role.
    Rejeita explicitamente chaves publishable/anon para evitar que a área ADMIN
    pareça configurada mas continue submetida ao RLS.
    """
    try:
        bloco = st.secrets["supabase"]
        for nome in ("secret_key", "service_role_key", "service_key"):
            valor = str(bloco.get(nome, "") or "").strip()
            if valor:
                return valor
    except Exception:
        pass

    return str(
        os.getenv("SUPABASE_SECRET_KEY", "")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        or ""
    ).strip()


def _validar_chave_admin_supabase(chave):
    """Falha cedo quando a chave configurada é pública/anon."""
    import base64
    import json

    k = str(chave or "").strip()
    if not k:
        raise RuntimeError("Chave administrativa do Supabase não configurada.")
    if k.startswith("sb_publishable_"):
        raise RuntimeError(
            "A chave configurada em [supabase] é PUBLISHABLE e não pode ser usada "
            "na área administrativa. Use a Secret Key (sb_secret_...) ou a legacy "
            "service_role."
        )
    if k.startswith("sb_secret_"):
        return

    # Chaves legacy são JWTs. Confere o claim role sem imprimir/expor a chave.
    if k.count(".") == 2:
        try:
            payload = k.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            dados = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
            role = str(dados.get("role", "") or "").strip().lower()
            if role != "service_role":
                raise RuntimeError(
                    "A chave administrativa configurada é uma chave legacy, mas o "
                    f"papel identificado é '{role or 'desconhecido'}'. Configure a "
                    "legacy service_role ou, preferencialmente, uma Secret Key."
                )
            return
        except RuntimeError:
            raise
        except Exception:
            pass


@st.cache_resource
def obter_supabase_admin():
    """Cliente isolado para operações ADMIN, sem sessão de usuário.

    Rev.189: persist_session=False e auto_refresh_token=False impedem que um JWT de
    usuário substitua o Authorization administrativo. Isso garante que a Secret
    Key/service_role permaneça responsável pelas operações e bypass do RLS.
    """
    try:
        from supabase import create_client, ClientOptions
    except Exception as exc:
        raise RuntimeError(
            "Falha ao carregar o cliente Supabase para a área administrativa."
        ) from exc

    url, _ = obter_credenciais_supabase()
    admin_key = obter_credencial_supabase_admin()
    if not url or not admin_key:
        raise RuntimeError(
            "A área administrativa precisa da Secret Key/Service Role Key do Supabase. "
            "No Streamlit Cloud, adicione em [supabase] a entrada "
            "secret_key = \"SUA_SECRET_KEY\" (recomendado) ou "
            "service_role_key = \"SUA_SERVICE_ROLE_KEY\". "
            "Não substitua a chave pública existente."
        )

    _validar_chave_admin_supabase(admin_key)

    opcoes = ClientOptions(
        auto_refresh_token=False,
        persist_session=False,
    )
    return create_client(url, admin_key, options=opcoes)
