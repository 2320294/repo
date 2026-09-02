import math
from io import BytesIO

import pandas as pd
import streamlit as st

from concessionarias import CHAVE_PARAMETROS_REDE
from balanceamento_fases import balancear_circuitos
from agrupamento_dr import agrupar_circuitos_dr
from demanda_qdc import calcular_demanda_qdc
from protecao_alimentador import avaliar_protecoes_alimentador
from tensoes_circuitos import tensao_circuito, tensao_base_fornecimento
from formacao_circuitos import formar_circuitos_definitivos

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)


# ============================================================
# PREMISSAS DE PROJETO
# ============================================================
#
# IMPORTANTE:
# A NBR 5410 exige que o dimensionamento final considere,
# entre outros fatores, corrente de projeto, método de
# instalação, capacidade de condução de corrente, agrupamento,
# temperatura, queda de tensão e proteção.
#
# Enquanto o CAD ainda não possui o traçado completo dos
# eletrodutos/circuitos, os COMPRIMENTOS abaixo são estimados
# geometricamente a partir dos centros dos ambientes e do QDC.
#
# A quantidade de pontos/caixas é calculada diretamente do
# projeto.
# ============================================================

# Tensões agora vêm dos parâmetros do projeto

FOLGA_CABOS = 1.15
FOLGA_ELETRODUTO = 1.10


from qdc_config import ambiente_qdc

def _numero(valor, padrao=0):
    try:
        return float(valor)
    except Exception:
        return float(padrao)


def _inteiro(valor, padrao=0):
    try:
        return int(valor)
    except Exception:
        return int(padrao)


def _potencia_w(row, campo_w, campo_va, padrao=0):
    if campo_w in row:
        return _numero(
            row.get(
                campo_w,
                padrao
            )
        )

    if campo_va in row:
        # Compatibilidade com projetos antigos.
        # Enquanto não houver FP individual cadastrado,
        # considera FP = 1,0.
        return _numero(
            row.get(
                campo_va,
                padrao
            )
        )

    return _numero(padrao)


def _centro_qdc(
    tabela_editada,
    local_qdc
):
    if not local_qdc:
        return None

    alvo = str(
        ambiente_qdc(
            local_qdc
        )
    ).strip().casefold()

    for row in tabela_editada:
        if (
            str(
                row.get(
                    "Ambiente",
                    ""
                )
            ).strip().casefold()
            ==
            alvo
        ):
            return (
                _numero(
                    row.get(
                        "Centro_X",
                        0
                    )
                ),
                _numero(
                    row.get(
                        "Centro_Y",
                        0
                    )
                )
            )

    return None


def _distancia_qdc_ambiente(
    row,
    centro_qdc
):
    if centro_qdc is None:
        # Quando não existe geometria do QDC disponível,
        # usa uma estimativa ligada ao tamanho do ambiente.
        return max(
            2.0,
            _numero(
                row.get(
                    "Perímetro (m)",
                    0
                )
            ) / 4
        )

    cx = _numero(
        row.get(
            "Centro_X",
            0
        )
    )

    cy = _numero(
        row.get(
            "Centro_Y",
            0
        )
    )

    # Distância Manhattan é mais coerente do que distância
    # reta para uma estimativa inicial de encaminhamento
    # ortogonal em planta.
    return (
        abs(
            cx - centro_qdc[0]
        )
        +
        abs(
            cy - centro_qdc[1]
        )
    )


def _bitola_tue(
    potencia_w,
    tensao=220
):
    """
    Seleção preliminar/conservadora para circuito TUE.

    O dimensionamento definitivo deve posteriormente verificar:
    capacidade de condução, método de instalação,
    agrupamento, temperatura e queda de tensão.
    """
    if potencia_w <= 0:
        return 2.5

    corrente = (
        potencia_w
        /
        max(
            tensao,
            1
        )
    )

    if corrente <= 16:
        return 2.5

    if corrente <= 25:
        return 4.0

    if corrente <= 36:
        return 6.0

    if corrente <= 50:
        return 10.0

    if corrente <= 63:
        return 16.0

    return 25.0


def _disjuntor_por_corrente(
    corrente
):
    valores = [
        6,
        10,
        16,
        20,
        25,
        32,
        40,
        50,
        63
    ]

    for valor in valores:
        if corrente <= valor:
            return valor

    return 63


def _comprimento_estimado_circuito(
    row,
    centro_qdc,
    adicional_ambiente=0.0,
    pe_direito=2.80
):
    distancia = (
        _distancia_qdc_ambiente(
            row,
            centro_qdc
        )
    )

    perimetro = _numero(
        row.get(
            "Perímetro (m)",
            0
        )
    )

    # Acrescenta uma subida/descida vertical aproximada.
    adicional_vertical = max(
        0.0,
        pe_direito - 1.10
    )

    return max(
        1.0,
        distancia
        +
        adicional_ambiente
        +
        perimetro * 0.25
        +
        adicional_vertical
    )


def _adicionar_material(
    materiais,
    categoria,
    material,
    especificacao,
    unidade,
    quantidade,
    criterio
):
    if quantidade is None:
        return

    if isinstance(
        quantidade,
        float
    ):
        quantidade = round(
            quantidade,
            1
        )

    materiais.append({
        "Categoria": categoria,
        "Material": material,
        "Especificação": especificacao,
        "Unidade": unidade,
        "Quantidade": quantidade,
        "Critério": criterio
    })


