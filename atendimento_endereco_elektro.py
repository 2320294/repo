"""Evidência declarada por endereço; não substitui confirmação da distribuidora."""
import json
import hashlib
from datetime import datetime, timezone
from auditoria_perfil_elektro import assinatura as assinatura_perfil

CHAVE = "atendimento_endereco_elektro"


def contexto(rede, perfil):
    dados = {"uf": rede.get("uf"), "municipio": rede.get("municipio"),
        "tensao_projeto": rede.get("tensao_fornecimento"), "perfil": assinatura_perfil(perfil)}
    return hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def registrar(rede, perfil, dados, projeto, responsavel):
    sem_dados = dados.get("sem_dados") is True
    entrada = {"sem_dados": sem_dados}
    pendencias = []
    if not rede.get("uf") or not rede.get("municipio"):
        pendencias.append("Selecione UF e município nos parâmetros do projeto.")
    if sem_dados:
        pendencias.append("Atendimento e tensão do endereço aguardam confirmação documentada.")
    else:
        for campo, rotulo in (("endereco", "Endereço completo"), ("fonte", "Fonte da informação"),
                              ("referencia", "Protocolo ou referência documental"), ("data_fonte", "Data da informação")):
            entrada[campo] = str(dados.get(campo) or "").strip()
            if not entrada[campo]:
                pendencias.append(rotulo + " não informado.")
        try:
            data = datetime.strptime(entrada["data_fonte"], "%Y-%m-%d").date()
            if data > datetime.now(timezone.utc).date():
                pendencias.append("A data da fonte não pode estar no futuro.")
        except ValueError:
            pendencias.append("Informe a data da fonte no formato AAAA-MM-DD.")
        entrada["tensao_informada"] = str(dados.get("tensao_informada") or "")
        if entrada["tensao_informada"] not in ("220/127 V", "380/220 V"):
            pendencias.append("Tensão no endereço não informada.")
        esperada = {"127/220 V": "220/127 V", "220/380 V": "380/220 V"}.get(rede.get("tensao_fornecimento"), rede.get("tensao_fornecimento"))
        if entrada["tensao_informada"] in ("220/127 V", "380/220 V") and entrada["tensao_informada"] != esperada:
            pendencias.append("A tensão informada difere da tensão dos parâmetros do projeto.")
        entrada["atendimento_confirmado"] = dados.get("atendimento_confirmado") is True
        entrada["conferido"] = dados.get("conferido") is True
        if not entrada["atendimento_confirmado"]:
            pendencias.append("Atendimento da Elektro neste endereço não confirmado.")
        if not entrada["conferido"]:
            pendencias.append("A aplicabilidade da fonte ao endereço não foi conferida.")
    return {"escopo": "Evidência declarada de atendimento e tensão por endereço",
        "projeto": projeto, "responsavel": responsavel,
        "registrado_em_utc": datetime.now(timezone.utc).isoformat(),
        "assinatura_contexto": contexto(rede, perfil),
        "local": {"uf": rede.get("uf"), "municipio": rede.get("municipio")},
        "entradas": entrada, "pendencias": list(dict.fromkeys(pendencias)),
        "status": "pendente" if pendencias else "evidencia_declarada_completa",
        "aprovado": False, "homologado": False}


def situacao(salvo, rede, perfil):
    if not isinstance(salvo, dict):
        return "Não registrado"
    if salvo.get("assinatura_contexto") != contexto(rede, perfil):
        return "Desatualizado — localidade, tensão ou perfil mudaram"
    return "Evidência declarada completa — exige validação técnica" if salvo.get("status") == "evidencia_declarada_completa" else "Pendente de dados ou conferência"


