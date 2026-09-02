import math


FOLGA_CABOS_ROTA = 1.15
FOLGA_ELETRODUTO_ROTA = 1.10
OCUPACAO_MAX_PRELIMINAR = 0.40

# Diâmetros externos aproximados de condutores isolados 750 V.
# Variam por fabricante; servem somente para pré-dimensionamento.
DIAMETRO_CONDUTOR_MM = {
    1.5: 3.0,
    2.5: 3.6,
    4.0: 4.2,
    6.0: 4.8,
    10.0: 6.1,
    16.0: 7.2,
}

# Diâmetro interno aproximado de eletroduto corrugado.
# O valor real deve ser confirmado no produto/fabricante escolhido.
ELETRODUTOS_MM = [
    (16, 12.0),
    (20, 15.5),
    (25, 20.5),
    (32, 26.5),
    (40, 34.0),
    (50, 43.0),
]


def _numero(v, padrao=0.0):
    try:
        return float(v)
    except Exception:
        return float(padrao)


def _tipo(c):
    return str(
        c.get(
            "tipo",
            ""
        )
        or ""
    ).strip().upper()


def _bitola(c):
    valor = _numero(
        c.get(
            "bitola",
            0.0
        )
    )

    if valor > 0:
        return valor

    tipo = _tipo(c)

    if tipo == "ILUMINAÇÃO".upper():
        return 1.5

    if tipo == "TUG":
        return 2.5

    return 2.5


def _condutores_circuito(circuito):
    """
    Representação preliminar dos condutores ativos do circuito.

    Iluminação/TUG:
      Fase + Neutro + PE

    TUE em 220 V:
      Fase L1 + Fase L2 + PE

    TUE em outra tensão:
      Fase + Neutro + PE

    O dimensionamento executivo ainda depende do equipamento,
    método de instalação e critérios finais do projeto.
    """
    bitola = _bitola(
        circuito
    )

    tipo = _tipo(
        circuito
    )

    tensao = _numero(
        circuito.get(
            "tensao",
            0.0
        )
    )

    if (
        tipo == "TUE"
        and tensao >= 200
    ):
        return [
            {
                "funcao": "Fase L1",
                "cor": "Vermelho",
                "bitola_mm2": bitola,
            },
            {
                "funcao": "Fase L2",
                "cor": "Preto",
                "bitola_mm2": bitola,
            },
            {
                "funcao": "Proteção (PE)",
                "cor": "Verde ou verde/amarelo",
                "bitola_mm2": bitola,
            },
        ]

    return [
        {
            "funcao": "Fase",
            "cor": "Vermelho",
            "bitola_mm2": bitola,
        },
        {
            "funcao": "Neutro",
            "cor": "Azul-claro",
            "bitola_mm2": bitola,
        },
        {
            "funcao": "Proteção (PE)",
            "cor": "Verde ou verde/amarelo",
            "bitola_mm2": bitola,
        },
    ]


def _area_ocupada_condutor(bitola_mm2):
    d = DIAMETRO_CONDUTOR_MM.get(
        float(bitola_mm2)
    )

    if d is None:
        # Aproximação conservadora para bitola fora da tabela.
        d = max(
            3.0,
            math.sqrt(
                float(bitola_mm2)
            ) * 1.8
        )

    return math.pi * d * d / 4.0


def _eletroduto_por_ocupacao(condutores):
    area_ocupada = sum(
        _area_ocupada_condutor(
            c["bitola_mm2"]
        )
        for c in condutores
    )

    for nominal, diametro_interno in ELETRODUTOS_MM:
        area_interna = (
            math.pi
            * diametro_interno
            * diametro_interno
            / 4.0
        )

        taxa = (
            area_ocupada
            / area_interna
            if area_interna > 0
            else 1.0
        )

        if taxa <= OCUPACAO_MAX_PRELIMINAR:
            return {
                "diametro_nominal_mm": nominal,
                "diametro_interno_aprox_mm": diametro_interno,
                "ocupacao_pct": taxa * 100.0,
                "area_condutores_mm2": area_ocupada,
            }

    nominal, diametro_interno = ELETRODUTOS_MM[-1]

    area_interna = (
        math.pi
        * diametro_interno
        * diametro_interno
        / 4.0
    )

    return {
        "diametro_nominal_mm": nominal,
        "diametro_interno_aprox_mm": diametro_interno,
        "ocupacao_pct": (
            area_ocupada
            / area_interna
            * 100.0
        ),
        "area_condutores_mm2": area_ocupada,
        "excedeu_tabela": True,
    }


def _comprimento_rota(rota):
    return max(
        0.0,
        _numero(
            rota.get(
                "comprimento_m",
                0.0
            )
        )
    )


