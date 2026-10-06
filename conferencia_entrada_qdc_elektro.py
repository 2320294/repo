"""Conferência integrada ao QDC, sem aplicar DG, cabos ou materiais."""
import hashlib
import json
import streamlit as st
from componentes_entrada_elektro import consultar_componentes, URL_FONTE
from verificacao_ramal_elektro import verificar_ramal


def assinatura_registro(registro):
    return hashlib.sha256(json.dumps({k: registro.get(k) for k in
        ("assinatura_contexto_projeto", "demanda_integrada", "componentes", "dados_ramal", "selecoes_informadas")},
        sort_keys=True, default=str).encode()).hexdigest()


def renderizar(resultado, chave_projeto, contexto=None, salvo=None, salvar=None, projeto=None):
    aviso_salvo = chave_projeto("entrada_salva_aviso")
    if st.session_state.pop(aviso_salvo, False):
        st.success('Conferência salva no projeto. Resumo atualizado; ao reabrir, a confirmação técnica deverá ser refeita.')
    auditoria = resultado.get("enquadramento_elektro") or {}
    candidato = auditoria.get("candidato") or {}
    salvo = salvo if isinstance(salvo, dict) else None
    contexto_igual = bool(salvo and salvo.get("assinatura_contexto_projeto") == contexto
        and salvo.get("demanda_integrada") == resultado)
    if salvo:
        with st.expander("Última conferência de entrada e ramal salva no projeto"):
            st.caption("Registro de " + str(salvo.get("registrado_em_utc", "data não informada")) + " (UTC)")
            if contexto_igual:
                st.info("Registro histórico correspondente às cargas e ao contexto atuais. Confira os dados do ramal antes de reutilizar.")
            else:
                st.warning("Conferência desatualizada: as cargas, o perfil ou o contexto do projeto mudaram. Faça nova conferência.")
            historico = salvo.get("verificacao_ramal") or {}
            st.write("Resultado salvo: " + str(historico.get("status", "pendente")))
            if historico.get("criterios"):
                st.table(historico["criterios"])
            st.caption("Registro histórico sem aprovação técnica; não aplica DG ou alimentador.")
            st.download_button("Baixar última conferência salva (JSON)", data=json.dumps(salvo, ensure_ascii=False, indent=2, allow_nan=False),
                file_name="Conferencia_Entrada_Ramal_Elektro_Salva.json", mime="application/json", key=chave_projeto("entrada_salva_json"))
    with st.expander("Conferir entrada e ramal Elektro no QDC — teste"):
        if auditoria.get("status") != "candidato" or auditoria.get("pendencias") or candidato.get("modalidade") != "Trifásico":
            st.info("Esta etapa exige categoria trifásica candidata fora das faixas bloqueadas, com contexto e dados completos. A demanda pode ser consultada; a conferência de entrada e ramal permanece pendente.")
            return
        st.caption(f"Categoria candidata {candidato.get('categoria')} — disjuntor de referência da tabela: {candidato.get('disjuntor_tabela_a')} A. Não aplicado como DG do projeto.")
        # O escopo inclui todo o cálculo atual: alterações das cargas ou do contexto
        # trocam as chaves e não reaproveitam dados confirmados para outro cenário.
        escopo = hashlib.sha256(json.dumps([resultado, contexto], sort_keys=True, default=str).encode()).hexdigest()[:20]
        def chave(campo):
            return chave_projeto(f"qdc_elektro_{escopo}_{campo}")
        # Recupera valores somente no mesmo contexto; a confirmação não é restaurada.
        if contexto_igual:
            selecoes_salvas = salvo.get("selecoes_informadas") or {}
            dados_salvos = salvo.get("dados_ramal") or {}
            defaults = dict(selecoes_salvas)
            defaults.update({k: v for k, v in dados_salvos.items() if k not in ("confirmado", "sem_dados")})
            defaults["modo"] = "Não tenho esses dados" if dados_salvos.get("sem_dados") else "Informar dados para conferência"
            for campo, valor in defaults.items():
                if chave(campo) not in st.session_state:
                    st.session_state[chave(campo)] = valor
        tipo = st.selectbox("Tipo do ramal de entrada", ["Não informado", "Embutido", "Subterrâneo"], key=chave("tipo"))
        isolacao_entrada = st.selectbox("Isolação do ramal de entrada", ["Não informada", "XLPE/HEPR", "PVC"], key=chave("isolacao_entrada"))
        isolacao = st.selectbox("Isolação do ramal de distribuição", ["Não informada", "XLPE/HEPR", "PVC"], key=chave("isolacao_distribuicao"))
        componentes = consultar_componentes(auditoria, tipo, isolacao_entrada, isolacao)
        if componentes.get("linhas"):
            st.table(componentes["linhas"])
        for nome, valor in componentes.get("selecoes", {}).items():
            st.write(f"**{nome}:** {valor}")
        for item in componentes.get("pendencias", []):
            st.caption("• " + item)
        st.markdown(f"[Consultar Tabela 3 na fonte oficial]({URL_FONTE})")
        modo = st.radio("Dados para conferir o ramal", ["Não tenho esses dados", "Informar dados para conferência"], key=chave("modo"))
        dados = {"sem_dados": modo == "Não tenho esses dados", "confirmado": False}
        if dados["sem_dados"]:
            st.info("Capacidade e queda de tensão aguardam os dados técnicos. Nenhum valor será presumido.")
        else:
            st.caption("Informe valores documentados pelo responsável técnico. Zero ou campo vazio significa dado desconhecido.")
            for campo, rotulo in (("metodo", "Método de instalação e condições reais"), ("fonte", "Fonte técnica: fabricante, documento, revisão e tabela/página")):
                dados[campo] = st.text_input(rotulo, key=chave(campo))
            for campo, rotulo in (
                ("corrente_a", "Corrente de projeto do trecho crítico (A)"),
                ("iz_corrigida_a", "Capacidade de condução já corrigida — Iz (A)"),
                ("comprimento_m", "Comprimento de ida do ramal (m)"),
                ("coeficiente_mv_am", "Coeficiente de queda aplicável ao circuito (mV/A/m)"),
                ("tensao_v", "Tensão de referência do trecho (V)"),
                ("limite_percentual", "Limite de queda disponível para este trecho (%)")):
                dados[campo] = st.number_input(rotulo, min_value=0.0, value=0.0, format="%.3f", key=chave(campo))
            st.caption("O coeficiente deve incorporar a configuração do circuito, fator de potência e temperatura. Não repita multiplicadores já incorporados. O limite deve considerar a queda acumulada nos demais trechos.")
            completos = bool(dados["metodo"].strip() and dados["fonte"].strip()) and all(dados[k] > 0 for k in ("corrente_a", "iz_corrigida_a", "comprimento_m", "coeficiente_mv_am", "tensao_v", "limite_percentual")) and bool(componentes.get("selecoes", {}).get("Ramal de distribuição"))
            assinatura = hashlib.sha256(json.dumps([dados, componentes], sort_keys=True, default=str).encode()).hexdigest()[:20]
            confirmado = st.checkbox("Conferi a aplicabilidade dos dados ao cabo, circuito e condições do trecho", disabled=not completos, key=chave("confirmacao_" + assinatura))
            dados["confirmado"] = bool(completos and confirmado)
        ramal = verificar_ramal(auditoria, componentes, dados)
        if ramal.get("criterios"):
            st.table(ramal["criterios"])
        for item in ramal.get("pendencias", []):
            st.caption("• " + item)
        if ramal["status"] == "nao_atende":
            st.warning("Um ou mais critérios não atendem aos dados informados. Revise o dimensionamento com o responsável técnico.")
        elif ramal["status"] == "criterios_informados_atendidos":
            st.info("Os critérios de capacidade e queda atendem aos dados informados. A validação completa da entrada e do alimentador permanece pendente.")
        st.caption("Não verifica curto-circuito, atuação da proteção, neutro, PE ou aterramento. Não aplica DG, cabos ou materiais ao projeto.")
        registro = {"escopo": "Conferência de entrada e ramal no QDC — teste", "aprovado": False, "demanda_integrada": resultado, "componentes": componentes, "dados_ramal": dados, "verificacao_ramal": ramal}
        registro["assinatura_contexto_projeto"] = contexto
        registro["projeto"] = projeto
        registro["selecoes_informadas"] = {"tipo": tipo, "isolacao_entrada": isolacao_entrada, "isolacao_distribuicao": isolacao}
        if salvo and contexto_igual and assinatura_registro(salvo) != assinatura_registro(registro):
            st.warning("Os dados ou a confirmação do ramal diferem do registro salvo. Reconfira e salve um novo registro.")
        if salvar is not None and st.button("Salvar conferência de entrada e ramal no projeto", key=chave("salvar")):
            from datetime import datetime, timezone
            registro["registrado_em_utc"] = datetime.now(timezone.utc).isoformat()
            try:
                salvar(registro)

            except Exception as erro:
                st.error(f"Não foi possível salvar a conferência: {erro}")
            else:
                st.session_state[aviso_salvo] = True
                st.rerun()
        st.download_button("Baixar conferência de entrada e ramal (JSON)", data=json.dumps(registro, ensure_ascii=False, indent=2, allow_nan=False), file_name="Conferencia_Entrada_Ramal_Elektro_QDC.json", mime="application/json", key=chave("baixar"))
