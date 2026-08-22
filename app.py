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

    return {
        "Qtd Ilum.": qtd_ilum, "Pot. Unit. Ilum (VA)": round(carga_ilum/qtd_ilum) if qtd_ilum>0 else 0, "Carga Ilum. (VA)": carga_ilum, 
        "TUGs (Qtd)": qtd_tugs, "Pot. Unit. TUG (VA)": round(carga_tugs/qtd_tugs) if qtd_tugs>0 else 0, "Carga TUGs (VA)": carga_tugs,
        "Equipamento TUE": tue_nome, "Qtd TUE": qtd_tue, "Pot. Unit. TUE (VA)": round(carga_tue/qtd_tue) if qtd_tue>0 else 0, "Carga TUE (VA)": carga_tue
    }

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
        nome_ambiente = next((t['nome'] for t in textos if (min_x-0.5) <= t['x'] <= (max_x+0.5) and (min_y-0.5) <= t['y'] <= (max_y+0.5)), None)
        if not nome_ambiente: continue
        if nome_ambiente in ambientes_processados:
            ambientes_processados[nome_ambiente] += 1
            nome_ambiente = f"{nome_ambiente} {ambientes_processados[nome_ambiente]}"
        else: ambientes_processados[nome_ambiente] = 1
        cargas = dimensionar_cargas(nome_ambiente, area, (max_x-min_x)*2 + (max_y-min_y)*2)
        resultados.append({"Ambiente": nome_ambiente, "Área (m²)": area, "Perímetro (m)": (max_x-min_x)*2 + (max_y-min_y)*2, **cargas})
    return resultados

def get_inside_normal(vx, vy, start_x, start_y, cx, cy):
    n1x, n1y = -vy, vx
    n2x, n2y = vy, -vx
    d1 = math.hypot(cx - (start_x + n1x), cy - (start_y + n1y))
    d2 = math.hypot(cx - (start_x + n2x), cy - (start_y + n2y))
    return (n1x, n1y) if d1 < d2 else (n2x, n2y)

