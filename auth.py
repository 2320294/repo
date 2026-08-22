import streamlit as st

def tela_login(supabase):
    st.title("🔐 Acesso - AutoElétrica")
    st.subheader("Bem-vindo à plataforma de projetos elétricos")
    
    if supabase is None:
        st.error("Erro Crítico: Não foi possível conectar ao banco de dados.")
        st.stop()
        
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_cadastro = st.tabs(["Fazer Login", "Criar Nova Conta"])
        
        with tab_login:
            with st.form("form_login"):
                email = st.text_input("E-mail")
                senha = st.text_input("Senha", type="password")
                submit_login = st.form_submit_button("Entrar no Sistema")
                
                if submit_login:
                    try:
                        response = supabase.auth.sign_in_with_password({"email": email, "password": senha})
                        st.session_state.usuario_autenticado = True
                        st.session_state.user_email = email
                        st.session_state.user_id = response.user.id
                        st.success("Login realizado com sucesso! Carregando plataforma...")
                        st.rerun()
                    except Exception as erro:
                        st.error("Credenciais inválidas. Verifique seu e-mail e senha.")

        with tab_cadastro:
            with st.form("form_cadastro"):
                novo_email = st.text_input("Seu E-mail")
                nova_senha = st.text_input("Crie uma Senha (mín. 6 caracteres)", type="password")
                submit_cadastro = st.form_submit_button("Criar Minha Conta")
                
                if submit_cadastro:
                    if len(nova_senha) < 6:
                        st.warning("A senha deve ter pelo menos 6 caracteres.")
                    else:
                        try:
                            response = supabase.auth.sign_up({"email": novo_email, "password": nova_senha})
                            st.success("✅ Conta criada com sucesso! Verifique sua caixa de entrada.")
                        except Exception as erro:
                            st.error(f"Erro ao criar conta. Detalhes: {erro}")
