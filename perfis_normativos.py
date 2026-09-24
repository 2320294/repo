from config import obter_supabase, obter_supabase_admin

STATUS_PUBLICADOS = {"ATIVO"}


def perfil_atende_municipio(perfil, uf, municipio):
    """Respeita a lista explícita; mantém os perfis antigos de cidade/UF."""
    uf_perfil = str(perfil.get("uf") or "").strip().upper()
    if uf_perfil and uf_perfil != str(uf or "").strip().upper():
        return False
    cidade = str(municipio or "").strip().casefold()
    cidades = perfil.get("municipios_atendidos")
    if cidades is not None:
        return bool(cidade and cidade in {
            str(nome).strip().casefold() for nome in cidades if str(nome).strip()
        })
    cidade_antiga = str(perfil.get("municipio") or "").strip().casefold()
    return not cidade_antiga or cidade_antiga == cidade


def _db():
    return obter_supabase()


def listar_perfis(ativos_apenas=False, administrativo=False):
    db = obter_supabase_admin() if administrativo else _db()
    q = db.table("perfis_normativos").select("*")
    if ativos_apenas:
        q = q.eq("status", "ATIVO")
    r = q.order("concessionaria").order("uf").order("municipio").execute()
    return r.data or []


def listar_perfis_liberados(uf="", municipio=""):
    """Lista somente perfis ATIVOS aplicáveis à localidade do projeto.

    Rev.203 — a leitura dos perfis publicados é feita no servidor com o cliente
    administrativo. O cliente público pode estar sujeito ao RLS e retornar uma
    lista vazia mesmo quando o perfil foi corretamente marcado como ATIVO.

    Abrangência:
    - perfil com município igual ao projeto: específico da cidade;
    - perfil com município vazio: válido para toda a UF.
    Perfis específicos são apresentados antes dos estaduais.
    """
    q = obter_supabase_admin().table("perfis_normativos").select("*").eq("status", "ATIVO")
    uf_norm = str(uf or "").upper().strip()
    if uf_norm:
        q = q.eq("uf", uf_norm)
    r = q.order("concessionaria").order("revisao", desc=True).execute()
    itens = r.data or []

    mun = str(municipio or "").strip().casefold()
    if mun:
        itens = [p for p in itens if perfil_atende_municipio(p, uf_norm, mun)]
        itens.sort(
            key=lambda p: (
                0 if str(p.get("municipio") or "").strip().casefold() == mun else 1,
                str(p.get("concessionaria") or "").casefold(),
            )
        )
    return itens


def salvar_perfil(dados, perfil_id=None):
    payload = dict(dados)
    db = obter_supabase_admin()
    if perfil_id:
        return db.table("perfis_normativos").update(payload).eq("id", perfil_id).execute().data
    return db.table("perfis_normativos").insert(payload).execute().data


def atualizar_status(perfil_id, status, validado_por=""):
    db = obter_supabase_admin()
    payload = {"status": status}
    if status in ("VALIDADO", "ATIVO"):
        payload["validado_por"] = validado_por
    return db.table("perfis_normativos").update(payload).eq("id", perfil_id).execute().data


def perfil_por_id(perfil_id):
    """Carrega um perfil pelo ID para uso interno do motor normativo.

    Rev.204 — leitura server-side para evitar que RLS do cliente público faça o
    perfil ATIVO selecionado desaparecer no momento do cálculo. A função apenas
    lê o registro; alterações continuam restritas às rotinas administrativas.
    """
    if not perfil_id:
        return None
    r = (
        obter_supabase_admin()
        .table("perfis_normativos")
        .select("*")
        .eq("id", perfil_id)
        .limit(1)
        .execute()
    )
    return r.data[0] if r.data else None
