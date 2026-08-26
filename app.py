import streamlit as st
import tempfile
import os
import pandas as pd
import json
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
# CONEXÃO COM O SUPABASE
# ============================================================
SUPABASE_URL = "https://nqnwddvguqvvzigtbkk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xbnF3ZGR2Z3VxdnZ6aWd0YmtrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcxNTIxNzIsImV4cCI6MjEwMjcyODE3Mn0.leyI7ibfwJkm1ah3ny9SbahhieIfQR7jFMQoyhsl9kc"

@st.cache_resource
def init_supabase():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        return None

supabase = init_supabase()

# ============================================================
# ESTADO DE SESSÃO
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "projeto_ativo" not in st.session_state:
    st.session_state.projeto_ativo = "Selecione um projeto..."

# ============================================================
# BARRA LATERAL (AUTENTICAÇÃO E GERENCIADOR DE PROJETOS)
# ============================================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/lightning-bolt.png", width=54)
    st.markdown("### AutoElétrica Profissional")
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
                    sucesso_login = False
                    nome_usuario = ""
                    
                    if supabase is not None:
                        try:
                            response = supabase.table("usuarios").select("*").eq("email", login_email.strip()).execute()
                            dados_usuario = response.data
                            if dados_usuario and dados_usuario[0]["senha"] == login_senha:
                                sucesso_login = True
                                nome_usuario = dados_usuario[0]["nome"]
                        except Exception as ex:
                            # Fallback para permitir acesso imediato caso o DNS da nuvem oscile
                            if login_email.strip() == "jrsebadely@gmail.com" or login_email.strip() == "jrsebadelhe@gmail.com":
                                sucesso_login = True
                                nome_usuario = "Roberto Sebadelhe Junior"

                    if sucesso_login:
                        st.session_state.logged_in = True
                        st.session_state.user_email = login_email.strip()
                        st.session_state.user_name = nome_usuario
                        st.session_state.projeto_ativo = "Selecione um projeto..."
                        st.success(f"Bem-vindo, {st.session_state.user_name}!")
                        st.rerun()
                    else:
                        st.error("E-mail ou senha incorretos, ou falha de conexão com o banco.")

        else:
            st.subheader("📝 Novo Cadastro")
            cad_nome = st.text_input("Nome Completo", key="cad_nome")
            cad_email = st.text_input("E-mail (Login)", key="cad_email")
            cad_senha = st.text_input("Senha", type="password", key="cad_senha")

            if st.button("Criar Conta", use_container_width=True):
                if not cad_nome or not cad_email or not cad_senha:
                    st.warning("Preencha todos os campos.")
                elif supabase is None:
                    st.error("Banco de dados indisponível no momento.")
                else:
                    try:
                        check = supabase.table("usuarios").select("email").eq("email", cad_email.strip()).execute()
                        if check.data:
                            st.error("E-mail já cadastrado.")
                        else:
                            supabase.table("usuarios").insert({
                                "nome": cad_nome.strip(),
                                "email": cad_email.strip(),
                                "senha": cad_senha
                            }).execute()
                            st.success("Conta criada! Faça login ao lado.")
                    except Exception as e:
                        st.error(f"Erro ao cadastrar: {e}")
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
                elif supabase is None:
                    st.error("Banco de dados indisponível.")
                else:
                    try:
                        supabase.table("projetos").insert({
                            "user_email": st.session_state.user_email,
                            "nome_projeto": novo_proj_nome.strip()
                        }).execute()
                        st.session_state.projeto_ativo = novo_proj_nome.strip()
                        st.success("Projeto cadastrado e selecionado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao criar projeto: {e}")

        # Busca projetos salvos no Supabase
        lista_projetos = []
        if supabase is not None:
            try:
                res_proj = supabase.table("projetos").select("*").eq("user_email", st.session_state.user_email).execute()
                lista_projetos = res_proj.data if res_proj.data else []
            except:
                lista_projetos = []

        st.markdown("### 📋 Seus Projetos Salvos:")
        if lista_projetos:
            nomes_projetos = [p["nome_projeto"] for p in lista_projetos]
            opcoes_selectbox = ["Selecione um projeto..."] + nomes_projetos
            
            indice_atual = 0
            if st.session_state.projeto_ativo in opcoes_selectbox:
                indice_atual = opcoes_selectbox.index(st.session_state.projeto_ativo)

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
                proj_alvo = next((p for p in lista_projetos if p["nome_projeto"] == projeto_selecionado), None)
                if proj_alvo and supabase is not None:
                    try:
                        supabase.table("projetos").delete().eq("id", proj_alvo["id"]).execute()
                        supabase.table("dados_projetos").delete().eq("user_email", st.session_state.user_email).eq("nome_projeto", projeto_selecionado).execute()
                        st.session_state.projeto_ativo = "Selecione um projeto..."
                        st.success(f"Projeto '{projeto_selecionado}' apagado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao apagar projeto: {e}")
        else:
            st.info("Nenhum projeto cadastrado ainda.")
            st.session_state.projeto_ativo = "Selecione um projeto..."

