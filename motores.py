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
    polilinhas, textos = [], []
    
    for entity in msp:
        tipo = entity.dxftype()
        if hasattr(entity.dxf, 'layer'):
            layer = str(entity.dxf.layer).upper().strip()
        else:
            continue
            
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
            
    portas = []
    for entity in msp:
        tipo = entity.dxftype()
        layer = str(entity.dxf.layer).upper().strip() if hasattr(entity.dxf, 'layer') else ""
        if layer == 'IA_PORTAS':
            if tipo == 'LINE': portas.append({'p1': (entity.dxf.start.x, entity.dxf.start.y), 'p2': (entity.dxf.end.x, entity.dxf.end.y)})
            elif tipo in ['LWPOLYLINE', 'POLYLINE']:
                pts = [(p[0], p[1]) for p in entity.get_points(format='xy')]
                if len(pts) >= 2: portas.append({'p1': pts[0], 'p2': pts[-1]})
            
    resultados, ambientes_processados = [], {}
    for polilinha in polilinhas:
        xs, ys = [p[0] for p in polilinha], [p[1] for p in polilinha]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        area = (max_x - min_x) * (max_y - min_y)
        perimetro = ((max_x - min_x) * 2) + ((max_y - min_y) * 2)
        if area < 0.5: continue
        
        nome = next((t['nome'] for t in textos if (min_x - 0.5) <= t['x'] <= (max_x + 0.5) and (min_y - 0.5) <= t['y'] <= (max_y + 0.5)), None)
        if not nome: continue
        
        centro_x, centro_y = (min_x + max_x) / 2, (min_y + max_y) / 2
        largura = max_x - min_x
        comprimento = max_y - min_y
        
        segmentos_crus, comp_total = [], 0
        poly = list(polilinha); poly.append(poly[0])
        for i in range(len(poly)-1):
            dst = math.hypot(poly[i+1][0]-poly[i][0], poly[i+1][1]-poly[i][1])
            if dst > 0.1:
                segmentos_crus.append((poly[i], poly[i+1], dst))
                comp_total += dst

        logical_walls = []
        for pt1, pt2, dst in segmentos_crus:
            mx, my = (pt1[0]+pt2[0])/2, (pt1[1]+pt2[1])/2
            vx, vy = (pt2[0] - pt1[0]) / dst, (pt2[1] - pt1[1]) / dst
            logical_walls.append({'p1': pt1, 'p2': pt2, 'length': dst, 'vx': vx, 'vy': vy})

        unique_portas = [p for p in portas if (min_x - 0.5) <= (p['p1'][0]+p['p2'][0])/2 <= (max_x + 0.5) and (min_y - 0.5) <= (p['p1'][1]+p['p2'][1])/2 <= (max_y + 0.5)]

        # 1. Distribuição de Luz e Depuração do Interruptor (Linha Magenta de 39cm a 15cm do término da soleira)
        if nome in dict_dados:
            qtd_ilum = int(dict_dados[nome]['Qtd Ilum.'])
            pot_ilum_unit = int(dict_dados[nome]['Pot. Unit. Ilum (VA)'])
            
            if qtd_ilum > 0:
                pontos_luz = []
                if largura >= comprimento:
                    if qtd_ilum == 1: pontos_luz.append((centro_x, centro_y))
                    else:
                        step = largura / (qtd_ilum + 1)
                        for i in range(1, qtd_ilum + 1): pontos_luz.append((min_x + step * i, centro_y))
                else:
                    if qtd_ilum == 1: pontos_luz.append((centro_x, centro_y))
                    else:
                        step = comprimento / (qtd_ilum + 1)
                        for i in range(1, qtd_ilum + 1): pontos_luz.append((centro_x, min_y + step * i))
                
                for lx, ly in pontos_luz:
                    msp.add_circle(center=(lx, ly), radius=0.25, dxfattribs={'layer': 'PROJ_ELETRICA_LUZ'})
                    msp.add_text(f"{pot_ilum_unit}VA", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.15, 'insert': (lx + 0.3, ly - 0.07)})
                    msp.add_text("a", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.15, 'color': 2, 'insert': (lx + 0.3, ly + 0.15)})

                # DEPURAÇÃO MAGENTA DO INTERRUPTOR
                if unique_portas and logical_walls:
                    p_porta = unique_portas[0]
                    mid_porta_x = (p_porta['p1'][0] + p_porta['p2'][0]) / 2
                    mid_porta_y = (p_porta['p1'][1] + p_porta['p2'][1]) / 2
                    
                    parede_porta = min(logical_walls, key=lambda w: point_seg_dist(mid_porta_x, mid_porta_y, w['p1'], w['p2']))
                    w_vx, w_vy = parede_porta['vx'], parede_porta['vy']
                    nx, ny = get_inside_normal(w_vx, w_vy, mid_porta_x, mid_porta_y, centro_x, centro_y)
                    
                    pt_porta_1, pt_porta_2 = p_porta['p1'], p_porta['p2']
                    d1 = math.hypot(pt_porta_1[0] - parede_porta['p1'][0], pt_porta_1[1] - parede_porta['p1'][1])
                    d2 = math.hypot(pt_porta_2[0] - parede_porta['p1'][0], pt_porta_2[1] - parede_porta['p1'][1])
                    
                    # Extremidade oposta à dobradiça (término do vão/soleira)
                    ponto_termino_soleira = pt_porta_2 if d1 < d2 else pt_porta_1
                    direcao_sinal = 1 if (ponto_termino_soleira[0] - mid_porta_x >= 0 and abs(w_vx) > 0.5) or (ponto_termino_soleira[1] - mid_porta_y >= 0 and abs(w_vy) > 0.5) else -1
                    
                    # Ponto inicial da linha magenta: 15cm após o término da soleira, tangenciando a parede para dentro
                    start_mx = ponto_termino_soleira[0] + (w_vx * 0.15 * direcao_sinal)
                    start_my = ponto_termino_soleira[1] + (w_vy * 0.15 * direcao_sinal)
                    
                    # Ponto final da linha magenta: comprimento de 39cm (0.39m) avançando para dentro do ambiente seguindo a normal
                    end_mx = start_mx + (nx * 0.39)
                    end_my = start_my + (ny * 0.39)
                    
                    if "PROJ_ELETRICA_DEBUG" not in doc.layers:
                        doc.layers.add(name="PROJ_ELETRICA_DEBUG", color=6)
                    msp.add_line((start_mx, start_my), (end_mx, end_my), dxfattribs={'layer': 'PROJ_ELETRICA_DEBUG'})

        # 2. POSICIONAMENTO DEFINITIVO DO QDC
        qdc_formatado = str(local_qdc).replace(" (recomendado)", "").strip().upper()
        nome_atual_upper = nome.strip().upper() if nome else ""
        is_ambiente_qdc = (nome_atual_upper == qdc_formatado)

        if is_ambiente_qdc and logical_walls:
            qdc_w, qdc_d = 0.4, 0.15
            maior_parede = max(logical_walls, key=lambda w: w['length'])
            pt1, pt2 = maior_parede['p1'], maior_parede['p2']
            
            is_vertical = abs(pt1[0] - pt2[0]) < abs(pt1[1] - pt2[1])
            
            cortes_portas = []
            for p in unique_portas:
                d_p1 = point_seg_dist(p['p1'][0], p['p1'][1], pt1, pt2)
                d_p2 = point_seg_dist(p['p2'][0], p['p2'][1], pt1, pt2)
                if d_p1 < 0.6 or d_p2 < 0.6:
                    if is_vertical:
                        y_min = min(p['p1'][1], p['p2'][1])
                        y_max = max(p['p1'][1], p['p2'][1])
                        cortes_portas.append((min(y_min, y_max), max(y_min, y_max)))
                    else:
                        x_min = min(p['p1'][0], p['p2'][0])
                        x_max = max(p['p1'][0], p['p2'][0])
                        cortes_portas.append((min(x_min, x_max), max(x_min, x_max)))
            
            if is_vertical:
                parede_min = min(pt1[1], pt2[1])
                parede_max = max(pt1[1], pt2[1])
                cortes_portas.sort(key=lambda x: x[0])
                
                trechos_livres = []
                cursor = parede_min
                for c_inf, c_sup in cortes_portas:
                    if c_inf > cursor + 0.1:
                        trechos_livres.append((cursor, c_inf))
                    cursor = max(cursor, c_sup)
                if cursor < parede_max - 0.1:
                    trechos_livres.append((cursor, parede_max))
                
                if trechos_livres:
                    melhor_trecho = max(trechos_livres, key=lambda t: t[1] - t[0])
                    if (melhor_trecho[1] - melhor_trecho[0]) >= qdc_w:
                        mid_y = (melhor_trecho[0] + melhor_trecho[1]) / 2
                        mx, my = pt1[0], mid_y
                    else:
                        mx, my = (pt1[0] + pt2[0]) / 2, (pt1[1] + pt2[1]) / 2
                else:
                    mx, my = (pt1[0] + pt2[0]) / 2, (pt1[1] + pt2[1]) / 2
            else:
                parede_min = min(pt1[0], pt2[0])
                parede_max = max(pt1[0], pt2[0])
                cortes_portas.sort(key=lambda x: x[0])
                
                trechos_livres = []
                cursor = parede_min
                for c_inf, c_sup in cortes_portas:
                    if c_inf > cursor + 0.1:
                        trechos_livres.append((cursor, c_inf))
                    cursor = max(cursor, c_sup)
                if cursor < parede_max - 0.1:
                    trechos_livres.append((cursor, parede_max))
                
                if trechos_livres:
                    melhor_trecho = max(trechos_livres, key=lambda t: t[1] - t[0])
                    if (melhor_trecho[1] - melhor_trecho[0]) >= qdc_w:
                        mid_x = (melhor_trecho[0] + melhor_trecho[1]) / 2
                        mx, my = mid_x, pt1[1]
                    else:
                        mx, my = (pt1[0] + pt2[0]) / 2, (pt1[1] + pt2[1]) / 2
                else:
                    mx, my = (pt1[0] + pt2[0]) / 2, (pt1[1] + pt2[1]) / 2

            vx, vy = maior_parede['vx'], maior_parede['vy']
            nx, ny = get_inside_normal(vx, vy, mx, my, centro_x, centro_y)
            out_nx, out_ny = -nx, -ny
            
            p1_qdc = (mx - vx * qdc_w/2, my - vy * qdc_w/2)
            p2_qdc = (mx + vx * qdc_w/2, my + vy * qdc_w/2)
            p3_qdc = (p2_qdc[0] + out_nx * qdc_d, p2_qdc[1] + out_ny * qdc_d)
            p4_qdc = (p1_qdc[0] + out_nx * qdc_d, p1_qdc[1] + out_ny * qdc_d)
            pts_qdc = [p1_qdc, p2_qdc, p3_qdc, p4_qdc]

            msp.add_lwpolyline(pts_qdc + [pts_qdc[0]], dxfattribs={'layer': 'PROJ_ELETRICA_QDC'})
            msp.add_solid(pts_qdc[:3], dxfattribs={'layer': 'PROJ_ELETRICA_QDC'})

        if nome in dict_dados:
            qtd_tugs = int(dict_dados[nome]['TUGs (Qtd)'])
            qtd_tue = int(dict_dados[nome]['Qtd TUE'])
            eq_tue_nome = str(dict_dados[nome]['Equipamento TUE'])
            pot_tue_val = int(dict_dados[nome]['Pot. Unit. TUE (VA)'])
            is_ac = "ar" in eq_tue_nome.lower()
            
            if is_ac and qtd_tue > 0 and logical_walls:
                menor_parede = min(logical_walls, key=lambda w: w['length'])
                pt1, pt2 = menor_parede['p1'], menor_parede['p2']
                px, py = (pt1[0] + pt2[0]) / 2, (pt1[1] + pt2[1]) / 2
                vx, vy = menor_parede['vx'], menor_parede['vy']
                nx, ny = get_inside_normal(vx, vy, px, py, centro_x, centro_y)
                
                ponto_base1 = (px - vx * 0.15, py - vy * 0.15)
                ponto_base2 = (px + vx * 0.15, py + vy * 0.15)
                ponto_ponta = (px + nx * 0.25, py + ny * 0.25)
                
                msp.add_solid([ponto_base1, ponto_base2, ponto_ponta], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                msp.add_lwpolyline([ponto_base1, ponto_base2, ponto_ponta, ponto_base1], close=True, dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                msp.add_text(f"{pot_tue_val}W", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.12, 'color': 2, 'insert': (px + nx * 0.35, py + ny * 0.35)})

            total_tugs = qtd_tugs + (qtd_tue if not is_ac else 0)
            if total_tugs > 0 and comp_total > 0:
                passo = comp_total / total_tugs
                is_umida = any(x in nome.lower() for x in ["coz", "serv", "banh", "lav", "sanit", "wc", "as"])
                
                for i in range(total_tugs):
                    px, py, seg_vx, seg_vy = get_ponto_perimetro(passo * i, segmentos_crus)
                    nx, ny = get_inside_normal(seg_vx, seg_vy, px, py, centro_x, centro_y)
                    
                    t_x = px + (nx * 0.10)
                    t_y = py + (ny * 0.10)
                    
                    ponto_b1 = (t_x - seg_vx * 0.10, t_y - seg_vy * 0.10)
                    ponto_b2 = (t_x + seg_vx * 0.10, t_y + seg_vy * 0.10)
                    ponto_pt = (t_x + nx * 0.20, t_y + ny * 0.20)
                    
                    msp.add_lwpolyline([ponto_b1, ponto_b2, ponto_pt, ponto_b1], close=True, dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                    if is_umida:
                        msp.add_solid([ponto_b1, ponto_b2, ponto_pt], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})

    doc.saveas(tmp_in_path)
    with open(tmp_in_path, "rb") as f:
        out_bytes = f.read()
    return out_bytes
    finally:
        if os.path.exists(tmp_in_path):
            os.remove(tmp_in_path)
