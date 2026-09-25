"""Preparação conservadora do perfil DIS-NOR-030 Rev. 07 da Elektro.

Somente dados de fornecimento documentalmente inequívocos. Demandas e
dimensionamento de entrada exigem auditoria própria antes da ativação.
"""

from copy import deepcopy

DOCUMENTO = "DIS-NOR-030"
REVISAO = "07"
MUNICIPIO_TENSAO_ESPECIAL = "São João da Boa Vista"
FAIXAS_CONFERENCIA_KW = ((10.0, 11.0), (13.0, 18.0))


def eh_perfil_elektro(perfil):
    return (str((perfil or {}).get("concessionaria") or "").strip().casefold() == "neoenergia elektro"
            and str((perfil or {}).get("documento") or "").strip().upper() == DOCUMENTO
            and str((perfil or {}).get("revisao") or "").strip() == REVISAO)


def motivo_conferencia(potencia_w, perfil):
    if not eh_perfil_elektro(perfil):
        return ""
    kw = max(0.0, float(potencia_w or 0)) / 1000.0
    for minimo, maximo in FAIXAS_CONFERENCIA_KW:
        if minimo < kw <= maximo:
            return (f"Carga instalada de {kw:.2f} kW: enquadramento da Neoenergia Elektro "
                    f"entre {minimo:g} e {maximo:g} kW requer conferência técnica. "
                    "A DIS-NOR-030 Rev. 07 não permite escolher automaticamente uma "
                    "categoria urbana inequívoca nesta faixa.")
    return ""


def preparar_regras(regras):
    """Preserva a demanda do rascunho; insere somente o fornecimento 220/127 V."""
    r = deepcopy(regras or {})
    r.setdefault("schema", "autoeletrica.perfil_normativo.v2")
    r.setdefault("tipo_instalacao", "Residencial individual")
    f = dict(r.get("fornecimento") or {})
    f.update({
        "tensao_fase_neutro_v": 127.0,
        "tensao_fase_fase_v": 220.0,
        "limite_potencia_instalada_kw": 75.0,
        "modalidades": ["Monofásico", "Bifásico", "Trifásico"],
        # Os intervalos com conflito ficam explicitamente sem faixa.
        "faixas_modalidade_kw": [
            {"modalidade": "Monofásico", "min_kw": 0.0, "max_kw": 10.0,
             "inclui_min": True, "inclui_max": True},
            {"modalidade": "Bifásico", "min_kw": 11.0, "max_kw": 13.0,
             "inclui_min": False, "inclui_max": True},
            {"modalidade": "Trifásico", "min_kw": 18.0, "max_kw": 75.0,
             "inclui_min": False, "inclui_max": True},
        ],
        "faixas_conferencia_tecnica_kw": [
            {"min_kw": a, "max_kw": b, "inclui_min": False, "inclui_max": True}
            for a, b in FAIXAS_CONFERENCIA_KW
        ],
        "fonte_faixas": "DIS-NOR-030 Rev. 07, itens 6.2.8 e Anexo I, Tabela 3",
    })
    r["fornecimento"] = f
    r.setdefault("demanda", {})
    r["fonte_conferida"] = False
    return r
