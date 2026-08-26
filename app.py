import streamlit as st
import tempfile
import os
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
# CONTROLE DE SESSÃO / LOGIN
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

# ============================================================
# BARRA LATERAL (GERENCIADOR DE OBRAS E LOGIN)
# ============================================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/lightning-bolt.png", width=50)
    st.markdown("### AutoElétrica NBR 5410")
    
    if not st.session_state.logged_in:
        st.subheader("Autenticação")
        email_input = st.text_input("E-mail de acesso", value="jrsebadelhe@gmail.com")
        if st.button("Entrar / Login", use_container_width=True):
            if email_input:
                st.session_state.logged_in = True
                st.session_state.user_email = email_input
                st.rerun()
            else:
                st.warning("Insira um e-mail válido.")
    else:
        st.markdown(f"**Logado como:**\n`{st.session_state.user_email}`")
        if st.button("Sair / Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.rerun()
            
        st.divider()
        st.markdown("### 📂 Gerenciador de Obras")
        if st.button("➕ Novo Projeto / Pavimento", use_container_width=True):
            st.toast("Novo projeto inicializado.")
            
        st.markdown("### 📋 Projetos Salvos:")
        pavimento_ativo = st.selectbox(
            "Selecione o pavimento para trabalhar:",
            ["Teste 01 - Térreo", "Teste 02 - Superior"]
        )
        
        if st.button("⚙️ Opções do Pavimento Atual", use_container_width=True):
            st.info(f"Gerenciando o pavimento: {pavimento_ativo}")

# ============================================================
# VALIDAÇÃO DE ACESSO
# ============================================================
if not st.session_state.logged_in:
    st.warning("🔒 Por favor, efetue o login na barra lateral esquerda para acessar o sistema de projetos.")
    st.stop()

# ============================================================
# TELA PRINCIPAL DA APLICAÇÃO
# ============================================================
st.title("⚡ Gerador de Projetos Elétricos (NBR 5410)")
st.markdown("Automação inteligente para dimensionamento, quantificação de materiais e geração de DXF.")

# Upload do arquivo DXF da planta baixa
st.subheader("📤 Envio da Planta Base")
uploaded_file = st.file_uploader("Reenvie a planta base (formato DXF):", type=["dxf"])

dados_ambientes = []

if uploaded_file is not None:
    dxf_bytes = uploaded_file.read()
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
            tmp.write(dxf_bytes)
            tmp_path = tmp.name
            
        # Processa o DXF utilizando o motor geométrico
        dados_ambientes = motores.processar_dxf(tmp_path)
        os.remove(tmp_path)
    except Exception as e:
        st.error(f"❌ Erro ao processar as camadas do DXF: {e}")

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
            
            # Constrói o dicionário atualizado por linha
            row_modificado = row.copy()
            row_modificado["Qtd Ilum."] = q_ilum
            row_modificado["Pot. Unit. Ilum (VA)"] = p_ilum
            row_modificado["TUGs (Qtd)"] = qtd_tugs
            row_modificado["Qtd TUE"] = qtd_tue
            row_modificado["Equipamento TUE"] = eq_tue
            
            # Recálculos automáticos consistentes
            row_modificado["Carga Ilum. (VA)"] = q_ilum * p_ilum
            is_molhado = any(x in row['Ambiente'].lower() for x in ["coz", "serv", "banh", "lav", "sanit", "wc", "as"])
            pot_tup_unit_calc = 600 if is_molhado else 100
            row_modificado["Pot. Unit. TUG (VA)"] = pot_tup_unit_calc
            row_modificado["Carga TUGs (VA)"] = qtd_tugs * pot_tup_unit_calc
            
            tabela_editada.append(row_modificado)
            st.markdown("---")

    # Exibição da tabela consolidada via dataframe
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
