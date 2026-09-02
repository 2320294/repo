
TERMOS_AREAS_MOLHADAS = (
    "BANHEIRO","BANH","WC","W.C","BWC","SANIT",
    "COZINHA","COPA","LAVAND","SERVICO","SERVIÇO",
    "A.S","AREA DE SERVICO","ÁREA DE SERVIÇO",
    "GARAGEM","VARANDA","TERRACO","TERRAÇO"
)
CALIBRES_DR=(25,40,63,80,100,125)

def _n(t): return str(t or "").upper().strip()
def _molhada(a):
    nome=_n(a)
    return any(t in nome for t in TERMOS_AREAS_MOLHADAS)

def _calibre(minimo):
    for x in CALIBRES_DR:
        if x >= minimo: return x
    return None

def agrupar_circuitos_dr(circuitos, disjuntor_geral_a=None):
    """
    Fase 11.4 Rev.5.
    Agrupa circuitos e pré-dimensiona corrente nominal dos DRs.
    Sensibilidade adotada para proteção adicional dos grupos de tomadas: 30 mA.
    O calibre do DR é escolhido >= maior disjuntor a jusante do grupo.
    Se houver DG conhecido, também verifica coerência hierárquica básica.
    Isto não substitui tabelas/curvas de seletividade de fabricante.
    """
    saida=[]; grupos={}
    for c0 in circuitos or []:
        c=dict(c0); tipo=_n(c.get("tipo")); amb=c.get("ambiente","")
        grupo=None
        if tipo=="TUG" and _molhada(amb): grupo="DR1"
        elif tipo=="TUE" and _molhada(amb): grupo="DR2"
        elif tipo in {"TUG","TUE"}: grupo="DR3"
        c["dr"]=grupo or ""
        saida.append(c)
        if grupo: grupos.setdefault(grupo,[]).append(c)

    descricoes={
        "DR1":"TUG - áreas molhadas/externas",
        "DR2":"TUE - áreas molhadas/externas",
        "DR3":"Demais tomadas/TUE",
    }
    resumo=[]
    for gid in ("DR1","DR2","DR3"):
        itens=grupos.get(gid,[])
        if not itens: continue
        maior_dj=max(int(c.get("disjuntor",0) or 0) for c in itens)
        nominal=_calibre(maior_dj)
        dg=int(disjuntor_geral_a or 0)
        coerente=(nominal is not None and nominal>=maior_dj)
        resumo.append({
            "dr":gid,
            "descricao":descricoes[gid],
            "circuitos":[int(c.get("numero",0) or 0) for c in itens],
            "potencia_w":sum(float(c.get("potencia",0) or 0) for c in itens),
            "maior_dj_a":maior_dj,
            "corrente_nominal_a":nominal,
            "sensibilidade_ma":30,
            "coordenacao_basica":"OK" if coerente else "REVISAR",
            "dg_a":dg or None,
        })
    return saida,resumo
