import base64
from pathlib import Path

import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"


def _arquivo_em_base64(caminho: Path) -> str:
    if not caminho.exists():
        return ""
    return base64.b64encode(caminho.read_bytes()).decode("utf-8")


def obter_logo_base64() -> str:
    return _arquivo_em_base64(ASSETS_DIR / "logo_autoeletrica.png")


def aplicar_fundo_login():
    """Aplica o visual completo da tela de autenticação."""
    st.markdown(
        """
        <style>
        :root {
            --ae-navy: #132440;
            --ae-navy-2: #1b3153;
            --ae-blue: #245fe7;
            --ae-blue-2: #1748c8;
            --ae-text: #141821;
            --ae-muted: #697386;
            --ae-border: #d9dee8;
        }

        html, body, [class*="css"] {
            font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont,
                "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        [data-testid="stAppViewContainer"] {
            background-color: #fbfbfb;
            background-image:
                linear-gradient(135deg, rgba(224,228,235,.44) 8%, transparent 8%, transparent 50%, rgba(224,228,235,.44) 50%, rgba(224,228,235,.44) 58%, transparent 58%, transparent),
                linear-gradient(45deg, rgba(234,237,242,.38) 8%, transparent 8%, transparent 50%, rgba(234,237,242,.38) 50%, rgba(234,237,242,.38) 58%, transparent 58%, transparent);
            background-size: 108px 108px;
            background-position: 0 0, 54px 54px;
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stToolbar"] {
            visibility: hidden;
            height: 0;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, var(--ae-navy) 0%, #172b49 100%);
            border-right: 0;
            min-width: 308px;
            max-width: 308px;
        }

        [data-testid="stSidebar"] > div:first-child {
            width: 308px;
        }

        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding-top: 0.8rem;
        }

        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span {
            color: #f7f9fd;
        }

        [data-testid="stSidebar"] [role="radiogroup"] {
            gap: .6rem;
        }

        [data-testid="stSidebar"] [data-baseweb="radio"] {
            background: transparent;
            border-radius: 10px;
            padding: .8rem .9rem;
            transition: all .15s ease;
        }

        [data-testid="stSidebar"] [data-baseweb="radio"]:hover {
            background: rgba(255,255,255,.08);
        }

        [data-testid="stSidebar"] [data-baseweb="radio"]:has(input:checked) {
            background: linear-gradient(90deg, rgba(36,95,231,.92), rgba(45,86,179,.82));
            box-shadow: 0 8px 18px rgba(0,0,0,.12);
        }

        [data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child {
            display: none;
        }

        .ae-brand {
            padding: 1.5rem 1rem 1.35rem 1rem;
            text-align: center;
        }

        .ae-brand img {
            width: 190px;
            max-width: 100%;
            display: block;
            margin: 0 auto;
        }

        .ae-brand-subtitle {
            color: #4f90ff;
            font-size: 1.02rem;
            font-weight: 500;
            margin-top: .1rem;
        }

        .ae-sidebar-separator {
            height: 1px;
            background: rgba(255,255,255,.08);
            margin: .2rem .5rem 1rem .5rem;
        }

        .ae-sidebar-footer {
            position: fixed;
            left: 30px;
            bottom: 28px;
            width: 245px;
            color: rgba(255,255,255,.68);
            font-size: .83rem;
            line-height: 1.65;
        }

        .ae-login-title {
            text-align: center;
            margin: 0;
            color: var(--ae-text);
            font-size: 2.05rem;
            font-weight: 800;
            letter-spacing: -.02em;
        }

        .ae-login-subtitle {
            text-align: center;
            color: #4a5568;
            margin-top: .35rem;
            margin-bottom: 1.55rem;
            font-size: 1rem;
        }

        .ae-lock {
            width: 76px;
            height: 76px;
            margin: 0 auto 1rem auto;
            border-radius: 50%;
            background: radial-gradient(circle at 35% 25%, #264a94, #142b62 70%);
            display: grid;
            place-items: center;
            box-shadow: 0 12px 25px rgba(20,43,98,.18);
            color: white;
            font-size: 2.1rem;
        }

        [data-testid="stMainBlockContainer"] {
            padding-top: 5.5rem;
            padding-bottom: 3rem;
            max-width: 100%;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255,255,255,.97);
            border: 1px solid rgba(211,217,226,.72) !important;
            border-radius: 22px !important;
            box-shadow: 0 18px 44px rgba(28,39,55,.13), 0 2px 8px rgba(28,39,55,.06);
        }

        [data-testid="stVerticalBlockBorderWrapper"] > div {
            padding: 1.35rem 1.05rem .95rem 1.05rem;
        }

        [data-testid="stTextInput"] label p {
            color: #161a22;
            font-weight: 600;
            font-size: .93rem;
        }

        [data-testid="stTextInput"] input {
            height: 50px;
            border-radius: 9px;
            border-color: #d4dae4;
            background: #fff;
            font-size: .96rem;
        }

        [data-testid="stFormSubmitButton"] button {
            height: 54px;
            border: 0;
            border-radius: 9px;
            background: linear-gradient(90deg, var(--ae-blue), var(--ae-blue-2));
            color: white;
            font-size: 1rem;
            font-weight: 700;
            box-shadow: 0 8px 18px rgba(36,95,231,.22);
        }

        [data-testid="stFormSubmitButton"] button:hover {
            border: 0;
            color: white;
            filter: brightness(1.03);
        }

        .ae-ou {
            display: flex;
            align-items: center;
            gap: .8rem;
            color: #697386;
            margin: .7rem 0;
            font-size: .9rem;
        }

        .ae-ou:before, .ae-ou:after {
            content: "";
            flex: 1;
            height: 1px;
            background: #e0e4eb;
        }

        .ae-info-card {
            background: rgba(255,255,255,.96);
            border: 1px solid #e2e6ed;
            border-radius: 18px;
            padding: 1.5rem 1.6rem;
            box-shadow: 0 15px 35px rgba(28,39,55,.08);
        }

        @media (max-width: 900px) {
            [data-testid="stSidebar"] {
                min-width: 260px;
                max-width: 260px;
            }
            [data-testid="stSidebar"] > div:first-child {
                width: 260px;
            }
            .ae-sidebar-footer {
                display: none;
            }
            [data-testid="stMainBlockContainer"] {
                padding-top: 2rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
