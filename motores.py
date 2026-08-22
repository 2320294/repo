import ezdxf
import math
import tempfile
import os

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
                if pontos: polilinhas.append(pontos)
            except Exception:
                continue
        elif tipo in ['TEXT', 'MTEXT'] and layer == 'IA_TEXTOS':
            try:
                texto_str = entity.text if tipo == 'MTEXT' else entity.dxf.text
                texto_str = texto_str.strip()
                if texto_str: 
                    textos.append({'nome': texto_str, 'x': entity.dxf.insert.x, 'y': entity.dxf.insert.y})
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
        
        if area < 0.5: continue
        
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
                
        cargas = dimensionar_cargas(nome_ambiente, area, perimetro)
        
        resultados.append({
            "Ambiente": nome_ambiente,
            "Centro_X": (min_x+max_x)/2,
            "Centro_Y": (min_y+max_y)/2,
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
    return (n1x, n1y) if d1 < d2 else (n2x, n2y)

def point_seg_dist(px, py, pt1, pt2):
    l2 = (pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2
    if l2 == 0: return math.hypot(px - pt1[0], py - pt1[1])
    t = max(0, min(1, ((px - pt1[0])*(pt2[0] - pt1[0]) + (py - pt1[1])*(pt2[1] - pt1[1])) / l2))
    return math.hypot(px - (pt1[0] + t * (pt2[0] - pt1[0])), py - (pt1[1] + t * (pt2[1] - pt1[1])))

def dist_to_line(px, py, pt1, pt2):
    den = math.hypot(pt2[0]-pt1[0], pt2[1]-pt1[1])
    if den == 0: return math.hypot(px-pt1[0], py-pt1[1])
    return abs((pt2[0]-pt1[0])*(pt1[1]-py) - (pt1[0]-px)*(pt2[1]-pt1[1])) / den

def get_dist_on_perimeter(px, py, segs):
    acumulado, min_d, best_d = 0, float('inf'), 0
    for pt1, pt2, dst in segs:
        l2 = (pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2
        if l2 == 0: continue
        t = max(0, min(1, ((px - pt1[0])*(pt2[0] - pt1[0]) + (py - pt1[1])*(pt2[1] - pt1[1])) / l2))
        d = math.hypot(px - (pt1[0] + t * (pt2[0] - pt1[0])), py - (pt1[1] + t * (pt2[1] - pt1[1])))
        if d < min_d: min_d, best_d = d, acumulado + (t * dst)
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

def tracar_eletroduto(msp, pt_origem, pt_destino, layer="PROJ_ELETRICA_ELETRODUTO"):
    if layer not in msp.doc.layers:
        msp.doc.layers.add(name=layer, color=3)
    msp.add_lwpolyline([pt_origem, pt_destino], dxfattribs={'layer': layer})

def gerar_cad_unifilar(dxf_bytes, dados_editados, local_qdc):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_in:
        tmp_in.write(dxf_bytes)
        tmp_in_path = tmp_in.name
        
    try:
        doc = ezdxf.readfile(tmp_in_path)
        msp = doc.modelspace()
        
        camadas = {
            "PROJ_ELETRICA_LUZ": 2,          # Amarelo
            "PROJ_ELETRICA_QDC": 1,          # Vermelho
            "PROJ_ELETRICA_TEXTO": 7,        # Branco / Cinza claro
            "PROJ_ELETRICA_TOMADA": 6,       # Magenta
            "PROJ_ELETRICA_INTERRUPTOR": 4,  # Ciano
            "PROJ_ELETRICA_ELETRODUTO": 3    # Verde
        }
        for nome_l, cor_l in camadas.items():
            if nome_l not in doc.layers:
                doc.layers.add(name=nome_l, color=cor_l)
            else:
                doc.layers.get(nome_l).color = cor_l
        
        polilinhas, textos, portas, soleiras = [], [], [], []
        
        for entity in msp:
            tipo = entity.dxftype()
            if hasattr(entity.dxf, 'layer'):
                layer = str(entity.dxf.layer).upper().strip()
                if tipo in ['LWPOLYLINE', 'POLYLINE'] and layer == 'IA_AMBIENTES':
                    try:
                        pts = [(p[0], p[1]) for p in entity.get_points(format='xy')] if tipo == 'LWPOLYLINE' else [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                        if pts: polilinhas.append(pts)
                    except: pass
                elif tipo in ['TEXT', 'MTEXT'] and layer == 'IA_TEXTOS':
                    try:
                        txt_str = (entity.text if tipo == 'MTEXT' else entity.dxf.text).strip()
                        if txt_str: textos.append({'nome': txt_str, 'x': entity.dxf.insert.x, 'y': entity.dxf.insert.y})
                    except: pass
                elif layer == 'IA_PORTAS':
                    try:
                        if tipo == 'LINE':
                            p1, p2 = (entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)
                            portas.append({'tipo': 'LINE', 'x': (p1[0]+p2[0])/2, 'y': (p1[1]+p2[1])/2, 'p1': p1, 'p2': p2})
                        elif tipo in ['LWPOLYLINE', 'POLYLINE']:
                            pts = [(p[0], p[1]) for p in entity.get_points(format='xy')] if tipo == 'LWPOLYLINE' else [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                            if len(pts) >= 2: portas.append({'tipo': 'LINE', 'x': (pts[0][0]+pts[-1][0])/2, 'y': (pts[0][1]+pts[-1][1])/2, 'p1': pts[0], 'p2': pts[-1]})
                    except: pass
                elif layer == 'IA_SOLEIRA':
                    try:
                        if tipo == 'LINE':
                            soleiras.append({'p1': (entity.dxf.start.x, entity.dxf.start.y), 'p2': (entity.dxf.end.x, entity.dxf.end.y)})
                        elif tipo in ['LWPOLYLINE', 'POLYLINE']:
                            pts = [(p[0], p[1]) for p in entity.get_points(format='xy')] if tipo == 'LWPOLYLINE' else [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                            if len(pts) >= 2: soleiras.append({'p1': pts[0], 'p2': pts[-1]})
                    except: pass

        ambientes_processados = {}
        dict_dados = {row['Ambiente']: row for row in dados_editados}
        geometrias_ambientes = {}
        
        for polilinha in polilinhas:
            xs = [p[0] for p in polilinha]
            ys = [p[1] for p in polilinha]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            if (max_x - min_x) * (max_y - min_y) < 0.5: continue
            
            nome_ambiente = next((t['nome'] for t in textos if (min_x - 0.5) <= t['x'] <= (max_x + 0.5) and (min_y - 0.5) <= t['y'] <= (max_y + 0.5)), None)
            if not nome_ambiente: continue
            if nome_ambiente in ambientes_processados:
                ambientes_processados[nome_ambiente] += 1
                nome_ambiente = f"{nome_ambiente} {ambientes_processados[nome_ambiente]}"
            else:
                ambientes_processados[nome_ambiente] = 1
                
            centro_x, centro_y = (min_x + max_x) / 2, (min_y + max_y) / 2
            
            segmentos_crus, comp_total = [], 0
            if len(polilinha) >= 3:
                poly_fechada = list(polilinha)
                if poly_fechada[0] != poly_fechada[-1]: poly_fechada.append(poly_fechada[0])
                for i in range(len(poly_fechada)-1):
                    dist = math.hypot(poly_fechada[i+1][0] - poly_fechada[i][0], poly_fechada[i+1][1] - poly_fechada[i][1])
                    if dist > 0: segmentos_crus.append((poly_fechada[i], poly_fechada[i+1], dist)); comp_total += dist

            logical_walls = []
            for pt1, pt2, dist in segmentos_crus:
                if dist < 0.1: continue
                mx, my = (pt1[0]+pt2[0])/2, (pt1[1]+pt2[1])/2
                vx, vy = (pt2[0] - pt1[0]) / dist, (pt2[1] - pt1[1]) / dist
                merged = False
                for lw in logical_walls:
                    if abs(lw['vx']*vx + lw['vy']*vy) > 0.98 and dist_to_line(mx, my, lw['p1'], lw['p2']) < 0.2:
                        pts = [lw['p1'], lw['p2'], pt1, pt2]
                        max_d, best_p1, best_p2 = 0, lw['p1'], lw['p2']
                        for i in range(4):
                            for j in range(i+1, 4):
                                d = math.hypot(pts[i][0]-pts[j][0], pts[i][1]-pts[j][1])
                                if d > max_d: max_d, best_p1, best_p2 = d, pts[i], pts[j]
                        lw['p1'], lw['p2'], lw['length'] = best_p1, best_p2, max_d
                        lw['vx'] = (best_p2[0]-best_p1[0])/max_d if max_d>0 else lw['vx']
                        lw['vy'] = (best_p2[1]-best_p1[1])/max_d if max_d>0 else lw['vy']
                        merged = True
                        break
                if not merged: logical_walls.append({'p1': pt1, 'p2': pt2, 'length': dist, 'vx': vx, 'vy': vy})

            geometrias_ambientes[nome_ambiente] = {
                'min_x': min_x, 'max_x': max_x, 'min_y': min_y, 'max_y': max_y,
                'centro_x': centro_x, 'centro_y': centro_y,
                'segmentos_crus': segmentos_crus, 'comp_total': comp_total,
                'logical_walls': logical_walls
            }

        for nome_ambiente, geom in geometrias_ambientes.items():
            if nome_ambiente not in dict_dados: continue
            dados_amb = dict_dados[nome_ambiente]
            centro_x, centro_y = geom['centro_x'], geom['centro_y']
            min_x, max_x, min_y, max_y = geom['min_x'], geom['max_x'], geom['min_y'], geom['max_y']
            segmentos_crus, comp_total = geom['segmentos_crus'], geom['comp_total']
            logical_walls = geom['logical_walls']
            
            nome_lower = nome_ambiente.lower().strip()
            is_area_umida = any(x in nome_lower for x in ["coz", "serv", "banh", "lav", "sanit", "área", "area"])
            
            unique_soleiras = []
            for sol in soleiras:
                mx, my = (sol['p1'][0] + sol['p2'][0]) / 2, (sol['p1'][1] + sol['p2'][1]) / 2
                if (min_x - 0.5) <= mx <= (max_x + 0.5) and (min_y - 0.5) <= my <= (max_y + 0.5):
                    if not any(math.hypot(mx - (usol['p1'][0]+usol['p2'][0])/2, my - (usol['p1'][1]+usol['p2'][1])/2) < 0.3 for usol in unique_soleiras):
                        unique_soleiras.append(sol)

            hinge, latch = None, None
            for sol in unique_soleiras:
                for p in portas:
                    if p['tipo'] == 'LINE':
                        d11 = math.hypot(p['p1'][0] - sol['p1'][0], p['p1'][1] - sol['p1'][1])
                        d12 = math.hypot(p['p1'][0] - sol['p2'][0], p['p1'][1] - sol['p2'][1])
                        d21 = math.hypot(p['p2'][0] - sol['p1'][0], p['p2'][1] - sol['p1'][1])
                        d22 = math.hypot(p['p2'][0] - sol['p2'][0], p['p2'][1] - sol['p2'][1])
                        min_d = min(d11, d12, d21, d22)
                        if min_d < 0.2:
                            hinge, latch = (sol['p1'], sol['p2']) if min_d in [d11, d21] else (sol['p2'], sol['p1'])
                            break
                    if hinge: break

            sw_base_x, sw_base_y, sw_placed = centro_x, min_y, False
            if dados_amb['Qtd Ilum.'] > 0:
                msp.add_circle(center=(centro_x, centro_y), radius=0.25, dxfattribs={'layer': 'PROJ_ELETRICA_LUZ'})
                msp.add_text(f"{dados_amb['Pot. Unit. Ilum (VA)']}VA", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.15, 'insert': (centro_x + 0.3, centro_y - 0.07)})
                msp.add_text("a", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.15, 'color': 7, 'insert': (centro_x + 0.3, centro_y + 0.15)})
                
                if hinge and latch and logical_walls:
                    best_lw = min(logical_walls, key=lambda lw: point_seg_dist(latch[0], latch[1], lw['p1'], lw['p2']))
                    if best_lw and point_seg_dist(latch[0], latch[1], best_lw['p1'], best_lw['p2']) < 0.5:
                        vx, vy = best_lw['vx'], best_lw['vy']
                        if ((latch[0] - hinge[0]) * vx + (latch[1] - hinge[1]) * vy) < 0: vx, vy = -vx, -vy
                        sw_base_x, sw_base_y = latch[0] + vx * 0.15, latch[1] + vy * 0.15
                        nx, ny = get_inside_normal(vx, vy, sw_base_x, sw_base_y, centro_x, centro_y)
                        sw_x, sw_y = sw_base_x + nx * 0.12, sw_base_y + ny * 0.12
                        msp.add_circle(center=(sw_x, sw_y), radius=0.12, dxfattribs={'layer': 'PROJ_ELETRICA_INTERRUPTOR'})
                        msp.add_text("a", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.12, 'color': 7, 'insert': (sw_x + nx * 0.20, sw_y + ny * 0.20)})
                        tracar_eletroduto(msp, (sw_x, sw_y), (centro_x, centro_y), layer="PROJ_ELETRICA_ELETRODUTO")
                        sw_placed = True
                if not sw_placed:
                    sw_x, sw_y = centro_x, min_y + 0.12
                    msp.add_circle(center=(sw_x, sw_y), radius=0.12, dxfattribs={'layer': 'PROJ_ELETRICA_INTERRUPTOR'})
                    msp.add_text("a", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.12, 'color': 7, 'insert': (sw_x + 0.2, sw_y + 0.15)})
                    tracar_eletroduto(msp, (sw_x, sw_y), (centro_x, centro_y), layer="PROJ_ELETRICA_ELETRODUTO")

            qdc_formatado = str(local_qdc).replace(" (recomendado)", "")
            if nome_ambiente == qdc_formatado and not is_area_umida:
                qdc_w, qdc_d = 0.4, 0.15
                if logical_walls:
                    for lw in logical_walls: lw['score_porta'] = 0
                    for sol in unique_soleiras:
                        mx_sol, my_sol = (sol['p1'][0] + sol['p2'][0]) / 2, (sol['p1'][1] + sol['p2'][1]) / 2
                        closest_lw = min(logical_walls, key=lambda lw: point_seg_dist(mx_sol, my_sol, lw['p1'], lw['p2']))
                        if closest_lw and point_seg_dist(mx_sol, my_sol, closest_lw['p1'], closest_lw['p2']) < 0.6:
                            closest_lw['score_porta'] += 1
                    best_wall = min(logical_walls, key=lambda w: (w['score_porta'], -w['length']))
                    pt1, pt2 = best_wall['p1'], best_wall['p2']
                    mx, my = (pt1[0] + pt2[0]) / 2, (pt1[1] + pt2[1]) / 2
                    vx, vy = best_wall['vx'], best_wall['vy']
                    nx, ny = get_inside_normal(vx, vy, mx, my, centro_x, centro_y)
                    out_nx, out_ny = -nx, -ny
                    p1_qdc = (mx - vx * qdc_w/2, my - vy * qdc_w/2)
                    p2_qdc = (mx + vx * qdc_w/2, my + vy * qdc_w/2)
                    p3_qdc = (p2_qdc[0] + out_nx * qdc_d, p2_qdc[1] + out_ny * qdc_d)
                    p4_qdc = (p1_qdc[0] + out_nx * qdc_d, p1_qdc[1] + out_ny * qdc_d)
                    pts_qdc = [p1_qdc, p2_qdc, p3_qdc, p4_qdc]
                else:
                    cx_qdc, cy_qdc = centro_x - 0.2, max_y
                    pts_qdc = [(cx_qdc, cy_qdc), (cx_qdc + qdc_w, cy_qdc), (cx_qdc + qdc_w, cy_qdc + qdc_d), (cx_qdc, cy_qdc + qdc_d)]
                
                msp.add_lwpolyline([pts_qdc[0], pts_qdc[1], pts_qdc[2], pts_qdc[3], pts_qdc[0]], dxfattribs={'layer': 'PROJ_ELETRICA_QDC'})
                msp.add_solid([pts_qdc[0], pts_qdc[1], pts_qdc[2]], dxfattribs={'layer': 'PROJ_ELETRICA_QDC'})

            # Tratamento de TUGs e TUEs Específicas
            qtd_tugs = int(dados_amb.get('TUGs (Qtd)', 0))
            qtd_tue = int(dados_amb.get('Qtd TUE', 0))
            eq_tue_nome = str(dados_amb.get('Equipamento TUE', '-'))
            pot_tue_val = int(dados_amb.get('Pot. Unit. TUE (VA)', 0))
            eq_lower = eq_tue_nome.lower()
            
            is_ac = "ar" in eq_lower or "condicionado" in eq_lower
            
            # Se for Ar-Condicionado, posiciona especificamente no centro da menor parede
            if is_ac and qtd_tue > 0 and logical_walls:
                menor_parede = min(logical_walls, key=lambda w: w['length'])
                pt1, pt2 = menor_parede['p1'], menor_parede['p2']
                px, py = (pt1[0] + pt2[0]) / 2, (pt1[1] + pt2[1]) / 2
                vx, vy = menor_parede['vx'], menor_parede['vy']
                nx, ny = get_inside_normal(vx, vy, px, py, centro_x, centro_y)
                
                # Deslocamento para dentro da parede
                px_ac, py_ac = px + nx * 0.15, py + ny * 0.15
                
                ponto_base1 = (px_ac - vx * 0.15, py_ac - vy * 0.15)
                ponto_base2 = (px_ac + vx * 0.15, py_ac + vy * 0.15)
                ponto_ponta = (px_ac + nx * 0.25, py_ac + ny * 0.25)
                
                msp.add_solid([ponto_base1, ponto_base2, ponto_ponta], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                msp.add_lwpolyline([ponto_base1, ponto_base2, ponto_ponta, ponto_base1], close=True, dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                
                # Escreve a potência em Watts ao lado da TUE do ar-condicionado
                msp.add_text(f"{pot_tue_val}W", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.12, 'color': 7, 'insert': (px_ac + nx * 0.35, py_ac + ny * 0.35)})
                tracar_eletroduto(msp, (px_ac, py_ac), (centro_x, centro_y), layer="PROJ_ELETRICA_ELETRODUTO")

            # Demais TUGs distribuídas no perímetro com recuo de 10cm
            total_tomadas_geral = qtd_tugs + (qtd_tue if not is_ac else 0)
            if total_tomadas_geral > 0 and comp_total > 0:
                passo = comp_total / total_tomadas_geral
                d_sw = get_dist_on_perimeter(sw_base_x, sw_base_y, segmentos_crus)
                dist_atual = d_sw + 0.10
                
                tomadas_pos = 0
                while tomadas_pos < total_tomadas_geral:
                    px, py, ux_w, uy_w = get_ponto_perimetro((dist_atual + comp_total) % comp_total, segmentos_crus)
                    n1x, n1y, n2x, n2y = -uy_w, ux_w, uy_w, -ux_w
                    ponta1, ponta2 = (px + n1x * 0.25, py + n1y * 0.25), (px + n2x * 0.25, py + n2y * 0.25)
                    pt_ponta = ponta1 if math.hypot(centro_x - ponta1[0], centro_y - ponta1[1]) < math.hypot(centro_x - ponta2[0], centro_y - ponta2[1]) else ponta2
                    pt_base1, pt_base2 = (px + ux_w * 0.15, py + uy_w * 0.15), (px - ux_w * 0.15, py - uy_w * 0.15)
                    
                    fill_mode = "half" if is_area_umida else "empty"
                    if fill_mode == "half":
                        msp.add_solid([pt_base1, (px, py), pt_ponta], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                        
                    msp.add_lwpolyline([pt_base1, pt_base2, pt_ponta, pt_base1], close=True, dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                    tracar_eletroduto(msp, (px, py), (centro_x, centro_y), layer="PROJ_ELETRICA_ELETRODUTO")
                    
                    dist_atual += passo
                    tomadas_pos += 1

            # Outras TUEs (como chuveiro, etc.) se houverem que não sejam AC
            if not is_ac and qtd_tue > 0 and eq_tue_nome != "-":
                px_tue, py_tue = centro_x, max_y - 0.2
                ponto_base1 = (px_tue - 0.15, py_tue)
                ponto_base2 = (px_tue + 0.15, py_tue)
                ponto_ponta = (px_tue, py_tue + 0.25)
                
                msp.add_solid([ponto_base1, ponto_base2, ponto_ponta], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                msp.add_lwpolyline([ponto_base1, ponto_base2, ponto_ponta, ponto_base1], close=True, dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                msp.add_text(f"{pot_tue_val}W", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.12, 'color': 7, 'insert': (px_tue + 0.2, py_tue + 0.1)})
                tracar_eletroduto(msp, (px_tue, py_tue), (centro_x, centro_y), layer="PROJ_ELETRICA_ELETRODUTO")

        # Backbone ligando o QDC aos centros dos demais ambientes
        qdc_nome = local_qdc.replace(" (recomendado)", "")
        coords_qdc = next(((geom['centro_x'], geom['centro_y']) for nome, geom in geometrias_ambientes.items() if nome == qdc_nome), None)
        if coords_qdc:
            for nome, geom in geometrias_ambientes.items():
                if nome != qdc_nome:
                    tracar_eletroduto(msp, coords_qdc, (geom['centro_x'], geom['centro_y']), layer="PROJ_ELETRICA_ELETRODUTO")

        tmp_out_path = tmp_in_path.replace(".dxf", "_out.dxf")
        doc.saveas(tmp_out_path)
        with open(tmp_out_path, "rb") as f: out_bytes = f.read()
        os.remove(tmp_out_path)
        return out_bytes
    finally: os.remove(tmp_in_path)
