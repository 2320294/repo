
CHAVE_PARAMETROS_REDE = "__parametros_rede__"

UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"
]

# Cadastro inicial para a arquitetura da Fase 13.6 Rev.12.
# A cobertura municipal e os critérios de demanda serão ampliados
# gradualmente, sem espalhar regras pelo restante do sistema.
CONCESSIONARIAS_POR_UF = {
    "AL": ["Equatorial Alagoas"],
    "AP": ["CEA Equatorial"],
    "BA": ["Neoenergia Coelba"],
    "CE": ["Enel Distribuição Ceará"],
    "DF": ["Neoenergia Brasília"],
    "ES": ["EDP Espírito Santo"],
    "GO": ["Equatorial Goiás"],
    "MA": ["Equatorial Maranhão"],
    "MG": ["Cemig Distribuição"],
    "PA": ["Equatorial Pará"],
    "PE": ["Neoenergia Pernambuco"],
    "PI": ["Equatorial Piauí"],
    "RJ": ["Enel Distribuição Rio", "Light"],
    "RN": ["Neoenergia Cosern"],
    "SP": [
        "CPFL Paulista",
        "CPFL Piratininga",
        "Enel Distribuição São Paulo",
        "EDP São Paulo"
    ],
}

OUTRA_CONCESSIONARIA = "Outra / Não cadastrada"


def concessionarias_da_uf(uf):
    opcoes = list(
        CONCESSIONARIAS_POR_UF.get(
            str(uf or "").upper(),
            []
        )
    )

    if OUTRA_CONCESSIONARIA not in opcoes:
        opcoes.append(
            OUTRA_CONCESSIONARIA
        )

    return opcoes


def parametros_rede_padrao():
    return {
        "uf": "",
        "municipio": "",
        "concessionaria": OUTRA_CONCESSIONARIA,
        "concessionaria_manual": "",
        "tipo_fornecimento": "A definir",
        "tensao_fornecimento": "A definir",
        "metodo_demanda": (
            "Automático pela concessionária (quando cadastrado)"
        ),
        "fator_demanda_manual": 100.0,
        "norma_concessionaria": (
            "Perfil normativo ainda não cadastrado"
        ),
        "esquema_aterramento": "Não sei",
        "icc_conhecida": False,
        "icc_qdc_ka": 0.0,
        "fabricante_protecao": "",
        "capacidade_interrupcao_dg_ka": 0.0,
        "capacidade_interrupcao_terminais_ka": 0.0,
        "referencia_seletividade": "",
        "seletividade_validada_rt": False,
        "dps_tipo": "A definir",
        "dps_uc_v": 0.0,
        "dps_up_kv": 0.0,
        "dps_in_ka": 0.0,
        "dps_imax_ka": 0.0,
        "arranjo_dps": "",
        "arranjo_dps_validado_rt": False,
        "norma_concessionaria_referencia": "",
        "requisitos_concessionaria_validados_rt": False,
    }


def normalizar_parametros_rede(valor):
    padrao = parametros_rede_padrao()
    if isinstance(valor, dict):
        padrao.update(valor)

    uf = str(
        padrao.get("uf", "")
    ).upper().strip()

    if uf not in UFS:
        uf = ""

    padrao["uf"] = uf
    padrao["municipio"] = str(
        padrao.get("municipio", "")
    ).strip()

    padrao["concessionaria"] = str(
        padrao.get(
            "concessionaria",
            OUTRA_CONCESSIONARIA
        )
    ).strip()

    padrao["concessionaria_manual"] = str(
        padrao.get(
            "concessionaria_manual",
            ""
        )
    ).strip()

    return padrao


def nome_concessionaria(parametros):
    p = normalizar_parametros_rede(
        parametros
    )

    if (
        p["concessionaria"]
        == OUTRA_CONCESSIONARIA
    ):
        return (
            p["concessionaria_manual"]
            or OUTRA_CONCESSIONARIA
        )

    return p["concessionaria"]


def descricao_localidade(parametros):
    p = normalizar_parametros_rede(
        parametros
    )

    municipio = (
        p["municipio"]
        or "Município não informado"
    )

    uf = (
        p["uf"]
        or "UF não informada"
    )

    return f"{municipio} / {uf}"


def perfil_normativo_disponivel(parametros):
    """
    Na Fase 13.6 Rev.12 a estrutura de perfis está pronta, mas os métodos
    de demanda ainda não são executados. Retorna False para impedir
    que o sistema trate um critério não implementado como definitivo.
    """
    return False
