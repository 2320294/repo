
import hashlib

from soleiras_geometria import distancia_ponto_segmento

TOLERANCIA_SOLEIRA_AMBIENTE = 0.03


def vertices_soleira(s):
    out = []
    for p in (s.get("vertices") or []):
        q = (float(p[0]), float(p[1]))
        if q not in out:
            out.append(q)
    return out


def segmentos_poligono(poly):
    if len(poly) < 2:
        return []
    return [
        (poly[i], poly[(i + 1) % len(poly)])
        for i in range(len(poly))
    ]


def soleira_toca_ambiente(s, poly, tolerancia=TOLERANCIA_SOLEIRA_AMBIENTE):
    verts = vertices_soleira(s)
    segs = segmentos_poligono(poly)

    if not verts or not segs:
        return False

    return min(
        distancia_ponto_segmento(v, a, b)
        for v in verts
        for a, b in segs
    ) <= tolerancia


def centro_soleira(s):
    verts = vertices_soleira(s)
    if not verts:
        return None
    return (
        sum(p[0] for p in verts) / len(verts),
        sum(p[1] for p in verts) / len(verts),
    )


def id_porta(nome_ambiente, s):
    """
    ID estável baseado na geometria da soleira.
    Não depende da ordem das entidades no DXF.
    """
    verts = sorted(
        (round(x, 5), round(y, 5))
        for x, y in vertices_soleira(s)
    )
    assinatura = (
        str(nome_ambiente).strip().upper()
        + "|"
        + "|".join(f"{x:.5f},{y:.5f}" for x, y in verts)
    )
    digest = hashlib.sha1(
        assinatura.encode("utf-8")
    ).hexdigest()[:10]
    return f"PORTA_{digest}"


def portas_do_ambiente(nome_ambiente, poly, soleiras_raw):
    """
    Retorna as soleiras/portas pertencentes ao ambiente em ordem geométrica
    determinística. Cada item recebe id estável e número visual.
    """
    itens = []

    for s in soleiras_raw:
        if not soleira_toca_ambiente(s, poly):
            continue

        centro = centro_soleira(s)
        if centro is None:
            continue

        itens.append({
            "id": id_porta(nome_ambiente, s),
            "centro": centro,
            "soleira": s,
        })

    # Ordem visual estável: de cima para baixo e da esquerda para a direita.
    # O usuário não depende dessa ordem para escolher, pois clica na planta;
    # ela serve apenas para legenda "Porta 1", "Porta 2", ...
    itens.sort(
        key=lambda item: (
            -round(item["centro"][1], 5),
            round(item["centro"][0], 5),
        )
    )

    for indice, item in enumerate(itens, start=1):
        item["numero"] = indice
        item["rotulo"] = f"Porta {indice}"

    return itens
