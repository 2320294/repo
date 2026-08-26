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

def ponto_em_poligono(x, y, polilinha):
    n = len(polilinha)
    dentro = False
    p1x, p1y = polilinha[0]
    for i in range(n + 1):
        p2x, p2y = polilinha[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        dentro = not dentro
        p1x, p1y = p2x, p2y
    return dentro

def processar_dxf(caminho_arquivo):
    doc = ezdxf.readfile(caminho_arquivo)
    msp = doc.modelspace()
    
    contagem_camadas = {'IA_AMBIENTES': 0, 'IA_TEXTOS': 0, 'IA_PORTAS': 0, 'IA_SOLEIRAS': 0}
    for entity in msp:
        if hasattr(entity.dxf, 'layer'):
            l = str(entity.dxf.layer).upper().strip()
            if l in contagem_camadas:
                contagem_camadas[l] += 1
                
    camadas_vazias = [cam for cam, qtd in contagem_camadas.items() if qtd == 0]
    if camadas_vazias:
        raise ValueError(
            f"❌ Erro de Validação do DXF: A(s) seguinte(s) camada(s) obrigatória(s) está(ão) vazia(s) ou ausente(s): {', '.join(camadas_vazias)}. "
            f"Certifique-se de desenhar os elementos nos respectivos layers (IA_AMBIENTES, IA_TEXTOS, IA_PORTAS, IA_SOLEIRAS) antes de gerar o projeto."
        )

    polilinhas, textos = [], []
    for entity in msp:
        tipo = entity.dxftype()
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
            
    resultados, ambientes_processados = [], {}
    for polilinha in polilinhas:
        xs, ys = [p[0] for p in polilinha], [p[1] for p in polilinha]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        area = (max_x - min_x) * (max_y - min_y)
        perimetro = ((max_x - min_x) * 2) + ((max_y - min_y) * 2)
        if area < 0.5: continue
        
        nome_ambiente = next((t['nome'] for t in textos if (min_x - 0.5) <= t['x'] <= (max_x + 0.5) and (min_y - 0.5) <= t['y'] <= (max_y + 0.5)), None)
        if not nome_ambiente: continue
        
        if nome_ambiente in ambientes_processados:
            ambientes_processados[nome_ambiente] += 1
            nome_ambiente = f"{nome_ambiente} {ambientes_processados[nome_ambiente]}"
        else: ambientes_processados[nome_ambiente] = 1
                
        cargas = dimensionar_cargas(nome_ambiente, area, perimetro)
        resultados.append({
            "Ambiente": nome_ambiente, "Centro_X": (min_x+max_x)/2, "Centro_Y": (min_y+max_y)/2, "Área (m²)": area, "Perímetro (m)": perimetro,
            "Qtd Ilum.": int(cargas["Qtd Ilum."]), "Pot. Unit. Ilum (VA)": int(cargas["Pot. Unit. Ilum (VA)"]), "Carga Ilum. (VA)": int(cargas["Carga Ilum. (VA)"]),
            "TUGs (Qtd)": int(cargas["TUGs (Qtd)"]), "Pot. Unit. TUG (VA)": int(cargas["Pot. Unit. TUG (VA)"]), "Carga TUGs (VA)": int(cargas["Carga TUGs (VA)"]),
            "Equipamento TUE": cargas["Equipamento TUE"], "Qtd TUE": int(cargas["Qtd TUE"]), "Pot. Unit. TUE (VA)": int(cargas["Pot. Unit. TUE (VA)"]), "Carga TUE (VA)": int(cargas["Carga TUE (VA)"])
        })
    return resultados

def get_inside_normal(vx, vy, start_x, start_y, cx, cy):
    n1x, n1y, n2x, n2y = -vy, vx, vy, -vx
    return (n1x, n1y) if math.hypot(cx - (start_x + n1x), cy - (start_y + n1y)) < math.hypot(cx - (start_x + n2x), cy - (start_y + n2y)) else (n2x, n2y)

def point_seg_dist(px, py, pt1, pt2):
    l2 = (pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2
    if l2 == 0: return math.hypot(px - pt1[0], py - pt1[1])
    t = max(0, min(1, ((px - pt1[0])*(pt2[0] - pt1[0]) + (py - pt1[1])*(pt2[1] - pt1[1])) / l2))
    return math.hypot(px - (pt1[0] + t * (pt2[0] - pt1[0])), py - (pt1[1] + t * (pt2[1] - pt1[1])))

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
    tmp_in_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_in:
            tmp_in.write(dxf_bytes)
            tmp_in_path = tmp_in.name

        doc = ezdxf.readfile(tmp_in_path)
        msp = doc.modelspace()
        
        contagem_camadas = {'IA_AMBIENTES': 0, 'IA_TEXTOS': 0, 'IA_PORTAS': 0, 'IA_SOLEIRAS': 0}
        for entity in msp:
            if hasattr(entity.dxf, 'layer'):
                l = str(entity.dxf.layer).upper().strip()
                if l in contagem_camadas:
                    contagem_camadas[l] += 1
                    
        camadas_vazias = [cam for cam, qtd in contagem_camadas.items() if qtd == 0]
        if camadas_vazias:
            raise ValueError(
                f"❌ Erro de Geração do CAD: A(s) seguinte(s) camada(s) obrigatória(s) está(ão) vazia(s) ou ausente(s): {', '.join(camadas_vazias)}. "
                f"Verifique se os elementos estão corretamente posicionados em suas camadas antes de processar."
            )
        
        camadas = {
            "PROJ_ELETRICA_LUZ": 2,          # Amarelo
            "PROJ_ELETRICA_QDC": 1,          # Vermelho
            "PROJ_ELETRICA_TEXTO": 2,        # Amarelo
            "PROJ_ELETRICA_TOMADA": 4,       # Ciano
            "PROJ_ELETRICA_INTERRUPTOR": 5,  # Azul
            "PROJ_ELETRICA_DEBUG": 6         # Magenta
        }
        for nome_l, cor_l in camadas.items():
            if nome_l not in doc.layers: doc.layers.add(name=nome_l, color=cor_l)
            else: doc.layers.get(nome_l).color = cor_l
        
        polilinhas, textos, portas_raw, soleiras_raw = [], [], [], []
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
            elif layer == 'IA_PORTAS':
                if tipo == 'LINE':
                    portas_raw.append({'p1': (entity.dxf.start.x, entity.dxf.start.y), 'p2': (entity.dxf.end.x, entity.dxf.end.y)})
                elif tipo in ['LWPOLYLINE', 'POLYLINE']:
                    pts = [(p[0], p[1]) for p in entity.get_points(format='xy')]
                    if len(pts) >= 2: portas_raw.append({'p1': pts[0], 'p2': pts[-1]})
            elif layer == 'IA_SOLEIRAS':
                if tipo == 'LINE':
                    soleiras_raw.append({'p1': (entity.dxf.start.x, entity.dxf.start.y), 'p2': (entity.dxf.end.x, entity.dxf.end.y)})
                elif tipo in ['LWPOLYLINE', 'POLYLINE']:
                    pts = [(p[0], p[1]) for p in entity.get_points(format='xy')]
                    if len(pts) >= 2: soleiras_raw.append({'p1': pts[0], 'p2': pts[-1]})

        ambientes_nomes = {}
        for poly in polilinhas:
            xs, ys = [p[0] for p in poly], [p[1] for p in poly]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            nome_achado = next((t['nome'] for t in textos if (min_x - 0.5) <= t['x'] <= (max_x + 0.5) and (min_y - 0.5) <= t['y'] <= (max_y + 0.5)), "DESCONHECIDO")
            ambientes_nomes[tuple(poly)] = nome_achado

        # Identifica soleiras com porta encostada (< 0.3m)
        soleiras_com_porta = []
        for s in soleiras_raw:
            s_p1, s_p2 = s['p1'], s['p2']
            porta_encostada = None
            for p in portas_raw:
                d1 = point_seg_dist(p['p1'][0], p['p1'][1], s_p1, s_p2)
                d2 = point_seg_dist(p['p2'][0], p['p2'][1], s_p1, s_p2)
                d3 = point_seg_dist(s_p1[0], s_p1[1], p['p1'], p['p2'])
                d4 = point_seg_dist(s_p2[0], s_p2[1], p['p1'], p['p2'])
                
                if d1 < 0.3 or d2 < 0.3 or d3 < 0.3 or d4 < 0.3:
                    porta_encostada = p
                    break
            if porta_encostada is not None:
                soleiras_com_porta.append({'s': s, 'porta': porta_encostada})

        # 1. PROCESSA CADA SOLEIRA VÁLIDA GARANTINDO O POSICIONAMENTO ESTRITAMENTE INTERNO
        for item in soleiras_com_porta:
            s = item['s']
            p_porta = item['porta']
            s_p1, s_p2 = s['p1'], s['p2']
            
            pm_porta_x = (p_porta['p1'][0] + p_porta['p2'][0]) / 2
            pm_porta_y = (p_porta['p1'][1] + p_porta['p2'][1]) / 2
            
            d1 = math.hypot(s_p1[0] - pm_porta_x, s_p1[1] - pm_porta_y)
            d2 = math.hypot(s_p2[0] - pm_porta_x, s_p2[1] - pm_porta_y)
            ponto_oposto = s_p2 if d1 < d2 else s_p1
            
            # Varre todos os ambientes adjacentes para garantir que cômodos como a AS e o Quarto 2 recebam seus círculos corretamente
            for poly in polilinhas:
                xs, ys = [pt[0] for pt in poly], [pt[1] for pt in poly]
                sm_x, sm_y = (s_p1[0] + s_p2[0]) / 2, (s_p1[1] + s_p2[1]) / 2
                
                if min(xs) - 0.8 <= sm_x <= max(xs) + 0.8 and min(ys) - 0.8 <= sm_y <= max(ys) + 0.8:
                    cx = sum(xs) / len(xs)
                    cy = sum(ys) / len(ys)
                    
                    d_tot = math.hypot(cx - ponto_oposto[0], cy - ponto_oposto[1])
                    if d_tot > 0:
                        dir_x, dir_y = (cx - ponto_oposto[0]) / d_tot, (cy - ponto_oposto[1]) / d_tot
                        # Desloca estritamente 18cm para dentro do ambiente em direção ao centroide
                        final_x = ponto_oposto[0] + dir_x * 0.18
                        final_y = ponto_oposto[1] + dir_y * 0.18
                        
                        if ponto_em_poligono(final_x, final_y, poly):
                            msp.add_circle(center=(final_x, final_y), radius=0.15, dxfattribs={'layer': 'PROJ_ELETRICA_DEBUG', 'color': 6})

        ambientes_processados, dict_dados = {}, {row['Ambiente']: row for row in dados_editados}

        # 2. LOOP DE PROCESSAMENTO DOS AMBIENTES (ILUMINAÇÃO, QDC, TOMADAS)
        for polilinha in polilinhas:
            xs, ys = [p[0] for p in polilinha], [p[1] for p in polilinha]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            area = (max_x - min_x) * (max_y - min_y)
            perimetro = ((max_x - min_x) * 2) + ((max_y - min_y) * 2)
            if area < 0.5: continue
            
            nome = next((t['nome'] for t in textos if (min_x - 0.5) <= t['x'] <= (max_x + 0.5) and (min_y - 0.5) <= t['y'] <= (max_y + 0.5)), None)
            if not nome: continue
            
            if nome in ambientes_processados:
                ambientes_processados[nome] += 1
                nome = f"{nome} {ambientes_processados[nome]}"
            else:
                ambientes_processados[nome] = 1
            
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
                vx, vy = (pt2[0] - pt1[0]) / dst, (pt2[1] - pt1[1]) / dst
                logical_walls.append({'p1': pt1, 'p2': pt2, 'length': dst, 'vx': vx, 'vy': vy})

            unique_portas = [p for p in portas_raw if (min_x - 0.8) <= (p['p1'][0]+p['p2'][0])/2 <= (max_x + 0.8) and (min_y - 0.8) <= (p['p1'][1]+p['p2'][1])/2 <= (max_y + 0.8)]

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
                            cortes_portas.append((min(p['p1'][1], p['p2'][1]), max(p['p1'][1], p['p2'][1])))
                        else:
                            cortes_portas.append((min(p['p1'][0], p['p2'][0]), max(p['p1'][0], p['p2'][0])))
                
                if is_vertical:
                    parede_min = min(pt1[1], pt2[1])
                    parede_max = max(pt1[1], pt2[1])
                    cortes_portas.sort(key=lambda x: x[0])
                    
                    trechos_livres, cursor = [], parede_min
                    for c_inf, c_sup in cortes_portas:
                        if c_inf > cursor + 0.1: trechos_livres.append((cursor, c_inf))
                        cursor = max(cursor, c_sup)
                    if cursor < parede_max - 0.1: trechos_livres.append((cursor, parede_max))
                    
                    if trechos_livres:
                        melhor_trecho = max(trechos_livres, key=lambda t: t[1] - t[0])
                        mid_y = (melhor_trecho[0] + melhor_trecho[1]) / 2
                        mx, my = pt1[0], mid_y
                    else:
                        mx, my = (pt1[0] + pt2[0]) / 2, (pt1[1] + pt2[1]) / 2
                else:
                    parede_min = min(pt1[0], pt2[0])
                    parede_max = max(pt1[0], pt2[0])
                    cortes_portas.sort(key=lambda x: x[0])
                    
                    trechos_livres, cursor = [], parede_min
                    for c_inf, c_sup in cortes_portas:
                        if c_inf > cursor + 0.1: trechos_livres.append((cursor, c_inf))
                        cursor = max(cursor, c_sup)
                    if cursor < parede_max - 0.1: trechos_livres.append((cursor, parede_max))
                    
                    if trechos_livres:
                        melhor_trecho = max(trechos_livres, key=lambda t: t[1] - t[0])
                        mid_x = (melhor_trecho[0] + melhor_trecho[1]) / 2
                        mx, my = mid_x, pt1[1]
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
                qtd_tue = int(dict_dados[nome]['TUE']) if 'TUE' in dict_dados[nome] else int(dict_dados[nome]['Qtd TUE'])
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
    except Exception as e:
        raise e
    finally:
        if tmp_in_path and os.path.exists(tmp_in_path):
            os.remove(tmp_in_path)
