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
# 1. MOTORES DE ENGENHARIA (NBR 5410 E DXF)
# ==========================================
def dimensionar_cargas(nome, area, perimetro):
    if area <= 0 or perimetro <= 0:
        return {"Qtd Ilum.": 0, "Pot. Unit. Ilum (VA)": 0, "Carga Ilum. (VA)": 0, "TUGs (Qtd)": 0, "Pot. Unit. TUG (VA)": 0, "Carga TUGs (VA)": 0, "Equipamento TUE": "-", "Qtd TUE": 0, "Pot. Unit. TUE (VA)": 0, "Carga TUE (VA)": 0}

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
    
    if any(x in nome_lower for x in ["banh", "wc", "bwc", "sanit"]): tue_nome, qtd_tue, carga_tue = "Chuveiro Elétrico", 1, 5500
    elif any(x in nome_lower for x in ["coz"]): tue_nome, qtd_tue, carga_tue = "Micro-ondas/Forno", 1, 2000
    elif any(x in nome_lower for x in ["quarto", "dorm", "suite"]): tue_nome, qtd_tue, carga_tue = "Ar-Condicionado", 1, 1200
    elif any(x in nome_lower for x in ["serv", "lavand"]): tue_nome, qtd_tue, carga_tue = "Máquina de Lavar", 1, 1000

    return {
        "Qtd Ilum.": qtd_ilum, "Pot. Unit. Ilum (VA)": round(carga_ilum / qtd_ilum) if qtd_ilum > 0 else 0, "Carga Ilum. (VA)": carga_ilum, 
        "TUGs (Qtd)": qtd_tugs, "Pot. Unit. TUG (VA)": round(carga_tugs / qtd_tugs) if qtd_tugs > 0 else 0, "Carga TUGs (VA)": carga_tugs,
        "Equipamento TUE": tue_nome, "Qtd TUE": qtd_tue, "Pot. Unit. TUE (VA)": round(carga_tue / qtd_tue) if qtd_tue > 0 else 0, "Carga TUE (VA)": carga_tue
    }

