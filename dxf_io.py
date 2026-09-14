import ezdxf

from cargas import dimensionar_cargas
from geometria import bbox_poligono, ponto_em_poligono


CAMADAS_OBRIGATORIAS = {
    "IA_AMBIENTES": 0,
    "IA_TEXTOS": 0,
    "IA_PORTAS": 0,
    "IA_SOLEIRAS": 0
}


def validar_camadas(msp, contexto="DXF"):
    contagem = dict(CAMADAS_OBRIGATORIAS)

    for entity in msp:
        if hasattr(entity.dxf, "layer"):
            layer = str(
                entity.dxf.layer
            ).upper().strip()

            if layer in contagem:
                contagem[layer] += 1

    camadas_vazias = [
        cam
        for cam, qtd in contagem.items()
        if qtd == 0
    ]

    if camadas_vazias:
        raise ValueError(
            f"❌ Erro de {contexto}: "
            f"A(s) seguinte(s) camada(s) obrigatória(s) "
            f"está(ão) vazia(s) ou ausente(s): "
            f"{', '.join(camadas_vazias)}."
        )


def ler_elementos(msp):
    polilinhas = []
    textos = []
    portas_raw = []
    soleiras_raw = []

    for entity in msp:
        tipo = entity.dxftype()

        if not hasattr(entity.dxf, "layer"):
            continue

        layer = str(
            entity.dxf.layer
        ).upper().strip()

        if (
            tipo in ["LWPOLYLINE", "POLYLINE"]
            and layer == "IA_AMBIENTES"
        ):
            try:
                if tipo == "LWPOLYLINE":
                    pontos = [
                        (p[0], p[1])
                        for p in entity.get_points(
                            format="xy"
                        )
                    ]
                else:
                    pontos = [
                        (
                            v.dxf.location.x,
                            v.dxf.location.y
                        )
                        for v in entity.vertices
                    ]

                if pontos:
                    polilinhas.append(pontos)

            except Exception:
                pass

        elif (
            tipo in ["TEXT", "MTEXT"]
            and layer == "IA_TEXTOS"
        ):
            try:
                texto_str = (
                    entity.text
                    if tipo == "MTEXT"
                    else entity.dxf.text
                ).strip()

                if texto_str:
                    textos.append({
                        "nome": texto_str,
                        "x": entity.dxf.insert.x,
                        "y": entity.dxf.insert.y
                    })
            except Exception:
                pass

        elif layer == "IA_PORTAS":
            if tipo == "LINE":
                portas_raw.append({
                    "p1": (
                        entity.dxf.start.x,
                        entity.dxf.start.y
                    ),
                    "p2": (
                        entity.dxf.end.x,
                        entity.dxf.end.y
                    )
                })

            elif tipo in ["LWPOLYLINE", "POLYLINE"]:
                try:
                    if tipo == "LWPOLYLINE":
                        pts = [
                            (p[0], p[1])
                            for p in entity.get_points(
                                format="xy"
                            )
                        ]
                    else:
                        pts = [
                            (
                                v.dxf.location.x,
                                v.dxf.location.y
                            )
                            for v in entity.vertices
                        ]

                    if len(pts) >= 2:
                        portas_raw.append({
                            "p1": pts[0],
                            "p2": pts[-1]
                        })
                except Exception:
                    pass

        elif layer == "IA_SOLEIRAS":
            if tipo == "LINE":
                soleiras_raw.append({
                    "p1": (
                        entity.dxf.start.x,
                        entity.dxf.start.y
                    ),
                    "p2": (
                        entity.dxf.end.x,
                        entity.dxf.end.y
                    )
                })

            elif tipo in ["LWPOLYLINE", "POLYLINE"]:
                try:
                    if tipo == "LWPOLYLINE":
                        pts = [
                            (p[0], p[1])
                            for p in entity.get_points(
                                format="xy"
                            )
                        ]
                    else:
                        pts = [
                            (
                                v.dxf.location.x,
                                v.dxf.location.y
                            )
                            for v in entity.vertices
                        ]

                    if len(pts) >= 2:
                        # Fase 8.2: preserva os quatro vértices para que
                        # P1/P2/P3/P4 e o interruptor usem a MESMA geometria.
                        vertices_unicos = []
                        for pt in pts:
                            q = (float(pt[0]), float(pt[1]))
                            if q not in vertices_unicos:
                                vertices_unicos.append(q)

                        soleiras_raw.append({
                            "p1": pts[0],
                            "p2": pts[-1],
                            "vertices": vertices_unicos
                        })
                except Exception:
                    pass

    return {
        "polilinhas": polilinhas,
        "textos": textos,
        "portas_raw": portas_raw,
        "soleiras_raw": soleiras_raw
    }


