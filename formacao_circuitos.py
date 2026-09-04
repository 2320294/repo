import math


LIMITES_W = {
    "Iluminação": 1200.0,
    "TUG_SECO": 1800.0,
}

PALAVRAS_SERVICO = (
    "COZIN", "COPA", "LAVAND", "SERVI", "A.S", "AREA DE SERV",
    "ÁREA DE SERV", "DESPENSA"
)


def _norm(txt):
    return str(txt or "").strip().upper()


def _eh_servico(ambiente):
    nome = _norm(ambiente)
    return any(p in nome for p in PALAVRAS_SERVICO)


def _fechar_grupo(grupo, saida):
    if not grupo:
        return
    base = dict(grupo[0])
    ambientes = []
    potencia = 0.0
    for item in grupo:
        amb = str(item.get("ambiente", "") or "").strip()
        if amb and amb not in ambientes:
            ambientes.append(amb)
        potencia += float(item.get("potencia", 0) or 0)

    base["ambientes"] = ambientes
    base["ambiente"] = " + ".join(ambientes)
    base["potencia"] = potencia
    tensao = float(base.get("tensao", 0) or 0)
    base["corrente"] = potencia / tensao if tensao else 0.0
    base["origens"] = [
        {
            "ambiente": i.get("ambiente", ""),
            "potencia": float(i.get("potencia", 0) or 0),
        }
        for i in grupo
    ]
    saida.append(base)


def formar_circuitos_definitivos(circuitos_elementares, disjuntor_por_corrente):
    """
    Consolida as cargas elementares por ambiente em circuitos físicos.

    Regras da Fase 13.0:
    - TUE permanece dedicada, uma carga por circuito.
    - TUG de cozinha/serviço/lavanderia e análogos permanece exclusiva
      daquele ambiente; não é misturada com TUG de outros ambientes.
    - TUG dos demais ambientes pode compartilhar circuito, limitado
      preliminarmente a 1800 W.
    - Iluminação pode compartilhar circuito, limitada preliminarmente
      a 1200 W.
    - Não mistura tipos nem tensões diferentes.
    - O disjuntor é recalculado pela potência consolidada.
    """
    elementares = [dict(c) for c in (circuitos_elementares or [])]
    saida = []

    # TUEs: dedicadas.
    for c in elementares:
        if c.get("tipo") == "TUE":
            c["ambientes"] = [c.get("ambiente", "")]
            c["origens"] = [{
                "ambiente": c.get("ambiente", ""),
                "potencia": float(c.get("potencia", 0) or 0),
            }]
            c["criterio_formacao"] = "Circuito dedicado TUE"
            saida.append(c)

    # Iluminação: agrupar por tensão e limite.
    iluminacao = [c for c in elementares if c.get("tipo") == "Iluminação"]
    for tensao in sorted({float(c.get("tensao", 0) or 0) for c in iluminacao}):
        itens = [c for c in iluminacao if float(c.get("tensao", 0) or 0) == tensao]
        grupo = []
        soma = 0.0
        for c in itens:
            pot = float(c.get("potencia", 0) or 0)
            if grupo and soma + pot > LIMITES_W["Iluminação"]:
                antes = len(saida)
                _fechar_grupo(grupo, saida)
                saida[-1]["criterio_formacao"] = "Iluminação agrupada até 1200 W"
                grupo, soma = [], 0.0
            grupo.append(c); soma += pot
        if grupo:
            _fechar_grupo(grupo, saida)
            saida[-1]["criterio_formacao"] = "Iluminação agrupada até 1200 W"

    # TUG de serviço: exclusivo por ambiente.
    tug = [c for c in elementares if c.get("tipo") == "TUG"]
    servico = [c for c in tug if _eh_servico(c.get("ambiente"))]
    for c in servico:
        c = dict(c)
        c["ambientes"] = [c.get("ambiente", "")]
        c["origens"] = [{"ambiente": c.get("ambiente", ""), "potencia": float(c.get("potencia",0) or 0)}]
        c["criterio_formacao"] = "TUG de cozinha/serviço exclusiva do ambiente"
        saida.append(c)

    # Demais TUGs: agrupamento por tensão e limite.
    secos = [c for c in tug if not _eh_servico(c.get("ambiente"))]
    for tensao in sorted({float(c.get("tensao", 0) or 0) for c in secos}):
        itens = [c for c in secos if float(c.get("tensao", 0) or 0) == tensao]
        grupo = []; soma = 0.0
        for c in itens:
            pot = float(c.get("potencia", 0) or 0)
            if grupo and soma + pot > LIMITES_W["TUG_SECO"]:
                _fechar_grupo(grupo, saida)
                saida[-1]["criterio_formacao"] = "TUG agrupada até 1800 W"
                grupo, soma = [], 0.0
            grupo.append(c); soma += pot
        if grupo:
            _fechar_grupo(grupo, saida)
            saida[-1]["criterio_formacao"] = "TUG agrupada até 1800 W"

    # Ordenação funcional: iluminação, TUG, TUE.
    ordem = {"Iluminação": 0, "TUG": 1, "TUE": 2}
    saida.sort(key=lambda c: (
        ordem.get(c.get("tipo"), 9),
        str(c.get("ambiente", "")).casefold()
    ))

    for c in saida:
        corrente = float(c.get("corrente", 0) or 0)
        c["disjuntor"] = disjuntor_por_corrente(corrente)
        # bitolas mínimas já vêm do circuito elementar e não são reduzidas.
        c["formacao_fase"] = "11.0"

    return saida
