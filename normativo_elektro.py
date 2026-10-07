"""Regras e auditoria Elektro consolidadas. Sem liberação automática de DG/alimentador."""


# ========================================================================
# municipios_elektro
# ========================================================================
"""Municípios da área de concessão Neoenergia Elektro.
Fonte: relatório oficial Neoenergia Elektro 13/02/2026, tabela 1 (códigos IBGE).
Nomes conferidos pela API de localidades do IBGE.
"""
municipios_MUNICIPIOS_ELEKTRO = {'SP': ['Aguaí', 'Américo de Campos', 'Andradina', 'Angatuba', 'Anhembi', 'Anhumas', "Aparecida d'Oeste", 'Apiaí', 'Arapeí', 'Araras', 'Areias', 'Artur Nogueira', 'Arujá', 'Aspásia', 'Atibaia', 'Auriflama', 'Bananal', 'Barra do Chapéu', 'Barra do Turvo', 'Barão de Antonina', 'Bertioga', 'Bom Jesus dos Perdões', 'Bom Sucesso de Itararé', 'Buri', 'Buritama', 'Cabreúva', 'Caieiras', 'Cajati', 'Campina do Monte Alegre', 'Campos do Jordão', 'Cananéia', 'Capão Bonito', 'Cardoso', 'Castilho', 'Cerquilho', 'Cesário Lange', 'Conchal', 'Conchas', 'Cordeirópolis', 'Coronel Macedo', 'Corumbataí', 'Cosmorama', 'Cunha', 'Dirce Reis', 'Dolcinópolis', 'Dracena', 'Eldorado', 'Engenheiro Coelho', 'Estiva Gerbi', "Estrela d'Oeste", 'Estrela do Norte', 'Euclides da Cunha Paulista', 'Fartura', 'Fernandópolis', 'Flora Rica', 'Floreal', 'Flórida Paulista', 'Francisco Morato', 'Franco da Rocha', 'Gastão Vidigal', 'General Salgado', 'Guapiara', "Guarani d'Oeste", 'Guaraçaí', 'Guarujá', 'Guzolândia', 'Igaratá', 'Iguape', 'Ilha Comprida', 'Ilha Solteira', 'Ilhabela', 'Indiaporã', 'Ipeúna', 'Iporanga', 'Iracemápolis', 'Irapuru', 'Itaberá', 'Itanhaém', 'Itaoca', 'Itapeva', 'Itapirapuã Paulista', 'Itaporanga', 'Itapura', 'Itararé', 'Itariri', 'Itirapina', 'Jacupiranga', 'Jales', 'Jarinu', 'Joanópolis', 'Jumirim', 'Junqueirópolis', 'Juquiá', 'Lagoinha', 'Laranjal Paulista', 'Lavrinhas', 'Lavínia', 'Leme', 'Limeira', 'Lourdes', 'Macaubal', 'Macedônia', 'Magda', 'Mairiporã', 'Marabá Paulista', 'Marinópolis', 'Mariápolis', 'Meridiano', 'Mesópolis', 'Mira Estrela', 'Miracatu', 'Mirandópolis', 'Mirante do Paranapanema', 'Mogi Guaçu', 'Mogi Mirim', 'Mongaguá', 'Monte Castelo', 'Monções', 'Murutinga do Sul', 'Narandiba', 'Natividade da Serra', 'Nazaré Paulista', 'Nhandeara', 'Nipoã', 'Nova Campina', 'Nova Canaã Paulista', 'Nova Castilho', 'Nova Guataporanga', 'Nova Independência', 'Nova Luzitânia', 'Orindiúva', 'Ouro Verde', 'Ouroeste', 'Pacaembu', "Palmeira d'Oeste", 'Panorama', 'Paraibuna', 'Paranapuã', 'Pariquera-Açu', 'Parisi', 'Paulicéia', 'Paulo de Faria', 'Pedranópolis', 'Pedro de Toledo', 'Pereira Barreto', 'Pereiras', 'Peruíbe', 'Piedade', 'Pilar do Sul', 'Piquete', 'Piracaia', 'Pirapozinho', 'Pirassununga', 'Planalto', 'Pontalinda', 'Pontes Gestal', 'Populina', 'Porangaba', 'Porto Ferreira', 'Praia Grande', 'Quadra', 'Queluz', 'Redenção da Serra', 'Registro', 'Ribeira', 'Ribeirão Branco', 'Ribeirão Grande', 'Rio Claro', 'Riolândia', 'Riversul', 'Rosana', 'Rubinéia', 'Sandovalina', 'Santa Albertina', "Santa Clara d'Oeste", 'Santa Cruz da Conceição', 'Santa Cruz das Palmeiras', 'Santa Fé do Sul', 'Santa Gertrudes', 'Santa Isabel', 'Santa Mercedes', "Santa Rita d'Oeste", 'Santa Rita do Passa Quatro', 'Santa Salete', 'Santana da Ponte Pensa', 'Santo Antônio de Posse', 'Santo Antônio do Pinhal', 'Sebastianópolis do Sul', 'Sete Barras', 'Silveiras', 'Sud Mennucci', 'Suzanápolis', 'São Bento do Sapucaí', 'São Francisco', 'São José do Barreiro', 'São João da Boa Vista', 'São João das Duas Pontes', 'São João de Iracema', "São João do Pau d'Alho", 'São Luiz do Paraitinga', 'Taciba', 'Tambaú', 'Tapiraí', 'Taquarivaí', 'Tarabai', 'Tatuí', 'Teodoro Sampaio', 'Tietê', 'Torre de Pedra', 'Três Fronteiras', 'Tupi Paulista', 'Turiúba', 'Turmalina', 'Ubatuba', 'União Paulista', 'Urânia', 'Valentim Gentil', 'Vargem Grande do Sul', 'Vitória Brasil', 'Votuporanga', 'Zacarias', 'Águas da Prata', 'Álvares Florence'], 'MS': ['Anaurilândia', 'Brasilândia', 'Santa Rita do Pardo', 'Selvíria', 'Três Lagoas']}


# ========================================================================
# neoenergia_elektro
# ========================================================================
"""Preparação conservadora do perfil DIS-NOR-030 Rev. 07 da Elektro.

Somente dados de fornecimento documentalmente inequívocos. Demandas e
dimensionamento de entrada exigem auditoria própria antes da ativação.
"""

from copy import deepcopy
import math

perfil_DOCUMENTO = "DIS-NOR-030"
perfil_REVISAO = "07"
perfil_MUNICIPIO_TENSAO_ESPECIAL = "São João da Boa Vista"
perfil_FAIXAS_CONFERENCIA_KW = ((10.0, 11.0), (13.0, 18.0))


def perfil_eh_perfil_elektro(perfil):
    return (str((perfil or {}).get("concessionaria") or "").strip().casefold() == "neoenergia elektro"
            and str((perfil or {}).get("documento") or "").strip().upper() == perfil_DOCUMENTO
            and str((perfil or {}).get("revisao") or "").strip() == perfil_REVISAO)


def perfil_motivo_conferencia(potencia_w, perfil):
    if not perfil_eh_perfil_elektro(perfil):
        return ""
    try:
        watts = float(potencia_w)
    except (TypeError, ValueError):
        return "Carga instalada inválida: informar potência numérica para conferência."
    if not math.isfinite(watts) or watts <= 0:
        return "Carga instalada inválida: informar potência positiva e finita para conferência."
    kw = watts / 1000.0
    if 11.0 < kw < 11.1:
        return ("Carga instalada entre 11 e 11,1 kW: lacuna entre B0 e B1 na Tabela 3. "
                "Encaminhar à conferência técnica sem arredondamento automático.")
    for minimo, maximo in perfil_FAIXAS_CONFERENCIA_KW:
        if minimo < kw <= maximo:
            return (f"Carga instalada de {kw:.2f} kW: enquadramento da Neoenergia Elektro "
                    f"entre {minimo:g} e {maximo:g} kW requer conferência técnica. "
                    "O AutoElétrica mantém o enquadramento automático bloqueado nesta faixa "
                    "até a conferência documental da DIS-NOR-030 Rev. 07.")
    return ""


def perfil_preparar_regras(regras):
    """Preserva a demanda do rascunho; insere somente o fornecimento 220/127 V."""
    r = deepcopy(regras or {})
    r.setdefault("schema", "autoeletrica.perfil_normativo.v2")
    r.setdefault("tipo_instalacao", "Residencial individual")
    f = dict(r.get("fornecimento") or {})
    f.update({
        "tensao_fase_neutro_v": 127.0,
        "tensao_fase_fase_v": 220.0,
        "limite_potencia_instalada_kw": 75.0,
        "modalidades": ["Monofásico", "Bifásico", "Trifásico"],
        # Os intervalos com conflito ficam explicitamente sem faixa.
        "faixas_modalidade_kw": [
            {"modalidade": "Monofásico", "min_kw": 0.0, "max_kw": 10.0,
             "inclui_min": True, "inclui_max": True},
            {"modalidade": "Bifásico", "min_kw": 11.1, "max_kw": 13.0,
             "inclui_min": True, "inclui_max": True},
            {"modalidade": "Trifásico", "min_kw": 18.0, "max_kw": 75.0,
             "inclui_min": False, "inclui_max": True},
        ],
        "faixas_conferencia_tecnica_kw": [
            {"min_kw": a, "max_kw": b, "inclui_min": False, "inclui_max": True}
            for a, b in perfil_FAIXAS_CONFERENCIA_KW
        ],
        "fonte_faixas": "DIS-NOR-030 Rev. 07, itens 6.2.8 e Anexo I, Tabela 3",
        "lacunas_conferencia_tecnica_kw": [
            {"min_kw": 11.0, "max_kw": 11.1, "inclui_min": False, "inclui_max": False}
        ],
    })
    r["fornecimento"] = f
    r.setdefault("demanda", {})
    r["fonte_conferida"] = False
    return r


def perfil_preparar_tabelas_demanda(regras):
    """Transcreve tabelas do Anexo II para auditoria, sem habilitar o cálculo.

    O item 6.27 aplica a demanda a instalações trifásicas; o motor de cálculo
    atual ainda não interpreta estas tabelas nem todas as cargas da Elektro.
    """
    r = deepcopy(regras or {})
    def faixas(limites, fatores):
        return [{"ate": limite, "fator": fator} for limite, fator in zip(limites, fatores)]

    r["demanda_elektro_auditoria"] = {
        "documento": perfil_DOCUMENTO, "revisao": perfil_REVISAO,
        "fonte": "Anexo II, Tabelas 6 a 16; itens 6.27 e 6.28",
        "unidade_resultado": "kVA", "aplicacao": "instalacao_trifasica",
        "tabela_6_iluminacao_tug": {"unidade_entrada": "kW", "faixas": faixas(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, None],
            [.86, .75, .66, .59, .52, .45, .40, .35, .31, .27, .24])},
        "tabela_7_chuveiros": {"faixas": faixas(
            list(range(1, 26)) + [None],
            [1, 1, .84, .76, .70, .65, .60, .57, .54, .52, .49, .48,
             .46, .45, .44, .43, .42, .41, .40, .40, .39, .39, .39, .38, .38, .38])},
        "tabela_8_boiler": {"faixas": faixas([1, 2, 3, None], [1, .72, .62, .62])},
        "tabela_9_eletrodomesticos": {"faixas": [
            {"min": 1, "max": 1, "fator": 1}, {"min": 2, "max": 4, "fator": .70},
            {"min": 5, "max": 6, "fator": .60}, {"min": 7, "max": None, "fator": .50}]},
        "tabela_10_fogoes": {"faixas": faixas(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 15, None],
            [1, .60, .48, .40, .37, .35, .33, .32, .31, .30, .28, .26])},
        "tabela_11_ar_condicionado": {"potencias": [
            {"btu_h": b, "va": va, "w": w} for b, va, w in [
                (7500, 1100, 900), (9000, 1550, 1300), (10000, 1650, 1400),
                (12000, 1900, 1600), (15000, 2100, 1900), (18000, 2860, 2600),
                (21000, 3080, 2800), (30000, 4000, 3800), (41000, 5500, 5000),
                (60000, 9000, 7500)]], "preferir_placa": True},
        "tabela_12_ar_condicionado": {"ate_quantidade": [10, 20, 30, 40, 50, 75, 100, None],
            "residencial": [1, .86, .80, .78, .75, .70, .65, .60],
            "comercial": [1, .90, .82, .80, .77, .75, .75, .75],
            "unidade_central": 1},
        "tabela_13_recarga": {"faixas": faixas([10, 20, 30, 40, 50, None],
            [1, .90, .82, .80, .77, .75])},
        "tabela_14_motores": {"maior": 1, "demais": .50,
            "partida_simultanea_agrupar": True},
        "tabela_15_especiais": {"maior": 1, "demais": .60},
        "tabela_16_bombas_hidromassagem": {"faixas": faixas(
            [1, 2, 3, None], [1, .56, .47, .39])},
        "pendencias": [
            "Integrar motor de demanda exclusivo, FP e classificacao de cargas por item 6.27.",
            "Conferir divergencia do item 6.27.5 para fogoes eletricos frente a Tabela 10.",
            "Validar alimentador trifasico e casos de tensao local com a distribuidora."],
    }
    r["fonte_conferida"] = False
    return r


