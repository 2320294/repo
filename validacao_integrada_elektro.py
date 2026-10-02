"""Testes executáveis de software com cargas fictícias; não homologam a norma."""
from copy import deepcopy
from datetime import datetime, timezone
from integracao_demanda_elektro import calcular_integrada, METODO
from auditoria_perfil_elektro import assinatura

CHAVE = "validacao_automatica_integracao_elektro"

def executar(perfil, email):
    casos = []
    cidade = next(iter(perfil.get("municipios_atendidos") or []), perfil.get("municipio") or "")
    rede = {"metodo_demanda": METODO, "uf": perfil.get("uf"), "municipio": cidade,
            "tensao_fornecimento": "127/220 V", "tipo_fornecimento": "Trifásico",
            "contexto_elektro_teste": {k: True for k in ("atendimento_confirmado", "urbano_individual", "cargas_conferidas", "equipamentos_conferidos")}}
    base = [{"Qtd Ilum.": 1, "Pot. Unit. Ilum (W)": 10098},
            {"Qtd TUE": 1, "Pot. Unit. TUE (W)": 350, "Equipamento TUE": "Máquina de lavar"},
            {"Qtd TUE": 1, "Pot. Unit. TUE (W)": 1000, "Equipamento TUE": "Forno elétrico"}]
    def verificar(nome, rows, parametros, categoria, demanda):
        antes = deepcopy((rows, parametros, perfil))
        try:
            r = calcular_integrada(rows, parametros, perfil, {"total_w": 0})
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
            "assinatura_perfil": assinatura(perfil), "casos": casos,
            "passou": bool(cidade) and all(c["Passou"] for c in casos),
            "homologado": False, "escopo": "Software, cargas fictícias em 220/127 V. Não confirma atendimento ou tensão no endereço."}
