
import streamlit as st

from tensoes_circuitos import tensao_base_fornecimento

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

    Fase 13.6 Rev.6:
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
        municipio = st.text_input(
            "Município:",
            value=rede.get(
                "municipio",
                ""
            ),
            placeholder="Ex.: Belo Horizonte",
            key=_widget_key("rede_municipio")
        ).strip()

    opcoes_concessionaria = (
        concessionarias_da_uf(
            uf
        )
    )

    concessionaria_salva = rede.get(
        "concessionaria",
        OUTRA_CONCESSIONARIA
    )

    if (
        concessionaria_salva
        not in opcoes_concessionaria
    ):
        concessionaria_salva = (
            OUTRA_CONCESSIONARIA
        )

    concessionaria = st.selectbox(
        "Concessionária de distribuição:",
        options=opcoes_concessionaria,
        index=opcoes_concessionaria.index(
            concessionaria_salva
        ),
        key=_widget_key("rede_concessionaria")
    )

    concessionaria_manual = ""

    if (
        concessionaria
        == OUTRA_CONCESSIONARIA
    ):
        concessionaria_manual = (
            st.text_input(
                "Nome da concessionária:",
                value=rede.get(
                    "concessionaria_manual",
                    ""
                ),
                placeholder=(
                    "Informe a distribuidora local"
                ),
                key=_widget_key("rede_concessionaria_manual")
            ).strip()
        )

    st.caption(
        "O cadastro de concessionárias é progressivo. "
        "A opção 'Outra / Não cadastrada' mantém o projeto "
        "utilizável em qualquer localidade."
    )

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

    metodo_demanda = st.selectbox(
        "Método de cálculo de demanda:",
        metodos,
        index=metodos.index(
            metodo_salvo
        ),
        key=_widget_key("rede_metodo_demanda")
    )

    fator_demanda_manual = float(
        rede.get(
            "fator_demanda_manual",
            100.0
        )
        or 100.0
    )

    if metodo_demanda == "Manual pelo responsável técnico":
        fator_demanda_manual = st.number_input(
            "Fator global de demanda informado pelo responsável técnico (%):",
            min_value=0.0,
            max_value=100.0,
            value=min(100.0, max(0.0, fator_demanda_manual)),
            step=1.0,
            format="%.1f",
            key=_widget_key("rede_fator_demanda_manual")
        )
        st.caption(
            "Entrada técnica explícita. O sistema não trata este valor "
            "como regra de concessionária."
        )


    st.markdown("#### 🛡️ Validação do QDC")

    st.caption(
        "O AutoElétrica usa automaticamente os dados já conhecidos do projeto. "
        "Informe apenas o que você souber."
    )

    col_aterramento, col_icc, col_fabricante = st.columns(3)

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

    with col_icc:
        icc_opcao = st.selectbox(
            "Corrente de curto-circuito no QDC:",
            ["Não sei", "Informar valor"],
            index=1 if bool(rede.get("icc_conhecida", False)) else 0,
            key=_widget_key("qdc_icc_opcao")
        )

    with col_fabricante:
        fabricante_protecao = st.text_input(
            "Fabricante das proteções (opcional):",
            value=str(rede.get("fabricante_protecao", "") or ""),
            placeholder="Pode deixar em branco",
            key=_widget_key("qdc_fabricante_protecao")
        ).strip()

    icc_conhecida = icc_opcao == "Informar valor"
    icc_qdc_ka = float(rede.get("icc_qdc_ka", 0.0) or 0.0)

    if icc_conhecida:
        icc_qdc_ka = st.number_input(
            "Icc presumida no QDC (kA):",
            min_value=0.1,
            max_value=200.0,
            value=max(0.1, icc_qdc_ka),
            step=0.1,
            format="%.1f",
            key=_widget_key("qdc_icc_ka")
        )
    else:
        icc_qdc_ka = 0.0

    with st.expander(
        "⚙️ Configurações técnicas avançadas",
        expanded=False
    ):
        st.caption(
            "Preencha somente se estes dados estiverem disponíveis no projeto "
            "executivo, catálogo do fabricante ou documentação da concessionária."
        )

        st.markdown("##### Disjuntores e seletividade")
        c1, c2 = st.columns(2)

        with c1:
            cap_dg_ka = st.number_input(
                "Capacidade de interrupção do DG (kA):",
                min_value=0.0,
                max_value=200.0,
                value=float(rede.get("capacidade_interrupcao_dg_ka", 0.0) or 0.0),
                step=0.1,
                format="%.1f",
                key=_widget_key("qdc_cap_dg_ka")
            )

        with c2:
            cap_terminais_ka = st.number_input(
                "Capacidade dos disjuntores terminais (kA):",
                min_value=0.0,
                max_value=200.0,
                value=float(rede.get("capacidade_interrupcao_terminais_ka", 0.0) or 0.0),
                step=0.1,
                format="%.1f",
                key=_widget_key("qdc_cap_terminais_ka")
            )

        referencia_seletividade = st.text_input(
            "Referência de seletividade/coordenação:",
            value=str(rede.get("referencia_seletividade", "") or ""),
            placeholder="Catálogo, tabela ou documento técnico",
            key=_widget_key("qdc_referencia_seletividade")
        ).strip()

        seletividade_validada_rt = st.checkbox(
            "Seletividade/coordenação confirmada pelo responsável técnico",
            value=bool(rede.get("seletividade_validada_rt", False)),
            key=_widget_key("qdc_seletividade_validada_rt")
        )

        st.markdown("##### DPS")
        tipos_dps = ["A definir", "Tipo 1", "Tipo 2", "Tipo 1+2", "Tipo 3"]
        dps_tipo_salvo = str(rede.get("dps_tipo", "A definir") or "A definir")
        if dps_tipo_salvo not in tipos_dps:
            dps_tipo_salvo = "A definir"

        dps_tipo = st.selectbox(
            "Tipo do DPS:",
            tipos_dps,
            index=tipos_dps.index(dps_tipo_salvo),
            key=_widget_key("qdc_dps_tipo")
        )

        d1, d2, d3, d4 = st.columns(4)

        with d1:
            dps_uc_v = st.number_input(
                "Uc (V):",
                min_value=0.0,
                max_value=2000.0,
                value=float(rede.get("dps_uc_v", 0.0) or 0.0),
                step=1.0,
                format="%.0f",
                key=_widget_key("qdc_dps_uc_v")
            )

        with d2:
            dps_up_kv = st.number_input(
                "Up (kV):",
                min_value=0.0,
                max_value=20.0,
                value=float(rede.get("dps_up_kv", 0.0) or 0.0),
                step=0.1,
                format="%.1f",
                key=_widget_key("qdc_dps_up_kv")
            )

        with d3:
            dps_in_ka = st.number_input(
                "In (kA):",
                min_value=0.0,
                max_value=500.0,
                value=float(rede.get("dps_in_ka", 0.0) or 0.0),
                step=0.5,
                format="%.1f",
                key=_widget_key("qdc_dps_in_ka")
            )

        with d4:
            dps_imax_ka = st.number_input(
                "Imax (kA):",
                min_value=0.0,
                max_value=500.0,
                value=float(rede.get("dps_imax_ka", 0.0) or 0.0),
                step=0.5,
                format="%.1f",
                key=_widget_key("qdc_dps_imax_ka")
            )

        st.markdown("##### Aterramento e concessionária")

        arranjo_dps = st.text_input(
            "Arranjo de ligação do DPS:",
            value=str(rede.get("arranjo_dps", "") or ""),
            placeholder="Opcional",
            key=_widget_key("qdc_arranjo_dps")
        ).strip()

        arranjo_dps_validado_rt = st.checkbox(
            "Arranjo do DPS confirmado para o esquema de aterramento",
            value=bool(rede.get("arranjo_dps_validado_rt", False)),
            key=_widget_key("qdc_arranjo_dps_validado_rt")
        )

        norma_concessionaria_referencia = st.text_input(
            "Norma/padrão da concessionária utilizado:",
            value=str(rede.get("norma_concessionaria_referencia", "") or ""),
            placeholder="Opcional",
            key=_widget_key("qdc_norma_concessionaria_ref")
        ).strip()

        requisitos_concessionaria_validos = st.checkbox(
            "Requisitos adicionais da concessionária confirmados",
            value=bool(rede.get("requisitos_concessionaria_validados_rt", False)),
            key=_widget_key("qdc_concessionaria_validada_rt")
        )

    parametros_rede = {
        "uf": uf,
        "municipio": municipio,
        "concessionaria": concessionaria,
        "concessionaria_manual":
            concessionaria_manual,
        "tipo_fornecimento":
            tipo_fornecimento,
        "tensao_fornecimento":
            tensao_fornecimento,
        "metodo_demanda":
            metodo_demanda,
        "fator_demanda_manual":
            float(fator_demanda_manual),
        "norma_concessionaria": (
            "Perfil normativo ainda não cadastrado"
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

    if (
        metodo_demanda.startswith(
            "Automático"
        )
        and not perfil_normativo_disponivel(
            parametros_rede
        )
    ):
        st.info(
            "ℹ️ A localização e a concessionária serão salvas "
            "no projeto, mas nesta Fase 13.6 Rev.6 o cálculo de demanda "
            "ainda não é aplicado automaticamente. "
            "O perfil normativo será ativado somente quando "
            "a regra oficial dessa concessionária estiver "
            "cadastrada e validada."
        )

    if uf and municipio:
        st.success(
            f"📍 Perfil do projeto: **{municipio}/{uf}** — "
            f"**{concessionaria_nome}**"
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
