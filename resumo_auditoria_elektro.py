"""Resumo somente de leitura; não concede homologação ou ativação."""
from auditoria_perfil_elektro import assinatura
from neoenergia_elektro import eh_perfil_elektro


def resumir(perfil):
    if not eh_perfil_elektro(perfil):
        return []
    regras = perfil.get("regras") or {}
    atual = assinatura(perfil)
    linhas = []
    itens = (
        ("Testes manuais de enquadramento", "registro_testes_enquadramento_elektro", "manual"),
        ("Testes automáticos da demanda integrada", "validacao_automatica_integracao_elektro", "automatico"),
        ("Conferência documental parcial", "conferencia_documental_parcial_elektro", "documental"))
    for titulo, chave, tipo in itens:
        registro = regras.get(chave) or {}
        estado = "Não registrado"
        acao = "Registrar a evidência na seção correspondente."
        if registro:
            if registro.get("assinatura_perfil") != atual:
                estado = "Desatualizado"
                acao = "Repetir a conferência com as regras atuais."
            elif tipo == "automatico" and registro.get("passou") is not True:
                estado = "Testes com falha"
                acao = "Revisar os casos com falha e executar novamente."
            elif tipo == "documental" and not all((registro.get("confirmacoes") or {}).get(k) is True for k in ("documento", "escopo_demanda", "tabela_entrada")):
                estado = "Registro incompleto"
                acao = "Conferir e registrar os três itens documentais."
            else:
                estado = "Evidência atual — escopo parcial"
                acao = "Preservar a evidência; não equivale à homologação normativa."
        linhas.append({"Etapa": titulo, "Situação": estado, "Próximo passo": acao})
    for titulo, acao in (
        ("Faixas conflitantes", "Obter esclarecimento documental e concluir a conferência técnica; manter os bloqueios."),
        ("Atendimento e tensão por endereço", "Confirmar a cobertura e a tensão local; o vínculo do município não confirma o endereço."),
        ("Demanda efetiva, DG e alimentador", "Concluir a homologação técnica antes da aplicação ao projeto."),
        ("Entrada e proteção completas", "Conferir curto-circuito, atuação da proteção, neutro, PE e aterramento.")):
        linhas.append({"Etapa": titulo, "Situação": "Pendente de homologação", "Próximo passo": acao})
    return linhas


def resumo_projeto(salvo, contexto, resultado):
    if not isinstance(salvo, dict):
        return "Não salva", "Preencher e salvar a conferência no QDC."
    if salvo.get("assinatura_contexto_projeto") != contexto or salvo.get("demanda_integrada") != resultado:
        return "Desatualizada", "Refazer a conferência com as cargas e o contexto atuais."
    status = (salvo.get("verificacao_ramal") or {}).get("status")
    if status == "nao_atende":
        return "Critério não atendido", "Revisar os dados e o dimensionamento com o responsável técnico."
    if status == "criterios_informados_atendidos":
        return "Dois critérios informados atendidos", "Concluir a validação completa; o registro não aprova a entrada."
    return "Dados ou confirmação pendentes", "Completar os dados técnicos e conferir sua aplicabilidade."


def renderizar(perfil, chave):
    import streamlit as st
    import json
    linhas = resumir(perfil)
    if not linhas:
        return
    with st.expander("Resumo da auditoria do perfil Elektro"):
        st.table(linhas)
        st.caption("Resumo das evidências cadastradas e pendências. Testes de software e conferência parcial não homologam o perfil. Mantenha em RASCUNHO até concluir a homologação.")
        st.download_button("Baixar resumo da auditoria Elektro (JSON)",
            data=json.dumps({"perfil_id": perfil.get("id"), "documento": perfil.get("documento"),
                "revisao": perfil.get("revisao"), "assinatura_perfil": assinatura(perfil),
                "homologado": False, "etapas": linhas}, ensure_ascii=False, indent=2),
            file_name="Resumo_Auditoria_Perfil_Elektro.json", mime="application/json", key=chave)


def resumir_projeto(atendimento, rede, perfil, entrada, contexto, resultado):
    from atendimento_endereco_elektro import situacao
    estado = situacao(atendimento, rede, perfil)
    if estado == "Não registrado":
        passo = "Registrar os dados do endereço ou indicar que ainda não os possui."
    elif estado.startswith("Desatualizado"):
        passo = "Conferir a fonte para a localidade, tensão e perfil atuais e salvar novo registro."
    elif estado.startswith("Evidência declarada completa"):
        passo = "Obter validação técnica da evidência; dados declarados não aprovam o atendimento."
    else:
        passo = "Completar os dados e confirmar a fonte aplicável ao endereço."
    estado_entrada, passo_entrada = resumo_projeto(entrada, contexto, resultado)
    return [{"Etapa": "Atendimento e tensão por endereço", "Situação": estado, "Próximo passo": passo},
        {"Etapa": "Conferência de entrada e ramal", "Situação": estado_entrada, "Próximo passo": passo_entrada}]


def renderizar_projeto(atendimento, rede, perfil, entrada, contexto, resultado):
    import streamlit as st
    with st.expander("Resumo da auditoria deste projeto — Elektro"):
        st.table(resumir_projeto(atendimento, rede, perfil, entrada, contexto, resultado))
        st.caption("Resumo dos registros salvos deste projeto. Evidência declarada e critérios informados atendidos exigem validação técnica. Os bloqueios normativos permanecem e não há liberação de DG ou alimentador.")
