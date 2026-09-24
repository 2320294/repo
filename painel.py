import streamlit as st

from versao import VERSAO_SISTEMA

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

from protecao_alimentador import dimensionar_alimentador_geral

from upload_cad import (
    renderizar_upload_dxf,
    renderizar_salvar_e_gerar_cad,
    calcular_rotas_antes_do_dxf
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
    elif (
        not st.session_state.get(chave_tabela)
        and dados_ambientes
    ):
        # Fase 13.6 Rev.242 — recuperação defensiva para projeto novo:
        # se a sessão criou a tabela vazia antes do primeiro upload, mas o
        # Supabase já possui os ambientes/cargas processados, hidrata o cache
        # local em vez de manter a Etapa 2 vazia.
        st.session_state[chave_tabela] = list(dados_ambientes)

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

    if (
        chave not in st.session_state
        or st.session_state.get(chave) not in etapas
    ):
        st.session_state[chave] = etapas[0]

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


def _garantir_dimensionamento_fisico(
    dxf_bytes,
    tabela_editada,
    local_qdc,
    config_atual,
    parametros_projeto
):
    """
    Fase 13.6 Rev.124:
    cálculo compartilhado pelas páginas Dimensionamento, Eletrodutos
    e Materiais. O cache também considera método B1/B2 e temperatura.
    """
    if not dxf_bytes or not local_qdc:
        return None

    rotulo_metodo = str(
        st.session_state.get(
            "fase12_1_metodo_instalacao_rotulo",
            "B1 — Condutores isolados em eletroduto embutido na parede"
        )
        or "B1"
    )

    metodo = (
        "B2"
        if rotulo_metodo.upper().startswith("B2")
        else "B1"
    )

    temperatura = int(
        st.session_state.get(
            "fase12_1_temperatura_ambiente",
            30
        )
        or 30
    )

    resumo_cache = st.session_state.get(
        "dimensionamento_rotas"
    )

    cache_compativel = False

    if (
        st.session_state.get("dimensionamento_rotas_projeto")
        == st.session_state.get("projeto_ativo")
        and st.session_state.get("dimensionamento_rotas_versao")
        == VERSAO_SISTEMA
        and isinstance(resumo_cache, dict)
    ):
        iterativo_cache = (
            resumo_cache.get(
                "dimensionamento_iterativo",
                {}
            )
            or {}
        )

        metodo_cache = str(
            iterativo_cache.get(
                "metodo_instalacao",
                ""
            )
            or ""
        ).upper()

        temperatura_cache = int(
            iterativo_cache.get(
                "temperatura_ambiente_c",
                0
            )
            or 0
        )

        cache_compativel = (
            metodo_cache == metodo
            and temperatura_cache == temperatura
        )

    if cache_compativel:
        return resumo_cache

    resumo = calcular_rotas_antes_do_dxf(
        dxf_bytes=dxf_bytes,
        tabela_editada=tabela_editada,
        local_qdc=local_qdc,
        config_interruptores_usuario=config_atual,
        tensao_projeto=parametros_projeto["tensao_projeto"],
        pe_direito=parametros_projeto["pe_direito"],
        metodo_instalacao=metodo,
        temperatura_ambiente_c=temperatura,
    )

    if isinstance(resumo, dict):
        st.session_state["dimensionamento_rotas"] = resumo
        st.session_state["dimensionamento_rotas_projeto"] = (
            st.session_state.get("projeto_ativo")
        )
        st.session_state["dimensionamento_rotas_versao"] = (
            VERSAO_SISTEMA
        )

    return resumo



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
        st.caption(
            "Configure os dados básicos do projeto, a localização, o perfil normativo de fornecimento "
            "e os parâmetros da planta que serão utilizados nas próximas etapas."
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
        st.caption(
            "Confira e, se necessário, ajuste as cargas previstas de cada ambiente "
            "antes de prosseguir para o dimensionamento do projeto elétrico."
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
        st.caption(
            "Defina a posição do quadro de distribuição na planta. Esta etapa é importante para o quantitativo."
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

        # REV.238 — alerta visual somente quando o perfil normativo realmente
        # altera automaticamente a modalidade escolhida para o projeto.
        if resultado_demanda.get("fornecimento_alterado_automaticamente"):
            aviso_fornecimento = str(resultado_demanda.get("aviso_alteracao_fornecimento") or "").strip()
            if aviso_fornecimento:
                st.warning(
                    "⚠️ **Modalidade de fornecimento alterada automaticamente**\n\n"
                    + aviso_fornecimento
                )

        status = resultado_demanda.get("status")
        if status == "aguardando_perfil":
            st.info(
                "ℹ️ O método automático está selecionado. Selecione em Parâmetros "
                "um perfil normativo ATIVO liberado pelo administrador. "
                "Nenhum fator de demanda é inventado pelo sistema."
            )
        elif status == "cargas_sem_regra":
            parcial = resultado_demanda.get("potencia_demanda_parcial_w")
            st.warning(
                "⚠️ O perfil normativo ATIVO foi aplicado às cargas reconhecidas, "
                "mas existem TUEs sem categoria/regra automática. Por segurança, "
                "o AutoElétrica não fecha a demanda total enquanto houver pendências."
            )
            if parcial is not None:
                st.caption(f"Demanda normativa parcial das cargas classificadas: {parcial/1000:.2f} kW")
            for pendencia in resultado_demanda.get("pendencias", []):
                st.caption(f"• {pendencia}")
        elif status == "ok_com_criterio_tecnico":
            # REV.218 — mensagem verde removida da interface da Etapa 3.
            # O critério continua registrado no resultado e nos relatórios técnicos.
            pass
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
        detalhes_demanda = resultado_demanda.get("detalhes_demanda") or []
        # REV.218 — memória técnica mantida no motor, ocultada da interface.
        if False and detalhes_demanda:
            with st.expander("📋 Memória do cálculo de demanda", expanded=False):
                perfil_usado = resultado_demanda.get("perfil_normativo")
                if perfil_usado:
                    st.caption(f"Perfil aplicado: {perfil_usado}")
                linhas_memoria = []
                for item in detalhes_demanda:
                    linhas_memoria.append({
                        "Categoria": item.get("categoria", ""),
                        "Carga instalada (kW)": round(float(item.get("carga_instalada_w", 0) or 0) / 1000.0, 3),
                        "Quantidade": item.get("quantidade"),
                        "Fator": item.get("fator"),
                        "Demanda (kW)": round(float(item.get("demanda_w", 0) or 0) / 1000.0, 3),
                        "Regra": item.get("tabela_id", ""),
                    })
                st.dataframe(linhas_memoria, use_container_width=True, hide_index=True)

        memoria_entrada = resultado_demanda.get("memoria_dimensionamento_entrada") or {}
        # REV.218 — memória de entrada mantida no motor, ocultada da interface.
        if False and memoria_entrada and resultado_demanda.get("corrente_demanda_a") is not None:
            with st.expander("⚡ Memória do dimensionamento de entrada", expanded=True):
                p_kw = float(memoria_entrada.get("potencia_demanda_w", 0) or 0) / 1000.0
                st.write(f"**Fornecimento:** {memoria_entrada.get('tipo_fornecimento','')} — {memoria_entrada.get('tensao_fornecimento','')}")
                if memoria_entrada.get("descricao"):
                    st.caption(memoria_entrada.get("descricao"))
                formula = memoria_entrada.get("formula", "")
                vcalc = memoria_entrada.get("tensao_calculo_v")
                corrente_calc = memoria_entrada.get("corrente_demanda_a")
                if formula:
                    st.write(f"**Fórmula aplicada:** `{formula}`")
                if str(memoria_entrada.get("tipo_fornecimento")) == "Trifásico" and vcalc:
                    st.write(f"**Substituição:** I = {p_kw:.2f} kW × 1000 / (√3 × {float(vcalc):.0f} V) = **{float(corrente_calc):.1f} A**")
                elif corrente_calc is not None:
                    st.write(f"**Corrente calculada:** **{float(corrente_calc):.1f} A**")
                dg_mem = memoria_entrada.get("disjuntor_geral_a")
                if dg_mem is not None:
                    st.write(f"**DG pré-selecionado:** **{dg_mem} A** — {memoria_entrada.get('criterio_dg','')}")
                st.info("O DG exibido é uma pré-seleção elétrica. A seleção definitiva deve ser confrontada com a tabela de padrão de entrada do perfil da concessionária e com o dimensionamento do alimentador (capacidade de condução, queda de tensão, curto-circuito e coordenação).")
                perfil_usado = resultado_demanda.get("perfil_normativo")
                if perfil_usado:
                    st.caption(f"Rastreabilidade do cálculo: {perfil_usado}")

        # REV.218 — dimensionamento do alimentador continua automático e persistido,
        # porém seus controles/memória deixam de ser exibidos na Etapa 3.
        if resultado_demanda.get("corrente_demanda_a") is not None and resultado_demanda.get("disjuntor_geral_a") is not None:
            metodo_alim = st.session_state.get("rev209_metodo_alimentador", "B1")
            temp_alim = st.session_state.get("rev209_temp_alimentador", 30)
            comp_alim = float(st.session_state.get("rev209_comprimento_alimentador", 0.0) or 0.0)
            fator_ag = float(st.session_state.get("rev209_fator_agrupamento", 1.0) or 1.0)
            limite_q = float(st.session_state.get("rev209_limite_queda_alimentador", 2.0) or 2.0)
            mem = resultado_demanda.get("memoria_dimensionamento_entrada") or {}
            alim = dimensionar_alimentador_geral(
                resultado_demanda.get("corrente_demanda_a"),
                resultado_demanda.get("disjuntor_geral_a"),
                mem.get("tipo_fornecimento", ""),
                mem.get("tensao_calculo_v", 220),
                metodo_alim, temp_alim, comp_alim, limite_q, fator_ag
            )
            # REV.211 — integra o fechamento do alimentador às demais saídas.
            # O bloco fica dentro dos parâmetros de rede já persistidos pelo projeto,
            # sem criar nova tabela/estrutura de banco e sem alterar o desenho aprovado.
            rede_integrada = dict(config_atual.get(CHAVE_PARAMETROS_REDE, {}) or {})
            # REV.237 — a modalidade definida pelo perfil normativo passa a ser a
            # fonte única de verdade do projeto. A Rev.236 usava essa modalidade
            # para calcular Ib/DG, mas mantinha o tipo antigo no restante do QDC,
            # causando, por exemplo, DG 80 A 1P e balanceamento somente na Fase A.
            # Persistimos a modalidade/tensão efetivas antes de materiais,
            # balanceamento, proteção, unifilar e demais consumidores.
            tipo_efetivo = resultado_demanda.get("tipo_fornecimento")
            tensao_efetiva = resultado_demanda.get("tensao_fornecimento")
            if tipo_efetivo and tipo_efetivo != "A definir":
                rede_integrada["tipo_fornecimento"] = tipo_efetivo
            if tensao_efetiva and tensao_efetiva != "A definir":
                rede_integrada["tensao_fornecimento"] = tensao_efetiva
            rede_integrada["fornecimento_auto_perfil"] = bool(
                resultado_demanda.get("fornecimento_auto_perfil")
            )
            # REV.212 — congela também o resultado de demanda que originou
            # Ib/In e o fechamento do alimentador. Relatórios e unifilar devem
            # consumir este mesmo resultado, sem recalcular a demanda.
            rede_integrada["demanda_fechada"] = {
                "total_w": resultado_demanda.get("total_w"),
                "potencia_demanda_w": resultado_demanda.get("potencia_demanda_w"),
                "potencia_demanda_parcial_w": resultado_demanda.get("potencia_demanda_parcial_w"),
                "corrente_demanda_a": resultado_demanda.get("corrente_demanda_a"),
                "disjuntor_geral_a": resultado_demanda.get("disjuntor_geral_a"),
                "tipo_fornecimento": resultado_demanda.get("tipo_fornecimento"),
                "tensao_fornecimento": resultado_demanda.get("tensao_fornecimento"),
                "fornecimento_auto_perfil": bool(resultado_demanda.get("fornecimento_auto_perfil")),
                "fornecimento_alterado_automaticamente": bool(resultado_demanda.get("fornecimento_alterado_automaticamente")),
                "tipo_fornecimento_anterior": resultado_demanda.get("tipo_fornecimento_anterior"),
                "tensao_fornecimento_anterior": resultado_demanda.get("tensao_fornecimento_anterior"),
                "aviso_alteracao_fornecimento": resultado_demanda.get("aviso_alteracao_fornecimento"),
                "status": resultado_demanda.get("status"),
                "perfil_normativo": resultado_demanda.get("perfil_normativo"),
                "memoria_dimensionamento_entrada": resultado_demanda.get("memoria_dimensionamento_entrada"),
                "detalhes_demanda": resultado_demanda.get("detalhes_demanda"),
                "origem": "QDC_DEMANDA_FECHADA_REV212",
            }
            rede_integrada["alimentador_geral"] = {
                "metodo": alim.get("metodo"),
                "temperatura_c": alim.get("temperatura_referencia_c"),
                "material": alim.get("material"),
                "isolacao": alim.get("isolacao"),
                "condutores_carregados": alim.get("condutores_carregados"),
                "fator_temperatura": alim.get("fator_temperatura"),
                "fator_agrupamento": alim.get("fator_agrupamento"),
                "comprimento_m": alim.get("comprimento_m"),
                "limite_queda_pct": alim.get("limite_queda_pct"),
                "queda_tensao_v": alim.get("queda_tensao_v"),
                "queda_tensao_pct": alim.get("queda_tensao_pct"),
                "secao_por_capacidade_mm2": alim.get("secao_por_capacidade_mm2"),
                "secao_por_queda_mm2": alim.get("secao_por_queda_mm2"),
                "secao_final_mm2": alim.get("secao_final_mm2"),
                "fase_mm2": alim.get("fase_mm2"),
                "neutro_mm2": alim.get("neutro_mm2"),
                "pe_mm2": alim.get("pe_mm2"),
                "iz_corrigida_a": alim.get("iz_corrigida_a"),
                "ib_a": alim.get("ib_a"),
                "in_a": alim.get("in_a"),
                "criterio_determinante": alim.get("criterio_determinante"),
                "atende_ib_in_iz": alim.get("atende_ib_in_iz"),
                "status_queda": alim.get("status_queda"),
            }
            config_atual[CHAVE_PARAMETROS_REDE] = rede_integrada
            st.session_state[chave_config] = dict(config_atual)
            parametros_projeto["parametros_rede"] = rede_integrada
            st.session_state[chave_parametros] = dict(parametros_projeto)

            # REV.213 — persistência imediata do snapshot fechado no QDC.
            # Na Rev.212 os dados existiam apenas no session_state; ao gerar o
            # Memorial por outro fluxo, o relatório podia reler do Supabase a
            # configuração anterior e concluir incorretamente que o alimentador
            # ainda não estava fechado. Persistimos somente quando o snapshot
            # mudou, evitando escrita desnecessária a cada rerun do Streamlit.
            config_persistida = dict((dados_obj or {}).get("config_interruptores", {}) or {})
            rede_persistida = dict(config_persistida.get(CHAVE_PARAMETROS_REDE, {}) or {})
            precisa_persistir_213 = (
                rede_persistida.get("demanda_fechada") != rede_integrada.get("demanda_fechada")
                or rede_persistida.get("alimentador_geral") != rede_integrada.get("alimentador_geral")
            )
            if precisa_persistir_213:
                try:
                    salvar_dados_projeto(
                        st.session_state.user_email,
                        st.session_state.projeto_ativo,
                        config_interruptores=dict(config_atual),
                    )
                    # Mantém o objeto carregado coerente durante o mesmo rerun.
                    dados_obj["config_interruptores"] = dict(config_atual)
                except Exception as e:
                    st.warning(
                        "⚠️ O cálculo foi concluído, mas não foi possível persistir "
                        f"o fechamento do alimentador no projeto: {e}"
                    )

        renderizar_materiais(
            tabela_editada,
            config_atual,
            local_qdc,
            tensao_projeto=parametros_projeto["tensao_projeto"],
            pe_direito=parametros_projeto["pe_direito"],
            pagina="qdc"
        )

        return

    # --------------------------------------------------------
    # ETAPA 4 — INTERRUPTORES
    # --------------------------------------------------------
    if etapa == "💡 Interruptores":
        st.subheader(
            "💡 Posicionamento dos Interruptores"
        )
        st.caption(
            "Nos ambientes abaixo, organizados em **duas colunas**, escolha **diretamente na mini planta** "
            "quais portas receberão interruptores. Clique em uma porta para selecionar ou retirar a seleção."
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
        st.caption(
            "Escolha na mini planta onde cada tomada alta será instalada. "
            "**Ar-condicionado** permanece centralizado no trecho escolhido. "
            "Para **chuveiro**, depois escolha também o ponto desejado na parede."
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
    # ETAPA 6 — DIMENSIONAMENTO DOS CIRCUITOS
    # --------------------------------------------------------
    if etapa == "⚙️ Dimensionamento":
        st.subheader(
            "⚙️ Dimensionamento dos Circuitos"
        )

        st.markdown(
            "#### 🧱 Método de instalação e temperatura"
        )

        metodo_opcoes = [
            "B1 — Condutores isolados em eletroduto embutido na parede",
            "B2 — Cabo multipolar em eletroduto embutido na parede",
        ]

        metodo_atual = str(
            st.session_state.get(
                "fase12_1_metodo_instalacao_rotulo",
                metodo_opcoes[0]
            )
            or metodo_opcoes[0]
        )

        if metodo_atual not in metodo_opcoes:
            metodo_atual = (
                metodo_opcoes[1]
                if metodo_atual.upper().startswith("B2")
                else metodo_opcoes[0]
            )

        metodo_selecionado = st.selectbox(
            "Método de instalação",
            metodo_opcoes,
            index=metodo_opcoes.index(
                metodo_atual
            ),
            key="fase13_3_metodo_instalacao_ui"
        )

        temperatura_selecionada = st.selectbox(
            "Temperatura ambiente de referência",
            [30, 35, 40, 45, 50, 55, 60],
            index=(
                [30, 35, 40, 45, 50, 55, 60].index(
                    int(
                        st.session_state.get(
                            "fase12_1_temperatura_ambiente",
                            30
                        )
                        or 30
                    )
                )
                if int(
                    st.session_state.get(
                        "fase12_1_temperatura_ambiente",
                        30
                    )
                    or 30
                )
                in [30, 35, 40, 45, 50, 55, 60]
                else 0
            ),
            format_func=lambda valor: f"{valor} °C",
            key="fase13_3_temperatura_ui"
        )

        st.session_state[
            "fase12_1_metodo_instalacao_rotulo"
        ] = metodo_selecionado

        st.session_state[
            "fase12_1_temperatura_ambiente"
        ] = temperatura_selecionada

        with st.expander(
            "ℹ️ Como escolher entre B1 e B2?",
            expanded=False
        ):
            st.markdown(
                "**B1:** condutores isolados individualmente dentro de "
                "eletroduto embutido na parede.\n\n"
                "**B2:** cabo multipolar dentro de eletroduto embutido "
                "na parede.\n\n"
                "A escolha altera a capacidade de condução usada no "
                "pré-dimensionamento. O sistema não deve assumir B1 "
                "silenciosamente quando o usuário pode definir o método."
            )

        if not local_qdc:
            st.warning(
                "Defina primeiro a posição do QDC."
            )
            return

        try:
            with st.spinner(
                "Calculando roteamento e dimensionamento elétrico..."
            ):
                _garantir_dimensionamento_fisico(
                    dxf_bytes,
                    tabela_editada,
                    local_qdc,
                    config_atual,
                    parametros_projeto
                )
        except Exception as exc:
            st.warning(
                "Não foi possível concluir o dimensionamento: "
                f"{exc}"
            )

        renderizar_materiais(
            tabela_editada,
            config_atual,
            local_qdc,
            tensao_projeto=parametros_projeto["tensao_projeto"],
            pe_direito=parametros_projeto["pe_direito"],
            pagina="dimensionamento"
        )
        return

    # --------------------------------------------------------
    # ETAPA 7 — ELETRODUTOS
    # --------------------------------------------------------
    if etapa == "🧵 Eletrodutos":
        st.subheader(
            "🧵 Eletrodutos e Rotas Físicas"
        )

        if not local_qdc:
            st.warning(
                "Defina primeiro a posição do QDC."
            )
            return

        try:
            with st.spinner(
                "Conferindo rotas, ocupação e agrupamento..."
            ):
                _garantir_dimensionamento_fisico(
                    dxf_bytes,
                    tabela_editada,
                    local_qdc,
                    config_atual,
                    parametros_projeto
                )
        except Exception as exc:
            st.warning(
                "Não foi possível concluir a análise dos eletrodutos: "
                f"{exc}"
            )

        renderizar_materiais(
            tabela_editada,
            config_atual,
            local_qdc,
            tensao_projeto=parametros_projeto["tensao_projeto"],
            pe_direito=parametros_projeto["pe_direito"],
            pagina="eletrodutos"
        )
        return

    # --------------------------------------------------------
    # ETAPA 8 — MATERIAIS
    # --------------------------------------------------------
    if etapa == "📦 Materiais":
        st.subheader(
            "📦 Quantitativo de Materiais"
        )
        st.caption(
            "Quantidades obtidas diretamente do projeto, com base no roteamento "
            "físico calculado automaticamente pelo sistema."
        )

        if dxf_bytes and local_qdc:
            try:
                with st.spinner(
                    "Atualizando quantitativo com as rotas físicas..."
                ):
                    _garantir_dimensionamento_fisico(
                        dxf_bytes,
                        tabela_editada,
                        local_qdc,
                        config_atual,
                        parametros_projeto
                    )
            except Exception as exc:
                st.warning(
                    "O quantitativo será exibido com os dados disponíveis. "
                    f"Detalhe: {exc}"
                )

        renderizar_materiais(
            tabela_editada,
            config_atual,
            local_qdc,
            tensao_projeto=parametros_projeto["tensao_projeto"],
            pe_direito=parametros_projeto["pe_direito"],
            pagina="materiais"
        )
        return

    # --------------------------------------------------------
    # ETAPA 9 — SALVAR / EXPORTAR / GERAR CAD
    # --------------------------------------------------------
    if etapa == "📐 Gerar Projeto":
        st.subheader(
            "📐 Salvar e Gerar Projeto"
        )

        st.caption(
            "Revise as etapas anteriores e, quando estiver tudo "
            "correto, salve as configurações e gere os arquivos."
        )

        # REV.231 — o Memorial usa exatamente o mesmo roteamento físico
        # já empregado pelo Quantitativo de Materiais, mesmo sem exportar o DXF.
        resumo_rotas_memorial = None
        if dxf_bytes and local_qdc:
            try:
                resumo_rotas_memorial = _garantir_dimensionamento_fisico(
                    dxf_bytes,
                    tabela_editada,
                    local_qdc,
                    config_atual,
                    parametros_projeto
                )
            except Exception:
                # Mantém o fluxo de geração disponível; o Memorial exibirá
                # os dados que estiverem efetivamente calculados.
                resumo_rotas_memorial = st.session_state.get("dimensionamento_rotas")

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
            ),
            resumo_rotas=resumo_rotas_memorial
        )

        return
