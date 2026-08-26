import streamlit as st
import tempfile
import os
import pandas as pd
import motores
from supabase import create_client, Client

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="AutoElétrica NBR 5410",
    page_icon="⚡",
    layout="wide"
)

# ============================================================
# CONEXÃO COM O SUPABASE (BLINDADA CONTRA ERROS DE URL)
# ============================================================
try:
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
except Exception:
    SUPABASE_URL = ""
    SUPABASE_KEY = ""

@st.cache_resource
def init_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY or "AQUI" in SUPABASE_URL:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

if supabase is None:
    st.error("❌ **Erro de Configuração do Supabase:** As credenciais de conexão não foram encontradas. Certifique-se de configurar os Secrets no painel do Streamlit Cloud (`Settings > Secrets`) com a estrutura correta:")
    st.code("""
[supabase]
url = "https://nqnqwddvguqvvzigtbkk.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xbnF3ZGR2Z3VxdnZ6aWd0YmtrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcxNTIxNzIsImV4cCI6MjEwMjcyODE3Mn0.leyI7ibfwJkm1ah3ny9SbahhieIfQR7jFMQoyhsl9kc"
    """, language="toml")
    st.stop()
