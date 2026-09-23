"""Municípios brasileiros por UF para os seletores do AutoElétrica.

Rev.245:
- seleção em cascata UF -> Município -> Perfil Normativo;
- tenta mais de uma fonte pública de municípios para não depender de um único serviço;
- mantém cache do Streamlit;
- o perfil normativo só é liberado depois da escolha do município.

A fonte principal continua sendo o serviço de localidades do IBGE. As fontes
alternativas são usadas apenas quando a consulta principal estiver indisponível.
"""
from __future__ import annotations

import json
from urllib.request import Request, urlopen

import streamlit as st

_IBGE_UF_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios?orderBy=nome"
_BRASILAPI_URL = "https://brasilapi.com.br/api/ibge/municipios/v1/{uf}?providers=dados-abertos-br,gov,wikipedia"
_GITHUB_CSV_URL = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"

_CODIGO_UF = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17",
    "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27",
    "SE": "28", "BA": "29", "MG": "31", "ES": "32", "RJ": "33", "SP": "35", "PR": "41",
    "SC": "42", "RS": "43", "MS": "50", "MT": "51", "GO": "52", "DF": "53",
}


def _baixar_json(url: str):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 AutoEletrica/13.6.245", "Accept": "application/json"})
    with urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8-sig"))


def _normalizar(nomes) -> list[str]:
    return sorted({str(n or "").strip() for n in nomes if str(n or "").strip()}, key=lambda s: s.casefold())


@st.cache_data(ttl=86400, show_spinner=False)
def municipios_da_uf(uf: str) -> list[str]:
    uf = str(uf or "").strip().upper()
    if uf not in _CODIGO_UF:
        return []

    # 1) Fonte oficial IBGE.
    try:
        dados = _baixar_json(_IBGE_UF_URL.format(uf=uf))
        nomes = _normalizar(item.get("nome") for item in dados if isinstance(item, dict))
        if nomes:
            return nomes
    except Exception:
        pass

    # 2) Contingência: BrasilAPI, que replica dados de municípios do IBGE.
    try:
        dados = _baixar_json(_BRASILAPI_URL.format(uf=uf))
        nomes = _normalizar(
            (item.get("nome") or item.get("municipio"))
            for item in dados if isinstance(item, dict)
        )
        if nomes:
            return nomes
    except Exception:
        pass

    # 3) Contingência estática: dataset público de municípios brasileiros.
    # O filtro usa o código oficial da UF, evitando misturar cidades homônimas.
    try:
        req = Request(_GITHUB_CSV_URL, headers={"User-Agent": "Mozilla/5.0 AutoEletrica/13.6.245"})
        with urlopen(req, timeout=12) as resp:
            texto = resp.read().decode("utf-8-sig")
        codigo = _CODIGO_UF[uf]
        nomes = []
        for linha in texto.splitlines()[1:]:
            partes = linha.split(",")
            if len(partes) >= 6 and partes[5].strip() == codigo:
                nomes.append(partes[1].strip())
        nomes = _normalizar(nomes)
        if nomes:
            return nomes
    except Exception:
        pass

    return []
