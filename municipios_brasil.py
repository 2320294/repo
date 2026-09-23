"""Municípios brasileiros por UF para os seletores do AutoElétrica.

Rev.244: consulta a API oficial de localidades do IBGE e mantém cache local do
Streamlit. Em indisponibilidade temporária da API, preserva o município já salvo
no projeto para não bloquear projetos existentes.
"""
from __future__ import annotations

import json
from urllib.request import Request, urlopen

import streamlit as st

_IBGE_UF_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"


@st.cache_data(ttl=86400, show_spinner=False)
def municipios_da_uf(uf: str) -> list[str]:
    uf = str(uf or "").strip().upper()
    if len(uf) != 2:
        return []
    try:
        req = Request(
            _IBGE_UF_URL.format(uf=uf),
            headers={"User-Agent": "AutoEletrica/13.6.244"},
        )
        with urlopen(req, timeout=8) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
        nomes = sorted(
            {str(item.get("nome") or "").strip() for item in dados if item.get("nome")},
            key=lambda s: s.casefold(),
        )
        return nomes
    except Exception:
        return []
