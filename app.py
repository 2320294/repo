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

def dimensionar_cargas(nome, area, perimetro):
    if area <= 0 or perimetro <= 0:
        return {"Qtd Ilum.": 0, "Pot. Unit. Ilum (VA)": 0, "Carga Ilum. (VA)": 0, "TUGs (Qtd)": 0, "Pot. Unit. TUG (VA)": 0, "Carga TUGs (VA)": 0, "Equipamento TUE": "-", "Qtd TUE": 0, "Pot. Unit. TUE (VA)": 0, "Carga TUE (VA)": 0}
    qtd_ilum = 1 if area <= 10 else math.ceil(area / 10)
    carga_ilum = 100 if area <= 6 else 100 + (((area - 6) // 4) * 60)
    nome_lower = nome.lower().strip()
    nome_words = nome_lower.replace('-', ' ').split()
    is_umida = any(x in nome_lower for x in ["coz", "serv", "banh", "lav", "sanit", "área", "area"]) or any(w in nome_words for w in ["as", "wc", "bwc"])
    is_corredor = any(x in nome_lower for x in ["hall", "corredor", "circulação", "circulacao"])
    if is_umida:
        qtd_tugs = math.ceil(perimetro / 3.5)
        carga_tugs = (qtd_tugs * 600) if qtd_tugs <= 3 else (3 * 600) + ((qtd_tugs - 3) * 100)
    elif is_corredor:
        comprimento_estimado = (perimetro / 2) - 1
        qtd_tugs = 1 if comprimento_estimado <= 3 else max(1, math.ceil(comprimento_estimado / 3))
        carga_tugs = qtd_tugs * 100
    else:
        qtd_tugs = math.ceil(perimetro / 5)
        carga_tugs = qtd_tugs * 100
    tue_nome = "-"
    qtd_tue = 0
    carga_tue = 0
    if any(x in nome_lower for x in ["banh", "sanit"]) or any(w in nome_words for w in ["wc", "bwc"]):
        tue_nome = "Chuveiro Elétrico"; qtd_tue = 1; carga_tue = 5500
    elif any(x in nome_lower for x in ["coz"]):
        tue_nome = "Micro-ondas/Forno"; qtd_tue = 1; carga_tue = 2000
    elif any(x in nome_lower for x in ["quarto", "dorm", "suite"]):
        tue_nome = "Ar-Condicionado"; qtd_tue = 1; carga_tue = 1200
    elif any(x in nome_lower for x in ["serv", "lavand"]) or "as" in nome_words:
        tue_nome = "Máquina de Lavar"; qtd_tue = 1; carga_tue = 1000
    return {"Qtd Ilum.": qtd_ilum, "Pot. Unit. Ilum (VA)": round(carga_ilum/qtd_ilum) if qtd_ilum>0 else 0, "Carga Ilum. (VA)": carga_ilum, "TUGs (Qtd)": qtd_tugs, "Pot. Unit. TUG (VA)": round(carga_tugs/qtd_tugs) if qtd_tugs>0 else 0, "Carga TUGs (VA)": carga_tugs, "Equipamento TUE": tue_nome, "Qtd TUE": qtd_tue, "Pot. Unit. TUE (VA)": round(carga_tue/qtd_tue) if qtd_tue>0 else 0, "Carga TUE (VA)": carga_tue}

def processar_dxf(caminho_arquivo):
    doc = ezdxf.readfile(caminho_arquivo); msp = doc.modelspace()
    polilinhas = []; textos = []
    for entity in msp:
        tipo = entity.dxftype()
        if hasattr(entity.dxf, 'layer'):
            layer = str(entity.dxf.layer).upper().strip()
            if tipo in ['LWPOLYLINE', 'POLYLINE'] and layer == 'IA_AMBIENTES':
                pontos = [(p[0], p[1]) for p in entity.get_points(format='xy')] if tipo == 'LWPOLYLINE' else [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                if pontos: polilinhas.append(pontos)
            elif tipo in ['TEXT', 'MTEXT'] and layer == 'IA_TEXTOS':
                texto_str = (entity.text if tipo == 'MTEXT' else entity.dxf.text).strip()
                if texto_str: textos.append({'nome': texto_str, 'x': entity.dxf.insert.x, 'y': entity.dxf.insert.y})
    resultados = []
    ambientes_processados = {}
    for polilinha in polilinhas:
        xs = [p[0] for p in polilinha]; ys = [p[1] for p in polilinha]
        min_x, max_x = min(xs), max(xs); min_y, max_y = min(ys), max(ys)
        area = (max_x - min_x) * (max_y - min_y)
        if area < 0.5: continue
        nome_ambiente = None
        for t in textos:
            if (min_x-0.5) <= t['x'] <= (max_x+0.5) and (min_y-0.5) <= t['y'] <= (max_y+0.5):
                nome_ambiente = t['nome']; break
        if not nome_ambiente: continue
        if nome_ambiente in ambientes_processados:
            ambientes_processados[nome_ambiente] += 1
            nome_ambiente = f"{nome_ambiente} {ambientes_processados[nome_ambiente]}"
        else: ambientes_processados[nome_ambiente] = 1
        cargas = dimensionar_cargas(nome_ambiente, (max_x-min_x)*(max_y-min_y), (max_x-min_x)*2 + (max_y-min_y)*2)
        resultados.append({"Ambiente": nome_ambiente, "Área (m²)": area, "Perímetro (m)": (max_x-min_x)*2 + (max_y-min_y)*2, **cargas})
    return resultados

def get_inside_normal(vx, vy, cx, cy, min_x, max_x, min_y, max_y):
    normals = [(-vy, vx), (vy, -vx)]
    best_n = normals[0]
    min_dist = float('inf')
    for nx, ny in normals:
        test_x, test_y = cx + nx * 0.5, cy + ny * 0.5
        if min_x <= test_x <= max_x and min_y <= test_y <= max_y: best_n = (nx, ny); break
    return best_n

def point_seg_dist(px, py, pt1, pt2):
    l2 = (pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2
    if l2 == 0: return math.hypot(px - pt1[0], py - pt1[1])
    t = max(0, min(1, ((px - pt1[0])*(pt2[0] - pt1[0]) + (py - pt1[1])*(pt2[1] - pt1[1])) / l2))
    return math.hypot(px - (pt1[0] + t * (pt2[0] - pt1[0])), py - (pt1[1] + t * (pt2[1] - pt1[1])))

def dist_to_line(px, py, pt1, pt2):
    den = math.hypot(pt2[0]-pt1[0], pt2[1]-pt1[1])
    return abs((pt2[0]-pt1[0])*(pt1[1]-py) - (pt1[0]-px)*(pt2[1]-pt1[1])) / den if den != 0 else math.hypot(px-pt1[0], py-pt1[1])

def get_dist_on_perimeter(px, py, segs):
    acumulado = 0
    min_d = float('inf'); best_d = 0
    for pt1, pt2, dst in segs:
        l2 = (pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2
        if l2 == 0: continue
        t = max(0, min(1, ((px - pt1[0])*(pt2[0] - pt1[0]) + (py - pt1[1])*(pt2[1] - pt1[1])) / l2))
        d = math.hypot(px - (pt1[0] + t * (pt2[0] - pt1[0])), py - (pt1[1] + t * (pt2[1] - pt1[1])))
        if d < min_d: min_d = d; best_d = acumulado + (t * dst)
        acumulado += dst
    return best_d

def get_ponto_perimetro(d, segs):
    acumulado = 0
    for pt1, pt2, dst in segs:
        if acumulado + dst >= d or math.isclose(acumulado + dst, d, abs_tol=1e-5):
            ratio = (d - acumulado) / dst
            return pt1[0] + (pt2[0] - pt1[0]) * ratio, pt1[1] + (pt2[1] - pt1[1]) * ratio, (pt2[0]-pt1[0])/dst, (pt2[1]-pt1[1])/dst
        acumulado += dst
    pt1, pt2, dst = segs[-1]
    return pt2[0], pt2[1], (pt2[0]-pt1[0])/dst, (pt2[1]-pt1[1])/dst

def gerar_cad_unifilar(dxf_bytes, dados_editados, local_qdc):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_in:
        tmp_in.write(dxf_bytes); tmp_in_path = tmp_in.name
    try:
        doc = ezdxf.readfile(tmp_in_path); msp = doc.modelspace()
        for layer in ["PROJ_ELETRICA_LUZ", "PROJ_ELETRICA_QDC", "PROJ_ELETRICA_TEXTO", "PROJ_ELETRICA_TOMADA", "PROJ_ELETRICA_INTERRUPTOR"]:
            if layer not in doc.layers: doc.layers.add(name=layer, color=1 if "QDC" in layer else 2 if "LUZ" in layer else 4 if "TOMADA" in layer else 5)
        
        polilinhas = []; textos = []; portas = []; soleiras = []
        for entity in msp:
            tipo = entity.dxftype(); layer = str(entity.dxf.layer).upper().strip()
            if tipo in ['LWPOLYLINE', 'POLYLINE'] and layer == 'IA_AMBIENTES':
                polilinhas.append([(p[0], p[1]) for p in entity.get_points(format='xy')] if tipo == 'LWPOLYLINE' else [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices])
            elif tipo in ['TEXT', 'MTEXT'] and layer == 'IA_TEXTOS':
                textos.append({'nome': (entity.text if tipo == 'MTEXT' else entity.dxf.text).strip(), 'x': entity.dxf.insert.x, 'y': entity.dxf.insert.y})
            elif layer == 'IA_PORTAS':
                if tipo == 'LINE': portas.append({'tipo': 'LINE', 'x': (entity.dxf.start.x+entity.dxf.end.x)/2, 'y': (entity.dxf.start.y+entity.dxf.end.y)/2, 'p1': (entity.dxf.start.x, entity.dxf.start.y), 'p2': (entity.dxf.end.x, entity.dxf.end.y)})
            elif layer == 'IA_SOLEIRA':
                if tipo == 'LINE': soleiras.append({'p1': (entity.dxf.start.x, entity.dxf.start.y), 'p2': (entity.dxf.end.x, entity.dxf.end.y)})
        
        dict_dados = {row['Ambiente']: row for row in dados_editados}
        for polilinha in polilinhas:
            xs = [p[0] for p in polilinha]; ys = [p[1] for p in polilinha]
            min_x, max_x = min(xs), max(xs); min_y, max_y = min(ys), max(ys)
            nome_ambiente = next((t['nome'] for t in textos if (min_x-0.5) <= t['x'] <= (max_x+0.5) and (min_y-0.5) <= t['y'] <= (max_y+0.5)), None)
            if not nome_ambiente or nome_ambiente not in dict_dados: continue
            
            centro_x, centro_y = (min_x + max_x) / 2, (min_y + max_y) / 2
            segmentos = []
            poly = list(polilinha); poly.append(poly[0])
            for i in range(len(poly)-1):
                pt1, pt2 = poly[i], poly[i+1]; dist = math.hypot(pt2[0]-pt1[0], pt2[1]-pt1[1])
                if dist > 0: segmentos.append((pt1, pt2, dist))
            
            hinge, latch = None, None
            for sol in soleiras:
                mx, my = (sol['p1'][0]+sol['p2'][0])/2, (sol['p1'][1]+sol['p2'][1])/2
                if (min_x-0.5) <= mx <= (max_x+0.5) and (min_y-0.5) <= my <= (max_y+0.5):
                    for p in portas:
                        if min(math.hypot(p['p1'][0]-sol['p1'][0], p['p1'][1]-sol['p1'][1]), math.hypot(p['p1'][0]-sol['p2'][0], p['p1'][1]-sol['p2'][1]), math.hypot(p['p2'][0]-sol['p1'][0], p['p2'][1]-sol['p1'][1]), math.hypot(p['p2'][0]-sol['p2'][0], p['p2'][1]-sol['p2'][1])) < 0.2: hinge, latch = sol['p1'], sol['p2']; break
                if hinge: break
            
            dados = dict_dados[nome_ambiente]
            # Desenha Interruptor
            if hinge and latch:
                vx, vy = (latch[0]-hinge[0])/math.hypot(latch[0]-hinge[0], latch[1]-hinge[1]), (latch[1]-hinge[1])/math.hypot(latch[0]-hinge[0], latch[1]-hinge[1])
                sw_base_x, sw_base_y = latch[0] + vx*0.15, latch[1] + vy*0.15
                nx, ny = get_inside_normal(vx, vy, sw_base_x, sw_base_y, centro_x, centro_y, min_x, max_x, min_y, max_y)
                sw_x, sw_y = sw_base_x + nx*0.12, sw_base_y + ny*0.12
            else: sw_x, sw_y = centro_x, min_y + 0.12
            msp.add_circle(center=(sw_x, sw_y), radius=0.12, dxfattribs={'layer': 'PROJ_ELETRICA_INTERRUPTOR'})
            
            # Tomadas
            total_tugs = int(dados.get('TUGs (Qtd)', 0)); total_tues = int(dados.get('Qtd TUE', 0))
            is_umida = any(x in nome_ambiente.lower() for x in ["coz", "serv", "banh", "lav", "sanit", "área", "area"]) or any(w in nome_ambiente.lower().replace('-', ' ').split() for w in ["as", "wc", "bwc"])
            
            d_sw = get_dist_on_perimeter(sw_x, sw_y, segmentos)
            dist_atual = d_sw + 0.10
            tomadas_pos = 0
            while tomadas_pos < (total_tugs + total_tues):
                px, py, ux, uy = get_ponto_perimetro(dist_atual % sum(s[2] for s in segmentos), segmentos)
                fill = "half" if is_umida or tomadas_pos >= total_tugs else "empty"
                if tomadas_pos >= total_tugs: fill = "full"
                
                n1x, n1y = -uy, ux; pt_ponta = (px + n1x*0.25, py + n1y*0.25)
                msp.add_lwpolyline([(px+ux*0.15, py+uy*0.15), (px-ux*0.15, py-uy*0.15), pt_ponta, (px+ux*0.15, py+uy*0.15)], close=True, dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                if fill == "full": msp.add_solid([(px+ux*0.15, py+uy*0.15), (px-ux*0.15, py-uy*0.15), pt_ponta], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                elif fill == "half": msp.add_solid([(px+ux*0.15, py+uy*0.15), (px, py), pt_ponta], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                
                if tomadas_pos >= total_tugs: msp.add_text(f"{int(dados.get('Pot. Unit. TUE (VA)', 0))}W", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.1, 'insert': pt_ponta})
                dist_atual += (sum(s[2] for s in segmentos) / (total_tugs+total_tues))
                tomadas_pos += 1
                
        doc.saveas(tmp_in_path.replace(".dxf", "_out.dxf"))
        with open(tmp_in_path.replace(".dxf", "_out.dxf"), "rb") as f: return f.read()
    finally: os.remove(tmp_in_path)

# ... (Resto das funções login/sidebar/etc mantidas igual) ...
