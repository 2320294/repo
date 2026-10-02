"""Registro exportável de simulações, sem aprovação ou aplicação ao projeto."""
import json
import math
from datetime import datetime, timezone
from copy import deepcopy


def _limpar(valor):
    if isinstance(valor, dict):
        return {str(k): _limpar(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_limpar(v) for v in valor]
    if isinstance(valor, float) and not math.isfinite(valor):
        return None
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    return str(valor)


def registrar(projeto, local, perfil, entradas, cargas, previa, enquadramento, componentes, ramal):
    dados = deepcopy(entradas)
    if dados.get("ramal", {}).get("sem_dados"):
        dados["ramal"] = {"sem_dados": True, "confirmado": False}
    return _limpar({"tipo": "Simulação preliminar Elektro — sem aprovação técnica",
        "registrado_em_utc": datetime.now(timezone.utc).isoformat(),
        "projeto": projeto, "local": local,
        "perfil": {k: perfil.get(k) for k in ("id", "concessionaria", "documento", "revisao", "uf", "status")},
        "aprovado": False, "entradas": dados, "cargas_cadastradas": cargas,
        "demanda": previa, "enquadramento": enquadramento,
        "componentes_documentais": componentes, "conferencia_ramal": ramal,
        "limites": "Não aprova o padrão, não ativa o perfil e não altera o alimentador. Dados informados exigem conferência técnica."})


def exportar_json(registro):
    return json.dumps(registro, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def exportar_resumo(registro):
    linhas = [registro["tipo"], "Projeto: " + str(registro["projeto"]),
              "Local: " + str(registro["local"]), "Registro UTC: " + registro["registrado_em_utc"],
              "", registro["limites"]]
    for titulo, chave in [("Perfil e documento", "perfil"), ("Dados informados", "entradas"),
        ("Cargas cadastradas", "cargas_cadastradas"), ("Demanda", "demanda"),
        ("Enquadramento", "enquadramento"), ("Componentes documentais", "componentes_documentais"),
        ("Conferência do ramal", "conferencia_ramal")]:
        linhas.extend(["", titulo, json.dumps(registro[chave], ensure_ascii=False, indent=2, allow_nan=False)])
    return "\n".join(linhas).encode("utf-8")
