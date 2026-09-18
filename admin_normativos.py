import json
import streamlit as st
from perfis_normativos import listar_perfis, salvar_perfil, atualizar_status
from concessionarias import UFS

CATEGORIAS_DEMANDA = [
    ("iluminacao_tug", "Iluminação + TUG"),
    ("chuveiros", "Chuveiros / aquecimento elétrico"),
    ("ar_condicionado", "Ar-condicionado"),
    ("motores", "Motores"),
    ("demais_tues", "Demais TUEs"),
]


def _emails_admin_secrets():
    try:
        bloco = st.secrets.get("admin", {})
        valor = bloco.get("emails", []) if hasattr(bloco, "get") else []
        if isinstance(valor, str):
            return {x.strip().lower() for x in valor.split(",") if x.strip()}
        return {str(x).strip().lower() for x in valor if str(x).strip()}
    except Exception:
        return set()


def usuario_e_admin(email):
    email = str(email or "").strip().lower()
    if not email:
        return False
    if email in _emails_admin_secrets():
        return True
    try:
        from config import obter_supabase
        r = obter_supabase().table("usuarios").select("role").eq("email", email).limit(1).execute()
        return bool(r.data and str(r.data[0].get("role", "")).upper() == "ADMIN")
    except Exception:
        return False


def _numero(txt):
    txt = str(txt or "").strip().replace(".", "").replace(",", ".") if "," in str(txt or "") else str(txt or "").strip()
    if not txt:
        return None
    try:
        return float(txt)
    except Exception:
        return None


def _texto_numero(valor):
    if valor in (None, ""):
        return ""
    try:
        n = float(valor)
        return str(int(n)) if n.is_integer() else str(n).replace(".", ",")
    except Exception:
        return str(valor)


def _regras_base(regras=None):
    r = regras if isinstance(regras, dict) else {}
    return {
        "schema": "autoeletrica.perfil_normativo.v1",
        "tipo_instalacao": r.get("tipo_instalacao", "Residencial individual"),
        "fornecimento": dict(r.get("fornecimento") or {}),
        "demanda": dict(r.get("demanda") or {}),
        "observacoes": r.get("observacoes", ""),
        "fonte_conferida": bool(r.get("fonte_conferida", False)),
    }


def _perfil_pronto(regras):
    if not isinstance(regras, dict) or regras.get("schema") != "autoeletrica.perfil_normativo.v1":
        return False
    if not regras.get("fonte_conferida"):
        return False
    f = regras.get("fornecimento") or {}
    return bool(f.get("tensao_fase_neutro_v") and f.get("tensao_fase_fase_v"))


def _editor_regras(prefixo, regras=None):
    r = _regras_base(regras)
    f = r["fornecimento"]
    demanda = r["demanda"]

    st.markdown("#### Aplicação e fornecimento")
    tipo = st.selectbox(
        "Tipo de instalação atendida pelo perfil",
        ["Residencial individual", "Comercial individual", "Misto", "Outro"],
        index=max(0, ["Residencial individual", "Comercial individual", "Misto", "Outro"].index(r["tipo_instalacao"])) if r["tipo_instalacao"] in ["Residencial individual", "Comercial individual", "Misto", "Outro"] else 0,
        key=f"{prefixo}_tipo",
    )
    c1, c2, c3 = st.columns(3)
    vfn = c1.text_input("Tensão fase-neutro (V)", value=_texto_numero(f.get("tensao_fase_neutro_v")), key=f"{prefixo}_vfn")
    vff = c2.text_input("Tensão fase-fase (V)", value=_texto_numero(f.get("tensao_fase_fase_v")), key=f"{prefixo}_vff")
    limite = c3.text_input("Limite de fornecimento (kVA)", value=_texto_numero(f.get("limite_fornecimento_kva")), key=f"{prefixo}_lim")
    fases = st.multiselect(
        "Modalidades permitidas",
        ["Monofásico", "Bifásico", "Trifásico"],
        default=f.get("modalidades", []),
        key=f"{prefixo}_fases",
    )

    st.markdown("#### Regras de demanda")
    st.caption("Cadastre somente fatores/faixas confirmados na norma oficial. Campos vazios permanecem sem regra e não são inventados pelo sistema.")
    demanda_saida = {}
    for chave, rotulo in CATEGORIAS_DEMANDA:
        atual = demanda.get(chave) or {}
        with st.expander(rotulo, expanded=False):
            metodo = st.selectbox(
                "Método",
                ["Não cadastrado", "Fator único (%)", "Tabela por faixas", "Regra específica"],
                index=["Não cadastrado", "Fator único (%)", "Tabela por faixas", "Regra específica"].index(atual.get("metodo", "Não cadastrado")) if atual.get("metodo", "Não cadastrado") in ["Não cadastrado", "Fator único (%)", "Tabela por faixas", "Regra específica"] else 0,
                key=f"{prefixo}_{chave}_metodo",
            )
            fator = st.text_input("Fator de demanda (%)", value=_texto_numero(atual.get("fator_percentual")), key=f"{prefixo}_{chave}_fator", disabled=metodo != "Fator único (%)")
            tabela = st.text_area("Tabela/faixas ou regra oficial", value=atual.get("regra_texto", ""), height=90, key=f"{prefixo}_{chave}_regra", disabled=metodo not in ("Tabela por faixas", "Regra específica"), help="Transcreva de forma estruturada/resumida a regra confirmada no documento oficial; não é necessário editar JSON.")
            demanda_saida[chave] = {"metodo": metodo}
            if metodo == "Fator único (%)":
                demanda_saida[chave]["fator_percentual"] = _numero(fator)
            elif metodo in ("Tabela por faixas", "Regra específica"):
                demanda_saida[chave]["regra_texto"] = tabela.strip()

    obs = st.text_area("Observações normativas / exceções", value=r.get("observacoes", ""), height=90, key=f"{prefixo}_obs")
    conferida = st.checkbox(
        "Confirmo que os dados acima foram conferidos no documento oficial indicado neste perfil.",
        value=bool(r.get("fonte_conferida")),
        key=f"{prefixo}_conf",
    )
    return {
        "schema": "autoeletrica.perfil_normativo.v1",
        "tipo_instalacao": tipo,
        "fornecimento": {
            "tensao_fase_neutro_v": _numero(vfn),
            "tensao_fase_fase_v": _numero(vff),
            "limite_fornecimento_kva": _numero(limite),
            "modalidades": fases,
        },
        "demanda": demanda_saida,
        "observacoes": obs.strip(),
        "fonte_conferida": conferida,
    }