def calcular_quantitativo_materiais(
    tabela_editada,
    config_interruptores_usuario,
    local_qdc=None,
    tensao_projeto=110,
    pe_direito=2.80
):
    materiais = []

    tensao_projeto = int(
        tensao_projeto
        if tensao_projeto in [110, 220]
        else 110
    )

    pe_direito = max(
        2.0,
        float(pe_direito)
    )

    centro_qdc = _centro_qdc(
        tabela_editada,
        local_qdc
    )

    parametros_rede_calculo = (
        (config_interruptores_usuario or {}).get(
            CHAVE_PARAMETROS_REDE,
            {}
        )
    )

    tensao_base = tensao_base_fornecimento(
        parametros_rede_calculo,
        fallback=tensao_projeto
    )

    # ========================================================
    # PONTOS / CAIXAS / ACESSÓRIOS
    # ========================================================

    total_iluminacao = sum(
        _inteiro(
            r.get(
                "Qtd Ilum.",
                0
            )
        )
        for r in tabela_editada
    )

    total_tug = sum(
        _inteiro(
            r.get(
                "Qtd TUG",
                r.get(
                    "TUGs (Qtd)",
                    0
                )
            )
        )
        for r in tabela_editada
    )

    total_tue = sum(
        _inteiro(
            r.get(
                "Qtd TUE",
                0
            )
        )
        for r in tabela_editada
    )

    total_interruptores = sum(
        _inteiro(
            cfg.get(
                "quantidade",
                0
            )
        )
        for chave_cfg, cfg
        in config_interruptores_usuario.items()
        if (
            not str(
                chave_cfg
            ).startswith("__")
            and isinstance(
                cfg,
                dict
            )
        )
    )

    _adicionar_material(
        materiais,
        "Caixas",
        "Caixa octogonal de teto",
        '4x4" — ponto de iluminação',
        "pç",
        total_iluminacao,
        "1 por ponto de iluminação"
    )

    _adicionar_material(
        materiais,
        "Caixas",
        "Caixa de embutir",
        '4x2" — tomadas TUG',
        "pç",
        total_tug,
        "1 por TUG"
    )

    _adicionar_material(
        materiais,
        "Caixas",
        "Caixa de embutir",
        '4x2" — tomadas/equipamentos TUE',
        "pç",
        total_tue,
        "1 por TUE"
    )

    _adicionar_material(
        materiais,
        "Caixas",
        "Caixa de embutir",
        '4x2" — interruptores',
        "pç",
        total_interruptores,
        "1 por interruptor"
    )

    # Caixa de passagem: estimativa preliminar
    # 1 por ambiente com pontos elétricos + 1 junto ao QDC.
    ambientes_com_pontos = sum(
        1
        for r in tabela_editada
        if (
            _inteiro(
                r.get(
                    "Qtd Ilum.",
                    0
                )
            )
            +
            _inteiro(
                r.get(
                    "Qtd TUG",
                    r.get(
                        "TUGs (Qtd)",
                        0
                    )
                )
            )
            +
            _inteiro(
                r.get(
                    "Qtd TUE",
                    0
                )
            )
            > 0
        )
    )

    _adicionar_material(
        materiais,
        "Caixas",
        "Caixa de passagem",
        '4x4" ou dimensão compatível',
        "pç",
        max(
            1,
            ambientes_com_pontos + 1
        ),
        "Estimativa preliminar; confirmar no traçado dos eletrodutos"
    )

    _adicionar_material(
        materiais,
        "Tomadas",
        "Tomada TUG",
        "2P+T 10 A",
        "pç",
        total_tug,
        "Quantidade de TUGs do quadro de cargas"
    )

    _adicionar_material(
        materiais,
        "Tomadas",
        "Tomada TUE",
        "2P+T 20 A ou conexão específica",
        "pç",
        total_tue,
        "Quantidade de TUEs; especificação final depende do equipamento"
    )

    _adicionar_material(
        materiais,
        "Comandos",
        "Interruptor",
        "Módulo simples/paralelo conforme comando",
        "pç",
        total_interruptores,
        "Configuração escolhida por ambiente"
    )

    # ========================================================
    # CIRCUITOS E CABOS
    # ========================================================

    comprimentos_por_bitola = {}
    comprimentos_cabos_cor = {}
    eletroduto_total = 0.0
    circuitos_elementares = []

    def acumular_cabo_cor(
        bitola,
        funcao,
        cor,
        comprimento
    ):
        chave = (
            float(bitola),
            str(funcao),
            str(cor)
        )
        comprimentos_cabos_cor[
            chave
        ] = (
            comprimentos_cabos_cor.get(
                chave,
                0.0
            )
            +
            float(comprimento)
        )

    for row in tabela_editada:
        ambiente = str(
            row.get(
                "Ambiente",
                ""
            )
        )

        qtd_ilum = _inteiro(
            row.get(
                "Qtd Ilum.",
                0
            )
        )

        pot_ilum_unit = _potencia_w(
            row,
            "Pot. Unit. Ilum (W)",
            "Pot. Unit. Ilum (VA)",
            0
        )

        qtd_tug = _inteiro(
            row.get(
                "Qtd TUG",
                row.get(
                    "TUGs (Qtd)",
                    0
                )
            )
        )

        pot_tug_unit = _potencia_w(
            row,
            "Pot. Unit. TUG (W)",
            "Pot. Unit. TUG (VA)",
            0
        )

        qtd_tue = _inteiro(
            row.get(
                "Qtd TUE",
                0
            )
        )

        pot_tue_unit = _potencia_w(
            row,
            "Pot. Unit. TUE (W)",
            "Pot. Unit. TUE (VA)",
            0
        )

        # ----------------------------------------------------
        # ILUMINAÇÃO
        # ----------------------------------------------------

        if qtd_ilum > 0:
            potencia = (
                qtd_ilum
                *
                pot_ilum_unit
            )

            comprimento = (
                _comprimento_estimado_circuito(
                    row,
                    centro_qdc,
                    adicional_ambiente=1.5,
                    pe_direito=pe_direito
                )
            )

            eletroduto_total += comprimento

            # fase + neutro + PE
            cabo = (
                comprimento
                *
                3
                *
                FOLGA_CABOS
            )

            comprimentos_por_bitola[
                1.5
            ] = (
                comprimentos_por_bitola.get(
                    1.5,
                    0.0
                )
                +
                cabo
            )

            comprimento_condutor = (
                comprimento
                *
                FOLGA_CABOS
            )
            acumular_cabo_cor(
                1.5,
                "Fase",
                "Vermelho",
                comprimento_condutor
            )
            acumular_cabo_cor(
                1.5,
                "Neutro",
                "Azul-claro",
                comprimento_condutor
            )
            acumular_cabo_cor(
                1.5,
                "Proteção (PE)",
                "Verde ou verde/amarelo",
                comprimento_condutor
            )

            tensao_circ = tensao_circuito(
                "Iluminação",
                parametros_rede_calculo,
                fallback=tensao_base
            )

            corrente = (
                potencia
                /
                tensao_circ
                if tensao_circ
                else 0
            )

            circuitos_elementares.append({
                "tipo": "Iluminação",
                "ambiente": ambiente,
                "potencia": potencia,
                "tensao": tensao_circ,
                "corrente": corrente,
                "bitola": 1.5,
                "disjuntor":
                    _disjuntor_por_corrente(
                        corrente
                    )
            })

        # ----------------------------------------------------
        # TUG
        # ----------------------------------------------------

        if qtd_tug > 0:
            potencia = (
                qtd_tug
                *
                pot_tug_unit
            )

            comprimento = (
                _comprimento_estimado_circuito(
                    row,
                    centro_qdc,
                    adicional_ambiente=2.0,
                    pe_direito=pe_direito
                )
            )

            eletroduto_total += comprimento

            cabo = (
                comprimento
                *
                3
                *
                FOLGA_CABOS
            )

            comprimentos_por_bitola[
                2.5
            ] = (
                comprimentos_por_bitola.get(
                    2.5,
                    0.0
                )
                +
                cabo
            )

            comprimento_condutor = (
                comprimento
                *
                FOLGA_CABOS
            )
            acumular_cabo_cor(
                2.5,
                "Fase",
                "Vermelho",
                comprimento_condutor
            )
            acumular_cabo_cor(
                2.5,
                "Neutro",
                "Azul-claro",
                comprimento_condutor
            )
            acumular_cabo_cor(
                2.5,
                "Proteção (PE)",
                "Verde ou verde/amarelo",
                comprimento_condutor
            )

            tensao_circ = tensao_circuito(
                "TUG",
                parametros_rede_calculo,
                fallback=tensao_base
            )

            corrente = (
                potencia
                /
                tensao_circ
                if tensao_circ
                else 0
            )

            circuitos_elementares.append({
                "tipo": "TUG",
                "ambiente": ambiente,
                "potencia": potencia,
                "tensao": tensao_circ,
                "corrente": corrente,
                "bitola": 2.5,
                "disjuntor":
                    _disjuntor_por_corrente(
                        corrente
                    )
            })

        # ----------------------------------------------------
        # TUE
        # ----------------------------------------------------

        for indice in range(
            qtd_tue
        ):
            potencia = (
                pot_tue_unit
            )

            tensao_circ = tensao_circuito(
                "TUE",
                parametros_rede_calculo,
                fallback=tensao_base
            )

            bitola = (
                _bitola_tue(
                    potencia,
                    tensao_circ
                )
            )

            comprimento = (
                _comprimento_estimado_circuito(
                    row,
                    centro_qdc,
                    adicional_ambiente=1.0,
                    pe_direito=pe_direito
                )
            )

            eletroduto_total += comprimento

            # 220 V bifásico: 2 fases + PE.
            cabo = (
                comprimento
                *
                3
                *
                FOLGA_CABOS
            )

            comprimentos_por_bitola[
                bitola
            ] = (
                comprimentos_por_bitola.get(
                    bitola,
                    0.0
                )
                +
                cabo
            )

            comprimento_condutor = (
                comprimento
                *
                FOLGA_CABOS
            )
            acumular_cabo_cor(
                bitola,
                "Fase L1",
                "Vermelho",
                comprimento_condutor
            )
            acumular_cabo_cor(
                bitola,
                "Fase L2",
                "Preto",
                comprimento_condutor
            )
            acumular_cabo_cor(
                bitola,
                "Proteção (PE)",
                "Verde ou verde/amarelo",
                comprimento_condutor
            )

            corrente = (
                potencia
                /
                tensao_circ
                if tensao_circ
                else 0
            )

            circuitos_elementares.append({
                "tipo": "TUE",
                "ambiente": ambiente,
                "potencia": potencia,
                "tensao": tensao_circ,
                "corrente": corrente,
                "bitola": bitola,
                "disjuntor":
                    _disjuntor_por_corrente(
                        corrente
                    )
            })

        # ========================================================
    # FASE 11.5 REV.1 — FORMAÇÃO DEFINITIVA DOS CIRCUITOS
    # ========================================================
    # A estimativa geométrica de cabos/eletrodutos continua baseada nas
    # cargas elementares por ambiente até a Fase 11.5 Rev.1/11.2, quando o
    # roteamento físico passará a fornecer os comprimentos reais.
    circuitos = formar_circuitos_definitivos(
        circuitos_elementares,
        _disjuntor_por_corrente
    )

