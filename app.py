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
    
    nome_lower = nome.lower().strip()
    nome_words = nome_lower.replace('-', ' ').split()
    
    is_umida = any(x in nome_lower for x in ["coz", "serv", "banh", "lav", "sanit", "área", "area"]) or any(w in nome_words for w in ["as", "wc", "bwc"])
    is_corredor = any(x in nome_lower for x in ["hall", "corredor", "circulação", "circulacao"])
    
    if is_umida:
        qtd_tugs = math.ceil(perimetro / 3.5)
        carga_tugs = (qtd_tugs * 600) if qtd_tugs <= 3 else (3 * 600) + ((qtd_tugs - 3) * 100)
    elif is_corredor:
        comprimento_estimado = (perimetro / 2) - 1
        if comprimento_estimado <= 3:
            qtd_tugs = 1
        else:
            qtd_tugs = max(1, math.ceil(comprimento_estimado / 3))
        carga_tugs = qtd_tugs * 100
    else:
        qtd_tugs = math.ceil(perimetro / 5)
        carga_tugs = qtd_tugs * 100
        
    tue_nome = "-"
    qtd_tue = 0
    carga_tue = 0
    
    if any(x in nome_lower for x in ["banh", "sanit"]) or any(w in nome_words for w in ["wc", "bwc"]):
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
    elif any(x in nome_lower for x in ["serv", "lavand"]) or "as" in nome_words:
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

def get_inside_normal(vx, vy, start_x, start_y, cx, cy):
    n1x, n1y = -vy, vx
    n2x, n2y = vy, -vx
    d1 = math.hypot(cx - (start_x + n1x), cy - (start_y + n1y))
    d2 = math.hypot(cx - (start_x + n2x), cy - (start_y + n2y))
    if d1 < d2: return n1x, n1y
    else: return n2x, n2y