def nome_ambiente_para_polilinha(
    polilinha,
    textos
):
    """
    Associa o texto correto ao ambiente.

    Fase 13.6 Rev.121:
    1) prioridade absoluta para textos realmente DENTRO do polígono;
    2) se houver mais de um texto interno, usa o mais próximo do centro
       geométrico do ambiente;
    3) a tolerância antiga de +/-0,50 m fica apenas como fallback para
       plantas em que o texto foi desenhado ligeiramente fora do contorno.

    Isso evita que ambientes estreitos, como HALL/corredor, recebam o nome
    de um cômodo vizinho apenas porque os bounding boxes ficam próximos.
    """
    min_x, max_x, min_y, max_y = bbox_poligono(polilinha)
    cx = (float(min_x) + float(max_x)) / 2.0
    cy = (float(min_y) + float(max_y)) / 2.0

    internos = []
    for t in textos:
        try:
            tx = float(t["x"])
            ty = float(t["y"])
        except Exception:
            continue

        if ponto_em_poligono(tx, ty, polilinha):
            internos.append((
                (tx - cx) ** 2 + (ty - cy) ** 2,
                t
            ))

    if internos:
        internos.sort(key=lambda item: item[0])
        return internos[0][1]["nome"]

    # Compatibilidade com desenhos antigos: somente quando nenhum texto
    # estiver efetivamente dentro do polígono, aceita a tolerância de 0,50 m.
    candidatos = []
    for t in textos:
        try:
            tx = float(t["x"])
            ty = float(t["y"])
        except Exception:
            continue

        if (
            min_x - 0.5 <= tx <= max_x + 0.5
            and min_y - 0.5 <= ty <= max_y + 0.5
        ):
            # Entre candidatos do fallback, escolhe o mais próximo do centro
            # do ambiente em vez de depender da ordem das entidades no DXF.
            candidatos.append((
                (tx - cx) ** 2 + (ty - cy) ** 2,
                t
            ))

    if candidatos:
        candidatos.sort(key=lambda item: item[0])
        return candidatos[0][1]["nome"]

    return None


def processar_dxf(caminho_arquivo):
    doc = ezdxf.readfile(
        caminho_arquivo
    )

    msp = doc.modelspace()

    validar_camadas(
        msp,
        contexto="Validação do DXF"
    )

    elementos = ler_elementos(msp)

    polilinhas = elementos["polilinhas"]
    textos = elementos["textos"]

    resultados = []
    ambientes_processados = {}

    for polilinha in polilinhas:
        min_x, max_x, min_y, max_y = (
            bbox_poligono(polilinha)
        )

        area = (
            (max_x - min_x)
            *
            (max_y - min_y)
        )

        perimetro = (
            (max_x - min_x) * 2
            +
            (max_y - min_y) * 2
        )

        if area < 0.5:
            continue

        nome_ambiente = (
            nome_ambiente_para_polilinha(
                polilinha,
                textos
            )
        )

        if not nome_ambiente:
            continue

        if nome_ambiente in ambientes_processados:
            ambientes_processados[
                nome_ambiente
            ] += 1

            nome_ambiente = (
                f"{nome_ambiente} "
                f"{ambientes_processados[nome_ambiente]}"
            )
        else:
            ambientes_processados[
                nome_ambiente
            ] = 1

        cargas = dimensionar_cargas(
            nome_ambiente,
            area,
            perimetro
        )

        resultados.append({
            "Ambiente": nome_ambiente,

            "Centro_X":
                (min_x + max_x) / 2,

            "Centro_Y":
                (min_y + max_y) / 2,

            "Área (m²)":
                area,

            "Perímetro (m)":
                perimetro,

            "Qtd Ilum.":
                int(
                    cargas["Qtd Ilum."]
                ),

            "Pot. Unit. Ilum (VA)":
                int(
                    cargas[
                        "Pot. Unit. Ilum (VA)"
                    ]
                ),

            "Carga Ilum. (VA)":
                int(
                    cargas[
                        "Carga Ilum. (VA)"
                    ]
                ),

            "TUGs (Qtd)":
                int(
                    cargas[
                        "TUGs (Qtd)"
                    ]
                ),

            "Pot. Unit. TUG (VA)":
                int(
                    cargas[
                        "Pot. Unit. TUG (VA)"
                    ]
                ),

            "Carga TUGs (VA)":
                int(
                    cargas[
                        "Carga TUGs (VA)"
                    ]
                ),

            "Equipamento TUE":
                cargas[
                    "Equipamento TUE"
                ],

            "Qtd TUE":
                int(
                    cargas[
                        "Qtd TUE"
                    ]
                ),

            "Pot. Unit. TUE (VA)":
                int(
                    cargas[
                        "Pot. Unit. TUE (VA)"
                    ]
                ),

            "Carga TUE (VA)":
                int(
                    cargas[
                        "Carga TUE (VA)"
                    ]
                )
        })

    return resultados
