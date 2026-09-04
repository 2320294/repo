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


def _eletroduto_por_ocupacao(
    condutores,
    max_nominal_mm=None
):
    area_ocupada = sum(
        _area_ocupada_condutor(
            c["bitola_mm2"]
        )
        for c in condutores
    )

    tabela = [
        (nominal, diametro_interno)
        for nominal, diametro_interno in ELETRODUTOS_MM
        if (
            max_nominal_mm is None
            or nominal <= int(max_nominal_mm)
        )
    ]

    if not tabela:
        tabela = list(ELETRODUTOS_MM)

    for nominal, diametro_interno in tabela:
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

    nominal, diametro_interno = tabela[-1]

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
        "limite_nominal_mm": (
            int(max_nominal_mm)
            if max_nominal_mm is not None
            else nominal
        ),
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
            condutores,
            max_nominal_mm=25
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
            "limite_eletroduto_terminal_mm":
                25,
            "excede_limite_eletroduto_terminal":
                bool(
                    dimens.get(
                        "excedeu_tabela",
                        False
                    )
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
# FASE 13.6 REV.1 — VALIDAÇÃO ELÉTRICA PRELIMINAR DAS ROTAS
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



SECOES_PADRONIZADAS_MM2 = [
    1.5,
    2.5,
    4.0,
    6.0,
    10.0,
    16.0,
    25.0,
    35.0,
    50.0,
]


def _secao_minima_funcional(
    circuito
):
    tipo = _tipo(
        circuito
    )

    if tipo == "ILUMINAÇÃO".upper():
        return 1.5

    if tipo == "TUG":
        return 2.5

    return max(
        0.0,
        _bitola(
            circuito
        )
    )


def _proxima_secao_padronizada(
    secao_atual,
    secao_minima=0.0
):
    referencia = max(
        float(
            secao_atual
        ),
        float(
            secao_minima
        )
    )

    for secao in SECOES_PADRONIZADAS_MM2:
        if secao > referencia + 1e-9:
            return secao

    return None


def corrigir_bitolas_por_queda(
    rotas,
    circuitos,
    limite_queda_pct=QUEDA_REFERENCIA_PCT
):
    """
    Fase 13.6 Rev.13.

    Corrige automaticamente APENAS a seção necessária por queda de tensão.

    Para cada circuito:
    1. calcula o maior percurso físico;
    2. testa a seção atual;
    3. se exceder o limite, sobe para a próxima seção padronizada;
    4. repete até atender ou acabar a tabela.

    Não reduz nenhuma seção existente.
    Não altera o disjuntor nesta etapa.
    """
    corrigidos = [
        dict(c)
        for c in (
            circuitos
            or []
        )
    ]

    relatorio = []

    for circuito in corrigidos:
        numero = int(
            circuito.get(
                "numero",
                0
            )
            or 0
        )

        if numero <= 0:
            continue

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

        comprimento = _comprimento_maximo_circuito(
            numero,
            rotas
        )

        original = _bitola(
            circuito
        )

        minimo = _secao_minima_funcional(
            circuito
        )

        secao = max(
            original,
            minimo
        )

        queda_inicial = _queda_tensao_pct(
            comprimento,
            corrente,
            secao,
            tensao
        )

        queda_final = queda_inicial
        status = "MANTIDA"

        while (
            queda_final
            > float(
                limite_queda_pct
            )
        ):
            proxima = _proxima_secao_padronizada(
                secao,
                minimo
            )

            if proxima is None:
                status = "SEM_SECAO_NA_TABELA"
                break

            secao = proxima

            queda_final = _queda_tensao_pct(
                comprimento,
                corrente,
                secao,
                tensao
            )

            status = "CORRIGIDA"

        if secao > original + 1e-9:
            circuito[
                "bitola_original"
            ] = original

            circuito[
                "bitola"
            ] = secao

            circuito[
                "criterio_bitola"
            ] = (
                "Seção elevada automaticamente por queda de tensão"
            )

            circuito[
                "queda_tensao_antes_pct"
            ] = round(
                queda_inicial,
                2
            )

            circuito[
                "queda_tensao_depois_pct"
            ] = round(
                queda_final,
                2
            )

        relatorio.append({
            "numero":
                numero,
            "tipo":
                circuito.get(
                    "tipo",
                    ""
                ),
            "ambiente":
                circuito.get(
                    "ambiente",
                    ""
                ),
            "comprimento_max_m":
                round(
                    comprimento,
                    2
                ),
            "corrente_a":
                round(
                    corrente,
                    2
                ),
            "bitola_original_mm2":
                original,
            "bitola_final_mm2":
                secao,
            "queda_antes_pct":
                round(
                    queda_inicial,
                    2
                ),
            "queda_depois_pct":
                round(
                    queda_final,
                    2
                ),
            "limite_pct":
                float(
                    limite_queda_pct
                ),
            "status":
                status,
        })

    return (
        corrigidos,
        relatorio
    )


def validar_eletrica_rotas(
    resumo_rotas,
    circuitos
):
    """
    Validação preliminar da Fase 13.6 Rev.13.

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


# ============================================================
# FASE 13.6 REV.1 — DIAGNÓSTICO DE AGRUPAMENTO NOS ELETRODUTOS
# ============================================================

def _prioridade_agrupamento(qtd_circuitos):
    """
    Classificação de prioridade para revisão.

    IMPORTANTE:
    estes limites NÃO são fatores normativos de correção.
    Servem apenas para ordenar os trechos que merecem análise primeiro.
    """
    qtd = int(qtd_circuitos or 0)

    if qtd <= 0:
        return "SEM CIRCUITO"

    if qtd == 1:
        return "BAIXA"

    if qtd <= 3:
        return "MÉDIA"

    return "ALTA"


def diagnosticar_agrupamento_rotas(
    resumo_rotas,
    circuitos
):
    """
    Fase 13.6 Rev.13.

    Analisa a concentração física já conhecida no roteamento, sem aplicar
    automaticamente fatores de capacidade de condução.

    Por trecho:
    - circuitos compartilhados;
    - quantidade de condutores;
    - ocupação geométrica;
    - eletroduto preliminar;
    - prioridade de revisão.

    Por circuito:
    - maior quantidade de circuitos simultâneos em seu caminho;
    - maior quantidade de condutores no mesmo trecho;
    - maior ocupação geométrica encontrada;
    - trechos compartilhados.

    A capacidade de condução permanece PENDENTE DE PARÂMETROS enquanto
    não houver método de instalação, temperatura, características reais
    dos cabos/eletrodutos e critério de agrupamento aplicável.
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

    por_numero = {
        int(c.get("numero", 0) or 0): dict(c)
        for c in (circuitos or [])
        if int(c.get("numero", 0) or 0) > 0
    }

    trechos = []
    resumo_circuitos = {
        numero: {
            "numero": numero,
            "tipo": circuito.get("tipo", ""),
            "ambiente": circuito.get("ambiente", ""),
            "corrente_a": round(
                _numero(
                    circuito.get(
                        "corrente",
                        0.0
                    )
                ),
                2
            ),
            "bitola_mm2": _bitola(
                circuito
            ),
            "max_circuitos_compartilhados": 0,
            "max_condutores_trecho": 0,
            "max_ocupacao_pct": 0.0,
            "trechos_compartilhados": [],
        }
        for numero, circuito in por_numero.items()
    }

    for rota in rotas:
        numeros = sorted(
            set(
                int(n)
                for n in (
                    rota.get(
                        "circuitos",
                        []
                    )
                    or []
                )
                if int(n) > 0
            )
        )

        qtd_circuitos = len(
            numeros
        )

        qtd_condutores = int(
            rota.get(
                "qtd_condutores",
                0
            )
            or 0
        )

        ocupacao = _numero(
            rota.get(
                "ocupacao_pct",
                0.0
            )
        )

        trecho_id = rota.get(
            "trecho_id"
        )

        prioridade = _prioridade_agrupamento(
            qtd_circuitos
        )

        trechos.append({
            "trecho_id":
                trecho_id,
            "tipo_rede":
                rota.get(
                    "tipo_rede",
                    ""
                ),
            "criterio":
                rota.get(
                    "criterio",
                    ""
                ),
            "circuitos":
                numeros,
            "qtd_circuitos":
                qtd_circuitos,
            "qtd_condutores":
                qtd_condutores,
            "diametro_eletroduto_mm":
                rota.get(
                    "diametro_eletroduto_mm"
                ),
            "ocupacao_pct":
                round(
                    ocupacao,
                    1
                ),
            "comprimento_m":
                round(
                    _numero(
                        rota.get(
                            "comprimento_m",
                            0.0
                        )
                    ),
                    2
                ),
            "prioridade_revisao":
                prioridade,
            "avaliacao_capacidade":
                (
                    "PENDENTE DE PARÂMETROS"
                    if qtd_circuitos > 0
                    else "SEM CIRCUITO"
                ),
        })

        for numero in numeros:
            resumo = resumo_circuitos.get(
                numero
            )

            if resumo is None:
                continue

            resumo[
                "max_circuitos_compartilhados"
            ] = max(
                resumo[
                    "max_circuitos_compartilhados"
                ],
                qtd_circuitos
            )

            resumo[
                "max_condutores_trecho"
            ] = max(
                resumo[
                    "max_condutores_trecho"
                ],
                qtd_condutores
            )

            resumo[
                "max_ocupacao_pct"
            ] = max(
                resumo[
                    "max_ocupacao_pct"
                ],
                ocupacao
            )

            if qtd_circuitos > 1:
                resumo[
                    "trechos_compartilhados"
                ].append(
                    trecho_id
                )

    circuitos_diag = []

    for numero in sorted(
        resumo_circuitos
    ):
        item = resumo_circuitos[
            numero
        ]

        item[
            "max_ocupacao_pct"
        ] = round(
            item[
                "max_ocupacao_pct"
            ],
            1
        )

        item[
            "qtd_trechos_compartilhados"
        ] = len(
            [
                t
                for t in item[
                    "trechos_compartilhados"
                ]
                if t is not None
            ]
        )

        item[
            "prioridade_revisao"
        ] = _prioridade_agrupamento(
            item[
                "max_circuitos_compartilhados"
            ]
        )

        item[
            "avaliacao_capacidade"
        ] = (
            "PENDENTE DE PARÂMETROS"
        )

        circuitos_diag.append(
            item
        )

    trechos_alta = [
        t
        for t in trechos
        if t.get(
            "prioridade_revisao"
        )
        == "ALTA"
    ]

    return {
        "status":
            "diagnostico",
        "criterio":
            (
                "Diagnóstico físico de concentração. Não aplica fator "
                "normativo de agrupamento nem altera bitolas."
            ),
        "trechos":
            trechos,
        "circuitos":
            circuitos_diag,
        "qtd_trechos_alta_prioridade":
            len(
                trechos_alta
            ),
        "max_circuitos_mesmo_trecho":
            max(
                [
                    t.get(
                        "qtd_circuitos",
                        0
                    )
                    for t in trechos
                ]
                or [0]
            ),
        "observacao":
            (
                "Para validar capacidade de condução é necessário informar "
                "método de instalação, temperatura ambiente, características "
                "reais dos cabos/eletrodutos e critério de agrupamento aplicável."
            ),
    }


# ============================================================
# FASE 13.6 REV.1 — CAPACIDADE DE CONDUÇÃO PRELIMINAR
# ============================================================

# Referências internas preliminares para cobre/PVC 70 °C.
# A validação executiva deve ser conferida pelo responsável técnico
# contra a edição normativa aplicável e dados dos fabricantes.
CAPACIDADE_REFERENCIA_A = {
    "B1": {
        1.5: 17.5,
        2.5: 24.0,
        4.0: 32.0,
        6.0: 41.0,
        10.0: 57.0,
        16.0: 76.0,
        25.0: 101.0,
        35.0: 125.0,
        50.0: 151.0,
        70.0: 192.0,
    },
    "B2": {
        1.5: 16.5,
        2.5: 23.0,
        4.0: 30.0,
        6.0: 38.0,
        10.0: 52.0,
        16.0: 69.0,
        25.0: 90.0,
        35.0: 111.0,
        50.0: 133.0,
        70.0: 168.0,
    },
}

FATOR_AGRUPAMENTO_REFERENCIA = {
    1: 1.00,
    2: 0.80,
    3: 0.70,
    4: 0.65,
    5: 0.60,
    6: 0.57,
    7: 0.54,
    8: 0.52,
    9: 0.50,
    10: 0.48,
    11: 0.47,
    12: 0.45,
}

FATOR_TEMPERATURA_PVC = {
    25: 1.03,
    30: 1.00,
    35: 0.94,
    40: 0.87,
    45: 0.79,
    50: 0.71,
    55: 0.61,
    60: 0.50,
}


def _fator_agrupamento_preliminar(qtd_circuitos):
    qtd = max(1, int(qtd_circuitos or 1))
    if qtd in FATOR_AGRUPAMENTO_REFERENCIA:
        return FATOR_AGRUPAMENTO_REFERENCIA[qtd]
    return FATOR_AGRUPAMENTO_REFERENCIA[max(FATOR_AGRUPAMENTO_REFERENCIA)]


def _fator_temperatura_preliminar(temperatura_c):
    temp = int(round(float(temperatura_c or 30)))
    chaves = sorted(FATOR_TEMPERATURA_PVC)
    mais_proxima = min(chaves, key=lambda x: abs(x - temp))
    return FATOR_TEMPERATURA_PVC[mais_proxima], mais_proxima


def _secao_recomendada_capacidade(
    corrente_a,
    metodo_instalacao,
    fator_agrupamento,
    fator_temperatura,
    secao_minima
):
    tabela = CAPACIDADE_REFERENCIA_A.get(
        metodo_instalacao,
        CAPACIDADE_REFERENCIA_A["B1"]
    )

    secoes = sorted(tabela)

    for secao in secoes:
        if secao < float(secao_minima or 0):
            continue

        iz_corrigida = (
            float(tabela[secao])
            * float(fator_agrupamento)
            * float(fator_temperatura)
        )

        if iz_corrigida + 1e-9 >= float(corrente_a or 0):
            return float(secao), float(iz_corrigida)

    ultima = float(secoes[-1])
    iz_ultima = (
        float(tabela[ultima])
        * float(fator_agrupamento)
        * float(fator_temperatura)
    )
    return ultima, float(iz_ultima)


def verificar_capacidade_conducao_preliminar(
    diagnostico_agrupamento,
    circuitos,
    metodo_instalacao="B1",
    temperatura_ambiente_c=30
):
    """Fase 13.6 Rev.13: verifica a capacidade trecho a trecho e identifica o trecho crítico."""
    metodo = str(metodo_instalacao or "B1").upper().strip()
    if metodo not in CAPACIDADE_REFERENCIA_A:
        metodo = "B1"

    fator_temp, temp_ref = _fator_temperatura_preliminar(
        temperatura_ambiente_c
    )
    tabela = CAPACIDADE_REFERENCIA_A[metodo]

    circuitos_por_numero = {
        int(c.get("numero", 0) or 0): c
        for c in (circuitos or [])
        if int(c.get("numero", 0) or 0) > 0
    }

    resultados_trechos = []
    for trecho in ((diagnostico_agrupamento or {}).get("trechos", []) or []):
        numeros = [
            int(n)
            for n in (trecho.get("circuitos", []) or [])
            if int(n) > 0
        ]
        qtd = max(
            1,
            int(
                trecho.get("qtd_circuitos", len(numeros))
                or len(numeros)
                or 1
            )
        )
        fator_agr = _fator_agrupamento_preliminar(qtd)

        for numero in numeros:
            circuito = circuitos_por_numero.get(numero)
            if not circuito:
                continue

            corrente = _numero(circuito.get("corrente", 0.0))
            bitola = _bitola(circuito)
            iz_base = float(tabela.get(bitola, 0.0) or 0.0)
            iz_corrigida = iz_base * fator_agr * fator_temp

            if iz_base <= 0:
                status = "SEM REFERÊNCIA"
            elif iz_corrigida + 1e-9 >= corrente:
                status = "OK"
            else:
                status = "ATENÇÃO"

            resultados_trechos.append({
                "trecho_id": trecho.get("trecho_id"),
                "numero": numero,
                "tipo": circuito.get("tipo", ""),
                "ambiente": circuito.get("ambiente", ""),
                "comprimento_trecho_m": round(
                    _numero(trecho.get("comprimento_m", 0.0)),
                    2
                ),
                "qtd_circuitos_agrupados": qtd,
                "fator_agrupamento": round(fator_agr, 3),
                "fator_temperatura": round(fator_temp, 3),
                "corrente_a": round(corrente, 2),
                "bitola_atual_mm2": bitola,
                "iz_base_a": round(iz_base, 2),
                "iz_corrigida_a": round(iz_corrigida, 2),
                "status": status,
            })

    resultados = []
    alertas = 0

    for numero in sorted(circuitos_por_numero):
        circuito = circuitos_por_numero[numero]
        corrente = _numero(circuito.get("corrente", 0.0))
        bitola = _bitola(circuito)

        trechos_circuito = [
            t for t in resultados_trechos
            if int(t.get("numero", 0) or 0) == numero
        ]

        if trechos_circuito:
            trecho_critico = min(
                trechos_circuito,
                key=lambda t: float(t.get("iz_corrigida_a", 0.0) or 0.0)
            )
            fator_agr = float(trecho_critico.get("fator_agrupamento", 1.0) or 1.0)
            iz_base = float(trecho_critico.get("iz_base_a", 0.0) or 0.0)
            iz_corrigida = float(trecho_critico.get("iz_corrigida_a", 0.0) or 0.0)
        else:
            fator_agr = 1.0
            iz_base = float(tabela.get(bitola, 0.0) or 0.0)
            iz_corrigida = iz_base * fator_temp
            trecho_critico = {
                "trecho_id": None,
                "comprimento_trecho_m": 0.0,
                "qtd_circuitos_agrupados": 1,
            }

        secao_rec, iz_rec = _secao_recomendada_capacidade(
            corrente_a=corrente,
            metodo_instalacao=metodo,
            fator_agrupamento=fator_agr,
            fator_temperatura=fator_temp,
            secao_minima=bitola,
        )

        if iz_base <= 0:
            status = "SEM REFERÊNCIA"
        elif iz_corrigida + 1e-9 >= corrente:
            status = "OK"
        else:
            status = "ATENÇÃO"
            alertas += 1

        resultados.append({
            "numero": numero,
            "tipo": circuito.get("tipo", ""),
            "ambiente": circuito.get("ambiente", ""),
            "corrente_a": round(corrente, 2),
            "bitola_atual_mm2": bitola,
            "metodo_instalacao": metodo,
            "temperatura_ref_c": temp_ref,
            "trecho_critico_id": trecho_critico.get("trecho_id"),
            "comprimento_trecho_critico_m": round(
                _numero(trecho_critico.get("comprimento_trecho_m", 0.0)),
                2
            ),
            "qtd_circuitos_agrupados": max(
                1,
                int(trecho_critico.get("qtd_circuitos_agrupados", 1) or 1)
            ),
            "fator_agrupamento": round(fator_agr, 3),
            "fator_temperatura": round(fator_temp, 3),
            "iz_base_a": round(iz_base, 2),
            "iz_corrigida_a": round(iz_corrigida, 2),
            "bitola_recomendada_mm2": round(secao_rec, 2),
            "iz_recomendada_a": round(iz_rec, 2),
            "status": status,
        })

    return {
        "status": "alerta" if alertas else "ok",
        "metodo_instalacao": metodo,
        "temperatura_ambiente_c": float(temperatura_ambiente_c or 30),
        "temperatura_referencia_c": temp_ref,
        "fator_temperatura": round(fator_temp, 3),
        "qtd_alertas": alertas,
        "circuitos": resultados,
        "trechos": resultados_trechos,
        "criterio_governante": (
            "Menor Iz corrigida entre os trechos físicos em que "
            "cada circuito realmente passa."
        ),
        "observacao": (
            "Verificação preliminar trecho a trecho para cobre/PVC 70 °C. "
            "A bitola não é alterada automaticamente nesta fase."
        ),
    }


# ============================================================
# FASE 13.6 REV.1 — OTIMIZAÇÃO PRELIMINAR DE ELETRODUTOS
# ============================================================

def _dados_eletroduto_nominal(nominal):
    for nom, interno in ELETRODUTOS_MM:
        if int(nom) == int(nominal or 0):
            return int(nom), float(interno)
    return None, None


def _ocupacao_para_condutores(condutores, nominal):
    nom, interno = _dados_eletroduto_nominal(nominal)
    if not nom or not interno:
        return None

    area_cond = sum(
        _area_ocupada_condutor(
            c.get("bitola_mm2", 0)
        )
        for c in (condutores or [])
    )
    area_int = math.pi * interno * interno / 4.0
    if area_int <= 0:
        return None
    return 100.0 * area_cond / area_int


def _proximo_eletroduto_nominal(
    atual,
    max_nominal_mm=25
):
    atuais = [
        int(n)
        for n, _ in ELETRODUTOS_MM
        if int(n) <= int(max_nominal_mm)
    ]
    try:
        i = atuais.index(int(atual))
    except Exception:
        return atuais[0] if atuais else None
    return atuais[i + 1] if i + 1 < len(atuais) else None


def _condutores_por_circuito_trecho(rota):
    por = {}
    for c in (rota.get("condutores", []) or []):
        num = int(c.get("circuito", 0) or 0)
        if num <= 0:
            continue
        por.setdefault(num, []).append(dict(c))
    return por


def _dividir_circuitos_balanceado(rota):
    """
    Divide os circuitos do trecho em dois grupos tentando equilibrar
    a área externa total dos condutores. É uma simulação de infraestrutura,
    não um novo traçado CAD nesta fase.
    """
    por = _condutores_por_circuito_trecho(rota)

    itens = []
    for numero, conds in por.items():
        area = sum(
            _area_ocupada_condutor(c.get("bitola_mm2", 0))
            for c in conds
        )
        itens.append((numero, area, conds))

    itens.sort(key=lambda x: x[1], reverse=True)

    grupos = [
        {"circuitos": [], "condutores": [], "area": 0.0},
        {"circuitos": [], "condutores": [], "area": 0.0},
    ]

    for numero, area, conds in itens:
        alvo = 0 if grupos[0]["area"] <= grupos[1]["area"] else 1
        grupos[alvo]["circuitos"].append(numero)
        grupos[alvo]["condutores"].extend(conds)
        grupos[alvo]["area"] += area

    return grupos


def otimizar_eletrodutos_preliminar(
    resumo_rotas,
    limite_ocupacao_pct=40.0,
    limite_circuitos_preferencial=3
):
    """
    Fase 13.6 Rev.13.

    Para cada trecho físico compara três estratégias:
    1) MANTER o eletroduto atual;
    2) AUMENTAR para o próximo diâmetro nominal;
    3) DIVIDIR os circuitos em dois eletrodutos paralelos simulados.

    A escolha recomendada prioriza:
    - respeitar a ocupação geométrica;
    - reduzir agrupamento quando houver concentração elevada;
    - evitar aumento desnecessário de bitola dos condutores.

    IMPORTANTE:
    a opção DIVIDIR é somente uma recomendação/simulação nesta fase.
    O sistema ainda não redesenha automaticamente uma segunda rota no CAD.
    """
    rotas = (
        resumo_rotas.get("rotas", [])
        if isinstance(resumo_rotas, dict)
        else []
    ) or []

    resultados = []
    qtd_dividir = 0
    qtd_aumentar = 0
    qtd_manter = 0

    for rota in rotas:
        condutores = list(rota.get("condutores", []) or [])
        circuitos = sorted(set(
            int(n)
            for n in (rota.get("circuitos", []) or [])
            if int(n) > 0
        ))

        atual = rota.get("diametro_eletroduto_mm")
        ocup_atual = float(rota.get("ocupacao_pct", 0.0) or 0.0)
        qtd_circ = len(circuitos)

        if not condutores or not atual:
            resultados.append({
                "trecho_id": rota.get("trecho_id"),
                "comprimento_m": round(_numero(rota.get("comprimento_m", 0.0)), 2),
                "circuitos": circuitos,
                "qtd_circuitos": qtd_circ,
                "eletroduto_atual_mm": atual,
                "ocupacao_atual_pct": round(ocup_atual, 1),
                "recomendacao": "SEM DADOS",
                "justificativa": "Trecho sem dados suficientes de condutores/eletroduto.",
            })
            continue

        proximo = _proximo_eletroduto_nominal(
            atual,
            max_nominal_mm=25
        )
        ocup_proximo = (
            _ocupacao_para_condutores(condutores, proximo)
            if proximo
            else None
        )

        grupos = _dividir_circuitos_balanceado(rota)
        simulacao_grupos = []

        for idx, grupo in enumerate(grupos, start=1):
            if not grupo["condutores"]:
                continue
            dim = _eletroduto_por_ocupacao(
                grupo["condutores"],
                max_nominal_mm=25
            )
            simulacao_grupos.append({
                "grupo": idx,
                "circuitos": sorted(grupo["circuitos"]),
                "qtd_circuitos": len(grupo["circuitos"]),
                "eletroduto_mm": dim.get("diametro_nominal_mm"),
                "ocupacao_pct": round(float(dim.get("ocupacao_pct", 0.0) or 0.0), 1),
            })

        max_circ_div = max(
            [g["qtd_circuitos"] for g in simulacao_grupos] or [0]
        )
        max_ocup_div = max(
            [g["ocupacao_pct"] for g in simulacao_grupos] or [0.0]
        )

        # Decisão preliminar de projeto.
        # 1) Se ocupação já ultrapassa o limite, primeiro verifica aumento simples.
        # 2) Se há concentração alta de circuitos, prioriza dividir,
        #    pois aumentar somente o diâmetro não reduz a quantidade agrupada.
        if ocup_atual > float(limite_ocupacao_pct or 40.0):
            if proximo and ocup_proximo is not None and ocup_proximo <= limite_ocupacao_pct:
                recomendacao = "AUMENTAR ELETRODUTO"
                justificativa = (
                    f"Ocupação atual de {ocup_atual:.1f}% excede o limite "
                    f"preliminar de {limite_ocupacao_pct:.0f}%. O próximo "
                    f"diâmetro reduz para aproximadamente {ocup_proximo:.1f}%."
                )
                qtd_aumentar += 1
            else:
                recomendacao = "NOVO CAMINHO VIA CAIXA"
                justificativa = (
                    "O eletroduto terminal atingiu o limite de Ø25 mm ou a ocupação "
                    "permanece crítica. O sistema deve procurar outra caixa octogonal "
                    "de iluminação com entrada disponível para criar um caminho alternativo."
                )
                qtd_dividir += 1
        else:
            recomendacao = "MANTER"
            justificativa = (
                f"Ocupação de {ocup_atual:.1f}% e {qtd_circ} circuito(s) "
                "não acionam a otimização preliminar deste trecho."
            )
            qtd_manter += 1

        resultados.append({
            "trecho_id": rota.get("trecho_id"),
            "comprimento_m": round(_numero(rota.get("comprimento_m", 0.0)), 2),
            "circuitos": circuitos,
            "qtd_circuitos": qtd_circ,
            "qtd_condutores": int(rota.get("qtd_condutores", 0) or 0),
            "eletroduto_atual_mm": int(atual) if atual else None,
            "ocupacao_atual_pct": round(ocup_atual, 1),
            "proximo_eletroduto_mm": proximo,
            "ocupacao_proximo_pct": (
                round(float(ocup_proximo), 1)
                if ocup_proximo is not None
                else None
            ),
            "divisao_grupos": simulacao_grupos,
            "max_circuitos_apos_divisao": max_circ_div,
            "max_ocupacao_apos_divisao_pct": round(max_ocup_div, 1),
            "recomendacao": recomendacao,
            "justificativa": justificativa,
        })

    return {
        "status": "simulacao",
        "limite_ocupacao_pct": float(limite_ocupacao_pct),
        "limite_circuitos_preferencial": None,
        "qtd_manter": qtd_manter,
        "qtd_aumentar": qtd_aumentar,
        "qtd_dividir": qtd_dividir,
        "trechos": resultados,
        "observacao": (
            "Simulação de infraestrutura. 'NOVO CAMINHO VIA CAIXA' indica "
            "redistribuição por outra caixa octogonal; a Fase 13.6 Rev.13 também passa "
            "a reduzir a concentração já na formação da rede troncal."
        ),
    }


# ============================================================
# FASE 13.6 REV.1 — CORREÇÃO AUTOMÁTICA POR CAPACIDADE DE CONDUÇÃO
# ============================================================

def corrigir_bitolas_por_capacidade(
    diagnostico_agrupamento,
    circuitos,
    metodo_instalacao="B1",
    temperatura_ambiente_c=30
):
    """
    Eleva automaticamente a seção quando a capacidade de condução
    corrigida fica abaixo da corrente de projeto.

    Usa o trecho físico governante de cada circuito, já considerando
    agrupamento real da rota e temperatura selecionada.

    Não reduz seção existente.
    Não altera o disjuntor.
    """
    corrigidos = [
        dict(c)
        for c in (
            circuitos
            or []
        )
    ]

    verificacao = (
        verificar_capacidade_conducao_preliminar(
            diagnostico_agrupamento,
            corrigidos,
            metodo_instalacao=metodo_instalacao,
            temperatura_ambiente_c=temperatura_ambiente_c,
        )
    )

    por_numero = {
        int(item.get("numero", 0) or 0): item
        for item in (
            verificacao.get(
                "circuitos",
                []
            )
            or []
        )
        if int(item.get("numero", 0) or 0) > 0
    }

    relatorio = []

    for circuito in corrigidos:
        numero = int(
            circuito.get(
                "numero",
                0
            )
            or 0
        )

        if numero <= 0:
            continue

        item = por_numero.get(
            numero,
            {}
        )

        original = _bitola(
            circuito
        )

        ib = _numero(
            item.get(
                "corrente_a",
                circuito.get(
                    "corrente",
                    0.0
                )
            )
        )

        in_a = _numero(
            circuito.get(
                "disjuntor",
                0.0
            )
        )

        corrente_dimensionamento = max(
            ib,
            in_a
        )

        fator_agr = _numero(
            item.get(
                "fator_agrupamento",
                1.0
            ),
            1.0
        )

        fator_temp = _numero(
            item.get(
                "fator_temperatura",
                1.0
            ),
            1.0
        )

        recomendada, iz_recomendada = (
            _secao_recomendada_capacidade(
                corrente_a=corrente_dimensionamento,
                metodo_instalacao=str(
                    item.get(
                        "metodo_instalacao",
                        metodo_instalacao
                    )
                    or metodo_instalacao
                ),
                fator_agrupamento=fator_agr,
                fator_temperatura=fator_temp,
                secao_minima=original,
            )
        )

        final = max(
            original,
            recomendada
        )

        status_original = str(
            item.get(
                "status",
                "SEM REFERÊNCIA"
            )
            or "SEM REFERÊNCIA"
        )

        status = (
            "CORRIGIDA"
            if final > original + 1e-9
            else (
                "MANTIDA"
                if status_original == "OK"
                else status_original
            )
        )

        if final > original + 1e-9:
            circuito[
                "bitola"
            ] = final

            circuito[
                "bitola_antes_capacidade"
            ] = original

            circuito[
                "criterio_bitola"
            ] = (
                "Seção elevada automaticamente por capacidade de condução"
            )

        relatorio.append({
            "numero":
                numero,
            "tipo":
                circuito.get(
                    "tipo",
                    ""
                ),
            "ambiente":
                circuito.get(
                    "ambiente",
                    ""
                ),
            "corrente_a":
                round(
                    ib,
                    2
                ),
            "disjuntor_a":
                round(
                    in_a,
                    2
                ),
            "corrente_dimensionamento_a":
                round(
                    corrente_dimensionamento,
                    2
                ),
            "bitola_original_mm2":
                original,
            "bitola_final_mm2":
                final,
            "trecho_critico_id":
                item.get(
                    "trecho_critico_id"
                ),
            "comprimento_trecho_critico_m":
                item.get(
                    "comprimento_trecho_critico_m"
                ),
            "qtd_circuitos_agrupados":
                item.get(
                    "qtd_circuitos_agrupados"
                ),
            "fator_agrupamento":
                item.get(
                    "fator_agrupamento"
                ),
            "fator_temperatura":
                item.get(
                    "fator_temperatura"
                ),
            "iz_antes_a":
                item.get(
                    "iz_corrigida_a"
                ),
            "iz_recomendada_a":
                round(
                    iz_recomendada,
                    2
                ),
            "metodo_instalacao":
                item.get(
                    "metodo_instalacao",
                    metodo_instalacao
                ),
            "temperatura_ref_c":
                item.get(
                    "temperatura_ref_c",
                    temperatura_ambiente_c
                ),
            "status":
                status,
        })

    return (
        corrigidos,
        relatorio
    )


def validar_relacao_ib_in_iz(
    capacidade,
    circuitos
):
    """
    Valida a relação preliminar:
        Ib <= In <= Iz

    Ib = corrente de projeto
    In = disjuntor nominal
    Iz = capacidade corrigida do condutor no trecho governante
    """
    capacidade_por_numero = {
        int(item.get("numero", 0) or 0): item
        for item in (
            (capacidade or {}).get(
                "circuitos",
                []
            )
            or []
        )
        if int(item.get("numero", 0) or 0) > 0
    }

    resultados = []
    alertas = 0

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

        cap = capacidade_por_numero.get(
            numero,
            {}
        )

        ib = _numero(
            circuito.get(
                "corrente",
                cap.get(
                    "corrente_a",
                    0.0
                )
            )
        )

        in_a = _numero(
            circuito.get(
                "disjuntor",
                0.0
            )
        )

        iz = _numero(
            cap.get(
                "iz_corrigida_a",
                0.0
            )
        )

        if iz <= 0 or in_a <= 0:
            status = "PENDENTE"
        elif (
            ib <= in_a + 1e-9
            and in_a <= iz + 1e-9
        ):
            status = "OK"
        else:
            status = "ATENÇÃO"
            alertas += 1

        resultados.append({
            "numero":
                numero,
            "tipo":
                circuito.get(
                    "tipo",
                    ""
                ),
            "ambiente":
                circuito.get(
                    "ambiente",
                    ""
                ),
            "ib_a":
                round(
                    ib,
                    2
                ),
            "in_a":
                round(
                    in_a,
                    2
                ),
            "iz_a":
                round(
                    iz,
                    2
                ),
            "bitola_mm2":
                _bitola(
                    circuito
                ),
            "status":
                status,
        })

    return {
        "status":
            (
                "alerta"
                if alertas
                else "ok"
            ),
        "qtd_alertas":
            alertas,
        "circuitos":
            resultados,
        "criterio":
            "Ib <= In <= Iz",
    }
