
TERMOS_AREAS_MOLHADAS = (
    "BANHEIRO", "BANH", "WC", "W.C", "BWC", "SANIT",
    "COZINHA", "COPA", "LAVAND", "SERVICO", "SERVIÇO",
    "A.S", "AREA DE SERVICO", "ÁREA DE SERVIÇO",
    "GARAGEM", "VARANDA", "TERRACO", "TERRAÇO"
)

def _normalizar(texto):
    return str(texto or "").upper().strip()

def _area_molhada_ou_externa(ambiente):
    nome=_normalizar(ambiente)
    return any(t in nome for t in TERMOS_AREAS_MOLHADAS)

def agrupar_circuitos_dr(circuitos):
    """
    Fase 9.4:
    cria agrupamentos funcionais de DR para o quadro, evitando um único DR
    geral. A topologia é deliberadamente conservadora e transparente:
      DR1 - TUG de áreas molhadas/externas;
      DR2 - TUE de áreas molhadas/externas;
      DR3 - demais TUG/TUE;
    iluminação permanece fora desses grupos nesta etapa.
    O dimensionamento nominal/sensibilidade final do DR será validado junto
    à seletividade e às regras específicas do perfil normativo.
    """
    saida=[]
    grupos={}
    for c in circuitos or []:
        c=dict(c)
        tipo=_normalizar(c.get("tipo"))
        amb=c.get("ambiente","")
        grupo=None

        if tipo=="TUG" and _area_molhada_ou_externa(amb):
            grupo="DR1"
        elif tipo=="TUE" and _area_molhada_ou_externa(amb):
            grupo="DR2"
        elif tipo in {"TUG","TUE"}:
            grupo="DR3"

        c["dr"]=grupo or "—"
        saida.append(c)
        if grupo:
            grupos.setdefault(grupo,[]).append(c)

    descricoes={
        "DR1":"TUG - áreas molhadas/externas",
        "DR2":"TUE - áreas molhadas/externas",
        "DR3":"Demais tomadas/TUE",
    }
    resumo=[]
    for gid in ["DR1","DR2","DR3"]:
        itens=grupos.get(gid,[])
        if not itens:
            continue
        resumo.append({
            "dr":gid,
            "descricao":descricoes[gid],
            "circuitos":[int(c.get("numero",0) or 0) for c in itens],
            "potencia_w":sum(float(c.get("potencia",0) or 0) for c in itens),
        })
    return saida,resumo
