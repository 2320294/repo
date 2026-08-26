import streamlit as st
import tempfile
import os
import pandas as pd
from supabase import create_client, Client
import motores

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="AutoElétrica NBR 5410",
    page_icon="⚡",
    layout="wide"
)

# ============================================================
# CREDENCIAIS DO SUPABASE
# ============================================================
SUPABASE_URL = "https://nqnwddvguqvvzigtbkk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xbnF3ZGR2Z3VxdnZ6aWd0YmtrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcxNTIxNzIsImV4cCI6MjEwMjcyODE3Mn0.leyI7ibfwJkm1ah3ny9SbahhieIfQR7jFMQoyhsl9kc"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# ============================================================
# ESTADO DE SESSÃO
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

# ============================================================
# BARRA LATERAL (AUTENTICAÇÃO E GERENCIADOR DINÂMICO DE PROJETOS)
# ============================================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/lightning-bolt.png", width=54)
    st.markdown("### AutoElétrica NBR 5410")
    st.divider()

    if not st.session_state.logged_in:
        aba_auth = st.radio("Acesso ao Sistema", ["Entrar (Login)", "Cadastrar-se"], horizontal=True)

        if aba_auth == "Entrar (Login)":
            st.subheader("🔐 Fazer Login")
            login_email = st.text_input("E-mail / Login", key="login_email")
            login_senha = st.text_input("Senha", type="password", key="login_senha")

            if st.button("Entrar", use_container_width=True):
                if not login_email or not login_senha:
                    st.warning("Preencha o e-mail e a senha.")
                else:
                    try:
                        response = supabase.table("usuarios").select("*").eq("email", login_email.strip()).execute()
                        dados_usuario = response.data

                        if dados_usuario and dados_usuario[0]["senha"] == login_senha:
                            st.session_state.logged_in = True
                            st.session_state.user_email = dados_usuario[0]["email"]
                            st.session_state.user_name = dados_usuario[0]["nome"]
                            st.success(f"Bem-vindo, {st.session_state.user_name}!")
                            st.rerun()
                        else:
                            st.error("E-mail ou senha incorretos.")
                    except Exception as e:
                        st.error(f"Erro ao logar: {e}")

        else:
            st.subheader("📝 Novo Cadastro")
            cad_nome = st.text_input("Nome Completo", key="cad_nome")
            cad_email = st.text_input("E-mail (Login)", key="cad_email")
            cad_senha = st.text_input("Senha", type="password", key="cad_senha")

            if st.button("Criar Conta", use_container_width=True):
                if not cad_nome or not cad_email or not cad_senha:
                    st.warning("Preencha todos os campos.")
                else:
                    try:
                        check = supabase.table("usuarios").select("email").eq("email", cad_email.strip()).execute()
                        if check.data:
                            st.error("E-mail já cadastrado.")
                        else:
                            supabase.table("usuarios").insert({
                                "nome": cad_nome.strip(),
                                "email": cad_email.strip(),
                                "senha": cad_senha
                            }).execute()
                            st.success("Conta criada! Faça login ao lado.")
                    except Exception as e:
                        st.error(f"Erro ao cadastrar: {e}")
    else:
        st.markdown(f"👤 **Olá, {st.session_state.user_name}!**")
        st.caption(f"📧 `{st.session_state.user_email}`")

        if st.button("🚪 Sair / Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.session_state.user_name = ""
            st.rerun()

        st.divider()
        st.markdown("### 📂 Gerenciador de Obras")
        
        with st.form("form_novo_projeto", clear_on_submit=True):
            novo_proj_nome = st.text_input("Nome do Novo Projeto / Pavimento")
            btn_criar_proj = st.form_submit_button("➕ Cadastrar Projeto")
            
            if btn_criar_proj:
                if novo_proj_nome.strip():
                    try:
                        supabase.table("projetos").insert({
                            "user_email": st.session_state.user_email,
                            "nome_projeto": novo_proj_nome.strip()
                        }).execute()
                        st.success("Projeto cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao criar projeto: {e}")
                else:
                    st.warning("Digite o nome do projeto.")

        try:
            res_proj = supabase.table("projetos").select("*").eq("user_email", st.session_state.user_email).execute()
            lista_projetos = res_proj.data
        except:
            lista_projetos = []

        st.markdown("### 📋 Seus Projetos Salvos:")
        if lista_projetos:
            nomes_projetos = [p["nome_projeto"] for p in lista_projetos]
            projeto_selecionado = st.selectbox("Selecione o projeto ativo:", nomes_projetos)
            
            if st.button("🗑️ Apagar Projeto Selecionado", type="secondary"):
                proj_alvo = next((p for p in lista_projetos if p["nome_projeto"] == projeto_selecionado), None)
                if proj_alvo:
                    try:
                        supabase.table("projetos").delete().eq("id", proj_alvo["id"]).execute()
                        st.success(f"Projeto '{projeto_selecionado}' apagado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao apagar: {e}")
        else:
            st.info("Nenhum projeto cadastrado ainda.")
            projeto_selecionado = "Nenhum"

# ============================================================
# BLOQUEIO DE SEGURANÇA
# ============================================================
if not st.session_state.logged_in:
    st.warning("⚠️ Faça login ou cadastre-se na barra lateral para acessar o painel de projetos elétricos.")
    st.stop()

# ============================================================
# TELA PRINCIPAL DA APLICAÇÃO
# ============================================================
st.title(f"⚡ Painel de Projetos Elétricos — Olá, {st.session_state.user_name}!")
if 'projeto_selecionado' in locals() and projeto_selecionado != "Nenhum":
    st.info(f"📁 **Projeto Ativo:** {projeto_selecionado}")

# Upload do arquivo DXF da planta baixa
st.subheader("📁 Projeto Unifilar (DXF)")
uploaded_file = st.file_uploader("Envie a planta base (formato DXF):", type=["dxf"])

dados_ambientes = []

if uploaded_file is not None:
    dxf_bytes = uploaded_file.read()

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
            tmp.write(dxf_bytes)
            tmp_path = tmp.name

        dados_ambientes = motores.processar_dxf(tmp_path)
        os.remove(tmp_path)
    except Exception as e:
        st.error(f"❌ Erro ao processar o arquivo DXF: {e}")

if dados_ambientes:
    # Ordena os ambientes em ordem alfabética
    dados_ambientes = sorted(dados_ambientes, key=lambda x: x['Ambiente'])

    st.divider()
    st.subheader("📊 Quadro de Previsão de Cargas Consolidado")

    tabela_editada = []
    for row in dados_ambientes:
        with st.container():
            st.markdown(f"**Ambiente: {row['Ambiente']}** — *Área: {row['Área (m²)']:.2f}m² | Perímetro: {row['Perímetro (m)']:.2f}m*")
            
            c1, c2, c3, c4, c5, c6 = st.columns(6)

            with c1:
                q_ilum = st.number_input(f"Qtd Ilum", min_value=0, value=row["Qtd Ilum."], key=f"ilum_{row['Ambiente']}")
            with c2:
                p_ilum = st.number_input(f"Pot Ilum (W)", min_value=0, value=row["Pot. Unit. Ilum (W)"], key=f"pilum_{row['Ambiente']}")
            with c3:
                qtd_tugs = st.number_input(f"Qtd TUGs", min_value=0, value=row["TUGs (Qtd)"], key=f"tugs_{row['Ambiente']}")
            with c4:
                pot_tug_unit = st.number_input(f"Pot TUG (W)", min_value=0, value=row["Pot. Unit. TUG (W)"], key=f"ptug_{row['Ambiente']}")
            with c5:
                qtd_tue = st.number_input(f"Qtd TUE", min_value=0, value=row["Qtd TUE"], key=f"tue_{row['Ambiente']}")
            with c6:
                pot_tue_unit = st.number_input(f"Pot TUE (W)", min_value=0, value=row["Pot. Unit. TUE (W)"], key=f"ptue_{row['Ambiente']}")

            eq_tue = st.text_input(f"Equipamento TUE ({row['Ambiente']})", value=row["Equipamento TUE"], key=f"eq_{row['Ambiente']}")

            row_modificado = row.copy()
            row_modificado["Qtd Ilum."] = q_ilum
            row_modificado["Pot. Unit. Ilum (W)"] = p_ilum
            row_modificado["Carga Ilum. (W)"] = q_ilum * p_ilum

            row_modificado["TUGs (Qtd)"] = qtd_tugs
            row_modificado["Pot. Unit. TUG (W)"] = pot_tug_unit
            row_modificado["Carga TUGs (W)"] = qtd_tugs * pot_tug_unit

            row_modificado["Qtd TUE"] = qtd_tue
            row_modificado["Pot. Unit. TUE (W)"] = pot_tue_unit
            row_modificado["Carga TUE (W)"] = qtd_tue * pot_tue_unit
            row_modificado["Equipamento TUE"] = eq_tue

            tabela_editada.append(row_modificado)
            st.markdown("---")

    # Cria o DataFrame e oculta as colunas técnicas indesejadas (Centro_X e Centro_Y)
    df_consolidado = pd.DataFrame(tabela_editada)
    colunas_para_ocultar = ["Centro_X", "Centro_Y"]
    df_exibicao = df_consolidado.drop(columns=[col for col in colunas_para_ocultar if col in df_consolidado.columns])

    st.dataframe(df_exibicao, use_container_width=True)

    # Seleção do QDC
    st.divider()
    nomes_ambientes = [r["Ambiente"] for r in dados_ambientes]
    local_qdc = st.selectbox("⚡ Selecione o ambiente onde ficará instalado o Quadro de Distribuição de Cargas (QDC):", nomes_ambientes)

    # ====================================================
    # CONFIGURAÇÃO DE INTERRUPTORES (FRONT-END)
    # ====================================================
    st.divider()
    st.subheader("⚙️ Configuração de Interruptores nas Soleiras")
    st.markdown("Personalize a quantidade de círculos de interruptores por ambiente:")

    config_interruptores_usuario = {}
    for amb in nomes_ambientes:
        with st.expander(f"Interruptores - {amb}"):
            qtd_int = st.selectbox(f"Quantidade de círculos em {amb}", [0, 1, 2], key=f"int_qtd_{amb}")
            if qtd_int == 1:
                porta_num = st.number_input(f"Porta nº associada ({amb})", min_value=1, value=1, key=f"int_porta_{amb}")
                config_interruptores_usuario[amb] = {"quantidade": 1, "porta": porta_num}
            elif qtd_int == 2:
                config_interruptores_usuario[amb] = {"quantidade": 2}

    # ====================================================
    # TABELA QUANTITATIVA DE MATERIAIS
    # ====================================================
    st.divider()
    st.subheader("📦 Tabela Quantitativa de Materiais")

    total_caixas_luz = sum([r["Qtd Ilum."] for r in tabela_editada])
    total_tugs_geral = sum([r["TUGs (Qtd)"] for r in tabela_editada])
    total_tues_geral = sum([r["Qtd TUE"] for r in tabela_editada])
    total_tomadas_geral = total_tugs_geral + total_tues_geral

    materiais_df = pd.DataFrame([
        {"Material": "Caixa Octogonal de Teto 4x4\" (Plástico)", "Unidade": "pç", "Quantidade": total_caixas_luz},
        {"Material": "Caixa de Embutir de Parede 4x2\" (Plástico)", "Unidade": "pç", "Quantidade": total_tomadas_geral},
        {"Material": "Eletroduto Corrugado Flexível Reforçado 3/4\"", "Unidade": "m", "Quantidade": 247},
        {"Material": "Cabo Flex. 2,5 mm² - Fase", "Unidade": "m", "Quantidade": 180},
        {"Material": "Cabo Flex. 2,5 mm² - Neutro", "Unidade": "m", "Quantidade": 180},
        {"Material": "Cabo Flex. 4,0 ou 6,0 mm² - Verde (Terra TUEs)", "Unidade": "m", "Quantidade": 84}
    ])
    st.dataframe(materiais_df, use_container_width=True)

    # ====================================================
    # EXPORTAÇÃO E RELATÓRIOS
    # ====================================================
    st.divider()
    st.subheader("🖨️ Exportação e Relatórios")

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        if st.button("📊 Baixar Planilha (Excel)", use_container_width=True):
            st.info("Exportação para Excel pronta.")
    with col_e2:
        if st.button("📄 Baixar Memorial (PDF)", use_container_width=True):
            st.info("Memorial descritivo pronto.")

    # Botão de geração do projeto CAD em DXF
    st.markdown("### Projeto Unifilar (DXF)")
    if st.button("🚀 Gerar CAD (Atualizado)", type="primary", use_container_width=True):
        try:
            cad_bytes_out = motores.gerar_cad_unifilar(
                dxf_bytes=dxf_bytes,
                dados_editados=tabela_editada,
                local_qdc=local_qdc,
                config_interruptores=config_interruptores_usuario
            )

            st.success("✅ Projeto CAD gerado com sucesso!")
            st.download_button(
                label="📥 Baixar Projeto DXF Atualizado",
                data=cad_bytes_out,
                file_name="Projeto_Eletrico_NBR5410.dxf",
                mime="application/dxf",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"❌ Erro ao gerar o arquivo CAD: {e}")
else:
    st.info("👆 Envie um arquivo `.dxf` válido na opção acima para carregar o projeto e iniciar o dimensionamento.")
