"""Regras e validação do perfil CPFL GED-13, preservadas da versão anterior.

Interface administrativa, persistência e motor genérico de demanda permanecem
compartilhados. Este módulo não ativa perfis nem modifica projetos.
"""

def _numero(txt):
    txt = str(txt or "").strip().replace(".", "").replace(",", ".") if "," in str(txt or "") else str(txt or "").strip()
    if not txt:
        return None
    try:
        return float(txt)
    except Exception:
        return None


def _regras_base(regras=None):
    r = regras if isinstance(regras, dict) else {}
    return {
        "schema": "autoeletrica.perfil_normativo.v2",
        "tipo_instalacao": r.get("tipo_instalacao", "Residencial individual"),
        "fornecimento": dict(r.get("fornecimento") or {}),
        "demanda": dict(r.get("demanda") or {}),
        "observacoes": r.get("observacoes", ""),
        "fonte_conferida": bool(r.get("fonte_conferida", False)),
    }


def _sincronizar_regras_ged13_residencial(regras=None):
    """Materializa no JSON persistido as regras oficiais GED-13 usadas pelo editor.

    Rev.200: perfis criados antes das revisões 192–196 podiam exibir as tabelas
    pela interface sem tê-las gravadas em ``regras.demanda``. Esta função cria
    a representação canônica que também é consumida pelo validador.
    """
    r = _regras_base(regras)
    if r.get("tipo_instalacao") != "Residencial individual":
        return r

    # Rev.201 — materializa também os parâmetros de fornecimento no mesmo
    # schema canônico consumido pelo validador. Nas revisões anteriores esses
    # valores podiam aparecer nos widgets do editor, mas não existir no JSON
    # persistido de perfis antigos, resultando em ``None`` nos quatro testes.
    f = dict(r.get("fornecimento") or {})
    if f.get("tensao_fase_neutro_v") in (None, ""):
        f["tensao_fase_neutro_v"] = 127.0
    if f.get("tensao_fase_fase_v") in (None, ""):
        f["tensao_fase_fase_v"] = 220.0
    if f.get("limite_potencia_instalada_kw") in (None, ""):
        legado = f.get("limite_fornecimento_kva")
        f["limite_potencia_instalada_kw"] = float(legado) if legado not in (None, "") else 75.0
    modalidades = f.get("modalidades")
    if not isinstance(modalidades, list) or not modalidades:
        f["modalidades"] = ["Monofásico", "Bifásico", "Trifásico"]
    # GED-13 v46.0, itens 6.4.1–6.4.3 e Tabelas 1A/1B: classe 127/220 V.
    # Somente completa o perfil CPFL GED-13 sincronizado pelo chamador quando
    # nenhuma faixa foi gravada; preserva qualquer cadastro parcial ou existente.
    if (not f.get("faixas_modalidade_kw")
            and float(f.get("tensao_fase_neutro_v") or 0) == 127
            and float(f.get("tensao_fase_fase_v") or 0) == 220):
        f["faixas_modalidade_kw"] = [
            {"modalidade": "Monofásico", "min_kw": 0.0, "max_kw": 12.0,
             "inclui_min": True, "inclui_max": True},
            {"modalidade": "Bifásico", "min_kw": 12.0, "max_kw": 25.0,
             "inclui_min": False, "inclui_max": True},
            {"modalidade": "Trifásico", "min_kw": 25.0, "max_kw": 75.0,
             "inclui_min": False, "inclui_max": True},
        ]
    r["fornecimento"] = f

    d = dict(r.get("demanda") or {})
    d["iluminacao_tug"] = {
        "metodo":"Tabela por faixas","tabela_id":"GED13_TABELA_3","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":1.0,"variavel":"carga_instalada_iluminacao_tug_kw",
        "faixas":[
            {"min_kw":0.0,"max_kw":1.0,"fator":0.86},{"min_kw":1.0,"max_kw":2.0,"fator":0.75},{"min_kw":2.0,"max_kw":3.0,"fator":0.66},{"min_kw":3.0,"max_kw":4.0,"fator":0.59},{"min_kw":4.0,"max_kw":5.0,"fator":0.52},{"min_kw":5.0,"max_kw":6.0,"fator":0.45},{"min_kw":6.0,"max_kw":7.0,"fator":0.40},{"min_kw":7.0,"max_kw":8.0,"fator":0.35},{"min_kw":8.0,"max_kw":9.0,"fator":0.31},{"min_kw":9.0,"max_kw":10.0,"fator":0.27},{"min_kw":10.0,"max_kw":None,"fator":0.24}
        ]}
    fatores4=[(1,1.00),(2,1.00),(3,0.84),(4,0.76),(5,0.70),(6,0.65),(7,0.60),(8,0.57),(9,0.54),(10,0.52),(11,0.49),(12,0.48),(13,0.46),(14,0.45),(15,0.44),(16,0.43),(17,0.42),(18,0.41),(19,0.40),(20,0.40),(21,0.39),(22,0.39),(23,0.39),(24,0.38),(25,0.38)]
    d["chuveiros"]={"metodo":"Tabela por quantidade","tabela_id":"GED13_TABELA_4","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","variavel":"numero_aparelhos_chuveiros_torneiras_aquecedores_passagem_ferros","fatores_por_quantidade":[{"quantidade":n,"fator":fd} for n,fd in fatores4],"acima_de_25":{"fator":0.38}}
    d["boiler"]={"metodo":"Tabela por quantidade","tabela_id":"GED13_TABELA_5","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":1.0,"variavel":"numero_aquecedores_centrais_ou_acumulacao","fatores_por_quantidade":[{"quantidade":1,"fator":1.00},{"quantidade":2,"fator":0.72},{"quantidade":3,"fator":0.62}],"acima_de_3":{"fator":0.62}}
    d["eletrodomesticos"]={"metodo":"Tabela por quantidade","tabela_id":"GED13_TABELA_6","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":1.0,"variavel":"numero_secadoras_fornos_lava_loucas_microondas","faixas_quantidade":[{"min":1,"max":1,"fator":1.00},{"min":2,"max":4,"fator":0.70},{"min":5,"max":6,"fator":0.60},{"min":7,"max":8,"fator":0.50},{"min":9,"max":None,"fator":0.50}]}
    d["fogoes"]={"metodo":"Tabela por quantidade","tabela_id":"GED13_TABELA_7","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":1.0,"variavel":"numero_fogoes_eletricos","faixas_quantidade":[{"min":1,"max":1,"fator":1.00},{"min":2,"max":2,"fator":0.60},{"min":3,"max":3,"fator":0.48},{"min":4,"max":4,"fator":0.40},{"min":5,"max":5,"fator":0.37},{"min":6,"max":6,"fator":0.35},{"min":7,"max":7,"fator":0.33},{"min":8,"max":8,"fator":0.32},{"min":9,"max":9,"fator":0.31},{"min":10,"max":11,"fator":0.30},{"min":12,"max":15,"fator":0.28},{"min":16,"max":20,"fator":0.26},{"min":21,"max":25,"fator":0.26},{"min":26,"max":None,"fator":0.26}]}
    aparelhos=[(7100,1100,900),(8500,1550,1300),(10000,1650,1400),(12000,1900,1600),(14000,2100,1900),(18000,2860,2600),(21000,3080,2800),(30000,4000,3600)]
    d["ar_condicionado"]={"metodo":"Regra específica","tabela_id":"GED13_TABELAS_8_9","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","uso_residencial_fator_demanda":1.0,"unidade_central_fator_demanda":1.0,"tabela_potencias":[{"btu_h":b,"potencia_va":va,"potencia_w":w} for b,va,w in aparelhos],"tabela_9_comercial":[{"min":1,"max":10,"fator":1.00},{"min":11,"max":20,"fator":0.90},{"min":21,"max":30,"fator":0.82},{"min":31,"max":40,"fator":0.80},{"min":41,"max":50,"fator":0.77},{"min":51,"max":75,"fator":0.75},{"min":76,"max":100,"fator":0.75},{"min":101,"max":None,"fator":0.75}]}
    d["motores"]={"metodo":"Regra por ordem de potência","tabela_id":"GED13_TABELA_10","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fatores_ordem":{"primeiro":1.0,"segundo":0.9,"terceiro_quarto_quinto":0.8,"demais":0.7},"regra_motores_iguais":True,"regra_simultaneos_agrupar":True}
    d["equipamentos_especiais"]={"metodo":"Regra por tipo e ordem de potência","tabela_id":"GED13_TABELA_11","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":0.75,"regras":{"solda_arco_galvanizacao":{"primeiro":1.0,"segundo":0.7,"terceiro":0.4,"demais":0.3},"solda_resistencia":{"maior":1.0,"demais":0.6},"raios_x":{"maior":1.0,"demais":0.7}}}
    d["hidromassagem"]={"metodo":"GED-13 / Tabela 10 (motores)","tabela_id":"GED13_TABELA_10_HIDROMASSAGEM","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":1.0,"usar_regra_motores_tabela_10":True}
    d["demais_tues"]={"metodo":"Sem regra genérica","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","regra":"classificar_por_categoria_normativa","fator_generico":None}
    r["demanda"] = d
    return r