def perfil_auditar_tabelas_demanda(regras):
    """Checa independentemente marcadores que divergem do perfil CPFL."""
    d = (regras or {}).get("demanda_elektro_auditoria") or {}
    if d.get("documento") != perfil_DOCUMENTO or d.get("revisao") != perfil_REVISAO:
        return False
    try:
        return (d["tabela_6_iluminacao_tug"]["faixas"][-1]["fator"] == .24
                and d["tabela_7_chuveiros"]["faixas"][6]["fator"] == .60
                and d["tabela_9_eletrodomesticos"]["faixas"][1]["fator"] == .70
                and d["tabela_10_fogoes"]["faixas"][-1]["fator"] == .26
                and d["tabela_11_ar_condicionado"]["potencias"][0]["va"] == 1100
                and d["tabela_12_ar_condicionado"]["residencial"][1] == .86
                and d["tabela_13_recarga"]["faixas"][-1]["fator"] == .75
                and d["tabela_14_motores"]["demais"] == .50
                and d["tabela_15_especiais"]["demais"] == .60
                and d["tabela_16_bombas_hidromassagem"]["faixas"][-1]["fator"] == .39)
    except (KeyError, IndexError, TypeError):
        return False


# ========================================================================
# demanda_elektro
# ========================================================================
"""Prévia isolada da demanda residencial trifásica DIS-NOR-030 Rev. 07.

Não dimensiona DG ou alimentador, não publica perfil e não altera GED-13.
Quando a planilha não informa os dados exigidos pelo item 6.27, não fecha
demanda nem supõe fator de potência ou categoria de equipamento.
"""

import math
import unicodedata

pass # Referência interna consolidada em normativo_elektro.


def demanda_numero(valor):
    try:
        n = float(valor)
        return n if math.isfinite(n) else 0.0
    except (ValueError, TypeError):
        return 0.0


