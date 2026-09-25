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


def preparar_tabelas_demanda(regras):
    """Transcreve tabelas do Anexo II para auditoria, sem habilitar o cálculo.

    O item 6.27 aplica a demanda a instalações trifásicas; o motor de cálculo
    atual ainda não interpreta estas tabelas nem todas as cargas da Elektro.
    """
    r = deepcopy(regras or {})
    def faixas(limites, fatores):
        return [{"ate": limite, "fator": fator} for limite, fator in zip(limites, fatores)]

    r["demanda_elektro_auditoria"] = {
        "documento": DOCUMENTO, "revisao": REVISAO,
        "fonte": "Anexo II, Tabelas 6 a 16; itens 6.27 e 6.28",
        "unidade_resultado": "kVA", "aplicacao": "instalacao_trifasica",
        "tabela_6_iluminacao_tug": {"unidade_entrada": "kW", "faixas": faixas(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, None],
            [.86, .75, .66, .59, .52, .45, .40, .35, .31, .27, .24])},
        "tabela_7_chuveiros": {"faixas": faixas(
            list(range(1, 26)) + [None],
            [1, 1, .84, .76, .70, .65, .60, .57, .54, .52, .49, .48,
             .46, .45, .44, .43, .42, .41, .40, .40, .39, .39, .39, .38, .38, .38])},
        "tabela_8_boiler": {"faixas": faixas([1, 2, 3, None], [1, .72, .62, .62])},
        "tabela_9_eletrodomesticos": {"faixas": [
            {"min": 1, "max": 1, "fator": 1}, {"min": 2, "max": 4, "fator": .70},
            {"min": 5, "max": 6, "fator": .60}, {"min": 7, "max": None, "fator": .50}]},
        "tabela_10_fogoes": {"faixas": faixas(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 15, None],
            [1, .60, .48, .40, .37, .35, .33, .32, .31, .30, .28, .26])},
        "tabela_11_ar_condicionado": {"potencias": [
            {"btu_h": b, "va": va, "w": w} for b, va, w in [
                (7500, 1100, 900), (9000, 1550, 1300), (10000, 1650, 1400),
                (12000, 1900, 1600), (15000, 2100, 1900), (18000, 2860, 2600),
                (21000, 3080, 2800), (30000, 4000, 3800), (41000, 5500, 5000),
                (60000, 9000, 7500)]], "preferir_placa": True},
        "tabela_12_ar_condicionado": {"ate_quantidade": [10, 20, 30, 40, 50, 75, 100, None],
            "residencial": [1, .86, .80, .78, .75, .70, .65, .60],
            "comercial": [1, .90, .82, .80, .77, .75, .75, .75],
            "unidade_central": 1},
        "tabela_13_recarga": {"faixas": faixas([10, 20, 30, 40, 50, None],
            [1, .90, .82, .80, .77, .75])},
        "tabela_14_motores": {"maior": 1, "demais": .50,
            "partida_simultanea_agrupar": True},
        "tabela_15_especiais": {"maior": 1, "demais": .60},
        "tabela_16_bombas_hidromassagem": {"faixas": faixas(
            [1, 2, 3, None], [1, .56, .47, .39])},
        "pendencias": [
            "Integrar motor de demanda exclusivo, FP e classificacao de cargas por item 6.27.",
            "Conferir divergencia entre texto do item 6.27.5 e titulo da Tabela 10.",
            "Validar alimentador trifasico e casos de tensao local com a distribuidora."],
    }
    r["fonte_conferida"] = False
    return r


def auditar_tabelas_demanda(regras):
    """Checa independentemente marcadores que divergem do perfil CPFL."""
    d = (regras or {}).get("demanda_elektro_auditoria") or {}
    if d.get("documento") != DOCUMENTO or d.get("revisao") != REVISAO:
        return False
    try:
        return (d["tabela_6_iluminacao_tug"]["faixas"][-1]["fator"] == .24
                and d["tabela_7_chuveiros"]["faixas"][6]["fator"] == .60
                and d["tabela_9_eletrodomesticos"]["faixas"][1]["fator"] == .70
                and d["tabela_10_fogoes"]["faixas"][-1]["fator"] == .26
                and d["tabela_11_ar_condicionado"]["potencias"][0]["va"] == 1100
                and d["tabela_12_ar_condicionado"]["residencial"][1] == .86
                and d["tabela_13_recarga"]["faixas"][-1]["fator"] == .75
                and d["tabela_14_motores"]["demais"] == .50
                and d["tabela_15_especiais"]["demais"] == .60
                and d["tabela_16_bombas_hidromassagem"]["faixas"][-1]["fator"] == .39)
    except (KeyError, IndexError, TypeError):
        return False