# ========================================================
    # CABOS POR BITOLA, FUNÇÃO E COR
    # ========================================================

    for (
        bitola,
        funcao,
        cor
    ) in sorted(
        comprimentos_cabos_cor
    ):
        _adicionar_material(
            materiais,
            "Condutores",
            "Cabo de cobre isolado",
            (
                f"{bitola:g} mm² — "
                f"{funcao} — "
                f"{cor}"
            ),
            "m",
            math.ceil(
                comprimentos_cabos_cor[
                    (
                        bitola,
                        funcao,
                        cor
                    )
                ]
            ),
            (
                "Comprimento estimado pela geometria "
                "+ 15% de folga"
            )
        )

    # ========================================================
    # ELETRODUTOS
    # ========================================================

    _adicionar_material(
        materiais,
        "Infraestrutura",
        "Eletroduto corrugado flexível",
        '3/4" — distribuição interna',
        "m",
        math.ceil(
            eletroduto_total
            *
            FOLGA_ELETRODUTO
        ),
        "Comprimento estimado dos circuitos + 10% de folga"
    )

    # ========================================================
    # QUADRO E PROTEÇÕES
    # ========================================================

    numero_circuitos = len(
        circuitos
    )

    # reserva técnica de espaço no quadro
    modulos_estimados = (
        numero_circuitos
        +
        1     # geral
        +
        2     # IDR
        +
        2     # DPS / reserva mínima
    )

    tamanhos_qdc = [
        12,
        18,
        24,
        36,
        48
    ]

    tamanho_qdc = next(
        (
            x
            for x in tamanhos_qdc
            if x >= math.ceil(
                modulos_estimados * 1.20
            )
        ),
        48
    )

    _adicionar_material(
        materiais,
        "Quadro",
        "Quadro de distribuição",
        f"{tamanho_qdc} módulos DIN, com barramentos N e PE",
        "pç",
        1,
        "Quantidade de circuitos + proteções + reserva técnica"
    )

    _adicionar_material(
        materiais,
        "Quadro",
        "Barramento de neutro",
        "Compatível com QDC",
        "pç",
        1,
        "1 por quadro"
    )

    _adicionar_material(
        materiais,
        "Quadro",
        "Barramento de proteção PE",
        "Compatível com QDC",
        "pç",
        1,
        "1 por quadro"
    )

    # disjuntor geral:
    potencia_total = sum(
        c["potencia"]
        for c in circuitos
    )

    # estimativa simplificada com alimentação 220 V
    corrente_geral = (
        potencia_total
        /
        tensao_projeto
        if potencia_total > 0
        else 0
    )

    disjuntor_geral = (
        _disjuntor_por_corrente(
            corrente_geral
        )
    )

    _adicionar_material(
        materiais,
        "Proteção",
        "Disjuntor geral",
        f"{disjuntor_geral} A — curva e nº de polos a confirmar pela alimentação",
        "pç",
        1,
        "Pré-dimensionamento pela carga total; confirmar padrão de fornecimento"
    )

    # Disjuntores terminais agrupados por corrente
    contagem_disjuntores = {}

    for circuito in circuitos:
        chave = (
            circuito["disjuntor"],
            circuito["tipo"]
        )

        contagem_disjuntores[
            chave
        ] = (
            contagem_disjuntores.get(
                chave,
                0
            )
            +
            1
        )

    for (
        corrente_disj,
        tipo
    ), quantidade in sorted(
        contagem_disjuntores.items()
    ):
        polos = (
            "2P"
            if tipo == "TUE"
            else "1P"
        )

        _adicionar_material(
            materiais,
            "Proteção",
            "Disjuntor termomagnético",
            f"{polos} {corrente_disj} A — circuito {tipo}",
            "pç",
            quantidade,
            "Pré-dimensionado pela corrente da carga; verificar capacidade do condutor"
        )

    # DR
    _adicionar_material(
        materiais,
        "Proteção",
        "IDR / DR",
        "30 mA — corrente nominal compatível com o quadro",
        "pç",
        1,
        "Proteção adicional; circuitos aplicáveis devem ser definidos no esquema final"
    )

    # DPS
    _adicionar_material(
        materiais,
        "Proteção",
        "DPS",
        "Classe II — tensão compatível com o sistema",
        "pç",
        2,
        "Quantidade preliminar para sistema fase/fase ou fase/neutro; confirmar esquema de alimentação"
    )

    _adicionar_material(
        materiais,
        "Proteção",
        "Dispositivo de proteção do DPS",
        "Disjuntor/fusível de retaguarda conforme fabricante",
        "pç",
        1,
        "Dimensionar conforme DPS selecionado"
    )

    # ========================================================
    # ACESSÓRIOS DE MONTAGEM
    # ========================================================

    _adicionar_material(
        materiais,
        "Acessórios",
        "Conector de emenda",
        "Compatível com as bitolas dos circuitos",
        "pç",
        max(
            10,
            (
                total_iluminacao
                +
                total_tug
                +
                total_tue
                +
                total_interruptores
            ) * 2
        ),
        "Estimativa para derivações e terminações"
    )

    _adicionar_material(
        materiais,
        "Acessórios",
        "Terminal tubular / ilhós",
        "Bitolas variadas",
        "pç",
        max(
            20,
            numero_circuitos * 6
        ),
        "Estimativa para terminações no quadro"
    )

    _adicionar_material(
        materiais,
        "Acessórios",
        "Identificador de cabos/circuitos",
        "Etiquetas ou anilhas",
        "pç",
        max(
            1,
            numero_circuitos * 3
        ),
        "Identificação dos condutores e circuitos"
    )

    return materiais, circuitos



