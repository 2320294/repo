import os
import tempfile
import pandas as pd
import streamlit as st
from supabase import create_client, Client
import motores

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="AutoElétrica Profissional",
    page_icon="⚡",
    layout="wide"
)

# ============================================================
# SUPABASE
# ============================================================
def obter_credenciais_supabase():
    """
    Lê primeiro o formato usado no Streamlit Cloud:

    [supabase]
    url = "..."
    key = "..."

    Também aceita, como alternativa, variáveis de ambiente
    SUPABASE_URL / SUPABASE_KEY / SUPABASE_ANON_KEY.
    """
    url = ""
    key = ""

    try:
        if "supabase" in st.secrets:
            bloco = st.secrets["supabase"]
            url = str(bloco.get("url", "")).strip()
            key = str(bloco.get("key", "")).strip()
    except Exception:
        pass

    if not url:
        url = os.getenv("SUPABASE_URL", "").strip()

    if not key:
        key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.getenv("SUPABASE_KEY", "").strip()
            or os.getenv("SUPABASE_ANON_KEY", "").strip()
        )

    return url, key


SUPABASE_URL, SUPABASE_KEY = obter_credenciais_supabase()

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error(
        "❌ As credenciais do Supabase não foram encontradas. "
        "No Streamlit Cloud, use o bloco [supabase] com "
        "url e key, exatamente como configurado nos Secrets."
    )
    st.stop()


@st.cache_resource
def obter_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


supabase = obter_supabase()

# ============================================================
# FUNÇÕES DE BANCO
# ============================================================
def buscar_usuario(email, senha):
    resposta = (
        supabase.table("usuarios")
        .select("id,nome,email,senha")
        .eq("email", email.strip())
        .eq("senha", senha)
        .limit(1)
        .execute()
    )
    return resposta.data[0] if resposta.data else None


def cadastrar_usuario(nome, email, senha):
    existente = (
        supabase.table("usuarios")
        .select("id")
        .eq("email", email.strip())
        .limit(1)
        .execute()
    )
    if existente.data:
        return False, "E-mail já cadastrado."

    supabase.table("usuarios").insert({
        "nome": nome.strip(),
        "email": email.strip(),
        "senha": senha
    }).execute()
    return True, "Conta criada! Faça login."


def listar_projetos(email):
    resposta = (
        supabase.table("projetos")
        .select("id,user_email,nome_projeto,created_at")
        .eq("user_email", email)
        .order("nome_projeto")
        .execute()
    )
    return resposta.data or []


def buscar_projeto(email, nome_projeto):
    projeto = (
        supabase.table("projetos")
        .select("id,user_email,nome_projeto,created_at")
        .eq("user_email", email)
        .eq("nome_projeto", nome_projeto)
        .limit(1)
        .execute()
    )
    if not projeto.data:
        return None, None

    projeto = projeto.data[0]
    dados = (
        supabase.table("dados_projetos")
        .select("id,user_email,nome_projeto,dxf_bytes,tabela_editada,local_qdc,config_interruptores,created_at")
        .eq("user_email", email)
        .eq("nome_projeto", nome_projeto)
        .order("id", desc=True)
        .limit(1)
        .execute()
    )
    dados = dados.data[0] if dados.data else None
    return projeto, dados


def criar_projeto(email, nome_projeto):
    nome_projeto = nome_projeto.strip()
    existentes = listar_projetos(email)
    if any(p.get("nome_projeto") == nome_projeto for p in existentes):
        return False, "Já existe um projeto com esse nome."

    supabase.table("projetos").insert({
        "user_email": email,
        "nome_projeto": nome_projeto
    }).execute()

    supabase.table("dados_projetos").insert({
        "user_email": email,
        "nome_projeto": nome_projeto,
        "dxf_bytes": None,
        "tabela_editada": [],
        "local_qdc": None,
        "config_interruptores": {}
    }).execute()
    return True, "Projeto cadastrado e selecionado!"


def apagar_projeto(email, nome_projeto):
    supabase.table("dados_projetos").delete().eq("user_email", email).eq("nome_projeto", nome_projeto).execute()
    supabase.table("projetos").delete().eq("user_email", email).eq("nome_projeto", nome_projeto).execute()