def _quase_igual(a, b, tol=1e-9):
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return False


def _validar_perfil_ged13(regras):
    """Valida estrutura e casos matemáticos do perfil GED-13 residencial.

    Não altera cálculo de projeto. Serve como trava administrativa antes de
    permitir VALIDADO/ATIVO.
    """
    resultados = []

    def teste(grupo, caso, esperado, obtido, ok=None):
        passou = _quase_igual(obtido, esperado, 1e-8) if ok is None else bool(ok)
        resultados.append({
            "Grupo": grupo,
            "Caso de teste": caso,
            "Esperado": esperado,
            "Obtido": obtido,
            "Status": "PASSOU" if passou else "FALHOU",
        })
        return passou

    if not isinstance(regras, dict):
        teste("Perfil", "Estrutura de regras", "dicionário válido", type(regras).__name__, False)
        return False, resultados

    f = regras.get("fornecimento") or {}
    teste("Fornecimento", "Tensão fase-neutro", 127.0, f.get("tensao_fase_neutro_v"))
    teste("Fornecimento", "Tensão fase-fase", 220.0, f.get("tensao_fase_fase_v"))
    teste("Fornecimento", "Limite de potência instalada", 75.0, f.get("limite_potencia_instalada_kw"))
    mods = set(f.get("modalidades") or [])
    teste("Fornecimento", "Modalidades M/B/T", "Monofásico, Bifásico, Trifásico", ", ".join(sorted(mods)), mods == {"Monofásico", "Bifásico", "Trifásico"})
    faixas_fornecimento = f.get("faixas_modalidade_kw") or []
    faixas_por_modalidade = {
        faixa.get("modalidade"): faixa for faixa in faixas_fornecimento
        if isinstance(faixa, dict)
    } if isinstance(faixas_fornecimento, list) else {}
    anterior = 0.0
    for modalidade in ("Monofásico", "Bifásico", "Trifásico"):
        faixa = faixas_por_modalidade.get(modalidade) or {}
        # _numero(0.0) trata zero como vazio; 0 kW é o início válido
        # da primeira faixa e deve permanecer numérico na auditoria.
        minimo = _numero(str(faixa["min_kw"])) if faixa.get("min_kw") is not None else None
        maximo = _numero(str(faixa["max_kw"])) if faixa.get("max_kw") is not None else None
        valido = (minimo is not None and maximo is not None
                  and abs(minimo - anterior) < 1e-8 and maximo > minimo)
        teste("Fornecimento", f"Faixa {modalidade} (kW)",
              "limites cadastrados e crescentes", faixa or "ausente", valido)
        if valido:
            anterior = maximo

    d = regras.get("demanda") or {}

    # Tabela 3 — caso documental já usado no cadastro: 4,2 kW x 0,52 = 2,184 kVA (FP=1).
    t3 = d.get("iluminacao_tug") or {}
    faixas = t3.get("faixas") or []
    fator_42 = next((x.get("fator") for x in faixas if _quase_igual(x.get("min_kw"), 4.0) and _quase_igual(x.get("max_kw"), 5.0)), None)
    teste("Tabela 3", "Fator para 4,2 kW", 0.52, fator_42)
    teste("Tabela 3", "Demanda para 4,2 kW", 2.184, 4.2 * float(fator_42 or 0))
    teste("Tabela 3", "Faixa acima de 10 kW", 0.24, next((x.get("fator") for x in faixas if _quase_igual(x.get("min_kw"), 10.0) and x.get("max_kw") is None), None))

    # Tabela 4
    t4 = d.get("chuveiros") or {}
    q4 = {int(x.get("quantidade")): x.get("fator") for x in (t4.get("fatores_por_quantidade") or []) if x.get("quantidade") is not None}
    teste("Tabela 4", "3 aparelhos", 0.84, q4.get(3))
    teste("Tabela 4", "25 aparelhos", 0.38, q4.get(25))
    teste("Tabela 4", "Acima de 25", 0.38, (t4.get("acima_de_25") or {}).get("fator"))

    # Tabela 5
    t5 = d.get("boiler") or {}
    q5 = {int(x.get("quantidade")): x.get("fator") for x in (t5.get("fatores_por_quantidade") or []) if x.get("quantidade") is not None}
    teste("Tabela 5", "2 boilers", 0.72, q5.get(2))
    teste("Tabela 5", "Acima de 3", 0.62, (t5.get("acima_de_3") or {}).get("fator"))

    # Tabela 6
    t6 = d.get("eletrodomesticos") or {}
    fq6 = t6.get("faixas_quantidade") or []
    def fator_faixas(lista, n):
        for x in lista:
            mn, mx = x.get("min"), x.get("max")
            if mn is not None and n >= mn and (mx is None or n <= mx):
                return x.get("fator")
        return None
    teste("Tabela 6", "4 aparelhos", 0.70, fator_faixas(fq6, 4))
    teste("Tabela 6", "6 aparelhos", 0.60, fator_faixas(fq6, 6))
    teste("Tabela 6", "9 aparelhos", 0.50, fator_faixas(fq6, 9))

    # Tabela 7
    t7 = d.get("fogoes") or {}
    fq7 = t7.get("faixas_quantidade") or []
    teste("Tabela 7", "3 fogões", 0.48, fator_faixas(fq7, 3))
    teste("Tabela 7", "10 fogões", 0.30, fator_faixas(fq7, 10))
    teste("Tabela 7", "26 fogões", 0.26, fator_faixas(fq7, 26))

    # Tabelas 8/9 — no perfil residencial a demanda dos aparelhos é integral.
    t89 = d.get("ar_condicionado") or {}
    teste("Tabelas 8/9", "FD residencial", 1.00, t89.get("uso_residencial_fator_demanda"))
    teste("Tabelas 8/9", "Unidade central", 1.00, t89.get("unidade_central_fator_demanda"))
    pot = {int(x.get("btu_h")): x for x in (t89.get("tabela_potencias") or []) if x.get("btu_h") is not None}
    teste("Tabela 8", "12.000 BTU/h — potência VA", 1900.0, (pot.get(12000) or {}).get("potencia_va"))

    # Tabela 10 — valida fatores e um caso matemático de ordenação.
    t10 = d.get("motores") or {}
    fo = t10.get("fatores_ordem") or {}
    teste("Tabela 10", "1º maior motor", 1.00, fo.get("primeiro"))
    teste("Tabela 10", "2º maior motor", 0.90, fo.get("segundo"))
    teste("Tabela 10", "3º ao 5º", 0.80, fo.get("terceiro_quarto_quinto"))
    teste("Tabela 10", "Demais", 0.70, fo.get("demais"))
    motores = [5.0, 3.0, 2.0, 1.0, 0.5, 0.25]
    demanda_motores = motores[0]*float(fo.get("primeiro") or 0) + motores[1]*float(fo.get("segundo") or 0) + sum(motores[2:5])*float(fo.get("terceiro_quarto_quinto") or 0) + sum(motores[5:])*float(fo.get("demais") or 0)
    teste("Tabela 10", "Caso 6 motores [5;3;2;1;0,5;0,25]", 10.675, demanda_motores)

    # Tabela 11
    t11 = d.get("equipamentos_especiais") or {}
    re = t11.get("regras") or {}
    solda = re.get("solda_arco_galvanizacao") or {}
    teste("Tabela 11", "Solda a arco — 1º maior", 1.00, solda.get("primeiro"))
    teste("Tabela 11", "Solda a arco — 2º maior", 0.70, solda.get("segundo"))
    teste("Tabela 11", "FP equipamentos especiais", 0.75, t11.get("fator_potencia"))

    # Hidromassagem e TUEs sem regra genérica.
    hid = d.get("hidromassagem") or {}
    teste("Hidromassagem", "Reutiliza Tabela 10", True, hid.get("usar_regra_motores_tabela_10"), hid.get("usar_regra_motores_tabela_10") is True)
    outros = d.get("demais_tues") or {}
    teste("Demais TUEs", "Sem fator genérico inventado", None, outros.get("fator_generico"), "fator_generico" in outros and outros.get("fator_generico") is None)

    # Metadados mínimos de rastreabilidade para todas as categorias normativas automáticas.
    for chave in ["iluminacao_tug", "chuveiros", "boiler", "eletrodomesticos", "fogoes", "ar_condicionado", "motores", "equipamentos_especiais", "hidromassagem"]:
        regra = d.get(chave) or {}
        ok_meta = regra.get("documento") == "GED-13" and regra.get("versao_documento") == "46.0" and regra.get("publicacao") == "19/03/2026"
        teste("Rastreabilidade", chave, "GED-13 v46.0 · 19/03/2026", f"{regra.get('documento')} v{regra.get('versao_documento')} · {regra.get('publicacao')}", ok_meta)

    passou = bool(resultados) and all(x["Status"] == "PASSOU" for x in resultados)
    return passou, resultados


