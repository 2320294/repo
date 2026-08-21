import streamlit as st
from supabase import create_client, Client
import ezdxf
import math
import tempfile
import os
import pandas as pd
import unicodedata
import io
from datetime import datetime

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
    
    for entity in msp:
        tipo = entity.dxftype()
        if hasattr(entity.dxf, 'layer'):
            layer = str(entity.dxf.layer).upper().strip()
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
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)
        
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
        
    return resultados

def gerar_cad_unifilar(dxf_bytes, dados_editados, local_qdc):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_in:
        tmp_in.write(dxf_bytes)
        tmp_in_path = tmp_in.name
        
    try:
        doc = ezdxf.readfile(tmp_in_path)
        msp = doc.modelspace()
        
        if "PROJ_ELETRICA_LUZ" not in doc.layers:
            doc.layers.add(name="PROJ_ELETRICA_LUZ", color=2)
        if "PROJ_ELETRICA_QDC" not in doc.layers:
            doc.layers.add(name="PROJ_ELETRICA_QDC", color=1)
        if "PROJ_ELETRICA_TEXTO" not in doc.layers:
            doc.layers.add(name="PROJ_ELETRICA_TEXTO", color=3)
        if "PROJ_ELETRICA_TOMADA" not in doc.layers:
            doc.layers.add(name="PROJ_ELETRICA_TOMADA", color=4)
        
        polilinhas = []
        textos = []
        portas = [] 
        
        for entity in msp:
            tipo = entity.dxftype()
            if hasattr(entity.dxf, 'layer'):
                layer = str(entity.dxf.layer).upper().strip()
                
                if tipo in ['LWPOLYLINE', 'POLYLINE'] and layer == 'IA_AMBIENTES':
                    try:
                        pontos = [(p[0], p[1]) for p in entity.get_points(format='xy')] if tipo == 'LWPOLYLINE' else [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                        if pontos: polilinhas.append(pontos)
                    except: pass
                
                elif tipo in ['TEXT', 'MTEXT'] and layer == 'IA_TEXTOS':
                    try:
                        texto_str = (entity.text if tipo == 'MTEXT' else entity.dxf.text).strip()
                        if texto_str: textos.append({'nome': texto_str, 'x': entity.dxf.insert.x, 'y': entity.dxf.insert.y})
                    except: pass
                
                elif layer == 'IA_PORTAS':
                    try:
                        if tipo == 'LINE':
                            px = (entity.dxf.start.x + entity.dxf.end.x) / 2
                            py = (entity.dxf.start.y + entity.dxf.end.y) / 2
                            portas.append({'x': px, 'y': py})
                        elif tipo in ['LWPOLYLINE', 'POLYLINE']:
                            pontos_p = [(p[0], p[1]) for p in entity.get_points(format='xy')] if tipo == 'LWPOLYLINE' else [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                            if pontos_p:
                                px = sum([p[0] for p in pontos_p]) / len(pontos_p)
                                py = sum([p[1] for p in pontos_p]) / len(pontos_p)
                                portas.append({'x': px, 'y': py})
                    except: pass
                    
        ambientes_processados = {}
        dict_dados = {row['Ambiente']: row for row in dados_editados}
        
        for polilinha in polilinhas:
            xs = [p[0] for p in polilinha]
            ys = [p[1] for p in polilinha]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            
            if (max_x - min_x) * (max_y - min_y) < 0.5: continue
            
            nome_ambiente = None
            for t in textos:
                if (min_x - 0.5) <= t['x'] <= (max_x + 0.5) and (min_y - 0.5) <= t['y'] <= (max_y + 0.5):
                    nome_ambiente = t['nome']
                    break
                    
            if not nome_ambiente: continue
            
            if nome_ambiente in ambientes_processados:
                ambientes_processados[nome_ambiente] += 1
                nome_ambiente = f"{nome_ambiente} {ambientes_processados[nome_ambiente]}"
            else:
                ambientes_processados[nome_ambiente] = 1
            
            centro_x = (min_x + max_x) / 2
            centro_y = (min_y + max_y) / 2
            
            if nome_ambiente in dict_dados:
                dados_amb = dict_dados[nome_ambiente]
                
                # 1. PONTO DE LUZ
                if dados_amb['Qtd Ilum.'] > 0:
                    msp.add_circle(center=(centro_x, centro_y), radius=0.25, dxfattribs={'layer': 'PROJ_ELETRICA_LUZ'})
                    potencia_luz = f"{dados_amb['Pot. Unit. Ilum (VA)']}VA"
                    msp.add_text(potencia_luz, dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.15, 'insert': (centro_x + 0.3, centro_y - 0.07)})
                    
                # 2. QUADRO DE DISTRIBUIÇÃO
                qdc_formatado = str(local_qdc).replace(" (recomendado)", "")
                if nome_ambiente == qdc_formatado:
                    porta_ambiente = None
                    for p in portas:
                        if (min_x - 0.5) <= p['x'] <= (max_x + 0.5) and (min_y - 0.5) <= p['y'] <= (max_y + 0.5):
                            porta_ambiente = p
                            break
                    
                    qdc_w, qdc_d = 0.4, 0.15
                    afastamento = 0.8
                    
                    if porta_ambiente:
                        px, py = porta_ambiente['x'], porta_ambiente['y']
                        dist_esq = abs(px - min_x)
                        dist_dir = abs(px - max_x)
                        dist_baixo = abs(py - min_y)
                        dist_cima = abs(py - max_y)
                        menor_dist = min(dist_esq, dist_dir, dist_baixo, dist_cima)
                        
                        if menor_dist == dist_cima: 
                            start_x = px + afastamento if (px + afastamento + qdc_w) <= max_x else px - afastamento - qdc_w
                            pts = [(start_x, max_y), (start_x + qdc_w, max_y), (start_x + qdc_w, max_y - qdc_d), (start_x, max_y - qdc_d)]
                            cx, cy = start_x + (qdc_w / 2), max_y - (qdc_d / 2)
                            txt_pos = (cx - 0.08, cy - 0.035)
                            rot = 0
                        elif menor_dist == dist_baixo: 
                            start_x = px + afastamento if (px + afastamento + qdc_w) <= max_x else px - afastamento - qdc_w
                            pts = [(start_x, min_y), (start_x + qdc_w, min_y), (start_x + qdc_w, min_y + qdc_d), (start_x, min_y + qdc_d)]
                            cx, cy = start_x + (qdc_w / 2), min_y + (qdc_d / 2)
                            txt_pos = (cx - 0.08, cy - 0.035)
                            rot = 0
                        elif menor_dist == dist_esq: 
                            start_y = py + afastamento if (py + afastamento + qdc_w) <= max_y else py - afastamento - qdc_w
                            pts = [(min_x, start_y), (min_x + qdc_d, start_y), (min_x + qdc_d, start_y + qdc_w), (min_x, start_y + qdc_w)]
                            cx, cy = min_x + (qdc_d / 2), start_y + (qdc_w / 2)
                            txt_pos = (cx + 0.035, cy - 0.08)
                            rot = 90
                        else: 
                            start_y = py + afastamento if (py + afastamento + qdc_w) <= max_y else py - afastamento - qdc_w
                            pts = [(max_x, start_y), (max_x - qdc_d, start_y), (max_x - qdc_d, start_y + qdc_w), (max_x, start_y + qdc_w)]
                            cx, cy = max_x - (qdc_d / 2), start_y + (qdc_w / 2)
                            txt_pos = (cx + 0.035, cy - 0.08)
                            rot = 90
                    else:
                        start_x = centro_x - 0.2
                        pts = [(start_x, max_y), (start_x + qdc_w, max_y), (start_x + qdc_w, max_y - qdc_d), (start_x, max_y - qdc_d)]
                        cx, cy = start_x + (qdc_w / 2), max_y - (qdc_d / 2)
                        txt_pos = (cx - 0.08, cy - 0.035)
                        rot = 0
                    
                    msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': 'PROJ_ELETRICA_QDC'})
                    msp.add_text("QDC", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.07, 'color': 1, 'rotation': rot, 'insert': txt_pos})

                # 3. TOMADAS ORTOGONAIS (MOTOR INFALÍVEL POR DISTÂNCIA)
                qtd_tugs = int(dados_amb.get('TUGs (Qtd)', 0))
                qtd_tues = int(dados_amb.get('Qtd TUE', 0))
                total_tomadas = qtd_tugs + qtd_tues
                
                if total_tomadas > 0 and len(polilinha) >= 3:
                    poly_fechada = list(polilinha)
                    if poly_fechada[0] != poly_fechada[-1]:
                        poly_fechada.append(poly_fechada[0])
                        
                    segmentos = []
                    comp_total = 0
                    for i in range(len(poly_fechada)-1):
                        p1 = poly_fechada[i]
                        p2 = poly_fechada[i+1]
                        dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                        if dist > 0:
                            segmentos.append((p1, p2, dist))
                            comp_total += dist
                            
                    passo = comp_total / total_tomadas
                    dist_atual = passo / 2 
                    
                    idx_seg = 0
                    comp_acumulado = 0
                    tomadas_pos = 0
                    
                    while tomadas_pos < total_tomadas and idx_seg < len(segmentos):
                        p1, p2, dist = segmentos[idx_seg]
                        if comp_acumulado + dist >= dist_atual:
                            ratio = (dist_atual - comp_acumulado) / dist
                            px = p1[0] + (p2[0] - p1[0]) * ratio
                            py = p1[1] + (p2[1] - p1[1]) * ratio
                            
                            dx_parede = p2[0] - p1[0]
                            dy_parede = p2[1] - p1[1]
                            mag_parede = math.hypot(dx_parede, dy_parede)
                            
                            if mag_parede > 0:
                                ux_w = dx_parede / mag_parede
                                uy_w = dy_parede / mag_parede
                                
                                perto_porta = False
                                for p in portas:
                                    if math.hypot(px - p['x'], py - p['y']) < 0.6:
                                        perto_porta = True
                                        break
                                
                                if perto_porta:
                                    px = px + (ux_w * 0.6)
                                    py = py + (uy_w * 0.6)
                                
                                # Cria as duas perpendiculares possíveis (+90 e -90 graus)
                                n1x, n1y = -uy_w, ux_w
                                n2x, n2y = uy_w, -ux_w
                                
                                base_half = 0.15
                                height = 0.25
                                
                                # Simula as duas pontas possíveis
                                ponta1 = (px + n1x * height, py + n1y * height)
                                ponta2 = (px + n2x * height, py + n2y * height)
                                
                                # A ponta certa é a que estiver MAIS PERTO do Ponto de Luz (centro)
                                dist_ponta1_centro = math.hypot(centro_x - ponta1[0], centro_y - ponta1[1])
                                dist_ponta2_centro = math.hypot(centro_x - ponta2[0], centro_y - ponta2[1])
                                
                                if dist_ponta1_centro < dist_ponta2_centro:
                                    ux_n, uy_n = n1x, n1y
                                    pt_ponta = ponta1
                                else:
                                    ux_n, uy_n = n2x, n2y
                                    pt_ponta = ponta2
                                
                                pt_base1 = (px + ux_w * base_half, py + uy_w * base_half)
                                pt_base2 = (px - ux_w * base_half, py - uy_w * base_half)
                                
                                msp.add_lwpolyline([pt_base1, pt_base2, pt_ponta, pt_base1], close=True, dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                                
                                if tomadas_pos >= qtd_tugs:
                                    txt_tue = str(dados_amb.get('Equipamento TUE', 'TUE'))
                                    txt_px = px + ux_n * (height + 0.1)
                                    txt_py = py + uy_n * (height + 0.1)
                                    msp.add_text(txt_tue, dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.1, 'color': 4, 'insert': (txt_px, txt_py)})
                            
                            dist_atual += passo
                            tomadas_pos += 1
                        else:
                            comp_acumulado += dist
                            idx_seg += 1

        tmp_out_path = tmp_in_path.replace(".dxf", "_out.dxf")
        doc.saveas(tmp_out_path)
        
        with open(tmp_out_path, "rb") as f:
            out_bytes = f.read()
            
        os.remove(tmp_out_path)
        return out_bytes
        
    finally:
        os.remove(tmp_in_path)