def salvar_dados_projeto(email, nome_projeto, dxf_bytes=None, tabela_editada=None, local_qdc=None, config_interruptores=None):
    existentes = (
        supabase.table("dados_projetos")
        .select("id")
        .eq("user_email", email)
        .eq("nome_projeto", nome_projeto)
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    registro = {}
    if dxf_bytes is not None:
        registro["dxf_bytes"] = "\\x" + bytes(dxf_bytes).hex()
    if tabela_editada is not None:
        registro["tabela_editada"] = tabela_editada
    if local_qdc is not None:
        registro["local_qdc"] = local_qdc
    if config_interruptores is not None:
        registro["config_interruptores"] = config_interruptores

    if existentes.data:
        supabase.table("dados_projetos").update(registro).eq("id", existentes.data[0]["id"]).execute()
    else:
        registro.update({
            "user_email": email,
            "nome_projeto": nome_projeto
        })
        supabase.table("dados_projetos").insert(registro).execute()


def converter_dxf_do_supabase(valor):
    if valor is None:
        return None
    if isinstance(valor, bytes):
        return valor
    if isinstance(valor, bytearray):
        return bytes(valor)
    if isinstance(valor, list):
        try:
            return bytes(valor)
        except Exception:
            return None
    if isinstance(valor, str):
        texto = valor.strip()
        if texto.startswith("\\x"):
            try:
                return bytes.fromhex(texto[2:])
            except Exception:
                return None
        try:
            return bytes.fromhex(texto)
        except Exception:
            return None
    return None

# ============================================================
# ESTADO DE SESSÃO
# ============================================================
for chave, valor in {
    "logged_in": False,
    "user_email": "",
    "user_name": "",
    "projeto_ativo": "Selecione um projeto..."
}.items():
    if chave not in st.session_state:
        st.session_state[chave] = valor

# ============================================================
# BARRA LATERAL
# ============================================================
with st.sidebar:
    st.markdown("## ⚡ AutoElétrica Profissional")
    st.divider()

    if not st.session_state.logged_in:
        aba_auth = st.radio("Acesso ao Sistema", ["Entrar (Login)", "Cadastrar-se"], horizontal=True)

        if aba_auth == "Entrar (Login)":
            st.subheader("🔐 Fazer Login")
            login_email = st.text_input("E-mail / Login", key="login_email")
            login_senha = st.text_input("Senha", type="password", key="login_senha")

            if st.button("Entrar", use_container_width=True):
                if not login_email or not login_senha:
                    st.warning("Preencha o e-mail e a senha.")
                else:
                    try:
                        usuario = buscar_usuario(login_email, login_senha)
                        if usuario:
                            st.session_state.logged_in = True
                            st.session_state.user_email = usuario["email"]
                            st.session_state.user_name = usuario["nome"]
                            st.session_state.projeto_ativo = "Selecione um projeto..."
                            st.rerun()
                        else:
                            st.error("E-mail ou senha incorretos.")
                    except Exception as e:
                        st.error(f"❌ Erro ao consultar o Supabase: {e}")

        else:
            st.subheader("📝 Novo Cadastro")
            cad_nome = st.text_input("Nome Completo", key="cad_nome")
            cad_email = st.text_input("E-mail (Login)", key="cad_email")
            cad_senha = st.text_input("Senha", type="password", key="cad_senha")

            if st.button("Criar Conta", use_container_width=True):
                if not cad_nome or not cad_email or not cad_senha:
                    st.warning("Preencha todos os campos.")
                else:
                    try:
                        ok, mensagem = cadastrar_usuario(cad_nome, cad_email, cad_senha)
                        if ok:
                            st.success(mensagem)
                        else:
                            st.error(mensagem)
                    except Exception as e:
                        st.error(f"❌ Erro ao cadastrar no Supabase: {e}")

    else:
        st.markdown(f"👤 **Olá, {st.session_state.user_name}!**")
        st.caption(f"📧 `{st.session_state.user_email}`")

        if st.button("🚪 Sair / Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.session_state.user_name = ""
            st.session_state.projeto_ativo = "Selecione um projeto..."
            st.rerun()

        st.divider()
        st.markdown("### 📂 Gerenciador de Obras")

        with st.form("form_novo_projeto", clear_on_submit=True):
            novo_proj_nome = st.text_input("Nome do Novo Projeto / Pavimento")
            btn_criar_proj = st.form_submit_button("➕ Cadastrar Projeto")

            if btn_criar_proj:
                if not novo_proj_nome.strip():
                    st.warning("Digite o nome do projeto.")
                else:
                    try:
                        ok, mensagem = criar_projeto(st.session_state.user_email, novo_proj_nome)
                        if ok:
                            st.session_state.projeto_ativo = novo_proj_nome.strip()
                            st.success(mensagem)
                            st.rerun()
                        else:
                            st.warning(mensagem)
                    except Exception as e:
                        st.error(f"❌ Erro ao criar projeto no Supabase: {e}")

        try:
            projetos_usuario = listar_projetos(st.session_state.user_email)
        except Exception as e:
            st.error(f"❌ Erro ao listar projetos: {e}")
            projetos_usuario = []

        st.markdown("### 📋 Seus Projetos Salvos:")
        if projetos_usuario:
            nomes_projetos = [p["nome_projeto"] for p in projetos_usuario]
            opcoes_selectbox = ["Selecione um projeto..."] + nomes_projetos
            indice_atual = opcoes_selectbox.index(st.session_state.projeto_ativo) if st.session_state.projeto_ativo in opcoes_selectbox else 0

            projeto_selecionado = st.selectbox(
                "Selecione o projeto ativo:",
                opcoes_selectbox,
                index=indice_atual,
                key="selectbox_projeto_ativo"
            )

            if projeto_selecionado != st.session_state.projeto_ativo:
                st.session_state.projeto_ativo = projeto_selecionado
                st.rerun()

            if projeto_selecionado != "Selecione um projeto..." and st.button("🗑️ Apagar Projeto Selecionado", type="secondary"):
                try:
                    apagar_projeto(st.session_state.user_email, projeto_selecionado)
                    st.session_state.projeto_ativo = "Selecione um projeto..."
                    st.success(f"Projeto '{projeto_selecionado}' apagado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao apagar projeto: {e}")
        else:
            st.info("Nenhum projeto cadastrado ainda.")
            st.session_state.projeto_ativo = "Selecione um projeto..."

# ============================================================
# BLOQUEIO
# ============================================================
if not st.session_state.logged_in:
    st.warning("⚠️ Faça login ou cadastre-se na barra lateral para acessar o painel.")
    st.stop()

# ============================================================
# PROJETO ATIVO
# ============================================================
st.title(f"⚡ Painel de Projetos Elétricos — Olá, {st.session_state.user_name}!")

if st.session_state.projeto_ativo == "Selecione um projeto...":
    st.info("👈 Selecione um projeto na barra lateral ou cadastre um novo.")
    st.stop()

st.info(f"📁 **Projeto Ativo:** {st.session_state.projeto_ativo}")

try:
    projeto_obj, dados_obj = buscar_projeto(
        st.session_state.user_email,
        st.session_state.projeto_ativo
    )
except Exception as e:
    st.error(f"❌ Erro ao carregar o projeto do Supabase: {e}")
    st.stop()

if not projeto_obj:
    st.error("❌ O projeto selecionado não foi encontrado no Supabase.")
    st.stop()

if dados_obj is None:
    try:
        salvar_dados_projeto(
            st.session_state.user_email,
            st.session_state.projeto_ativo,
            tabela_editada=[],
            config_interruptores={}
        )
        _, dados_obj = buscar_projeto(st.session_state.user_email, st.session_state.projeto_ativo)
    except Exception as e:
        st.error(f"❌ Não foi possível criar os dados do projeto: {e}")
        st.stop()


dxf_bytes = converter_dxf_do_supabase(dados_obj.get("dxf_bytes"))
dados_ambientes = dados_obj.get("tabela_editada") or []
config_salva = dados_obj.get("config_interruptores") or {}
local_qdc_salvo = dados_obj.get("local_qdc")

# ============================================================
# UPLOAD / REENVIO DXF
# ============================================================
tem_dxf_salvo = dxf_bytes is not None and len(dados_ambientes) > 0

if not tem_dxf_salvo:
    st.subheader("📁 Enviar Planta Base (Formato DXF)")
    uploaded_file = st.file_uploader("Envie o arquivo DXF para iniciar o dimensionamento:", type=["dxf"], key="upload_inicial")
    if uploaded_file is not None:
        novo_dxf = uploaded_file.read()
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
                tmp.write(novo_dxf)
                tmp_path = tmp.name
            try:
                novos_dados = motores.processar_dxf(tmp_path)
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
            st.success("✅ Planta baixa processada e salva no Supabase!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Erro ao processar/salvar o DXF: {e}")
else:
    with st.expander("🔄 Reenviar / Substituir Planta Baixa (DXF)"):
        st.markdown("Envie um novo DXF caso a geometria tenha sido alterada.")
        novo_uploaded_file = st.file_uploader("Envie a nova planta base (.dxf):", type=["dxf"], key="upload_substituicao")
        if novo_uploaded_file is not None:
            novo_dxf = novo_uploaded_file.read()
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
                    tmp.write(novo_dxf)
                    tmp_path = tmp.name
                try:
                    novos_dados = motores.processar_dxf(tmp_path)
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
                st.success("✅ Nova planta baixa substituída no Supabase!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao substituir o DXF: {e}")

# ============================================================
# QUADRO DE CARGAS
# ============================================================
if dados_ambientes:
    dados_ambientes = sorted(dados_ambientes, key=lambda x: x.get("Ambiente", ""))

    st.divider()
    st.subheader("📊 Quadro de Previsão de Cargas Consolidado")

    tabela_editada = []
    for row in dados_ambientes:
        ambiente = row["Ambiente"]
        with st.container():
            st.markdown(f"**Ambiente: {ambiente}** — *Área: {float(row.get('Área (m²)', 0)):.2f}m² | Perímetro: {float(row.get('Perímetro (m)', 0)):.2f}m*")
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            with c1:
                q_ilum = st.number_input("Qtd Ilum", min_value=0, value=int(row.get("Qtd Ilum.", 1)), key=f"ilum_{ambiente}")
            with c2:
                p_ilum = st.number_input("Pot Ilum (VA)", min_value=0, value=int(row.get("Pot. Unit. Ilum (VA)", row.get("Pot. Unit. Ilum (W)", 100))), key=f"pilum_{ambiente}")
            with c3:
                qtd_tugs = st.number_input("Qtd TUGs", min_value=0, value=int(row.get("TUGs (Qtd)", 1)), key=f"tugs_{ambiente}")
            with c4:
                pot_tug_unit = st.number_input("Pot TUG (VA)", min_value=0, value=int(row.get("Pot. Unit. TUG (VA)", row.get("Pot. Unit. TUG (W)", 100))), key=f"ptug_{ambiente}")
            with c5:
                qtd_tue = st.number_input("Qtd TUE", min_value=0, value=int(row.get("Qtd TUE", 0)), key=f"tue_{ambiente}")
            with c6:
                pot_tue_unit = st.number_input("Pot TUE (VA)", min_value=0, value=int(row.get("Pot. Unit. TUE (VA)", row.get("Pot. Unit. TUE (W)", 0))), key=f"ptue_{ambiente}")

            eq_tue = st.text_input(f"Equipamento TUE ({ambiente})", value=str(row.get("Equipamento TUE", "-")), key=f"eq_{ambiente}")

            row_modificado = row.copy()
            row_modificado["Qtd Ilum."] = q_ilum
            row_modificado["Pot. Unit. Ilum (VA)"] = p_ilum
            row_modificado["Carga Ilum. (VA)"] = q_ilum * p_ilum
            row_modificado["TUGs (Qtd)"] = qtd_tugs
            row_modificado["Pot. Unit. TUG (VA)"] = pot_tug_unit
            row_modificado["Carga TUGs (VA)"] = qtd_tugs * pot_tug_unit
            row_modificado["Qtd TUE"] = qtd_tue
            row_modificado["Pot. Unit. TUE (VA)"] = pot_tue_unit
            row_modificado["Carga TUE (VA)"] = qtd_tue * pot_tue_unit
            row_modificado["Equipamento TUE"] = eq_tue
            tabela_editada.append(row_modificado)
            st.markdown("---")

    df_consolidado = pd.DataFrame(tabela_editada)
    colunas_para_ocultar = [
        "Centro_X", "Centro_Y",
        "Pot. Unit. Ilum (VA)", "Carga Ilum. (VA)",
        "Pot. Unit. TUG (VA)", "Carga TUGs (VA)",
        "Pot. Unit. TUE (VA)", "Carga TUE (VA)"
    ]
    df_exibicao = df_consolidado.drop(columns=[c for c in colunas_para_ocultar if c in df_consolidado.columns], errors="ignore")
    if "Área (m²)" in df_exibicao.columns:
        df_exibicao["Área (m²)"] = df_exibicao["Área (m²)"].round(2)
    if "Perímetro (m)" in df_exibicao.columns:
        df_exibicao["Perímetro (m)"] = df_exibicao["Perímetro (m)"].round(2)

    linha_total = {
        "Ambiente": "TOTAL GERAL",
        "Área (m²)": round(df_exibicao["Área (m²)"].sum(), 2),
        "Perímetro (m)": round(df_exibicao["Perímetro (m)"].sum(), 2),
        "Qtd Ilum.": int(df_exibicao["Qtd Ilum."].sum()),
        "TUGs (Qtd)": int(df_exibicao["TUGs (Qtd)"].sum()),
        "Equipamento TUE": "-",
        "Qtd TUE": int(df_exibicao["Qtd TUE"].sum())
    }
    st.dataframe(pd.concat([df_exibicao, pd.DataFrame([linha_total])], ignore_index=True), use_container_width=True, hide_index=True)

    # ========================================================
    # QDC
    # ========================================================
    st.divider()
    ambientes_validos_qdc = []
    ambientes_recomendados_qdc = []
    for r in dados_ambientes:
        nome_amb = r["Ambiente"]
        nome_lower = nome_amb.lower()
        is_molhado = any(x in nome_lower for x in ["coz", "serv", "banh", "lav", "sanit", "wc", "as", "área", "area"])
        if is_molhado:
            continue
        is_circulacao = any(x in nome_lower for x in ["hall", "corredor", "circul", "circ"])
        if is_circulacao:
            ambientes_recomendados_qdc.append(f"{nome_amb} (Recomendado)")
        else:
            ambientes_validos_qdc.append(nome_amb)

    opcoes_qdc = ambientes_recomendados_qdc + ambientes_validos_qdc
    if not opcoes_qdc:
        opcoes_qdc = [r["Ambiente"] for r in dados_ambientes]

    indice_qdc = 0
    if local_qdc_salvo:
        candidatos = [local_qdc_salvo, f"{local_qdc_salvo} (Recomendado)"]
        for c in candidatos:
            if c in opcoes_qdc:
                indice_qdc = opcoes_qdc.index(c)
                break

    local_qdc_selecionado = st.selectbox(
        "⚡ Selecione o ambiente onde ficará instalado o QDC:",
        opcoes_qdc,
        index=indice_qdc,
        key="select_qdc"
    )
    local_qdc = local_qdc_selecionado.split(" (Recomendado")[0].strip()

    # ========================================================
    # CONFIGURAÇÃO DE INTERRUPTORES
    # ========================================================
    st.divider()
    st.subheader("⚙️ Configuração de Interruptores nas Soleiras")
    st.markdown("Escolha **0, 1 ou 2 interruptores por ambiente**. Com 2, o motor usará as duas portas/posições disponíveis da soleira. Com 1, escolha qual porta deverá receber o interruptor.")

    nomes_ambientes = [r["Ambiente"] for r in dados_ambientes]
    config_interruptores_usuario = {}

    for amb in nomes_ambientes:
        cfg_atual = config_salva.get(amb, {}) if isinstance(config_salva, dict) else {}
        qtd_salva = max(0, min(2, int(cfg_atual.get("quantidade", 0))))

        with st.expander(f"Interruptores — {amb}"):
            qtd_int = st.selectbox(
                f"Quantidade de interruptores em {amb}",
                [0, 1, 2],
                index=qtd_salva,
                key=f"int_qtd_{amb}"
            )

            if qtd_int == 1:
                porta_salva = max(1, min(2, int(cfg_atual.get("porta", 1))))
                porta_num = st.selectbox(
                    f"Qual porta recebe o interruptor — {amb}",
                    [1, 2],
                    index=porta_salva - 1,
                    key=f"int_porta_{amb}"
                )
                config_interruptores_usuario[amb] = {
                    "quantidade": 1,
                    "porta": porta_num
                }
                st.caption(f"Será desenhado 1 círculo tangente à posição da porta {porta_num}.")
            elif qtd_int == 2:
                config_interruptores_usuario[amb] = {
                    "quantidade": 2
                }
                st.caption("Serão desenhados 2 círculos: um em cada extremidade/posição da soleira associada às portas.")
            else:
                config_interruptores_usuario[amb] = {
                    "quantidade": 0
                }

    # ========================================================
    # MATERIAIS
    # ========================================================
    st.divider()
    st.subheader("📦 Tabela Quantitativa de Materiais")
    total_caixas_luz = sum(int(r.get("Qtd Ilum.", 0)) for r in tabela_editada)
    total_tugs_geral = sum(int(r.get("TUGs (Qtd)", 0)) for r in tabela_editada)
    total_tues_geral = sum(int(r.get("Qtd TUE", 0)) for r in tabela_editada)
    total_tomadas_geral = total_tugs_geral + total_tues_geral
    total_interruptores = sum(int(cfg.get("quantidade", 0)) for cfg in config_interruptores_usuario.values())

    materiais_df = pd.DataFrame([
        {"Material": "Caixa Octogonal de teto 4x4\" (Plástico)", "Unidade": "pç", "Quantidade": total_caixas_luz},
        {"Material": "Caixa de Embutir de Parede 4x2\" (Plástico) — Tomadas", "Unidade": "pç", "Quantidade": total_tomadas_geral},
        {"Material": "Caixa de Embutir de Parede 4x2\" (Plástico) — Interruptores", "Unidade": "pç", "Quantidade": total_interruptores},
        {"Material": "Eletroduto Corrugado Flexível Reforçado 3/4\"", "Unidade": "m", "Quantidade": 247},
        {"Material": "Cabo Flex. 2,5 mm² - Fase", "Unidade": "m", "Quantidade": 180},
        {"Material": "Cabo Flex. 2,5 mm² - Neutro", "Unidade": "m", "Quantidade": 180},
        {"Material": "Cabo Flex. 4,0 ou 6,0 mm² - Verde (Terra TUEs)", "Unidade": "m", "Quantidade": 84}
    ])
    st.dataframe(materiais_df, use_container_width=True, hide_index=True)

    # ========================================================
    # SALVAR / EXPORTAR / CAD
    # ========================================================
    st.divider()
    st.subheader("🖨️ Exportação e Relatórios")

    if st.button("💾 Salvar Alterações do Projeto", use_container_width=True):
        try:
            salvar_dados_projeto(
                st.session_state.user_email,
                st.session_state.projeto_ativo,
                tabela_editada=tabela_editada,
                local_qdc=local_qdc,
                config_interruptores=config_interruptores_usuario
            )
            st.success("✅ Alterações salvas no Supabase com sucesso!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Erro ao salvar alterações: {e}")

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        if st.button("📊 Baixar Planilha (Excel)", use_container_width=True):
            st.info("Exportação para Excel pronta.")
    with col_e2:
        if st.button("📄 Baixar Memorial (PDF)", use_container_width=True):
            st.info("Memorial descritivo pronto.")

    st.markdown("### Projeto Unifilar (DXF)")
    if st.button("🚀 Gerar CAD (Atualizado)", type="primary", use_container_width=True):
        if not dxf_bytes:
            st.error("❌ Nenhum arquivo DXF associado.")
        else:
            try:
                # Salva as configurações atuais antes de gerar o CAD.
                salvar_dados_projeto(
                    st.session_state.user_email,
                    st.session_state.projeto_ativo,
                    tabela_editada=tabela_editada,
                    local_qdc=local_qdc,
                    config_interruptores=config_interruptores_usuario
                )

                cad_bytes_out = motores.gerar_cad_unifilar(
                    dxf_bytes=dxf_bytes,
                    dados_editados=tabela_editada,
                    local_qdc=local_qdc,
                    config_interruptores=config_interruptores_usuario
                )

                st.success("✅ Projeto CAD gerado com sucesso!")
                st.download_button(
                    label="📥 Baixar Projeto DXF Atualizado",
                    data=cad_bytes_out,
                    file_name="Projeto_Eletrico.dxf",
                    mime="application/dxf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"❌ Erro ao gerar o arquivo CAD: {e}")
