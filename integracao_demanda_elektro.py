"""Demanda Elektro no fluxo do projeto, sem liberar proteções ou alimentador."""
from demanda_elektro import calcular_previa
from enquadramento_elektro import auditar_enquadramento
from neoenergia_elektro import eh_perfil_elektro
from perfis_normativos import perfil_atende_municipio

METODO = "Elektro — teste integrado de demanda (sem DG)"

def calcular_integrada(tabela, rede, perfil, potencia):
    resultado = {**potencia, "status": "elektro_integracao_pendente", "metodo": METODO,
        "potencia_demanda_w": None, "potencia_demanda_parcial_w": None,
        "demanda_aparente_kva": None, "corrente_demanda_a": None,
        "disjuntor_geral_a": None, "fator_demanda_pct": None,
        "tipo_fornecimento": rede.get("tipo_fornecimento", "A definir"),
        "tensao_fornecimento": rede.get("tensao_fornecimento", "A definir"),
        "detalhes_demanda": [], "pendencias": [], "aprovado": False,
        "observacao": "Teste integrado de demanda Elektro: não libera corrente, DG ou alimentador."}
    if not eh_perfil_elektro(perfil) or str((perfil or {}).get("status", "")).upper() not in ("RASCUNHO", "VALIDADO", "ATIVO"):
        resultado["pendencias"] = ["Selecione um rascunho Elektro DIS-NOR-030 Rev. 07 disponível para o teste."]
        return resultado
    if not perfil_atende_municipio(perfil, rede.get("uf"), rede.get("municipio")):
        resultado["pendencias"] = ["UF/município não vinculado ao perfil Elektro do teste."]
        return resultado
    resultado["perfil_normativo_id"] = perfil.get("id")
    resultado["perfil_normativo"] = "Neoenergia Elektro — DIS-NOR-030 Rev. 07 (teste integrado)"
    previa = calcular_previa(tabela, perfil.get("regras"))
    contexto = dict(rede.get("contexto_elektro_teste") or {})
    contexto["municipio_vinculado"] = True
    contexto["tensao"] = "220/127 V" if rede.get("tensao_fornecimento") == "127/220 V" else "Não informada"
    enquadramento = auditar_enquadramento(tabela, perfil, previa, contexto)
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