def point_seg_dist(px, py, pt1, pt2):
    l2 = (pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2
    if l2 == 0: return math.hypot(px - pt1[0], py - pt1[1])
    t = max(0, min(1, ((px - pt1[0])*(pt2[0] - pt1[0]) + (py - pt1[1])*(pt2[1] - pt1[1])) / l2))
    return math.hypot(px - (pt1[0] + t * (pt2[0] - pt1[0])), py - (pt1[1] + t * (pt2[1] - pt1[1])))

def dist_to_line(px, py, pt1, pt2):
    den = math.hypot(pt2[0]-pt1[0], pt2[1]-pt1[1])
    return abs((pt2[0]-pt1[0])*(pt1[1]-py) - (pt1[0]-px)*(pt2[1]-pt1[1])) / den if den != 0 else math.hypot(px-pt1[0], py-pt1[1])

def get_dist_on_perimeter(px, py, segs):
    acumulado = 0; min_d = float('inf'); best_d = 0
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
            margin = 0.3
            if dst > margin * 2:
                if ratio * dst < margin: ratio = margin / dst
                elif (1 - ratio) * dst < margin: ratio = (dst - margin) / dst
            else: ratio = 0.5 
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
            tipo = entity.dxftype()
            if hasattr(entity.dxf, 'layer'):
                layer = str(entity.dxf.layer).upper().strip()
                if tipo in ['LWPOLYLINE', 'POLYLINE'] and layer == 'IA_AMBIENTES':
                    polilinhas.append([(p[0], p[1]) for p in entity.get_points(format='xy')] if tipo == 'LWPOLYLINE' else [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices])
                elif tipo in ['TEXT', 'MTEXT'] and layer == 'IA_TEXTOS':
                    textos.append({'nome': (entity.text if tipo == 'MTEXT' else entity.dxf.text).strip(), 'x': entity.dxf.insert.x, 'y': entity.dxf.insert.y})
                elif layer == 'IA_PORTAS':
                    if tipo == 'LINE':
                        p1, p2 = (entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)
                        portas.append({'tipo': 'LINE', 'x': (p1[0]+p2[0])/2, 'y': (p1[1]+p2[1])/2, 'p1': p1, 'p2': p2})
                elif layer == 'IA_SOLEIRA':
                    if tipo == 'LINE':
                        soleiras.append({'p1': (entity.dxf.start.x, entity.dxf.start.y), 'p2': (entity.dxf.end.x, entity.dxf.end.y)})
        
        dict_dados = {row['Ambiente']: row for row in dados_editados}
        global_max_y = 0 
        
        for polilinha in polilinhas:
            xs = [p[0] for p in polilinha]; ys = [p[1] for p in polilinha]
            min_x, max_x = min(xs), max(xs); min_y, max_y = min(ys), max(ys)
            if max_y > global_max_y: global_max_y = max_y
            if (max_x - min_x) * (max_y - min_y) < 0.5: continue
            
            nome_ambiente = next((t['nome'] for t in textos if (min_x-0.5) <= t['x'] <= (max_x+0.5) and (min_y-0.5) <= t['y'] <= (max_y+0.5)), None)
            if not nome_ambiente or nome_ambiente not in dict_dados: continue
            
            centro_x, centro_y = (min_x + max_x) / 2, (min_y + max_y) / 2
            segmentos_crus = []
            poly = list(polilinha); 
            if poly[0] != poly[-1]: poly.append(poly[0])
            comp_total = 0
            for i in range(len(poly)-1):
                dist = math.hypot(poly[i+1][0]-poly[i][0], poly[i+1][1]-poly[i][1])
                if dist > 0: segmentos_crus.append((poly[i], poly[i+1], dist)); comp_total += dist
            
            logical_walls = []
            for pt1, pt2, dist in segmentos_crus:
                mx, my = (pt1[0]+pt2[0])/2, (pt1[1]+pt2[1])/2
                vx, vy = (pt2[0]-pt1[0])/dist, (pt2[1]-pt1[1])/dist
                merged = False
                for lw in logical_walls:
                    if abs(lw['vx']*vx + lw['vy']*vy) > 0.98 and dist_to_line(mx, my, lw['p1'], lw['p2']) < 0.2:
                        pts = [lw['p1'], lw['p2'], pt1, pt2]; max_d = 0; bp1, bp2 = lw['p1'], lw['p2']
                        for a in range(4):
                            for b in range(a+1, 4):
                                d = math.hypot(pts[a][0]-pts[b][0], pts[a][1]-pts[b][1])
                                if d > max_d: max_d = d; bp1, bp2 = pts[a], pts[b]
                        lw['p1'], lw['p2'], lw['length'] = bp1, bp2, max_d
                        lw['vx'], lw['vy'] = (bp2[0]-bp1[0])/max_d, (bp2[1]-bp1[1])/max_d
                        merged = True; break
                if not merged: logical_walls.append({'p1': pt1, 'p2': pt2, 'length': dist, 'vx': vx, 'vy': vy})

            unique_soleiras = []
            for sol in soleiras:
                mx, my = (sol['p1'][0]+sol['p2'][0])/2, (sol['p1'][1]+sol['p2'][1])/2
                if (min_x - 0.5) <= mx <= (max_x + 0.5) and (min_y - 0.5) <= my <= (max_y + 0.5):
                    if not any(math.hypot(mx - (u['p1'][0]+u['p2'][0])/2, my - (u['p1'][1]+u['p2'][1])/2) < 0.3 for u in unique_soleiras):
                        unique_soleiras.append(sol)

            dados = dict_dados[nome_ambiente]
            nome_lower = nome_ambiente.lower().strip()
            nome_words = nome_lower.replace('-', ' ').split()
            is_area_umida = any(x in nome_lower for x in ["coz", "serv", "banh", "lav", "sanit", "área", "area"]) or any(w in nome_words for w in ["as", "wc", "bwc"])
            
            hinge, latch = None, None
            for sol in unique_soleiras:
                for p in portas:
                    if p['tipo'] == 'LINE':
                        d11 = math.hypot(p['p1'][0] - sol['p1'][0], p['p1'][1] - sol['p1'][1])
                        d12 = math.hypot(p['p1'][0] - sol['p2'][0], p['p1'][1] - sol['p2'][1])
                        if min(d11, d12) < 0.2:
                            hinge, latch = (sol['p1'], sol['p2']) if d11 < d12 else (sol['p2'], sol['p1'])
                            break
                if hinge: break

            # Iluminação e Interruptor
            sw_base_x, sw_base_y = centro_x, min_y
            if dados.get('Qtd Ilum.', 0) > 0:
                msp.add_circle(center=(centro_x, centro_y), radius=0.25, dxfattribs={'layer': 'PROJ_ELETRICA_LUZ'})
                msp.add_text(f"{dados.get('Pot. Unit. Ilum (VA)', 0)}VA", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.15, 'insert': (centro_x + 0.3, centro_y - 0.07)})
                msp.add_text("a", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.15, 'color': 2, 'insert': (centro_x + 0.3, centro_y + 0.15)})
                
                sw_placed = False
                if hinge and latch and logical_walls:
                    best_lw = min(logical_walls, key=lambda lw: point_seg_dist(latch[0], latch[1], lw['p1'], lw['p2']))
                    if point_seg_dist(latch[0], latch[1], best_lw['p1'], best_lw['p2']) < 0.5:
                        vx, vy = best_lw['vx'], best_lw['vy']
                        if (latch[0]-hinge[0])*vx + (latch[1]-hinge[1])*vy < 0: vx, vy = -vx, -vy
                        sw_base_x, sw_base_y = latch[0] + vx * 0.15, latch[1] + vy * 0.15
                        nx, ny = get_inside_normal(vx, vy, sw_base_x, sw_base_y, centro_x, centro_y)
                        sw_x, sw_y = sw_base_x + nx * 0.12, sw_base_y + ny * 0.12
                        msp.add_circle(center=(sw_x, sw_y), radius=0.12, dxfattribs={'layer': 'PROJ_ELETRICA_INTERRUPTOR'})
                        msp.add_text("a", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.12, 'color': 5, 'insert': (sw_x + nx*0.2, sw_y + ny*0.2)})
                        sw_placed = True
                if not sw_placed:
                    sw_x, sw_y = centro_x, min_y + 0.12
                    msp.add_circle(center=(sw_x, sw_y), radius=0.12, dxfattribs={'layer': 'PROJ_ELETRICA_INTERRUPTOR'})
                    msp.add_text("a", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.12, 'color': 5, 'insert': (sw_x + 0.2, sw_y + 0.15)})

            # QDC Embutido
            qdc_formatado = str(local_qdc).replace(" (recomendado)", "")
            if nome_ambiente == qdc_formatado and not is_area_umida and logical_walls:
                qdc_w, qdc_d = 0.4, 0.15
                for lw in logical_walls: lw['soleiras'] = 0
                for sol in unique_soleiras:
                    mx_s, my_s = (sol['p1'][0]+sol['p2'][0])/2, (sol['p1'][1]+sol['p2'][1])/2
                    closest_lw = min(logical_walls, key=lambda lw: point_seg_dist(mx_s, my_s, lw['p1'], lw['p2']))
                    if point_seg_dist(mx_s, my_s, closest_lw['p1'], closest_lw['p2']) < 0.6: closest_lw['soleiras'] += 1
                best_wall = sorted(sorted(logical_walls, key=lambda w: w['length'], reverse=True)[:2], key=lambda w: w['soleiras'])[0]
                pt1, pt2 = best_wall['p1'], best_wall['p2']
                mx, my = (pt1[0]+pt2[0])/2, (pt1[1]+pt2[1])/2
                nx, ny = get_inside_normal(best_wall['vx'], best_wall['vy'], mx, my, centro_x, centro_y)
                out_nx, out_ny = -nx, -ny
                p1 = (mx - best_wall['vx']*qdc_w/2, my - best_wall['vy']*qdc_w/2)
                p2 = (mx + best_wall['vx']*qdc_w/2, my + best_wall['vy']*qdc_w/2)
                p3 = (p2[0] + out_nx*qdc_d, p2[1] + out_ny*qdc_d)
                p4 = (p1[0] + out_nx*qdc_d, p1[1] + out_ny*qdc_d)
                msp.add_lwpolyline([p1, p2, p3, p4, p1], dxfattribs={'layer': 'PROJ_ELETRICA_QDC'})
                msp.add_solid([p1, p2, p3], dxfattribs={'layer': 'PROJ_ELETRICA_QDC'})

            # Tomadas
            qtd_tugs = int(dados.get('TUGs (Qtd)', 0))
            qtd_tues = int(dados.get('Qtd TUE', 0))
            eq_nome = str(dados.get('Equipamento TUE', '')).lower().replace("-", " ")
            is_ac = ("ar" in eq_nome and "cond" in eq_nome) and qtd_tues > 0
            
            ac_placed = False; mx_ac, my_ac = 0, 0
            if is_ac and logical_walls:
                best_ac_wall = sorted(logical_walls, key=lambda w: w['length'])[0]
                mx_ac, my_ac = (best_ac_wall['p1'][0]+best_ac_wall['p2'][0])/2, (best_ac_wall['p1'][1]+best_ac_wall['p2'][1])/2
                nx_ac, ny_ac = get_inside_normal(best_ac_wall['vx'], best_ac_wall['vy'], mx_ac, my_ac, centro_x, centro_y)
                pt_ponta = (mx_ac + nx_ac * 0.25, my_ac + ny_ac * 0.25)
                msp.add_solid([(mx_ac + best_ac_wall['vx']*0.15, my_ac + best_ac_wall['vy']*0.15), (mx_ac - best_ac_wall['vx']*0.15, my_ac - best_ac_wall['vy']*0.15), pt_ponta], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                msp.add_lwpolyline([(mx_ac + best_ac_wall['vx']*0.15, my_ac + best_ac_wall['vy']*0.15), (mx_ac - best_ac_wall['vx']*0.15, my_ac - best_ac_wall['vy']*0.15), pt_ponta, (mx_ac + best_ac_wall['vx']*0.15, my_ac + best_ac_wall['vy']*0.15)], close=True, dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                pot_tue_val = int(dados.get('Pot. Unit. TUE (VA)', 0))
                if pot_tue_val > 0: msp.add_text(f"{pot_tue_val}W", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.1, 'color': 4, 'insert': (mx_ac + nx_ac*0.4, my_ac + ny_ac*0.4)})
                ac_placed = True; qtd_tues -= 1

            total_tomadas = qtd_tugs + qtd_tues
            if total_tomadas > 0 and comp_total > 0:
                passo = comp_total / total_tomadas
                d_sw = get_dist_on_perimeter(sw_base_x, sw_base_y, segmentos_crus)
                dir_step = 1
                if hinge and latch:
                    px_p, py_p, _, _ = get_ponto_perimetro((d_sw + 0.15) % comp_total, segmentos_crus)
                    if math.hypot(px_p - latch[0], py_p - latch[1]) < 0.2: dir_step = -1
                
                dist_atual = d_sw + (0.10 * dir_step)
                tomadas_pos = 0; tentativas = 0
                while tomadas_pos < total_tomadas and tentativas < total_tomadas * 5:
                    tentativas += 1
                    px, py, ux_w, uy_w = get_ponto_perimetro((dist_atual + comp_total) % comp_total, segmentos_crus)
                    
                    perto = False
                    if hinge and latch and (math.hypot(px - hinge[0], py - hinge[1]) < 0.8 or math.hypot(px - latch[0], py - latch[1]) < 0.5): perto = True
                    for sol in unique_soleiras:
                        if math.hypot(px - (sol['p1'][0]+sol['p2'][0])/2, py - (sol['p1'][1]+sol['p2'][1])/2) < 0.6: perto = True; break
                    if ac_placed and math.hypot(px - mx_ac, py - my_ac) < 0.6: perto = True
                    
                    if perto: dist_atual += (0.4 * dir_step); continue
                    
                    n1x, n1y = -uy_w, ux_w; n2x, n2y = uy_w, -ux_w
                    ponta1 = (px + n1x * 0.25, py + n1y * 0.25); ponta2 = (px + n2x * 0.25, py + n2y * 0.25)
                    ux_n, uy_n, pt_ponta = (n1x, n1y, ponta1) if math.hypot(centro_x - ponta1[0], centro_y - ponta1[1]) < math.hypot(centro_x - ponta2[0], centro_y - ponta2[1]) else (n2x, n2y, ponta2)
                    pt_base1 = (px + ux_w * 0.15, py + uy_w * 0.15)
                    pt_base2 = (px - ux_w * 0.15, py - uy_w * 0.15)
                    
                    is_tue = tomadas_pos >= qtd_tugs
                    fill = "full" if is_tue else ("half" if is_area_umida else "empty")
                    
                    msp.add_lwpolyline([pt_base1, pt_base2, pt_ponta, pt_base1], close=True, dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                    if fill == "full": msp.add_solid([pt_base1, pt_base2, pt_ponta], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                    elif fill == "half": msp.add_solid([pt_base1, (px, py), pt_ponta], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                    
                    if is_tue:
                        pot_val = int(dados.get('Pot. Unit. TUE (VA)', 0))
                        if pot_val > 0: msp.add_text(f"{pot_val}W", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.1, 'color': 4, 'insert': (px + ux_n * 0.4, py + uy_n * 0.4)})
                    
                    dist_atual += (passo * dir_step); tomadas_pos += 1

        msp.add_text(">>> MOTOR 34.4 (CORRECAO DEFINITIVA) <<<", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.8, 'color': 1, 'insert': (0, global_max_y + 2.0)})
        doc.saveas(tmp_in_path.replace(".dxf", "_out.dxf"))
        with open(tmp_in_path.replace(".dxf", "_out.dxf"), "rb") as f: return f.read()
    finally: os.remove(tmp_in_path)

# ==========================================
# 2. TELA DE LOGIN
# ==========================================
def tela_login():
    st.title("🔐 Acesso - AutoElétrica")
    if supabase is None: st.error("Erro: Supabase não conectado."); st.stop()
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        tab1, tab2 = st.tabs(["Login", "Cadastro"])
        with tab1:
            with st.form("f_login"):
                email = st.text_input("E-mail"); senha = st.text_input("Senha", type="password")
                if st.form_submit_button("Entrar"):
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email, "password": senha})
                        st.session_state.usuario_autenticado = True; st.session_state.user_email = email; st.session_state.user_id = res.user.id
                        st.rerun()
                    except: st.error("Credenciais inválidas.")
        with tab2:
            with st.form("f_cad"):
                ne = st.text_input("E-mail"); ns = st.text_input("Senha (mín. 6)", type="password")
                if st.form_submit_button("Criar"):
                    if len(ns) >= 6: supabase.auth.sign_up({"email": ne, "password": ns}); st.success("Conta criada!")

