"""Consulta documental isolada da Tabela 3, página 63, DIS-NOR-030 Rev.07.

Notações transcritas em mm². Não calcula capacidade de condução, queda de
tensão, proteção ou materiais de execução; não altera o projeto.
"""

from copy import deepcopy
import math

FONTE = "DIS-NOR-030 Rev. 07 — Tabela 3, página 63/142 — 220/127 V"
URL_FONTE = "https://www.neoenergia.com/documents/d/sp/dis-nor-030-rev07?download=true"


def _linha(disjuntor, conexao, embutido, subterraneo, distribuicao, caixa,
           eletroduto, motores, medicao="Direta"):
    return {"disjuntor_a": disjuntor, "conexao_aereo": conexao,
            "entrada_embutida": embutido, "entrada_subterranea": subterraneo,
            "distribuicao": distribuicao, "caixa": caixa, "medicao": medicao,
            "eletroduto_fases_neutro": eletroduto,
            "eletroduto_aterramento": '3/4 pol.', "limite_motor_cv": motores}


TABELA_3 = {
    "M1": _linha(63, ["10+10 CU CONC", "16+16 AL CONC"],
        {"Distribuidora": "FORNECIMENTO DISTRIBUIDORA"},
        {"XLPE/HEPR": "10/10 CU XLPE/HEPR"},
        {"XLPE/HEPR": "10/10/10 CU XLPE/HEPR", "PVC": "16/16/16 CU PVC"},
        "Monofásica ou Polifásica", '1 1/4 pol.', {"FN": 2, "FF": None, "3F": None}),
    "B1": _linha(63, ["2x16+16 AL MULT"],
        {"Distribuidora": "FORNECIMENTO DISTRIBUIDORA"},
        {"XLPE/HEPR": "2x10/10 CU XLPE/HEPR"},
        {"XLPE/HEPR": "2x10/10/10 CU XLPE/HEPR", "PVC": "2x16/16/16 CU PVC"},
        "Polifásica", '1 1/4 pol.', {"FN": 2, "FF": 2, "3F": None}),
    "T0": _linha(50, ["3x16+16 AL MULT"],
        {"Distribuidora": "FORNECIMENTO DISTRIBUIDORA"},
        {"XLPE/HEPR": "3x10/10 CU XLPE/HEPR"},
        {"XLPE/HEPR": "3x10/10/10 CU XLPE/HEPR", "PVC": "3x16/16/16 CU PVC"},
        "Polifásica", '1 1/4 pol.', {"FN": 1, "FF": 2, "3F": 5}),
    "T1": _linha(63, ["3x16+16 AL MULT"],
        {"Distribuidora": "FORNECIMENTO DISTRIBUIDORA"},
        {"XLPE/HEPR": "3x16/16 CU XLPE/HEPR"},
        {"XLPE/HEPR": "3x16/16/16 CU XLPE/HEPR", "PVC": "3x25/25/16 CU PVC"},
        "Polifásica", '1 1/4 pol.', {"FN": 2, "FF": 5, "3F": 20}),
    "T2": _linha(100, ["3x25+25 AL MULT"],
        {"XLPE/HEPR": "3x25/25 CU XLPE/HEPR", "PVC": "3x35/35 CU PVC"},
        {"XLPE/HEPR": "3x35/35 CU XLPE/HEPR"},
        {"XLPE/HEPR": "3x35/35/16 CU XLPE/HEPR", "PVC": "3x35/35/16 CU PVC"},
        "Polifásica* ou Caixa para Medidor 200 A ou Módulo de Policarbonato",
        '2 pol.', {"FN": 3, "FF": 7.5, "3F": 25}),
    "T3": _linha(125, ["3x35+35 AL MULT"],
        {"XLPE/HEPR": "3x35/35 CU XLPE/HEPR", "PVC": "3x50/50 CU PVC"},
        {"XLPE/HEPR": "3x50/50 CU XLPE/HEPR"},
        {"XLPE/HEPR": "3x50/50/16 CU XLPE/HEPR", "PVC": "3x70/70/35 CU PVC"},
        "Caixa para Medidor 200 A ou Módulo de Policarbonato",
        '2 pol.', {"FN": 7.5, "FF": 10, "3F": 30}),
    "T4": _linha(150, ["3x50+50 AL MULT"],
        {"XLPE/HEPR": "3x50/50 CU XLPE/HEPR", "PVC": "3x70/70 CU PVC"},
        {"XLPE/HEPR": "3x70/70 CU XLPE/HEPR"},
        {"XLPE/HEPR": "3x70/70/35 CU XLPE/HEPR"},
        "Caixa para Medidor 200 A ou Módulo de Policarbonato",
        '2 pol.', {"FN": 7.5, "FF": 10, "3F": 30}),
    "T5": _linha(200, ["3x70+50 AL MULT"],
        {"XLPE/HEPR": "3x70/70 CU XLPE/HEPR"},
        {"XLPE/HEPR": "3x95/95 CU XLPE/HEPR"},
        {"XLPE/HEPR": "3x95/95/50 CU XLPE/HEPR"},
        "Caixa para TC", '2 1/2 pol.', {"FN": 7.5, "FF": 10, "3F": 50}, "Indireta"),
}


def consultar_componentes(auditoria, tipo_entrada="Não informado",
                          isolacao_entrada="Não informada", isolacao_distribuicao="Não informada"):
    """Exibe alternativas documentais apenas para candidato consistente.

    Uma opção não informada não é substituída pela primeira alternativa.
    """
    resultado = {"status": "pendente", "linhas": [], "selecoes": {},
                 "pendencias": [], "aprovado": False, "fonte": FONTE}
    a = auditoria or {}
    candidato = a.get("candidato") or {}
    categoria = candidato.get("categoria")
    linha = TABELA_3.get(categoria)
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
            from enquadramento_elektro import FAIXAS_TRIFASICAS
            valido = kw > 18 and candidato.get("modalidade") == "Trifásico" and any(
                cat == categoria and minimo <= demanda <= maximo
                for cat, minimo, maximo, _ in FAIXAS_TRIFASICAS)
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
