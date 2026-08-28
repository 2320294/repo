import os
import tempfile

import streamlit as st

import motores

from database import (
    salvar_dados_projeto
)

from exportacoes import (
    gerar_excel_projeto,
    gerar_memorial_pdf
)


def renderizar_upload_dxf(
    dxf_bytes,
    dados_ambientes,
    config_salva
):
    """
    Renderiza upload inicial ou substituição da planta.
    Retorna True se houve rerun/alteração e False caso contrário.
    """
    tem_dxf_salvo = (
        dxf_bytes is not None
        and len(dados_ambientes) > 0
    )

    if not tem_dxf_salvo:
        st.subheader(
            "📁 Enviar Planta Base (Formato DXF)"
        )

        uploaded_file = st.file_uploader(
            "Envie o arquivo DXF para iniciar "
            "o dimensionamento:",
            type=["dxf"],
            key="upload_inicial"
        )

        if uploaded_file is not None:
            novo_dxf = uploaded_file.read()

            try:
                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".dxf"
                ) as tmp:
                    tmp.write(novo_dxf)
                    tmp_path = tmp.name

                try:
                    novos_dados = (
                        motores.processar_dxf(
                            tmp_path
                        )
                    )
                finally:
                    if os.path.exists(
                        tmp_path
                    ):
                        os.remove(tmp_path)

                salvar_dados_projeto(
                    st.session_state.user_email,
                    st.session_state.projeto_ativo,
                    dxf_bytes=novo_dxf,
                    tabela_editada=novos_dados,
                    config_interruptores=config_salva
                )

                st.success(
                    "✅ Planta baixa processada e "
                    "salva no Supabase!"
                )

                st.rerun()

            except Exception as e:
                st.error(
                    f"❌ Erro ao processar/salvar "
                    f"o DXF: {e}"
                )

        return False

    with st.expander(
        "🔄 Reenviar / Substituir Planta Baixa (DXF)"
    ):
        st.markdown(
            "Envie um novo DXF caso a geometria "
            "tenha sido alterada."
        )

        novo_uploaded_file = st.file_uploader(
            "Envie a nova planta base (.dxf):",
            type=["dxf"],
            key="upload_substituicao"
        )

        if novo_uploaded_file is not None:
            novo_dxf = (
                novo_uploaded_file.read()
            )

            try:
                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".dxf"
                ) as tmp:
                    tmp.write(novo_dxf)
                    tmp_path = tmp.name

                try:
                    novos_dados = (
                        motores.processar_dxf(
                            tmp_path
                        )
                    )
                finally:
                    if os.path.exists(
                        tmp_path
                    ):
                        os.remove(tmp_path)

                salvar_dados_projeto(
                    st.session_state.user_email,
                    st.session_state.projeto_ativo,
                    dxf_bytes=novo_dxf,
                    tabela_editada=novos_dados,
                    config_interruptores=config_salva
                )

                st.success(
                    "✅ Nova planta baixa "
                    "substituída no Supabase!"
                )

                st.rerun()

            except Exception as e:
                st.error(
                    f"❌ Erro ao substituir "
                    f"o DXF: {e}"
                )

    return True


