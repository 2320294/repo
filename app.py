import streamlit as st
from supabase import create_client, Client
import pandas as pd
import unicodedata
import io
import tempfile
import os
import math
from datetime import datetime

# Importação dos nossos módulos separados
from motores import processar_dxf, gerar_cad_unifilar
from auth import tela_login

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# ==========================================
# 0. CONFIGURAÇÃO DE SESSÃO E BANCO DE DADOS
# ==========================================
st.set_page_config(page_title="AutoElétrica NBR 5410", layout="wide")

@st.cache_resource
def iniciar_conexao():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception:
        return None

supabase = iniciar_conexao()

if 'usuario_autenticado' not in st.session_state:
    st.session_state.usuario_autenticado = False

# ==========================================
# 3. SISTEMA PRINCIPAL
# ==========================================
def sistema_principal():
    with st.sidebar:
        st.write(f"👤 Logado como: **{st.session_state.user_email}**")
        if st.button("Sair / Logout", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.clear()
            st.rerun()
            
        st.divider()
        st.write("📂 **Gerenciador de Obras**")
        
        resposta_db = supabase.table("obras").select("*").eq("user_id", st.session_state.user_id).execute()
        obras_usuario = resposta_db.data

        with st.expander("➕ Novo Projeto / Pavimento"):
            nome_nova_obra = st.text_input("Nome do Empreendimento", placeholder="Ex: Edifício Alpha")
            nome_novo_pav = st.text_input("Pavimento", placeholder="Ex: Térreo")
            if st.button("Criar e Salvar"):
                if nome_nova_obra and nome_novo_pav:
                    supabase.table("obras").insert({
                        "user_id": st.session_state.user_id,
                        "nome_obra": nome_nova_obra,
                        "pavimento": nome_novo_pav,
                        "dados_json": [] 
                    }).execute()
                    st.success("Pavimento criado!")
                    st.rerun()

        if obras_usuario:
            st.write("📖 **Projetos Salvos:**")
            opcoes_dict = {f"{ob['nome_obra']} - {ob['pavimento']}": ob for ob in obras_usuario}
            obra_escolhida = st.selectbox("Selecione o pavimento para trabalhar:", ["Nenhum"] + list(opcoes_dict.keys()))
            
            if obra_escolhida != "Nenhum":
                obra_selecionada = opcoes_dict[obra_escolhida]
                if "obra_atual" not in st.session_state or st.session_state.obra_atual is None or st.session_state.obra_atual['id'] != obra_selecionada['id']:
                    st.session_state.obra_atual = obra_selecionada
                    st.session_state.dados_extraidos = obra_selecionada.get("dados_json", [])
                    st.rerun()
                
                st.divider()
                with st.expander("⚙️ Opções do Pavimento Atual"):
                    novo_nome_obra = st.text_input("Editar Empreendimento", value=st.session_state.obra_atual['nome_obra'])
                    novo_nome_pav = st.text_input("Editar Pavimento", value=st.session_state.obra_atual['pavimento'])
                    
                    if st.button("✏️ Salvar Novos Nomes", use_container_width=True):
                        if novo_nome_obra and novo_nome_pav:
                            supabase.table("obras").update({
                                "nome_obra": novo_nome_obra,
                                "pavimento": novo_nome_pav
                            }).eq("id", st.session_state.obra_atual['id']).execute()
                            st.session_state.obra_atual['nome_obra'] = novo_nome_obra
                            st.session_state.obra_atual['pavimento'] = novo_nome_pav
                            st.success("Nomes atualizados com sucesso!")
                            st.rerun()
                            
                    st.write("---")
                    st.write("**Área de Perigo**")
                    confirmar_exclusao = st.checkbox("Liberar exclusão do projeto")
                    if st.button("🗑️ Excluir Pavimento", type="primary", disabled=not confirmar_exclusao, use_container_width=True):
                        supabase.table("obras").delete().eq("id", st.session_state.obra_atual['id']).execute()
                        st.session_state.obra_atual = None
                        st.session_state.dados_extraidos = None
                        st.success("Pavimento excluído com sucesso!")
                        st.rerun()
            else:
                st.session_state.obra_atual = None
                st.session_state.dados_extraidos = None
        else:
            st.info("Você ainda não tem obras cadastradas.")
            st.session_state.obra_atual = None

    st.title("⚡ Gerador de Projeto Elétrico Automatizado")
    
    if "obra_atual" not in st.session_state or st.session_state.obra_atual is None:
        st.info("👈 **Para começar:** Crie um novo projeto no menu lateral ou selecione um existente.")
        return 

    st.subheader(f"🏢 Empreendimento: {st.session_state.obra_atual['nome_obra']} | 📍 Pavimento: {st.session_state.obra_atual['pavimento']}")
    st.divider()

    if not st.session_state.dados_extraidos:
        st.write("### 1. Importação da Planta Baixa (DXF)")
        arquivo_dxf = st.file_uploader("Faça o upload do arquivo (.dxf)", type=["dxf"])

        if arquivo_dxf is not None:
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("Ler Arquivo CAD", type="primary"):
                    with st.spinner("Analisando geometria..."):
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
                            tmp_file.write(arquivo_dxf.getvalue())
                            tmp_path = tmp_file.name
                        try:
                            resultados = processar_dxf(tmp_path)
                            if len(resultados) > 0:
                                supabase.table("obras").update({"dados_json": resultados}).eq("id", st.session_state.obra_atual['id']).execute()
                                st.session_state.dados_extraidos = resultados
                                st.rerun() 
                            else:
                                st.warning("O arquivo foi lido, mas não foram encontrados ambientes válidos.")
                        except Exception as e:
                            st.error(f"Erro ao processar: {e}")
                        finally:
                            os.remove(tmp_path)
    
    else:
        st.success("✅ Planta carregada do banco de dados! Ajuste os parâmetros abaixo.")
        st.divider()
        
        try:
            df_base = pd.DataFrame(st.session_state.dados_extraidos)
            df_base = df_base.sort_values(
                by="Ambiente", 
                key=lambda col: col.apply(lambda x: unicodedata.normalize('NFKD', str(x)).encode('ASCII', 'ignore').decode('utf-8').lower())
            ).reset_index(drop=True)
            
            ambientes_cad = df_base['Ambiente'].tolist()
            ambientes_seguros = [amb for amb in ambientes_cad if not any(x in amb.lower() for x in ["coz", "serv", "banh", "lav", "wc", "bwc", "sanit"])]
            
            opcoes_formatadas = []
            for amb in ambientes_seguros:
                if any(termo in amb.lower() for termo in ["hall", "corredor", "circulação", "circulacao"]):
                    opcoes_formatadas.append(f"{amb} (recomendado)")
                else:
                    opcoes_formatadas.append(amb)
            
            opcoes_qdc = ["Selecione o ambiente..."] + opcoes_formatadas
            opcoes_qdc = list(dict.fromkeys(opcoes_qdc))
            
            st.write("### ⚙️ Parâmetros Globais da Instalação")
            colA, colB, colC = st.columns([1, 1, 2])
            
            with colA:
                tensao_salva = st.session_state.obra_atual.get('tensao_projeto')
                tensao_salva = int(tensao_salva) if tensao_salva is not None else 220
                index_tensao = 0 if tensao_salva == 127 else 1
                tensao_projeto = st.radio("Tensão do Projeto (V):", [127, 220], index=index_tensao, horizontal=True)
                
            with colB:
                pe_direito_salvo = st.session_state.obra_atual.get('pe_direito')
                pe_direito_salvo = float(pe_direito_salvo) if pe_direito_salvo is not None else 2.80
                pe_direito = st.number_input("Pé Direito (m):", value=pe_direito_salvo, step=0.10)
                
            with colC:
                qdc_salvo = st.session_state.obra_atual.get('local_qdc')
                index_qdc = 0
                if qdc_salvo and qdc_salvo in opcoes_qdc:
                    index_qdc = opcoes_qdc.index(qdc_salvo)
                local_qdc_selecionado = st.selectbox("Locação do QDC:", options=opcoes_qdc, index=index_qdc)

            if local_qdc_selecionado == "Selecione o ambiente...":
                texto_local_qdc = "local a ser definido"
            else:
                texto_local_qdc = local_qdc_selecionado.replace(" (recomendado)", "")
                
            st.info(f"📌 **Diretriz de Execução:** QDC no(a) **{texto_local_qdc}** (Altura: 1,50 m a 1,70 m). Proibido em áreas molhadas ou perigosas.")
            st.divider()
            
            st.write("### 🛠️ Ajuste Fino do Projetista")
            df_editado = df_base.copy()
            
            with st.expander("✏️ Editar Quantidades e Potências Unitárias", expanded=True):
                for index, row in df_editado.iterrows():
                    c1, c2, c3, c4, c5 = st.columns([1.2, 1.2, 1.2, 1.2, 1.2])
                    with c1:
                        st.markdown(f"**{row['Ambiente']}**<br><small>Área: {row['Área (m²)']:.2f}m²</small>", unsafe_allow_html=True)
                    with c2:
                        nova_qtd_ilum = st.number_input("Qtd Ilum", value=int(row['Qtd Ilum.']), step=1, key=f"qilum_{index}")
                        nova_pot_ilum = st.number_input("Pot. Ilum (VA)", value=int(row['Pot. Unit. Ilum (VA)']), step=10, key=f"pilum_{index}")
                    with c3:
                        nova_qtd_tug = st.number_input("Qtd TUG", value=int(row['TUGs (Qtd)']), step=1, key=f"qtug_{index}")
                        nova_pot_tug = st.number_input("Pot. TUG (VA)", value=int(row['Pot. Unit. TUG (VA)']), step=10, key=f"ptug_{index}")
                    with c4:
                        novo_equip = st.text_input("Equip. TUE", value=str(row['Equipamento TUE']), key=f"eq_{index}")
                        nova_qtd_tue = st.number_input("Qtd TUE", value=int(row['Qtd TUE']), step=1, key=f"qtue_{index}")
                    with c5:
                        nova_pot_tue = st.number_input("Pot. TUE (VA)", value=int(row['Pot. Unit. TUE (VA)']), step=100, key=f"ptue_{index}")
                    
                    df_editado.at[index, 'Qtd Ilum.'] = nova_qtd_ilum
                    df_editado.at[index, 'Pot. Unit. Ilum (VA)'] = nova_pot_ilum
                    df_editado.at[index, 'Carga Ilum. (VA)'] = int(nova_qtd_ilum * nova_pot_ilum)
                    df_editado.at[index, 'TUGs (Qtd)'] = nova_qtd_tug
                    df_editado.at[index, 'Pot. Unit. TUG (VA)'] = nova_pot_tug
                    df_editado.at[index, 'Carga TUGs (VA)'] = int(nova_qtd_tug * nova_pot_tug)
                    df_editado.at[index, 'Equipamento TUE'] = novo_equip
                    df_editado.at[index, 'Qtd TUE'] = nova_qtd_tue
                    df_editado.at[index, 'Pot. Unit. TUE (VA)'] = nova_pot_tue
                    df_editado.at[index, 'Carga TUE (VA)'] = int(nova_qtd_tue * nova_pot_tue)
                    st.divider()

            if st.button("💾 Salvar Alterações na Nuvem", type="primary"):
                dados_atualizados = df_editado.to_dict(orient='records')
                supabase.table("obras").update({
                    "dados_json": dados_atualizados,
                    "local_qdc": local_qdc_selecionado,
                    "tensao_projeto": int(tensao_projeto),
                    "pe_direito": float(pe_direito)
                }).eq("id", st.session_state.obra_atual['id']).execute()
                
                st.session_state.dados_extraidos = dados_atualizados
                st.session_state.obra_atual['local_qdc'] = local_qdc_selecionado
                st.session_state.obra_atual['tensao_projeto'] = int(tensao_projeto)
                st.session_state.obra_atual['pe_direito'] = float(pe_direito)
                st.success("✅ Projeto atualizado e salvo na nuvem com sucesso!")
            
            st.write("### 📊 Quadro de Previsão de Cargas Consolidado")
            linha_total = pd.DataFrame([{
                "Ambiente": "TOTAL", 
                "Área (m²)": df_editado["Área (m²)"].sum(), 
                "Perímetro (m)": df_editado["Perímetro (m)"].sum(),
                "Qtd Ilum.": df_editado["Qtd Ilum."].sum(), 
                "Carga Ilum. (VA)": df_editado["Carga Ilum. (VA)"].sum(),
                "TUGs (Qtd)": df_editado["TUGs (Qtd)"].sum(), 
                "Carga TUGs (VA)": df_editado["Carga TUGs (VA)"].sum(),
                "Equipamento TUE": "-", 
                "Qtd TUE": df_editado["Qtd TUE"].sum(), 
                "Carga TUE (VA)": df_editado["Carga TUE (VA)"].sum()
            }])
            
            df_final = pd.concat([df_editado, linha_total], ignore_index=True)
            df_final = df_final.rename(columns={"Qtd TUE": "TUEs (Qtd)", "Carga TUE (VA)": "Carga TUEs (VA)"})
            
            ordem_colunas = ["Ambiente", "Área (m²)", "Perímetro (m)", "Qtd Ilum.", "Carga Ilum. (VA)", "TUGs (Qtd)", "Carga TUGs (VA)", "TUEs (Qtd)", "Carga TUEs (VA)", "Equipamento TUE"]
            df_final = df_final[[col for col in ordem_colunas if col in df_final.columns]]
            
            df_final_exibir = df_final.copy()
            if "Área (m²)" in df_final_exibir: df_final_exibir["Área (m²)"] = df_final_exibir["Área (m²)"].apply(lambda x: f"{x:.2f}".replace(".", ","))
            if "Perímetro (m)" in df_final_exibir: df_final_exibir["Perímetro (m)"] = df_final_exibir["Perímetro (m)"].apply(lambda x: f"{x:.2f}".replace(".", ","))
            st.table(df_final_exibir) 

            st.divider()
            st.write("### 📦 Tabela Quantitativa de Materiais")
            
            acrescimo_qdc = 5 if local_qdc_selecionado == "Selecione o ambiente..." else (0 if "(recomendado)" in local_qdc_selecionado else 3)

            total_eletroduto = 0
            total_cabo_ilum = 0
            total_cabo_tug = 0
            total_cabo_tue = 0
            dist_base_qdc = 4 + acrescimo_qdc

            for index, row in df_editado.iterrows():
                area_amb = float(row["Área (m²)"])
                perim_amb = float(row["Perímetro (m)"])
                q_ilum = float(row["Qtd Ilum."])
                q_tug = float(row["TUGs (Qtd)"])
                q_tue = float(row["Qtd TUE"])

                dim_teto = math.sqrt(area_amb) if area_amb > 0 else 2.0

                if q_ilum > 0:
                    rota_ilum = dist_base_qdc + dim_teto + pe_direito
                    total_eletroduto += rota_ilum
                    total_cabo_ilum += (rota_ilum * 3) * q_ilum 
                if q_tug > 0:
                    rota_tug = dist_base_qdc + pe_direito + (perim_amb / 2)
                    total_eletroduto += rota_tug
                    total_cabo_tug += (rota_tug * 3) 
                if q_tue > 0:
                    rota_tue = (dist_base_qdc + dim_teto + pe_direito) * q_tue
                    total_eletroduto += rota_tue
                    total_cabo_tue += (rota_tue * 3) 
                    
            cabo_ilum_final = round(total_cabo_ilum * 1.15)
            cabo_tug_final = round(total_cabo_tug * 1.15)
            cabo_tue_final = round(total_cabo_tue * 1.15)
            eletroduto_final = round(total_eletroduto * 1.10)
            
            ilum_fase = math.ceil(cabo_ilum_final / 3)
            ilum_neutro = math.ceil(cabo_ilum_final / 3)
            ilum_retorno = math.ceil(cabo_ilum_final / 3)
            
            tug_fase = math.ceil(cabo_tug_final / 3)
            tug_neutro = math.ceil(cabo_tug_final / 3)
            tug_terra = math.ceil(cabo_tug_final / 3)
            
            tue_fase = math.ceil(cabo_tue_final / 3)
            tue_neutro_fase = math.ceil(cabo_tue_final / 3)
            tue_terra = math.ceil(cabo_tue_final / 3)

            total_ambientes = len(df_editado) 
            total_pontos_luz = int(df_editado["Qtd Ilum."].sum())
            total_pontos_tugs = int(df_editado["TUGs (Qtd)"].sum())
            tues_validas = df_editado[df_editado["Qtd TUE"] > 0]
            total_pontos_tue = int(tues_validas["Qtd TUE"].sum())
            
            total_interruptores = total_ambientes
            caixas_teto = total_pontos_luz
            caixas_parede = total_pontos_tugs + total_pontos_tue + total_interruptores
            
            def calc_disj(potencia_va):
                if potencia_va <= 0: return 10
                corrente_proj = potencia_va / tensao_projeto
                for d in [10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125]:
                    if d >= corrente_proj: return d
                return 125 

            carga_total_geral = df_editado["Carga Ilum. (VA)"].sum() + df_editado["Carga TUGs (VA)"].sum() + df_editado["Carga TUE (VA)"].sum()
            disj_geral = calc_disj(carga_total_geral)
            idr_geral = next((d for d in [25, 40, 63, 80, 100, 125] if d >= disj_geral), 125)
            disj_ilum = calc_disj(df_editado["Carga Ilum. (VA)"].sum())
            disj_tug_media = calc_disj(df_editado["Carga TUGs (VA)"].sum() / 2) 
            
            materiais = [
                {"Material": "Caixa Octogonal de Teto 4x4\" (Plástico)", "Unidade": "pç", "Quantidade": caixas_teto},
                {"Material": "Caixa de Embutir de Parede 4x2\" (Plástico)", "Unidade": "pç", "Quantidade": caixas_parede},
                {"Material": "Interruptor Simples (Módulo + Espelho)", "Unidade": "cj", "Quantidade": total_interruptores},
                {"Material": "Tomada Baixa 2P+T 10A (Espelho + Módulos)", "Unidade": "cj", "Quantidade": total_pontos_tugs},
                {"Material": "Tomada Especial / Força 20A (para TUEs)", "Unidade": "cj", "Quantidade": total_pontos_tue},
                {"Material": "Quadro de Distribuição (QDC) para no mín. 16 a 24 Módulos DIN", "Unidade": "pç", "Quantidade": 1},
                {"Material": f"Disjuntor Geral Termomagnético DIN - {disj_geral}A", "Unidade": "pç", "Quantidade": 1},
                {"Material": f"Interruptor Diferencial Residual (IDR) Tetrapolar - {idr_geral}A / 30mA", "Unidade": "pç", "Quantidade": 1},
                {"Material": "Dispositivo de Proteção contra Surtos (DPS) - Classe II (275V/45kA)", "Unidade": "pç", "Quantidade": 2},
                {"Material": f"Disjuntor DIN {disj_ilum}A (Circuito Geral: Iluminação)", "Unidade": "pç", "Quantidade": 1},
                {"Material": f"Disjuntor DIN {disj_tug_media}A (Circuitos Gerais: TUGs Secas e Molhadas)", "Unidade": "pç", "Quantidade": 2 if df_editado["Carga TUGs (VA)"].sum() > 0 else 0}
            ]
            
            for index, row in tues_validas.iterrows():
                pot_tue_unit = row["Pot. Unit. TUE (VA)"]
                dj_tue = calc_disj(pot_tue_unit)
                materiais.append({"Material": f"Disjuntor DIN {dj_tue}A (Circuito Específico TUE: {row['Equipamento TUE']} - {row['Ambiente']})", "Unidade": "pç", "Quantidade": int(row["Qtd TUE"])})
                
            materiais.extend([
                {"Material": "Cabo Flex. 1,5 mm² - Preto (Fase Iluminação)", "Unidade": "m", "Quantidade": ilum_fase},
                {"Material": "Cabo Flex. 1,5 mm² - Azul Claro (Neutro Iluminação)", "Unidade": "m", "Quantidade": ilum_neutro},
                {"Material": "Cabo Flex. 1,5 mm² - Amarelo (Retorno Iluminação)", "Unidade": "m", "Quantidade": ilum_retorno},
                {"Material": "Cabo Flex. 2,5 mm² - Vermelho (Fase TUGs)", "Unidade": "m", "Quantidade": tug_fase},
                {"Material": "Cabo Flex. 2,5 mm² - Azul Claro (Neutro TUGs)", "Unidade": "m", "Quantidade": tug_neutro},
                {"Material": "Cabo Flex. 2,5 mm² - Verde (Terra TUGs)", "Unidade": "m", "Quantidade": tug_terra},
                {"Material": "Cabo Flex. 4,0 ou 6,0 mm² - Vermelho (Fase 1 TUEs)", "Unidade": "m", "Quantidade": tue_fase},
                {"Material": "Cabo Flex. 4,0 ou 6,0 mm² - Azul/Preto (Neutro/Fase 2 TUEs)", "Unidade": "m", "Quantidade": tue_neutro_fase},
                {"Material": "Cabo Flex. 4,0 ou 6,0 mm² - Verde (Terra TUEs)", "Unidade": "m", "Quantidade": tue_terra},
                {"Material": "Eletroduto Corrugado Flexível Reforçado 3/4\"", "Unidade": "m", "Quantidade": eletroduto_final}
            ])
            
            df_materiais_final = pd.DataFrame(materiais)
            st.table(df_materiais_final)
            
            st.divider()
            st.write("### 🖨️ Exportação e Relatórios")
            col_exp1, col_exp2, col_exp3 = st.columns(3)
            
            with col_exp1:
                buffer_excel = io.BytesIO()
                with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                    df_final.to_excel(writer, index=False, sheet_name='Quadro de Cargas')
                    df_materiais_final.to_excel(writer, index=False, sheet_name='Lista de Materiais')
                st.download_button("📊 Baixar Planilha (Excel)", data=buffer_excel.getvalue(), file_name=f"Orcamento_{st.session_state.obra_atual['nome_obra']}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                
            with col_exp2:
                if FPDF is not None:
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 16)
                    def formatar_txt(t): return unicodedata.normalize('NFKD', str(t)).encode('ASCII', 'ignore').decode('utf-8')
                    pdf.cell(0, 10, formatar_txt(f"Memorial: {st.session_state.obra_atual['nome_obra']}"), ln=True, align='C')
                    pdf.set_font("Arial", '', 10)
                    pdf.cell(0, 8, formatar_txt(f"Carga Total Ilum: {df_editado['Carga Ilum. (VA)'].sum()} VA"), ln=True)
                    try:
                        st.download_button("📄 Baixar Memorial (PDF)", data=pdf.output(dest='S').encode('latin1'), file_name="Memorial.pdf", mime="application/pdf", use_container_width=True)
                    except Exception as e: st.error(f"Erro PDF: {e}")
                else: st.warning("FPDF não instalado.")

            with col_exp3:
                st.write("**Projeto Unifilar (DXF)**")
                arquivo_base = st.file_uploader("Reenvie a planta base:", type=["dxf"], key="dxf_unifilar")
                if arquivo_base is not None:
                    if st.button("🎨 Gerar CAD (Atualizado)", type="primary", use_container_width=True):
                        with st.spinner("Desenhando..."):
                            try:
                                dxf_bytes_gerado = gerar_cad_unifilar(arquivo_base.getvalue(), df_editado.to_dict(orient='records'), local_qdc_selecionado)
                                st.download_button("⬇️ Baixar DXF Desenhado", data=dxf_bytes_gerado, file_name=f"Proj_{st.session_state.obra_atual['nome_obra']}.dxf", mime="application/dxf", use_container_width=True)
                                st.success("Gerado com sucesso!")
                            except Exception as e: st.error(f"Erro CAD: {e}")

        except Exception as erro_visual:
            st.error(f"Erro interno: {erro_visual}")

# ==========================================
# 4. ROTEADOR
# ==========================================
if not st.session_state.usuario_autenticado:
    tela_login(supabase)
else:
    sistema_principal()
