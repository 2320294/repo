"""Rastreabilidade documental parcial, independente da homologação final."""
from datetime import datetime, timezone
from auditoria_perfil_elektro import assinatura
from neoenergia_elektro import eh_perfil_elektro

CHAVE = "conferencia_documental_parcial_elektro"
FONTE = "https://www.neoenergia.com/documents/d/sp/dis-nor-030-rev07?download=true"

def registrar(perfil, email, confirmacoes, notas=""):
    if not eh_perfil_elektro(perfil):
        raise ValueError("Perfil fora do documento Elektro DIS-NOR-030 Rev. 07.")
    teste = (perfil.get("regras") or {}).get("validacao_automatica_integracao_elektro") or {}
    if not teste.get("passou") or teste.get("assinatura_perfil") != assinatura(perfil):
        raise ValueError("Execute os testes integrados com as regras atuais antes da conferência parcial.")
    if not all(confirmacoes.get(k) is True for k in ("documento", "escopo_demanda", "tabela_entrada")):
        raise ValueError("Confira os três itens documentais antes de registrar.")
    return {"data_utc": datetime.now(timezone.utc).isoformat(), "responsavel": email,
            "assinatura_perfil": assinatura(perfil), "fonte": FONTE,
            "documento": "DIS-NOR-030", "revisao": "07", "aprovacao_documento": "17/04/2026",
            "referencias": ["Identificação do documento — página 1", "Item 6.27 — páginas 47–49: demanda trifásica em kVA", "Item 6.28 e Tabela 3 — página 63: entrada Elektro 220/127 V"],
            "confirmacoes": dict(confirmacoes), "notas": str(notas).strip(),
            "escopo": "Conferência documental parcial. Não resolve conflitos, não confirma tensão por endereço e não homologa DG ou alimentador.",
            "homologado": False}
