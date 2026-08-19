import streamlit as st
from supabase import create_client, Client
import ezdxf
import math
import tempfile
import os
import pandas as pd
import unicodedata

# ==========================================
# 0. CONFIGURAÇÃO DE SESSÃO E BANCO DE DADOS
# ==========================================
st.set_page_config(page_title="AutoElétrica NBR 5410", layout="wide")

# Conecta ao Supabase usando os Secrets do Streamlit Cloud
@st.cache_resource
def iniciar_conexao():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception:
        return None

supabase = iniciar_conexao()

# Controle de estado do login
if 'usuario_autenticado' not in st.session_state:
    st.session_state.usuario_autenticado = False

# ==========================================
# 1. MOTORES DE ENGENHARIA (NBR 5410 E DXF)
# ==========================================
def dimensionar_cargas(nome, area, perimetro):
    if area <= 0 or perimetro <= 0:
        return {
            "Qtd Ilum.": 0, "Pot. Unit. Ilum (VA)": 0, "Carga Ilum. (VA)": 0, 
            "TUGs (Qtd)": 0, "Pot. Unit. TUG (VA)": 0, "Carga TUGs (VA)": 0, 
            "Equipamento TUE": "-", "Qtd TUE": 0, "Pot. Unit. TUE (VA)": 0, "Carga TUE (VA)": 0
        }

    qtd_ilum = 1 if area <= 10 else math.ceil(area / 10)
    carga_ilum = 100 if area <= 6 else 100 + (((area - 6) // 4) * 60)
    
    nome_lower = nome.lower()
    if any(x in nome_lower for x in ["coz", "serv", "banh", "lav"]):
        qtd_tugs = math.ceil(perimetro / 3.5)
        carga_tugs = (qtd_tugs * 600) if qtd_tugs <= 3 else (3 * 600) + ((qtd_tugs - 3) * 100)
    else:
        qtd_tugs = math.ceil(perimetro / 5)
        carga_tugs = qtd_tugs * 100
        
    tue_nome = "-"
    qtd_tue = 0
    carga_tue = 0
    
    if any(x in nome_lower for x in ["banh", "wc", "bwc", "sanit"]):
        tue_nome = "Chuveiro Elétrico"
        qtd_tue = 1
        carga_tue = 5500
    elif any(x in nome_lower for x in ["coz"]):
        tue_nome = "Micro-ondas/Forno"
        qtd_tue = 1
        carga_tue = 2000
    elif any(x in nome_lower for x in ["quarto", "dorm", "suite"]):
        tue_nome = "Ar-Condicionado"
        qtd_tue = 1
        carga_tue = 1200
    elif any(x in nome_lower for x in ["serv", "lavand"]):
        tue_nome = "Máquina de Lavar"
        qtd_tue = 1
        carga_tue = 1000

    return {
        "Qtd Ilum.": qtd_ilum,
        "Pot. Unit. Ilum (VA)": round(carga_ilum / qtd_ilum) if qtd_ilum > 0 else 0,
        "Carga Ilum. (VA)": carga_ilum, 
        "TUGs (Qtd)": qtd_tugs, 
        "Pot. Unit. TUG (VA)": round(carga_tugs / qtd_tugs) if qtd_tugs > 0 else 0,
        "Carga TUGs (VA)": carga_tugs,
        "Equipamento TUE": tue_nome,
        "Qtd TUE": qtd_tue,
        "Pot. Unit. TUE (VA)": round(carga_tue / qtd_tue) if qtd_tue > 0 else 0,
        "Carga TUE (VA)": carga_tue
    }

def processar_dxf(caminho_arquivo):
    doc = ezdxf.readfile(caminho_arquivo)
    msp = doc.modelspace()
    
    polilinhas = []
    textos = []
    debug_layers = set()
    
    for entity in msp:
        tipo = entity.dxftype()
        if hasattr(entity.dxf, 'layer'):
            layer = str(entity.dxf.layer).upper().strip()
            debug_layers.add(layer)
        else:
            continue
            
        if tipo in ['LWPOLYLINE', 'POLYLINE'] and layer == 'IA_AMBIENTES':
            try:
                if tipo == 'LWPOLYLINE':
                    pontos = [(p[0], p[1]) for p in entity.get_points(format='xy')]
                else:
                    pontos = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                if pontos:
                    polilinhas.append(pontos)
            except Exception:
                continue
                
        elif tipo in ['TEXT', 'MTEXT'] and layer == 'IA_TEXTOS':
            try:
                texto_str = entity.text if tipo == 'MTEXT' else entity.dxf.text
                texto_str = texto_str.strip()
                if texto_str: 
                    textos.append({
                        'nome': texto_str,
                        'x': entity.dxf.insert.x,
                        'y': entity.dxf.insert.y
                    })
            except Exception:
                continue
            
    resultados = []
    ambientes_processados = {}
    
    for polilinha in polilinhas:
        xs = [p[0] for p in polilinha]
        ys = [p[1] for p in polilinha]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        largura = max_x - min_x
        comprimento = max_y - min_y
        area = largura * comprimento
        perimetro = (largura * 2) + (comprimento * 2)
        
        if area < 0.5:
            continue
        
        nome_ambiente = None
        for t in textos:
            if (min_x - 0.5) <= t['x'] <= (max_x + 0.5) and (min_y - 0.5) <= t['y'] <= (max_y + 0.5):
                nome_ambiente = t['nome']
                break
                
        if not nome_ambiente:
            continue
            
        if nome_ambiente in ambientes_processados:
            ambientes_processados[nome_ambiente] += 1
            nome_ambiente = f"{nome_ambiente} {ambientes_processados[nome_ambiente]}"
        else:
            ambientes_processados[nome_ambiente] = 1
                
        cargas = dimensionar_cargas(nome_ambiente, area, perimetro)
        
        resultados.append({
            "Ambiente": nome_ambiente,
            "Área (m²)": area,
            "Perímetro (m)": perimetro,
            "Qtd Ilum.": int(cargas["Qtd Ilum."]),
            "Pot. Unit. Ilum (VA)": int(cargas["Pot. Unit. Ilum (VA)"]),
            "Carga Ilum. (VA)": int(cargas["Carga Ilum. (VA)"]),
            "TUGs (Qtd)": int(cargas["TUGs (Qtd)"]),
            "Pot. Unit. TUG (VA)": int(cargas["Pot. Unit. TUG (VA)"]),
            "Carga TUGs (VA)": int(cargas["Carga TUGs (VA)"]),
            "Equipamento TUE": cargas["Equipamento TUE"],
            "Qtd TUE": int(cargas["Qtd TUE"]),
            "Pot. Unit. TUE (VA)": int(cargas["Pot. Unit. TUE (VA)"]),
            "Carga TUE (VA)": int(cargas["Carga TUE (VA)"])
        })
        
    return resultados, len(polilinhas), len(textos), debug_layers

# ==========================================
# 2. TELA DE LOGIN
# ==========================================
def tela_login():
    st.title("🔐 Login - AutoElétrica SaaS")
    st.subheader("Acesso restrito à plataforma de projetos")
    
    if supabase is None:
        st.error("Erro Crítico: Não foi possível conectar ao banco de dados. Verifique se configurou os Segredos (Secrets) do Streamlit Cloud.")
        st.stop()
        
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("form_login"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar no Sistema")
            
            if submit:
                try:
                    response = supabase.auth.sign_in_with_password({"email": email, "password": senha})
                    st.session_state.usuario_autenticado = True
                    st.session_state.user_email = email
                    st.success("Login realizado com sucesso! Carregando plataforma...")
                    st.rerun()
                except Exception as erro:
                    st.error("Credenciais inválidas. Verifique seu e-mail e senha.")

# ==========================================
# 3. SISTEMA PRINCIPAL (O SaaS)
# ==========================================
def sistema_principal():
    # BARRA LATERAL
    with st.sidebar:
        st.write(f"👤 Logado como: **{st.session_state.user_email}**")
        if st.button("Sair / Logout", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.usuario_autenticado = False
            st.session_state.dados_extraidos = None
            st.rerun()
            
        st.divider()
        st.write("📂 **Gerenciador de Obras**")
        st.info("A funcionalidade de salvar projetos na nuvem e alternar entre pavimentos será liberada na próxima atualização.")

    st.title("⚡ Gerador de Projeto Elétrico Automatizado")
    st.subheader("Integração CAD (DXF) -> Dimensionamento NBR 5410")
    st.divider()

    if "dados_extraidos" not in st.session_state:
        st.session_state.dados_extraidos = None

    st.write("### 1. Importação da Planta Baixa")
    arquivo_dxf = st.file_uploader("Faça o upload do arquivo (.dxf)", type=["dxf"], key="dxf_uploader")

    if arquivo_dxf is not None:
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Ler Arquivo CAD", type="primary"):
                with st.spinner("Analisando geometria..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
                        tmp_file.write(arquivo_dxf.getvalue())
                        tmp_path = tmp_file.name
                    try:
                        resultados, qtd_poly, qtd_text, layers_vistos = processar_dxf(tmp_path)
                        if len(resultados) > 0:
                            st.session_state.dados_extraidos = resultados
                            st.rerun() 
                        else:
                            st.warning("O arquivo foi lido, mas não foram encontrados ambientes válidos.")
                    except Exception as e:
                        st.error(f"Erro ao processar: {e}")
                    finally:
                        os.remove(tmp_path)

    if st.session_state.dados_extraidos is not None:
        st.success("Planta processada e validada! Configure os parâmetros da edificação e ajuste as cargas.")
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
                tensao_projeto = st.radio("Tensão do Projeto (V):", [127, 220], index=1, horizontal=True)
            with colB:
                pe_direito = st.number_input("Pé Direito (m):", value=2.80, step=0.10)
            with colC:
                local_qdc_selecionado = st.selectbox("Locação do QDC:", options=opcoes_qdc)
                
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
            
            st.write("### 📊 Quadro de Previsão de Cargas Consolidado")
            linha_total = pd.DataFrame([{
                "Ambiente": "TOTAL", "Área (m²)": df_editado["Área (m²)"].sum(), "Perímetro (m)": df_editado["Perímetro (m)"].sum(),
                "Qtd Ilum.": df_editado["Qtd Ilum."].sum(), "Carga Ilum. (VA)": df_editado["Carga Ilum. (VA)"].sum(),
                "TUGs (Qtd)": df_editado["TUGs (Qtd)"].sum(), "Carga TUGs (VA)": df_editado["Carga TUGs (VA)"].sum(),
                "Equipamento TUE": "-", "Qtd TUE": df_editado["Qtd TUE"].sum(), "Carga TUE (VA)": df_editado["Carga TUE (VA)"].sum()
            }])
            
            df_final = pd.concat([df_editado, linha_total], ignore_index=True)
            df_final = df_final.drop(columns=["Pot. Unit. Ilum (VA)", "Pot. Unit. TUG (VA)", "Pot. Unit. TUE (VA)"])
            df_final["Área (m²)"] = df_final["Área (m²)"].apply(lambda x: f"{x:.2f}".replace(".", ","))
            df_final["Perímetro (m)"] = df_final["Perímetro (m)"].apply(lambda x: f"{x:.2f}".replace(".", ","))
            st.table(df_final) 

            st.divider()
            st.write("### 📦 Tabela Quantitativa de Materiais (Integração Volumétrica 3D)")
            
            if local_qdc_selecionado == "Selecione o ambiente...":
                acrescimo_qdc = 5  
                st.warning("⚠️ **Aviso:** Como o QDC não foi alocado, o sistema adicionou 5m de margem de segurança na rota de cada circuito.")
            elif "(recomendado)" in local_qdc_selecionado:
                acrescimo_qdc = 0  
                st.success("✅ **Otimização Ativa:** QDC alocado em área de circulação. Rotas de distribuição minimizadas.")
            else:
                acrescimo_qdc = 3  
                st.info("ℹ️ **Ajuste de Rota:** QDC em ambiente descentralizado. Adicionados 3m extras por circuito para compensar o trajeto.")

            total_eletroduto = 0; total_cabo_ilum = 0; total_cabo_tug = 0; total_cabo_tue = 0
            dist_base_qdc = 4 + acrescimo_qdc

            for index, row in df_editado.iterrows():
                area_amb = float(row["Área (m²)"]); perim_amb = float(row["Perímetro (m)"])
                q_ilum = float(row["Qtd Ilum."]); q_tug = float(row["TUGs (Qtd)"]); q_tue = float(row["Qtd TUE"])
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
            
            ilum_fase = math.ceil(cabo_ilum_final / 3); ilum_neutro = math.ceil(cabo_ilum_final / 3); ilum_retorno = math.ceil(cabo_ilum_final / 3)
            tug_fase = math.ceil(cabo_tug_final / 3); tug_neutro = math.ceil(cabo_tug_final / 3); tug_terra = math.ceil(cabo_tug_final / 3)
            tue_fase = math.ceil(cabo_tue_final / 3); tue_neutro_fase = math.ceil(cabo_tue_final / 3); tue_terra = math.ceil(cabo_tue_final / 3)

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
                {"Material": f"Disjuntor DIN {disj_tug_media}A (Circuitos Gerais: TUGs)", "Unidade": "pç", "Quantidade": 2 if df_editado["Carga TUGs (VA)"].sum() > 0 else 0}
            ]
            
            for index, row in tues_validas.iterrows():
                materiais.append({"Material": f"Disjuntor DIN {calc_disj(row['Pot. Unit. TUE (VA)'])}A (TUE: {row['Equipamento TUE']} - {row['Ambiente']})", "Unidade": "pç", "Quantidade": int(row["Qtd TUE"])})
                
            materiais.extend([
                {"Material": "Cabo Flex. 1,5 mm² - Preto (Fase Ilum)", "Unidade": "m", "Quantidade": ilum_fase},
                {"Material": "Cabo Flex. 1,5 mm² - Azul Claro (Neutro Ilum)", "Unidade": "m", "Quantidade": ilum_neutro},
                {"Material": "Cabo Flex. 1,5 mm² - Amarelo (Retorno Ilum)", "Unidade": "m", "Quantidade": ilum_retorno},
                {"Material": "Cabo Flex. 2,5 mm² - Vermelho (Fase TUG)", "Unidade": "m", "Quantidade": tug_fase},
                {"Material": "Cabo Flex. 2,5 mm² - Azul Claro (Neutro TUG)", "Unidade": "m", "Quantidade": tug_neutro},
                {"Material": "Cabo Flex. 2,5 mm² - Verde (Terra TUG)", "Unidade": "m", "Quantidade": tug_terra},
                {"Material": "Cabo Flex. 4,0 ou 6,0 mm² - Vermelho (Fase 1 TUE)", "Unidade": "m", "Quantidade": tue_fase},
                {"Material": "Cabo Flex. 4,0 ou 6,0 mm² - Azul Claro/Preto (Neutro/Fase 2 TUE)", "Unidade": "m", "Quantidade": tue_neutro_fase},
                {"Material": "Cabo Flex. 4,0 ou 6,0 mm² - Verde (Terra TUE)", "Unidade": "m", "Quantidade": tue_terra},
                {"Material": "Eletroduto Corrugado Flexível Reforçado 3/4\"", "Unidade": "m", "Quantidade": eletroduto_final}
            ])
            
            st.table(pd.DataFrame(materiais))
            
        except Exception as erro_visual:
            st.error(f"Erro interno de renderização: {erro_visual}")

# ==========================================
# 4. ROTEADOR DE TELAS
# ==========================================
if not st.session_state.usuario_autenticado:
    tela_login()
else:
    sistema_principal()
