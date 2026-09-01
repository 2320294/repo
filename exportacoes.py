from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak
)

from materiais import calcular_quantitativo_materiais


from qdc_config import descricao_qdc

def _valor_w(row, campo_w, campo_va, padrao=0):
    if campo_w in row:
        return float(row.get(campo_w, padrao) or 0)

    if campo_va in row:
        return float(row.get(campo_va, padrao) or 0)

    return float(padrao)


def gerar_excel_projeto(
    tabela_editada,
    config_interruptores_usuario,
    local_qdc,
    tensao_projeto,
    pe_direito
):
    """
    Gera uma planilha Excel em memória com:
      - Quadro de cargas
      - Quantitativo de materiais
      - Parâmetros do projeto
      - Configuração de interruptores
    """
    buffer = BytesIO()

    materiais, circuitos = calcular_quantitativo_materiais(
        tabela_editada=tabela_editada,
        config_interruptores_usuario=config_interruptores_usuario,
        local_qdc=local_qdc,
        tensao_projeto=tensao_projeto,
        pe_direito=pe_direito
    )

    linhas_cargas = []

    for row in sorted(
        tabela_editada,
        key=lambda x: str(
            x.get("Ambiente", "")
        ).casefold()
    ):
        linhas_cargas.append({
            "Ambiente": row.get("Ambiente", ""),
            "Área (m²)": round(
                float(
                    row.get(
                        "Área (m²)",
                        0
                    )
                ),
                2
            ),
            "Perímetro (m)": round(
                float(
                    row.get(
                        "Perímetro (m)",
                        0
                    )
                ),
                2
            ),
            "Qtd Ilum.": int(
                row.get(
                    "Qtd Ilum.",
                    0
                )
            ),
            "Potência Ilum. (W)": int(
                _valor_w(
                    row,
                    "Pot. Unit. Ilum (W)",
                    "Pot. Unit. Ilum (VA)",
                    0
                )
            ),
            "Qtd TUG": int(
                row.get(
                    "Qtd TUG",
                    row.get(
                        "TUGs (Qtd)",
                        0
                    )
                )
            ),
            "Potência TUG (W)": int(
                _valor_w(
                    row,
                    "Pot. Unit. TUG (W)",
                    "Pot. Unit. TUG (VA)",
                    0
                )
            ),
            "Qtd TUE": int(
                row.get(
                    "Qtd TUE",
                    0
                )
            ),
            "Potência TUE (W)": int(
                _valor_w(
                    row,
                    "Pot. Unit. TUE (W)",
                    "Pot. Unit. TUE (VA)",
                    0
                )
            ),
            "Equipamento TUE": row.get(
                "Equipamento TUE",
                "-"
            )
        })

    df_cargas = pd.DataFrame(
        linhas_cargas
    )

    if not df_cargas.empty:
        total = {
            "Ambiente": "TOTAL GERAL",
            "Área (m²)": round(
                df_cargas[
                    "Área (m²)"
                ].sum(),
                2
            ),
            "Perímetro (m)": round(
                df_cargas[
                    "Perímetro (m)"
                ].sum(),
                2
            ),
            "Qtd Ilum.": int(
                df_cargas[
                    "Qtd Ilum."
                ].sum()
            ),
            "Potência Ilum. (W)": int(
                sum(
                    int(r["Qtd Ilum."])
                    *
                    int(r["Potência Ilum. (W)"])
                    for _, r
                    in df_cargas.iterrows()
                )
            ),
            "Qtd TUG": int(
                df_cargas[
                    "Qtd TUG"
                ].sum()
            ),
            "Potência TUG (W)": int(
                sum(
                    int(r["Qtd TUG"])
                    *
                    int(r["Potência TUG (W)"])
                    for _, r
                    in df_cargas.iterrows()
                )
            ),
            "Qtd TUE": int(
                df_cargas[
                    "Qtd TUE"
                ].sum()
            ),
            "Potência TUE (W)": int(
                sum(
                    int(r["Qtd TUE"])
                    *
                    int(r["Potência TUE (W)"])
                    for _, r
                    in df_cargas.iterrows()
                )
            ),
            "Equipamento TUE": "-"
        }

        df_cargas = pd.concat(
            [
                df_cargas,
                pd.DataFrame(
                    [total]
                )
            ],
            ignore_index=True
        )

    df_materiais = pd.DataFrame(
        materiais
    )

    df_circuitos = pd.DataFrame(
        circuitos
    )

    df_parametros = pd.DataFrame([
        {
            "Parâmetro": "Tensão do quadro",
            "Valor": f"{int(tensao_projeto)} V"
        },
        {
            "Parâmetro": "Pé-direito do pavimento",
            "Valor": f"{float(pe_direito):.2f} m"
        },
        {
            "Parâmetro": "Local do QDC",
            "Valor": descricao_qdc(local_qdc)
        }
    ])

    linhas_interruptores = []

    for ambiente in sorted(
        config_interruptores_usuario,
        key=str.casefold
    ):
        cfg = (
            config_interruptores_usuario.get(
                ambiente,
                {}
            )
        )

        linhas_interruptores.append({
            "Ambiente": ambiente,
            "Quantidade": int(
                cfg.get(
                    "quantidade",
                    0
                )
            ),
            "Porta": (
                cfg.get(
                    "porta",
                    "-"
                )
            )
        })

    df_interruptores = pd.DataFrame(
        linhas_interruptores
    )

    with pd.ExcelWriter(
        buffer,
        engine="xlsxwriter"
    ) as writer:
        df_cargas.to_excel(
            writer,
            sheet_name="Quadro de Cargas",
            index=False
        )

        df_materiais.to_excel(
            writer,
            sheet_name="Materiais",
            index=False
        )

        df_parametros.to_excel(
            writer,
            sheet_name="Parâmetros",
            index=False
        )

        df_interruptores.to_excel(
            writer,
            sheet_name="Interruptores",
            index=False
        )

        if not df_circuitos.empty:
            df_circuitos.to_excel(
                writer,
                sheet_name="Circuitos",
                index=False
            )

        workbook = writer.book

        formato_cabecalho = workbook.add_format({
            "bold": True,
            "bg_color": "#F0F2F6",
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })

        formato_total = workbook.add_format({
            "bold": True,
            "bg_color": "#F0F2F6",
            "border": 1
        })

        formato_borda = workbook.add_format({
            "border": 1
        })

        for sheet_name, df in [
            ("Quadro de Cargas", df_cargas),
            ("Materiais", df_materiais),
            ("Parâmetros", df_parametros),
            ("Interruptores", df_interruptores),
            ("Circuitos", df_circuitos)
        ]:
            if sheet_name not in writer.sheets:
                continue

            worksheet = writer.sheets[
                sheet_name
            ]

            worksheet.freeze_panes(
                1,
                0
            )

            for col_num, coluna in enumerate(
                df.columns
            ):
                worksheet.write(
                    0,
                    col_num,
                    coluna,
                    formato_cabecalho
                )

                valores = (
                    df[coluna]
                    .astype(str)
                    .tolist()
                    if not df.empty
                    else []
                )

                largura = max(
                    [len(str(coluna))]
                    +
                    [
                        len(v)
                        for v in valores[:200]
                    ]
                )

                worksheet.set_column(
                    col_num,
                    col_num,
                    min(
                        max(
                            largura + 2,
                            12
                        ),
                        40
                    )
                )

            if not df.empty:
                worksheet.conditional_format(
                    1,
                    0,
                    len(df),
                    max(
                        len(df.columns) - 1,
                        0
                    ),
                    {
                        "type": "no_blanks",
                        "format": formato_borda
                    }
                )

        if (
            "Quadro de Cargas"
            in writer.sheets
            and not df_cargas.empty
        ):
            ws = writer.sheets[
                "Quadro de Cargas"
            ]

            total_row = len(
                df_cargas
            )

            ws.set_row(
                total_row,
                None,
                formato_total
            )

    buffer.seek(0)

    return buffer.getvalue()


