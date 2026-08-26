import streamlit as st
import tempfile
import os
import motores

st.set_page_config(page_title="Projeto Elétrico NBR 5410", layout="wide")

st.title("⚡ Gerador Automático de Documentação Elétrica (NBR 5410)")

# Upload do DXF
uploaded_file = st.file_uploader("Envie a planta base em formato DXF", type=["dxf"])

if uploaded_file is not None:
    dxf_bytes = uploaded_file.read()
    
    # Processa o DXF para extrair ambientes e gerar a tabela de cargas
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
            tmp.write(dxf_bytes)
            tmp_path = tmp.name
            
        dados_ambientes = motores.processar_dxf(tmp_path)
        os.remove(tmp_path)
    except Exception as e:
        st.error(f"Erro ao processar o DXF: {e}")
        dados_ambientes = []

    if dados_ambientes:
        st.subheader("📊 Quadro de Previsão de Cargas Consolidado")
        
        # Exibe em formato editável ou tabela interativa
        tabela_editada = []
        for row in dados_ambientes:
            st.markdown(f"**Ambiente: {row['Ambiente']}** (Área: {row['Área (m²)']:.2f}m² | Perímetro: {row['Perímetro (m)']}m)")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                qtd_tugs = st.number_input(f"TUGs Qtd ({row['Ambiente']})", min_value=0, value=row["TUGs (Qtd)"], key=f"tugs_{row['Ambiente']}")
            with col2:
                qtd_tue = st.number_input(f"TUEs Qtd ({row['Ambiente']})", min_value=0, value=row["Qtd TUE"], key=f"tue_{row['Ambiente']}")
            with col3:
                eq_tue = st.text_input(f"Equipamento ({row['Ambiente']})", value=row["Equipamento TUE"], key=f"eq_{row['Ambiente']}")
            with col4:
                pot_tue = st.number_input(f"Pot TUE VA ({row['Ambiente']})", min_value=0, value=row["Pot. Unit. TUE (VA)"], key=f"pot_{row['Ambiente']}")
            
            # Atualiza o registro
            row_copia = row.copy()
            row_copia["TUGs (Qtd)"] = qtd_tugs
            row_copia["Qtd TUE"] = qtd_tue
            row_copia["Equipamento TUE"] = eq_tue
            row_copia["Pot. Unit. TUE (VA)"] = pot_tue
            tabela_editada.append(row_copia)
            st.divider()

        # Seleção do QDC
        nomes_ambientes = [r["Ambiente"] for r in dados_ambientes]
        local_qdc = st.selectbox("Selecione o ambiente onde ficará instalado o QDC:", nomes_ambientes)

        # Configuração de Interruptores Dinâmica via Front-End
        st.subheader("⚙️ Configuração de Interruptores por Ambiente")
        config_interruptores_usuario = {}
        
        for amb in nomes_ambientes:
            with st.expander(f"Interruptor - {amb}"):
                qtd_int = st.selectbox(f"Qtd de Interruptores em {amb}", [0, 1, 2], key=f"int_qtd_{amb}")
                if qtd_int == 1:
                    porta_num = st.number_input(f"Número da Porta para {amb}", min_value=1, value=1, key=f"int_porta_{amb}")
                    config_interruptores_usuario[amb] = {"quantidade": 1, "porta": porta_num}
                elif qtd_int == 2:
                    config_interruptores_usuario[amb] = {"quantidade": 2}

        # Botão de Geração do CAD
        if st.button("🚀 Gerar Projeto Elétrico em CAD (DXF)", type="primary"):
            try:
                cad_bytes_out = motores.gerar_cad_unifilar(
                    dxf_bytes=dxf_bytes,
                    dados_editados=tabela_editada,
                    local_qdc=local_qdc,
                    config_interruptores=config_interruptores_usuario
                )
                st.success("✅ Projeto CAD gerado com sucesso!")
                st.download_button(
                    label="📥 Baixar Projeto Elétrico (.dxf)",
                    data=cad_bytes_out,
                    file_name="Projeto_Eletrico_NBR5410.dxf",
                    mime="application/dxf"
                )
            except Exception as e:
                st.error(f"❌ Erro ao gerar o CAD: {e}")
