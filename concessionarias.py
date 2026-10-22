
CHAVE_PARAMETROS_REDE = "__parametros_rede__"

UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"
]

# Cadastro inicial para a arquitetura da Fase 13.6 Rev.124.
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
    "RS": ["RGE"],
    "MG": ["Cemig Distribuição", "CPFL Santa Cruz"],
    "PR": ["CPFL Santa Cruz"],
    "PA": ["Equatorial Pará"],
    "PE": ["Neoenergia Pernambuco"],
    "PI": ["Equatorial Piauí"],
    "RJ": ["Enel Distribuição Rio", "Light"],
    "RN": ["Neoenergia Cosern"],
    "SP": [
        "CPFL Paulista",
        "CPFL Piratininga",
        "CPFL Santa Cruz",
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
        "perfil_normativo_id": None,
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


def contexto_resultados_rede(rede):
    """Identidade dos parâmetros que originam demanda e alimentador."""
    campos = ("uf", "municipio", "concessionaria", "perfil_normativo_id",
              "perfil_normativo_documento", "perfil_normativo_revisao",
              "metodo_demanda", "fator_demanda_manual", "tipo_fornecimento",
              "tensao_fornecimento", "perfil_elektro_teste_id", "contexto_elektro_teste")
    from copy import deepcopy
    return deepcopy({k: (rede or {}).get(k) for k in campos})


def limpar_resultados_contexto(rede, anterior=None):
    """Descarta apenas resultados derivados incompatíveis; preserva entradas."""
    r = dict(rede or {})
    atual = contexto_resultados_rede(r)
    salvo = r.get("contexto_resultados_rede")
    mudou = anterior is not None and contexto_resultados_rede(anterior) != atual
    invalido = mudou or (salvo is not None and salvo != atual)
    # O modo de ensaio Elektro nunca aplica DG/alimentador fechado em outro fluxo.
    invalido = invalido or r.get("metodo_demanda") == "Elektro — teste integrado de demanda (sem DG)"
    demanda = r.get("demanda_fechada") or {}
    identificacao = str(demanda.get("perfil_normativo") or "").casefold()
    distribuidora = str(r.get("perfil_normativo_concessionaria") or r.get("concessionaria") or "").casefold()
    if identificacao and distribuidora and ("cpfl" in identificacao or "elektro" in identificacao):
        invalido = invalido or distribuidora not in identificacao
    if invalido:
        for chave in ("demanda_fechada", "alimentador_geral", "contexto_resultados_rede", "fornecimento_auto_perfil"):
            r.pop(chave, None)
    return r


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

    return limpar_resultados_contexto(padrao)


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
    """Indica perfil administrativo ATIVO, sem ativar ainda o motor de demanda."""
    try:
        from perfis_normativos import perfil_por_id
        pid = (parametros or {}).get("perfil_normativo_id")
        p = perfil_por_id(pid)
        return bool(p and p.get("status") == "ATIVO")
    except Exception:
        return False
