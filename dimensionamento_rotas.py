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


# ============================================================
# FASE 11.7 — VALIDAÇÃO ELÉTRICA PRELIMINAR DAS ROTAS
# ============================================================

RHO_COBRE_OPERACAO = 0.0225  # ohm.mm²/m — valor preliminar conservador
QUEDA_REFERENCIA_PCT = 4.0   # referência de projeto; confirmar no executivo


def _ponto_chave(pt):
    if not pt:
        return None
    return (
        round(float(pt[0]), 4),
        round(float(pt[1]), 4),
    )


def _disjuntor_a(circuito):
    valor = circuito.get(
        "disjuntor",
        0
    )

    try:
        return float(valor)
    except Exception:
        txt = str(valor or "")
        numero = ""
        for ch in txt:
            if (
                ch.isdigit()
                or ch in ".,"
            ):
                numero += ch
            elif numero:
                break

        try:
            return float(
                numero.replace(",", ".")
            )
        except Exception:
            return 0.0


def _comprimento_maximo_circuito(
    numero,
    rotas
):
    """
    Reconstrói o caminho dirigido do circuito usando a própria topologia
    do roteamento e retorna a maior distância acumulada da origem até
    qualquer ponto terminal.

    É mais adequado para queda de tensão do que somar todos os ramos.
    """
    arestas = []

    for rota in (
        rotas
        or []
    ):
        if numero not in (
            rota.get(
                "circuitos",
                []
            )
            or []
        ):
            continue

        a = _ponto_chave(
            rota.get(
                "inicio"
            )
        )
        b = _ponto_chave(
            rota.get(
                "fim"
            )
        )

        if (
            a is None
            or b is None
        ):
            continue

        arestas.append({
            "a": a,
            "b": b,
            "l": max(
                0.0,
                _numero(
                    rota.get(
                        "comprimento_m",
                        0.0
                    )
                )
            ),
        })

    if not arestas:
        return 0.0

    entradas = {
        e["b"]
        for e in arestas
    }

    origens = [
        e["a"]
        for e in arestas
        if e["a"] not in entradas
    ]

    if not origens:
        origens = [
            arestas[0]["a"]
        ]

    saidas = {}

    for e in arestas:
        saidas.setdefault(
            e["a"],
            []
        ).append(
            e
        )

    memo = {}

    def maior_a_partir(no, visitando=None):
        if no in memo:
            return memo[no]

        visitando = set(
            visitando
            or set()
        )

        if no in visitando:
            return 0.0

        visitando.add(
            no
        )

        melhor = 0.0

        for e in saidas.get(
            no,
            []
        ):
            melhor = max(
                melhor,
                e["l"]
                + maior_a_partir(
                    e["b"],
                    visitando
                )
            )

        memo[
            no
        ] = melhor

        return melhor

    return max(
        maior_a_partir(
            origem
        )
        for origem in origens
    )


def _queda_tensao_pct(
    comprimento_m,
    corrente_a,
    bitola_mm2,
    tensao_v
):
    if (
        comprimento_m <= 0
        or corrente_a <= 0
        or bitola_mm2 <= 0
        or tensao_v <= 0
    ):
        return 0.0

    # Circuitos monofásicos/bifásicos: percurso elétrico de ida e volta.
    delta_v = (
        2.0
        * RHO_COBRE_OPERACAO
        * comprimento_m
        * corrente_a
        / bitola_mm2
    )

    return (
        delta_v
        / tensao_v
        * 100.0
    )


