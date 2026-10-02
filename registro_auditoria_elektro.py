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


def assinatura_contexto(cargas, parametros, perfil):
    import hashlib
    dados = _limpar({"cargas": cargas, "parametros": parametros, "perfil": perfil})
    return hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def exportar_resumo(registro):
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
