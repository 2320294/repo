import os
import tempfile

import streamlit as st

import motores

from versao import VERSAO_SISTEMA, VERSAO_ARQUIVO, BUILD_ID

from database import (
    salvar_dados_projeto
)

from exportacoes import (
    gerar_memorial_pdf
)


def calcular_rotas_antes_do_dxf(
    dxf_bytes, tabela_editada, local_qdc,
    config_interruptores_usuario, tensao_projeto=220, pe_direito=2.80
):
    """Fase 12.2: calcula o resumo físico antes da exportação do DXF."""
    if not dxf_bytes or not local_qdc:
        return None
    resultado = motores.gerar_cad_unifilar(
        dxf_bytes=dxf_bytes,
        dados_editados=tabela_editada,
        local_qdc=local_qdc,
        config_interruptores=config_interruptores_usuario,
        tensao_projeto=tensao_projeto,
        pe_direito=pe_direito,
        retornar_resumo_rotas=True,
    )
    if isinstance(resultado, tuple) and len(resultado) == 2:
        if isinstance(resultado[1], dict):
            return resultado[1]
    return None


def renderizar_upload_dxf(
    dxf_bytes,
    dados_ambientes,
    config_salva
):
    """
    Upload inicial / substituição do DXF.

    Fase 12.2:
    - o file_uploader recebe uma chave com nonce;
    - após salvar com sucesso, o nonce é incrementado;
    - no rerun seguinte, nasce um uploader novo e vazio;
    - o mesmo arquivo não é processado repetidamente;
    - elimina o ciclo contínuo de rerun ("bicicletinha").
    """

    tem_dxf_salvo = (
        dxf_bytes is not None
        and len(dados_ambientes) > 0
    )

    # Mensagem flash exibida somente depois do rerun de sucesso.
    mensagem_flash = st.session_state.pop(
        "mensagem_upload_dxf",
        None
    )

    if mensagem_flash:
        st.success(mensagem_flash)

    # --------------------------------------------------------
    # UPLOAD INICIAL
    # --------------------------------------------------------
    if not tem_dxf_salvo:
        st.subheader(
            "📁 Enviar Planta Base (Formato DXF)"
        )

        nonce_inicial = st.session_state.get(
            "upload_inicial_nonce",
            0
        )

        uploaded_file = st.file_uploader(
            "Envie o arquivo DXF para iniciar "
            "o dimensionamento:",
            type=["dxf"],
            key=f"upload_inicial_{nonce_inicial}"
        )

        if uploaded_file is not None:
            novo_dxf = uploaded_file.getvalue()

            try:
                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".dxf"
                ) as tmp:
                    tmp.write(novo_dxf)
                    tmp_path = tmp.name

                try:
                    novos_dados = motores.processar_dxf(
                        tmp_path
                    )
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

                salvar_dados_projeto(
                    st.session_state.user_email,
                    st.session_state.projeto_ativo,
                    dxf_bytes=novo_dxf,
                    tabela_editada=novos_dados,
                    config_interruptores=config_salva
                )

                # Troca a chave do uploader ANTES do rerun.
                st.session_state[
                    "upload_inicial_nonce"
                ] = nonce_inicial + 1

                st.session_state[
                    "mensagem_upload_dxf"
                ] = (
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

    # --------------------------------------------------------
    # SUBSTITUIÇÃO / REENVIO
    # --------------------------------------------------------
    with st.expander(
        "🔄 Reenviar / Substituir Planta Baixa (DXF)"
    ):
        st.markdown(
            "Envie um novo DXF caso a geometria "
            "tenha sido alterada."
        )

        nonce_substituicao = st.session_state.get(
            "upload_substituicao_nonce",
            0
        )

        novo_uploaded_file = st.file_uploader(
            "Envie a nova planta base (.dxf):",
            type=["dxf"],
            key=(
                "upload_substituicao_"
                f"{nonce_substituicao}"
            )
        )

        if novo_uploaded_file is not None:
            novo_dxf = novo_uploaded_file.getvalue()

            try:
                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".dxf"
                ) as tmp:
                    tmp.write(novo_dxf)
                    tmp_path = tmp.name

                try:
                    novos_dados = motores.processar_dxf(
                        tmp_path
                    )
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

                salvar_dados_projeto(
                    st.session_state.user_email,
                    st.session_state.projeto_ativo,
                    dxf_bytes=novo_dxf,
                    tabela_editada=novos_dados,
                    config_interruptores=config_salva
                )

                # PONTO PRINCIPAL DA CORREÇÃO:
                # cria uma nova chave de uploader no próximo ciclo.
                # Assim o arquivo recém-enviado não reaparece como
                # novo input e não dispara processamento infinito.
                st.session_state[
                    "upload_substituicao_nonce"
                ] = nonce_substituicao + 1

                st.session_state[
                    "mensagem_upload_dxf"
                ] = (
                    "✅ Nova planta baixa substituída "
                    "no Supabase!"
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

    st.subheader(
        "💾 Finalização do Projeto"
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
    # MEMORIAL DESCRITIVO
    # ========================================================

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
    VERSAO_CAD = VERSAO_SISTEMA
    st.info(
        f"🔖 Versão atual do gerador CAD: **{VERSAO_CAD}** — Build **{BUILD_ID}**",
        icon="ℹ️",
    )

    # Nunca reaproveita CAD de uma fase anterior. Ao detectar mudança de
    # versão, descarta o arquivo persistido e exige uma nova geração.
    if st.session_state.get("cad_gerado_versao") != VERSAO_CAD:
        st.session_state.pop("cad_gerado_bytes", None)
        st.session_state.pop("cad_gerado_projeto", None)
        st.session_state.pop("cad_gerado_tamanho", None)
        st.session_state.pop("cad_gerado_versao", None)
        st.session_state.pop("dimensionamento_rotas", None)
        st.session_state.pop("dimensionamento_rotas_projeto", None)
        st.session_state.pop("dimensionamento_rotas_versao", None)

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

                    resultado_cad = motores.gerar_cad_unifilar(
                        dxf_bytes=dxf_bytes,
                        dados_editados=tabela_editada,
                        local_qdc=local_qdc,
                        config_interruptores=(
                            config_interruptores_usuario
                        ),
                        tensao_projeto=tensao_projeto,
                        pe_direito=pe_direito,
                        retornar_resumo_rotas=True,
                    )

                    if (
                        isinstance(
                            resultado_cad,
                            tuple
                        )
                        and len(
                            resultado_cad
                        ) == 2
                    ):
                        (
                            cad_bytes_out,
                            resumo_rotas
                        ) = resultado_cad
                    else:
                        cad_bytes_out = resultado_cad
                        resumo_rotas = None

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
                st.session_state["cad_gerado_versao"] = VERSAO_CAD

                if resumo_rotas:
                    st.session_state[
                        "dimensionamento_rotas"
                    ] = resumo_rotas
                    st.session_state[
                        "dimensionamento_rotas_projeto"
                    ] = st.session_state.projeto_ativo
                    st.session_state[
                        "dimensionamento_rotas_versao"
                    ] = VERSAO_CAD

                st.session_state.pop("cad_gerado_erro", None)
                cad_gerado_neste_ciclo = True

            except Exception as e:
                st.session_state.pop("cad_gerado_bytes", None)
                st.session_state.pop("cad_gerado_projeto", None)
                st.session_state.pop("cad_gerado_tamanho", None)
                st.session_state.pop("cad_gerado_versao", None)
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

    if (
        cad_salvo
        and projeto_cad == st.session_state.projeto_ativo
        and st.session_state.get("cad_gerado_versao") == VERSAO_CAD
    ):
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

        st.download_button(
            label=f"📥 Baixar Projeto DXF Atualizado — {VERSAO_CAD}",
            data=bytes(cad_salvo),
            file_name=(
                f"{nome_seguro}_Projeto_Eletrico_{VERSAO_ARQUIVO}.dxf"
            ),
            # application/octet-stream força o navegador a tratar o DXF
            # como arquivo para download, sem tentar interpretá-lo.
            mime="application/octet-stream",
            use_container_width=True,
            key=f"download_cad_atualizado_{VERSAO_ARQUIVO}",
            # Fase 12.2:
            # impede o rerun do Streamlit no clique do download.
            # O rerun podia reconstruir a página antes de o navegador
            # iniciar a transferência do DXF.
            on_click="ignore",
        )

        st.caption(
            f"Arquivo DXF pronto para download: {tamanho / 1024:.1f} KB"
        )