def validar_eletrica_rotas(
    resumo_rotas,
    circuitos
):
    """
    Validação preliminar da Fase 11.7.

    Verifica:
    - maior percurso físico de cada circuito;
    - queda de tensão estimada;
    - disjuntor >= corrente de projeto;
    - seção mínima funcional (iluminação/TUG);
    - maior número de circuitos compartilhando um mesmo eletroduto.

    NÃO substitui verificação executiva de capacidade de condução,
    método de instalação, agrupamento, temperatura e curto-circuito.
    """
    rotas = (
        resumo_rotas.get(
            "rotas",
            []
        )
        if isinstance(
            resumo_rotas,
            dict
        )
        else []
    )

    resultados = []
    alertas = []

    max_circuitos_trecho = 0
    trecho_mais_carregado = None

    for rota in rotas:
        qtd = len(
            set(
                rota.get(
                    "circuitos",
                    []
                )
                or []
            )
        )

        if qtd > max_circuitos_trecho:
            max_circuitos_trecho = qtd
            trecho_mais_carregado = rota.get(
                "trecho_id"
            )

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

        if numero <= 0:
            continue

        tipo = str(
            circuito.get(
                "tipo",
                ""
            )
            or ""
        )

        potencia = _numero(
            circuito.get(
                "potencia",
                0.0
            )
        )

        tensao = _numero(
            circuito.get(
                "tensao",
                0.0
            )
        )

        corrente = _numero(
            circuito.get(
                "corrente",
                0.0
            )
        )

        if (
            corrente <= 0
            and potencia > 0
            and tensao > 0
        ):
            corrente = (
                potencia
                / tensao
            )

        bitola = _bitola(
            circuito
        )

        disjuntor = _disjuntor_a(
            circuito
        )

        comprimento_max = (
            _comprimento_maximo_circuito(
                numero,
                rotas
            )
        )

        queda_pct = _queda_tensao_pct(
            comprimento_max,
            corrente,
            bitola,
            tensao
        )

        if (
            str(tipo).upper()
            == "ILUMINAÇÃO".upper()
        ):
            secao_min = 1.5
        elif (
            str(tipo).upper()
            == "TUG"
        ):
            secao_min = 2.5
        else:
            secao_min = 0.0

        status_queda = (
            "OK"
            if queda_pct
            <= QUEDA_REFERENCIA_PCT
            else "ALERTA"
        )

        status_disjuntor = (
            "OK"
            if (
                disjuntor <= 0
                or corrente <= disjuntor
            )
            else "ALERTA"
        )

        status_secao = (
            "OK"
            if (
                secao_min <= 0
                or bitola >= secao_min
            )
            else "ALERTA"
        )

        status = (
            "OK"
            if all(
                x == "OK"
                for x in [
                    status_queda,
                    status_disjuntor,
                    status_secao,
                ]
            )
            else "ALERTA"
        )

        resultado = {
            "numero":
                numero,
            "tipo":
                tipo,
            "ambiente":
                circuito.get(
                    "ambiente",
                    ""
                ),
            "potencia_w":
                round(
                    potencia,
                    1
                ),
            "tensao_v":
                round(
                    tensao,
                    1
                ),
            "corrente_a":
                round(
                    corrente,
                    2
                ),
            "bitola_mm2":
                bitola,
            "disjuntor_a":
                disjuntor,
            "comprimento_max_m":
                round(
                    comprimento_max,
                    2
                ),
            "queda_tensao_pct":
                round(
                    queda_pct,
                    2
                ),
            "status_queda":
                status_queda,
            "status_disjuntor":
                status_disjuntor,
            "status_secao":
                status_secao,
            "status":
                status,
        }

        resultados.append(
            resultado
        )

        if status == "ALERTA":
            alertas.append(
                numero
            )

    return {
        "status":
            (
                "ok_preliminar"
                if not alertas
                else "alerta"
            ),
        "queda_referencia_pct":
            QUEDA_REFERENCIA_PCT,
        "criterio_queda":
            (
                "Estimativa pelo maior percurso físico dirigido do circuito, "
                "cobre com resistividade preliminar de operação "
                f"{RHO_COBRE_OPERACAO:g} ohm.mm²/m."
            ),
        "max_circuitos_mesmo_trecho":
            max_circuitos_trecho,
        "trecho_mais_carregado":
            trecho_mais_carregado,
        "circuitos_alerta":
            alertas,
        "circuitos":
            resultados,
        "observacao":
            (
                "A capacidade de condução de corrente ainda não é validada "
                "porque depende do método de instalação, temperatura, "
                "agrupamento real e dados do fabricante."
            ),
    }