def renderizar_admin_normativos(email):
    st.title("⚙️ Administração — Perfis Normativos")
    st.caption("Somente perfis ATIVOS são disponibilizados aos usuários. O cadastro não altera automaticamente os cálculos da versão estável.")
    try:
        perfis = listar_perfis(False, administrativo=True)
    except Exception as e:
        st.error("Banco de perfis normativos ainda não preparado. Execute o arquivo supabase_perfis_normativos.sql no Supabase.")
        st.code(str(e))
        return

    with st.expander("➕ Novo perfil normativo", expanded=not bool(perfis)):
        with st.form("novo_perfil_normativo"):
            c1, c2, c3 = st.columns(3)
            concessionaria = c1.text_input("Concessionária")
            uf = c2.selectbox("UF", UFS)
            municipio = c3.text_input("Município (vazio = toda a UF)")
            documento = st.text_input("Documento / norma oficial")
            c4, c5 = st.columns(2)
            revisao = c4.text_input("Revisão")
            vigencia = c5.text_input("Data/vigência")
            fonte = st.text_input("Fonte / referência oficial")
            regras_json = _editor_regras("novo")
            if st.form_submit_button("Salvar como RASCUNHO", use_container_width=True):
                try:
                    salvar_perfil({"concessionaria": concessionaria.strip(), "uf": uf, "municipio": municipio.strip(), "documento": documento.strip(), "revisao": revisao.strip(), "vigencia": vigencia.strip(), "fonte_oficial": fonte.strip(), "regras": regras_json, "status": "RASCUNHO", "criado_por": email})
                    st.success("Perfil salvo como RASCUNHO.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Não foi possível salvar: {e}")

    if not perfis:
        st.info("Nenhum perfil cadastrado.")
        return

    st.subheader("Perfis cadastrados")
    for p in perfis:
        titulo = f"{p.get('concessionaria','')} — {p.get('municipio') or 'Toda a UF'}/{p.get('uf','')} — {p.get('documento') or 'Sem documento'} {p.get('revisao') or ''}"
        with st.expander(f"{titulo} · {p.get('status','RASCUNHO')}"):
            st.write(f"**Fonte:** {p.get('fonte_oficial') or '—'}")
            regras_atual = p.get("regras") or {}
            with st.form(f"editar_perfil_{p.get('id')}"):
                regras_editadas = _editor_regras(f"edit_{p.get('id')}", regras_atual)
                if st.form_submit_button("Salvar regras deste perfil", use_container_width=True):
                    try:
                        salvar_perfil({"regras": regras_editadas}, perfil_id=p.get("id"))
                        st.success("Regras salvas.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível atualizar: {e}")

            pronto = _perfil_pronto(regras_atual)
            if not pronto:
                st.info("Perfil ainda incompleto: mantenha em RASCUNHO até preencher e conferir os dados oficiais mínimos.")
            cols = st.columns(4)
            for col, status in zip(cols, ["RASCUNHO", "VALIDADO", "ATIVO", "INATIVO"]):
                bloquear = status in ("VALIDADO", "ATIVO") and not pronto
                if col.button(status, key=f"status_{p.get('id')}_{status}", use_container_width=True, disabled=bloquear):
                    try:
                        atualizar_status(p.get("id"), status, email)
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
