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


def obter_fundo_login_base64() -> str:
    return _arquivo_em_base64(ASSETS_DIR / "fundo_login.png")


def aplicar_fundo_login():
    """Aplica o visual completo da tela de autenticação."""
    fundo_b64 = obter_fundo_login_base64()

    fundo_css = (
        f'background-image: url("data:image/png;base64,{fundo_b64}");'
        if fundo_b64
        else "background-color: #fbfbfb;"
    )

    st.markdown(
        f"""
        <style>
        :root {{
            --ae-navy: #1b2840;
            --ae-blue: #2e63e6;
            --ae-blue-dark: #2050cc;
            --ae-text: #171b23;
            --ae-muted: #4d596b;
            --ae-border: #d9dee7;
        }}

        html, body, [class*="css"] {{
            font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont,
                "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}

        /* Fundo da área principal: usa a imagem enviada pelo usuário. */
        [data-testid="stAppViewContainer"] {{
            background-color: #fbfbfb;
            {fundo_css}
            background-repeat: repeat;
            background-size: 410px auto;
            background-position: top left;
            min-height: 100vh;
        }}

        [data-testid="stHeader"] {{
            background: transparent;
        }}

        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"] {{
            visibility: hidden;
            height: 0;
        }}

        button[kind="header"] {{
            display: none !important;
        }}

        /* Barra lateral com a MESMA cor do fundo do arquivo do logo. */
        section[data-testid="stSidebar"] {{
            background: var(--ae-navy) !important;
            border-right: 0 !important;
            min-width: 310px !important;
            max-width: 310px !important;
            width: 310px !important;
            border-radius: 0 22px 22px 0;
            overflow: hidden;
            box-shadow: 5px 0 24px rgba(12, 25, 46, .10);
        }}

        section[data-testid="stSidebar"] > div:first-child {{
            width: 310px !important;
            background: var(--ae-navy) !important;
        }}

        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
            padding: 0 16px !important;
            background: var(--ae-navy) !important;
        }}

        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] span {{
            color: #f7f9fd;
        }}

        .ae-brand {{
            padding: 92px 6px 62px 6px;
            text-align: center;
        }}

        .ae-brand img {{
            width: 220px;
            max-width: 100%;
            display: block;
            margin: 0 auto;
            border: 0;
        }}

        .ae-brand-subtitle {{
            color: #4f8cff;
            font-size: 1.10rem;
            font-weight: 500;
            margin-top: 7px;
            letter-spacing: .01em;
        }}

        .ae-sidebar-separator {{
            display: none;
        }}

        /* Menu lateral - duas opções somente. */
        section[data-testid="stSidebar"] [role="radiogroup"] {{
            gap: 14px;
        }}

        section[data-testid="stSidebar"] [data-baseweb="radio"] {{
            background: transparent;
            border-radius: 9px;
            padding: 14px 16px;
            min-height: 60px;
            display: flex;
            align-items: center;
            transition: background .15s ease, transform .15s ease;
        }}

        section[data-testid="stSidebar"] [data-baseweb="radio"]:hover {{
            background: rgba(255,255,255,.075);
        }}

        section[data-testid="stSidebar"] [data-baseweb="radio"]:has(input:checked) {{
            background: linear-gradient(90deg, #2c5fcf 0%, #294f9f 100%);
            box-shadow: 0 10px 22px rgba(3, 13, 33, .18);
        }}

        section[data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child {{
            display: none;
        }}

        section[data-testid="stSidebar"] [data-baseweb="radio"] p {{
            font-size: 1.02rem;
            font-weight: 500;
            margin: 0;
        }}

        .ae-sidebar-footer {{
            position: fixed;
            left: 30px;
            bottom: 25px;
            width: 245px;
            color: rgba(255,255,255,.70);
            font-size: .82rem;
            line-height: 1.65;
        }}

        /* Área central. */
        [data-testid="stMainBlockContainer"] {{
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            padding-left: 4.5rem !important;
            padding-right: 4.5rem !important;
            max-width: 100% !important;
            min-height: 100vh;
        }}

        .ae-main-spacer {{
            height: 17vh;
            min-height: 135px;
        }}

        /* Card do login. */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: rgba(255,255,255,.975);
            border: 1px solid rgba(215,220,228,.88) !important;
            border-radius: 22px !important;
            box-shadow: 0 18px 44px rgba(30,40,55,.13), 0 2px 7px rgba(30,40,55,.05);
        }}

        [data-testid="stVerticalBlockBorderWrapper"] > div {{
            padding: 28px 32px 26px 32px !important;
        }}

        .ae-lock {{
            width: 76px;
            height: 76px;
            margin: 0 auto 18px auto;
            border-radius: 50%;
            background: linear-gradient(150deg, #203d80 0%, #152d65 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 12px 25px rgba(20,43,98,.16);
            position: relative;
        }}

        .ae-lock-body {{
            width: 30px;
            height: 25px;
            border: 4px solid white;
            border-radius: 6px;
            box-sizing: border-box;
            position: absolute;
            top: 36px;
        }}

        .ae-lock-body:before {{
            content: "";
            position: absolute;
            width: 19px;
            height: 18px;
            border: 4px solid white;
            border-bottom: 0;
            border-radius: 13px 13px 0 0;
            left: 2px;
            top: -19px;
            box-sizing: border-box;
        }}

        .ae-lock-body:after {{
            content: "";
            position: absolute;
            width: 4px;
            height: 7px;
            border-radius: 2px;
            background: white;
            left: 9px;
            top: 7px;
        }}


        /* Ícone da tela de cadastro. */
        .ae-user-icon {{
            width: 76px;
            height: 76px;
            margin: 0 auto 18px auto;
            border-radius: 50%;
            background: linear-gradient(150deg, #203d80 0%, #152d65 100%);
            position: relative;
            box-shadow: 0 12px 25px rgba(20,43,98,.16);
        }}

        .ae-user-head {{
            position: absolute;
            width: 20px;
            height: 20px;
            border: 3px solid white;
            border-radius: 50%;
            left: 22px;
            top: 15px;
            box-sizing: border-box;
        }}

        .ae-user-body {{
            position: absolute;
            width: 34px;
            height: 20px;
            border: 3px solid white;
            border-bottom: 0;
            border-radius: 18px 18px 0 0;
            left: 15px;
            top: 39px;
            box-sizing: border-box;
        }}

        .ae-user-plus {{
            position: absolute;
            right: 9px;
            bottom: 8px;
            width: 22px;
            height: 22px;
            border-radius: 50%;
            background: #4f8cff;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.15rem;
            line-height: 1;
            font-weight: 700;
            border: 2px solid #1b2840;
        }}

        .ae-login-title {{
            text-align: center;
            margin: 0;
            color: var(--ae-text);
            font-size: 2.05rem;
            font-weight: 800;
            letter-spacing: -.025em;
            line-height: 1.1;
        }}

        .ae-login-subtitle {{
            text-align: center;
            color: #475365;
            margin-top: 8px;
            margin-bottom: 24px;
            font-size: .99rem;
        }}

        [data-testid="stTextInput"] {{
            margin-bottom: 3px;
        }}

        [data-testid="stTextInput"] label p {{
            color: #171b23;
            font-weight: 500;
            font-size: .93rem;
        }}

        [data-testid="stTextInput"] input {{
            min-height: 51px;
            border-radius: 9px;
            border-color: #d3d9e3;
            background: #fff;
            font-size: .96rem;
            padding-left: 14px;
        }}

        [data-testid="stTextInput"] input:focus {{
            border-color: #7ca2ff;
            box-shadow: 0 0 0 1px #7ca2ff;
        }}

        [data-testid="stFormSubmitButton"] button {{
            height: 56px;
            border: 0 !important;
            border-radius: 8px;
            background: linear-gradient(90deg, var(--ae-blue), var(--ae-blue-dark));
            color: white !important;
            font-size: 1.02rem;
            font-weight: 700;
            box-shadow: 0 8px 18px rgba(36,95,231,.20);
            margin-top: 5px;
        }}

        [data-testid="stFormSubmitButton"] button:hover {{
            filter: brightness(1.035);
            transform: translateY(-1px);
        }}

        .ae-ou {{
            display: flex;
            align-items: center;
            gap: .85rem;
            color: #657084;
            margin: 15px 0 12px 0;
            font-size: .90rem;
        }}

        .ae-ou:before,
        .ae-ou:after {{
            content: "";
            flex: 1;
            height: 1px;
            background: #dfe4eb;
        }}

        .ae-google {{
            height: 49px;
            border: 1px solid #d9dee7;
            border-radius: 8px;
            background: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 11px;
            color: #171b23;
            font-size: .98rem;
            user-select: none;
        }}

        .ae-google-g {{
            font-size: 1.05rem;
            font-weight: 800;
            color: #4285f4;
        }}

        .ae-auth-switch-label {{
            text-align: center;
            color: #697487;
            font-size: .90rem;
            margin: 17px 0 7px 0;
        }}

        /* Botão de cadastro/voltar, dentro do próprio card de autenticação. */
        [data-testid="stMain"] [data-testid="stButton"] button {{
            min-height: 46px;
            border-radius: 8px;
            border: 1px solid #cdd8ef !important;
            background: #f7f9fe !important;
            color: #2757bb !important;
            font-weight: 650;
            box-shadow: none !important;
        }}

        [data-testid="stMain"] [data-testid="stButton"] button:hover {{
            background: #eef3ff !important;
            border-color: #9db7ec !important;
            color: #1949ac !important;
        }}

        /* Card de Sobre o Sistema. */
        .ae-info-card {{
            background: rgba(255,255,255,.975);
            border: 1px solid rgba(215,220,228,.88);
            border-radius: 22px;
            padding: 34px 38px;
            box-shadow: 0 18px 44px rgba(30,40,55,.12), 0 2px 7px rgba(30,40,55,.04);
            color: #1a202b;
        }}

        .ae-info-icon {{
            width: 66px;
            height: 66px;
            border-radius: 50%;
            margin: 0 auto 18px auto;
            background: linear-gradient(150deg, #203d80 0%, #152d65 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2rem;
            font-family: Georgia, serif;
            font-weight: 700;
        }}

        .ae-info-card h2 {{
            margin: 0 0 12px 0;
            text-align: center;
            font-size: 1.85rem;
            color: #171b23;
        }}

        .ae-info-card .ae-info-lead {{
            text-align: center;
            color: #4c5869;
            margin: 0 0 22px 0;
            line-height: 1.6;
        }}

        .ae-info-card p {{
            color: #3d4757;
            line-height: 1.72;
            font-size: .97rem;
            margin: 0 0 13px 0;
        }}

        .ae-info-highlight {{
            margin-top: 18px;
            padding: 14px 16px;
            border-radius: 10px;
            background: #f5f8ff;
            border: 1px solid #dce6fb;
            color: #31528d;
            line-height: 1.55;
        }}

        /* Esconde elementos que atrapalham o layout de login. */
        [data-testid="stSidebarCollapseButton"] {{
            display: none !important;
        }}

        @media (max-width: 900px) {{
            section[data-testid="stSidebar"] {{
                min-width: 255px !important;
                max-width: 255px !important;
                width: 255px !important;
            }}

            section[data-testid="stSidebar"] > div:first-child {{
                width: 255px !important;
            }}

            .ae-brand {{
                padding-top: 48px;
                padding-bottom: 36px;
            }}

            .ae-brand img {{
                width: 205px;
            }}

            .ae-sidebar-footer {{
                display: none;
            }}

            [data-testid="stMainBlockContainer"] {{
                padding-left: 1.5rem !important;
                padding-right: 1.5rem !important;
            }}

            .ae-main-spacer {{
                height: 8vh;
                min-height: 55px;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
