
import math

DISJUNTORES_PADRAO = [10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125]

def _float(valor, padrao=0.0):
    try:
        return float(valor)
    except Exception:
        return float(padrao)

def potencia_instalada(tabela_editada):
    total_ilum = 0.0
    total_tug = 0.0
    total_tue = 0.0
    for row in tabela_editada or []:
        qi = int(_float(row.get("Qtd Ilum.", 0)))
        qt = int(_float(row.get("Qtd TUG", row.get("TUGs (Qtd)", 0))))
        qe = int(_float(row.get("Qtd TUE", 0)))
        pi = _float(row.get("Pot. Unit. Ilum (W)", row.get("Pot. Unit. Ilum (VA)", 0)))
        pt = _float(row.get("Pot. Unit. TUG (W)", row.get("Pot. Unit. TUG (VA)", 0)))
        pe = _float(row.get("Pot. Unit. TUE (W)", row.get("Pot. Unit. TUE (VA)", 0)))
        total_ilum += qi * pi
        total_tug += qt * pt
        total_tue += qe * pe
    return {
        "iluminacao_w": total_ilum,
        "tug_w": total_tug,
        "tue_w": total_tue,
        "total_w": total_ilum + total_tug + total_tue,
    }

def corrente_demanda_equivalente(potencia_demanda_w, tipo_fornecimento, tensao_fornecimento):
    p = max(0.0, _float(potencia_demanda_w))
    tipo = str(tipo_fornecimento or "")
    tensao = str(tensao_fornecimento or "")

    if p <= 0:
        return 0.0

    if tipo == "Monofásico":
        v = 127.0 if tensao == "127 V" else 220.0 if tensao == "220 V" else None
        return None if not v else p / v

    if tipo == "Bifásico":
        if tensao == "127/220 V":
            return p / (2.0 * 127.0)
        if tensao == "220 V":
            return p / 220.0
        return None

    if tipo == "Trifásico":
        vlinha = 220.0 if tensao == "127/220 V" else 380.0 if tensao == "220/380 V" else None
        return None if not vlinha else p / (math.sqrt(3.0) * vlinha)

    return None

def proximo_disjuntor(corrente_a):
    if corrente_a is None:
        return None
    corrente = max(0.0, _float(corrente_a))
    for valor in DISJUNTORES_PADRAO:
        if valor >= corrente:
            return valor
    return None

def calcular_demanda_qdc(tabela_editada, parametros_rede):
    rede = dict(parametros_rede or {})
    pot = potencia_instalada(tabela_editada)
    metodo = str(rede.get("metodo_demanda", ""))

    if metodo.startswith("Automático"):
        return {
            **pot,
            "status": "aguardando_perfil",
            "metodo": metodo,
            "fator_demanda_pct": None,
            "potencia_demanda_w": None,
            "corrente_demanda_a": None,
            "disjuntor_geral_a": None,
            "tipo_fornecimento": rede.get("tipo_fornecimento", "A definir"),
            "tensao_fornecimento": rede.get("tensao_fornecimento", "A definir"),
            "observacao": "Perfil normativo automático ainda não cadastrado/validado."
        }

    fator = min(100.0, max(0.0, _float(rede.get("fator_demanda_manual", 100.0), 100.0)))
    demanda = pot["total_w"] * fator / 100.0
    corrente = corrente_demanda_equivalente(
        demanda,
        rede.get("tipo_fornecimento"),
        rede.get("tensao_fornecimento"),
    )
    dg = proximo_disjuntor(corrente)

    if corrente is None:
        status = "fornecimento_incompleto"
    elif dg is None:
        status = "acima_da_faixa"
    else:
        status = "ok"

    return {
        **pot,
        "status": status,
        "metodo": metodo,
        "fator_demanda_pct": fator,
        "potencia_demanda_w": demanda,
        "corrente_demanda_a": corrente,
        "disjuntor_geral_a": dg,
        "tipo_fornecimento": rede.get("tipo_fornecimento", "A definir"),
        "tensao_fornecimento": rede.get("tensao_fornecimento", "A definir"),
        "observacao": (
            "Pré-dimensionamento: validar perfil da concessionária, alimentador, "
            "capacidade de condução, queda de tensão, curto-circuito e coordenação."
        )
    }
