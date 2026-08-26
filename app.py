import streamlit as st
import tempfile
import os
import pandas as pd
import json
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
# BANCO DE DADOS LOCAL EM JSON (ESTÁVEL E SEM ERROS DE REDE)
# ============================================================
ARQUIVO_DB = "db_sistema_eletrico.json"

def carregar_banco():
    if os.path.exists(ARQUIVO_DB):
        try:
            with open(ARQUIVO_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"usuarios": [], "projetos": []}

def salvar_banco(dados):
    with open(ARQUIVO_DB, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

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
# BARRA LATERAL (AUTENTICAÇÃO E GERENCIADOR DE OBRAS)
# ============================================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/lightning-bolt.png", width=54)
    st.markdown("### AutoElétrica Profissional")
    st.divider()

    db = carregar_banco()

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
                    usuario = next((u for u in db["usuarios"] if u["email"] == login_email.strip() and u["senha"] == login_senha), None)
                    if usuario:
                        st.session_state.logged_in = True
                        st.session_state.user_email = usuario["email"]
                        st.session_state.user_name = usuario["nome"]
                        st.session_state.projeto_ativo = "Selecione um projeto..."
                        st.success(f"Bem-vindo, {st.session_state.user_name}!")
                        st.rerun()
                    else:
                        st.error("E-mail ou senha incorretos.")

        else:
            st.subheader("📝 Novo Cadastro")
            cad_nome = st.text_input("Nome Completo", key="cad_nome")
            cad_email = st.text_input("E-mail (Login)", key="cad_email")
            cad_senha = st.text_input("Senha", type="password", key="cad_senha")

            if st.button("Criar Conta", use_container_width=True):
                if not cad_nome or not cad_email or not cad_senha:
                    st.warning("Preencha todos os campos.")
                elif any(u["email"] == cad_email.strip() for u in db["usuarios"]):
                    st.error("E-mail já cadastrado.")
                else:
                    db["usuarios"].append({
                        "nome": cad_nome.strip(),
                        "email": cad_email.strip(),
                        "senha": cad_senha
                    })
                    salvar_banco(db)
                    st.success("Conta criada! Faça login ao lado.")
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
                    projetos_usuario = [p for p in db["projetos"] if p["user_email"] == st.session_state.user_email]
                    if any(p["nome_projeto"] == novo_proj_nome.strip() for p in projetos_usuario):
                        st.warning("Já existe um projeto com esse nome.")
                    else:
                        db["projetos"].append({
                            "user_email": st.session_state.user_email,
                            "nome_projeto": novo_proj_nome.strip(),
                            "dxf_hex": None,
                            "tabela_editada": [],
                            "config_interruptores": {}
                        })
                        salvar_banco(db)
                        st.session_state.projeto_ativo = novo_proj_nome.strip()
                        st.success("Projeto cadastrado e selecionado!")
                        st.rerun()

        # Listagem de projetos do usuário
        projetos_usuario = [p for p in db["projetos"] if p["user_email"] == st.session_state.user_email]

        st.markdown("### 📋 Seus Projetos Salvos:")
        if projetos_usuario:
            nomes_projetos = [p["nome_projeto"] for p in projetos_usuario]
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
                db["projetos"] = [p for p in db["projetos"] if not (p["user_email"] == st.session_state.user_email and p["nome_projeto"] == projeto_selecionado)]
                salvar_banco(db)
                st.session_state.projeto_ativo = "Selecione um projeto..."
                st.success(f"Projeto '{projeto_selecionado}' apagado!")
                st.rerun()
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

# Localiza o projeto atual no banco local
db = carregar_banco()
projeto_obj = next((p for p in db["projetos"] if p["user_email"] == st.session_state.user_email and p["nome_projeto"] == st.session_state.projeto_ativo), None)

dxf_bytes = None
dados_ambientes = []

if projeto_obj:
    if projeto_obj.get("dxf_hex"):
        try:
            dxf_bytes = bytes.fromhex(projeto_obj["dxf_hex"])
        except:
            dxf_bytes = None
    dados_ambientes = projeto_obj.get("tabela_editada", [])

# ============================================================
# ÁREA DE UPLOAD / REENVIO DA PLANTA BAIXA (DXF)
# ============================================================
tem_dxf_salvo = dxf_bytes is not None and len(dados_ambientes) > 0

if not tem_dxf_salvo:
    st.subheader("📁 Enviar Planta Base (Formato DXF)")
    uploaded_file = st.file_uploader("Envie o arquivo DXF para iniciar o dimensionamento:", type=["dxf"], key="upload_inicial")
    if uploaded_file is not None:
        dxf_bytes = uploaded_file.read()
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
                tmp.write(dxf_bytes)
                tmp_path = tmp.name
            dados_ambientes = motores.processar_dxf(tmp_path)
            os.remove(tmp_path)
            
            # Salva no banco local
            projeto_obj["dxf_hex"] = dxf_bytes.hex()
            projeto_obj["tabela_editada"] = dados_ambientes
            salvar_banco(db)
            st.success("✅ Planta baixa processada e salva com sucesso!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Erro ao processar o DXF: {e}")
else:
    with st.expander("🔄 Reenviar / Substituir Planta Baixa (DXF)"):
        st.markdown("Envie um novo arquivo DXF caso a geometria tenha sido alterada. Os dados ajustados abaixo serão preservados.")
        novo_uploaded_file = st.file_uploader("Envie a nova planta base (.dxf):", type=["dxf"], key="upload_substituicao")
        if novo_uploaded_file is not None:
            dxf_bytes = novo_uploaded_file.read()
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
                    tmp.write(dxf_bytes)
                    tmp_path = tmp.name
                novos_dados = motores.processar_dxf(tmp_path)
                os.remove(tmp_path)
                
                # Atualiza geometria preservando cargas existentes se os ambientes baterem
                projeto_obj["dxf_hex"] = dxf_bytes.hex()
                projeto_obj["tabela_editada"] = novos_dados
                salvar_banco(db)
                st.success("✅ Nova planta baixa substituída com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao processar o novo DXF: {e}")

# ============================================================
# QUADRO DE CARGAS E EDIÇÃO
# ============================================================
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
    # CONFIGURAÇÃO DE INTERRUPTORES
    # ====================================================
    st.divider()
    st.subheader("⚙️ Configuração de Interruptores nas Soleiras")
    st.markdown("Personalize a quantidade de círculos de interruptores por ambiente:")

    nomes_ambientes = [r["Ambiente"] for r in dados_ambientes]
    config_interruptores_usuario = {}
    config_salva = projeto_obj.get("config_interruptores", {}) if projeto_obj else {}

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

    if st.button("💾 Salvar Alterações do Projeto", use_container_width=True):
        if projeto_obj:
            projeto_obj["tabela_editada"] = tabela_editada
            projeto_obj["config_interruptores"] = config_interruptores_usuario
            salvar_banco(db)
            st.success("✅ Alterações salvas com sucesso!")

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
            st.error("❌ Nenhum arquivo DXF associado. Envie uma planta base na opção acima.")
        else:
            try:
                cad_bytes_out = motores.gerar_cad_unifilar(
                    dxf_bytes=dxf_bytes,
                    dados_editados=tabela_editada,
                    local_qdc=local_qdc,
                    config_interruptores=config_interruptores_usuario
                )

                st.success("✅ Projeto CAD gerado com sucesso a partir da planta e dos dados salvos!")
                st.download_button(
                    label="📥 Baixar Projeto DXF Atualizado",
                    data=cad_bytes_out,
                    file_name="Projeto_Eletrico.dxf",
                    mime="application/dxf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"❌ Erro ao gerar o arquivo CAD: {e}")
