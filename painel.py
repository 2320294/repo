import streamlit as st

from database import (
    buscar_projeto,
    salvar_dados_projeto,
    converter_dxf_do_supabase
)

from quadro_cargas import (
    renderizar_edicao_cargas,
    renderizar_tabela_consolidada
)

from qdc import (
    renderizar_qdc
)

from interruptores import (
    renderizar_interruptores
)

from tomadas_altas import (
    renderizar_tomadas_altas,
    CHAVE_CONFIG as CHAVE_TOMADAS_ALTAS
)

from materiais import (
    renderizar_materiais
)

from parametros_projeto import (
    renderizar_parametros_projeto
)

from concessionarias import (
    CHAVE_PARAMETROS_REDE,
    normalizar_parametros_rede
)

from demanda_qdc import (
    calcular_demanda_qdc
)

from upload_cad import (
    renderizar_upload_dxf,
    renderizar_salvar_e_gerar_cad
)


from exportacoes import (
    gerar_excel_projeto
)


from guia_importacao import renderizar_guia_preparacao_planta

def _chave_projeto(
    sufixo
):
    """
    Estado temporário isolado por projeto.
    Permite navegar entre as etapas sem perder alterações ainda não salvas.
    """
    projeto = str(
        st.session_state.get(
            "projeto_ativo",
            "SEM_PROJETO"
        )
    )

    return (
        "fase8_16_"
        f"{projeto}_"
        f"{sufixo}"
    )


def _inicializar_cache_etapas(
    dados_ambientes,
    config_salva,
    local_qdc_salvo,
    tensao_projeto_salva,
    pe_direito_salvo
):
    chave_tabela = _chave_projeto(
        "tabela_editada"
    )
    chave_config = _chave_projeto(
        "config_eletrica"
    )
    chave_qdc = _chave_projeto(
        "local_qdc"
    )
    chave_parametros = _chave_projeto(
        "parametros"
    )

    if chave_tabela not in st.session_state:
        st.session_state[
            chave_tabela
        ] = list(
            dados_ambientes
            or []
        )

    if chave_config not in st.session_state:
        st.session_state[
            chave_config
        ] = dict(
            config_salva
            or {}
        )

    if chave_qdc not in st.session_state:
        st.session_state[
            chave_qdc
        ] = local_qdc_salvo

    if chave_parametros not in st.session_state:
        try:
            tensao = int(
                tensao_projeto_salva
                if tensao_projeto_salva is not None
                else 110
            )
        except Exception:
            tensao = 110

        try:
            pe = float(
                pe_direito_salvo
                if pe_direito_salvo is not None
                else 2.80
            )
        except Exception:
            pe = 2.80

        st.session_state[
            chave_parametros
        ] = {
            "tensao_projeto":
                tensao,
            "pe_direito":
                pe,
            "parametros_rede":
                normalizar_parametros_rede(
                    (
                        config_salva
                        or {}
                    ).get(
                        CHAVE_PARAMETROS_REDE,
                        {}
                    )
                )
        }

    return (
        chave_tabela,
        chave_config,
        chave_qdc,
        chave_parametros
    )


def _navegacao_etapas():
    etapas = [
        "⚙️ Parâmetros",
        "📊 Cargas",
        "⚡ QDC",
        "💡 Interruptores",
        "🔌 Tomadas Altas",
        "📦 Materiais",
        "📐 Gerar Projeto"
    ]

    chave = _chave_projeto(
        "etapa_ativa"
    )

    if chave not in st.session_state:
        st.session_state[
            chave
        ] = etapas[0]

    etapa = st.radio(
        "Etapas do projeto",
        etapas,
        horizontal=True,
        key=chave,
        label_visibility="collapsed"
    )

    indice = (
        etapas.index(
            etapa
        )
        + 1
    )

    st.caption(
        f"Etapa {indice} de {len(etapas)}"
    )

    return etapa


