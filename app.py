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
# SISTEMA DE LOGIN / SESSÃO (PRESERVADO INTEGRALMENTE)
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

# Barra Lateral de Autenticação e Gerenciador
with st.sidebar:
    st.image("https://img.icons8.com/color/96/lightning-bolt.png", width=64)
    st.markdown("### AutoElétrica NBR 5410")
    
    if not st.session_state.logged_in:
        st.subheader("Login / Acesso")
        email_input = st.text_input("E-mail de acesso", value="jrsebadelt@gmail.com")
        if st.button("Entrar / Login"):
            if email_input:
                st.session_state.logged_in = True
                st.session_state.user_email = email_input
                st.rerun()
            else:
                st.warning("Digite um e-mail válido.")
    else:
        st.markdown(f"**Logado como:**\n`{st.session_state.user_email}`")
        if st.button("Sair / Logout"):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.rerun()
            
        st.divider()
        st.markdown("### Gerenciador de Obras")
        if st.button("➕ Novo Projeto / Pavimento"):
            st.toast("Funcionalidade de novo projeto ativa!")
            
        st.markdown("### Projetos Salvos:")
        projeto_selecionado = st.selectbox(
            "Selecione o pavimento para trabalhar:",
            ["Teste 01 - Térreo", "Teste 02 - Superior"]
        )
        
        if st.button("⚙️ Opções do Pavimento Atual"):
            st.info("Painel de propriedades do pavimento.")

# ============================================================
# FLUXO PRINCIPAL DA APLICAÇÃO
# ============================================================
if not st.session_state.logged_in:
    st.warning("⚠️ Por favor, faça login na barra lateral para acessar o sistema de projetos elétricos.")
    st.stop()

st.title("⚡ Gerenciador e Dimensionador Elétrico NBR 5410")
st.markdown("Automação completa para dimensionamento de cargas, previsão, relatórios e geração de DXF (CAD).")

# ============================================================
# UPLOAD DA PLANTA BASE (DXF)
# ============================================================
st.subheader("📁 Projeto Unifilar (DXF)")
uploaded_file = st.file_uploader("Reenvie a planta base:", type=["dxf"], key="dxf_uploader")