def _dataframes_materiais_circuitos(materiais, circuitos):
    materiais_df = pd.DataFrame(materiais)
    if not materiais_df.empty:
        materiais_df = materiais_df.sort_values(
            by=["Categoria", "Material", "Especificação"],
            kind="stable"
        ).reset_index(drop=True)

    circuitos_df = pd.DataFrame(circuitos)
    if not circuitos_df.empty:
        circuitos_df = circuitos_df.rename(columns={
            "numero": "Nº",
            "tipo": "Circuito",
            "ambiente": "Ambiente",
            "fase": "Fase(s)",
            "polos": "Polos",
            "dr": "DR",
            "criterio_formacao": "Critério de formação",
            "potencia": "Potência (W)",
            "tensao": "Tensão (V)",
            "corrente": "Corrente estimada (A)",
            "bitola": "Bitola preliminar (mm²)",
            "disjuntor": "Disjuntor preliminar (A)"
        })
        circuitos_df["Corrente estimada (A)"] = (
            circuitos_df["Corrente estimada (A)"].round(2)
        )
        if "Nº" in circuitos_df.columns:
            circuitos_df["Nº"] = circuitos_df["Nº"].apply(
                lambda valor: f"C{int(valor):02d}"
            )

        # Fase 11.5 Rev.1: dados estruturais usados pelo roteamento continuam
        # dentro dos circuitos em memória, mas não são expostos ao usuário.
        circuitos_df = circuitos_df.drop(
            columns=["ambientes", "origens"],
            errors="ignore"
        )
    return materiais_df, circuitos_df