def renderizar_painel_principal():

    st.title(
        "⚡ Painel de Projetos Elétricos"
    )

    if (
        st.session_state.projeto_ativo
        == "Selecione um projeto..."
    ):
        st.info(
            "👈 Selecione um projeto na barra lateral "
            "ou cadastre um novo."
        )
        renderizar_guia_preparacao_planta()
        st.stop()

    st.info(
        f"📁 **Projeto Ativo:** "
        f"{st.session_state.projeto_ativo}"
    )

    try:
        projeto_obj, dados_obj = buscar_projeto(
            st.session_state.user_email,
            st.session_state.projeto_ativo
        )

    except Exception as e:
        st.error(
            f"❌ Erro ao carregar o projeto "
            f"do Supabase: {e}"
        )
        st.stop()

    if not projeto_obj:
        st.error(
            "❌ O projeto selecionado não foi "
            "encontrado no Supabase."
        )
        st.stop()

    if dados_obj is None:
        try:
            salvar_dados_projeto(
                st.session_state.user_email,
                st.session_state.projeto_ativo,
                tabela_editada=[],
                config_interruptores={}
            )

            _, dados_obj = buscar_projeto(
                st.session_state.user_email,
                st.session_state.projeto_ativo
            )

        except Exception as e:
            st.error(
                f"❌ Não foi possível criar "
                f"os dados do projeto: {e}"
            )
            st.stop()

    dxf_bytes = converter_dxf_do_supabase(
        dados_obj.get(
            "dxf_bytes"
        )
    )

    dados_ambientes = (
        dados_obj.get(
            "tabela_editada"
        )
        or []
    )

    config_salva = (
        dados_obj.get(
            "config_interruptores"
        )
        or {}
    )

    local_qdc_salvo = (
        dados_obj.get(
            "local_qdc"
        )
    )

    tensao_projeto_salva = (
        dados_obj.get(
            "tensao_projeto"
        )
    )

    pe_direito_salvo = (
        dados_obj.get(
            "pe_direito"
        )
    )

    (
        chave_tabela,
        chave_config,
        chave_qdc,
        chave_parametros
    ) = _inicializar_cache_etapas(
        dados_ambientes,
        config_salva,
        local_qdc_salvo,
        tensao_projeto_salva,
        pe_direito_salvo
    )

    etapa = _navegacao_etapas()

    # --------------------------------------------------------
    # ETAPA 1 — PARÂMETROS E PLANTA
    # --------------------------------------------------------
    if etapa == "⚙️ Parâmetros":
        st.subheader(
            "⚙️ Parâmetros e Planta do Projeto"
        )

        parametros = (
            renderizar_parametros_projeto(
                st.session_state[
                    chave_parametros
                ].get(
                    "tensao_projeto"
                ),
                st.session_state[
                    chave_parametros
                ].get(
                    "pe_direito"
                ),
                st.session_state[
                    chave_parametros
                ].get(
                    "parametros_rede",
                    {}
                )
            )
        )

        st.session_state[
            chave_parametros
        ] = parametros

        config_parametros = dict(
            st.session_state[
                chave_config
            ]
            or {}
        )

        config_parametros[
            CHAVE_PARAMETROS_REDE
        ] = parametros.get(
            "parametros_rede",
            {}
        )

        st.session_state[
            chave_config
        ] = config_parametros

        renderizar_upload_dxf(
            dxf_bytes=dxf_bytes,
            dados_ambientes=dados_ambientes,
            config_salva=(
                st.session_state[
                    chave_config
                ]
            )
        )

        if not dxf_bytes:
            st.info(
                "Envie uma planta DXF para liberar "
                "as próximas etapas."
            )

        return

    # Da etapa 2 em diante é necessária uma planta processada.
    if not dados_ambientes:
        st.warning(
            "⚠️ Primeiro envie e processe uma planta DXF "
            "na etapa **Parâmetros**."
        )
        return

    # --------------------------------------------------------
    # ETAPA 2 — PREVISÃO DE CARGAS
    # --------------------------------------------------------
    if etapa == "📊 Cargas":
        st.subheader(
            "📊 Quadro de Previsão de Cargas"
        )

        tabela_editada = (
            renderizar_edicao_cargas(
                st.session_state[
                    chave_tabela
                ]
            )
        )

        st.session_state[
            chave_tabela
        ] = tabela_editada

        renderizar_tabela_consolidada(
            tabela_editada
        )

        st.markdown(
            "#### 📥 Exportação do Quadro de Cargas"
        )

        try:
            excel_bytes = gerar_excel_projeto(
                tabela_editada=tabela_editada,
                config_interruptores_usuario=(
                    st.session_state[
                        chave_config
                    ]
                ),
                local_qdc=(
                    st.session_state[
                        chave_qdc
                    ]
                ),
                tensao_projeto=(
                    st.session_state[
                        chave_parametros
                    ][
                        "tensao_projeto"
                    ]
                ),
                pe_direito=(
                    st.session_state[
                        chave_parametros
                    ][
                        "pe_direito"
                    ]
                )
            )

            st.download_button(
                label="📊 Exportar Cargas para Excel",
                data=excel_bytes,
                file_name=(
                    f"{st.session_state.projeto_ativo}"
                    "_Quadro_Cargas.xlsx"
                ),
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                use_container_width=True
            )

        except Exception as e:
            st.error(
                f"❌ Erro ao preparar Excel: {e}"
            )

        return

    # Valores correntes compartilhados pelas demais etapas.
    tabela_editada = (
        st.session_state[
            chave_tabela
        ]
        or dados_ambientes
    )

    config_atual = dict(
        st.session_state[
            chave_config
        ]
        or {}
    )

    local_qdc = (
        st.session_state[
            chave_qdc
        ]
    )

    parametros_projeto = (
        st.session_state[
            chave_parametros
        ]
    )

    # --------------------------------------------------------
    # ETAPA 3 — QDC
    # --------------------------------------------------------
    if etapa == "⚡ QDC":
        st.subheader(
            "⚡ Posicionamento do QDC"
        )

        local_qdc = renderizar_qdc(
            dados_ambientes,
            local_qdc,
            dxf_bytes=dxf_bytes
        )

        st.session_state[
            chave_qdc
        ] = local_qdc

        st.markdown("#### ⚙️ Demanda e proteção geral")

        resultado_demanda = calcular_demanda_qdc(
            tabela_editada,
            parametros_projeto.get(
                "parametros_rede",
                {}
            )
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Potência instalada",
            f"{resultado_demanda['total_w']/1000:.2f} kW"
        )

        pd = resultado_demanda.get("potencia_demanda_w")
        idm = resultado_demanda.get("corrente_demanda_a")
        dg = resultado_demanda.get("disjuntor_geral_a")

        c2.metric(
            "Potência demandada",
            f"{pd/1000:.2f} kW" if pd is not None else "Aguardando perfil"
        )
        c3.metric(
            "Corrente de demanda",
            f"{idm:.1f} A" if idm is not None else "—"
        )
        c4.metric(
            "DG pré-selecionado",
            f"{dg} A" if dg is not None else "—"
        )

        status = resultado_demanda.get("status")
        if status == "aguardando_perfil":
            st.info(
                "ℹ️ O método automático está selecionado, mas o perfil "
                "normativo desta concessionária ainda não foi ativado. "
                "Nenhum fator de demanda foi inventado pelo sistema."
            )
        elif status == "fornecimento_incompleto":
            st.warning(
                "⚠️ Informe tipo e tensão de fornecimento em Parâmetros "
                "para calcular corrente de demanda e DG."
            )
        elif status == "acima_da_faixa":
            st.warning(
                "⚠️ A corrente calculada ultrapassa a faixa preliminar "
                "de disjuntores cadastrada. Reavalie o fornecimento."
            )
        else:
            st.caption(
                "Pré-dimensionamento da Fase 11.8. O DG depende da validação "
                "do alimentador e do perfil da concessionária."
            )

        return

    # --------------------------------------------------------
    # ETAPA 4 — INTERRUPTORES
    # --------------------------------------------------------
    if etapa == "💡 Interruptores":
        st.subheader(
            "💡 Posicionamento dos Interruptores"
        )

        config_interruptores = (
            renderizar_interruptores(
                dados_ambientes,
                config_atual,
                dxf_bytes=dxf_bytes
            )
        )

        # Preserva configurações reservadas enquanto
        # a etapa de interruptores é editada.
        if (
            CHAVE_TOMADAS_ALTAS
            in config_atual
        ):
            config_interruptores[
                CHAVE_TOMADAS_ALTAS
            ] = config_atual[
                CHAVE_TOMADAS_ALTAS
            ]

        if (
            CHAVE_PARAMETROS_REDE
            in config_atual
        ):
            config_interruptores[
                CHAVE_PARAMETROS_REDE
            ] = config_atual[
                CHAVE_PARAMETROS_REDE
            ]

        st.session_state[
            chave_config
        ] = config_interruptores

        return

    # --------------------------------------------------------
    # ETAPA 5 — TOMADAS ALTAS
    # --------------------------------------------------------
    if etapa == "🔌 Tomadas Altas":
        st.subheader(
            "🔌 Posicionamento das Tomadas Altas"
        )

        config_tomadas_altas = (
            renderizar_tomadas_altas(
                tabela_editada,
                config_atual,
                dxf_bytes=dxf_bytes
            )
        )

        config_atual[
            CHAVE_TOMADAS_ALTAS
        ] = config_tomadas_altas

        st.session_state[
            chave_config
        ] = config_atual

        return

    # --------------------------------------------------------
    # ETAPA 6 — MATERIAIS
    # --------------------------------------------------------
    if etapa == "📦 Materiais":
        st.subheader(
            "📦 Circuitos e Quantitativo de Materiais"
        )

        renderizar_materiais(
            tabela_editada,
            config_atual,
            local_qdc,
            tensao_projeto=(
                parametros_projeto[
                    "tensao_projeto"
                ]
            ),
            pe_direito=(
                parametros_projeto[
                    "pe_direito"
                ]
            )
        )

        return

    # --------------------------------------------------------
    # ETAPA 7 — SALVAR / EXPORTAR / GERAR CAD
    # --------------------------------------------------------
    if etapa == "📐 Gerar Projeto":
        st.subheader(
            "📐 Salvar e Gerar Projeto"
        )

        st.markdown(
            "Revise as etapas anteriores e, quando estiver tudo "
            "correto, salve as configurações e gere os arquivos."
        )

        renderizar_salvar_e_gerar_cad(
            dxf_bytes=dxf_bytes,
            tabela_editada=tabela_editada,
            local_qdc=local_qdc,
            config_interruptores_usuario=(
                config_atual
            ),
            tensao_projeto=(
                parametros_projeto[
                    "tensao_projeto"
                ]
            ),
            pe_direito=(
                parametros_projeto[
                    "pe_direito"
                ]
            )
        )

        return