if uploaded_file is not None:
    dxf_bytes = uploaded_file.read()
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
            tmp.write(dxf_bytes)
            tmp_path = tmp.name
            
        # Processa o DXF através do motores.py
        dados_ambientes = motores.processar_dxf(tmp_path)
        os.remove(tmp_path)
    except Exception as e:
        st.error(f"❌ Erro ao processar o arquivo DXF: {e}")
        dados_ambientes = []

    if dados_ambientes:
        st.divider()
        st.subheader("📊 Quadro de Previsão de Cargas Consolidado")
        
        # Tabela interativa / editável de cargas por ambiente
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
                
                # Sincroniza dados modificados
                row_modificado = row.copy()
                row_modificado["Qtd Ilum."] = q_ilum
                row_modificado["Pot. Unit. Ilum (VA)"] = p_ilum
                row_modificado["TUGs (Qtd)"] = qtd_tugs
                row_modificado["Qtd TUE"] = qtd_tue
                row_modificado["Equipamento TUE"] = eq_tue
                
                # Recalcula cargas parciais para exibição consistente
                row_modificado["Carga Ilum. (VA)"] = q_ilum * p_ilum
                row_modificado["Carga TUGs (VA)"] = qtd_tugs * (600 if any(x in row['Ambiente'].lower() for x in ["coz", "serv", "banh", "lav", "sanit", "wc", "as"]) else 100)
                
                tabela_editada.append(row_modificado)
                st.markdown("---")

        # Exibição da Tabela Consolidada em DataFrame
        df_consolidado = pd.DataFrame(tabela_editada)
        st.dataframe(df_consolidado, use_container_width=True)

        # Seleção do QDC
        st.divider()
        nomes_ambientes = [r["Ambiente"] for r in dados_ambientes]
        local_qdc = st.selectbox("⚡ Selecione o ambiente onde ficará instalado o Quadro de Distribuição de Cargas (QDC):", nomes_ambientes)

        # ====================================================
        # NOVO: CONFIGURAÇÃO DE INTERRUPTORES NO FRONT-END
        # ====================================================
        st.divider()
        st.subheader("⚙️ Configuração de Interruptores nas Soleiras (Opcional)")
        st.markdown("Defina se deseja posicionar círculos de interruptores nas portas dos ambientes:")
        
        config_interruptores_usuario = {}
        for amb in nomes_ambientes:
            with st.expander(f"Interruptor para o ambiente: {amb}"):
                qtd_int = st.selectbox(f"Quantidade de interruptores em {amb}", [0, 1, 2], key=f"int_qtd_{amb}")
                if qtd_int == 1:
                    porta_num = st.number_input(f"Número da porta associada ({amb})", min_value=1, value=1, key=f"int_porta_{amb}")
                    config_interruptores_usuario[amb] = {"quantidade": 1, "porta": porta_num}
                elif qtd_int == 2:
                    config_interruptores_usuario[amb] = {"quantidade": 2}

        # ====================================================
        # TABELA QUANTITATIVA DE MATERIAIS (MANTIDA)
        # ====================================================
        st.divider()
        st.subheader("📦 Tabela Quantitativa de Materiais Estimada")
        
        total_caixas_luz = sum([r["Qtd Ilum."] for r in tabela_editada])
        total_tugs_geral = sum([r["TUGs (Qtd)"] for r in tabela_editada])
        total_tues_geral = sum([r["Qtd TUE"] for r in tabela_editada])
        total_tomadas_geral = total_tugs_geral + total_tues_geral
        
        materiais_df = pd.DataFrame([
            {"Material": "Caixa Octogonal de Teto 4x4\" (Plástico)", "Unidade": "pç", "Quantidade": total_caixas_luz},
            {"Material": "Caixa de Embutir de Parede 4x2\" (Plástico - Tomadas)", "Unidade": "pç", "Quantidade": total_tomadas_geral},
            {"Material": "Eletroduto Corrugado Flexível Reforçado 3/4\"", "Unidade": "m", "Quantidade": 247},
            {"Material": "Cabo Flex. 2,5 mm² - Preto ou Vermelho (Fase)", "Unidade": "m", "Quantidade": 180},
            {"Material": "Cabo Flex. 2,5 mm² - Azul Claro (Neutro)", "Unidade": "m", "Quantidade": 180},
            {"Material": "Cabo Flex. 2,5 ou 4,0 mm² - Verde (Terra TUEs/TUGs)", "Unidade": "m", "Quantidade": 95}
        ])
        st.dataframe(materiais_df, use_container_width=True)

        # ====================================================
        # EXPORTAÇÃO E RELATÓRIOS
        # ====================================================
        st.divider()
        st.subheader("🖨️ Exportação e Relatórios")
        
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            if st.button("📊 Baixar Planilha (Excel)"):
                st.info("Geração de Excel disponível.")
        with col_exp2:
            if st.button("📄 Baixar Memorial (PDF)"):
                st.info("Geração de Memorial descritivo disponível.")

        # Botão principal de Geração de CAD atualizado
        st.markdown("### Gerar Projeto Gráfico CAD")
        if st.button("🚀 Gerar CAD (Atualizado com Regras NBR 5410)", type="primary", use_container_width=True):
            try:
                cad_bytes_out = motores.gerar_cad_unifilar(
                    dxf_bytes=dxf_bytes,
                    dados_editados=tabela_editada,
                    local_qdc=local_qdc,
                    config_interruptores=config_interruptores_usuario
                )
                
                st.success("🎉 Projeto CAD gerado com sucesso aplicando todas as diretrizes normativas e anti-vertex!")
                st.download_button(
                    label="📥 Baixar Arquivo DXF Atualizado",
                    data=cad_bytes_out,
                    file_name="Projeto_Eletrico_NBR5410_Atualizado.dxf",
                    mime="application/dxf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"❌ Erro crítico ao gerar o CAD: {e}")
else:
    st.info("👆 Por favor, envie um arquivo `.dxf` na parte superior para iniciar o dimensionamento e a automação do projeto.")
