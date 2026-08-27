import base64
from pathlib import Path

import streamlit as st


def aplicar_fundo_login():
    """
    Aplica a textura repetida somente na área principal
    enquanto o usuário não estiver logado.
    A barra lateral permanece sem essa textura.
    """
    imagem_path = (
        Path(__file__).resolve().parent
        / "assets"
        / "fundo_login.png"
    )

    if not imagem_path.exists():
        return

    imagem_base64 = base64.b64encode(
        imagem_path.read_bytes()
    ).decode("utf-8")

    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background-image:
                url("data:image/png;base64,{imagem_base64}");
            background-repeat: repeat;
            background-position: top left;
            background-size: 256px 256px;
            background-attachment: fixed;
        }}

        [data-testid="stHeader"] {{
            background: transparent;
        }}

        [data-testid="stSidebar"] {{
            background-image: none !important;
        }}

        .stMainBlockContainer {{
            background: transparent;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )
