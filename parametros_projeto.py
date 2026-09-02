
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


def renderizar_parametros_projeto(
    tensao_salva=None,
    pe_direito_salvo=None,
    parametros_rede_salvos=None
):
    """
    Parâmetros gerais e perfil de fornecimento do projeto.

    Fase 10.3:
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
        key="param_pe_direito"
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
            key="param_rede_uf"
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
            key="param_rede_municipio"
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
        key="param_rede_concessionaria"
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
                key=(
                    "param_rede_concessionaria_manual"
                )
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
                key=(
                    "param_rede_tipo_fornecimento"
                )
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
                key=(
                    "param_rede_tensao_fornecimento"
                )
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
        key="param_rede_metodo_demanda"
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
            key="param_rede_fator_demanda_manual"
        )
        st.caption(
            "Entrada técnica explícita. O sistema não trata este valor "
            "como regra de concessionária."
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
            "no projeto, mas nesta Fase 10.3 o cálculo de demanda "
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