def linhas_registro(salvo):
    """Apresentação legível sem modificar a evidência ou o JSON exportado."""
    entrada = salvo.get("entradas") or {}
    local = salvo.get("local") or {}
    def valor(campo):
        return str(entrada.get(campo) or "Não informado")
    def confirmacao(campo):
        if campo not in entrada:
            return "Não informado"
        return "Sim" if entrada[campo] is True else "Não"
    data = valor("data_fonte")
    try:
        data = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        pass
    pares = [("UF", local.get("uf") or "Não informada"),
        ("Município", local.get("municipio") or "Não informado"),
        ("Usuário sem dados do endereço", confirmacao("sem_dados")),
        ("Endereço do imóvel", valor("endereco")),
        ("Fonte da informação", valor("fonte")),
        ("Protocolo ou referência documental", valor("referencia")),
        ("Data da informação", data),
        ("Tensão informada", valor("tensao_informada")),
        ("Atendimento confirmado na fonte", confirmacao("atendimento_confirmado")),
        ("Correspondência da fonte com o endereço conferida", confirmacao("conferido"))]
    return [{"Campo": campo, "Informação salva": informacao} for campo, informacao in pares]


def renderizar(rede, perfil, salvo, salvar, chave, projeto, responsavel):
    import streamlit as st
    aviso_salvo = chave("atendimento_salvo_aviso")
    if st.session_state.pop(aviso_salvo, False):
        st.success('Registro salvo. Resumo atualizado; será recuperado ao reabrir o projeto.')
    with st.expander("Atendimento e tensão por endereço — Elektro"):
        st.caption("O município vinculado ao perfil não confirma o atendimento ou a tensão de cada endereço. Registre a fonte aplicável ao imóvel.")
        if isinstance(salvo, dict):
            st.write("Registro salvo: " + situacao(salvo, rede, perfil))
            st.caption("Data do registro: " + str(salvo.get("registrado_em_utc")) + " (UTC)")
            st.table(linhas_registro(salvo))
            for item in salvo.get("pendencias") or []:
                st.caption("• " + item)
            st.download_button("Baixar registro de atendimento salvo (JSON)", data=json.dumps(salvo, ensure_ascii=False, indent=2),
                file_name="Atendimento_Endereco_Elektro.json", mime="application/json", key=chave("atendimento_exportar"))
        escopo = contexto(rede, perfil)[:20]
        def k(campo):return chave("atendimento_" + escopo + "_" + campo)
        modo = st.radio("Informações do endereço", ["Não tenho esses dados", "Informar fonte e tensão do endereço"], key=k("modo"))
        dados = {"sem_dados": modo == "Não tenho esses dados"}
        if dados["sem_dados"]:
            st.info("Você pode continuar a prévia de demanda. Atendimento e tensão ficam pendentes; nenhum valor será presumido.")
        else:
            for campo, rotulo in (("endereco", "Endereço completo do imóvel"), ("fonte", "Fonte: documento ou resposta da distribuidora"),
                ("referencia", "Protocolo, link ou referência documental"), ("data_fonte", "Data da informação (AAAA-MM-DD)")):
                dados[campo] = st.text_input(rotulo, key=k(campo))
            dados["tensao_informada"] = st.selectbox("Tensão informada para este endereço", ["Não informada", "220/127 V", "380/220 V"], key=k("tensao"))
            dados["atendimento_confirmado"] = st.checkbox("A fonte confirma atendimento da Neoenergia Elektro neste endereço", key=k("atendido"))
            assinatura = hashlib.sha256(json.dumps(dados, sort_keys=True).encode()).hexdigest()[:20]
            dados["conferido"] = st.checkbox("Conferi a fonte e sua correspondência com este endereço", key=k("conferido_" + assinatura))
        registro = registrar(rede, perfil, dados, projeto, responsavel)
        for item in registro["pendencias"]:
            st.caption("• " + item)
        if not registro["pendencias"]:
            st.info("Evidência declarada completa. A validação técnica permanece pendente.")
        st.caption("Este registro não altera a tensão do projeto, as confirmações existentes, os bloqueios normativos ou o DG.")
        if st.button("Salvar atendimento e tensão no projeto", key=k("salvar")):
            try:
                salvar(registro)

            except Exception as erro:
                st.error(f"Não foi possível salvar: {erro}")
            else:
                st.session_state[aviso_salvo] = True
                st.rerun()