def _resumo_auditoria_ged13(regras):
    passou, resultados = _validar_perfil_ged13(regras)
    demanda = (regras or {}).get("demanda") or {}
    categorias = ["iluminacao_tug", "chuveiros", "boiler", "eletrodomesticos", "fogoes", "ar_condicionado", "motores", "equipamentos_especiais", "hidromassagem"]
    tabelas_ok = 0
    for chave in categorias:
        reg = demanda.get(chave) or {}
        if reg.get("documento") == "GED-13" and reg.get("versao_documento") == "46.0" and reg.get("publicacao") == "19/03/2026":
            tabelas_ok += 1
    total = len(resultados)
    aprovados = sum(1 for x in resultados if x.get("Status") == "PASSOU")
    pendencias = total - aprovados
    return passou, resultados, tabelas_ok, len(categorias), aprovados, total, pendencias




def fator_tabela3_limites_cpfl(regra, carga_kw):
    """Tabela 3 GED-13: limite inferior exclusivo e superior inclusivo."""
    carga = float(carga_kw)
    if carga == 0:
        return 0.0
    for faixa in regra.get("faixas", []) or []:
        minimo = float(faixa.get("min_kw", 0) or 0)
        maximo = faixa.get("max_kw")
        if carga > minimo and (maximo in (None, "") or carga <= float(maximo)):
            return float(faixa.get("fator", 0) or 0)
    return None


