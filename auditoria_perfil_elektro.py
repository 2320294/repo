"""Evidências de testes de software; não constituem homologação normativa."""
from datetime import datetime, timezone
from hashlib import sha256
import json

CHAVE = "registro_testes_enquadramento_elektro"
CASOS = (
    (12.048, "B1", "Bifásico", 63),
    (14.348, None, "Conferência técnica", None),
    (18.000, None, "Conferência técnica", None),
    (18.948, "T0", "Trifásico", 50),
)

def assinatura(perfil):
    regras = dict(perfil.get("regras") or {})
    regras.pop(CHAVE, None)
    regras.pop("validacao_automatica_integracao_elektro", None)
    regras.pop("conferencia_documental_parcial_elektro", None)
    dados = {k: perfil.get(k) for k in ("concessionaria", "documento", "revisao", "uf", "fonte_oficial", "municipios_atendidos", "municipio")}
    dados["regras"] = regras
    return sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()

def registrar(perfil, email):
    return {"data_utc": datetime.now(timezone.utc).isoformat(), "registrado_por": email,
            "assinatura_perfil": assinatura(perfil), "local_teste": "Guarujá/SP",
            "evidencia": "Conferência manual dos prints dos testes de software de 02/10/2026",
            "casos": [{"carga_kw": kw, "categoria": cat, "modalidade": mod,
                       "disjuntor_a": amp} for kw, cat, mod, amp in CASOS],
            "homologado": False}

def registro_atual(perfil):
    registro = (perfil.get("regras") or {}).get(CHAVE) or {}
    return bool(registro) and registro.get("assinatura_perfil") == assinatura(perfil)