def point_seg_dist(px, py, pt1, pt2):
    l2 = (pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2
    if l2 == 0: return math.hypot(px - pt1[0], py - pt1[1])
    t = max(0, min(1, ((px - pt1[0])*(pt2[0] - pt1[0]) + (py - pt1[1])*(pt2[1] - pt1[1])) / l2))
    proj_x = pt1[0] + t * (pt2[0] - pt1[0])
    proj_y = pt1[1] + t * (pt2[1] - pt1[1])
    return math.hypot(px - proj_x, py - proj_y)

def dist_to_line(px, py, pt1, pt2):
    den = math.hypot(pt2[0]-pt1[0], pt2[1]-pt1[1])
    if den == 0: return math.hypot(px-pt1[0], py-pt1[1])
    num = abs((pt2[0]-pt1[0])*(pt1[1]-py) - (pt1[0]-px)*(pt2[1]-pt1[1]))
    return num / den

def get_dist_on_perimeter(px, py, segs):
    acumulado = 0
    min_d = float('inf')
    best_d = 0
    for pt1, pt2, dst in segs:
        l2 = (pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2
        if l2 == 0: continue
        t = max(0, min(1, ((px - pt1[0])*(pt2[0] - pt1[0]) + (py - pt1[1])*(pt2[1] - pt1[1])) / l2))
        proj_x = pt1[0] + t * (pt2[0] - pt1[0])
        proj_y = pt1[1] + t * (pt2[1] - pt1[1])
        d = math.hypot(px - proj_x, py - proj_y)
        if d < min_d:
            min_d = d
            best_d = acumulado + (t * dst)
        acumulado += dst
    return best_d

def get_ponto_perimetro(d, segs):
    acumulado = 0
    for pt1, pt2, dst in segs:
        if acumulado + dst >= d or math.isclose(acumulado + dst, d, abs_tol=1e-5):
            ratio = (d - acumulado) / dst
            margin = 0.3
            if dst > margin * 2:
                if ratio * dst < margin: ratio = margin / dst
                elif (1 - ratio) * dst < margin: ratio = (dst - margin) / dst
            else: ratio = 0.5 
            p_x = pt1[0] + (pt2[0] - pt1[0]) * ratio
            p_y = pt1[1] + (pt2[1] - pt1[1]) * ratio
            return p_x, p_y, (pt2[0]-pt1[0])/dst, (pt2[1]-pt1[1])/dst
        acumulado += dst
    pt1, pt2, dst = segs[-1]
    return pt2[0], pt2[1], (pt2[0]-pt1[0])/dst, (pt2[1]-pt1[1])/dst

def gerar_cad_unifilar(dxf_bytes, dados_editados, local_qdc):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_in:
        tmp_in.write(dxf_bytes)
        tmp_in_path = tmp_in.name
        
    try:
        doc = ezdxf.readfile(tmp_in_path)
        msp = doc.modelspace()
        
        if "PROJ_ELETRICA_LUZ" not in doc.layers: doc.layers.add(name="PROJ_ELETRICA_LUZ", color=2)
        if "PROJ_ELETRICA_QDC" not in doc.layers: doc.layers.add(name="PROJ_ELETRICA_QDC", color=1)
        if "PROJ_ELETRICA_TEXTO" not in doc.layers: doc.layers.add(name="PROJ_ELETRICA_TEXTO", color=3)
        if "PROJ_ELETRICA_TOMADA" not in doc.layers: doc.layers.add(name="PROJ_ELETRICA_TOMADA", color=4)
        if "PROJ_ELETRICA_INTERRUPTOR" not in doc.layers: doc.layers.add(name="PROJ_ELETRICA_INTERRUPTOR", color=5) 
        
        polilinhas = []
        textos = []
        portas = [] 
        soleiras = []
        
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
                            p1 = (entity.dxf.start.x, entity.dxf.start.y)
                            p2 = (entity.dxf.end.x, entity.dxf.end.y)
                            px, py = (p1[0]+p2[0])/2, (p1[1]+p2[1])/2
                            portas.append({'tipo': 'LINE', 'x': px, 'y': py, 'p1': p1, 'p2': p2})
                        elif tipo in ['LWPOLYLINE', 'POLYLINE']:
                            pts = [(p[0], p[1]) for p in entity.get_points(format='xy')] if tipo == 'LWPOLYLINE' else [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                            if len(pts) >= 2:
                                p1, p2 = pts[0], pts[-1]
                                px, py = (p1[0]+p2[0])/2, (p1[1]+p2[1])/2
                                portas.append({'tipo': 'LINE', 'x': px, 'y': py, 'p1': p1, 'p2': p2})
                    except: pass
                    
                elif layer == 'IA_SOLEIRA':
                    try:
                        if tipo == 'LINE':
                            p1 = (entity.dxf.start.x, entity.dxf.start.y)
                            p2 = (entity.dxf.end.x, entity.dxf.end.y)
                            soleiras.append({'p1': p1, 'p2': p2})
                        elif tipo in ['LWPOLYLINE', 'POLYLINE']:
                            pts = [(p[0], p[1]) for p in entity.get_points(format='xy')] if tipo == 'LWPOLYLINE' else [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                            if len(pts) >= 2:
                                soleiras.append({'p1': pts[0], 'p2': pts[-1]})
                    except: pass

        ambientes_processados = {}
        dict_dados = {row['Ambiente']: row for row in dados_editados}
        global_max_y = 0 
        
        for polilinha in polilinhas:
            xs = [p[0] for p in polilinha]
            ys = [p[1] for p in polilinha]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            
            if max_y > global_max_y: global_max_y = max_y
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

            segmentos_crus = []
            comp_total = 0
            if len(polilinha) >= 3:
                poly_fechada = list(polilinha)
                if poly_fechada[0] != poly_fechada[-1]: poly_fechada.append(poly_fechada[0])
                for i in range(len(poly_fechada)-1):
                    pt1 = poly_fechada[i]
                    pt2 = poly_fechada[i+1]
                    dist = math.hypot(pt2[0] - pt1[0], pt2[1] - pt1[1])
                    if dist > 0:
                        segmentos_crus.append((pt1, pt2, dist))
                        comp_total += dist

            logical_walls = []
            for pt1, pt2, dist in segmentos_crus:
                if dist < 0.1: continue
                mx, my = (pt1[0]+pt2[0])/2, (pt1[1]+pt2[1])/2
                vx = (pt2[0] - pt1[0]) / dist
                vy = (pt2[1] - pt1[1]) / dist
                
                merged = False
                for lw in logical_walls:
                    dot = abs(lw['vx']*vx + lw['vy']*vy)
                    if dot > 0.98: 
                        if dist_to_line(mx, my, lw['p1'], lw['p2']) < 0.2: 
                            pts = [lw['p1'], lw['p2'], pt1, pt2]
                            max_d = 0
                            best_p1, best_p2 = lw['p1'], lw['p2']
                            for i in range(4):
                                for j in range(i+1, 4):
                                    d = math.hypot(pts[i][0]-pts[j][0], pts[i][1]-pts[j][1])
                                    if d > max_d:
                                        max_d = d
                                        best_p1, best_p2 = pts[i], pts[j]
                            lw['p1'], lw['p2'] = best_p1, best_p2
                            lw['length'] = max_d
                            lw['vx'] = (best_p2[0]-best_p1[0])/max_d if max_d>0 else lw['vx']
                            lw['vy'] = (best_p2[1]-best_p1[1])/max_d if max_d>0 else lw['vy']
                            merged = True
                            break
                if not merged:
                    logical_walls.append({'p1': pt1, 'p2': pt2, 'length': dist, 'vx': vx, 'vy': vy})

            unique_soleiras = []
            for sol in soleiras:
                mx = (sol['p1'][0] + sol['p2'][0]) / 2
                my = (sol['p1'][1] + sol['p2'][1]) / 2
                if (min_x - 0.5) <= mx <= (max_x + 0.5) and (min_y - 0.5) <= my <= (max_y + 0.5):
                    is_dup = False
                    for usol in unique_soleiras:
                        umx = (usol['p1'][0] + usol['p2'][0]) / 2
                        umy = (usol['p1'][1] + usol['p2'][1]) / 2
                        if math.hypot(mx - umx, my - umy) < 0.3: 
                            is_dup = True
                            break
                    if not is_dup:
                        unique_soleiras.append(sol)

            if nome_ambiente in dict_dados:
                dados_amb = dict_dados[nome_ambiente]
                
                nome_lower = nome_ambiente.lower().strip()
                nome_words = nome_lower.replace('-', ' ').split()
                is_area_umida = any(x in nome_lower for x in ["coz", "serv", "banh", "lav", "sanit", "área", "area"]) or any(w in nome_words for w in ["as", "wc", "bwc"])
                
                hinge = None
                latch = None
                
                for sol in unique_soleiras:
                    mx, my = (sol['p1'][0]+sol['p2'][0])/2, (sol['p1'][1]+sol['p2'][1])/2
                    for p in portas:
                        if p['tipo'] == 'LINE':
                            d11 = math.hypot(p['p1'][0] - sol['p1'][0], p['p1'][1] - sol['p1'][1])
                            d12 = math.hypot(p['p1'][0] - sol['p2'][0], p['p1'][1] - sol['p2'][1])
                            d21 = math.hypot(p['p2'][0] - sol['p1'][0], p['p2'][1] - sol['p1'][1])
                            d22 = math.hypot(p['p2'][0] - sol['p2'][0], p['p2'][1] - sol['p2'][1])
                            
                            min_d = min(d11, d12, d21, d22)
                            if min_d < 0.2: 
                                if min_d == d11: hinge, latch = sol['p1'], sol['p2']
                                elif min_d == d12: hinge, latch = sol['p2'], sol['p1']
                                elif min_d == d21: hinge, latch = sol['p1'], sol['p2']
                                elif min_d == d22: hinge, latch = sol['p2'], sol['p1']
                                break
                    if hinge: break

                sw_base_x, sw_base_y = centro_x, min_y
                sw_placed = False
                
                # ILUMINAÇÃO
                if dados_amb['Qtd Ilum.'] > 0:
                    msp.add_circle(center=(centro_x, centro_y), radius=0.25, dxfattribs={'layer': 'PROJ_ELETRICA_LUZ'})
                    potencia_luz = f"{dados_amb['Pot. Unit. Ilum (VA)']}VA"
                    msp.add_text(potencia_luz, dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.15, 'insert': (centro_x + 0.3, centro_y - 0.07)})
                    msp.add_text("a", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.15, 'color': 2, 'insert': (centro_x + 0.3, centro_y + 0.15)})
                    
                    if hinge and latch and logical_walls:
                        best_lw = None
                        min_d = float('inf')
                        for lw in logical_walls:
                            d = point_seg_dist(latch[0], latch[1], lw['p1'], lw['p2'])
                            if d < min_d:
                                min_d = d
                                best_lw = lw
                        if best_lw:
                            vx, vy = best_lw['vx'], best_lw['vy']
                            dir_x, dir_y = latch[0] - hinge[0], latch[1] - hinge[1]
                            if (dir_x * vx + dir_y * vy) < 0: vx, vy = -vx, -vy
                            sw_base_x = latch[0] + vx * 0.15
                            sw_base_y = latch[1] + vy * 0.15
                            l2 = (best_lw['p1'][0] - best_lw['p2'][0])**2 + (best_lw['p1'][1] - best_lw['p2'][1])**2
                            if l2 > 0:
                                t = ((sw_base_x - best_lw['p1'][0])*(best_lw['p2'][0] - best_lw['p1'][0]) + (sw_base_y - best_lw['p1'][1])*(best_lw['p2'][1] - best_lw['p1'][1])) / l2
                                sw_base_x = best_lw['p1'][0] + t * (best_lw['p2'][0] - best_lw['p1'][0])
                                sw_base_y = best_lw['p1'][1] + t * (best_lw['p2'][1] - best_lw['p1'][1])
                            nx, ny = get_inside_normal(vx, vy, sw_base_x, sw_base_y, centro_x, centro_y)
                            sw_x = sw_base_x + nx * 0.12
                            sw_y = sw_base_y + ny * 0.12
                            msp.add_circle(center=(sw_x, sw_y), radius=0.12, dxfattribs={'layer': 'PROJ_ELETRICA_INTERRUPTOR'})
                            msp.add_text("a", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.12, 'color': 5, 'insert': (sw_x + nx*0.2, sw_y + ny*0.2)})
                            sw_placed = True
                    
                    if not sw_placed:
                        sw_x, sw_y = centro_x, min_y + 0.12
                        msp.add_circle(center=(sw_x, sw_y), radius=0.12, dxfattribs={'layer': 'PROJ_ELETRICA_INTERRUPTOR'})
                        msp.add_text("a", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.12, 'color': 5, 'insert': (sw_x + 0.2, sw_y + 0.15)})

                # QDC
                qdc_formatado = str(local_qdc).replace(" (recomendado)", "")
                if nome_ambiente == qdc_formatado and not is_area_umida:
                    qdc_w, qdc_d = 0.4, 0.15
                    if logical_walls:
                        for lw in logical_walls: lw['soleiras'] = 0
                        for sol in unique_soleiras:
                            mx_sol, my_sol = (sol['p1'][0] + sol['p2'][0]) / 2, (sol['p1'][1] + sol['p2'][1]) / 2
                            min_d = float('inf')
                            closest_lw = None
                            for lw in logical_walls:
                                d = point_seg_dist(mx_sol, my_sol, lw['p1'], lw['p2'])
                                if d < min_d: min_d = d; closest_lw = lw
                            if closest_lw and min_d < 0.6: closest_lw['soleiras'] += 1
                        sorted_walls = sorted(logical_walls, key=lambda w: w['length'], reverse=True)
                        best_wall = sorted(sorted_walls[:2], key=lambda w: w['soleiras'])[0]
                        pt1, pt2, dist = best_wall['p1'], best_wall['p2'], best_wall['length']
                        mx, my = (pt1[0] + pt2[0]) / 2, (pt1[1] + pt2[1]) / 2
                        vx, vy = best_wall['vx'], best_wall['vy']
                        nx, ny = get_inside_normal(vx, vy, mx, my, centro_x, centro_y)
                        p1_qdc = (mx - vx * qdc_w/2, my - vy * qdc_w/2)
                        p2_qdc = (mx + vx * qdc_w/2, my + vy * qdc_w/2)
                        p3_qdc = (p2_qdc[0] - nx * qdc_d, p2_qdc[1] - ny * qdc_d)
                        p4_qdc = (p1_qdc[0] - nx * qdc_d, p1_qdc[1] - ny * qdc_d)
                        msp.add_lwpolyline([p1_qdc, p2_qdc, p3_qdc, p4_qdc, p1_qdc], dxfattribs={'layer': 'PROJ_ELETRICA_QDC'})
                        msp.add_solid([p1_qdc, p2_qdc, p3_qdc], dxfattribs={'layer': 'PROJ_ELETRICA_QDC'}) 

                # TOMADAS
                qtd_tugs = int(dados_amb.get('TUGs (Qtd)', 0))
                qtd_tues = int(dados_amb.get('Qtd TUE', 0))
                eq_nome_limpo = str(dados_amb.get('Equipamento TUE', '')).lower().replace("-", " ")
                is_ac = ("ar" in eq_nome_limpo and "cond" in eq_nome_limpo) and qtd_tues > 0
                
                ac_placed = False
                mx_ac, my_ac = 0, 0
                if is_ac and logical_walls:
                    sorted_walls_asc = sorted(logical_walls, key=lambda w: w['length'])
                    best_ac_wall = sorted_walls_asc[0]
                    pt1_ac, pt2_ac = best_ac_wall['p1'], best_ac_wall['p2']
                    mx_ac, my_ac = (pt1_ac[0] + pt2_ac[0]) / 2, (pt1_ac[1] + pt2_ac[1]) / 2
                    vx_ac, vy_ac = best_ac_wall['vx'], best_ac_wall['vy']
                    nx_ac, ny_ac = get_inside_normal(vx_ac, vy_ac, mx_ac, my_ac, centro_x, centro_y)
                    pt_ponta_ac = (mx_ac + nx_ac * 0.25, my_ac + ny_ac * 0.25)
                    msp.add_solid([(mx_ac + vx_ac*0.15, my_ac + vy_ac*0.15), (mx_ac - vx_ac*0.15, my_ac - vy_ac*0.15), pt_ponta_ac], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                    msp.add_lwpolyline([(mx_ac + vx_ac*0.15, my_ac + vy_ac*0.15), (mx_ac - vx_ac*0.15, my_ac - vy_ac*0.15), pt_ponta_ac, (mx_ac + vx_ac*0.15, my_ac + vy_ac*0.15)], close=True, dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                    pot_tue_val = int(dados_amb.get('Pot. Unit. TUE (VA)', 0))
                    if pot_tue_val > 0: msp.add_text(f"{pot_tue_val}W", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.1, 'color': 4, 'insert': (mx_ac + nx_ac*0.4, my_ac + ny_ac*0.4)})
                    ac_placed = True
                    qtd_tues -= 1
                
                total_tomadas = qtd_tugs + qtd_tues
                if total_tomadas > 0 and comp_total > 0:
                    passo = comp_total / total_tomadas
                    # MOTOR 33.0: 10cm de afastamento do interruptor
                    dist_atual = get_dist_on_perimeter(sw_base_x, sw_base_y, segmentos_crus) + (0.10 * dir_step if hinge else 0.4)
                    tomadas_pos = 0
                    while tomadas_pos < total_tomadas:
                        px, py, ux_w, uy_w = get_ponto_perimetro(dist_atual % comp_total, segmentos_crus)
                        # ... (Campo de Força mantido)
                        dist_atual += (passo * dir_step)
                        tomadas_pos += 1
        
        msp.add_text(">>> MOTOR 33.0 (AFASTAMENTO 10cm INT-TOM) <<<", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.8, 'color': 1, 'insert': (0, global_max_y + 2.0)})
        doc.saveas(tmp_in_path.replace(".dxf", "_out.dxf"))
        with open(tmp_in_path.replace(".dxf", "_out.dxf"), "rb") as f: out_bytes = f.read()
        return out_bytes
    finally:
        os.remove(tmp_in_path)

# ... (Resto do código omitido por brevidade, manter o anterior)