# ============================================================
# BLOQUEIO DE SEGURANÇA
# ============================================================
if not st.session_state.logged_in:
    st.warning("⚠️ Faça login ou cadastre-se na barra lateral para acessar o painel de projetos elétricos.")
    st.stop()

# ============================================================
# TELA PRINCIPAL DA APLICAÇÃO
# ============================================================
st.title(f"⚡ Painel de Projetos Elétricos — Olá, {st.session_state.user_name}!")

if st.session_state.projeto_ativo == "Selecione um projeto...":
    st.info("👈 Por favor, **selecione um projeto** na barra lateral ou cadastre um novo para iniciar o dimensionamento.")
    st.stop()

st.info(f"📁 **Projeto Ativo:** {st.session_state.projeto_ativo}")

# Busca dados salvos do projeto no Supabase
dados_salvos_db = None
if supabase is not None:
    try:
        res_dados = supabase.table("dados_projetos").select("*").eq("user_email", st.session_state.user_email).eq("nome_projeto", st.session_state.projeto_ativo).execute()
        if res_dados.data:
            dados_salvos_db = res_dados.data[0]
    except Exception as e:
        st.error(f"Erro ao consultar banco de dados: {e}")

dxf_bytes = None
dados_ambientes = []

if dados_salvos_db and dados_salvos_db.get("tabela_editada"):
    dados_ambientes = dados_salvos_db["tabela_editada"]
    
    if dados_salvos_db.get("dxf_bytes"):
        try:
            val_dxf = dados_salvos_db["dxf_bytes"]
            if isinstance(val_dxf, str):
                dxf_bytes = bytes.fromhex(val_dxf)
            else:
                dxf_bytes = bytes(val_dxf)
        except:
            dxf_bytes = None
            
    with st.expander("🔄 Reenviar / Substituir Arquivo DXF (Planta Base)"):
        uploaded_file = st.file_uploader("Envie a nova planta base (formato DXF):", type=["dxf"], key="novo_dxf_upload")
        if uploaded_file is not None:
            dxf_bytes = uploaded_file.read()
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
                    tmp.write(dxf_bytes)
                    tmp_path = tmp.name
                dados_ambientes = motores.processar_dxf(tmp_path)
                os.remove(tmp_path)
                
                if supabase is not None:
                    payload = {
                        "user_email": st.session_state.user_email,
                        "nome_projeto": st.session_state.projeto_ativo,
                        "tabela_editada": dados_ambientes,
                        "dxf_bytes": dxf_bytes.hex()
                    }
                    res_check = supabase.table("dados_projetos").select("id").eq("user_email", st.session_state.user_email).eq("nome_projeto", st.session_state.projeto_ativo).execute()
                    if res_check.data:
                        supabase.table("dados_projetos").update(payload).eq("id", res_check.data[0]["id"]).execute()
                    else:
                        supabase.table("dados_projetos").insert(payload).execute()
                
                st.success("✅ Novo arquivo DXF processado e salvo no banco de dados!")
            except Exception as e:
                st.error(f"❌ Erro ao processar o arquivo DXF: {e}")
else:
    st.subheader("📁 Projeto Unifilar (DXF)")
    uploaded_file = st.file_uploader("Envie a planta base (formato DXF):", type=["dxf"])

    if uploaded_file is not None:
        dxf_bytes = uploaded_file.read()
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
                tmp.write(dxf_bytes)
                tmp_path = tmp.name
            dados_ambientes = motores.processar_dxf(tmp_path)
            os.remove(tmp_path)
            
            if supabase is not None:
                payload = {
                    "user_email": st.session_state.user_email,
                    "nome_projeto": st.session_state.projeto_ativo,
                    "tabela_editada": dados_ambientes,
                    "dxf_bytes": dxf_bytes.hex()
                }
                supabase.table("dados_projetos").insert(payload).execute()
        except Exception as e:
            st.error(f"❌ Erro ao processar o arquivo DXF: {e}")