def gerar_memorial_pdf(
    nome_projeto,
    tabela_editada,
    config_interruptores_usuario,
    local_qdc,
    tensao_projeto,
    pe_direito
):
    """
    Gera Memorial Descritivo preliminar em PDF.

    O texto se apoia nos critérios gerais de instalações elétricas
    de baixa tensão e deixa explícito quando algo ainda depende
    do detalhamento executivo/validação final.
    """
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="TituloCentral",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=16,
            spaceAfter=14
        )
    )

    styles.add(
        ParagraphStyle(
            name="Secao",
            parent=styles["Heading2"],
            fontSize=12,
            spaceBefore=10,
            spaceAfter=6
        )
    )

    styles.add(
        ParagraphStyle(
            name="Texto",
            parent=styles["BodyText"],
            fontSize=9.5,
            leading=13,
            spaceAfter=6
        )
    )

    story = []

    story.append(
        Paragraph(
            "MEMORIAL DESCRITIVO - INSTALAÇÕES ELÉTRICAS",
            styles["TituloCentral"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Projeto:</b> {nome_projeto}",
            styles["Texto"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Tensão do quadro:</b> {int(tensao_projeto)} V",
            styles["Texto"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Pé-direito:</b> {float(pe_direito):.2f} m",
            styles["Texto"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Local previsto para o QDC:</b> {descricao_qdc(local_qdc)}",
            styles["Texto"]
        )
    )

    story.append(
        Spacer(
            1,
            8
        )
    )

    story.append(
        Paragraph(
            "1. OBJETO",
            styles["Secao"]
        )
    )

    story.append(
        Paragraph(
            "Este memorial apresenta os critérios adotados para o "
            "dimensionamento preliminar das instalações elétricas de "
            "baixa tensão do projeto, incluindo pontos de iluminação, "
            "tomadas de uso geral, tomadas de uso específico, dispositivos "
            "de proteção, quadro de distribuição e quantitativo de materiais.",
            styles["Texto"]
        )
    )

    story.append(
        Paragraph(
            "2. REFERÊNCIAS E CRITÉRIOS",
            styles["Secao"]
        )
    )

    story.append(
        Paragraph(
            "O projeto deve ser executado e verificado conforme a edição "
            "vigente da ABNT NBR 5410 e demais normas, regulamentos da "
            "concessionária e requisitos de segurança aplicáveis. "
            "As seções de condutores, proteções e dispositivos diferenciais "
            "devem ser confirmadas no projeto executivo considerando corrente "
            "de projeto, método de instalação, capacidade de condução, "
            "agrupamento, temperatura, queda de tensão e condições reais da obra.",
            styles["Texto"]
        )
    )

    story.append(
        Paragraph(
            "3. QUADRO DE CARGAS",
            styles["Secao"]
        )
    )

    cabecalho = [
        "Ambiente",
        "Ilum.",
        "P.Ilum.(W)",
        "TUG",
        "P.TUG(W)",
        "TUE",
        "P.TUE(W)"
    ]

    dados_tabela = [
        cabecalho
    ]

    for row in sorted(
        tabela_editada,
        key=lambda x: str(
            x.get(
                "Ambiente",
                ""
            )
        ).casefold()
    ):
        dados_tabela.append([
            str(
                row.get(
                    "Ambiente",
                    ""
                )
            ),
            str(
                int(
                    row.get(
                        "Qtd Ilum.",
                        0
                    )
                )
            ),
            str(
                int(
                    _valor_w(
                        row,
                        "Pot. Unit. Ilum (W)",
                        "Pot. Unit. Ilum (VA)",
                        0
                    )
                )
            ),
            str(
                int(
                    row.get(
                        "Qtd TUG",
                        row.get(
                            "TUGs (Qtd)",
                            0
                        )
                    )
                )
            ),
            str(
                int(
                    _valor_w(
                        row,
                        "Pot. Unit. TUG (W)",
                        "Pot. Unit. TUG (VA)",
                        0
                    )
                )
            ),
            str(
                int(
                    row.get(
                        "Qtd TUE",
                        0
                    )
                )
            ),
            str(
                int(
                    _valor_w(
                        row,
                        "Pot. Unit. TUE (W)",
                        "Pot. Unit. TUE (VA)",
                        0
                    )
                )
            )
        ])

    tabela = Table(
        dados_tabela,
        repeatRows=1,
        colWidths=[
            4.0 * cm,
            1.2 * cm,
            2.2 * cm,
            1.2 * cm,
            2.2 * cm,
            1.2 * cm,
            2.2 * cm
        ]
    )

    tabela.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor(
                    "#F0F2F6"
                )
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.grey
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                8
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            )
        ])
    )

    story.append(
        tabela
    )

    story.append(
        Paragraph(
            "4. PROTEÇÕES",
            styles["Secao"]
        )
    )

    story.append(
        Paragraph(
            "Os circuitos deverão possuir proteção contra sobrecorrente "
            "compatível com a seção dos condutores e com a corrente prevista. "
            "O quadro deverá prever dispositivo diferencial residual (DR/IDR) "
            "nos circuitos aplicáveis, proteção contra surtos (DPS) conforme "
            "as condições da instalação e dispositivos de seccionamento "
            "adequados ao esquema de alimentação.",
            styles["Texto"]
        )
    )

    story.append(
        Paragraph(
            "5. ATERRAMENTO E CONDUTOR DE PROTEÇÃO",
            styles["Secao"]
        )
    )

    story.append(
        Paragraph(
            "Todos os circuitos deverão possuir condutor de proteção e "
            "equipotencialização conforme aplicável. O barramento de proteção "
            "do QDC deverá ser interligado ao sistema de aterramento da edificação.",
            styles["Texto"]
        )
    )

    story.append(
        Paragraph(
            "6. INTERRUPTORES E PONTOS DE UTILIZAÇÃO",
            styles["Secao"]
        )
    )

    total_interruptores = sum(
        int(
            cfg.get(
                "quantidade",
                0
            )
        )
        for cfg
        in config_interruptores_usuario.values()
    )

    story.append(
        Paragraph(
            f"O projeto prevê {total_interruptores} ponto(s) de interruptor "
            "conforme configuração definida por ambiente. Os pontos são "
            "posicionados junto às portas/soleiras conforme a geometria do CAD.",
            styles["Texto"]
        )
    )

    story.append(
        Paragraph(
            "7. QUANTITATIVO",
            styles["Secao"]
        )
    )

    materiais, _ = calcular_quantitativo_materiais(
        tabela_editada=tabela_editada,
        config_interruptores_usuario=config_interruptores_usuario,
        local_qdc=local_qdc,
        tensao_projeto=tensao_projeto,
        pe_direito=pe_direito
    )

    dados_mat = [
        [
            "Material",
            "Especificação",
            "Un.",
            "Qtd."
        ]
    ]

    for item in materiais:
        dados_mat.append([
            str(
                item.get(
                    "Material",
                    ""
                )
            ),
            str(
                item.get(
                    "Especificação",
                    ""
                )
            ),
            str(
                item.get(
                    "Unidade",
                    ""
                )
            ),
            str(
                item.get(
                    "Quantidade",
                    ""
                )
            )
        ])

    tabela_mat = Table(
        dados_mat,
        repeatRows=1,
        colWidths=[
            5.0 * cm,
            7.0 * cm,
            1.2 * cm,
            1.5 * cm
        ]
    )

    tabela_mat.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor(
                    "#F0F2F6"
                )
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.35,
                colors.grey
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                7.5
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            )
        ])
    )

    story.append(
        tabela_mat
    )

    story.append(
        Spacer(
            1,
            10
        )
    )

    story.append(
        Paragraph(
            "<b>Observação:</b> Comprimentos de cabos/eletrodutos e "
            "dimensionamentos de proteção apresentados nesta etapa são "
            "preliminares quando o traçado executivo completo ainda não "
            "estiver definido. O responsável técnico deverá validar o "
            "dimensionamento final antes da execução.",
            styles["Texto"]
        )
    )

    doc.build(
        story
    )

    buffer.seek(0)

    return buffer.getvalue()
