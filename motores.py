# --- DIAGNÓSTICO DIRETO DAS EXTREMIDADES DA SOLEIRA ---
            if logical_walls:
                maior_parede = max(logical_walls, key=lambda w: w['length'])
                pt1, pt2 = maior_parede['p1'], maior_parede['p2']
                
                # Procura soleiras que tenham qualquer um dos pontos próximos à maior parede
                soleira_encontrada = None
                ponto_soleira_na_parede = None
                
                for sol in unique_soleiras:
                    # Verifica a distância de ambas as pontas da soleira (p1 e p2) até a reta da maior parede
                    d_sol_p1 = point_seg_dist(sol['p1'][0], sol['p1'][1], pt1, pt2)
                    d_sol_p2 = point_seg_dist(sol['p2'][0], sol['p2'][1], pt1, pt2)
                    
                    if d_sol_p1 < 0.3 or d_sol_p2 < 0.3:
                        soleira_encontrada = sol
                        # Pega exatamente a ponta da soleira que está encostada/mais próxima da parede
                        ponto_soleira_na_parede = sol['p1'] if d_sol_p1 < d_sol_p2 else sol['p2']
                        break
                
                if soleira_encontrada is not None and ponto_soleira_na_parede is not None:
                    # Compara qual canto da parede (pt1 ou pt2) está mais perto dessa ponta da soleira
                    d_canto1 = math.hypot(ponto_soleira_na_parede[0] - pt1[0], ponto_soleira_na_parede[1] - pt1[1])
                    d_canto2 = math.hypot(ponto_soleira_na_parede[0] - pt2[0], ponto_soleira_na_parede[1] - pt2[1])
                    canto_alvo = pt1 if d_canto1 < d_canto2 else pt2
                    
                    # Desenha a linha magenta EXATAMENTE da ponta da soleira até o canto correspondente da parede!
                    msp.add_line(ponto_soleira_na_parede, canto_alvo, dxfattribs={'layer': 'PROJ_ELETRICA_DEBUG'})
                else:
                    # Fallback apenas se nenhuma soleira encostar na maior parede
                    msp.add_line(pt1, pt2, dxfattribs={'layer': 'PROJ_ELETRICA_DEBUG'})