def processar_dxf(caminho_arquivo):
    doc = ezdxf.readfile(caminho_arquivo)
    msp = doc.modelspace()
    polilinhas, textos = [], []
    
    for entity in msp:
        tipo = entity.dxftype()
        layer = str(entity.dxf.layer).upper().strip() if hasattr(entity.dxf, 'layer') else ""
            
        if tipo in ['LWPOLYLINE', 'POLYLINE'] and layer == 'IA_AMBIENTES':
            try:
                pontos = [(p[0], p[1]) for p in entity.get_points(format='xy')] if tipo == 'LWPOLYLINE' else [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                if pontos: polilinhas.append(pontos)
            except Exception: continue
                
        elif tipo in ['TEXT', 'MTEXT'] and layer == 'IA_TEXTOS':
            try:
                texto_str = (entity.text if tipo == 'MTEXT' else entity.dxf.text).strip()
                if texto_str: textos.append({'nome': texto_str, 'x': entity.dxf.insert.x, 'y': entity.dxf.insert.y})
            except Exception: continue
            
    resultados, ambientes_processados = [], {}
    
    for polilinha in polilinhas:
        xs, ys = [p[0] for p in polilinha], [p[1] for p in polilinha]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        area, perimetro = (max_x - min_x) * (max_y - min_y), ((max_x - min_x) * 2) + ((max_y - min_y) * 2)
        if area < 0.5: continue
        
        nome_ambiente = next((t['nome'] for t in textos if (min_x - 0.5) <= t['x'] <= (max_x + 0.5) and (min_y - 0.5) <= t['y'] <= (max_y + 0.5)), None)
        if not nome_ambiente: continue
            
        if nome_ambiente in ambientes_processados:
            ambientes_processados[nome_ambiente] += 1
            nome_ambiente = f"{nome_ambiente} {ambientes_processados[nome_ambiente]}"
        else: ambientes_processados[nome_ambiente] = 1
                
        cargas = dimensionar_cargas(nome_ambiente, area, perimetro)
        resultados.append({
            "Ambiente": nome_ambiente, "Área (m²)": area, "Perímetro (m)": perimetro,
            **cargas
        })
    return resultados

# ==========================================
# 2. TELA DE LOGIN E CADASTRO
# ==========================================
def tela_login():
    st.title("🔐 Acesso - AutoElétrica SaaS")
    st.subheader("Bem-vindo à plataforma de projetos elétricos")
    if supabase is None:
        st.error("Erro Crítico: Não foi possível conectar ao banco de dados.")
        st.stop()
        
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_cadastro = st.tabs(["Fazer Login", "Criar Nova Conta"])
        
        with tab_login:
            with st.form("form_login"):
                email = st.text_input("E-mail")
                senha = st.text_input("Senha", type="password")
                if st.form_submit_button("Entrar no Sistema"):
                    try:
                        response = supabase.auth.sign_in_with_password({"email": email, "password": senha})
                        st.session_state.usuario_autenticado = True
                        st.session_state.user_email = email
                        st.session_state.user_id = response.user.id # CAPTURA O ID DO ENGENHEIRO
                        st.success("Login realizado com sucesso! Carregando...")
                        st.rerun()
                    except Exception as erro:
                        st.error("Credenciais inválidas. Verifique seu e-mail e senha.")

        with tab_cadastro:
            with st.form("form_cadastro"):
                novo_email = st.text_input("Seu E-mail")
                nova_senha = st.text_input("Crie uma Senha (mín. 6 caracteres)", type="password")
                if st.form_submit_button("Criar Minha Conta"):
                    if len(nova_senha) < 6: st.warning("A senha deve ter pelo menos 6 caracteres.")
                    else:
                        try:
                            response = supabase.auth.sign_up({"email": novo_email, "password": nova_senha})
                            st.success("✅ Conta criada com sucesso! Enviamos um link de confirmação para o seu e-mail. Valide seu cadastro antes de fazer o login.")
                        except Exception as erro: st.error(f"Erro ao criar conta: {erro}")

# ==========================================
# 3. SISTEMA PRINCIPAL (O SaaS)
# ==========================================
def sistema_principal():
    # --- GESTÃO DE OBRAS (SIDEBAR) ---
    with st.sidebar:
        st.write(f"👤 **{st.session_state.user_email}**")
        if st.button("Sair / Logout", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.clear()
            st.rerun()
            
        st.divider()
        st.write("📂 **Gerenciador de Obras**")
        
        # Buscar obras do usuário logado no banco de dados
        resposta_db = supabase.table("obras").select("*").eq("user_id", st.session_state.user_id).execute()
        obras_usuario = resposta_db.data

        # Criar nova obra
        with st.expander("➕ Novo Projeto / Pavimento"):
            nome_nova_obra = st.text_input("Nome do Empreendimento", placeholder="Ex: Edifício Alpha")
            nome_novo_pav = st.text_input("Pavimento", placeholder="Ex: Térreo")
            if st.button("Criar e Salvar"):
                if nome_nova_obra and nome_novo_pav:
                    supabase.table("obras").insert({
                        "user_id": st.session_state.user_id,
                        "nome_obra": nome_nova_obra,
                        "pavimento": nome_novo_pav,
                        "dados_json": [] # Inicia vazio
                    }).execute()
                    st.success("Criado!")
                    st.rerun()

        # Selecionar obra existente
        if obras_usuario:
            st.write("📖 **Projetos Salvos:**")
            opcoes_dict = {f"{ob['nome_obra']} - {ob['pavimento']}": ob for ob in obras_usuario}
            obra_escolhida = st.selectbox("Selecione o pavimento para trabalhar:", ["Nenhum"] + list(opcoes_dict.keys()))
            
if obra_escolhida != "Nenhum":
                obra_selecionada = opcoes_dict[obra_escolhida]
                # Se a obra mudou, atualiza a sessão
                if "obra_atual" not in st.session_state or st.session_state.obra_atual is None or st.session_state.obra_atual['id'] != obra_selecionada['id']:
                    st.session_state.obra_atual = obra_selecionada
                    st.session_state.dados_extraidos = obra_selecionada.get("dados_json", [])
                    st.rerun()
            else:
                st.session_state.obra_atual = None
                st.session_state.dados_extraidos = None
        else:
            st.info("Você ainda não tem obras cadastradas.")
            st.session_state.obra_atual = None

    # --- TELA PRINCIPAL ---
    st.title("⚡ Gerador de Projeto Elétrico Automatizado")
    
    if "obra_atual" not in st.session_state or st.session_state.obra_atual is None:
        st.info("👈 **Para começar:** Crie um novo projeto no menu lateral ou selecione um existente.")
        return # Para a execução aqui se não houver obra selecionada

    st.subheader(f"🏢 Empreendimento: {st.session_state.obra_atual['nome_obra']} | 📍 Pavimento: {st.session_state.obra_atual['pavimento']}")
    st.divider()

    # Se a obra estiver vazia (sem dados salvos), exibe o upload do DXF
    if not st.session_state.dados_extraidos:
        st.write("### 1. Importação da Planta Baixa (DXF)")
        arquivo_dxf = st.file_uploader("Faça o upload do arquivo (.dxf)", type=["dxf"])

        if arquivo_dxf is not None and st.button("Ler Arquivo CAD", type="primary"):
            with st.spinner("Extraindo e calculando geometria..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
                    tmp_file.write(arquivo_dxf.getvalue())
                    tmp_path = tmp_file.name
                try:
                    resultados = processar_dxf(tmp_path)
                    if len(resultados) > 0:
                        # Salva o resultado no Supabase automaticamente
                        supabase.table("obras").update({"dados_json": resultados}).eq("id", st.session_state.obra_atual['id']).execute()
                        st.session_state.dados_extraidos = resultados
                        st.rerun() 
                    else: st.warning("Não foram encontrados ambientes válidos.")
                except Exception as e: st.error(f"Erro ao processar: {e}")
                finally: os.remove(tmp_path)
    
    # Se já houver dados (recém extraídos ou baixados da nuvem)
    else:
        st.success("✅ Planta carregada do banco de dados! Ajuste os parâmetros abaixo.")
        st.divider()
        
        try:
            df_base = pd.DataFrame(st.session_state.dados_extraidos)
            
            ambientes_seguros = [amb for amb in df_base['Ambiente'].tolist() if not any(x in amb.lower() for x in ["coz", "serv", "banh", "lav", "wc", "bwc", "sanit"])]
            opcoes_qdc = ["Selecione o ambiente..."] + [f"{amb} (recomendado)" if any(t in amb.lower() for t in ["hall", "corredor", "circulação"]) else amb for amb in ambientes_seguros]
            opcoes_qdc = list(dict.fromkeys(opcoes_qdc))
            
            st.write("### ⚙️ Parâmetros Globais da Instalação")
            colA, colB, colC = st.columns([1, 1, 2])
            with colA: tensao_projeto = st.radio("Tensão do Projeto (V):", [127, 220], index=1, horizontal=True)
            with colB: pe_direito = st.number_input("Pé Direito (m):", value=2.80, step=0.10)
            with colC: local_qdc_selecionado = st.selectbox("Locação do QDC:", options=opcoes_qdc)
            st.info("📌 O QDC deve ficar a uma altura entre 1,50 m e 1,70 m. Proibido em áreas molhadas.")
            st.divider()
            
            st.write("### 🛠️ Ajuste Fino do Projetista")
            df_editado = df_base.copy()
            
            with st.expander("✏️ Editar Quantidades e Potências Unitárias", expanded=True):
                for index, row in df_editado.iterrows():
                    c1, c2, c3, c4, c5 = st.columns([1.2, 1.2, 1.2, 1.2, 1.2])
                    with c1: st.markdown(f"**{row['Ambiente']}**<br><small>Área: {row['Área (m²)']:.2f}m²</small>", unsafe_allow_html=True)
                    with c2:
                        nova_qtd_ilum = st.number_input("Qtd Ilum", value=int(row['Qtd Ilum.']), step=1, key=f"qilum_{index}")
                        nova_pot_ilum = st.number_input("Pot. Ilum", value=int(row['Pot. Unit. Ilum (VA)']), step=10, key=f"pilum_{index}")
                    with c3:
                        nova_qtd_tug = st.number_input("Qtd TUG", value=int(row['TUGs (Qtd)']), step=1, key=f"qtug_{index}")
                        nova_pot_tug = st.number_input("Pot. TUG", value=int(row['Pot. Unit. TUG (VA)']), step=10, key=f"ptug_{index}")
                    with c4:
                        novo_equip = st.text_input("Equip. TUE", value=str(row['Equipamento TUE']), key=f"eq_{index}")
                        nova_qtd_tue = st.number_input("Qtd TUE", value=int(row['Qtd TUE']), step=1, key=f"qtue_{index}")
                    with c5:
                        nova_pot_tue = st.number_input("Pot. TUE", value=int(row['Pot. Unit. TUE (VA)']), step=100, key=f"ptue_{index}")
                    
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

            # BOTÃO MÁGICO DO SAAS (Salva as edições do projetista no Banco de Dados)
            if st.button("💾 Salvar Alterações na Nuvem", type="primary"):
                # Transforma o DataFrame editado de volta em JSON
                dados_atualizados = df_editado.to_dict(orient='records')
                supabase.table("obras").update({"dados_json": dados_atualizados}).eq("id", st.session_state.obra_atual['id']).execute()
                # Atualiza a memória local para não perder o sincronismo
                st.session_state.dados_extraidos = dados_atualizados
                st.success("✅ Projeto atualizado e salvo na nuvem com sucesso!")
            
            st.write("### 📊 Quadro de Previsão de Cargas Consolidado")
            linha_total = pd.DataFrame([{
                "Ambiente": "TOTAL", "Área (m²)": df_editado["Área (m²)"].sum(), "Perímetro (m)": df_editado["Perímetro (m)"].sum(),
                "Qtd Ilum.": df_editado["Qtd Ilum."].sum(), "Carga Ilum. (VA)": df_editado["Carga Ilum. (VA)"].sum(),
                "TUGs (Qtd)": df_editado["TUGs (Qtd)"].sum(), "Carga TUGs (VA)": df_editado["Carga TUGs (VA)"].sum(),
                "Equipamento TUE": "-", "Qtd TUE": df_editado["Qtd TUE"].sum(), "Carga TUE (VA)": df_editado["Carga TUE (VA)"].sum()
            }])
            df_final = pd.concat([df_editado, linha_total], ignore_index=True).drop(columns=["Pot. Unit. Ilum (VA)", "Pot. Unit. TUG (VA)", "Pot. Unit. TUE (VA)"])
            st.table(df_final) 

            st.divider()
            st.write("### 📦 Tabela Quantitativa de Materiais")
            
            acrescimo_qdc = 5 if local_qdc_selecionado == "Selecione o ambiente..." else (0 if "(recomendado)" in local_qdc_selecionado else 3)
            total_eletroduto = total_cabo_ilum = total_cabo_tug = total_cabo_tue = 0
            dist_base_qdc = 4 + acrescimo_qdc

            for index, row in df_editado.iterrows():
                area_amb, perim_amb = float(row["Área (m²)"]), float(row["Perímetro (m)"])
                q_ilum, q_tug, q_tue = float(row["Qtd Ilum."]), float(row["TUGs (Qtd)"]), float(row["Qtd TUE"])
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
                    
            cabo_ilum_final, cabo_tug_final, cabo_tue_final, eletroduto_final = round(total_cabo_ilum * 1.15), round(total_cabo_tug * 1.15), round(total_cabo_tue * 1.15), round(total_eletroduto * 1.10)
            ilum_fase = ilum_neutro = ilum_retorno = math.ceil(cabo_ilum_final / 3)
            tug_fase = tug_neutro = tug_terra = math.ceil(cabo_tug_final / 3)
            tue_fase = tue_neutro_fase = tue_terra = math.ceil(cabo_tue_final / 3)

            total_interruptores = len(df_editado) 
            caixas_teto = int(df_editado["Qtd Ilum."].sum())
            caixas_parede = int(df_editado["TUGs (Qtd)"].sum()) + int(df_editado[df_editado["Qtd TUE"] > 0]["Qtd TUE"].sum()) + total_interruptores
            
            def calc_disj(potencia_va):
                if potencia_va <= 0: return 10
                return next((d for d in [10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125] if d >= (potencia_va / tensao_projeto)), 125)

            disj_geral = calc_disj(df_editado["Carga Ilum. (VA)"].sum() + df_editado["Carga TUGs (VA)"].sum() + df_editado["Carga TUE (VA)"].sum())
            idr_geral = next((d for d in [25, 40, 63, 80, 100, 125] if d >= disj_geral), 125)
            
            materiais = [
                {"Material": "Caixa Octogonal Teto 4x4\"", "Qtd": caixas_teto}, {"Material": "Caixa Parede 4x2\"", "Qtd": caixas_parede},
                {"Material": "Interruptor Simples (cj)", "Qtd": total_interruptores}, {"Material": "Tomada 2P+T 10A (cj)", "Qtd": int(df_editado["TUGs (Qtd)"].sum())},
                {"Material": "QDC (16 a 24 Módulos)", "Qtd": 1}, {"Material": f"Disjuntor Geral DIN {disj_geral}A", "Qtd": 1},
                {"Material": f"IDR Tetrapolar {idr_geral}A / 30mA", "Qtd": 1}, {"Material": "DPS Classe II (275V/45kA)", "Qtd": 2},
                {"Material": f"Disjuntor DIN {calc_disj(df_editado['Carga Ilum. (VA)'].sum())}A (Iluminação)", "Qtd": 1},
                {"Material": f"Disjuntor DIN {calc_disj(df_editado['Carga TUGs (VA)'].sum() / 2)}A (TUGs)", "Qtd": 2 if df_editado["Carga TUGs (VA)"].sum() > 0 else 0}
            ]
            for _, row in df_editado[df_editado["Qtd TUE"] > 0].iterrows(): materiais.append({"Material": f"Disjuntor DIN {calc_disj(row['Pot. Unit. TUE (VA)'])}A (TUE: {row['Equipamento TUE']})", "Qtd": int(row["Qtd TUE"])})
            materiais.extend([
                {"Material": "Cabo Flex 1,5mm² (Ilum)", "Qtd": f"{cabo_ilum_final} m (F/N/R)"},
                {"Material": "Cabo Flex 2,5mm² (TUG)", "Qtd": f"{cabo_tug_final} m (F/N/T)"},
                {"Material": "Cabo Flex 4/6mm² (TUE)", "Qtd": f"{cabo_tue_final} m (F/N/T)"},
                {"Material": "Eletroduto Corrugado 3/4\"", "Qtd": f"{eletroduto_final} m"}
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
