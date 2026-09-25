"""Prévia isolada da demanda residencial trifásica DIS-NOR-030 Rev. 07.

Não dimensiona DG ou alimentador, não publica perfil e não altera GED-13.
Quando a planilha não informa os dados exigidos pelo item 6.27, não fecha
demanda nem supõe fator de potência ou categoria de equipamento.
"""

import math
import unicodedata

from neoenergia_elektro import auditar_tabelas_demanda


def _numero(valor):
    try:
        n = float(valor)
        return n if math.isfinite(n) else 0.0
    except (ValueError, TypeError):
        return 0.0


def _nome(texto):
    s = unicodedata.normalize("NFKD", str(texto or "").casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


def _fator(faixas, quantidade):
    for faixa in faixas:
        if "min" in faixa and quantidade < faixa["min"]:
            continue
        maximo = faixa.get("max", faixa.get("ate"))
        if maximo is None or quantidade <= maximo:
            return faixa["fator"]
    return None


def calcular_previa(tabela, regras):
    """Retorna kVA e memória apenas para dados completos e sem ambiguidades."""
    if not auditar_tabelas_demanda(regras):
        return {"status": "pendente", "demanda_kva": None,
                "pendencias": ["Tabelas da Elektro ausentes ou inconsistentes."], "detalhes": []}
    t = regras["demanda_elektro_auditoria"]
    pendencias, detalhes = [], []
    grupos = {k: [] for k in ("chuveiros", "boiler", "eletrodomesticos", "forno_eletrico", "fogoes",
                                "ar_condicionado", "bombas", "motores", "especiais", "recarga")}
    iluminacao_tug_w = 0.0
    for i, linha in enumerate(tabela or [], 1):
        local = str(linha.get("Ambiente") or f"Linha {i}").strip()
        qi = int(_numero(linha.get("Qtd Ilum.", 0)))
        qt = int(_numero(linha.get("Qtd TUG", linha.get("TUGs (Qtd)", 0))))
        qe = int(_numero(linha.get("Qtd TUE", 0)))
        wi = _numero(linha.get("Pot. Unit. Ilum (W)", linha.get("Pot. Unit. Ilum (VA)", 0)))
        wt = _numero(linha.get("Pot. Unit. TUG (W)", linha.get("Pot. Unit. TUG (VA)", 0)))
        w = _numero(linha.get("Pot. Unit. TUE (W)", linha.get("Pot. Unit. TUE (VA)", 0)))
        if min(qi, qt, qe, wi, wt, w) < 0:
            pendencias.append(f"{local}: carga ou quantidade negativa.")
            continue
        iluminacao_tug_w += qi * wi + qt * wt
        if not qe:
            continue
        nome = str(linha.get("Equipamento TUE") or linha.get("Equipamento") or "")
        n = _nome(nome)
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
            fp = _numero(linha.get("Fator de Potência TUE", linha.get("FP TUE")))
            if fp < 0 or fp > 1:
                pendencias.append(f"{local}: fator de potência fora do intervalo (0, 1].")
                fp = 0.0
            if categoria in ("eletrodomesticos", "recarga", "motores", "especiais", "ar_condicionado") and not 0 < fp <= 1:
                # Para ar-condicionado, VA de placa explícito dispensa FP.
                va_placa = _numero(linha.get("Pot. Placa TUE (VA)"))
                if categoria != "ar_condicionado" or va_placa <= 0:
                    if categoria not in ("eletrodomesticos", "ar_condicionado"):
                        pendencias.append(f"{local}: informar fator de potência/VA de placa de '{nome}'.")
            btu = int(_numero(linha.get("Capacidade TUE (BTU/h)")))
            if categoria == "ar_condicionado" and fp <= 0 and _numero(linha.get("Pot. Placa TUE (VA)")) <= 0:
                conhecidos = {item["btu_h"]: item for item in t["tabela_11_ar_condicionado"]["potencias"]}
                if btu not in conhecidos:
                    pendencias.append(f"{local}: informar VA/FP de placa ou capacidade (BTU/h) "
                                      f"da Tabela 11 para '{nome}'.")
                elif w != conhecidos[btu]["w"]:
                    pendencias.append(f"{local}: {btu} BTU/h corresponde a "
                                      f"{conhecidos[btu]['w']} W na Tabela 11, mas o projeto informa "
                                      f"{w:g} W. Conferir W ou informar VA/FP de placa.")
            for _ in range(qe):
                grupos[categoria].append({"w": w, "fp": fp, "va": _numero(linha.get("Pot. Placa TUE (VA)")),
                                          "btu": btu, "nome": nome})

    def acrescentar(categoria, itens, fator, fp=1.0, tabela_id=""):
        watts = sum(x["w"] for x in itens)
        kva = watts * fator / fp / 1000.0
        detalhes.append({"categoria": categoria, "tabela_id": tabela_id,
                         "quantidade": len(itens), "carga_w": watts, "fator": fator,
                         "fator_potencia": fp, "demanda_kva": kva})

    if iluminacao_tug_w:
        fd = _fator(t["tabela_6_iluminacao_tug"]["faixas"], iluminacao_tug_w / 1000)
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
            fd = _fator(t[tabela_chave]["faixas"], len(itens))
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
