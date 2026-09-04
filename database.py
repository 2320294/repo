from config import obter_supabase


def _db():
    return obter_supabase()


# ============================================================
# USUÁRIOS
# ============================================================

def buscar_usuario(email, senha):
    resposta = (
        _db()
        .table("usuarios")
        .select("id,nome,email,senha")
        .eq("email", email.strip())
        .eq("senha", senha)
        .limit(1)
        .execute()
    )

    return (
        resposta.data[0]
        if resposta.data
        else None
    )


def cadastrar_usuario(nome, email, senha):
    email = email.strip()

    existente = (
        _db()
        .table("usuarios")
        .select("id")
        .eq("email", email)
        .limit(1)
        .execute()
    )

    if existente.data:
        return False, "E-mail já cadastrado."

    (
        _db()
        .table("usuarios")
        .insert({
            "nome": nome.strip(),
            "email": email,
            "senha": senha
        })
        .execute()
    )

    return True, "Conta criada! Faça login."


# ============================================================
# PROJETOS
# ============================================================

def listar_projetos(email):
    resposta = (
        _db()
        .table("projetos")
        .select(
            "id,user_email,nome_projeto,created_at"
        )
        .eq("user_email", email)
        .order("nome_projeto")
        .execute()
    )

    return resposta.data or []


def buscar_projeto(email, nome_projeto):
    projeto = (
        _db()
        .table("projetos")
        .select(
            "id,user_email,nome_projeto,created_at"
        )
        .eq("user_email", email)
        .eq("nome_projeto", nome_projeto)
        .limit(1)
        .execute()
    )

    if not projeto.data:
        return None, None

    projeto = projeto.data[0]

    dados = (
        _db()
        .table("dados_projetos")
        .select(
            "id,user_email,nome_projeto,dxf_bytes,"
            "tabela_editada,local_qdc,config_interruptores,"
            "tensao_projeto,pe_direito,created_at"
        )
        .eq("user_email", email)
        .eq("nome_projeto", nome_projeto)
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    dados = (
        dados.data[0]
        if dados.data
        else None
    )

    return projeto, dados


def criar_projeto(email, nome_projeto):
    nome_projeto = nome_projeto.strip()

    existentes = listar_projetos(email)

    if any(
        p.get("nome_projeto") == nome_projeto
        for p in existentes
    ):
        return False, "Já existe um projeto com esse nome."

    (
        _db()
        .table("projetos")
        .insert({
            "user_email": email,
            "nome_projeto": nome_projeto
        })
        .execute()
    )

    (
        _db()
        .table("dados_projetos")
        .insert({
            "user_email": email,
            "nome_projeto": nome_projeto,
            "dxf_bytes": None,
            "tabela_editada": [],
            "local_qdc": None,
            "config_interruptores": {},
            "tensao_projeto": 110,
            "pe_direito": 2.80
        })
        .execute()
    )

    return True, "Projeto cadastrado e selecionado!"


def apagar_projeto(email, nome_projeto):
    (
        _db()
        .table("dados_projetos")
        .delete()
        .eq("user_email", email)
        .eq("nome_projeto", nome_projeto)
        .execute()
    )

    (
        _db()
        .table("projetos")
        .delete()
        .eq("user_email", email)
        .eq("nome_projeto", nome_projeto)
        .execute()
    )


def salvar_dados_projeto(
    email,
    nome_projeto,
    dxf_bytes=None,
    tabela_editada=None,
    local_qdc=None,
    config_interruptores=None,
    tensao_projeto=None,
    pe_direito=None
):
    existentes = (
        _db()
        .table("dados_projetos")
        .select("id")
        .eq("user_email", email)
        .eq("nome_projeto", nome_projeto)
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    registro = {}

    if dxf_bytes is not None:
        registro["dxf_bytes"] = (
            "\\x" + bytes(dxf_bytes).hex()
        )

    if tabela_editada is not None:
        registro["tabela_editada"] = tabela_editada

    if local_qdc is not None:
        registro["local_qdc"] = local_qdc

    if config_interruptores is not None:
        registro["config_interruptores"] = (
            config_interruptores
        )

    # Fase 13.6 Rev.13:
    # "tensao_projeto" é uma coluna legada do banco, com CHECK histórico
    # limitado aos valores antigos (110/220). A partir da Fase 13.6 Rev.13,
    # a fonte de verdade é parametros_rede["tensao_fornecimento"],
    # persistida dentro de config_interruptores.
    #
    # Portanto NÃO atualizamos mais esta coluna durante o salvamento.
    # Isso evita violação do CHECK ao trabalhar corretamente com
    # fornecimentos 127/220 V ou 220/380 V.

    if pe_direito is not None:
        registro["pe_direito"] = float(
            pe_direito
        )

    if existentes.data:
        (
            _db()
            .table("dados_projetos")
            .update(registro)
            .eq("id", existentes.data[0]["id"])
            .execute()
        )

    else:
        registro.update({
            "user_email": email,
            "nome_projeto": nome_projeto
        })

        (
            _db()
            .table("dados_projetos")
            .insert(registro)
            .execute()
        )


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
                return bytes.fromhex(
                    texto[2:]
                )
            except Exception:
                return None

        try:
            return bytes.fromhex(texto)
        except Exception:
            return None

    return None
