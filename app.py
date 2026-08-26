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
# CONEXÃO COM O SUPABASE (BLINDADA)
# ============================================================
SUPABASE_URL = ""
SUPABASE_KEY = ""

# Tenta ler de st.secrets de forma segura
try:
    if "supabase" in st.secrets:
        SUPABASE_URL = st.secrets["supabase"].get("url", "")
        SUPABASE_KEY = st.secrets["supabase"].get("key", "")
except Exception:
    pass

@st.cache_resource
def init_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

if supabase is None:
    st.error("❌ **Erro de Configuração do Supabase:** As credenciais não foram encontradas no ambiente.")
    st.markdown("Certifique-se de que no painel do Streamlit Cloud (**Settings > Secrets**) o formato exato esteja assim:")
    st.code("""[supabase]
url = "https://nqnqwddvguqvvzigtbkk.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xbnF3ZGR2Z3VxdnZ6aWd0YmtrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcxNTIxNzIsImV4cCI6MjEwMjcyODE3Mn0.leyI7ibfwJkm1ah3ny9SbahhieIfQR7jFMQoyhsl9kc"
""", language="toml")
    st.stop()