def conferir_entrada_trifasica_cpfl(perfil, detalhes, tipo, tensao):
    import math
    """Consulta documental independente; não altera DG nem alimentador."""
    import re
    documento = str(perfil.get("documento", "")).upper()
    if "CPFL" not in str(perfil.get("concessionaria", "")).upper() or not re.search(r"\bGED\s*[-–—]?\s*13\b", documento):
        return None
    if tipo != "Trifásico" or tensao != "127/220 V":
        return None
    fp_unidade = {"GED13_TABELA_3", "GED13_TABELA_4", "GED13_TABELA_5", "GED13_TABELA_6", "GED13_TABELA_6_CRITERIO_FUNCAO_SECAGEM", "GED13_TABELA_7", "GED13_TABELA_10_HIDROMASSAGEM"}
    parcial = 0.0
    pendencias = []
    for item in detalhes:
        watts = float(item.get("demanda_w", 0) or 0)
        if not math.isfinite(watts) or watts < 0:
            pendencias.append("Parcela de demanda inválida.")
            continue
        if watts == 0:
            continue
        if item.get("tabela_id") in fp_unidade:
            parcial += watts / 1000.0
        else:
            pendencias.append(str(item.get("categoria") or "Carga") + ": confirmar potência aparente (VA) ou fator de potência e regra aplicável.")
    resultado = {"status": "pendente", "demanda_parcial_kva": parcial, "demanda_kva": None, "categoria": None, "pendencias": pendencias, "fonte": "GED-13 Rev.46.0, itens 6.22.1 e Tabela 1C", "aprovacao_automatica": False}
    if pendencias or not detalhes or parcial <= 0:
        if not pendencias:
            resultado["pendencias"] = ["Demanda aparente total indisponível."]
        return resultado
    resultado["demanda_kva"] = parcial
    limites = [(23, "C1", 63, 16, 10, 40), (30, "C2", 80, 25, 10, 40), (38, "C3", 100, 35, 10, 40), (47, "C4", 125, 50, 16, 50), (57, "C5", 150, 70, 25, 60), (76, "C6", 200, 95, 35, 60)]
    for maximo, categoria, disjuntor, cobre, terra, eletroduto in limites:
        if parcial <= maximo:
            resultado.update(status="referencia_documental", categoria=categoria, disjuntor_padrao_a=disjuntor, ramal_entrada_cobre_mm2=cobre, aterramento_padrao_mm2=terra, eletroduto_padrao_mm=eletroduto)
            return resultado
    resultado["pendencias"] = ["Demanda acima da faixa da Tabela 1C cadastrada."]
    return resultado