def _gerar_excel_materiais_circuitos(materiais_df, circuitos_df):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        materiais_df.to_excel(writer, sheet_name="Materiais", index=False)
        circuitos_df.to_excel(writer, sheet_name="Circuitos", index=False)

        workbook = writer.book
        cabecalho = workbook.add_format({
            "bold": True, "bg_color": "#EAF2FF", "border": 1,
            "align": "center", "valign": "vcenter"
        })
        borda = workbook.add_format({"border": 1, "valign": "top"})

        for nome_aba, df in [("Materiais", materiais_df), ("Circuitos", circuitos_df)]:
            ws = writer.sheets[nome_aba]
            ws.freeze_panes(1, 0)
            for col, coluna in enumerate(df.columns):
                ws.write(0, col, coluna, cabecalho)
                valores = df[coluna].astype(str).tolist() if not df.empty else []
                largura = max([len(str(coluna))] + [len(v) for v in valores[:200]])
                ws.set_column(col, col, min(max(largura + 2, 12), 42))
            if not df.empty:
                ws.conditional_format(
                    1, 0, len(df), max(len(df.columns)-1, 0),
                    {"type": "no_blanks", "format": borda}
                )
    buffer.seek(0)
    return buffer.getvalue()


def _pdf_paragrafo_celula(valor, estilo):
    texto = "" if valor is None else str(valor)
    texto = texto.replace("<br/>", " ").replace("<br>", " ")
    texto = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(texto, estilo)


def _pdf_tabela(df, larguras, cabecalhos=None, fonte=6.2):
    styles = getSampleStyleSheet()
    estilo_header = ParagraphStyle(
        "TabelaHeader",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=max(5.4, fonte - 0.2),
        leading=max(6.3, fonte + 0.7),
        alignment=TA_CENTER,
        textColor=colors.HexColor("#172033"),
    )
    estilo_corpo = ParagraphStyle(
        "TabelaCorpo",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=fonte,
        leading=fonte + 1.0,
        textColor=colors.HexColor("#111827"),
    )

    nomes = list(df.columns)
    exibidos = [cabecalhos.get(c, c) if cabecalhos else c for c in nomes]
    dados = [[_pdf_paragrafo_celula(c, estilo_header) for c in exibidos]]
    for _, row in df.iterrows():
        dados.append([
            _pdf_paragrafo_celula(row[c], estilo_corpo)
            for c in nomes
        ])

    tabela = Table(dados, repeatRows=1, colWidths=larguras)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EAF2FF")),
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#8A8A8A")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (-1,0), "CENTER"),
        ("LEFTPADDING", (0,0), (-1,-1), 2.2),
        ("RIGHTPADDING", (0,0), (-1,-1), 2.2),
        ("TOPPADDING", (0,0), (-1,-1), 3.2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3.2),
    ]))
    return tabela


def _tabela_resumo_pdf(linhas, largura_total=26.5*cm):
    df = pd.DataFrame(linhas, columns=["Parâmetro", "Resultado"])
    return _pdf_tabela(
        df,
        [7.0*cm, largura_total-7.0*cm],
        fonte=7.2
    )


