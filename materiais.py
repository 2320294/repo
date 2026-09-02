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
    circuitos = []

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

            circuitos.append({
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

            circuitos.append({
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

            circuitos.append({
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


def _pdf_tabela(df, larguras):
    dados = [[str(c) for c in df.columns]]
    dados.extend([[str(v) for v in row.tolist()] for _, row in df.iterrows()])
    tabela = Table(dados, repeatRows=1, colWidths=larguras)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EAF2FF")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#8A8A8A")),
        ("FONTSIZE", (0,0), (-1,-1), 6.5),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 3),
        ("RIGHTPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    return tabela


def _gerar_pdf_materiais_circuitos(
    nome_projeto, materiais_df, circuitos_df, tensao_projeto, pe_direito
):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=1.0*cm, leftMargin=1.0*cm,
        topMargin=1.0*cm, bottomMargin=1.0*cm
    )
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloMateriais", parent=styles["Title"],
        alignment=TA_CENTER, fontSize=15, spaceAfter=8
    )
    secao = ParagraphStyle(
        "SecaoMateriais", parent=styles["Heading2"],
        fontSize=11, spaceBefore=8, spaceAfter=5
    )
    texto = ParagraphStyle(
        "TextoMateriais", parent=styles["BodyText"],
        fontSize=8, leading=10, spaceAfter=6
    )

    story = [
        Paragraph("CIRCUITOS E QUANTITATIVO DE MATERIAIS", titulo),
        Paragraph(
            f"<b>Projeto:</b> {nome_projeto} &nbsp;&nbsp; "
            f"<b>Alimentação:</b> {int(tensao_projeto)} V &nbsp;&nbsp; "
            f"<b>Pé-direito:</b> {float(pe_direito):.2f} m", texto
        ),
        Paragraph("1. QUANTITATIVO DE MATERIAIS", secao)
    ]
    if materiais_df.empty:
        story.append(Paragraph("Nenhum material foi identificado.", texto))
    else:
        story.append(_pdf_tabela(
            materiais_df,
            [2.5*cm, 4.2*cm, 7.0*cm, 1.5*cm, 2.0*cm, 8.0*cm]
        ))

    story += [Spacer(1,10), Paragraph("2. CIRCUITOS CONSIDERADOS NO QUANTITATIVO", secao)]
    if circuitos_df.empty:
        story.append(Paragraph("Nenhum circuito foi identificado.", texto))
    else:
        story.append(_pdf_tabela(
            circuitos_df,
            [1.1*cm, 2.1*cm, 2.6*cm, 1.5*cm, 1.3*cm, 1.3*cm, 2.1*cm, 2.4*cm, 2.6*cm, 2.6*cm]
            [:len(circuitos_df.columns)]
        ))

    story += [
        Spacer(1,8),
        Paragraph(
            "Observação: comprimentos de cabos/eletrodutos e alguns dispositivos "
            "de proteção ainda são pré-dimensionamentos enquanto o roteamento "
            "completo dos circuitos não estiver implementado. O dimensionamento "
            "executivo deve ser confirmado conforme os critérios aplicáveis da NBR 5410.",
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
            "Fase 10.3: corrente nominal pré-dimensionada pelo maior "
            "disjuntor a jusante e sensibilidade de 30 mA para os grupos "
            "de tomadas. A seletividade completa depende das curvas e "
            "dados do fabricante."
        )
    else:
        st.info("Nenhum circuito de tomada/TUE foi identificado para agrupamento em DR.")

    st.markdown(
        "#### ⚡ Circuitos considerados no quantitativo"
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
        pe_direito
    )

    col_excel, col_pdf = st.columns(2)

    with col_excel:
        st.download_button(
            "📊 Exportar para Excel",
            data=excel_bytes,
            file_name=f"{nome_arquivo}_Circuitos_Materiais_Fase_10_3.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col_pdf:
        st.download_button(
            "📄 Gerar PDF",
            data=pdf_bytes,
            file_name=f"{nome_arquivo}_Circuitos_Materiais_Fase_10_3.pdf",
            mime="application/pdf",
            use_container_width=True
        )
