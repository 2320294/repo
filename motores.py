import ezdxf
import math
import tempfile
import os

# ============================================================
# CONFIGURAÇÃO DOS INTERRUPTORES / CÍRCULOS
# ============================================================
CONFIG_INTERRUPTores = {
    # Exemplo: "Sala": {"quantidade": 1, "porta": 1}
}

RAIO_CIRCULO_INTERRUPT = 0.15

# ============================================================
# DIMENSIONAMENTO DAS CARGAS (DINÂMICO)
# ============================================================

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
        "Pot. Unit. TUG (VA)": 600 if is_umida else 100, 
        "Carga TUGs (VA)": carga_tugs,
        "Equipamento TUE": tue_nome,
        "Qtd TUE": qtd_tue,
        "Pot. Unit. TUE (VA)": round(carga_tue / max(1, qtd_tue)),
        "Carga TUE (VA)": carga_tue
    }

# ============================================================
# GEOMETRIA E AUXILIARES
# ============================================================

def ponto_em_poligono(x, y, polilinha):
    if not polilinha: return False
    n = len(polilinha)
    dentro = False
    p1x, p1y = polilinha[0]
    for i in range(n + 1):
        p2x, p2y = polilinha[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    xinters = None
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or (xinters is not None and x <= xinters):
                        dentro = not dentro
        p1x, p1y = p2x, p2y
    return dentro

def point_seg_dist(px, py, pt1, pt2):
    l2 = (pt1[0] - pt2[0]) ** 2 + (pt1[1] - pt2[1]) ** 2
    if l2 == 0: return math.hypot(px - pt1[0], py - pt1[1])
    t = max(0, min(1, ((px - pt1[0]) * (pt2[0] - pt1[0]) + (py - pt1[1]) * (pt2[1] - pt1[1])) / l2))
    proj_x = pt1[0] + t * (pt2[0] - pt1[0])
    proj_y = pt1[1] + t * (pt2[1] - pt1[1])
    return math.hypot(px - proj_x, py - proj_y)

def get_ponto_perimetro(d, segs):
    acumulado = 0
    for pt1, pt2, dst in segs:
        if acumulado + dst >= d or math.isclose(acumulado + dst, d, abs_tol=1e-5):
            if dst == 0: return (pt1[0], pt1[1], 0, 0)
            ratio = (d - acumulado) / dst
            x = pt1[0] + (pt2[0] - pt1[0]) * ratio
            y = pt1[1] + (pt2[1] - pt1[1]) * ratio
            vx = (pt2[0] - pt1[0]) / dst
            vy = (pt2[1] - pt1[1]) / dst
            return (x, y, vx, vy)
        acumulado += dst
    pt1, pt2, dst = segs[-1]
    if dst == 0: return (pt2[0], pt2[1], 0, 0)
    return (pt2[0], pt2[1], (pt2[0] - pt1[0]) / dst, (pt2[1] - pt1[1]) / dst)

def get_inside_normal(vx, vy, start_x, start_y, cx, cy):
    n1x, n1y = -vy, vx
    n2x, n2y = vy, -vx
    d1 = math.hypot(cx - (start_x + n1x), cy - (start_y + n1y))
    d2 = math.hypot(cx - (start_x + n2x), cy - (start_y + n2y))
    return (n1x, n1y) if d1 < d2 else (n2x, n2y)

# ============================================================
# LÓGICA DE INTERRUPTORES (CÍRCULOS NAS SOLEIRAS)
# ============================================================

def normalizar_nome_ambiente(nome):
    if nome is None: return ""
    return str(nome).strip().lower()

def obter_config_interruptores(nome_ambiente):
    nome_normalizado = normalizar_nome_ambiente(nome_ambiente)
    for nome_config, config in CONFIG_INTERRUPTores.items():
        if normalizar_nome_ambiente(nome_config) == nome_normalizado:
            return config
    return None

def encontrar_portas_do_ambiente(polilinha, portas_raw):
    if not polilinha: return []
    xs, ys = [p[0] for p in polilinha], [p[1] for p in polilinha]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    portas_ambiente = []
    for porta in portas_raw:
        cx, cy = (porta['p1'][0] + porta['p2'][0]) / 2, (porta['p1'][1] + porta['p2'][1]) / 2
        if min_x - 0.8 <= cx <= max_x + 0.8 and min_y - 0.8 <= cy <= max_y + 0.8:
            portas_ambiente.append(porta)
    return portas_ambiente

def criar_geometria_circulo_soleira(soleira, porta, polilinha, polilinhas):
    s_p1, s_p2 = soleira['p1'], soleira['p2']
    d_porta_1 = point_seg_dist(porta['p1'][0], porta['p1'][1], s_p1, s_p2)
    d_porta_2 = point_seg_dist(porta['p2'][0], porta['p2'][1], s_p1, s_p2)
    extremo_porta_encostado = porta['p1'] if d_porta_1 <= d_porta_2 else porta['p2']
    p4 = porta['p2'] if d_porta_1 <= d_porta_2 else porta['p1']

    sx, sy = s_p2[0] - s_p1[0], s_p2[1] - s_p1[1]
    s2 = sx * sx + sy * sy
    if s2 == 0: return None
    t = max(0.0, min(1.0, ((extremo_porta_encostado[0] - s_p1[0]) * sx + (extremo_porta_encostado[1] - s_p1[1]) * sy) / s2))
    p1 = (s_p1[0] + t * sx, s_p1[1] + t * sy)
    p2 = s_p2 if math.hypot(p1[0]-s_p1[0], p1[1]-s_p1[1]) <= math.hypot(p1[0]-s_p2[0], p1[1]-s_p2[1]) else s_p1
    
    vetor_x, vetor_y = p2[0] - p1[0], p2[1] - p1[1]
    p3 = (p4[0] + vetor_x, p4[1] + vetor_y)
    
    soleira_len = math.hypot(vetor_x, vetor_y)
    if soleira_len == 0: return None
    
    return {
        'p1': p1, 'p2': p2, 'p3': p3, 'p4': p4,
        'soleira_vx': vetor_x / soleira_len, 'soleira_vy': vetor_y / soleira_len
    }

def desenhar_circulo_tangente_soleira(msp, ponto_tangencia, soleira_vx, soleira_vy, polilinha, raio=RAIO_CIRCULO_INTERRUPT):
    cx_ambiente = sum(pt[0] for pt in polilinha) / len(polilinha)
    cy_ambiente = sum(pt[1] for pt in polilinha) / len(polilinha)
    nx, ny = get_inside_normal(soleira_vx, soleira_vy, ponto_tangencia[0], ponto_tangencia[1], cx_ambiente, cy_ambiente)
    
    centro = (ponto_tangencia[0] + nx * raio, ponto_tangencia[1] + ny * raio)
    if not ponto_em_poligono(centro[0], centro[1], polilinha):
        centro = (ponto_tangencia[0] - nx * raio, ponto_tangencia[1] - ny * raio)
    if not ponto_em_poligono(centro[0], centro[1], polilinha): return False

    msp.add_circle(center=centro, radius=raio, dxfattribs={'layer': 'PROJ_ELETRICA_INTERRUPTOR', 'color': 5})
    return True

def processar_interruptores(msp, polilinhas, portas_raw, soleiras_raw, soleiras_com_porta, nome_ambiente, polilinha):
    config = obter_config_interruptores(nome_ambiente)
    if not config: return
    quantidade = int(config.get('quantidade', 0))
    if quantidade not in [1, 2]: return

    portas_ambiente = encontrar_portas_do_ambiente(polilinha, portas_raw)
    if not portas_ambiente: return

    portas_com_soleira = []
    for porta in portas_ambiente:
        soleiras_porta = [item['s'] for item in soleiras_com_porta if item['porta'] is porta]
        if soleiras_porta:
            portas_com_soleira.append({'porta': porta, 'soleiras': soleiras_porta})

    if not portas_com_soleira: return

    if quantidade == 1:
        porta_escolhida = int(config.get('porta', 1)) - 1
        if 0 <= porta_escolhida < len(portas_com_soleira):
            item_porta = portas_com_soleira[porta_escolhida]
            soleira = item_porta['soleiras'][0]
            geom = criar_geometria_circulo_soleira(soleira, item_porta['porta'], polilinha, polilinhas)
            if geom:
                ponto_tangencia = geom['p2'] if ponto_em_poligono(geom['p2'][0]+geom['soleira_vx']*RAIO_CIRCULO_INTERRUPT, geom['p2'][1]+geom['soleira_vy']*RAIO_CIRCULO_INTERRUPT, polilinha) else geom['p3']
                desenhar_circulo_tangente_soleira(msp, ponto_tangencia, geom['soleira_vx'], geom['soleira_vy'], polilinha)
    elif quantidade == 2:
        for item_porta in portas_com_soleira[:2]:
            soleira = item_porta['soleiras'][0]
            geom = criar_geometria_circulo_soleira(soleira, item_porta['porta'], polilinha, polilinhas)
            if geom:
                ponto_tangencia = geom['p2'] if ponto_em_poligono(geom['p2'][0]+geom['soleira_vx']*RAIO_CIRCULO_INTERRUPT, geom['p2'][1]+geom['soleira_vy']*RAIO_CIRCULO_INTERRUPT, polilinha) else geom['p3']
                desenhar_circulo_tangente_soleira(msp, ponto_tangencia, geom['soleira_vx'], geom['soleira_vy'], polilinha)

# ============================================================
# REGRAS DE SEGURANÇA PARA TOMADAS
# ============================================================

DISTANCIA_MINIMA_CANTO_TOMADA = 0.20
DISTANCIA_MINIMA_PORTA_TOMADA = 0.30
DISTANCIA_MINIMA_SOLEIRA_TOMADA = 0.30

def ponto_tomada_valido(px, py, polilinha, portas_raw, soleiras_raw):
    for vx, vy in polilinha:
        if math.hypot(px - vx, py - vy) < DISTANCIA_MINIMA_CANTO_TOMADA:
            return False
    for porta in portas_raw:
        if point_seg_dist(px, py, porta['p1'], porta['p2']) < DISTANCIA_MINIMA_PORTA_TOMADA:
            return False
    for soleira in soleiras_raw:
        if point_seg_dist(px, py, soleira['p1'], soleira['p2']) < DISTANCIA_MINIMA_SOLEIRA_TOMADA:
            return False
    return True

def procurar_ponto_valido_perimetro(distancia_original, comp_total, segmentos_crus, polilinha, portas_raw, soleiras_raw):
    if comp_total <= 0: return None
    px, py, vx, vy = get_ponto_perimetro(distancia_original, segmentos_crus)
    if ponto_tomada_valido(px, py, polilinha, portas_raw, soleiras_raw):
        return (px, py, vx, vy)
    for deslocamento in [0.05, 0.10, 0.20, 0.35, 0.50, -0.05, -0.10, -0.20, -0.35, -0.50]:
        dt = distancia_original + deslocamento
        if 0 < dt < comp_total:
            tx, ty, tvx, tvy = get_ponto_perimetro(dt, segmentos_crus)
            if ponto_tomada_valido(tx, ty, polilinha, portas_raw, soleiras_raw):
                return (tx, ty, tvx, tvy)
    return (px, py, vx, vy)

def procurar_ponto_valido_na_parede(pt1, pt2, fator_original, polilinha, portas_raw, soleiras_raw):
    dx, dy = pt2[0] - pt1[0], pt2[1] - pt1[1]
    comprimento = math.hypot(dx, dy)
    if comprimento <= 0.4: return (pt1[0] + dx/2, pt1[1] + dy/2, dx/comprimento, dy/comprimento)
    for f in [fator_original, 0.5, 0.3, 0.7, 0.2, 0.8]:
        px, py = pt1[0] + dx * f, pt1[1] + dy * f
        if ponto_tomada_valido(px, py, polilinha, portas_raw, soleiras_raw):
            return (px, py, dx / comprimento, dy / comprimento)
    return (pt1[0] + dx * fator_original, pt1[1] + dy * fator_original, dx / comprimento, dy / comprimento)

# ============================================================
# PROCESSAMENTO DO DXF E GERAÇÃO DO CAD
# ============================================================

def processar_dxf(caminho_arquivo):
    doc = ezdxf.readfile(caminho_arquivo)
    msp = doc.modelspace()
    
    contagem_camadas = {'IA_AMBIENTES': 0, 'IA_TEXTOS': 0, 'IA_PORTAS': 0, 'IA_SOLEIRAS': 0}
    for entity in msp:
        if hasattr(entity.dxf, 'layer'):
            l = str(entity.dxf.layer).upper().strip()
            if l in contagem_camadas: contagem_camadas[l] += 1
                
    camadas_vazias = [cam for cam, qtd in contagem_camadas.items() if qtd == 0]
    if camadas_vazias:
        raise ValueError(f"❌ Erro de Validação do DXF: Camada(s) obrigatória(s) vazia(s): {', '.join(camadas_vazias)}.")

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

def gerar_cad_unifilar(dxf_bytes, dados_editados, local_qdc):
    tmp_in_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_in:
            tmp_in.write(dxf_bytes)
            tmp_in_path = tmp_in.name

        doc = ezdxf.readfile(tmp_in_path)
        msp = doc.modelspace()
        
        camadas = {
            "PROJ_ELETRICA_LUZ": 2, "PROJ_ELETRICA_QDC": 1, "PROJ_ELETRICA_TEXTO": 2,
            "PROJ_ELETRICA_TOMADA": 4, "PROJ_ELETRICA_INTERRUPTOR": 5, "PROJ_ELETRICA_DEBUG": 6
        }
        for nome_l, cor_l in camadas.items():
            if nome_l not in doc.layers: doc.layers.add(name=nome_l, color=cor_l)
            else: doc.layers.get(nome_l).color = cor_l
        
        polilinhas, textos, portas_raw, soleiras_raw = [], [], [], []
        for entity in msp:
            tipo = entity.dxftype()
            if not hasattr(entity.dxf, 'layer'): continue
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
                if tipo == 'LINE': portas_raw.append({'p1': (entity.dxf.start.x, entity.dxf.start.y), 'p2': (entity.dxf.end.x, entity.dxf.end.y)})
                elif tipo in ['LWPOLYLINE', 'POLYLINE']:
                    pts = [(p[0], p[1]) for p in entity.get_points(format='xy')]
                    if len(pts) >= 2: portas_raw.append({'p1': pts[0], 'p2': pts[-1]})
            elif layer == 'IA_SOLEIRAS':
                if tipo == 'LINE': soleiras_raw.append({'p1': (entity.dxf.start.x, entity.dxf.start.y), 'p2': (entity.dxf.end.x, entity.dxf.end.y)})
                elif tipo in ['LWPOLYLINE', 'POLYLINE']:
                    pts = [(p[0], p[1]) for p in entity.get_points(format='xy')]
                    if len(pts) >= 2: soleiras_raw.append({'p1': pts[0], 'p2': pts[-1]})

        soleiras_com_porta = []
        for s in soleiras_raw:
            s_p1, s_p2 = s['p1'], s['p2']
            melhor_porta, menor_distancia = None, float('inf')
            for p in portas_raw:
                pm_porta = ((p['p1'][0] + p['p2'][0]) / 2, (p['p1'][1] + p['p2'][1]) / 2)
                d3 = point_seg_dist(pm_porta[0], pm_porta[1], s_p1, s_p2)
                if d3 <= 0.30 and d3 < menor_distancia:
                    menor_distancia, melhor_porta = d3, p
            if melhor_porta is not None:
                soleiras_com_porta.append({'s': s, 'porta': melhor_porta})

        # 1. PROCESSA INTERRUPTORES (CÍRCULOS)
        ambientes_proc_int = {}
        for polilinha in polilinhas:
            xs, ys = [p[0] for p in polilinha], [p[1] for p in polilinha]
            min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
            if (max_x - min_x) * (max_y - min_y) < 0.5: continue
            nome_ambiente = next((t['nome'] for t in textos if min_x - 0.5 <= t['x'] <= max_x + 0.5 and min_y - 0.5 <= t['y'] <= max_y + 0.5), None)
            if not nome_ambiente: continue
            
            if nome_ambiente in ambientes_proc_int:
                ambientes_proc_int[nome_ambiente] += 1
                nome_busca_int = f"{nome_ambiente} {ambientes_proc_int[nome_ambiente]}"
            else:
                ambientes_proc_int[nome_ambiente] = 1
                nome_busca_int = nome_ambiente

            processar_interruptores(msp, polilinhas, portas_raw, soleiras_raw, soleiras_com_porta, nome_busca_int, polilinha)

        # 2. PROCESSA AMBIENTES (QDC, ILUMINAÇÃO, TOMADAS TUE E TUG)
        ambientes_processados, dict_dados = {}, {row['Ambiente']: row for row in dados_editados}

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
                nome_busca = f"{nome} {ambientes_processados[nome]}"
            else:
                ambientes_processados[nome] = 1
                nome_busca = nome
            
            row_data = dict_dados.get(nome_busca, dict_dados.get(nome, None))
            if not row_data: continue
            
            centro_x, centro_y = (min_x + max_x) / 2, (min_y + max_y) / 2
            largura, comprimento = max_x - min_x, max_y - min_y
            
            segmentos_crus, comp_total = [], 0
            poly = list(polilinha)
            if poly[0] != poly[-1]: poly.append(poly[0])
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

            # ILUMINAÇÃO
            qtd_ilum = int(row_data.get('Qtd Ilum.', 1))
            pot_ilum_unit = int(row_data.get('Pot. Unit. Ilum (VA)', 100))
            if qtd_ilum > 0:
                pontos_luz = [(centro_x, centro_y)] if qtd_ilum == 1 else [(min_x + (largura / (qtd_ilum + 1)) * i, centro_y) for i in range(1, qtd_ilum + 1)] if largura >= comprimento else [(centro_x, min_y + (comprimento / (qtd_ilum + 1)) * i) for i in range(1, qtd_ilum + 1)]
                for lx, ly in pontos_luz:
                    msp.add_circle(center=(lx, ly), radius=0.25, dxfattribs={'layer': 'PROJ_ELETRICA_LUZ'})
                    msp.add_text(f"{pot_ilum_unit}VA", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.15, 'insert': (lx + 0.3, ly - 0.07)})
                    msp.add_text("a", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.15, 'color': 2, 'insert': (lx + 0.3, ly + 0.15)})

            # RENDERIZAÇÃO DO QDC (RESTAURADA COM SUCESSO)
            qdc_formatado = str(local_qdc).replace(" (recomendado)", "").strip().upper()
            if (nome.strip().upper() == qdc_formatado) and logical_walls:
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
                    parede_min, parede_max = min(pt1[1], pt2[1]), max(pt1[1], pt2[1])
                    cortes_portas.sort(key=lambda x: x[0])
                    trechos_livres, cursor = [], parede_min
                    for c_inf, c_sup in cortes_portas:
                        if c_inf > cursor + 0.1: trechos_livres.append((cursor, c_inf))
                        cursor = max(cursor, c_sup)
                    if cursor < parede_max - 0.1: trechos_livres.append((cursor, parede_max))
                    
                    if trechos_livres:
                        melhor_trecho = max(trechos_livres, key=lambda t: t[1] - t[0])
                        mx, my = pt1[0], (melhor_trecho[0] + melhor_trecho[1]) / 2
                    else:
                        mx, my = (pt1[0] + pt2[0]) / 2, (pt1[1] + pt2[1]) / 2
                else:
                    parede_min, parede_max = min(pt1[0], pt2[0]), max(pt1[0], pt2[0])
                    cortes_portas.sort(key=lambda x: x[0])
                    trechos_livres, cursor = [], parede_min
                    for c_inf, c_sup in cortes_portas:
                        if c_inf > cursor + 0.1: trechos_livres.append((cursor, c_inf))
                        cursor = max(cursor, c_sup)
                    if cursor < parede_max - 0.1: trechos_livres.append((cursor, parede_max))
                    
                    if trechos_livres:
                        melhor_trecho = max(trechos_livres, key=lambda t: t[1] - t[0])
                        mx, my = (melhor_trecho[0] + melhor_trecho[1]) / 2, pt1[1]
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

            # TOMADAS TUE
            qtd_tue = int(row_data.get('Qtd TUE', row_data.get('TUE', 0)))
            eq_tue_nome = str(row_data.get('Equipamento TUE', '-'))
            pot_tue_val = int(row_data.get('Pot. Unit. TUE (VA)', 0))
            if pot_tue_val == 0:
                eq_lower = eq_tue_nome.lower()
                pot_tue_val = 5500 if "chuveiro" in eq_lower else 1200 if "ar" in eq_lower else 2000 if "micro" in eq_lower or "forno" in eq_lower else 1000

            is_chuveiro_ou_ac = any(x in eq_tue_nome.lower() for x in ["chuveiro", "ar-condicionado", "ar condicionado"])
            is_ambiente_molhado = any(x in nome.lower() for x in ["coz", "serv", "banh", "lav", "sanit", "wc", "as"])

            if qtd_tue > 0 and logical_walls:
                paredes_candidatas = sorted(logical_walls, key=lambda w: w['length'])
                paredes_sem_porta = [w for w in paredes_candidatas if not any(point_seg_dist((p['p1'][0]+p['p2'][0])/2, (p['p1'][1]+p['p2'][1])/2, w['p1'], w['p2']) < 0.6 for p in unique_portas)]
                paredes_finais = paredes_sem_porta if paredes_sem_porta else paredes_candidatas
                
                for idx_tue in range(qtd_tue):
                    p_alvo = paredes_finais[idx_tue % len(paredes_finais)]
                    fator = 0.5 if qtd_tue == 1 else (idx_tue + 1) / (qtd_tue + 1)
                    res_tue = procurar_ponto_valido_na_parede(p_alvo['p1'], p_alvo['p2'], fator, polilinha, portas_raw, soleiras_raw)
                    if not res_tue: continue
                    px, py, vx, vy = res_tue
                    
                    nx, ny = get_inside_normal(vx, vy, px, py, centro_x, centro_y)
                    ponto_b1, ponto_b2, ponto_pt = (px - vx * 0.10, py - vy * 0.10), (px + vx * 0.10, py + vy * 0.10), (px + nx * 0.20, py + ny * 0.20)
                    
                    msp.add_lwpolyline([ponto_b1, ponto_b2, ponto_pt, ponto_b1], close=True, dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                    if is_chuveiro_ou_ac:
                        msp.add_solid([ponto_b1, ponto_b2, ponto_pt], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                    elif is_ambiente_molhado:
                        msp.add_solid([ponto_b1, (px, py), ponto_pt], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                    msp.add_text(f"{pot_tue_val}W", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.12, 'color': 2, 'insert': (px + nx * 0.35, py + ny * 0.35)})

            # TOMADAS TUG
            qtd_tugs = int(row_data.get('TUGs (Qtd)', row_data.get('TUGs', 0)))
            if qtd_tugs > 0 and comp_total > 0:
                margem_inicial = 0.20
                comprimento_util = comp_total - (2 * margem_inicial)
                passo = (comprimento_util / qtd_tugs) if comprimento_util > 0 else (comp_total / qtd_tugs)
                inicio_offset = (margem_inicial + passo / 2) if comprimento_util > 0 else (passo / 2)

                for i in range(qtd_tugs):
                    dist_desejada = inicio_offset + (i * passo)
                    res_ponto = procurar_ponto_valido_perimetro(dist_desejada, comp_total, segmentos_crus, polilinha, portas_raw, soleiras_raw)
                    if not res_ponto: continue
                    px, py, seg_vx, seg_vy = res_ponto

                    nx, ny = get_inside_normal(seg_vx, seg_vy, px, py, centro_x, centro_y)
                    ponto_b1, ponto_b2, ponto_pt = (px - seg_vx * 0.10, py - seg_vy * 0.10), (px + seg_vx * 0.10, py + seg_vy * 0.10), (px + nx * 0.20, py + ny * 0.20)
                    
                    msp.add_lwpolyline([ponto_b1, ponto_b2, ponto_pt, ponto_b1], close=True, dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                    if is_ambiente_molhado:
                        msp.add_solid([ponto_b1, (px, py), ponto_pt], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})

        doc.saveas(tmp_in_path)
        with open(tmp_in_path, "rb") as f:
            out_bytes = f.read()
        return out_bytes
    except Exception as e:
        raise e
    finally:
        if tmp_in_path and os.path.exists(tmp_in_path):
            os.remove(tmp_in_path)