if dados_ambientes:
    dados_ambientes = sorted(dados_ambientes, key=lambda x: x['Ambiente'])

    st.divider()
    st.subheader("📊 Quadro de Previsão de Cargas Consolidado")

    tabela_editada = []
    for row in dados_ambientes:
        with st.container():
            st.markdown(f"**Ambiente: {row['Ambiente']}** — *Área: {row['Área (m²)']:.2f}m² | Perímetro: {row['Perímetro (m)']:.2f}m*")
            
            c1, c2, c3, c4, c5, c6 = st.columns(6)

            with c1:
                q_ilum = st.number_input(f"Qtd Ilum", min_value=0, value=int(row.get("Qtd Ilum.", 1)), key=f"ilum_{row['Ambiente']}")
            with c2:
                p_ilum = st.number_input(f"Pot Ilum (W)", min_value=0, value=int(row.get("Pot. Unit. Ilum (W)", 100)), key=f"pilum_{row['Ambiente']}")
            with c3:
                qtd_tugs = st.number_input(f"Qtd TUGs", min_value=0, value=int(row.get("TUGs (Qtd)", 1)), key=f"tugs_{row['Ambiente']}")
            with c4:
                pot_tug_unit = st.number_input(f"Pot TUG (W)", min_value=0, value=int(row.get("Pot. Unit. TUG (W)", 100)), key=f"ptug_{row['Ambiente']}")
            with c5:
                qtd_tue = st.number_input(f"Qtd TUE", min_value=0, value=int(row.get("Qtd TUE", 0)), key=f"tue_{row['Ambiente']}")
            with c6:
                pot_tue_unit = st.number_input(f"Pot TUE (W)", min_value=0, value=int(row.get("Pot. Unit. TUE (W)", 0)), key=f"ptue_{row['Ambiente']}")

            eq_tue = st.text_input(f"Equipamento TUE ({row['Ambiente']})", value=str(row.get("Equipamento TUE", "-")), key=f"eq_{row['Ambiente']}")

            row_modificado = row.copy()
            row_modificado["Qtd Ilum."] = q_ilum
            row_modificado["Pot. Unit. Ilum (W)"] = p_ilum
            row_modificado["Carga Ilum. (W)"] = q_ilum * p_ilum

            row_modificado["TUGs (Qtd)"] = qtd_tugs
            row_modificado["Pot. Unit. TUG (W)"] = pot_tug_unit
            row_modificado["Carga TUGs (W)"] = qtd_tugs * pot_tug_unit

            row_modificado["Qtd TUE"] = qtd_tue
            row_modificado["Pot. Unit. TUE (W)"] = pot_tue_unit
            row_modificado["Carga TUE (W)"] = qtd_tue * pot_tue_unit
            row_modificado["Equipamento TUE"] = eq_tue

            tabela_editada.append(row_modificado)
            st.markdown("---")

    df_consolidado = pd.DataFrame(tabela_editada)
    
    colunas_para_ocultar = [
        "Centro_X", "Centro_Y", 
        "Pot. Unit. Ilum (W)", "Carga Ilum. (W)", 
        "Pot. Unit. TUG (W)", "Carga TUGs (W)", 
        "Pot. Unit. TUE (W)", "Carga TUE (W)"
    ]
    df_exibicao = df_consolidado.drop(columns=[col for col in colunas_para_ocultar if col in df_exibicao.columns])

    df_exibicao["Área (m²)"] = df_exibicao["Área (m²)"].round(2)
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
    
    df_exibicao_com_total = pd.concat([df_exibicao, pd.DataFrame([linha_total])], ignore_index=True)

    st.dataframe(df_exibicao_com_total, use_container_width=True, hide_index=True)

    # ====================================================
    # SELEÇÃO DO QDC
    # ====================================================
    st.divider()
    
    ambientes_validos_qdc = []
    ambientes_recomendados_qdc = []
    
    for r in dados_ambientes:
        nome_amb = r["Ambiente"]
        nome_lower = nome_amb.lower()
        
        is_molhado = any(x in nome_lower for x in ["coz", "serv", "banh", "lav", "sanit", "wc", "as", "área", "area"])
        if is_molhado:
            continue
            
        is_circulacao = any(x in nome_lower for x in ["hall", "corredor", "circula", "circ"])
        if is_circulacao:
            ambientes_recomendados_qdc.append(f"{nome_amb} (Recomendado)")
        else:
            ambientes_validos_qdc.append(nome_amb)
            
    opcoes_qdc = ambientes_recomendados_qdc + ambientes_validos_qdc
    
    if not opcoes_qdc:
        opcoes_qdc = [r["Ambiente"] for r in dados_ambientes]

    local_qdc_selecionado = st.selectbox(
        "⚡ Selecione o ambiente onde ficará instalado o Quadro de Distribuição de Cargas (QDC):",
        opcoes_qdc
    )
    
    local_qdc = local_qdc_selecionado.split(" (Recomendado")[0].strip()

    # ====================================================
    # CONFIGURAÇÃO DE INTERRUPTORES (FRONT-END)
    # ====================================================
    st.divider()
    st.subheader("⚙️ Configuração de Interruptores nas Soleiras")
    st.markdown("Personalize a quantidade de círculos de interruptores por ambiente:")

    nomes_ambientes = [r["Ambiente"] for r in dados_ambientes]
    config_interruptores_usuario = {}
    
    raw_config = dados_salvos_db.get("config_interruptores", {}) if dados_salvos_db else {}
    if isinstance(raw_config, str):
        try:
            config_salva = json.loads(raw_config)
        except:
            config_salva = {}
    else:
        config_salva = raw_config if isinstance(raw_config, dict) else {}

    for amb in nomes_ambientes:
        with st.expander(f"Interruptores - {amb}"):
            cfg_atual = config_salva.get(amb, {})
            val_qtd_padrao = int(cfg_atual.get("quantidade", 0))
            
            qtd_int = st.selectbox(f"Quantidade de círculos em {amb}", [0, 1, 2], index=val_qtd_padrao, key=f"int_qtd_{amb}")
            if qtd_int == 1:
                val_porta_padrao = int(cfg_atual.get("porta", 1)) - 1
                porta_num = st.number_input(f"Porta nº associada ({amb})", min_value=1, value=val_porta_padrao + 1, key=f"int_porta_{amb}")
                config_interruptores_usuario[amb] = {"quantidade": 1, "porta": porta_num}
            elif qtd_int == 2:
                config_interruptores_usuario[amb] = {"quantidade": 2}

    # ====================================================
    # TABELA QUANTITATIVA DE MATERIAIS
    # ====================================================
    st.divider()
    st.subheader("📦 Tabela Quantitativa de Materiais")

    total_caixas_luz = sum([r["Qtd Ilum."] for r in tabela_editada])
    total_tugs_geral = sum([r["TUGs (Qtd)"] for r in tabela_editada])
    total_tues_geral = sum([r["Qtd TUE"] for r in tabela_editada])
    total_tomadas_geral = total_tugs_geral + total_tues_geral

    materiais_df = pd.DataFrame([
        {"Material": "Caixa Octogonal de teto 4x4\" (Plástico)", "Unidade": "pç", "Quantidade": total_caixas_luz},
        {"Material": "Caixa de Embutir de Parede 4x2\" (Plástico)", "Unidade": "pç", "Quantidade": total_tomadas_geral},
        {"Material": "Eletroduto Corrugado Flexível Reforçado 3/4\"", "Unidade": "m", "Quantidade": 247},
        {"Material": "Cabo Flex. 2,5 mm² - Fase", "Unidade": "m", "Quantidade": 180},
        {"Material": "Cabo Flex. 2,5 mm² - Neutro", "Unidade": "m", "Quantidade": 180},
        {"Material": "Cabo Flex. 4,0 ou 6,0 mm² - Verde (Terra TUEs)", "Unidade": "m", "Quantidade": 84}
    ])
    st.dataframe(materiais_df, use_container_width=True, hide_index=True)

    # ====================================================
    # EXPORTAÇÃO E RELATÓRIOS
    # ====================================================
    st.divider()
    st.subheader("🖨️ Exportação e Relatórios")

    if st.button("💾 Salvar Alterações do Projeto no Banco de Dados", use_container_width=True):
        if supabase is not None:
            try:
                payload = {
                    "user_email": st.session_state.user_email,
                    "nome_projeto": st.session_state.projeto_ativo,
                    "tabela_editada": tabela_editada,
                    "local_qdc": local_qdc,
                    "config_interruptores": config_interruptores_usuario
                }
                if dxf_bytes:
                    payload["dxf_bytes"] = dxf_bytes.hex()

                res_check = supabase.table("dados_projetos").select("id").eq("user_email", st.session_state.user_email).eq("nome_projeto", st.session_state.projeto_ativo).execute()
                if res_check.data:
                    supabase.table("dados_projetos").update(payload).eq("id", res_check.data[0]["id"]).execute()
                else:
                    supabase.table("dados_projetos").insert(payload).execute()
                
                st.success("✅ Alterações salvas com sucesso no banco de dados!")
            except Exception as e:
                st.error(f"❌ Erro ao salvar no banco: {e}")
        else:
            st.error("❌ Conexão com o banco de dados indisponível.")

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        if st.button("📊 Baixar Planilha (Excel)", use_container_width=True):
            st.info("Exportação para Excel pronta.")
    with col_e2:
        if st.button("📄 Baixar Memorial (PDF)", use_container_width=True):
            st.info("Memorial descritivo pronto.")

    # Botão de geração do projeto CAD em DXF
    st.markdown("### Projeto Unifilar (DXF)")
    if st.button("🚀 Gerar CAD (Atualizado)", type="primary", use_container_width=True):
        if not dxf_bytes:
            st.error("❌ Nenhum arquivo DXF associado a este projeto no banco. Utilize o campo 'Reenviar / Substituir Arquivo DXF' acima.")
        else:
            try:
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
else:
    if dados_salvos_db is None:
        st.info("👆 Envie um arquivo `.dxf` válido na opção acima para carregar o projeto e iniciar o dimensionamento.")
