
import streamlit as st

from tensoes_circuitos import tensao_base_fornecimento
from perfis_normativos import listar_perfis_liberados
from municipios_brasil import municipios_da_uf

from concessionarias import (
    UFS,
    OUTRA_CONCESSIONARIA,
    concessionarias_da_uf,
    normalizar_parametros_rede,
    nome_concessionaria,
    perfil_normativo_disponivel
)


def _widget_key(sufixo):
    """
    Chave de widget isolada por projeto.

    Evita que o Streamlit reutilize valores visuais do projeto anterior
    ao trocar o projeto ativo na barra lateral.
    """
    projeto = str(
        st.session_state.get(
            "projeto_ativo",
            "SEM_PROJETO"
        )
        or "SEM_PROJETO"
    )

    seguro = (
        projeto
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )

    return f"parametros_{seguro}_{sufixo}"


def renderizar_parametros_projeto(
    tensao_salva=None,
    pe_direito_salvo=None,
    parametros_rede_salvos=None
):
    """
    Parâmetros gerais e perfil de fornecimento do projeto.

    Fase 13.6 Rev.124:
    - localização;
    - concessionária;
    - tipo/tensão de fornecimento;
    - método de demanda;
    - infraestrutura para perfis normativos por concessionária.
    """

    st.markdown(
        "#### 🏠 Dados gerais"
    )

    try:
        pe_atual = float(
            pe_direito_salvo
            if pe_direito_salvo is not None
            else 2.80
        )
    except Exception:
        pe_atual = 2.80

    if pe_atual < 2.00 or pe_atual > 10.00:
        pe_atual = 2.80

    pe_direito = st.number_input(
        "Pé-direito do pavimento (m):",
        min_value=2.00,
        max_value=10.00,
        value=pe_atual,
        step=0.05,
        format="%.2f",
        key=_widget_key("pe_direito")
    )

    st.markdown(
        "#### 🌎 Localização e concessionária"
    )

    rede = normalizar_parametros_rede(
        parametros_rede_salvos
    )

    col_uf, col_municipio = st.columns(2)

    with col_uf:
        opcoes_uf = [
            "Selecione..."
        ] + UFS

        uf_salva = rede.get(
            "uf",
            ""
        )

        indice_uf = (
            opcoes_uf.index(
                uf_salva
            )
            if uf_salva in opcoes_uf
            else 0
        )

        uf_escolhida = st.selectbox(
            "Estado (UF):",
            opcoes_uf,
            index=indice_uf,
            key=_widget_key("rede_uf")
        )

        uf = (
            ""
            if uf_escolhida == "Selecione..."
            else uf_escolhida
        )

    with col_municipio:
        # Rev.244 — município em cascata pela UF. A lista vem da API oficial
        # de localidades do IBGE; não há mais digitação livre na operação normal.
        municipio_salvo = str(rede.get("municipio", "") or "").strip()
        municipios = municipios_da_uf(uf) if uf else []
        opcoes_municipio = ["Selecione..."] + municipios

        # Preserva projetos antigos mesmo se a API estiver temporariamente
        # indisponível ou se o nome histórico não vier na consulta atual.
        if municipio_salvo and municipio_salvo not in opcoes_municipio:
            opcoes_municipio.append(municipio_salvo)

        indice_municipio = (
            opcoes_municipio.index(municipio_salvo)
            if municipio_salvo in opcoes_municipio
            else 0
        )
        municipio_escolhido = st.selectbox(
            "Município:",
            opcoes_municipio,
            index=indice_municipio,
            key=_widget_key(f"rede_municipio_{uf or 'SEM_UF'}")
        )
        municipio = "" if municipio_escolhido == "Selecione..." else municipio_escolhido

        if uf and not municipios:
            st.caption("Não foi possível atualizar a lista de municípios do IBGE agora; o valor salvo foi preservado.")

    # Rev.187 — usuário comum somente seleciona perfis liberados pelo administrador.
    try:
        perfis_liberados = listar_perfis_liberados(uf, municipio) if (uf and municipio) else []
    except Exception:
        perfis_liberados = []

    rotulos_perfis = ["Selecione um Perfil Normativo..."]
    mapa_perfis = {}
    for p in perfis_liberados:
        rotulo = f"{p.get('concessionaria','')} — {p.get('documento') or 'Norma'} {p.get('revisao') or ''}".strip()
        if p.get("municipio"):
            rotulo += f" — {p.get('municipio')}/{p.get('uf')}"
        rotulos_perfis.append(rotulo)
        mapa_perfis[rotulo] = p

    perfil_salvo_id = rede.get("perfil_normativo_id")
    indice_perfil = 0
    for i, rotulo in enumerate(rotulos_perfis):
        p = mapa_perfis.get(rotulo)
        if p and str(p.get("id")) == str(perfil_salvo_id):
            indice_perfil = i
            break

    perfil_rotulo = st.selectbox(
        "Perfil normativo liberado pelo AutoElétrica:",
        rotulos_perfis,
        index=indice_perfil,
        key=_widget_key(f"rede_perfil_normativo_{uf or 'SEM_UF'}_{municipio or 'SEM_MUNICIPIO'}"),
        disabled=not bool(municipio)
    )
    perfil_selecionado = mapa_perfis.get(perfil_rotulo)
    perfil_normativo_id = perfil_selecionado.get("id") if perfil_selecionado else None
    concessionaria = perfil_selecionado.get("concessionaria") if perfil_selecionado else OUTRA_CONCESSIONARIA
    concessionaria_manual = ""

    st.markdown(
        "#### ⚡ Perfil de fornecimento"
    )

    col_tipo, col_tensao_rede = (
        st.columns(2)
    )

    tipos = [
        "A definir",
        "Monofásico",
        "Bifásico",
        "Trifásico"
    ]

    tensoes_rede = [
        "A definir",
        "127 V",
        "220 V",
        "127/220 V",
        "220/380 V"
    ]

    with col_tipo:
        tipo_salvo = rede.get(
            "tipo_fornecimento",
            "A definir"
        )

        if tipo_salvo not in tipos:
            tipo_salvo = "A definir"

        tipo_fornecimento = (
            st.selectbox(
                "Tipo de fornecimento:",
                tipos,
                index=tipos.index(
                    tipo_salvo
                ),
                key=_widget_key("rede_tipo_fornecimento")
            )
        )

    with col_tensao_rede:
        tensao_rede_salva = rede.get(
            "tensao_fornecimento",
            "A definir"
        )

        # Rev.202 — ao selecionar um perfil ATIVO, usa os valores de
        # fornecimento persistidos no próprio perfil apenas como padrão inicial.
        # O usuário continua escolhendo a modalidade de fornecimento do projeto.
        if tensao_rede_salva == "A definir" and perfil_selecionado:
            try:
                _forn = (perfil_selecionado.get("regras") or {}).get("fornecimento") or {}
                _vfn = int(float(_forn.get("tensao_fase_neutro_v") or 0))
                _vff = int(float(_forn.get("tensao_fase_fase_v") or 0))
                _combinada = f"{_vfn}/{_vff} V" if _vfn and _vff else ""
                if _combinada in tensoes_rede:
                    tensao_rede_salva = _combinada
            except Exception:
                pass

        if (
            tensao_rede_salva
            not in tensoes_rede
        ):
            tensao_rede_salva = (
                "A definir"
            )

        tensao_fornecimento = (
            st.selectbox(
                "Tensão de fornecimento:",
                tensoes_rede,
                index=tensoes_rede.index(
                    tensao_rede_salva
                ),
                key=_widget_key("rede_tensao_fornecimento")
            )
        )

    metodos = [
        (
            "Automático pela concessionária "
            "(quando cadastrado)"
        ),
        "Manual pelo responsável técnico"
    ]

    metodo_salvo = rede.get(
        "metodo_demanda",
        metodos[0]
    )

    if metodo_salvo not in metodos:
        metodo_salvo = metodos[0]

    # Rev.204 — quando o projeto passa a usar um perfil normativo ATIVO pela
    # primeira vez (ou troca para outro perfil), o método normativo passa a ser
    # o padrão do projeto. Depois de persistido, uma escolha manual explícita do
    # responsável técnico continua sendo respeitada.
    perfil_trocado = bool(
        perfil_selecionado
        and str(perfil_selecionado.get("id")) != str(perfil_salvo_id or "")
    )
    if perfil_trocado:
        metodo_salvo = metodos[0]
        chave_metodo = _widget_key("rede_metodo_demanda")
        if chave_metodo in st.session_state:
            st.session_state[chave_metodo] = metodos[0]

    # Rev.216 atualizada — interface simplificada da Etapa 1.
    # Mantém toda a lógica/persistência técnica, mas exibe apenas os campos
    # necessários ao fluxo normal do usuário.
    col_metodo, col_aterramento = st.columns(2)

    with col_metodo:
        metodo_demanda = st.selectbox(
            "Método de cálculo de demanda:",
            metodos,
            index=metodos.index(metodo_salvo),
            key=_widget_key("rede_metodo_demanda")
        )

    with col_aterramento:
        esquemas = ["Não sei", "TN-S", "TN-C-S", "TT", "IT"]
        esquema_salvo = str(
            rede.get("esquema_aterramento", "Não sei") or "Não sei"
        )
        if esquema_salvo not in esquemas:
            esquema_salvo = "Não sei"
        esquema_aterramento = st.selectbox(
            "Esquema de aterramento:",
            esquemas,
            index=esquemas.index(esquema_salvo),
            key=_widget_key("qdc_esquema_aterramento")
        )

    fator_demanda_manual = float(rede.get("fator_demanda_manual", 100.0) or 100.0)
    if metodo_demanda == "Manual pelo responsável técnico":
        fator_demanda_manual = st.number_input(
            "Fator global de demanda informado pelo responsável técnico (%):",
            min_value=0.0, max_value=100.0,
            value=min(100.0, max(0.0, fator_demanda_manual)),
            step=1.0, format="%.1f",
            key=_widget_key("rede_fator_demanda_manual")
        )
        st.caption(
            "Entrada técnica explícita. O sistema não trata este valor "
            "como regra de concessionária."
        )

    # Campos técnicos avançados permanecem preservados internamente.
    # Eles deixam de ocupar a Etapa 1, mantendo os valores já salvos/fallbacks.
    icc_conhecida = bool(rede.get("icc_conhecida", False))
    icc_qdc_ka = float(rede.get("icc_qdc_ka", 0.0) or 0.0) if icc_conhecida else 0.0
    fabricante_protecao = str(rede.get("fabricante_protecao", "") or "").strip()
    cap_dg_ka = float(rede.get("capacidade_interrupcao_dg_ka", 0.0) or 0.0)
    cap_terminais_ka = float(rede.get("capacidade_interrupcao_terminais_ka", 0.0) or 0.0)
    referencia_seletividade = str(rede.get("referencia_seletividade", "") or "").strip()
    seletividade_validada_rt = bool(rede.get("seletividade_validada_rt", False))
    dps_tipo = str(rede.get("dps_tipo", "A definir") or "A definir")
    dps_uc_v = float(rede.get("dps_uc_v", 0.0) or 0.0)
    dps_up_kv = float(rede.get("dps_up_kv", 0.0) or 0.0)
    dps_in_ka = float(rede.get("dps_in_ka", 0.0) or 0.0)
    dps_imax_ka = float(rede.get("dps_imax_ka", 0.0) or 0.0)
    arranjo_dps = str(rede.get("arranjo_dps", "") or "").strip()
    arranjo_dps_validado_rt = bool(rede.get("arranjo_dps_validado_rt", False))
    norma_concessionaria_referencia = str(
        rede.get("norma_concessionaria_referencia", "") or ""
    ).strip()
    requisitos_concessionaria_validos = bool(
        rede.get("requisitos_concessionaria_validados_rt", False)
    )

    parametros_rede = {
        "uf": uf,
        "municipio": municipio,
        "concessionaria": concessionaria,
        "concessionaria_manual":
            concessionaria_manual,
        "perfil_normativo_id": perfil_normativo_id,
        # Rev.202 — snapshot textual para rastreabilidade do projeto.
        # O ID continua sendo a fonte de verdade para carregar as regras.
        "perfil_normativo_concessionaria": (
            perfil_selecionado.get("concessionaria", "") if perfil_selecionado else ""
        ),
        "perfil_normativo_documento": (
            perfil_selecionado.get("documento", "") if perfil_selecionado else ""
        ),
        "perfil_normativo_revisao": (
            perfil_selecionado.get("revisao", "") if perfil_selecionado else ""
        ),
        "perfil_normativo_status": (
            perfil_selecionado.get("status", "") if perfil_selecionado else ""
        ),
        "tipo_fornecimento":
            tipo_fornecimento,
        "tensao_fornecimento":
            tensao_fornecimento,
        "metodo_demanda":
            metodo_demanda,
        "fator_demanda_manual":
            float(fator_demanda_manual),
        "norma_concessionaria": (
            (f"{perfil_selecionado.get('documento','')} {perfil_selecionado.get('revisao','')}".strip())
            if perfil_selecionado else "Perfil normativo ainda não liberado"
        ),
        "esquema_aterramento": esquema_aterramento,
        "icc_conhecida": bool(icc_conhecida),
        "icc_qdc_ka": float(icc_qdc_ka),
        "fabricante_protecao": fabricante_protecao,
        "capacidade_interrupcao_dg_ka": float(cap_dg_ka),
        "capacidade_interrupcao_terminais_ka": float(cap_terminais_ka),
        "referencia_seletividade": referencia_seletividade,
        "seletividade_validada_rt": bool(seletividade_validada_rt),
        "dps_tipo": dps_tipo,
        "dps_uc_v": float(dps_uc_v),
        "dps_up_kv": float(dps_up_kv),
        "dps_in_ka": float(dps_in_ka),
        "dps_imax_ka": float(dps_imax_ka),
        "arranjo_dps": arranjo_dps,
        "arranjo_dps_validado_rt": bool(arranjo_dps_validado_rt),
        "norma_concessionaria_referencia": norma_concessionaria_referencia,
        "requisitos_concessionaria_validados_rt": bool(
            requisitos_concessionaria_validos
        )
    }

    concessionaria_nome = (
        nome_concessionaria(
            parametros_rede
        )
    )

    if metodo_demanda.startswith("Automático") and not perfil_normativo_disponivel(parametros_rede):
        st.warning(
            "⚠️ Perfil normativo da concessionária não disponível para esta região. "
            "O AutoElétrica não aplicará regras da CPFL nem de qualquer outra concessionária "
            "como padrão. Os cálculos que dependem da concessionária permanecerão indisponíveis "
            "até a seleção de um perfil normativo ATIVO compatível com a UF/município."
        )
    elif metodo_demanda.startswith("Automático") and perfil_selecionado:
        _forn = (perfil_selecionado.get("regras") or {}).get("fornecimento") or {}
        if not (_forn.get("faixas_modalidade_kw") or []):
            st.warning(
                "⚠️ O perfil selecionado ainda não possui as faixas de modalidade de fornecimento "
                "cadastradas. O AutoElétrica preservará a modalidade informada e não inventará "
                "limites de outra concessionária. O administrador deve completar esse perfil."
            )

    return {
        "tensao_projeto":
            int(
                tensao_base_fornecimento(
                    parametros_rede,
                    fallback=(
                        tensao_salva
                        if tensao_salva is not None
                        else 220
                    )
                )
            ),
        "pe_direito":
            float(pe_direito),
        "parametros_rede":
            parametros_rede
    }
