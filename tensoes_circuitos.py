
def tensao_base_fornecimento(parametros_rede, fallback=220):
    """
    Retorna a tensão fase-neutro/base do sistema para compatibilidade
    com rotinas legadas que ainda esperam um único valor escalar.
    """
    rede=dict(parametros_rede or {})
    tensao=str(rede.get("tensao_fornecimento","") or "").strip()

    if tensao=="127 V":
        return 127
    if tensao=="220 V":
        return 220
    if tensao=="127/220 V":
        return 127
    if tensao=="220/380 V":
        return 220

    try:
        return int(fallback)
    except Exception:
        return 220


def tensao_circuito(tipo, parametros_rede, fallback=220):
    """
    Tensão nominal preliminar por circuito, derivada do fornecimento.

    Convenção atual do AutoElétrica:
    - iluminação/TUG: tensão fase-neutro;
    - TUE: tensão entre fases quando o sistema possuir duas ou mais fases.

    Essa função elimina a necessidade do antigo campo manual
    "Tensão usada nos cálculos atuais".
    """
    rede=dict(parametros_rede or {})
    tensao=str(rede.get("tensao_fornecimento","") or "").strip()
    fornecimento=str(rede.get("tipo_fornecimento","") or "").strip()
    tipo_u=str(tipo or "").upper()

    if tensao=="127 V":
        return 127

    if tensao=="220 V":
        return 220

    if tensao=="127/220 V":
        if tipo_u=="TUE" and fornecimento in {"Bifásico","Trifásico"}:
            return 220
        return 127

    if tensao=="220/380 V":
        if tipo_u=="TUE" and fornecimento in {"Bifásico","Trifásico"}:
            return 380
        return 220

    try:
        return int(fallback)
    except Exception:
        return 220
