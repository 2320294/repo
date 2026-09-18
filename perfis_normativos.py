from config import obter_supabase, obter_supabase_admin

STATUS_PUBLICADOS = {"ATIVO"}


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
    q = _db().table("perfis_normativos").select("*").eq("status", "ATIVO")
    if uf:
        q = q.eq("uf", str(uf).upper().strip())
    r = q.order("concessionaria").order("revisao", desc=True).execute()
    itens = r.data or []
    mun = str(municipio or "").strip().casefold()
    if mun:
        itens = [p for p in itens if not str(p.get("municipio") or "").strip() or str(p.get("municipio") or "").strip().casefold() == mun]
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
    if not perfil_id:
        return None
    r = _db().table("perfis_normativos").select("*").eq("id", perfil_id).limit(1).execute()
    return r.data[0] if r.data else None