def _gerar_pdf_materiais_circuitos(
    nome_projeto, materiais_df, circuitos_df, tensao_projeto, pe_direito,
    resumo_balanceamento=None, resumo_protecao=None, resumo_drs=None,
    resultado_demanda=None, parametros_rede=None
):
    resumo_balanceamento = dict(resumo_balanceamento or {})
    resumo_protecao = dict(resumo_protecao or {})
    resumo_drs = list(resumo_drs or [])
    resultado_demanda = dict(resultado_demanda or {})
    parametros_rede = dict(parametros_rede or {})

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=0.8*cm, leftMargin=0.8*cm,
        topMargin=0.8*cm, bottomMargin=0.8*cm
    )
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloMateriais", parent=styles["Title"],
        alignment=TA_CENTER, fontSize=15, leading=18, spaceAfter=8
    )
    secao = ParagraphStyle(
        "SecaoMateriais", parent=styles["Heading2"],
        fontSize=11, leading=13, spaceBefore=9, spaceAfter=5
    )
    texto = ParagraphStyle(
        "TextoMateriais", parent=styles["BodyText"],
        fontSize=8, leading=10, spaceAfter=6
    )

    tensao_fornecimento = parametros_rede.get("tensao_fornecimento")
    tipo_fornecimento = parametros_rede.get("tipo_fornecimento")
    alimentacao = tensao_fornecimento or f"{int(tensao_projeto)} V"

    story = [
        Paragraph("CIRCUITOS E QUANTITATIVO DE MATERIAIS", titulo),
        Paragraph(
            f"<b>Projeto:</b> {nome_projeto} &nbsp;&nbsp; "
            f"<b>Fornecimento:</b> {tipo_fornecimento or 'A definir'} - {alimentacao} &nbsp;&nbsp; "
            f"<b>Pé-direito:</b> {float(pe_direito):.2f} m", texto
        ),
        Paragraph("1. QUANTITATIVO DE MATERIAIS", secao)
    ]

    if materiais_df.empty:
        story.append(Paragraph("Nenhum material foi identificado.", texto))
    else:
        story.append(_pdf_tabela(
            materiais_df,
            [2.3*cm, 4.0*cm, 6.5*cm, 1.4*cm, 1.8*cm, 10.4*cm],
            fonte=6.2
        ))

    story += [Spacer(1,8), Paragraph("2. CIRCUITOS CONSIDERADOS NO QUANTITATIVO", secao)]
    if circuitos_df.empty:
        story.append(Paragraph("Nenhum circuito foi identificado.", texto))
    else:
        cabecalhos = {
            "Circuito": "Tipo",
            "Ambiente": "Ambiente",
            "Potência (W)": "Potência<br/>(W)",
            "Tensão (V)": "Tensão<br/>(V)",
            "Corrente estimada (A)": "Corrente<br/>estimada (A)",
            "Bitola preliminar (mm²)": "Bitola<br/>prelim. (mm²)",
            "Disjuntor preliminar (A)": "Disjuntor<br/>prelim. (A)",
            "Nº": "Nº",
            "Fase(s)": "Fase(s)",
            "Polos": "Polos",
            "DR": "DR",
        }
        larguras_por_coluna = {
            "Circuito": 1.55*cm,
            "Ambiente": 3.15*cm,
            "Potência (W)": 1.75*cm,
            "Tensão (V)": 1.45*cm,
            "Corrente estimada (A)": 1.85*cm,
            "Bitola preliminar (mm²)": 1.85*cm,
            "Disjuntor preliminar (A)": 2.05*cm,
            "Nº": 1.25*cm,
            "Fase(s)": 1.45*cm,
            "Polos": 1.35*cm,
            "DR": 1.35*cm,
        }
        larguras = [larguras_por_coluna.get(c, 1.8*cm) for c in circuitos_df.columns]
        story.append(_pdf_tabela(
            circuitos_df, larguras, cabecalhos=cabecalhos, fonte=5.8
        ))

    story += [Spacer(1,10), Paragraph("3. BALANCEAMENTO AUTOMÁTICO DE FASES", secao)]
    if resumo_balanceamento.get("status") == "ok":
        linhas = []
        for fase, potencia in resumo_balanceamento.get("fases", {}).items():
            linhas.append((f"Fase {fase}", f"{float(potencia)/1000:.2f} kW"))
        linhas.extend([
            ("Diferença máxima entre fases", f"{float(resumo_balanceamento.get('diferenca_max_w', 0) or 0)/1000:.2f} kW"),
            ("Desequilíbrio preliminar", f"{float(resumo_balanceamento.get('desequilibrio_pct', 0) or 0):.1f}%"),
            ("Critério", "Balanceamento automático pela potência instalada dos circuitos."),
        ])
        story.append(_tabela_resumo_pdf(linhas))
    else:
        story.append(Paragraph(
            "Balanceamento indisponível: complete o tipo de fornecimento nos parâmetros do projeto.",
            texto
        ))

    story += [Spacer(1,8), Paragraph("4. PROTEÇÃO GERAL E ALIMENTADOR", secao)]
    if resumo_protecao.get("status") == "pre_dimensionado":
        sf = resumo_protecao.get("alimentador_fase_mm2")
        sn = resumo_protecao.get("alimentador_neutro_mm2")
        spe = resumo_protecao.get("alimentador_pe_mm2")
        demanda_w = resultado_demanda.get("potencia_demanda_w")
        ib = resumo_protecao.get("corrente_projeto_a")
        linhas = [
            ("Potência instalada", f"{float(resultado_demanda.get('total_w', 0) or 0)/1000:.2f} kW"),
            ("Fator de demanda", f"{float(resultado_demanda.get('fator_demanda_pct', 0) or 0):.1f}%"),
            ("Potência de demanda", f"{float(demanda_w or 0)/1000:.2f} kW" if demanda_w is not None else "A definir"),
            ("Corrente de projeto", f"{float(ib):.2f} A" if ib is not None else "A definir"),
            ("Disjuntor geral", f"{resumo_protecao.get('dg_a')} A {resumo_protecao.get('dg_polos','')}".strip()),
            ("Composição do alimentador", resumo_protecao.get("alimentador_composicao", "")),
            ("Condutor(es) de fase", f"{float(sf):g} mm²" if sf is not None else "A definir"),
            ("Condutor neutro", f"{float(sn):g} mm²" if sn is not None else "A definir"),
            ("Condutor PE", f"{float(spe):g} mm²" if spe is not None else "A definir"),
            ("Hierarquia DG x circuitos", resumo_protecao.get("hierarquia_dg_circuitos", "")),
            ("Hierarquia DR x circuitos", resumo_protecao.get("hierarquia_dr_circuitos", "")),
            ("Seletividade", resumo_protecao.get("seletividade", "")),
            ("Capacidade de interrupção", resumo_protecao.get("capacidade_interrupcao", "")),
        ]
        story.append(_tabela_resumo_pdf(linhas))
        story.append(Spacer(1,4))
        story.append(Paragraph(
            "Pré-dimensionamento condicionado ao método de instalação, temperatura, "
            "agrupamento, queda de tensão, curto-circuito e dados dos fabricantes.",
            texto
        ))
    else:
        story.append(Paragraph(
            "Proteção geral/alimentador ainda incompletos. Complete os parâmetros de fornecimento e demanda.",
            texto
        ))

    story += [Spacer(1,8), Paragraph("5. AGRUPAMENTO DOS DRS", secao)]
    if resumo_drs:
        linhas_dr = []
        for grupo in resumo_drs:
            circuitos_txt = ", ".join(f"C{int(n):02d}" for n in grupo.get("circuitos", []))
            nominal = grupo.get("corrente_nominal_a")
            sens = grupo.get("sensibilidade_ma")
            linhas_dr.append({
                "DR": grupo.get("dr", ""),
                "Aplicação": grupo.get("descricao", ""),
                "Circuitos": circuitos_txt,
                "Potência (W)": f"{float(grupo.get('potencia_w', 0) or 0):.0f}",
                "Maior DJ (A)": grupo.get("maior_dj_a", ""),
                "Nominal (A)": nominal if nominal is not None else "A definir",
                "Sensib. (mA)": sens if sens is not None else "",
                "Coordenação": grupo.get("coordenacao_basica", ""),
            })
        df_dr = pd.DataFrame(linhas_dr)
        story.append(_pdf_tabela(
            df_dr,
            [1.25*cm, 5.0*cm, 5.1*cm, 2.0*cm, 1.8*cm, 1.8*cm, 1.9*cm, 2.1*cm],
            cabecalhos={
                "Potência (W)": "Potência<br/>(W)",
                "Maior DJ (A)": "Maior DJ<br/>(A)",
                "Nominal (A)": "Nominal<br/>(A)",
                "Sensib. (mA)": "Sensib.<br/>(mA)",
            },
            fonte=6.4
        ))
        story.append(Spacer(1,4))
        story.append(Paragraph(
            "Sensibilidade adotada: 30 mA para os grupos definidos pelo sistema. "
            "A corrente nominal é pré-dimensionada a partir dos disjuntores a jusante. "
            "A seletividade definitiva depende das curvas/tabelas dos fabricantes.",
            texto
        ))
    else:
        story.append(Paragraph(
            "Nenhum circuito de tomada/TUE foi identificado para agrupamento em DR.",
            texto
        ))

    story += [
        Spacer(1,8),
        Paragraph(
            "Observação geral: comprimentos de cabos/eletrodutos e alguns dispositivos "
            "de proteção permanecem pré-dimensionados enquanto o roteamento completo "
            "dos circuitos não estiver implementado. O dimensionamento executivo deve "
            "ser confirmado conforme os critérios aplicáveis da NBR 5410 e os dados "
            "dos fabricantes/concessionária.",
            texto
        )
    ]

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def renderizar_materiais(
    tabela_editada,
    config_interruptores_usuario,
    local_qdc=None,
    tensao_projeto=110,
    pe_direito=2.80
):

    materiais, circuitos = (
        calcular_quantitativo_materiais(
            tabela_editada,
            config_interruptores_usuario,
            local_qdc,
            tensao_projeto,
            pe_direito
        )
    )

    parametros_rede = (
        (config_interruptores_usuario or {}).get(
            CHAVE_PARAMETROS_REDE,
            {}
        )
    )
    circuitos, resumo_balanceamento = balancear_circuitos(
        circuitos,
        parametros_rede
    )
    resultado_demanda_materiais = calcular_demanda_qdc(
        tabela_editada,
        parametros_rede
    )
    circuitos, resumo_drs = agrupar_circuitos_dr(
        circuitos,
        resultado_demanda_materiais.get("disjuntor_geral_a")
    )
    resumo_protecao = avaliar_protecoes_alimentador(
        resultado_demanda_materiais,
        parametros_rede,
        circuitos,
        resumo_drs
    )

    st.caption(
        f"Parâmetros usados: tensão derivada do perfil de fornecimento | "
        f"pé-direito {float(pe_direito):.2f} m. "
        "Quantidades de pontos e caixas são calculadas diretamente do projeto. "
        "Comprimentos de cabos/eletrodutos e alguns dispositivos de proteção "
        "ainda são pré-dimensionamentos, pois o CAD ainda não possui o "
        "roteamento completo dos circuitos nem todos os parâmetros exigidos "
        "para o dimensionamento final pela NBR 5410."
    )

    materiais_df, df_circuitos = _dataframes_materiais_circuitos(
        materiais,
        circuitos
    )

    if not materiais_df.empty:
        st.dataframe(
            materiais_df,
            use_container_width=True,
            hide_index=True
        )

    st.markdown("#### ⚖️ Balanceamento automático de fases")

    if resumo_balanceamento.get("status") == "ok":
        fases_resumo = resumo_balanceamento.get("fases", {})
        cols = st.columns(max(1, len(fases_resumo)))
        for col, (fase, pot) in zip(cols, fases_resumo.items()):
            col.metric(f"Fase {fase}", f"{pot/1000:.2f} kW")
        st.caption(
            "Desequilíbrio preliminar entre fases: "
            f"{resumo_balanceamento.get('desequilibrio_pct', 0):.1f}% "
            "com base na potência instalada."
        )
    else:
        st.info(
            "Informe o tipo de fornecimento na etapa Parâmetros "
            "para liberar o balanceamento automático."
        )

    st.markdown("#### 🔧 Proteção geral e alimentador")

    if resumo_protecao.get("status") == "pre_dimensionado":
        c1, c2, c3 = st.columns(3)
        dg = resumo_protecao.get("dg_a")
        polos = resumo_protecao.get("dg_polos","")
        sf = resumo_protecao.get("alimentador_fase_mm2")
        spe = resumo_protecao.get("alimentador_pe_mm2")
        c1.metric("Disjuntor geral", f"{dg} A {polos}".strip())
        c2.metric("Condutor fase preliminar", f"{sf:g} mm²")
        c3.metric("Condutor PE preliminar", f"{spe:g} mm²")
        st.caption(
            "Pré-dimensionamento condicionado ao método de instalação, "
            "temperatura, agrupamento, queda de tensão e curto-circuito."
        )
    else:
        st.info(
            "Complete os parâmetros de fornecimento/demanda para "
            "pré-dimensionar o alimentador e o DG."
        )

    st.markdown("#### 🛡️ Agrupamento dos DRs")

    if resumo_drs:
        for grupo in resumo_drs:
            lista = ", ".join(
                f"C{n:02d}" for n in grupo["circuitos"]
            )
            nominal = grupo.get("corrente_nominal_a")
            sens = grupo.get("sensibilidade_ma")
            especificacao = (
                f"{nominal} A / {sens} mA"
                if nominal is not None
                else f"{sens} mA"
            )
            st.write(
                f"**{grupo['dr']} — {especificacao}** — "
                f"{grupo['descricao']} — {lista}"
            )
        st.caption(
            "Fase 11.5 Rev.1: corrente nominal pré-dimensionada pelo maior "
            "disjuntor a jusante e sensibilidade de 30 mA para os grupos "
            "de tomadas. A seletividade completa depende das curvas e "
            "dados do fabricante."
        )
    else:
        st.info("Nenhum circuito de tomada/TUE foi identificado para agrupamento em DR.")

    st.markdown(
        "#### ⚡ Circuitos considerados no quantitativo"
    )

    st.caption(
        "Fase 11.5 Rev.1: os circuitos abaixo já são consolidados. "
        "TUEs permanecem dedicadas; TUGs de cozinha/serviço permanecem "
        "exclusivas do ambiente; iluminação e demais TUGs podem ser "
        "agrupadas dentro dos limites preliminares definidos pelo sistema."
    )

    if circuitos:
        st.dataframe(
            df_circuitos,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info(
            "Nenhum circuito foi identificado."
        )


    nome_projeto = str(
        st.session_state.get(
            "projeto_ativo",
            "Projeto"
        )
    )
    nome_arquivo = nome_projeto.strip().replace(" ", "_") or "Projeto"

    excel_bytes = _gerar_excel_materiais_circuitos(
        materiais_df,
        df_circuitos
    )
    pdf_bytes = _gerar_pdf_materiais_circuitos(
        nome_projeto,
        materiais_df,
        df_circuitos,
        tensao_projeto,
        pe_direito,
        resumo_balanceamento=resumo_balanceamento,
        resumo_protecao=resumo_protecao,
        resumo_drs=resumo_drs,
        resultado_demanda=resultado_demanda_materiais,
        parametros_rede=parametros_rede
    )

    col_excel, col_pdf = st.columns(2)

    with col_excel:
        st.download_button(
            "📊 Exportar para Excel",
            data=excel_bytes,
            file_name=f"{nome_arquivo}_Circuitos_Materiais_Fase_11_5_Rev_1.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col_pdf:
        st.download_button(
            "📄 Gerar PDF",
            data=pdf_bytes,
            file_name=f"{nome_arquivo}_Circuitos_Materiais_Fase_11_5_Rev_1.pdf",
            mime="application/pdf",
            use_container_width=True
        )
