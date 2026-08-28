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

    # Marcador visual para confirmar no Streamlit que esta versão
    # do arquivo upload_cad.py foi realmente publicada/carregada.
    VERSAO_CAD = "Fase 4.6"
    st.info(
        f"🔖 Versão atual do gerador CAD: **{VERSAO_CAD}**",
        icon="ℹ️",
    )

    # --------------------------------------------------------
    # O clique apenas grava uma solicitação persistente.
    # Em alguns reruns do Streamlit, executar todo o CAD dentro
    # do retorno booleano de st.button() pode fazer o evento se
    # perder. O session_state evita isso.
    # --------------------------------------------------------
    if "solicitar_geracao_cad" not in st.session_state:
        st.session_state["solicitar_geracao_cad"] = False

    # Indicadores locais desta execução. Não ficam persistidos entre
    # reruns, portanto a mensagem de sucesso só aparece imediatamente
    # após um clique real em "Gerar CAD".
    cad_gerado_neste_ciclo = False
    erro_cad_neste_ciclo = None

    if st.button(
        "🚀 Gerar CAD (Atualizado)",
        type="primary",
        use_container_width=True,
        key="btn_gerar_cad_atualizado",
    ):
        st.session_state["solicitar_geracao_cad"] = True
        st.session_state.pop("cad_gerado_erro", None)

    # A geração acontece fora do bloco do botão, usando o estado
    # persistente. Dessa forma, mesmo que haja rerun, a solicitação
    # continua verdadeira até o processamento terminar.
    if st.session_state.get("solicitar_geracao_cad", False):
        if not dxf_bytes:
            st.session_state["solicitar_geracao_cad"] = False
            erro_cad_neste_ciclo = (
                "Nenhum arquivo DXF associado ao projeto."
            )
        else:
            try:
                with st.spinner("Gerando o projeto CAD atualizado..."):
                    salvar_dados_projeto(
                        st.session_state.user_email,
                        st.session_state.projeto_ativo,
                        tabela_editada=tabela_editada,
                        local_qdc=local_qdc,
                        config_interruptores=(
                            config_interruptores_usuario
                        ),
                        tensao_projeto=tensao_projeto,
                        pe_direito=pe_direito,
                    )

                    cad_bytes_out = motores.gerar_cad_unifilar(
                        dxf_bytes=dxf_bytes,
                        dados_editados=tabela_editada,
                        local_qdc=local_qdc,
                        config_interruptores=(
                            config_interruptores_usuario
                        ),
                    )

                    if cad_bytes_out is None:
                        raise RuntimeError(
                            "A rotina gerar_cad_unifilar retornou vazio."
                        )

                    # Garante bytes reais para o download.
                    if isinstance(cad_bytes_out, bytearray):
                        cad_bytes_out = bytes(cad_bytes_out)
                    elif not isinstance(cad_bytes_out, bytes):
                        try:
                            cad_bytes_out = bytes(cad_bytes_out)
                        except Exception as exc:
                            raise TypeError(
                                "O CAD foi gerado em um formato que não "
                                "pode ser baixado como arquivo DXF."
                            ) from exc

                    if len(cad_bytes_out) == 0:
                        raise RuntimeError(
                            "O arquivo DXF gerado ficou vazio."
                        )

                st.session_state["cad_gerado_bytes"] = cad_bytes_out
                st.session_state["cad_gerado_projeto"] = (
                    st.session_state.projeto_ativo
                )
                st.session_state["cad_gerado_tamanho"] = len(
                    cad_bytes_out
                )
                st.session_state.pop("cad_gerado_erro", None)
                cad_gerado_neste_ciclo = True

            except Exception as e:
                st.session_state.pop("cad_gerado_bytes", None)
                st.session_state.pop("cad_gerado_projeto", None)
                st.session_state.pop("cad_gerado_tamanho", None)
                erro_cad_neste_ciclo = str(e)

            finally:
                # Só libera a solicitação depois que tentou processar.
                st.session_state["solicitar_geracao_cad"] = False

    if erro_cad_neste_ciclo:
        st.error(
            f"❌ Erro ao gerar o arquivo CAD ({VERSAO_CAD}): "
            f"{erro_cad_neste_ciclo}"
        )

    cad_salvo = st.session_state.get("cad_gerado_bytes")
    projeto_cad = st.session_state.get("cad_gerado_projeto")

    if cad_salvo and projeto_cad == st.session_state.projeto_ativo:
        nome_seguro = str(
            st.session_state.projeto_ativo
        ).strip() or "Projeto"

        tamanho = st.session_state.get("cad_gerado_tamanho", len(cad_salvo))

        # A mensagem verde aparece SOMENTE no rerun provocado pelo clique
        # em Gerar CAD. O arquivo continua guardado para download.
        if cad_gerado_neste_ciclo:
            st.success(
                f"✅ Projeto CAD {VERSAO_CAD} gerado com sucesso! "
                f"Arquivo preparado ({tamanho / 1024:.1f} KB)."
            )

        versao_arquivo = VERSAO_CAD.replace(" ", "_").replace(".", "_")
        st.download_button(
            label=f"📥 Baixar Projeto DXF Atualizado — {VERSAO_CAD}",
            data=cad_salvo,
            file_name=(
                f"{nome_seguro}_Projeto_Eletrico_{versao_arquivo}.dxf"
            ),
            mime="application/dxf",
            use_container_width=True,
            key="download_cad_atualizado_v45",
        )

