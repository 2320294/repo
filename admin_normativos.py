import json
import streamlit as st
from perfis_normativos import listar_perfis, salvar_perfil, atualizar_status
from concessionarias import UFS


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


def renderizar_admin_normativos(email):
    st.title("⚙️ Administração — Perfis Normativos")
    st.caption("Somente perfis ATIVOS são disponibilizados aos usuários. O cadastro não altera automaticamente os cálculos da versão estável.")
    try:
        perfis = listar_perfis(False)
    except Exception as e:
        st.error("Banco de perfis normativos ainda não preparado. Execute o arquivo supabase_perfis_normativos.sql no Supabase.")
        st.code(str(e))
        return

    with st.expander("➕ Novo perfil normativo", expanded=not bool(perfis)):
        with st.form("novo_perfil_normativo"):
            c1,c2,c3=st.columns(3)
            concessionaria=c1.text_input("Concessionária")
            uf=c2.selectbox("UF", UFS)
            municipio=c3.text_input("Município (vazio = toda a UF)")
            documento=st.text_input("Documento / norma oficial")
            c4,c5=st.columns(2)
            revisao=c4.text_input("Revisão")
            vigencia=c5.text_input("Data/vigência")
            fonte=st.text_input("Fonte / referência oficial")
            regras=st.text_area("Regras estruturadas (JSON)", value="{}", height=130, help="Infraestrutura para as regras oficiais. O motor automático de demanda continuará bloqueado até validação específica da regra.")
            if st.form_submit_button("Salvar como RASCUNHO", use_container_width=True):
                try:
                    regras_json=json.loads(regras or "{}")
                    salvar_perfil({"concessionaria":concessionaria.strip(),"uf":uf,"municipio":municipio.strip(),"documento":documento.strip(),"revisao":revisao.strip(),"vigencia":vigencia.strip(),"fonte_oficial":fonte.strip(),"regras":regras_json,"status":"RASCUNHO","criado_por":email})
                    st.success("Perfil salvo como RASCUNHO.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Não foi possível salvar: {e}")

    if not perfis:
        st.info("Nenhum perfil cadastrado.")
        return
    st.subheader("Perfis cadastrados")
    for p in perfis:
        titulo=f"{p.get('concessionaria','')} — {p.get('municipio') or 'Toda a UF'}/{p.get('uf','')} — {p.get('documento') or 'Sem documento'} {p.get('revisao') or ''}"
        with st.expander(f"{titulo} · {p.get('status','RASCUNHO')}"):
            st.write(f"**Fonte:** {p.get('fonte_oficial') or '—'}")
            st.json(p.get("regras") or {})
            cols=st.columns(4)
            for col,status in zip(cols,["RASCUNHO","VALIDADO","ATIVO","INATIVO"]):
                if col.button(status, key=f"status_{p.get('id')}_{status}", use_container_width=True):
                    try:
                        atualizar_status(p.get("id"), status, email)
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