def demanda_nome(texto):
    s = unicodedata.normalize("NFKD", str(texto or "").casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


def demanda_fator(faixas, quantidade):
    for faixa in faixas:
        if "min" in faixa and quantidade < faixa["min"]:
            continue
        maximo = faixa.get("max", faixa.get("ate"))
        if maximo is None or quantidade <= maximo:
            return faixa["fator"]
    return None


def demanda_calcular_previa(tabela, regras):
    """Retorna kVA e memória apenas para dados completos e sem ambiguidades."""
    if not perfil_auditar_tabelas_demanda(regras):
        return {"status": "pendente", "demanda_kva": None,
                "pendencias": ["Tabelas da Elektro ausentes ou inconsistentes."], "detalhes": []}
    t = regras["demanda_elektro_auditoria"]
    pendencias, detalhes = [], []
    grupos = {k: [] for k in ("chuveiros", "boiler", "eletrodomesticos", "forno_eletrico", "fogoes",
                                "ar_condicionado", "bombas", "motores", "especiais", "recarga")}
    iluminacao_tug_w = 0.0
    for i, linha in enumerate(tabela or [], 1):
        local = str(linha.get("Ambiente") or f"Linha {i}").strip()
        qi = int(demanda_numero(linha.get("Qtd Ilum.", 0)))
        qt = int(demanda_numero(linha.get("Qtd TUG", linha.get("TUGs (Qtd)", 0))))
        qe = int(demanda_numero(linha.get("Qtd TUE", 0)))
        wi = demanda_numero(linha.get("Pot. Unit. Ilum (W)", linha.get("Pot. Unit. Ilum (VA)", 0)))
        wt = demanda_numero(linha.get("Pot. Unit. TUG (W)", linha.get("Pot. Unit. TUG (VA)", 0)))
        w = demanda_numero(linha.get("Pot. Unit. TUE (W)", linha.get("Pot. Unit. TUE (VA)", 0)))
        if min(qi, qt, qe, wi, wt, w) < 0:
            pendencias.append(f"{local}: carga ou quantidade negativa.")
            continue
        iluminacao_tug_w += qi * wi + qt * wt
        if not qe:
            continue
        nome = str(linha.get("Equipamento TUE") or linha.get("Equipamento") or "")
        n = demanda_nome(nome)
        if not n or n == "-" or w <= 0:
            pendencias.append(f"{local}: TUE sem nome ou potência de placa.")
            continue
        if "/" in n:
            pendencias.append(f"{local}: '{nome}' indica alternativas ou equipamentos diferentes; "
                              "identificar um único equipamento por linha antes de calcular a demanda Elektro.")
            continue
        categoria = None
        categoria_declarada = str(linha.get("Categoria Normativa TUE") or "")
        categorias_validas = set(grupos) | {"outros"}
        if categoria_declarada and categoria_declarada not in categorias_validas:
            pendencias.append(f"{local}: categoria normativa da TUE desconhecida.")
            continue
        if "forno" in n and "micro" not in n:
            if categoria_declarada and categoria_declarada != "forno_eletrico":
                pendencias.append(f"{local}: categoria declarada incompatível com forno elétrico.")
            else:
                categoria = "forno_eletrico"
        elif "fogao" in n or "cooktop" in n or categoria_declarada == "fogoes":
            pendencias.append(f"{local}: fogão elétrico exige esclarecer a divergência entre "
                              "o item 6.27.5 e a Tabela 10 específica da DIS-NOR-030.")
        elif categoria_declarada == "forno_eletrico":
            pendencias.append(f"{local}: a categoria forno elétrico exige identificar o aparelho como forno.")
        elif categoria_declarada == "outros":
            pendencias.append(f"{local}: conferir norma aplicável à TUE '{nome}'.")
        elif categoria_declarada:
            categoria = categoria_declarada
        elif any(x in n for x in ("chuve", "torneira eletrica", "aquecedor de passagem", "ferro eletrico")):
            categoria = "chuveiros"
        elif any(x in n for x in ("boiler", "aquecedor central", "acumulacao")):
            categoria = "boiler"
        elif any(x in n for x in ("lava e seca", "lavaseca", "lava-e-seca", "micro", "secadora", "maquina de lavar", "lavadora", "lava-louca", "lava louca")):
            categoria = "eletrodomesticos"
        elif any(x in n for x in ("ar-condicionado", "ar condicionado", "split")):
            categoria = "ar_condicionado"
        elif any(x in n for x in ("hidromassagem", "banheira eletrica", "bomba")):
            categoria = "bombas"
        elif any(x in n for x in ("motor", "maquina de solda a motor")):
            categoria = "motores"
        elif any(x in n for x in ("recarga", "carregador veicular", "wallbox")):
            categoria = "recarga"
        elif any(x in n for x in ("raios x", "solda", "galvaniz")):
            categoria = "especiais"
        else:
            pendencias.append(f"{local}: classificar TUE '{nome}' para aplicar o item 6.27.")
        if categoria:
            fp = demanda_numero(linha.get("Fator de Potência TUE", linha.get("FP TUE")))
            if fp < 0 or fp > 1:
                pendencias.append(f"{local}: fator de potência fora do intervalo (0, 1].")
                fp = 0.0
            if categoria in ("eletrodomesticos", "recarga", "motores", "especiais", "ar_condicionado") and not 0 < fp <= 1:
                # Para ar-condicionado, VA de placa explícito dispensa FP.
                va_placa = demanda_numero(linha.get("Pot. Placa TUE (VA)"))
                if categoria != "ar_condicionado" or va_placa <= 0:
                    if categoria not in ("eletrodomesticos", "ar_condicionado"):
                        pendencias.append(f"{local}: informar fator de potência/VA de placa de '{nome}'.")
            btu = int(demanda_numero(linha.get("Capacidade TUE (BTU/h)")))
            if categoria == "ar_condicionado" and fp <= 0 and demanda_numero(linha.get("Pot. Placa TUE (VA)")) <= 0:
                conhecidos = {item["btu_h"]: item for item in t["tabela_11_ar_condicionado"]["potencias"]}
                if btu not in conhecidos:
                    pendencias.append(f"{local}: informar VA/FP de placa ou capacidade (BTU/h) "
                                      f"da Tabela 11 para '{nome}'.")
                elif w != conhecidos[btu]["w"]:
                    pendencias.append(f"{local}: {btu} BTU/h corresponde a "
                                      f"{conhecidos[btu]['w']} W na Tabela 11, mas o projeto informa "
                                      f"{w:g} W. Conferir W ou informar VA/FP de placa.")
            for _ in range(qe):
                grupos[categoria].append({"w": w, "fp": fp, "va": demanda_numero(linha.get("Pot. Placa TUE (VA)")),
                                          "btu": btu, "nome": nome})

    def acrescentar(categoria, itens, fator, fp=1.0, tabela_id=""):
        watts = sum(x["w"] for x in itens)
        kva = watts * fator / fp / 1000.0
        detalhes.append({"categoria": categoria, "tabela_id": tabela_id,
                         "quantidade": len(itens), "carga_w": watts, "fator": fator,
                         "fator_potencia": fp, "demanda_kva": kva})

    if iluminacao_tug_w:
        fd = demanda_fator(t["tabela_6_iluminacao_tug"]["faixas"], iluminacao_tug_w / 1000)
        acrescentar("Iluminação + TUG", [{"w": iluminacao_tug_w}], fd, tabela_id="DISNOR030_T6")
    simples = [("chuveiros", 7), ("boiler", 8), ("eletrodomesticos", 9),
               ("forno_eletrico", 9), ("bombas", 16)]
    for chave, numero in simples:
        itens = grupos[chave]
        if itens:
            tabela_chave = {"chuveiros": "tabela_7_chuveiros", "boiler": "tabela_8_boiler",
                            "eletrodomesticos": "tabela_9_eletrodomesticos",
                            "forno_eletrico": "tabela_9_eletrodomesticos",
                            "bombas": "tabela_16_bombas_hidromassagem"}[chave]
            fd = demanda_fator(t[tabela_chave]["faixas"], len(itens))
            if chave == "eletrodomesticos" and any(x["fp"] > 0 for x in itens):
                # FP de fabricante informado por aparelho prevalece sobre 0,92.
                kva = sum(x["w"] * fd / (x["fp"] or .92) for x in itens) / 1000
                detalhes.append({"categoria": chave, "tabela_id": "DISNOR030_T9",
                                 "quantidade": len(itens), "carga_w": sum(x["w"] for x in itens),
                                 "fator": fd, "demanda_kva": kva})
            else:
                acrescentar(chave, itens, fd, .92 if chave == "eletrodomesticos" else 1.0,
                            "DISNOR030_T9_FORNO" if chave == "forno_eletrico" else f"DISNOR030_T{numero}")
    if grupos["ar_condicionado"]:
        itens = grupos["ar_condicionado"]
        tab = t["tabela_12_ar_condicionado"]
        n = len(itens)
        fd = next((tab["residencial"][i] for i, limite in enumerate(tab["ate_quantidade"])
                   if limite is None or n <= limite), None)
        potencias_btu = {item["btu_h"]: item["va"] for item in t["tabela_11_ar_condicionado"]["potencias"]}
        kva = sum((x["va"] if x["va"] > 0 else x["w"] / x["fp"] if x["fp"] > 0
                   else potencias_btu.get(x["btu"], 0))
                  for x in itens) * fd / 1000
        detalhes.append({"categoria": "ar_condicionado", "tabela_id": "DISNOR030_T11_T12",
                         "quantidade": n, "fator": fd, "demanda_kva": kva})
    # Equipamentos restantes dependem de dados que a planilha atual não guarda:
    # potência de placa e FP por aparelho, simultaneidade dos motores, tipo de
    # equipamento especial e recarga individual/coletiva.
    for chave in ("motores", "especiais", "recarga"):
        if grupos[chave]:
            pendencias.append(f"{chave}: informar parâmetros específicos de placa e simultaneidade para o item 6.27.")
    return {"status": "pendente" if pendencias else "calculado",
            "demanda_kva": None if pendencias else sum(x["demanda_kva"] for x in detalhes),
            "pendencias": pendencias, "detalhes": detalhes}


# ========================================================================
# enquadramento_elektro
# ========================================================================
"""Auditoria isolada da Tabela 3. Não dimensiona nem publica um perfil."""

import math

pass # Referência interna consolidada em normativo_elektro.

# Limites literais do documento: os espaços entre linhas não são arredondados.
enquadramento_FAIXAS_TRIFASICAS = (
    ("T0", 0.0, 19.0, 50), ("T1", 19.1, 24.0, 63),
    ("T2", 24.1, 38.0, 100), ("T3", 38.1, 47.0, 125),
    ("T4", 47.1, 57.0, 150), ("T5", 57.1, 75.0, 200),
)


def enquadramento_auditar_enquadramento(tabela, perfil, previa, contexto=None):
    """Só informa candidato quando contexto e números foram conferidos.

    As confirmações pertencem à simulação administrativa; não alteram dados
    persistidos, status do perfil, QDC, DG ou alimentador.
    """
    c = contexto or {}
    pendencias = []
    carga_w = 0.0
    if not perfil_eh_perfil_elektro(perfil):
        pendencias.append("Perfil diferente da DIS-NOR-030 Rev. 07 da Elektro.")
    if not c.get("municipio_vinculado"):
        pendencias.append("Município não vinculado ao perfil selecionado.")
    if c.get("tensao") != "220/127 V":
        pendencias.append("Confirmar tensão local 220/127 V; outras tensões exigem auditoria própria.")
    if not c.get("atendimento_confirmado"):
        pendencias.append("Confirmar atendimento Elektro e tensão no endereço do projeto.")
    if not c.get("urbano_individual"):
        pendencias.append("Confirmar instalação residencial individual urbana para esta auditoria.")
    if not c.get("cargas_conferidas"):
        pendencias.append("Conferir potências ativas em W, quantidades e dados usados na prévia.")
    if not c.get("equipamentos_conferidos"):
        pendencias.append("Conferir motores, cargas especiais e equipamentos que exigem estudo específico.")
    for i, row in enumerate(tabela or [], 1):
        for qtd_key, w_key, va_key, alias in (
            ("Qtd Ilum.", "Pot. Unit. Ilum (W)", "Pot. Unit. Ilum (VA)", None),
            ("Qtd TUG", "Pot. Unit. TUG (W)", "Pot. Unit. TUG (VA)", "TUGs (Qtd)"),
            ("Qtd TUE", "Pot. Unit. TUE (W)", "Pot. Unit. TUE (VA)", None),
        ):
            try:
                qtd = float(row.get(qtd_key, row.get(alias, 0) if alias else 0))
                if not math.isfinite(qtd) or qtd < 0 or not qtd.is_integer():
                    raise ValueError
                if not qtd:
                    continue
                # Não converter silenciosamente VA em W para enquadrar a entrada.
                if w_key not in row:
                    pendencias.append(f"Linha {i}: informar potência ativa em W; {va_key} não substitui W.")
                    continue
                watts = float(row[w_key])
                if not math.isfinite(watts) or watts <= 0:
                    raise ValueError
                carga_w += qtd * watts
            except (TypeError, ValueError, OverflowError):
                pendencias.append(f"Linha {i}: quantidade ou potência inválida em {qtd_key}.")
    kw = carga_w / 1000.0
    motivo = perfil_motivo_conferencia(carga_w, perfil)
    if motivo:
        pendencias.append(motivo)
    if kw > 75:
        pendencias.append("Carga instalada acima de 75 kW: fora do escopo deste perfil.")
    demanda = (previa or {}).get("demanda_kva")
    try:
        demanda = float(demanda)
        if not math.isfinite(demanda) or demanda <= 0:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        demanda = None
    if (previa or {}).get("status") != "calculado" or demanda is None:
        pendencias.append("Prévia de demanda incompleta ou inválida.")
    elif demanda > 75:
        pendencias.append("Demanda acima de 75 kVA: fora do limite trifásico em 220/127 V.")

    candidato = None
    if not pendencias:
        if kw <= 10:
            if kw >= 5.1:
                candidato = {"categoria": "M1", "modalidade": "Monofásico", "disjuntor_tabela_a": 63}
            else:
                pendencias.append("Carga inferior a 5,1 kW: não inferir M1 pela modalidade; conferir a Tabela 3.")
        elif 11.1 <= kw <= 13:
            candidato = {"categoria": "B1", "modalidade": "Bifásico", "disjuntor_tabela_a": 63}
        elif kw > 18:
            for categoria, minimo, maximo, disjuntor in enquadramento_FAIXAS_TRIFASICAS:
                if minimo <= demanda <= maximo:
                    candidato = {"categoria": categoria, "modalidade": "Trifásico", "disjuntor_tabela_a": disjuntor}
                    break
            if candidato is None:
                pendencias.append("Demanda em lacuna decimal da Tabela 3: conferir sem arredondamento automático.")
    return {"status": "candidato" if candidato else "conferencia_tecnica",
            "carga_instalada_kw": kw, "demanda_kva": demanda,
            "candidato": candidato, "pendencias": list(dict.fromkeys(pendencias)),
            "fonte": "DIS-NOR-030 Rev. 07, item 6.28.1 e Tabela 3, página 63",
            "aprovado": False}


# ========================================================================
# componentes_entrada_elektro
# ========================================================================
"""Consulta documental isolada da Tabela 3, página 63, DIS-NOR-030 Rev.07.

Notações transcritas em mm². Não calcula capacidade de condução, queda de
tensão, proteção ou materiais de execução; não altera o projeto.
"""

from copy import deepcopy
import math

componentes_FONTE = "DIS-NOR-030 Rev. 07 — Tabela 3, página 63/142 — 220/127 V"
componentes_URL_FONTE = "https://www.neoenergia.com/documents/d/sp/dis-nor-030-rev07?download=true"


def componentes_linha(disjuntor, conexao, embutido, subterraneo, distribuicao, caixa,
           eletroduto, motores, medicao="Direta"):
    return {"disjuntor_a": disjuntor, "conexao_aereo": conexao,
            "entrada_embutida": embutido, "entrada_subterranea": subterraneo,
            "distribuicao": distribuicao, "caixa": caixa, "medicao": medicao,
            "eletroduto_fases_neutro": eletroduto,
            "eletroduto_aterramento": '3/4 pol.', "limite_motor_cv": motores}


componentes_TABELA_3 = {
    "M1": componentes_linha(63, ["10+10 CU CONC", "16+16 AL CONC"],
        {"Distribuidora": "FORNECIMENTO DISTRIBUIDORA"},
        {"XLPE/HEPR": "10/10 CU XLPE/HEPR"},
        {"XLPE/HEPR": "10/10/10 CU XLPE/HEPR", "PVC": "16/16/16 CU PVC"},
        "Monofásica ou Polifásica", '1 1/4 pol.', {"FN": 2, "FF": None, "3F": None}),
    "B1": componentes_linha(63, ["2x16+16 AL MULT"],
        {"Distribuidora": "FORNECIMENTO DISTRIBUIDORA"},
        {"XLPE/HEPR": "2x10/10 CU XLPE/HEPR"},
        {"XLPE/HEPR": "2x10/10/10 CU XLPE/HEPR", "PVC": "2x16/16/16 CU PVC"},
        "Polifásica", '1 1/4 pol.', {"FN": 2, "FF": 2, "3F": None}),
    "T0": componentes_linha(50, ["3x16+16 AL MULT"],
        {"Distribuidora": "FORNECIMENTO DISTRIBUIDORA"},
        {"XLPE/HEPR": "3x10/10 CU XLPE/HEPR"},
        {"XLPE/HEPR": "3x10/10/10 CU XLPE/HEPR", "PVC": "3x16/16/16 CU PVC"},
        "Polifásica", '1 1/4 pol.', {"FN": 1, "FF": 2, "3F": 5}),
    "T1": componentes_linha(63, ["3x16+16 AL MULT"],
        {"Distribuidora": "FORNECIMENTO DISTRIBUIDORA"},
        {"XLPE/HEPR": "3x16/16 CU XLPE/HEPR"},
        {"XLPE/HEPR": "3x16/16/16 CU XLPE/HEPR", "PVC": "3x25/25/16 CU PVC"},
        "Polifásica", '1 1/4 pol.', {"FN": 2, "FF": 5, "3F": 20}),
    "T2": componentes_linha(100, ["3x25+25 AL MULT"],
        {"XLPE/HEPR": "3x25/25 CU XLPE/HEPR", "PVC": "3x35/35 CU PVC"},
        {"XLPE/HEPR": "3x35/35 CU XLPE/HEPR"},
        {"XLPE/HEPR": "3x35/35/16 CU XLPE/HEPR", "PVC": "3x35/35/16 CU PVC"},
        "Polifásica* ou Caixa para Medidor 200 A ou Módulo de Policarbonato",
        '2 pol.', {"FN": 3, "FF": 7.5, "3F": 25}),
    "T3": componentes_linha(125, ["3x35+35 AL MULT"],
        {"XLPE/HEPR": "3x35/35 CU XLPE/HEPR", "PVC": "3x50/50 CU PVC"},
        {"XLPE/HEPR": "3x50/50 CU XLPE/HEPR"},
        {"XLPE/HEPR": "3x50/50/16 CU XLPE/HEPR", "PVC": "3x70/70/35 CU PVC"},
        "Caixa para Medidor 200 A ou Módulo de Policarbonato",
        '2 pol.', {"FN": 7.5, "FF": 10, "3F": 30}),
    "T4": componentes_linha(150, ["3x50+50 AL MULT"],
        {"XLPE/HEPR": "3x50/50 CU XLPE/HEPR", "PVC": "3x70/70 CU PVC"},
        {"XLPE/HEPR": "3x70/70 CU XLPE/HEPR"},
        {"XLPE/HEPR": "3x70/70/35 CU XLPE/HEPR"},
        "Caixa para Medidor 200 A ou Módulo de Policarbonato",
        '2 pol.', {"FN": 7.5, "FF": 10, "3F": 30}),
    "T5": componentes_linha(200, ["3x70+50 AL MULT"],
        {"XLPE/HEPR": "3x70/70 CU XLPE/HEPR"},
        {"XLPE/HEPR": "3x95/95 CU XLPE/HEPR"},
        {"XLPE/HEPR": "3x95/95/50 CU XLPE/HEPR"},
        "Caixa para TC", '2 1/2 pol.', {"FN": 7.5, "FF": 10, "3F": 50}, "Indireta"),
}


def componentes_consultar_componentes(auditoria, tipo_entrada="Não informado",
                          isolacao_entrada="Não informada", isolacao_distribuicao="Não informada"):
    """Exibe alternativas documentais apenas para candidato consistente.

    Uma opção não informada não é substituída pela primeira alternativa.
    """
    resultado = {"status": "pendente", "linhas": [], "selecoes": {},
                 "pendencias": [], "aprovado": False, "fonte": componentes_FONTE}
    a = auditoria or {}
    candidato = a.get("candidato") or {}
    categoria = candidato.get("categoria")
    linha = componentes_TABELA_3.get(categoria)
    if a.get("status") != "candidato" or a.get("pendencias") or not linha:
        resultado["pendencias"].append("Concluir a conferência do enquadramento antes de consultar componentes.")
        return resultado
    # Impede reaproveitar resultado inconsistente em categorias ou tensões diferentes.
    try:
        kw, demanda = float(a["carga_instalada_kw"]), float(a["demanda_kva"])
        if not all(math.isfinite(v) and v > 0 for v in (kw, demanda)) or kw > 75 or demanda > 75:
            raise ValueError
        if categoria == "M1":
            valido = 5.1 <= kw <= 10 and candidato.get("modalidade") == "Monofásico"
        elif categoria == "B1":
            valido = 11.1 <= kw <= 13 and candidato.get("modalidade") == "Bifásico"
        else:
            pass # Referência interna consolidada em normativo_elektro.
            valido = kw > 18 and candidato.get("modalidade") == "Trifásico" and any(
                cat == categoria and minimo <= demanda <= maximo
                for cat, minimo, maximo, _ in enquadramento_FAIXAS_TRIFASICAS)
        if not valido or candidato.get("disjuntor_tabela_a") != linha["disjuntor_a"]:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        resultado["pendencias"].append("Candidato inconsistente com os limites da Tabela 3; recalcular a auditoria.")
        return resultado
    linha = deepcopy(linha)
    def item(componente, especificacao):
        resultado["linhas"].append({"Componente": componente, "Referência da Tabela 3": especificacao})
    item("Disjuntor", f"{linha['disjuntor_a']} A")
    item("Ramal de conexão aéreo (mm²)", " ou ".join(linha["conexao_aereo"]))
    for nome, chave in (("Entrada embutida — fases/neutro (mm²)", "entrada_embutida"),
                       ("Entrada subterrânea — fases/neutro (mm²)", "entrada_subterranea"),
                       ("Distribuição — fases/neutro/terra (mm²)", "distribuicao")):
        item(nome, " ou ".join(linha[chave].values()))
    item("Caixa de medição", linha["caixa"])
    item("Tipo de medição", linha["medicao"])
    item("Eletroduto mínimo — fases e neutro", linha["eletroduto_fases_neutro"])
    item("Eletroduto mínimo — aterramento", linha["eletroduto_aterramento"])
    item("Limite do maior motor (cv)", "; ".join(
        f"{k}: {v:g}" if v is not None else f"{k}: —" for k, v in linha["limite_motor_cv"].items()))
    entrada = {"Embutido": "entrada_embutida", "Subterrâneo": "entrada_subterranea"}.get(tipo_entrada)
    if not entrada:
        resultado["pendencias"].append("Informar se o ramal de entrada é embutido ou subterrâneo para consultar a opção correspondente.")
    else:
        opcoes = linha[entrada]
        if "Distribuidora" in opcoes:
            resultado["selecoes"]["Ramal de entrada"] = opcoes["Distribuidora"]
        elif isolacao_entrada in opcoes:
            resultado["selecoes"]["Ramal de entrada"] = opcoes[isolacao_entrada]
        else:
            resultado["pendencias"].append("Informar isolação do ramal de entrada compatível com a alternativa da tabela.")
    if isolacao_distribuicao in linha["distribuicao"]:
        resultado["selecoes"]["Ramal de distribuição"] = linha["distribuicao"][isolacao_distribuicao]
    else:
        resultado["pendencias"].append("Informar isolação do ramal de distribuição compatível com a alternativa da tabela.")
    resultado["categoria"] = categoria
    resultado["status"] = "referencia_documental"
    return resultado


# ========================================================================
# verificacao_ramal_elektro
# ========================================================================
"""Conferência aritmética isolada; parâmetros documentados pelo responsável."""
import math


def ramal_verificar_ramal(auditoria, componentes, dados):
    resultado = {"status": "pendente", "aprovado": False, "criterios": [], "pendencias": []}
    def pendencia(texto):
        resultado["pendencias"].append(texto)
    def positivo(chave):
        valor = dados.get(chave)
        if isinstance(valor, bool):
            return None
        try:
            valor = float(valor)
            return valor if math.isfinite(valor) and valor > 0 else None
        except (TypeError, ValueError):
            return None
    candidato = auditoria.get("candidato") or {}
    cabo = componentes.get("selecoes", {}).get("Ramal de distribuição")
    if auditoria.get("status") != "candidato" or not cabo:
        pendencia("Selecione um enquadramento candidato e a isolação do ramal de distribuição.")
        return resultado
    resultado["cabo"] = cabo
    if dados.get("sem_dados") is True:
        pendencia("Dados do ramal não disponíveis. A prévia de demanda pode continuar; capacidade e queda de tensão aguardam conferência técnica.")
        dados = {}
    ib, iz, comprimento, coef, tensao, limite = [positivo(k) for k in
        ("corrente_a", "iz_corrigida_a", "comprimento_m", "coeficiente_mv_am", "tensao_v", "limite_percentual")]
    metodo_ok = bool(str(dados.get("metodo") or "").strip())
    fonte_ok = bool(str(dados.get("fonte") or "").strip())
    if not metodo_ok:
        pendencia("Falta informar o método de instalação e as condições reais do ramal.")
    if not fonte_ok:
        pendencia("Falta informar a fonte técnica: fabricante, documento, revisão e tabela/página.")
    for valor, mensagem in [
        (ib, "Falta informar a corrente de projeto do trecho crítico (A)."),
        (iz, "Falta informar a capacidade de condução corrigida — Iz (A)."),
        (comprimento, "Falta informar o comprimento de ida do ramal (m)."),
        (coef, "Falta informar o coeficiente de queda aplicável ao circuito (mV/A/m)."),
        (tensao, "Falta informar a tensão de referência do trecho (V)."),
        (limite, "Falta informar o limite de queda disponível para este trecho (%).")]:
        if valor is None:
            pendencia(mensagem)
    if dados.get("confirmado") is not True:
        pendencia("A aplicabilidade dos dados ao cabo, circuito e condições reais ainda não foi confirmada.")
    if not metodo_ok or not fonte_ok or dados.get("confirmado") is not True:
        return resultado
    nominal = candidato.get("disjuntor_tabela_a")
    if ib and iz:
        atende = ib <= nominal <= iz
        resultado["criterios"].append({"Critério": "Corrente de projeto e capacidade corrigida", "Resultado": "Atende ao critério informado" if atende else "Não atende", "Cálculo": f"Ib={ib:g} A; In={nominal:g} A; Iz corrigida={iz:g} A; verificar Ib ≤ In ≤ Iz"})
    if ib and comprimento and coef and tensao and limite:
        queda = coef * ib * comprimento / 1000
        percentual = 100 * queda / tensao
        if math.isfinite(percentual) and math.isfinite(queda):
            resultado["criterios"].append({"Critério": "Queda de tensão no trecho", "Resultado": "Atende ao critério informado" if percentual <= limite else "Não atende", "Cálculo": f"ΔV={queda:.3f} V ({percentual:.3f}%); limite informado={limite:g}%; ΔV=k×Ib×L/1000"})
        else:
            pendencia("Valores fora da faixa calculável para queda de tensão.")
    if any(c["Resultado"] == "Não atende" for c in resultado["criterios"]):
        resultado["status"] = "nao_atende"
    elif len(resultado["criterios"]) == 2 and not resultado["pendencias"]:
        resultado["status"] = "criterios_informados_atendidos"
    return resultado


# ========================================================================
# registro_auditoria_elektro
# ========================================================================
"""Registro exportável de simulações, sem aprovação ou aplicação ao projeto."""
import json
import math
from datetime import datetime, timezone
from copy import deepcopy


def registro_limpar(valor):
    if isinstance(valor, dict):
        return {str(k): registro_limpar(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [registro_limpar(v) for v in valor]
    if isinstance(valor, float) and not math.isfinite(valor):
        return None
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    return str(valor)


def registro_registrar(projeto, local, perfil, entradas, cargas, previa, enquadramento, componentes, ramal):
    dados = deepcopy(entradas)
    if dados.get("ramal", {}).get("sem_dados"):
        dados["ramal"] = {"sem_dados": True, "confirmado": False}
    return registro_limpar({"tipo": "Simulação preliminar Elektro — sem aprovação técnica",
        "registrado_em_utc": datetime.now(timezone.utc).isoformat(),
        "projeto": projeto, "local": local,
        "perfil": {k: perfil.get(k) for k in ("id", "concessionaria", "documento", "revisao", "uf", "status")},
        "aprovado": False, "entradas": dados, "cargas_cadastradas": cargas,
        "demanda": previa, "enquadramento": enquadramento,
        "componentes_documentais": componentes, "conferencia_ramal": ramal,
        "limites": "Não aprova o padrão, não ativa o perfil e não altera o alimentador. Dados informados exigem conferência técnica."})


def registro_exportar_json(registro):
    return json.dumps(registro, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def registro_assinatura_contexto(cargas, parametros, perfil):
    import hashlib
    dados = registro_limpar({"cargas": cargas, "parametros": parametros, "perfil": perfil})
    return hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def registro_exportar_resumo(registro):
    def texto(valor):
        if valor is True: return "Sim"
        if valor is False: return "Não"
        if valor is None or valor == "": return "Não informado"
        return str(valor)
    def numero(valor):
        return f"{valor:.3f}".replace(".", ",") if isinstance(valor, (int, float)) and not isinstance(valor, bool) else texto(valor)
    perfil = registro.get("perfil", {})
    demanda = registro.get("demanda", {})
    enquadramento = registro.get("enquadramento", {})
    candidato = enquadramento.get("candidato") or {}
    entradas = registro.get("entradas", {})
    ramal = entradas.get("ramal", {})
    componentes = registro.get("componentes_documentais", {})
    conferencia = registro.get("conferencia_ramal", {})
    linhas = ["AUDITORIA PRELIMINAR ELEKTRO — SEM APROVAÇÃO TÉCNICA",
        "Projeto: " + texto(registro.get("projeto")), "Local: " + texto(registro.get("local")),
        "Data do registro (UTC): " + texto(registro.get("registrado_em_utc")),
        "", "RESUMO", "Distribuidora: " + texto(perfil.get("concessionaria")),
        "Documento: " + texto(perfil.get("documento")) + " — revisão " + texto(perfil.get("revisao")),
        "Status do perfil no registro: " + texto(perfil.get("status")),
        "Carga instalada: " + numero(enquadramento.get("carga_instalada_kw")) + " kW",
        "Demanda preliminar: " + numero(demanda.get("demanda_kva")) + " kVA",
        "Categoria candidata: " + texto(candidato.get("categoria")),
        "Modalidade: " + texto(candidato.get("modalidade")),
        "Disjuntor da tabela: " + texto(candidato.get("disjuntor_tabela_a")) + " A",
        "", "DADOS INFORMADOS"]
    for chave, rotulo in [("tensao", "Tensão local"), ("tipo_entrada", "Tipo de entrada"),
        ("isolacao_entrada", "Isolação da entrada"), ("isolacao_distribuicao", "Isolação da distribuição"),
        ("atendimento_confirmado", "Atendimento no endereço conferido"),
        ("urbano_individual", "Residencial individual urbana"), ("cargas_conferidas", "Cargas conferidas"),
        ("equipamentos_conferidos", "Ausência de cargas especiais conferida")]:
        linhas.append(rotulo + ": " + texto(entradas.get(chave)))
    if ramal.get("sem_dados"):
        linhas.append("Ramal: usuário não dispõe dos dados para conferência.")
    else:
        for chave, rotulo in [("metodo", "Método e condições"), ("fonte", "Fonte técnica"),
            ("corrente_a", "Corrente de projeto (A)"), ("iz_corrigida_a", "Iz corrigida (A)"),
            ("comprimento_m", "Comprimento de ida (m)"), ("coeficiente_mv_am", "Coeficiente (mV/A/m)"),
            ("tensao_v", "Tensão de referência (V)"), ("limite_percentual", "Limite de queda (%)"),
            ("confirmado", "Aplicabilidade dos dados confirmada")]:
            linhas.append(rotulo + ": " + texto(ramal.get(chave)))
    linhas.extend(["", "MEMÓRIA DA DEMANDA"])
    for item in demanda.get("detalhes", []):
        linhas.append(texto(item.get("categoria")) + ": " + numero(item.get("demanda_kva")) +
            " kVA; fonte " + texto(item.get("tabela_id")) +
            "; quantidade " + texto(item.get("quantidade")) +
            "; carga (W) " + texto(item.get("carga_w")) +
            "; fator " + texto(item.get("fator")) + "; FP " + texto(item.get("fator_potencia")))
    linhas.extend(["", "COMPONENTES — REFERÊNCIAS DOCUMENTAIS"])
    for item in componentes.get("linhas", []):
        linhas.append(item["Componente"] + ": " + item["Referência da Tabela 3"])
    for nome, valor in componentes.get("selecoes", {}).items():
        linhas.append(nome + " — alternativa informada: " + texto(valor))
    linhas.extend(["", "CONFERÊNCIA DO RAMAL"])
    for item in conferencia.get("criterios", []):
        linhas.extend([item["Critério"] + ": " + item["Resultado"], "  " + item["Cálculo"]])
    if not conferencia.get("criterios"):
        linhas.append("Sem critérios calculados; conferir as pendências.")
    linhas.extend(["", "PENDÊNCIAS"])
    pendencias = []
    for bloco in (demanda, enquadramento, componentes, conferencia):
        for item in bloco.get("pendencias", []):
            if item not in pendencias: pendencias.append(item)
    linhas.extend(["- " + item for item in pendencias] or
        ["Nenhuma pendência de dados nestes cálculos. A aprovação técnica do padrão permanece pendente."])
    linhas.extend(["", "FONTES", texto(enquadramento.get("fonte")), texto(componentes.get("fonte")),
        "", "LIMITES DA CONFERÊNCIA", texto(registro.get("limites")),
        "Não verifica curto-circuito, atuação da proteção, neutro, PE ou aterramento."])
    return "\n".join(linhas).encode("utf-8")


# ========================================================================
# auditoria_perfil_elektro
# ========================================================================
"""Evidências de testes de software; não constituem homologação normativa."""
from datetime import datetime, timezone
from hashlib import sha256
import json

auditoria_CHAVE = "registro_testes_enquadramento_elektro"
auditoria_CASOS = (
    (12.048, "B1", "Bifásico", 63),
    (14.348, None, "Conferência técnica", None),
    (18.000, None, "Conferência técnica", None),
    (18.948, "T0", "Trifásico", 50),
)

def auditoria_assinatura(perfil):
    regras = dict(perfil.get("regras") or {})
    regras.pop("fonte_conferida", None)
    regras.pop(auditoria_CHAVE, None)
    regras.pop("validacao_automatica_integracao_elektro", None)
    regras.pop("conferencia_documental_parcial_elektro", None)
    dados = {k: perfil.get(k) for k in ("concessionaria", "documento", "revisao", "uf", "fonte_oficial", "municipios_atendidos", "municipio")}
    dados["regras"] = regras
    return sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()

def auditoria_registrar(perfil, email):
    return {"data_utc": datetime.now(timezone.utc).isoformat(), "registrado_por": email,
            "assinatura_perfil": auditoria_assinatura(perfil), "local_teste": "Guarujá/SP",
            "evidencia": "Conferência manual dos prints dos testes de software de 02/10/2026",
            "casos": [{"carga_kw": kw, "categoria": cat, "modalidade": mod,
                       "disjuntor_a": amp} for kw, cat, mod, amp in auditoria_CASOS],
            "homologado": False}

def auditoria_registro_atual(perfil):
    registro = (perfil.get("regras") or {}).get(auditoria_CHAVE) or {}
    return bool(registro) and registro.get("assinatura_perfil") == auditoria_assinatura(perfil)


# ========================================================================
# integracao_demanda_elektro
# ========================================================================
"""Demanda Elektro no fluxo do projeto, sem liberar proteções ou alimentador."""
pass # Referência interna consolidada em normativo_elektro.
pass # Referência interna consolidada em normativo_elektro.
pass # Referência interna consolidada em normativo_elektro.

integracao_METODO = "Elektro — teste integrado de demanda (sem DG)"

def integracao_calcular_integrada(tabela, rede, perfil, potencia):
    from perfis_normativos import perfil_atende_municipio
    resultado = {**potencia, "status": "elektro_integracao_pendente", "metodo": integracao_METODO,
        "potencia_demanda_w": None, "potencia_demanda_parcial_w": None,
        "demanda_aparente_kva": None, "corrente_demanda_a": None,
        "disjuntor_geral_a": None, "fator_demanda_pct": None,
        "tipo_fornecimento": rede.get("tipo_fornecimento", "A definir"),
        "tensao_fornecimento": rede.get("tensao_fornecimento", "A definir"),
        "detalhes_demanda": [], "pendencias": [], "aprovado": False,
        "observacao": "Teste integrado de demanda Elektro: não libera corrente, DG ou alimentador."}
    if not perfil_eh_perfil_elektro(perfil) or str((perfil or {}).get("status", "")).upper() not in ("RASCUNHO", "VALIDADO", "ATIVO"):
        resultado["pendencias"] = ["Selecione um rascunho Elektro DIS-NOR-030 Rev. 07 disponível para o teste."]
        return resultado
    if not perfil_atende_municipio(perfil, rede.get("uf"), rede.get("municipio")):
        resultado["pendencias"] = ["UF/município não vinculado ao perfil Elektro do teste."]
        return resultado
    resultado["perfil_normativo_id"] = perfil.get("id")
    resultado["perfil_normativo"] = "Neoenergia Elektro — DIS-NOR-030 Rev. 07 (teste integrado)"
    previa = demanda_calcular_previa(tabela, perfil.get("regras"))
    contexto = dict(rede.get("contexto_elektro_teste") or {})
    contexto["municipio_vinculado"] = True
    contexto["tensao"] = "220/127 V" if rede.get("tensao_fornecimento") == "127/220 V" else "Não informada"
    enquadramento = enquadramento_auditar_enquadramento(tabela, perfil, previa, contexto)
    resultado["detalhes_demanda"] = previa.get("detalhes") or []
    resultado["enquadramento_elektro"] = enquadramento
    resultado["pendencias"] = list(dict.fromkeys((previa.get("pendencias") or []) + (enquadramento.get("pendencias") or [])))
    # A demanda aparente não é convertida silenciosamente em potência ativa.
    if previa.get("status") == "calculado" and not enquadramento.get("pendencias"):
        resultado["demanda_aparente_kva"] = previa.get("demanda_kva")
        resultado["status"] = "elektro_demanda_integrada"
    elif previa.get("status") == "calculado":
        resultado["demanda_aparente_kva"] = previa.get("demanda_kva")
    return resultado


# ========================================================================
# validacao_integrada_elektro
# ========================================================================
"""Testes executáveis de software com cargas fictícias; não homologam a norma."""
from copy import deepcopy
from datetime import datetime, timezone
pass # Referência interna consolidada em normativo_elektro.
pass # Referência interna consolidada em normativo_elektro.

validacao_CHAVE = "validacao_automatica_integracao_elektro"

def validacao_executar(perfil, email):
    casos = []
    cidade = next(iter(perfil.get("municipios_atendidos") or []), perfil.get("municipio") or "")
    rede = {"metodo_demanda": integracao_METODO, "uf": perfil.get("uf"), "municipio": cidade,
            "tensao_fornecimento": "127/220 V", "tipo_fornecimento": "Trifásico",
            "contexto_elektro_teste": {k: True for k in ("atendimento_confirmado", "urbano_individual", "cargas_conferidas", "equipamentos_conferidos")}}
    base = [{"Qtd Ilum.": 1, "Pot. Unit. Ilum (W)": 10098},
            {"Qtd TUE": 1, "Pot. Unit. TUE (W)": 350, "Equipamento TUE": "Máquina de lavar"},
            {"Qtd TUE": 1, "Pot. Unit. TUE (W)": 1000, "Equipamento TUE": "Forno elétrico"}]
    def verificar(nome, rows, parametros, categoria, demanda):
        antes = deepcopy((rows, parametros, perfil))
        try:
            r = integracao_calcular_integrada(rows, parametros, perfil, {"total_w": 0})
            candidato = (r.get("enquadramento_elektro") or {}).get("candidato") or {}
            valor = r.get("demanda_aparente_kva")
            valor_ok = (valor is None if demanda is None else valor is not None and abs(valor-demanda) < 1e-8)
            esperado_status = "elektro_demanda_integrada" if categoria else "elektro_integracao_pendente"
            seguro = all(r.get(k) is None for k in ("potencia_demanda_w", "corrente_demanda_a", "disjuntor_geral_a")) and r.get("aprovado") is False
            passou = candidato.get("categoria") == categoria and valor_ok and r.get("status") == esperado_status and seguro and antes == (rows, parametros, perfil)
            casos.append({"Teste": nome, "Esperado": categoria or "Conferência técnica", "Obtido": candidato.get("categoria") or "Conferência técnica", "Demanda (kVA)": round(valor, 6) if valor is not None else None, "Passou": passou})
        except Exception as e:
            casos.append({"Teste": nome, "Esperado": categoria or "Conferência técnica", "Obtido": "Falha na execução", "Demanda (kVA)": None, "Passou": False, "erro": str(e)})
    for kw, watts, categoria in ((12.048,600,"B1"), (13.000,1552,"B1"), (13.001,1553,None), (14.348,2900,None), (18.000,6552,None), (18.001,6553,"T0"), (18.948,7500,"T0")):
        rows = base + [{"Qtd TUE": 1, "Pot. Unit. TUE (W)": watts, "Equipamento TUE": "Chuveiro elétrico"}]
        verificar(f"Carga {kw:.3f} kW", rows, rede, categoria, 10.098*.24+.350/.92+1+watts/1000)
    rows = base + [{"Qtd TUE": 1, "Pot. Unit. TUE (W)": 600, "Equipamento TUE": "Chuveiro elétrico"}]
    esperado = 10.098*.24+.350/.92+1+.600
    verificar("Confirmações ausentes", rows, {**rede, "contexto_elektro_teste": {}}, None, esperado)
    verificar("Tensão fora do escopo", rows, {**rede, "tensao_fornecimento": "220/380 V"}, None, esperado)
    verificar("UF incompatível", rows, {**rede, "uf": "ZZ"}, None, None)
    verificar("Município não vinculado", rows, {**rede, "municipio": "MUNICÍPIO FICTÍCIO NÃO VINCULADO"}, None, None)
    desconhecidas = base + [{"Qtd TUE": 1, "Pot. Unit. TUE (W)": 600, "Equipamento TUE": "Equipamento sem categoria"}]
    verificar("TUE sem categoria", desconhecidas, rede, None, None)
    return {"data_utc": datetime.now(timezone.utc).isoformat(), "responsavel": email,
            "assinatura_perfil": auditoria_assinatura(perfil), "casos": casos,
            "passou": bool(cidade) and all(c["Passou"] for c in casos),
            "homologado": False, "escopo": "Software, cargas fictícias em 220/127 V. Não confirma atendimento ou tensão no endereço."}


# ========================================================================
# conferencia_documental_elektro
# ========================================================================
"""Rastreabilidade documental parcial, independente da homologação final."""
from datetime import datetime, timezone
pass # Referência interna consolidada em normativo_elektro.
pass # Referência interna consolidada em normativo_elektro.

documental_CHAVE = "conferencia_documental_parcial_elektro"
documental_FONTE = "https://www.neoenergia.com/documents/d/sp/dis-nor-030-rev07?download=true"

def documental_registrar(perfil, email, confirmacoes, notas=""):
    if not perfil_eh_perfil_elektro(perfil):
        raise ValueError("Perfil fora do documento Elektro DIS-NOR-030 Rev. 07.")
    teste = (perfil.get("regras") or {}).get("validacao_automatica_integracao_elektro") or {}
    if not teste.get("passou") or teste.get("assinatura_perfil") != auditoria_assinatura(perfil):
        raise ValueError("Execute os testes integrados com as regras atuais antes da conferência parcial.")
    if not all(confirmacoes.get(k) is True for k in ("documento", "escopo_demanda", "tabela_entrada")):
        raise ValueError("Confira os três itens documentais antes de registrar.")
    return {"data_utc": datetime.now(timezone.utc).isoformat(), "responsavel": email,
            "assinatura_perfil": auditoria_assinatura(perfil), "fonte": documental_FONTE,
            "documento": "DIS-NOR-030", "revisao": "07", "aprovacao_documento": "17/04/2026",
            "referencias": ["Identificação do documento — página 1", "Item 6.27 — páginas 47–49: demanda trifásica em kVA", "Item 6.28 e Tabela 3 — página 63: entrada Elektro 220/127 V"],
            "confirmacoes": dict(confirmacoes), "notas": str(notas).strip(),
            "escopo": "Conferência documental parcial. Não resolve conflitos, não confirma tensão por endereço e não homologa DG ou alimentador.",
            "homologado": False}


# ========================================================================
# atendimento_endereco_elektro
# ========================================================================
"""Evidência declarada por endereço; não substitui confirmação da distribuidora."""
import json
import hashlib
from datetime import datetime, timezone
pass # Referência interna consolidada em normativo_elektro.

endereco_CHAVE = "atendimento_endereco_elektro"


def endereco_contexto(rede, perfil):
    dados = {"uf": rede.get("uf"), "municipio": rede.get("municipio"),
        "tensao_projeto": rede.get("tensao_fornecimento"), "perfil": auditoria_assinatura(perfil)}
    return hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def endereco_registrar(rede, perfil, dados, projeto, responsavel):
    sem_dados = dados.get("sem_dados") is True
    entrada = {"sem_dados": sem_dados}
    pendencias = []
    if not rede.get("uf") or not rede.get("municipio"):
        pendencias.append("Selecione UF e município nos parâmetros do projeto.")
    if sem_dados:
        pendencias.append("Atendimento e tensão do endereço aguardam confirmação documentada.")
    else:
        for campo, rotulo in (("endereco", "Endereço completo"), ("fonte", "Fonte da informação"),
                              ("referencia", "Protocolo ou referência documental"), ("data_fonte", "Data da informação")):
            entrada[campo] = str(dados.get(campo) or "").strip()
            if not entrada[campo]:
                pendencias.append(rotulo + " não informado.")
        try:
            data = datetime.strptime(entrada["data_fonte"], "%Y-%m-%d").date()
            if data > datetime.now(timezone.utc).date():
                pendencias.append("A data da fonte não pode estar no futuro.")
        except ValueError:
            pendencias.append("Informe a data da fonte no formato AAAA-MM-DD.")
        entrada["tensao_informada"] = str(dados.get("tensao_informada") or "")
        if entrada["tensao_informada"] not in ("220/127 V", "380/220 V"):
            pendencias.append("Tensão no endereço não informada.")
        esperada = {"127/220 V": "220/127 V", "220/380 V": "380/220 V"}.get(rede.get("tensao_fornecimento"), rede.get("tensao_fornecimento"))
        if entrada["tensao_informada"] in ("220/127 V", "380/220 V") and entrada["tensao_informada"] != esperada:
            pendencias.append("A tensão informada difere da tensão dos parâmetros do projeto.")
        entrada["atendimento_confirmado"] = dados.get("atendimento_confirmado") is True
        entrada["conferido"] = dados.get("conferido") is True
        if not entrada["atendimento_confirmado"]:
            pendencias.append("Atendimento da Elektro neste endereço não confirmado.")
        if not entrada["conferido"]:
            pendencias.append("A aplicabilidade da fonte ao endereço não foi conferida.")
    return {"escopo": "Evidência declarada de atendimento e tensão por endereço",
        "projeto": projeto, "responsavel": responsavel,
        "registrado_em_utc": datetime.now(timezone.utc).isoformat(),
        "assinatura_contexto": endereco_contexto(rede, perfil),
        "local": {"uf": rede.get("uf"), "municipio": rede.get("municipio")},
        "entradas": entrada, "pendencias": list(dict.fromkeys(pendencias)),
        "status": "pendente" if pendencias else "evidencia_declarada_completa",
        "aprovado": False, "homologado": False}


def endereco_situacao(salvo, rede, perfil):
    if not isinstance(salvo, dict):
        return "Não registrado"
    if salvo.get("assinatura_contexto") != endereco_contexto(rede, perfil):
        return "Desatualizado — localidade, tensão ou perfil mudaram"
    return "Evidência declarada completa — exige validação técnica" if salvo.get("status") == "evidencia_declarada_completa" else "Pendente de dados ou conferência"


def endereco_linhas_registro(salvo):
    """Apresentação legível sem modificar a evidência ou o JSON exportado."""
    entrada = salvo.get("entradas") or {}
    local = salvo.get("local") or {}
    def valor(campo):
        return str(entrada.get(campo) or "Não informado")
    def confirmacao(campo):
        if campo not in entrada:
            return "Não informado"
        return "Sim" if entrada[campo] is True else "Não"
    data = valor("data_fonte")
    try:
        data = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        pass
    pares = [("UF", local.get("uf") or "Não informada"),
        ("Município", local.get("municipio") or "Não informado"),
        ("Usuário sem dados do endereço", confirmacao("sem_dados")),
        ("Endereço do imóvel", valor("endereco")),
        ("Fonte da informação", valor("fonte")),
        ("Protocolo ou referência documental", valor("referencia")),
        ("Data da informação", data),
        ("Tensão informada", valor("tensao_informada")),
        ("Atendimento confirmado na fonte", confirmacao("atendimento_confirmado")),
        ("Correspondência da fonte com o endereço conferida", confirmacao("conferido"))]
    return [{"Campo": campo, "Informação salva": informacao} for campo, informacao in pares]


def endereco_renderizar(rede, perfil, salvo, salvar, chave, projeto, responsavel):
    import streamlit as st
    aviso_salvo = chave("atendimento_salvo_aviso")
    if st.session_state.pop(aviso_salvo, False):
        st.success('Registro salvo. Resumo atualizado; será recuperado ao reabrir o projeto.')
    with st.expander("Atendimento e tensão por endereço — Elektro"):
        st.caption("O município vinculado ao perfil não confirma o atendimento ou a tensão de cada endereço. Registre a fonte aplicável ao imóvel.")
        if isinstance(salvo, dict):
            st.write("Registro salvo: " + endereco_situacao(salvo, rede, perfil))
            st.caption("Data do registro: " + str(salvo.get("registrado_em_utc")) + " (UTC)")
            st.table(endereco_linhas_registro(salvo))
            for item in salvo.get("pendencias") or []:
                st.caption("• " + item)
            st.download_button("Baixar registro de atendimento salvo (JSON)", data=json.dumps(salvo, ensure_ascii=False, indent=2),
                file_name="Atendimento_Endereco_Elektro.json", mime="application/json", key=chave("atendimento_exportar"))
        escopo = endereco_contexto(rede, perfil)[:20]
        def k(campo):return chave("atendimento_" + escopo + "_" + campo)
        modo = st.radio("Informações do endereço", ["Não tenho esses dados", "Informar fonte e tensão do endereço"], key=k("modo"))
        dados = {"sem_dados": modo == "Não tenho esses dados"}
        if dados["sem_dados"]:
            st.info("Você pode continuar a prévia de demanda. Atendimento e tensão ficam pendentes; nenhum valor será presumido.")
        else:
            for campo, rotulo in (("endereco", "Endereço completo do imóvel"), ("fonte", "Fonte: documento ou resposta da distribuidora"),
                ("referencia", "Protocolo, link ou referência documental"), ("data_fonte", "Data da informação (AAAA-MM-DD)")):
                dados[campo] = st.text_input(rotulo, key=k(campo))
            dados["tensao_informada"] = st.selectbox("Tensão informada para este endereço", ["Não informada", "220/127 V", "380/220 V"], key=k("tensao"))
            dados["atendimento_confirmado"] = st.checkbox("A fonte confirma atendimento da Neoenergia Elektro neste endereço", key=k("atendido"))
            assinatura = hashlib.sha256(json.dumps(dados, sort_keys=True).encode()).hexdigest()[:20]
            dados["conferido"] = st.checkbox("Conferi a fonte e sua correspondência com este endereço", key=k("conferido_" + assinatura))
        registro = endereco_registrar(rede, perfil, dados, projeto, responsavel)
        for item in registro["pendencias"]:
            st.caption("• " + item)
        if not registro["pendencias"]:
            st.info("Evidência declarada completa. A validação técnica permanece pendente.")
        st.caption("Este registro não altera a tensão do projeto, as confirmações existentes, os bloqueios normativos ou o DG.")
        if st.button("Salvar atendimento e tensão no projeto", key=k("salvar")):
            try:
                salvar(registro)

            except Exception as erro:
                st.error(f"Não foi possível salvar: {erro}")
            else:
                st.session_state[aviso_salvo] = True
                st.rerun()


# ========================================================================
# conferencia_entrada_qdc_elektro
# ========================================================================
"""Conferência integrada ao QDC, sem aplicar DG, cabos ou materiais."""
import hashlib
import json
pass # Referência interna consolidada em normativo_elektro.
pass # Referência interna consolidada em normativo_elektro.


def entrada_qdc_assinatura_registro(registro):
    return hashlib.sha256(json.dumps({k: registro.get(k) for k in
        ("assinatura_contexto_projeto", "demanda_integrada", "componentes", "dados_ramal", "selecoes_informadas")},
        sort_keys=True, default=str).encode()).hexdigest()


def entrada_qdc_renderizar(resultado, chave_projeto, contexto=None, salvo=None, salvar=None, projeto=None):
    import streamlit as st
    aviso_salvo = chave_projeto("entrada_salva_aviso")
    if st.session_state.pop(aviso_salvo, False):
        st.success('Conferência salva no projeto. Resumo atualizado; ao reabrir, a confirmação técnica deverá ser refeita.')
    auditoria = resultado.get("enquadramento_elektro") or {}
    candidato = auditoria.get("candidato") or {}
    salvo = salvo if isinstance(salvo, dict) else None
    contexto_igual = bool(salvo and salvo.get("assinatura_contexto_projeto") == contexto
        and salvo.get("demanda_integrada") == resultado)
    if salvo:
        with st.expander("Última conferência de entrada e ramal salva no projeto"):
            st.caption("Registro de " + str(salvo.get("registrado_em_utc", "data não informada")) + " (UTC)")
            if contexto_igual:
                st.info("Registro histórico correspondente às cargas e ao contexto atuais. Confira os dados do ramal antes de reutilizar.")
            else:
                st.warning("Conferência desatualizada: as cargas, o perfil ou o contexto do projeto mudaram. Faça nova conferência.")
            historico = salvo.get("verificacao_ramal") or {}
            st.write("Resultado salvo: " + str(historico.get("status", "pendente")))
            if historico.get("criterios"):
                st.table(historico["criterios"])
            st.caption("Registro histórico sem aprovação técnica; não aplica DG ou alimentador.")
            st.download_button("Baixar última conferência salva (JSON)", data=json.dumps(salvo, ensure_ascii=False, indent=2, allow_nan=False),
                file_name="Conferencia_Entrada_Ramal_Elektro_Salva.json", mime="application/json", key=chave_projeto("entrada_salva_json"))
    with st.expander("Conferir entrada e ramal Elektro no QDC — teste"):
        if auditoria.get("status") != "candidato" or auditoria.get("pendencias") or candidato.get("modalidade") != "Trifásico":
            st.info("Esta etapa exige categoria trifásica candidata fora das faixas bloqueadas, com contexto e dados completos. A demanda pode ser consultada; a conferência de entrada e ramal permanece pendente.")
            return
        st.caption(f"Categoria candidata {candidato.get('categoria')} — disjuntor de referência da tabela: {candidato.get('disjuntor_tabela_a')} A. Não aplicado como DG do projeto.")
        # O escopo inclui todo o cálculo atual: alterações das cargas ou do contexto
        # trocam as chaves e não reaproveitam dados confirmados para outro cenário.
        escopo = hashlib.sha256(json.dumps([resultado, contexto], sort_keys=True, default=str).encode()).hexdigest()[:20]
        def chave(campo):
            return chave_projeto(f"qdc_elektro_{escopo}_{campo}")
        # Recupera valores somente no mesmo contexto; a confirmação não é restaurada.
        if contexto_igual:
            selecoes_salvas = salvo.get("selecoes_informadas") or {}
            dados_salvos = salvo.get("dados_ramal") or {}
            defaults = dict(selecoes_salvas)
            defaults.update({k: v for k, v in dados_salvos.items() if k not in ("confirmado", "sem_dados")})
            defaults["modo"] = "Não tenho esses dados" if dados_salvos.get("sem_dados") else "Informar dados para conferência"
            for campo, valor in defaults.items():
                if chave(campo) not in st.session_state:
                    st.session_state[chave(campo)] = valor
        tipo = st.selectbox("Tipo do ramal de entrada", ["Não informado", "Embutido", "Subterrâneo"], key=chave("tipo"))
        isolacao_entrada = st.selectbox("Isolação do ramal de entrada", ["Não informada", "XLPE/HEPR", "PVC"], key=chave("isolacao_entrada"))
        isolacao = st.selectbox("Isolação do ramal de distribuição", ["Não informada", "XLPE/HEPR", "PVC"], key=chave("isolacao_distribuicao"))
        componentes = componentes_consultar_componentes(auditoria, tipo, isolacao_entrada, isolacao)
        if componentes.get("linhas"):
            st.table(componentes["linhas"])
        for nome, valor in componentes.get("selecoes", {}).items():
            st.write(f"**{nome}:** {valor}")
        for item in componentes.get("pendencias", []):
            st.caption("• " + item)
        st.markdown(f"[Consultar Tabela 3 na fonte oficial]({componentes_URL_FONTE})")
        modo = st.radio("Dados para conferir o ramal", ["Não tenho esses dados", "Informar dados para conferência"], key=chave("modo"))
        dados = {"sem_dados": modo == "Não tenho esses dados", "confirmado": False}
        if dados["sem_dados"]:
            st.info("Capacidade e queda de tensão aguardam os dados técnicos. Nenhum valor será presumido.")
        else:
            st.caption("Informe valores documentados pelo responsável técnico. Zero ou campo vazio significa dado desconhecido.")
            for campo, rotulo in (("metodo", "Método de instalação e condições reais"), ("fonte", "Fonte técnica: fabricante, documento, revisão e tabela/página")):
                dados[campo] = st.text_input(rotulo, key=chave(campo))
            for campo, rotulo in (
                ("corrente_a", "Corrente de projeto do trecho crítico (A)"),
                ("iz_corrigida_a", "Capacidade de condução já corrigida — Iz (A)"),
                ("comprimento_m", "Comprimento de ida do ramal (m)"),
                ("coeficiente_mv_am", "Coeficiente de queda aplicável ao circuito (mV/A/m)"),
                ("tensao_v", "Tensão de referência do trecho (V)"),
                ("limite_percentual", "Limite de queda disponível para este trecho (%)")):
                dados[campo] = st.number_input(rotulo, min_value=0.0, value=0.0, format="%.3f", key=chave(campo))
            st.caption("O coeficiente deve incorporar a configuração do circuito, fator de potência e temperatura. Não repita multiplicadores já incorporados. O limite deve considerar a queda acumulada nos demais trechos.")
            completos = bool(dados["metodo"].strip() and dados["fonte"].strip()) and all(dados[k] > 0 for k in ("corrente_a", "iz_corrigida_a", "comprimento_m", "coeficiente_mv_am", "tensao_v", "limite_percentual")) and bool(componentes.get("selecoes", {}).get("Ramal de distribuição"))
            assinatura = hashlib.sha256(json.dumps([dados, componentes], sort_keys=True, default=str).encode()).hexdigest()[:20]
            confirmado = st.checkbox("Conferi a aplicabilidade dos dados ao cabo, circuito e condições do trecho", disabled=not completos, key=chave("confirmacao_" + assinatura))
            dados["confirmado"] = bool(completos and confirmado)
        ramal = ramal_verificar_ramal(auditoria, componentes, dados)
        if ramal.get("criterios"):
            st.table(ramal["criterios"])
        for item in ramal.get("pendencias", []):
            st.caption("• " + item)
        if ramal["status"] == "nao_atende":
            st.warning("Um ou mais critérios não atendem aos dados informados. Revise o dimensionamento com o responsável técnico.")
        elif ramal["status"] == "criterios_informados_atendidos":
            st.info("Os critérios de capacidade e queda atendem aos dados informados. A validação completa da entrada e do alimentador permanece pendente.")
        st.caption("Não verifica curto-circuito, atuação da proteção, neutro, PE ou aterramento. Não aplica DG, cabos ou materiais ao projeto.")
        registro = {"escopo": "Conferência de entrada e ramal no QDC — teste", "aprovado": False, "demanda_integrada": resultado, "componentes": componentes, "dados_ramal": dados, "verificacao_ramal": ramal}
        registro["assinatura_contexto_projeto"] = contexto
        registro["projeto"] = projeto
        registro["selecoes_informadas"] = {"tipo": tipo, "isolacao_entrada": isolacao_entrada, "isolacao_distribuicao": isolacao}
        if salvo and contexto_igual and entrada_qdc_assinatura_registro(salvo) != entrada_qdc_assinatura_registro(registro):
            st.warning("Os dados ou a confirmação do ramal diferem do registro salvo. Reconfira e salve um novo registro.")
        if salvar is not None and st.button("Salvar conferência de entrada e ramal no projeto", key=chave("salvar")):
            from datetime import datetime, timezone
            registro["registrado_em_utc"] = datetime.now(timezone.utc).isoformat()
            try:
                salvar(registro)

            except Exception as erro:
                st.error(f"Não foi possível salvar a conferência: {erro}")
            else:
                st.session_state[aviso_salvo] = True
                st.rerun()
        st.download_button("Baixar conferência de entrada e ramal (JSON)", data=json.dumps(registro, ensure_ascii=False, indent=2, allow_nan=False), file_name="Conferencia_Entrada_Ramal_Elektro_QDC.json", mime="application/json", key=chave("baixar"))


# ========================================================================
# resumo_auditoria_elektro
# ========================================================================
"""Resumo somente de leitura; não concede homologação ou ativação."""
pass # Referência interna consolidada em normativo_elektro.
pass # Referência interna consolidada em normativo_elektro.


def resumo_resumir(perfil):
    if not perfil_eh_perfil_elektro(perfil):
        return []
    regras = perfil.get("regras") or {}
    atual = auditoria_assinatura(perfil)
    linhas = []
    itens = (
        ("Testes manuais de enquadramento", "registro_testes_enquadramento_elektro", "manual"),
        ("Testes automáticos da demanda integrada", "validacao_automatica_integracao_elektro", "automatico"),
        ("Conferência documental parcial", "conferencia_documental_parcial_elektro", "documental"))
    for titulo, chave, tipo in itens:
        registro = regras.get(chave) or {}
        estado = "Não registrado"
        acao = "Registrar a evidência na seção correspondente."
        if registro:
            if registro.get("assinatura_perfil") != atual:
                estado = "Desatualizado"
                acao = "Repetir a conferência com as regras atuais."
            elif tipo == "automatico" and registro.get("passou") is not True:
                estado = "Testes com falha"
                acao = "Revisar os casos com falha e executar novamente."
            elif tipo == "documental" and not all((registro.get("confirmacoes") or {}).get(k) is True for k in ("documento", "escopo_demanda", "tabela_entrada")):
                estado = "Registro incompleto"
                acao = "Conferir e registrar os três itens documentais."
            else:
                estado = "Evidência atual — escopo parcial"
                acao = "Preservar a evidência; não equivale à homologação normativa."
        linhas.append({"Etapa": titulo, "Situação": estado, "Próximo passo": acao})
    for titulo, acao in (
        ("Faixas conflitantes", "Obter esclarecimento documental e concluir a conferência técnica; manter os bloqueios."),
        ("Atendimento e tensão por endereço", "Confirmar a cobertura e a tensão local; o vínculo do município não confirma o endereço."),
        ("Demanda efetiva, DG e alimentador", "Concluir a homologação técnica antes da aplicação ao projeto."),
        ("Entrada e proteção completas", "Conferir curto-circuito, atuação da proteção, neutro, PE e aterramento.")):
        linhas.append({"Etapa": titulo, "Situação": "Pendente de homologação", "Próximo passo": acao})
    return linhas


def resumo_resumo_projeto(salvo, contexto, resultado):
    if not isinstance(salvo, dict):
        return "Não salva", "Preencher e salvar a conferência no QDC."
    if salvo.get("assinatura_contexto_projeto") != contexto or salvo.get("demanda_integrada") != resultado:
        return "Desatualizada", "Refazer a conferência com as cargas e o contexto atuais."
    status = (salvo.get("verificacao_ramal") or {}).get("status")
    if status == "nao_atende":
        return "Critério não atendido", "Revisar os dados e o dimensionamento com o responsável técnico."
    if status == "criterios_informados_atendidos":
        return "Dois critérios informados atendidos", "Concluir a validação completa; o registro não aprova a entrada."
    return "Dados ou confirmação pendentes", "Completar os dados técnicos e conferir sua aplicabilidade."


def resumo_renderizar(perfil, chave):
    import streamlit as st
    import json
    linhas = resumo_resumir(perfil)
    if not linhas:
        return
    with st.expander("Resumo da auditoria do perfil Elektro"):
        st.table(linhas)
        st.caption("Resumo das evidências cadastradas e pendências. Testes de software e conferência parcial não homologam o perfil. Mantenha em RASCUNHO até concluir a homologação.")
        st.download_button("Baixar resumo da auditoria Elektro (JSON)",
            data=json.dumps({"perfil_id": perfil.get("id"), "documento": perfil.get("documento"),
                "revisao": perfil.get("revisao"), "assinatura_perfil": auditoria_assinatura(perfil),
                "homologado": False, "etapas": linhas}, ensure_ascii=False, indent=2),
            file_name="Resumo_Auditoria_Perfil_Elektro.json", mime="application/json", key=chave)


def resumo_resumir_projeto(atendimento, rede, perfil, entrada, contexto, resultado):
    pass # Referência interna consolidada em normativo_elektro.
    estado = endereco_situacao(atendimento, rede, perfil)
    if estado == "Não registrado":
        passo = "Registrar os dados do endereço ou indicar que ainda não os possui."
    elif estado.startswith("Desatualizado"):
        passo = "Conferir a fonte para a localidade, tensão e perfil atuais e salvar novo registro."
    elif estado.startswith("Evidência declarada completa"):
        passo = "Obter validação técnica da evidência; dados declarados não aprovam o atendimento."
    else:
        passo = "Completar os dados e confirmar a fonte aplicável ao endereço."
    estado_entrada, passo_entrada = resumo_resumo_projeto(entrada, contexto, resultado)
    return [{"Etapa": "Atendimento e tensão por endereço", "Situação": estado, "Próximo passo": passo},
        {"Etapa": "Conferência de entrada e ramal", "Situação": estado_entrada, "Próximo passo": passo_entrada}]


def resumo_renderizar_projeto(atendimento, rede, perfil, entrada, contexto, resultado, projeto=None, chave=None):
    import streamlit as st
    with st.expander("Resumo da auditoria deste projeto — Elektro"):
        st.table(resumo_resumir_projeto(atendimento, rede, perfil, entrada, contexto, resultado))
        st.caption("Resumo dos registros salvos deste projeto. Evidência declarada e critérios informados atendidos exigem validação técnica. Os bloqueios normativos permanecem e não há liberação de DG ou alimentador.")

        pass # Referência interna consolidada em normativo_elektro.
        import json
        relatorio = relatorio_consolidar(atendimento, rede, perfil, entrada, contexto, resultado, projeto)
        st.caption("O relatório reúne o cálculo atual e os registros salvos, indicando dados de teste e registros desatualizados. Abra o HTML no navegador para ler ou imprimir.")
        st.download_button("Baixar relatório da auditoria do projeto (HTML)", data=relatorio_gerar_html(relatorio),
            file_name="Auditoria_Projeto_Elektro.html", mime="text/html", key=(chave + "_html") if chave else None)
        st.download_button("Baixar dados completos da auditoria do projeto (JSON)", data=json.dumps(relatorio, ensure_ascii=False, indent=2, default=str),
            file_name="Auditoria_Projeto_Elektro.json", mime="application/json", key=(chave + "_json") if chave else None)


# ========================================================================
# relatorio_auditoria_projeto_elektro
# ========================================================================
"""Relatório de leitura: contexto atual e evidências salvas, sem aprovação."""
import copy
import html
import json
from datetime import datetime, timezone
pass # Referência interna consolidada em normativo_elektro.
pass # Referência interna consolidada em normativo_elektro.



def relatorio_identificar_perfil(perfil, resultado):
    dados = {k: perfil.get(k) for k in ('id', 'documento', 'revisao', 'status', 'fonte_oficial')}
    dados['distribuidora'] = perfil.get('concessionaria') or perfil.get('distribuidora')
    partes = [str(v) for v in (dados['distribuidora'], dados['documento']) if v]
    if dados['revisao']:
        partes.append('Rev. ' + str(dados['revisao']))
    dados['nome'] = perfil.get('nome') or (' — '.join(partes) if partes else resultado.get('perfil_normativo'))
    return dados


def relatorio_comparar_contextos(rede, perfil, resultado):
    identificado = relatorio_identificar_perfil(perfil, resultado)
    candidata = ((resultado.get('enquadramento_elektro') or {}).get('candidato') or {}).get('modalidade')
    pares = [('Distribuidora', rede.get('concessionaria_manual') or rede.get('concessionaria'), identificado['distribuidora']),
        ('Perfil normativo (ID)', rede.get('perfil_normativo_id'), identificado['id']),
        ('Modalidade de fornecimento', rede.get('tipo_fornecimento'), candidata)]
    linhas = []
    for campo, atual, teste in pares:
        if atual is None or atual == '' or teste is None or teste == '':
            situacao = 'Comparação pendente — dado ausente'
        else:
            situacao = 'Correspondente' if str(atual).strip().casefold() == str(teste).strip().casefold() else 'Divergente — conferir antes da aplicação'
        linhas.append({'Campo': campo, 'Parâmetro do projeto': atual,
            'Perfil ou candidato da simulação': teste, 'Situação': situacao})
    return linhas


def relatorio_consolidar(atendimento, rede, perfil, entrada, contexto, resultado, projeto):
    etapas = resumo_resumir_projeto(atendimento, rede, perfil, entrada, contexto, resultado)
    textos = json.dumps([atendimento, (entrada or {}).get('dados_ramal')], ensure_ascii=False).casefold()
    indicios = any(p in textos for p in ('fictíci', 'fictici', 'simulação', 'simulacao', 'teste de software', 'teste-'))
    return copy.deepcopy({
        'projeto': projeto, 'emitido_em_utc': datetime.now(timezone.utc).isoformat(),
        'escopo': 'Consolidação para conferência técnica; não constitui aprovação',
        'aprovado': False, 'homologado': False, 'dg_liberado': False, 'alimentador_liberado': False,
        'indicacao_dados_teste': indicios,
        'nota_dados': 'Há indicação textual de dados fictícios ou simulação nos registros.' if indicios else 'A origem real dos dados exige conferência; ausência de indicação textual não confirma autenticidade.',
        'perfil': relatorio_identificar_perfil(perfil, resultado),
        'comparacao_contextos': relatorio_comparar_contextos(rede, perfil, resultado),
        'rede_atual': rede, 'assinatura_contexto_projeto': contexto,
        'situacao_registros': etapas, 'auditoria_perfil': resumo_resumir(perfil),
        'demanda_atual': resultado, 'atendimento_salvo': atendimento, 'entrada_ramal_salva': entrada,
        'pendencias_demanda': resultado.get('pendencias') or [],
        'pendencias_enquadramento': (resultado.get('enquadramento_elektro') or {}).get('pendencias') or [],
        'bloqueios': ['Faixas conflitantes permanecem sujeitas a conferência técnica.',
            'Validação do atendimento e tensão por endereço permanece técnica.',
            'Sem liberação automática de DG, alimentador, cabos ou materiais.',
            'Conferência de ramal limitada aos critérios informados de capacidade e queda.',
            'Curto-circuito, atuação da proteção, neutro, PE e aterramento não verificados nesta etapa.']})


def relatorio_gerar_html(relatorio):
    def esc(v):
        if v is None or v == '':return 'Não informado'
        if isinstance(v, bool):return 'Sim' if v else 'Não'
        return html.escape(str(v))
    def tabela(linhas):
        if not linhas:return '<p>Não registrado.</p>'
        cab=list(linhas[0])
        return '<table><thead><tr>'+''.join('<th>'+esc(k)+'</th>' for k in cab)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(l.get(k))+'</td>' for k in cab)+'</tr>' for l in linhas)+'</tbody></table>'
    def pares(d):return tabela([{'Campo':k,'Valor':v} for k,v in d.items()])
    r=relatorio;dem=r['demanda_atual'];aud=dem.get('enquadramento_elektro') or {};cand=aud.get('candidato') or {}
    partes=['<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Auditoria do projeto — Elektro</title><style>body{font:14px Arial,sans-serif;max-width:1000px;margin:32px auto;padding:0 20px;color:#182433}h1{font-size:25px}h2{font-size:19px;margin-top:28px}table{border-collapse:collapse;width:100%;margin:12px 0}th,td{border:1px solid #bbc5d0;padding:9px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#edf2f7}.aviso{background:#fff1d6;padding:14px}pre{white-space:pre-wrap;overflow-wrap:anywhere}@media print{body{margin:0;font-size:10pt}tr{break-inside:avoid}thead{display:table-header-group}}</style><body><h1>Auditoria do projeto — Neoenergia Elektro</h1>',
        pares({'Projeto':r['projeto'],'Emissão (UTC)':r['emitido_em_utc'],'Escopo':r['escopo']}),
        '<p class="aviso">'+esc(r['nota_dados'])+' Este relatório não aprova o projeto nem homologa o perfil.</p>',
        '<h2>Situação dos registros deste projeto</h2>',tabela(r['situacao_registros']),
        '<h2>Contexto do projeto e da simulação</h2>',
        '<p class="aviso">O perfil de teste e a categoria candidata não alteram a distribuidora, o perfil ativo ou a modalidade de fornecimento cadastrados no projeto. Diferenças abaixo exigem conferência antes de qualquer aplicação.</p>',
        tabela(r.get('comparacao_contextos') or []),
        '<h2>Perfil normativo usado na simulação</h2>',pares({'Identificação':r['perfil'].get('nome'),'Distribuidora':r['perfil'].get('distribuidora'),'ID':r['perfil'].get('id'),'Documento':r['perfil'].get('documento'),'Revisão':r['perfil'].get('revisao'),'Situação':r['perfil'].get('status'),'Fonte oficial':r['perfil'].get('fonte_oficial')}),
        '<h2>Parâmetros atuais do projeto</h2>',pares(r['rede_atual']),
        '<h2>Demanda e enquadramento atuais — teste</h2>',pares({'Situação da demanda':dem.get('status'),'Demanda aparente (kVA)':dem.get('demanda_aparente_kva'),'Situação do enquadramento':aud.get('status'),'Categoria candidata':cand.get('categoria'),'Modalidade candidata':cand.get('modalidade'),'Disjuntor de referência da tabela (A), sem aplicação como DG':cand.get('disjuntor_tabela_a')}),
        '<h2>Evidência de atendimento salva</h2>']
    at=r['atendimento_salvo']
    if at:
        partes += [pares({'Registro (UTC)':at.get('registrado_em_utc')}),tabela(endereco_linhas_registro(at))]
        partes += ['<p>'+esc(p)+'</p>' for p in at.get('pendencias') or []]
    else:partes+=['<p>Não registrado.</p>']
    en=r['entrada_ramal_salva']
    partes+=['<h2>Conferência de entrada e ramal salva — histórico</h2><p>A situação de atualização consta no resumo acima. Um registro desatualizado não representa o contexto atual.</p>']
    if en:
        partes += [pares({'Registro (UTC)':en.get('registrado_em_utc')}),pares(en.get('selecoes_informadas') or {}),pares(en.get('dados_ramal') or {}),tabela((en.get('verificacao_ramal') or {}).get('criterios') or [])]
        partes += ['<p>'+esc(p)+'</p>' for p in (en.get('verificacao_ramal') or {}).get('pendencias') or []]
    else:partes+=['<p>Não salva.</p>']
    partes+=['<h2>Pendências da demanda e enquadramento atuais</h2>']
    pend=r['pendencias_demanda']+r['pendencias_enquadramento']
    partes+=['<p>'+esc(p)+'</p>' for p in pend] if pend else ['<p>Nenhuma pendência listada neste cálculo; permanecem os bloqueios técnicos abaixo.</p>']
    partes+=['<h2>Evidências e pendências do perfil</h2>',tabela(r['auditoria_perfil']),'<h2>Bloqueios e limites da conferência</h2>']
    partes+=['<p>'+esc(p)+'</p>' for p in r['bloqueios']]
    partes+=['<h2>Memória completa da demanda atual</h2><pre>'+html.escape(json.dumps(dem,ensure_ascii=False,indent=2,default=str))+'</pre></body></html>']
    return ''.join(partes)


# Publicação operacional limitada: não declara homologação de entrada.
ativacao_ESCOPO = "Demanda trifásica residencial urbana em 220/127 V; entrada sob conferência técnica"

def ativacao_pendencias(perfil, exigir_fonte=True):
    regras = (perfil or {}).get("regras") or {}
    pendencias = []
    if not perfil_eh_perfil_elektro(perfil):
        return ["Documento Elektro incompatível."]
    uf = str(perfil.get("uf") or "").strip().upper()
    cidades = perfil.get("municipios_atendidos") or [perfil.get("municipio")]
    conhecidas = {x.casefold() for x in municipios_MUNICIPIOS_ELEKTRO.get(uf, [])}
    if not conhecidas or not cidades or any(not isinstance(x, str) or x.strip().casefold() not in conhecidas for x in cidades):
        pendencias.append("Definir UF e municípios explícitos atendidos pela Elektro.")
    fornecimento = regras.get("fornecimento") or {}
    if (regras.get("schema") not in ("autoeletrica.perfil_normativo.v1", "autoeletrica.perfil_normativo.v2")
        or regras.get("tipo_instalacao") != "Residencial individual"
        or fornecimento.get("tensao_fase_neutro_v") != 127
        or fornecimento.get("tensao_fase_fase_v") != 220):
        pendencias.append("Configurar perfil residencial individual em 220/127 V.")
    tabelas = regras.get("demanda_elektro_auditoria") or {}
    referencia = perfil_preparar_tabelas_demanda({})["demanda_elektro_auditoria"]
    if not perfil_auditar_tabelas_demanda(regras) or any(tabelas.get(k) != v for k, v in referencia.items() if k.startswith("tabela_")):
        pendencias.append("Cadastrar e conferir todas as tabelas de demanda Elektro desta revisão.")
    assinatura = auditoria_assinatura(perfil)
    registro = regras.get(validacao_CHAVE) or {}
    if not registro.get("passou") or registro.get("assinatura_perfil") != assinatura:
        pendencias.append("Executar e registrar novamente os testes da demanda integrada.")
    # Não confiar somente no booleano persistido pelo cliente.
    if not pendencias and not validacao_executar(perfil, "validação interna").get("passou"):
        pendencias.append("O motor atual não passou nos testes obrigatórios.")
    doc = regras.get(documental_CHAVE) or {}
    if doc.get("assinatura_perfil") != assinatura or not all((doc.get("confirmacoes") or {}).get(k) is True for k in ("documento", "escopo_demanda", "tabela_entrada")):
        pendencias.append("Registrar a conferência documental para as regras atuais.")
    if exigir_fonte and regras.get("fonte_conferida") is not True:
        pendencias.append("Confirmar a fonte oficial e o escopo operacional limitado.")
    return pendencias


def ativacao_calcular_automatica(tabela, rede, perfil, potencia):
    resultado = integracao_calcular_integrada(tabela, rede, perfil, potencia)
    resultado.update(metodo=rede.get("metodo_demanda"),
                     perfil_normativo="Neoenergia Elektro — DIS-NOR-030 Rev. 07",
                     elektro_operacional=True, escopo_normativo=ativacao_ESCOPO,
                     observacao="Perfil operacional ativo. DG, entrada e alimentador aguardam conferência técnica.")
    pendencias = ativacao_pendencias(perfil) + list(resultado.get("pendencias") or [])
    if str(perfil.get("status") or "").upper() != "ATIVO":
        pendencias.append("Perfil Elektro ainda não ativo.")
    if str(rede.get("municipio") or "").strip().casefold() == perfil_MUNICIPIO_TENSAO_ESPECIAL.casefold():
        pendencias.append("São João da Boa Vista excluído do enquadramento automático; conferir atendimento e tensão.")
    if rede.get("tipo_fornecimento") != "Trifásico" or potencia.get("total_w", 0) <= 18000:
        pendencias.append("Demanda operacional restrita ao atendimento trifásico acima de 18 kW; conferir os demais casos tecnicamente.")
    if pendencias:
        resultado["demanda_aparente_kva"] = None
        resultado["enquadramento_elektro"] = {"pendencias": pendencias, "candidato": None, "aprovado": False}
    resultado["pendencias"] = list(dict.fromkeys(pendencias + resultado.get("pendencias", [])))
    resultado["pendencias"].append("Padrão de entrada, DG e alimentador exigem conferência técnica; não liberados automaticamente.")
    resultado["status"] = "elektro_integracao_pendente"
    return resultado
