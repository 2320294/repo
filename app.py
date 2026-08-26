import streamlit as st
import tempfile
import os
import json
import pandas as pd
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
# GERENCIAMENTO DE BANCO DE DADOS DE USUÁRIOS (JSON LOCAL)
# ============================================================
ARQUIVO_USUARIOS = "usuarios_db.json"

def carregar_usuarios():
    if os.path.exists(ARQUIVO_USUARIOS):
        try:
            with open(ARQUIVO_USUARIOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {
        # Usuário padrão inicial para testes
        "jrsebadelhe@gmail.com": {"nome": "Roberto Sebadelhe", "senha": "123456"}
    }

def salvar_usuarios(usuarios):
    with open(ARQUIVO_USUARIOS, "w", encoding="utf-8") as f:
        json.dump(usuarios, f, ensure_ascii=False, indent=4)

# Inicializa sessões de login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

# ============================================================
# BARRA LATERAL (AUTENTICAÇÃO, CADASTRO E GERENCIADOR)
# ============================================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/lightning-bolt.png", width=54)
    st.markdown("### AutoElétrica NBR 5410")
    st.divider()
    
    db_usuarios = carregar_usuarios()

    if not st.session_state.logged_in:
        aba_auth = st.radio("Acesso ao Sistema", ["Entrar (Login)", "Cadastrar-se"], horizontal=True)
        
        if aba_auth == "Entrar (Login)":
            st.subheader("🔐 Fazer Login")
            login_email = st.text_input("E-mail / Login", key="login_email")
            login_senha = st.text_input("Senha", type="password", key="login_senha")
            
            if st.button("Entrar", use_container_width=True):
                if login_email in db_usuarios and db_usuarios[login_email]["senha"] == login_senha:
                    st.session_state.logged_in = True
                    st.session_state.user_email = login_email
                    st.session_state.user_name = db_usuarios[login_email]["nome"]
                    st.success(f"Bem-vindo de volta, {st.session_state.user_name}!")
                    st.rerun()
                else:
                    st.error("E-mail ou senha inválidos.")
                    
        else:
            st.subheader("📝 Novo Cadastro")
            cad_nome = st.text_input("Nome Completo", key="cad_nome")
            cad_email = st.text_input("E-mail (Login)", key="cad_email")
            cad_senha = st.text_input("Senha", type="password", key="cad_senha")
            
            if st.button("Criar Conta", use_container_width=True):
                if not cad_nome or not cad_email or not cad_senha:
                    st.warning("Preencha todos os campos obrigatórios (Nome, E-mail e Senha).")
                elif cad_email in db_usuarios:
                    st.error("Este e-mail já está cadastrado no sistema.")
                else:
                    db_usuarios[cad_email] = {"nome": cad_nome, "senha": cad_senha}
                    salvar_usuarios(db_usuarios)
                    st.success("Cadastro realizado com sucesso! Faça login na aba ao lado.")
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
        if st.button("➕ Novo Projeto / Pavimento", use_container_width=True):
            st.toast("Novo projeto inicializado.")
            
        st.markdown("### 📋 Projetos Salvos:")
        projeto_selecionado = st.selectbox(
            "Selecione o pavimento:",
            ["Teste 01 - Térreo", "Teste 02 - Superior"]
        )
        
        if st.button("⚙️ Opções do Pavimento Atual", use_container_width=True):
            st.info(f"Gerenciando propriedades de: {projeto_selecionado}")

# ============================================================
# BLOQUEIO DE SEGURANÇA
# ============================================================
if not st.session_state.logged_in:
    st.warning("⚠️ Por favor, faça login ou cadastre-se na barra lateral para acessar o painel de projetos elétricos.")
    st.stop()

# ============================================================
# TELA PRINCIPAL DA APLICAÇÃO
# ============================================================
st.title(f"⚡ Painel de Projetos Elétricos — Olá, {st.session_state.user_name}!")
st.markdown("Automação profissional em conformidade com a NBR 5410 para dimensionamento, quantificação e CAD.")

# Upload do arquivo DXF da planta baixa
st.subheader("📁 Projeto Unifilar (DXF)")
uploaded_file = st.file_uploader("Reenvie a planta base (formato DXF):", type=["dxf"])

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
    st.divider()
    st.subheader("📊 Quadro de Previsão de Cargas Consolidado")
    
    tabela_editada = []
    for row in dados_ambientes:
        with st.container():
            st.markdown(f"**Ambiente: {row['Ambiente']}** — *Área: {row['Área (m²)']:.2f}m² | Perímetro: {row['Perímetro (m)']}m*")
            c1, c2, c3, c4, c5 = st.columns(5)
            
            with c1:
                q_ilum = st.number_input(f"Qtd Ilum ({row['Ambiente']})", min_value=0, value=row["Qtd Ilum."], key=f"ilum_{row['Ambiente']}")
            with c2:
                p_ilum = st.number_input(f"Pot Ilum VA ({row['Ambiente']})", min_value=0, value=row["Pot. Unit. Ilum (VA)"], key=f"pilum_{row['Ambiente']}")
            with c3:
                qtd_tugs = st.number_input(f"TUGs Qtd ({row['Ambiente']})", min_value=0, value=row["TUGs (Qtd)"], key=f"tugs_{row['Ambiente']}")
            with c4:
                qtd_tue = st.number_input(f"TUEs Qtd ({row['Ambiente']})", min_value=0, value=row["Qtd TUE"], key=f"tue_{row['Ambiente']}")
            with c5:
                eq_tue = st.text_input(f"Equipamento TUE ({row['Ambiente']})", value=row["Equipamento TUE"], key=f"eq_{row['Ambiente']}")
            
            row_modificado = row.copy()
            row_modificado["Qtd Ilum."] = q_ilum
            row_modificado["Pot. Unit. Ilum (VA)"] = p_ilum
            row_modificado["TUGs (Qtd)"] = qtd_tugs
            row_modificado["Qtd TUE"] = qtd_tue
            row_modificado["Equipamento TUE"] = eq_tue
            
            row_modificado["Carga Ilum. (VA)"] = q_ilum * p_ilum
            is_molhado = any(x in row['Ambiente'].lower() for x in ["coz", "serv", "banh", "lav", "sanit", "wc", "as"])
            pot_tup_unit_calc = 600 if is_molhado else 100
            row_modificado["Pot. Unit. TUG (VA)"] = pot_tup_unit_calc
            row_modificado["Carga TUGs (VA)"] = qtd_tugs * pot_tup_unit_calc
            
            tabela_editada.append(row_modificado)
            st.markdown("---")

    df_consolidado = pd.DataFrame(tabela_editada)
    st.dataframe(df_consolidado, use_container_width=True)

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
