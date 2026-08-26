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

from materiais import (
    renderizar_materiais
)

from parametros_projeto import (
    renderizar_parametros_projeto
)

from upload_cad import (
    renderizar_upload_dxf,
    renderizar_salvar_e_gerar_cad
)


def renderizar_painel_principal():

    st.title(
        f"⚡ Painel de Projetos Elétricos — "
        f"Olá, {st.session_state.user_name}!"
    )

    if (
        st.session_state.projeto_ativo
        == "Selecione um projeto..."
    ):
        st.info(
            "👈 Selecione um projeto na barra lateral "
            "ou cadastre um novo."
        )
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
        dados_obj.get("dxf_bytes")
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

    renderizar_upload_dxf(
        dxf_bytes=dxf_bytes,
        dados_ambientes=dados_ambientes,
        config_salva=config_salva
    )

    if not dados_ambientes:
        return

    tabela_editada = (
        renderizar_edicao_cargas(
            dados_ambientes
        )
    )

    renderizar_tabela_consolidada(
        tabela_editada
    )

    parametros_projeto = (
        renderizar_parametros_projeto(
            tensao_projeto_salva,
            pe_direito_salvo
        )
    )

    local_qdc = renderizar_qdc(
        dados_ambientes,
        local_qdc_salvo
    )

    config_interruptores_usuario = (
        renderizar_interruptores(
            dados_ambientes,
            config_salva
        )
    )

    renderizar_materiais(
        tabela_editada,
        config_interruptores_usuario,
        local_qdc,
        tensao_projeto=parametros_projeto["tensao_projeto"],
        pe_direito=parametros_projeto["pe_direito"]
    )

    renderizar_salvar_e_gerar_cad(
        dxf_bytes=dxf_bytes,
        tabela_editada=tabela_editada,
        local_qdc=local_qdc,
        config_interruptores_usuario=(
            config_interruptores_usuario
        ),
        tensao_projeto=parametros_projeto["tensao_projeto"],
        pe_direito=parametros_projeto["pe_direito"]
    )
