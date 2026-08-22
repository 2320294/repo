import ezdxf
import math
import tempfile
import os

# [Manter as funções dimensionar_cargas, processar_dxf, get_ponto_perimetro, etc. como estavam]
# (Abaixo a versão ajustada da função gerar_cad_unifilar para corrigir o erro)

def gerar_cad_unifilar(dxf_bytes, dados_editados, local_qdc):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_in:
        tmp_in.write(dxf_bytes)
        tmp_in_path = tmp_in.name
    try:
        doc = ezdxf.readfile(tmp_in_path)
        msp = doc.modelspace()
        camadas = {"PROJ_ELETRICA_LUZ": 2, "PROJ_ELETRICA_QDC": 1, "PROJ_ELETRICA_TEXTO": 2, "PROJ_ELETRICA_TOMADA": 4, "PROJ_ELETRICA_INTERRUPTOR": 5}
        for n, c in camadas.items(): doc.layers.add(name=n, color=c) if n not in doc.layers else setattr(doc.layers.get(n), 'color', c)
        
        polilinhas, textos, portas, soleiras = [], [], [], []
        for entity in msp:
            tipo = entity.dxftype(); layer = str(entity.dxf.layer).upper().strip() if hasattr(entity.dxf, 'layer') else ""
            if tipo in ['LWPOLYLINE', 'POLYLINE'] and layer == 'IA_AMBIENTES':
                polilinhas.append([(p[0], p[1]) for p in entity.get_points(format='xy')])
            elif tipo in ['TEXT', 'MTEXT'] and layer == 'IA_TEXTOS':
                textos.append({'nome': (entity.text if tipo == 'MTEXT' else entity.dxf.text).strip(), 'x': entity.dxf.insert.x, 'y': entity.dxf.insert.y})
            elif layer == 'IA_PORTAS':
                # Correção: Acessar pontos das polilinhas sem buscar 'start' em LWPOLYLINE
                if tipo == 'LINE': portas.append({'p1': (entity.dxf.start.x, entity.dxf.start.y), 'p2': (entity.dxf.end.x, entity.dxf.end.y)})
                elif tipo in ['LWPOLYLINE', 'POLYLINE']:
                    pts = [(p[0], p[1]) for p in entity.get_points(format='xy')]
                    if pts: portas.append({'p1': pts[0], 'p2': pts[-1]})
            elif layer == 'IA_SOLEIRA':
                if tipo == 'LINE': soleiras.append({'p1': (entity.dxf.start.x, entity.dxf.start.y), 'p2': (entity.dxf.end.x, entity.dxf.end.y)})
                elif tipo in ['LWPOLYLINE', 'POLYLINE']:
                    pts = [(p[0], p[1]) for p in entity.get_points(format='xy')]
                    if pts: soleiras.append({'p1': pts[0], 'p2': pts[-1]})

        ambientes_processados, dict_dados = {}, {row['Ambiente']: row for row in dados_editados}
        posicoes_sw = []
        for polilinha in polilinhas:
            xs, ys = [p[0] for p in polilinha], [p[1] for p in polilinha]
            min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
            nome = next((t['nome'] for t in textos if (min_x - 0.5) <= t['x'] <= (max_x + 0.5) and (min_y - 0.5) <= t['y'] <= (max_y + 0.5)), None)
            if not nome or nome not in dict_dados: continue
            
            geom = {'centro_x': (min_x+max_x)/2, 'centro_y': (min_y+max_y)/2, 'segs': [], 'walls': []}
            poly = list(polilinha); poly.append(poly[0])
            comp_total = 0
            for i in range(len(poly)-1):
                dst = math.hypot(poly[i+1][0]-poly[i][0], poly[i+1][1]-poly[i][1])
                if dst > 0.1:
                    geom['segs'].append((poly[i], poly[i+1], dst))
                    geom['walls'].append({'p1': poly[i], 'p2': poly[i+1], 'length': dst})
                    comp_total += dst

            sol_encontrada = None
            for sol in soleiras:
                mx, my = (sol['p1'][0]+sol['p2'][0])/2, (sol['p1'][1]+sol['p2'][1])/2
                if (min_x-0.5)<=mx<=(max_x+0.5) and (min_y-0.5)<=my<=(max_y+0.5):
                    sol_encontrada = sol
                    break

            if dict_dados[nome]['Qtd Ilum.'] > 0:
                msp.add_circle(center=(geom['centro_x'], geom['centro_y']), radius=0.25, dxfattribs={'layer': 'PROJ_ELETRICA_LUZ'})
                msp.add_text(f"{dict_dados[nome]['Pot. Unit. Ilum (VA)']}VA", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.15, 'insert': (geom['centro_x'] + 0.3, geom['centro_y'] - 0.07)})
                msp.add_text("a", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.15, 'color': 2, 'insert': (geom['centro_x'] + 0.3, geom['centro_y'] + 0.15)})
                
                sw_x, sw_y = (sol_encontrada['p1'][0]+sol_encontrada['p2'][0])/2, (sol_encontrada['p1'][1]+sol_encontrada['p2'][1])/2 if sol_encontrada else (geom['centro_x'], min_y+0.15)
                for p in posicoes_sw:
                    if math.hypot(sw_x - p[0], sw_y - p[1]) < 0.2: sw_y += 0.2
                posicoes_sw.append((sw_x, sw_y))
                msp.add_circle(center=(sw_x, sw_y), radius=0.12, dxfattribs={'layer': 'PROJ_ELETRICA_INTERRUPTOR'})
                msp.add_text("a", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.12, 'color': 5, 'insert': (sw_x+0.15, sw_y+0.15)})

            if nome == local_qdc.replace(" (recomendado)", "") and "coz" not in nome.lower() and "banh" not in nome.lower():
                pts = [(geom['centro_x']-0.2, max_y), (geom['centro_x']+0.2, max_y), (geom['centro_x']+0.2, max_y+0.15), (geom['centro_x']-0.2, max_y+0.15)]
                msp.add_lwpolyline(pts+[pts[0]], dxfattribs={'layer': 'PROJ_ELETRICA_QDC'}); msp.add_solid(pts[:3], dxfattribs={'layer': 'PROJ_ELETRICA_QDC'})

            is_ac = "ar" in str(dict_dados[nome]['Equipamento TUE']).lower()
            if is_ac and int(dict_dados[nome]['Qtd TUE']) > 0 and geom['walls']:
                p = min(geom['walls'], key=lambda w: w['length'])
                px, py = (p['p1'][0]+p['p2'][0])/2, (p['p1'][1]+p['p2'][1])/2
                msp.add_solid([(px-0.1, py), (px+0.1, py), (px, py+0.25)], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                msp.add_lwpolyline([(px-0.1, py), (px+0.1, py), (px, py+0.25), (px-0.1, py)], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                msp.add_text(f"{int(dict_dados[nome]['Pot. Unit. TUE (VA)'])}W", dxfattribs={'layer': 'PROJ_ELETRICA_TEXTO', 'height': 0.12, 'insert': (px+0.2, py+0.1)})
            
            for i in range(int(dict_dados[nome]['TUGs (Qtd)']) + (int(dict_dados[nome]['Qtd TUE']) if not is_ac else 0)):
                px, py, _, _ = get_ponto_perimetro((comp_total/(int(dict_dados[nome]['TUGs (Qtd)']) + int(dict_dados[nome]['Qtd TUE']))) * i, geom['segs'])
                msp.add_lwpolyline([(px-0.1, py), (px+0.1, py), (px, py+0.2), (px-0.1, py)], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})
                if any(x in nome.lower() for x in ["coz", "serv", "banh", "lav", "sanit", "wc", "as"]):
                    msp.add_solid([(px-0.1, py), (px+0.1, py), (px, py+0.2)], dxfattribs={'layer': 'PROJ_ELETRICA_TOMADA'})

        doc.saveas(tmp_in_path); 
        with open(tmp_in_path, "rb") as f: out_bytes = f.read()
        return out_bytes
    finally: os.remove(tmp_in_path)