# ==========================================
# 2. TELA DE LOGIN E CADASTRO
# ==========================================
def tela_login():
    st.title("🔐 Acesso - AutoElétrica")
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
                submit_login = st.form_submit_button("Entrar no Sistema")
                
                if submit_login:
                    try:
                        response = supabase.auth.sign_in_with_password({"email": email, "password": senha})
                        st.session_state.usuario_autenticado = True
                        st.session_state.user_email = email
                        st.session_state.user_id = response.user.id
                        st.success("Login realizado com sucesso! Carregando plataforma...")
                        st.rerun()
                    except Exception as erro:
                        st.error("Credenciais inválidas. Verifique seu e-mail e senha.")

        with tab_cadastro:
            with st.form("form_cadastro"):
                novo_email = st.text_input("Seu E-mail")
                nova_senha = st.text_input("Crie uma Senha (mín. 6 caracteres)", type="password")
                submit_cadastro = st.form_submit_button("Criar Minha Conta")
                
                if submit_cadastro:
                    if len(nova_senha) < 6:
                        st.warning("A senha deve ter pelo menos 6 caracteres.")
                    else:
                        try:
                            response = supabase.auth.sign_up({"email": novo_email, "password": nova_senha})
                            st.success("✅ Conta criada com sucesso! Verifique sua caixa de entrada.")
                        except Exception as erro:
                            st.error(f"Erro ao criar conta. Detalhes: {erro}")

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
            
            df_final = df_final.rename(columns={
                "Qtd TUE": "TUEs (Qtd)",
                "Carga TUE (VA)": "Carga TUEs (VA)"
            })
            
            ordem_colunas = [
                "Ambiente", 
                "Área (m²)", 
                "Perímetro (m)", 
                "Qtd Ilum.", 
                "Carga Ilum. (VA)", 
                "TUGs (Qtd)", 
                "Carga TUGs (VA)", 
                "TUEs (Qtd)", 
                "Carga TUEs (VA)", 
                "Equipamento TUE"
            ]
            
            df_final = df_final[ordem_colunas]
            
            df_final_exibir = df_final.copy()
            df_final_exibir["Área (m²)"] = df_final_exibir["Área (m²)"].apply(lambda x: f"{x:.2f}".replace(".", ","))
            df_final_exibir["Perímetro (m)"] = df_final_exibir["Perímetro (m)"].apply(lambda x: f"{x:.2f}".replace(".", ","))
            st.table(df_final_exibir) 

            st.divider()
            st.write("### 📦 Tabela Quantitativa de Materiais")
            
            if local_qdc_selecionado == "Selecione o ambiente...":
                acrescimo_qdc = 5  
                st.warning("⚠️ **Aviso:** Como o QDC não foi alocado, o sistema adicionou 5m de margem na rota dos circuitos.")
            elif "(recomendado)" in local_qdc_selecionado:
                acrescimo_qdc = 0  
                st.success("✅ **Otimização Ativa:** QDC em circulação minimizou rotas.")
            else:
                acrescimo_qdc = 3  

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
                    if d >= corrente_proj:
                        return d
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
                materiais.append({
                    "Material": f"Disjuntor DIN {dj_tue}A (Circuito Específico TUE: {row['Equipamento TUE']} - {row['Ambiente']})",
                    "Unidade": "pç", 
                    "Quantidade": int(row["Qtd TUE"])
                })
                
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
                
                st.download_button(
                    label="📊 Baixar Planilha (Excel)",
                    data=buffer_excel.getvalue(),
                    file_name=f"Orcamento_{st.session_state.obra_atual['nome_obra']}_{st.session_state.obra_atual['pavimento']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
            with col_exp2:
                if FPDF is not None:
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 16)
                    
                    def formatar_txt(texto):
                        return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8')
                        
                    pdf.cell(0, 10, formatar_txt(f"Memorial Descritivo: {st.session_state.obra_atual['nome_obra']}"), ln=True, align='C')
                    pdf.set_font("Arial", 'I', 12)
                    pdf.cell(0, 10, formatar_txt(f"Pavimento: {st.session_state.obra_atual['pavimento']} | Data: {datetime.now().strftime('%d/%m/%Y')}"), ln=True, align='C')
                    pdf.ln(10)
                    
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 10, "1. Resumo de Cargas:", ln=True)
                    pdf.set_font("Arial", '', 10)
                    pdf.cell(0, 8, formatar_txt(f"Carga Total de Iluminacao: {df_editado['Carga Ilum. (VA)'].sum()} VA"), ln=True)
                    pdf.cell(0, 8, formatar_txt(f"Carga Total de TUGs: {df_editado['Carga TUGs (VA)'].sum()} VA"), ln=True)
                    pdf.cell(0, 8, formatar_txt(f"Carga Total de TUEs: {df_editado['Carga TUE (VA)'].sum()} VA"), ln=True)
                    pdf.ln(5)
                    
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 10, "2. Diretrizes de Execucao (NBR 5410):", ln=True)
                    pdf.set_font("Arial", '', 10)
                    pdf.cell(0, 8, formatar_txt(f"Tensao adotada: {tensao_projeto}V"), ln=True)
                    pdf.cell(0, 8, formatar_txt(f"Pe Direito adotado: {pe_direito}m"), ln=True)
                    pdf.cell(0, 8, formatar_txt(f"Local sugerido para o QDC: {texto_local_qdc}"), ln=True)
                    pdf.ln(5)

                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 10, "3. Lista Quantitativa de Materiais:", ln=True)
                    pdf.set_font("Arial", '', 10)
                    for idx, row_mat in df_materiais_final.iterrows():
                        texto_mat = f"- {row_mat['Quantidade']} {row_mat['Unidade']} : {row_mat['Material']}"
                        pdf.cell(0, 6, formatar_txt(texto_mat), ln=True)
                    
                    try:
                        pdf_bytes = pdf.output(dest='S').encode('latin1')
                        st.download_button(
                            label="📄 Baixar Memorial (PDF)",
                            data=pdf_bytes,
                            file_name=f"Memorial_{st.session_state.obra_atual['nome_obra']}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Erro ao gerar PDF: {e}")
                else:
                    st.warning("⚠️ Adicione 'fpdf' no requirements.txt")

            with col_exp3:
                st.write("**Projeto Unifilar (DXF)**")
                arquivo_base = st.file_uploader("Reenvie a planta base:", type=["dxf"], key="dxf_unifilar")
                
                if arquivo_base is not None:
                    dados_dxf_atualizados = df_editado.to_dict(orient='records')
                    if st.button("🎨 Gerar CAD (Fase 1 e 2)", type="primary", use_container_width=True):
                        with st.spinner("Desenhando projeto no CAD..."):
                            try:
                                dxf_desenhado = gerar_cad_unifilar(arquivo_base.getvalue(), dados_dxf_atualizados, local_qdc_selecionado)
                                st.download_button(
                                    label="⬇️ Baixar DXF Desenhado",
                                    data=dxf_desenhado,
                                    file_name=f"Proj_Eletrico_{st.session_state.obra_atual['nome_obra']}.dxf",
                                    mime="application/dxf",
                                    use_container_width=True
                                )
                                st.success("Desenho gerado com sucesso!")
                            except Exception as e:
                                st.error(f"Erro ao desenhar DXF: {e}")
                else:
                    st.info("Para desenhar os pontos na planta, anexe o .dxf acima.")

        except Exception as erro_visual:
            st.error(f"Erro interno de renderização: {erro_visual}")

# ==========================================
# 4. ROTEADOR DE TELAS
# ==========================================
if not st.session_state.usuario_autenticado:
    tela_login()
else:
    sistema_principal()