def renderizar_salvar_e_gerar_cad(
    dxf_bytes,
    tabela_editada,
    local_qdc,
    config_interruptores_usuario,
    tensao_projeto,
    pe_direito
):
    st.divider()

    st.subheader(
        "🖨️ Exportação e Relatórios"
    )

    if st.button(
        "💾 Salvar Alterações do Projeto",
        use_container_width=True
    ):
        try:
            salvar_dados_projeto(
                st.session_state.user_email,
                st.session_state.projeto_ativo,
                tabela_editada=tabela_editada,
                local_qdc=local_qdc,
                config_interruptores=(
                    config_interruptores_usuario
                ),
                tensao_projeto=tensao_projeto,
                pe_direito=pe_direito
            )

            st.success(
                "✅ Alterações salvas no "
                "Supabase com sucesso!"
            )

            st.rerun()

        except Exception as e:
            st.error(
                f"❌ Erro ao salvar alterações: {e}"
            )

    # ========================================================
    # EXCEL E MEMORIAL DESCRITIVO
    # ========================================================

    col_excel, col_pdf = st.columns(2)

    with col_excel:
        try:
            excel_bytes = gerar_excel_projeto(
                tabela_editada=tabela_editada,
                config_interruptores_usuario=(
                    config_interruptores_usuario
                ),
                local_qdc=local_qdc,
                tensao_projeto=tensao_projeto,
                pe_direito=pe_direito
            )

            st.download_button(
                label="📊 Baixar Planilha (Excel)",
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

    with col_pdf:
        try:
            pdf_bytes = gerar_memorial_pdf(
                nome_projeto=(
                    st.session_state.projeto_ativo
                ),
                tabela_editada=tabela_editada,
                config_interruptores_usuario=(
                    config_interruptores_usuario
                ),
                local_qdc=local_qdc,
                tensao_projeto=tensao_projeto,
                pe_direito=pe_direito
            )

            st.download_button(
                label="📄 Baixar Memorial Descritivo (PDF)",
                data=pdf_bytes,
                file_name=(
                    f"{st.session_state.projeto_ativo}"
                    "_Memorial_Descritivo.pdf"
                ),
                mime="application/pdf",
                use_container_width=True
            )

        except Exception as e:
            st.error(
                f"❌ Erro ao preparar memorial PDF: {e}"
            )

    st.markdown(
        "### Projeto Unifilar (DXF)"
    )

    if st.button(
        "🚀 Gerar CAD (Atualizado)",
        type="primary",
        use_container_width=True
    ):
        if not dxf_bytes:
            st.error(
                "❌ Nenhum arquivo DXF associado."
            )

        else:
            try:
                salvar_dados_projeto(
                    st.session_state.user_email,
                    st.session_state.projeto_ativo,
                    tabela_editada=tabela_editada,
                    local_qdc=local_qdc,
                    config_interruptores=(
                        config_interruptores_usuario
                    ),
                    tensao_projeto=tensao_projeto,
                    pe_direito=pe_direito
                )

                cad_bytes_out = (
                    motores.gerar_cad_unifilar(
                        dxf_bytes=dxf_bytes,
                        dados_editados=tabela_editada,
                        local_qdc=local_qdc,
                        config_interruptores=(
                            config_interruptores_usuario
                        )
                    )
                )

                # Guarda o DXF gerado na sessão. Isso é necessário porque
                # o Streamlit executa novamente a página a cada interação;
                # se o download ficar somente dentro do st.button(), ele
                # pode desaparecer no rerun seguinte.
                st.session_state["cad_gerado_bytes"] = cad_bytes_out
                st.session_state["cad_gerado_projeto"] = (
                    st.session_state.projeto_ativo
                )

                st.success(
                    "✅ Projeto CAD gerado com sucesso! "
                    "O botão de download está disponível abaixo."
                )

            except Exception as e:
                # Evita oferecer um arquivo antigo se a nova geração falhar.
                st.session_state.pop("cad_gerado_bytes", None)
                st.session_state.pop("cad_gerado_projeto", None)
                st.error(
                    f"❌ Erro ao gerar o arquivo CAD: {e}"
                )

    # O botão de download fica FORA do botão de geração e é persistido
    # no session_state. Assim continua visível após os reruns do Streamlit.
    cad_salvo = st.session_state.get("cad_gerado_bytes")
    projeto_cad = st.session_state.get("cad_gerado_projeto")

    if (
        cad_salvo
        and projeto_cad == st.session_state.projeto_ativo
    ):
        nome_seguro = str(
            st.session_state.projeto_ativo
        ).strip() or "Projeto"

        st.download_button(
            label="📥 Baixar Projeto DXF Atualizado",
            data=cad_salvo,
            file_name=f"{nome_seguro}_Projeto_Eletrico.dxf",
            mime="application/dxf",
            use_container_width=True,
            key="download_cad_atualizado"
        )