# ==========================================
# 3. SISTEMA PRINCIPAL
# ==========================================
def sistema_principal():
    with st.sidebar:
        st.write(f"👤 **{st.session_state.user_email}**")
        if st.button("Sair", use_container_width=True): supabase.auth.sign_out(); st.session_state.clear(); st.rerun()
        st.divider()
        obras = supabase.table("obras").select("*").eq("user_id", st.session_state.user_id).execute().data
        with st.expander("➕ Nova Obra"):
            no = st.text_input("Nome"); np = st.text_input("Pavimento")
            if st.button("Salvar") and no and np:
                supabase.table("obras").insert({"user_id": st.session_state.user_id, "nome_obra": no, "pavimento": np, "dados_json": []}).execute()
                st.rerun()
        if obras:
            opcoes = {f"{o['nome_obra']} - {o['pavimento']}": o for o in obras}
            escolha = st.selectbox("Selecione:", ["Nenhum"] + list(opcoes.keys()))
            if escolha != "Nenhum":
                sel = opcoes[escolha]
                if "obra_atual" not in st.session_state or st.session_state.obra_atual.get('id') != sel.get('id'):
                    st.session_state.obra_atual = sel; st.session_state.dados_extraidos = sel.get("dados_json", []); st.rerun()
                if st.button("🗑️ Excluir", type="primary", use_container_width=True):
                    supabase.table("obras").delete().eq("id", sel['id']).execute()
                    st.session_state.obra_atual = None; st.session_state.dados_extraidos = []; st.rerun()
            else: st.session_state.obra_atual = None; st.session_state.dados_extraidos = []

    st.title("⚡ Gerador Elétrico")
    if "obra_atual" not in st.session_state or st.session_state.obra_atual is None:
        st.info("👈 Crie ou selecione uma obra."); return

    if not st.session_state.dados_extraidos:
        arq = st.file_uploader("Planta .dxf", type=["dxf"])
        if arq and st.button("Processar DXF", type="primary"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
                tmp.write(arq.getvalue()); path = tmp.name
            try:
                res = processar_dxf(path)
                if res:
                    supabase.table("obras").update({"dados_json": res}).eq("id", st.session_state.obra_atual['id']).execute()
                    st.session_state.dados_extraidos = res; st.rerun()
            finally: os.remove(path)
    else:
        df = pd.DataFrame(st.session_state.dados_extraidos)
        ambs = [a for a in df['Ambiente'].tolist() if not any(x in a.lower() for x in ["coz", "serv", "banh", "lav", "wc", "bwc", "sanit"])]
        op_qdc = ["Selecione..."] + [("  " if "hall" in a.lower() else a) for a in ambs]
        
        c1, c2, c3 = st.columns(3)
        with c1: tensao = st.radio("Tensão:", [127, 220], horizontal=True)
        with c2: pe = st.number_input("Pé Direito:", value=2.8)
        with c3: qdc = st.selectbox("QDC:", options=list(dict.fromkeys(op_qdc)))
        
        df_ed = df.copy()
        with st.expander("🛠️ Ajustes"):
            for i, r in df_ed.iterrows():
                col1, col2, col3 = st.columns(3)
                with col1: st.write(r['Ambiente'])
                with col2: df_ed.at[i, 'Qtd Ilum.'] = st.number_input("Ilum", value=int(r['Qtd Ilum.']), key=f"il_{i}")
                with col3: df_ed.at[i, 'TUGs (Qtd)'] = st.number_input("TUGs", value=int(r['TUGs (Qtd)']), key=f"tg_{i}")
                st.divider()

        if st.button("💾 Salvar", type="primary"):
            supabase.table("obras").update({"dados_json": df_ed.to_dict('records'), "local_qdc": qdc, "tensao_projeto": int(tensao), "pe_direito": float(pe)}).eq("id", st.session_state.obra_atual['id']).execute()
            st.session_state.dados_extraidos = df_ed.to_dict('records'); st.success("Salvo!")

        arq_b = st.file_uploader("Reenvie o .dxf para desenho:", type=["dxf"], key="dxf_dwg")
        if arq_b and st.button("🎨 Gerar CAD Final", type="primary"):
            b = gerar_cad_unifilar(arq_b.getvalue(), df_ed.to_dict('records'), qdc)
            st.download_button("⬇️ Baixar DXF", data=b, file_name="Projeto_Eletrico.dxf", mime="application/dxf", use_container_width=True)

if __name__ == "__main__":
    if not st.session_state.usuario_autenticado: tela_login()
    else: sistema_principal()