def dimensionar_rotas(
    rotas,
    circuitos
):
    """
    Dimensiona cada trecho físico já criado pelo roteamento.

    Resultado:
    - circuitos em cada trecho;
    - condutores em cada trecho;
    - ocupação aproximada;
    - eletroduto nominal preliminar;
    - quantitativo de condutores pelo comprimento REAL do traçado;
    - quantitativo de eletrodutos por diâmetro.
    """
    por_numero = {}

    for circuito in (
        circuitos
        or []
    ):
        numero = int(
            circuito.get(
                "numero",
                0
            )
            or 0
        )

        if numero > 0:
            por_numero[
                numero
            ] = dict(
                circuito
            )

    rotas_dim = []
    cabos = {}
    eletrodutos = {}

    for indice, rota in enumerate(
        rotas
        or [],
        start=1
    ):
        numeros = [
            int(n)
            for n in (
                rota.get(
                    "circuitos",
                    []
                )
                or []
            )
            if int(n) > 0
        ]

        condutores = []

        for numero in numeros:
            circuito = por_numero.get(
                numero
            )

            if circuito is None:
                continue

            for condutor in _condutores_circuito(
                circuito
            ):
                item = dict(
                    condutor
                )
                item[
                    "circuito"
                ] = numero
                condutores.append(
                    item
                )

        # Trechos puramente de comando/iluminação externa podem não ter
        # circuitos registrados pelas fases antigas. Não inventa cabo:
        # deixa o trecho identificado para auditoria.
        dimens = _eletroduto_por_ocupacao(
            condutores
        ) if condutores else {
            "diametro_nominal_mm": None,
            "diametro_interno_aprox_mm": None,
            "ocupacao_pct": 0.0,
            "area_condutores_mm2": 0.0,
        }

        comprimento = _comprimento_rota(
            rota
        )

        item_rota = dict(
            rota
        )

        item_rota.update({
            "trecho_id":
                indice,
            "condutores":
                condutores,
            "qtd_condutores":
                len(condutores),
            "diametro_eletroduto_mm":
                dimens.get(
                    "diametro_nominal_mm"
                ),
            "ocupacao_pct":
                round(
                    dimens.get(
                        "ocupacao_pct",
                        0.0
                    ),
                    1
                ),
        })

        rotas_dim.append(
            item_rota
        )

        diametro = dimens.get(
            "diametro_nominal_mm"
        )

        if (
            diametro
            and comprimento > 0
        ):
            eletrodutos[
                diametro
            ] = (
                eletrodutos.get(
                    diametro,
                    0.0
                )
                + comprimento
            )

        for condutor in condutores:
            chave = (
                int(
                    condutor[
                        "circuito"
                    ]
                ),
                float(
                    condutor[
                        "bitola_mm2"
                    ]
                ),
                str(
                    condutor[
                        "funcao"
                    ]
                ),
                str(
                    condutor[
                        "cor"
                    ]
                ),
            )

            cabos[
                chave
            ] = (
                cabos.get(
                    chave,
                    0.0
                )
                + comprimento
            )

    cabos_lista = []

    for (
        circuito,
        bitola,
        funcao,
        cor
    ), comprimento in sorted(
        cabos.items()
    ):
        cabos_lista.append({
            "circuito":
                circuito,
            "bitola_mm2":
                bitola,
            "funcao":
                funcao,
            "cor":
                cor,
            "comprimento_rota_m":
                round(
                    comprimento,
                    2
                ),
            "comprimento_com_folga_m":
                round(
                    comprimento
                    * FOLGA_CABOS_ROTA,
                    2
                ),
        })

    eletrodutos_lista = []

    for diametro, comprimento in sorted(
        eletrodutos.items()
    ):
        eletrodutos_lista.append({
            "diametro_mm":
                diametro,
            "comprimento_rota_m":
                round(
                    comprimento,
                    2
                ),
            "comprimento_com_folga_m":
                round(
                    comprimento
                    * FOLGA_ELETRODUTO_ROTA,
                    2
                ),
        })

    return {
        "status":
            "pre_dimensionado_por_rota",
        "criterio":
            (
                "Comprimento geométrico do traçado + ocupação preliminar "
                "de 40%; diâmetros externos dos condutores e internos dos "
                "eletrodutos são aproximações e devem ser confirmados "
                "com o fabricante."
            ),
        "total_trechos":
            len(rotas_dim),
        "rotas":
            rotas_dim,
        "cabos":
            cabos_lista,
        "eletrodutos":
            eletrodutos_lista,
    }


def desenhar_dimensionamento_rotas(
    msp,
    resumo,
    layer="PROJ_ELETRICA_DIMENSIONAMENTO"
):
    """
    Cria etiquetas técnicas em camada separada.

    A camada é congelada pelo gerador CAD para não poluir a planta.
    O usuário pode descongelá-la no CAD para auditoria.
    """
    for rota in (
        resumo.get(
            "rotas",
            []
        )
        or []
    ):
        diametro = rota.get(
            "diametro_eletroduto_mm"
        )

        if not diametro:
            continue

        p1 = rota.get(
            "inicio"
        )
        p2 = rota.get(
            "fim"
        )

        if not p1 or not p2:
            continue

        mx = (
            float(p1[0])
            + float(p2[0])
        ) / 2.0

        my = (
            float(p1[1])
            + float(p2[1])
        ) / 2.0

        nums = rota.get(
            "circuitos",
            []
        )

        txt_circuitos = ",".join(
            f"C{int(n):02d}"
            for n in nums
        )

        texto = (
            f"Ø{int(diametro)}"
            + (
                f" | {txt_circuitos}"
                if txt_circuitos
                else ""
            )
        )

        msp.add_text(
            texto,
            dxfattribs={
                "layer":
                    layer,
                "height":
                    0.08,
                "insert":
                    (mx, my),
            }
        )
