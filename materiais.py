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
from versao import VERSAO_SISTEMA
from dimensionamento_rotas import verificar_capacidade_conducao_preliminar
from dimensionamento_rotas import otimizar_eletrodutos_preliminar
from mapa_qdc import gerar_mapa_fisico_qdc, dataframe_slots

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
# Fase 13.2:
# o quantitativo exibido ao usuário não usa mais quantidades
# presumidas. Pontos/caixas vêm das entidades do projeto e
# comprimentos de cabos/eletrodutos só aparecem quando há
# roteamento físico calculado.
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



# ============================================================
# FASE 13.2 — QDC EXECUTIVO / QUANTITATIVO DERIVADO DO UNIFILAR
# ============================================================

MODULO_DIN_MM = 17.5
RESERVA_MINIMA_MODULOS_QDC = 4
RESERVA_QDC_FRACAO = 0.20
TAMANHOS_PADRAO_QDC = (8, 12, 16, 18, 24, 36, 48, 54, 72)


def _polos_numero(valor, padrao=1):
    texto = str(valor or "").upper().strip()
    numeros = "".join(ch for ch in texto if ch.isdigit())
    try:
        n = int(numeros)
        return max(1, n)
    except Exception:
        return max(1, int(padrao))


def _polos_circuito_real(circuito):
    polos = circuito.get("polos")
    if polos:
        return _polos_numero(polos, 1)

    tensao = float(circuito.get("tensao", 0) or 0)
    tipo = str(circuito.get("tipo", "") or "").upper()

    # Compatível com a arquitetura atual: circuitos 220 V/TUE usam 2P;
    # circuitos fase-neutro usam 1P.
    if tipo == "TUE" or tensao > 127.5:
        return 2
    return 1


def _polos_dr_por_circuitos(circuitos_grupo):
    maior = max(
        (_polos_circuito_real(c) for c in circuitos_grupo),
        default=1
    )
    return 2 if maior <= 2 else maior


def _proximo_qdc_padrao(modulos_necessarios):
    necessidade = max(1, int(modulos_necessarios))
    for tamanho in TAMANHOS_PADRAO_QDC:
        if tamanho >= necessidade:
            return tamanho
    # Acima dos tamanhos usuais internos, mantém múltiplo de 12
    return int(math.ceil(necessidade / 12.0) * 12)


def _adicionar_componentes_qdc_executivo(
    materiais,
    circuitos,
    resumo_drs,
    resumo_protecao,
    resultado_demanda,
    local_qdc
):
    """
    Fase 13.2.

    Transforma a estrutura já conhecida do unifilar em componentes físicos
    do QDC. Não inclui conectores genéricos: ainda não existe informação
    suficientemente determinística para contá-los sem estimativa.
    """
    if not local_qdc:
        return {}

    circuitos = list(circuitos or [])
    resumo_drs = list(resumo_drs or [])
    resumo_protecao = dict(resumo_protecao or {})
    resultado_demanda = dict(resultado_demanda or {})

    por_numero = {
        int(c.get("numero", 0) or 0): c
        for c in circuitos
        if int(c.get("numero", 0) or 0) > 0
    }

    # ------------------------
    # Disjuntores terminais
    # ------------------------
    contagem_dj = {}
    modulos_dj_terminais = 0
    for c in circuitos:
        corrente = int(c.get("disjuntor", 0) or 0)
        polos = _polos_circuito_real(c)
        if corrente <= 0:
            continue
        chave = (polos, corrente)
        contagem_dj[chave] = contagem_dj.get(chave, 0) + 1
        modulos_dj_terminais += polos

    for (polos, corrente), qtd in sorted(contagem_dj.items()):
        _adicionar_material(
            materiais,
            "QDC — Proteção",
            "Disjuntor termomagnético terminal",
            f"{polos}P {corrente} A",
            "pç",
            qtd,
            "Quantidade, polos e corrente derivados dos circuitos finais"
        )

    # ------------------------
    # Disjuntor geral
    # ------------------------
    dg_a = resultado_demanda.get("disjuntor_geral_a")
    dg_polos_txt = resumo_protecao.get("dg_polos", "")
    dg_polos = _polos_numero(dg_polos_txt, 2)
    modulos_dg = 0

    if dg_a is not None:
        modulos_dg = dg_polos
        _adicionar_material(
            materiais,
            "QDC — Proteção",
            "Disjuntor geral",
            f"{dg_polos}P {int(dg_a)} A",
            "pç",
            1,
            "Proteção geral derivada da demanda e do tipo de fornecimento"
        )

    # ------------------------
    # IDRs / DRs
    # ------------------------
    modulos_drs = 0
    drs_validos = []
    for dr in resumo_drs:
        nominal = dr.get("corrente_nominal_a")
        sens = dr.get("sensibilidade_ma")
        numeros = [
            int(n)
            for n in (dr.get("circuitos", []) or [])
            if int(n or 0) > 0
        ]
        grupo = [por_numero[n] for n in numeros if n in por_numero]
        polos = _polos_dr_por_circuitos(grupo)

        if nominal is None or sens is None:
            continue

        modulos_drs += polos
        drs_validos.append((dr, polos))

        _adicionar_material(
            materiais,
            "QDC — Proteção",
            "IDR / DR",
            (
                f"{polos}P {int(nominal)} A — "
                f"{int(sens)} mA — {dr.get('dr', '')}"
            ),
            "pç",
            1,
            (
                "Grupo "
                + ",".join(f"C{n}" for n in numeros)
                + "; corrente nominal e sensibilidade vindas do agrupamento DR"
            )
        )

    # ------------------------
    # DPS
    # ------------------------
    # O unifilar atual possui DPS após o DG. A quantidade física é derivada
    # dos condutores ativos protegidos pelo arranjo atual.
    tipo_fornecimento = str(
        resumo_protecao.get("alimentador_composicao", "") or ""
    )
    if "3F" in tipo_fornecimento:
        qtd_dps = 3
    elif "2F" in tipo_fornecimento:
        qtd_dps = 2
    elif "F +" in tipo_fornecimento or tipo_fornecimento.startswith("F"):
        qtd_dps = 1
    else:
        qtd_dps = dg_polos if dg_a is not None else 0

    modulos_dps = qtd_dps

    if qtd_dps > 0:
        _adicionar_material(
            materiais,
            "QDC — Proteção",
            "DPS",
            "1P — valor nominal a definir pelo perfil da rede/Icc",
            "pç",
            qtd_dps,
            (
                "Quantidade derivada dos condutores ativos do fornecimento; "
                "Uc/Up/In/Imax permanecem sem valor enquanto os parâmetros "
                "necessários não estiverem definidos"
            )
        )

    # ------------------------
    # Barramentos N e PE
    # ------------------------
    circuitos_com_neutro = sum(
        1
        for c in circuitos
        if _polos_circuito_real(c) == 1
    )
    bornes_n = circuitos_com_neutro + 1  # entrada/alimentação + circuitos
    bornes_pe = len(circuitos) + 1

    _adicionar_material(
        materiais,
        "QDC — Barramentos",
        "Barramento de neutro",
        f"mín. {bornes_n} bornes",
        "pç",
        1,
        "1 borne por circuito com neutro + 1 borne de entrada"
    )
    _adicionar_material(
        materiais,
        "QDC — Barramentos",
        "Barramento de proteção PE",
        f"mín. {bornes_pe} bornes",
        "pç",
        1,
        "1 borne PE por circuito + 1 borne de entrada"
    )

    # ------------------------
    # Barramento pente
    # ------------------------
    # Conta polos/módulos efetivamente alimentados no quadro.
    polos_pente = modulos_dj_terminais
    if polos_pente > 0:
        _adicionar_material(
            materiais,
            "QDC — Distribuição",
            "Barramento pente",
            f"capacidade mínima {polos_pente} polos/módulos",
            "pç",
            1,
            (
                "Comprimento útil derivado dos polos dos disjuntores terminais; "
                "configuração final 1P/2P/fases conforme montagem do unifilar"
            )
        )

    # ------------------------
    # Terminais tubulares por bitola
    # ------------------------
    # Duas terminações por condutor do circuito no interior do QDC:
    # dispositivo de proteção/distribuição e borne/barramento correspondente.
    terminais = {}
    for c in circuitos:
        bitola = float(c.get("bitola", 0) or 0)
        if bitola <= 0:
            continue
        polos = _polos_circuito_real(c)
        condutores_no_qdc = 3 if polos <= 2 else polos + 1
        terminais[bitola] = (
            terminais.get(bitola, 0)
            + 2 * condutores_no_qdc
        )

    # Alimentador: inclui terminais somente quando a seção já foi definida.
    sf = resumo_protecao.get("alimentador_fase_mm2")
    sn = resumo_protecao.get("alimentador_neutro_mm2")
    spe = resumo_protecao.get("alimentador_pe_mm2")
    comp = str(resumo_protecao.get("alimentador_composicao", "") or "")
    fases_alim = 3 if "3F" in comp else 2 if "2F" in comp else 1 if "F" in comp else 0

    if sf:
        terminais[float(sf)] = terminais.get(float(sf), 0) + 2 * fases_alim
    if sn:
        terminais[float(sn)] = terminais.get(float(sn), 0) + 2
    if spe:
        terminais[float(spe)] = terminais.get(float(spe), 0) + 2

    for bitola, qtd in sorted(terminais.items()):
        _adicionar_material(
            materiais,
            "QDC — Terminações",
            "Terminal tubular / ilhós",
            f"{bitola:g} mm²",
            "pç",
            int(qtd),
            "Contagem por seção a partir das terminações elétricas do QDC/unifilar"
        )

    # ------------------------
    # Módulos, quadro e trilho DIN
    # ------------------------
    modulos_ocupados = (
        modulos_dg
        + modulos_dps
        + modulos_drs
        + modulos_dj_terminais
    )
    reserva_modulos = max(
        RESERVA_MINIMA_MODULOS_QDC,
        int(math.ceil(modulos_ocupados * RESERVA_QDC_FRACAO))
    )
    modulos_requeridos = modulos_ocupados + reserva_modulos
    qdc_posicoes = _proximo_qdc_padrao(modulos_requeridos)

    _adicionar_material(
        materiais,
        "QDC",
        "Quadro de distribuição (QDC)",
        (
            f"{qdc_posicoes} posições DIN — "
            f"{modulos_ocupados} ocupadas + "
            f"{qdc_posicoes - modulos_ocupados} livres"
        ),
        "pç",
        1,
        (
            "Tamanho escolhido pela ocupação real dos dispositivos do unifilar "
            f"+ reserva mínima de {reserva_modulos} módulos"
        )
    )

    trilho_mm = qdc_posicoes * MODULO_DIN_MM
    _adicionar_material(
        materiais,
        "QDC — Montagem",
        "Trilho DIN 35 mm",
        f"comprimento útil mínimo {trilho_mm:.0f} mm",
        "m",
        round(trilho_mm / 1000.0, 2),
        "Comprimento derivado das posições DIN do quadro selecionado"
    )

    return {
        "modulos_ocupados": modulos_ocupados,
        "reserva_modulos": reserva_modulos,
        "qdc_posicoes": qdc_posicoes,
        "trilho_din_mm": trilho_mm,
        "quantidade_drs": len(drs_validos),
        "quantidade_dps": qtd_dps,
        "bornes_neutro": bornes_n,
        "bornes_pe": bornes_pe,
        "terminais_por_bitola": terminais,
    }



def _auditar_consistencia_qdc(
    circuitos,
    resumo_drs,
    resumo_protecao,
    resultado_demanda,
    resumo_qdc
):
    """
    Fase 13.2 — auditoria cruzada do QDC.

    A mesma estrutura elétrica usada no quantitativo/unifilar é verificada
    quanto a módulos DIN, polos, DR, barramentos, pente e sequência funcional.
    """
    circuitos = list(circuitos or [])
    drs = list(resumo_drs or [])
    protecao = dict(resumo_protecao or {})
    demanda = dict(resultado_demanda or {})
    qdc = dict(resumo_qdc or {})

    checks = []
    def add(item, status, detalhe):
        checks.append({
            "Verificação": item,
            "Status": status,
            "Detalhe": detalhe,
        })

    # 1. Capacidade física DIN.
    ocupados = int(qdc.get("modulos_ocupados", 0) or 0)
    posicoes = int(qdc.get("qdc_posicoes", 0) or 0)
    reserva = max(0, posicoes - ocupados)
    add(
        "Capacidade do QDC",
        "OK" if posicoes >= ocupados and posicoes > 0 else "ATENÇÃO",
        f"{ocupados} módulos ocupados / {posicoes} posições / {reserva} livres"
    )

    # 2. Polos/tensão dos circuitos.
    inconsist_polos = []
    for c in circuitos:
        n = int(c.get("numero", 0) or 0)
        polos = _polos_circuito_real(c)
        tensao = float(c.get("tensao", 0) or 0)
        if tensao > 127.5 and polos < 2:
            inconsist_polos.append(f"C{n}")
    add(
        "Polos × tensão dos circuitos",
        "OK" if not inconsist_polos else "ATENÇÃO",
        "Compatível" if not inconsist_polos else "Revisar " + ", ".join(inconsist_polos)
    )

    # 3. Cobertura DR e exclusividade de grupo.
    # Fase 13.2 Rev.1:
    # somente circuitos que a própria lógica do projeto classificou para DR
    # são obrigados a aparecer em um grupo IDR. Iluminação comum sem DR não
    # gera alerta apenas por estar fora dos grupos.
    cobertura = {}
    for dr in drs:
        nome = str(dr.get("dr", "") or "")
        for n in dr.get("circuitos", []) or []:
            n = int(n or 0)
            if n > 0:
                cobertura.setdefault(n, []).append(nome)

    problemas_dr = []
    qtd_classificados_dr = 0

    for c in circuitos:
        n = int(c.get("numero", 0) or 0)
        grupo_projeto = str(c.get("dr", "") or "").strip()
        grupos = cobertura.get(n, [])

        if not grupo_projeto:
            continue

        qtd_classificados_dr += 1

        if len(grupos) == 0:
            problemas_dr.append(f"C{n} classificado para DR sem grupo correspondente")
        elif len(grupos) > 1:
            problemas_dr.append(f"C{n} associado a mais de um IDR")

    if problemas_dr:
        add(
            "Agrupamento dos IDRs",
            "ATENÇÃO",
            "; ".join(problemas_dr)
        )
    else:
        add(
            "Agrupamento dos IDRs",
            "OK",
            (
                f"{qtd_classificados_dr} circuito(s) classificados para DR "
                "estão associados corretamente. Circuitos não classificados "
                "para DR, como iluminação comum, não geram alerta."
            )
        )

    # 4. Neutros separados por IDR.
    grupos_com_neutro = 0
    for dr in drs:
        numeros = {int(n or 0) for n in (dr.get("circuitos", []) or [])}
        if any(
            _polos_circuito_real(c) == 1
            for c in circuitos
            if int(c.get("numero", 0) or 0) in numeros
        ):
            grupos_com_neutro += 1

    bornes_n = int(qdc.get("bornes_neutro", 0) or 0)
    neutros_circuitos = sum(1 for c in circuitos if _polos_circuito_real(c) == 1)
    minimo_n = neutros_circuitos + max(1, grupos_com_neutro)
    add(
        "Barramento(s) de neutro",
        "OK" if bornes_n >= neutros_circuitos + 1 else "ATENÇÃO",
        (
            f"{bornes_n} bornes previstos; {neutros_circuitos} circuito(s) com N. "
            f"Há {grupos_com_neutro} grupo(s) DR com neutro; os neutros a jusante "
            "devem permanecer separados por IDR."
        )
    )

    # 5. PE.
    bornes_pe = int(qdc.get("bornes_pe", 0) or 0)
    minimo_pe = len(circuitos) + 1
    add(
        "Barramento PE",
        "OK" if bornes_pe >= minimo_pe else "ATENÇÃO",
        f"{bornes_pe} bornes previstos / mínimo {minimo_pe}"
    )

    # 6. Barramento pente.
    polos_terminais = sum(_polos_circuito_real(c) for c in circuitos)
    add(
        "Barramento pente",
        "OK" if polos_terminais > 0 else "ATENÇÃO",
        f"Capacidade útil mínima: {polos_terminais} polos/módulos de disjuntores terminais"
    )

    # 7. Proteção geral.
    dg = demanda.get("disjuntor_geral_a")
    add(
        "Disjuntor geral",
        "OK" if dg else "ATENÇÃO",
        f"DG {int(dg)} A definido" if dg else "Disjuntor geral ainda não definido"
    )

    # 8. DPS.
    qtd_dps = int(qdc.get("quantidade_dps", 0) or 0)
    add(
        "Quantidade de DPS",
        "OK" if qtd_dps > 0 else "ATENÇÃO",
        f"{qtd_dps} módulo(s) DPS previsto(s)" if qtd_dps else "Quantidade de DPS não definida"
    )

    # 9. Sequência funcional do unifilar.
    tem_dg = bool(dg)
    tem_dps = qtd_dps > 0
    tem_dr = len(drs) > 0
    tem_dj = len(circuitos) > 0
    sequencia_ok = tem_dg and tem_dps and tem_dr and tem_dj
    add(
        "Sequência funcional",
        "OK" if sequencia_ok else "ATENÇÃO",
        "Entrada → DG → DPS → IDR/DR → disjuntores → circuitos"
        if sequencia_ok else
        "Estrutura incompleta para Entrada → DG → DPS → IDR/DR → disjuntores → circuitos"
    )

    alertas = sum(1 for item in checks if item["Status"] != "OK")
    return {
        "status": "OK" if alertas == 0 else "ATENÇÃO",
        "qtd_alertas": alertas,
        "verificacoes": checks,
        "modulos_ocupados": ocupados,
        "qdc_posicoes": posicoes,
        "posicoes_livres": reserva,
        "grupos_dr": len(drs),
        "grupos_dr_com_neutro": grupos_com_neutro,
        "polos_disjuntores_terminais": polos_terminais,
    }


def calcular_quantitativo_materiais(
    tabela_editada,
    config_interruptores_usuario,
    local_qdc=None,
    tensao_projeto=110,
    pe_direito=2.80,
    resumo_rotas=None
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

    configuracoes_interruptores_reais = [
        cfg
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
    ]

    total_interruptores_simples = sum(
        1
        for cfg in configuracoes_interruptores_reais
        if _inteiro(
            cfg.get(
                "quantidade",
                0
            )
        )
        == 1
    )

    total_interruptores_paralelos = sum(
        _inteiro(
            cfg.get(
                "quantidade",
                0
            )
        )
        for cfg in configuracoes_interruptores_reais
        if _inteiro(
            cfg.get(
                "quantidade",
                0
            )
        )
        >= 2
    )

    total_interruptores = (
        total_interruptores_simples
        + total_interruptores_paralelos
    )

    _adicionar_material(
        materiais,
        "Caixas",
        "Caixa octogonal de teto",
        '4x4" — ponto de iluminação',
        "pç",
        total_iluminacao,
        "1 por ponto de iluminação desenhado"
    )

    _adicionar_material(
        materiais,
        "Caixas",
        "Caixa de embutir",
        '4x2" — tomadas TUG',
        "pç",
        total_tug,
        "1 por ponto TUG desenhado"
    )

    _adicionar_material(
        materiais,
        "Caixas",
        "Caixa de embutir",
        '4x2" — tomadas/equipamentos TUE',
        "pç",
        total_tue,
        "1 por ponto TUE desenhado"
    )

    _adicionar_material(
        materiais,
        "Caixas",
        "Caixa de embutir",
        '4x2" — interruptores',
        "pç",
        total_interruptores,
        "1 por interruptor desenhado"
    )

    # Fase 13.2:
    # caixas octogonais dos próprios pontos de iluminação também atuam
    # como nós de passagem/distribuição da rede. Nenhuma caixa de passagem
    # adicional é contabilizada se ela não existir fisicamente no projeto.

    _adicionar_material(
        materiais,
        "Tomadas",
        "Tomada TUG",
        "2P+T 10 A",
        "pç",
        total_tug,
        "Quantidade física de pontos TUG do projeto"
    )

    # TUE: o ponto/caixa é real e permanece no quantitativo.
    # A peça de conexão final (tomada 20 A, borne, saída direta etc.)
    # não é inventada porque depende do equipamento e ainda não é
    # definida como entidade física pelo projeto.

    if total_interruptores_simples > 0:
        _adicionar_material(
            materiais,
            "Comandos",
            "Interruptor simples",
            "Módulo simples",
            "pç",
            total_interruptores_simples,
            "Quantidade física de comandos simples do projeto"
        )

    if total_interruptores_paralelos > 0:
        _adicionar_material(
            materiais,
            "Comandos",
            "Interruptor paralelo",
            "Módulo paralelo",
            "pç",
            total_interruptores_paralelos,
            "Quantidade física de comandos paralelos do projeto"
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
    # FASE 13.2 — FORMAÇÃO DEFINITIVA DOS CIRCUITOS
    # ========================================================
    # A estimativa geométrica de cabos/eletrodutos continua baseada nas
    # cargas elementares por ambiente até a Fase 13.2/11.2, quando o
    # roteamento físico passará a fornecer os comprimentos reais.
    circuitos = formar_circuitos_definitivos(
        circuitos_elementares,
        _disjuntor_por_corrente
    )

    # Fase 13.2 — se o CAD desta versão já calculou correções por
    # queda de tensão, a tabela de circuitos passa a refletir a seção final.
    correcoes_por_numero = {}

    if isinstance(
        resumo_rotas,
        dict
    ):
        for item in (
            resumo_rotas.get(
                "correcoes_bitola",
                []
            )
            or []
        ):
            numero = int(
                item.get(
                    "numero",
                    0
                )
                or 0
            )

            if numero > 0:
                correcoes_por_numero[
                    numero
                ] = item

    for circuito in circuitos:
        numero = int(
            circuito.get(
                "numero",
                0
            )
            or 0
        )

        correcao = correcoes_por_numero.get(
            numero
        )

        if (
            correcao
            and correcao.get(
                "status"
            )
            == "CORRIGIDA"
        ):
            circuito[
                "bitola_original"
            ] = correcao.get(
                "bitola_original_mm2"
            )

            circuito[
                "bitola"
            ] = correcao.get(
                "bitola_final_mm2"
            )

            circuito[
                "queda_tensao_antes_pct"
            ] = correcao.get(
                "queda_antes_pct"
            )

            circuito[
                "queda_tensao_depois_pct"
            ] = correcao.get(
                "queda_depois_pct"
            )

            circuito[
                "criterio_bitola"
            ] = (
                "Seção elevada automaticamente por queda de tensão"
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

    # QDC executivo é consolidado após balanceamento/DR, no renderizador,
    # porque somente ali estão disponíveis polos, grupos DR e proteção geral.

    # ========================================================
    # FASE 13.2 — COMPRIMENTOS REAIS DERIVADOS DO ROTEAMENTO FÍSICO
    # ========================================================
    if (
        isinstance(
            resumo_rotas,
            dict
        )
        and resumo_rotas.get(
            "status"
        )
        == "pre_dimensionado_por_rota"
    ):
        # Remove somente as linhas antigas de comprimento estimado.
        # Pontos, caixas, proteções e demais materiais permanecem.
        materiais = [
            item
            for item in materiais
            if not (
                item.get(
                    "Categoria"
                ) == "Condutores"
                and "Comprimento estimado" in str(
                    item.get(
                        "Critério",
                        ""
                    )
                )
            )
            and not (
                item.get(
                    "Categoria"
                ) == "Infraestrutura"
                and item.get(
                    "Material"
                )
                == "Eletroduto corrugado flexível"
            )
        ]

        # Cabos medidos pelo caminho físico dos trechos.
        agregados_cabos = {}

        for cabo in (
            resumo_rotas.get(
                "cabos",
                []
            )
            or []
        ):
            chave = (
                float(
                    cabo.get(
                        "bitola_mm2",
                        0.0
                    )
                    or 0.0
                ),
                str(
                    cabo.get(
                        "funcao",
                        ""
                    )
                ),
                str(
                    cabo.get(
                        "cor",
                        ""
                    )
                ),
            )

            agregados_cabos[
                chave
            ] = (
                agregados_cabos.get(
                    chave,
                    0.0
                )
                + float(
                    cabo.get(
                        "comprimento_com_folga_m",
                        0.0
                    )
                    or 0.0
                )
            )

        for (
            bitola,
            funcao,
            cor
        ), comprimento in sorted(
            agregados_cabos.items()
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
                    comprimento
                ),
                (
                    "Comprimento obtido do roteamento físico "
                    "+ 15% de folga"
                )
            )

        for eletroduto in (
            resumo_rotas.get(
                "eletrodutos",
                []
            )
            or []
        ):
            diametro = int(
                eletroduto.get(
                    "diametro_mm",
                    0
                )
                or 0
            )

            if diametro <= 0:
                continue

            _adicionar_material(
                materiais,
                "Infraestrutura",
                "Eletroduto corrugado flexível",
                (
                    f"Ø {diametro} mm — "
                    "dimensionado pela ocupação do trecho"
                ),
                "m",
                math.ceil(
                    float(
                        eletroduto.get(
                            "comprimento_com_folga_m",
                            0.0
                        )
                        or 0.0
                    )
                ),
                (
                    "Comprimento do traçado físico + 10% de reserva de instalação; "
                    "diâmetro preliminar pela ocupação dos condutores"
                )
            )

    # ========================================================
    # FASE 13.2 — FILTRO EXECUTIVO: SOMENTE QUANTIDADES DO PROJETO
    # ========================================================
    # Nenhum item entra no quantitativo apenas por regra percentual de
    # quantidade de peças, estimativa por ambiente ou "kit" presumido.
    # Comprimentos permanecem derivados do roteamento físico; a reserva
    # de instalação de cabos/eletrodutos é explícita no critério.
    materiais_estimados_proibidos = {
        "Caixa de passagem",
        "Conector de emenda",
        "Identificador de cabos/circuitos",
    }

    materiais = [
        item
        for item in materiais
        if item.get(
            "Material"
        )
        not in materiais_estimados_proibidos
    ]

    # Se o roteamento físico não estiver disponível, não inventa
    # comprimentos de cabos/eletrodutos.
    tem_rota_fisica = (
        isinstance(
            resumo_rotas,
            dict
        )
        and bool(
            resumo_rotas.get(
                "rotas",
                []
            )
        )
    )

    if not tem_rota_fisica:
        materiais = [
            item
            for item in materiais
            if item.get(
                "Categoria"
            )
            not in {
                "Condutores",
                "Infraestrutura",
            }
        ]

    # Remove qualquer resíduo legado explicitamente marcado como estimativa.
    materiais = [
        item
        for item in materiais
        if "estimativ" not in str(
            item.get(
                "Critério",
                ""
            )
        ).casefold()
    ]

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
            "bitola": "Bitola final (mm²)",
            "disjuntor": "Disjuntor preliminar (A)"
        })
        circuitos_df["Corrente estimada (A)"] = (
            circuitos_df["Corrente estimada (A)"].round(2)
        )
        if "Nº" in circuitos_df.columns:
            circuitos_df["Nº"] = circuitos_df["Nº"].apply(
                lambda valor: f"C{int(valor):02d}"
            )

        # Fase 13.2: dados estruturais usados pelo roteamento continuam
        # dentro dos circuitos em memória, mas não são expostos ao usuário.
        circuitos_df = circuitos_df.drop(
            columns=["ambientes", "origens"],
            errors="ignore"
        )
    return materiais_df, circuitos_df


def _gerar_excel_materiais_circuitos(
    materiais_df,
    circuitos_df,
    validacao_df=None,
    correcoes_df=None,
    agrupamento_df=None,
    capacidade_df=None,
    trechos_capacidade_df=None,
    correcoes_capacidade_df=None,
    iteracoes_df=None,
    auditoria_final_df=None,
    auditoria_trechos_df=None,
    auditoria_qdc_df=None,
    mapa_qdc_df=None,
    mapa_qdc_dispositivos_df=None
):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        materiais_df.to_excel(writer, sheet_name="Materiais", index=False)
        circuitos_df.to_excel(writer, sheet_name="Circuitos", index=False)

        abas = [
            ("Materiais", materiais_df),
            ("Circuitos", circuitos_df),
        ]

        if (
            validacao_df is not None
            and not validacao_df.empty
        ):
            validacao_df.to_excel(
                writer,
                sheet_name="Validacao_Rotas",
                index=False
            )
            abas.append(
                (
                    "Validacao_Rotas",
                    validacao_df
                )
            )

        if (
            correcoes_df is not None
            and not correcoes_df.empty
        ):
            correcoes_df.to_excel(
                writer,
                sheet_name="Correcoes_Queda",
                index=False
            )
            abas.append(
                (
                    "Correcoes_Queda",
                    correcoes_df
                )
            )

        if (
            agrupamento_df is not None
            and not agrupamento_df.empty
        ):
            agrupamento_df.to_excel(
                writer,
                sheet_name="Agrupamento_Rotas",
                index=False
            )
            abas.append(
                (
                    "Agrupamento_Rotas",
                    agrupamento_df
                )
            )

        if (
            capacidade_df is not None
            and not capacidade_df.empty
        ):
            capacidade_df.to_excel(
                writer,
                sheet_name="Capacidade_Conducao",
                index=False
            )
            abas.append(
                (
                    "Capacidade_Conducao",
                    capacidade_df
                )
            )

        if (
            trechos_capacidade_df is not None
            and not trechos_capacidade_df.empty
        ):
            trechos_capacidade_df.to_excel(
                writer,
                sheet_name="Capacidade_Trechos",
                index=False
            )
            abas.append(
                (
                    "Capacidade_Trechos",
                    trechos_capacidade_df
                )
            )

        if (
            correcoes_capacidade_df is not None
            and not correcoes_capacidade_df.empty
        ):
            correcoes_capacidade_df.to_excel(
                writer,
                sheet_name="Correcoes_Capacidade",
                index=False
            )
            abas.append(
                (
                    "Correcoes_Capacidade",
                    correcoes_capacidade_df
                )
            )

        if (
            iteracoes_df is not None
            and not iteracoes_df.empty
        ):
            iteracoes_df.to_excel(
                writer,
                sheet_name="Iteracoes_Dimensionamento",
                index=False
            )
            abas.append(
                (
                    "Iteracoes_Dimensionamento",
                    iteracoes_df
                )
            )

        if (
            auditoria_final_df is not None
            and not auditoria_final_df.empty
        ):
            auditoria_final_df.to_excel(
                writer,
                sheet_name="Auditoria_Final",
                index=False
            )
            abas.append(
                (
                    "Auditoria_Final",
                    auditoria_final_df
                )
            )

        if (
            auditoria_trechos_df is not None
            and not auditoria_trechos_df.empty
        ):
            auditoria_trechos_df.to_excel(
                writer,
                sheet_name="Auditoria_Trechos",
                index=False
            )
            abas.append(
                (
                    "Auditoria_Trechos",
                    auditoria_trechos_df
                )
            )

        if (
            auditoria_qdc_df is not None
            and not auditoria_qdc_df.empty
        ):
            auditoria_qdc_df.to_excel(
                writer,
                sheet_name="Auditoria_QDC",
                index=False
            )
            abas.append(
                (
                    "Auditoria_QDC",
                    auditoria_qdc_df
                )
            )

        if (
            mapa_qdc_df is not None
            and not mapa_qdc_df.empty
        ):
            mapa_qdc_df.to_excel(
                writer,
                sheet_name="Mapa_QDC",
                index=False
            )
            abas.append(
                (
                    "Mapa_QDC",
                    mapa_qdc_df
                )
            )

        if (
            mapa_qdc_dispositivos_df is not None
            and not mapa_qdc_dispositivos_df.empty
        ):
            mapa_qdc_dispositivos_df.to_excel(
                writer,
                sheet_name="Mapa_QDC_Dispositivos",
                index=False
            )
            abas.append(
                (
                    "Mapa_QDC_Dispositivos",
                    mapa_qdc_dispositivos_df
                )
            )

        workbook = writer.book
        cabecalho = workbook.add_format({
            "bold": True, "bg_color": "#EAF2FF", "border": 1,
            "align": "center", "valign": "vcenter"
        })
        borda = workbook.add_format({"border": 1, "valign": "top"})

        for nome_aba, df in abas:
            ws = writer.sheets[nome_aba]
            ws.freeze_panes(1, 0)
            for col, coluna in enumerate(df.columns):
                ws.write(0, col, coluna, cabecalho)
                valores = df[coluna].astype(str).tolist() if not df.empty else []
                largura = max([len(str(coluna))] + [len(str(v)) for v in valores[:200]])
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
    resultado_demanda=None,
    parametros_rede=None,
    validacao_df=None,
    correcoes_df=None,
    agrupamento_df=None,
    capacidade_df=None,
    trechos_capacidade_df=None,
    correcoes_capacidade_df=None,
    iteracoes_df=None,
    auditoria_final_df=None,
    auditoria_trechos_df=None,
    auditoria_qdc_df=None,
    mapa_qdc_df=None,
    mapa_qdc_dispositivos_df=None
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
            "Bitola final (mm²)": "Bitola<br/>final (mm²)",
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
            "Bitola final (mm²)": 1.85*cm,
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

    if (
        correcoes_df is not None
        and not correcoes_df.empty
    ):
        story += [
            Spacer(1,8),
            Paragraph(
                "6. CORREÇÕES AUTOMÁTICAS POR QUEDA DE TENSÃO",
                secao
            )
        ]

        cols_corr_pdf = [
            c
            for c in [
                "Nº",
                "Circuito",
                "Ambiente",
                "Percurso máx. (m)",
                "Bitola anterior (mm²)",
                "Bitola corrigida (mm²)",
                "Queda antes (%)",
                "Queda depois (%)",
            ]
            if c in correcoes_df.columns
        ]

        story.append(
            _pdf_tabela(
                correcoes_df[
                    cols_corr_pdf
                ],
                [
                    1.1*cm,
                    2.0*cm,
                    4.0*cm,
                    2.2*cm,
                    2.3*cm,
                    2.4*cm,
                    2.0*cm,
                    2.0*cm,
                ][:len(cols_corr_pdf)],
                fonte=6.1
            )
        )

        story.append(
            Paragraph(
                "A seção é elevada para a primeira bitola padronizada que "
                "atende ao limite preliminar de queda de tensão. O eletroduto "
                "é recalculado considerando as novas dimensões dos condutores.",
                texto
            )
        )

    if (
        validacao_df is not None
        and not validacao_df.empty
    ):
        story += [
            Spacer(1,8),
            Paragraph(
                "7. QUEDA DE TENSÃO E VALIDAÇÃO DAS ROTAS",
                secao
            )
        ]

        colunas_validacao = [
            c
            for c in [
                "Nº",
                "Circuito",
                "Ambiente",
                "Corrente (A)",
                "Bitola (mm²)",
                "Disjuntor (A)",
                "Percurso máx. (m)",
                "Queda (%)",
                "Status",
            ]
            if c in validacao_df.columns
        ]

        df_pdf_validacao = validacao_df[
            colunas_validacao
        ].copy()

        larguras_validacao = [
            1.1*cm,
            2.0*cm,
            4.0*cm,
            2.0*cm,
            2.0*cm,
            2.1*cm,
            2.4*cm,
            1.8*cm,
            1.7*cm,
        ][:len(colunas_validacao)]

        story.append(
            _pdf_tabela(
                df_pdf_validacao,
                larguras_validacao,
                fonte=6.1
            )
        )

        story.append(
            Paragraph(
                "A queda de tensão é preliminar e usa o maior percurso físico "
                "do circuito. Capacidade de condução, agrupamento, temperatura, "
                "curto-circuito e dados reais dos fabricantes ainda devem ser "
                "confirmados no dimensionamento executivo.",
                texto
            )
        )

    if (
        agrupamento_df is not None
        and not agrupamento_df.empty
    ):
        story += [
            Spacer(1,8),
            Paragraph(
                "8. DIAGNÓSTICO DE AGRUPAMENTO NOS ELETRODUTOS",
                secao
            )
        ]

        cols_agr_pdf = [
            c
            for c in [
                "Nº",
                "Circuito",
                "Ambiente",
                "Bitola (mm²)",
                "Máx. circuitos no trecho",
                "Máx. condutores no trecho",
                "Máx. ocupação (%)",
                "Prioridade",
                "Capacidade de condução",
            ]
            if c in agrupamento_df.columns
        ]

        story.append(
            _pdf_tabela(
                agrupamento_df[
                    cols_agr_pdf
                ],
                [
                    1.0*cm,
                    1.8*cm,
                    3.5*cm,
                    1.8*cm,
                    2.3*cm,
                    2.4*cm,
                    2.1*cm,
                    1.7*cm,
                    4.7*cm,
                ][:len(cols_agr_pdf)],
                fonte=5.8
            )
        )

        story.append(
            Paragraph(
                "A prioridade de revisão é um diagnóstico interno de concentração "
                "física e não substitui os fatores de correção aplicáveis. A "
                "capacidade de condução permanece pendente até a definição do "
                "método de instalação, temperatura e dados reais dos fabricantes.",
                texto
            )
        )

    if (
        capacidade_df is not None
        and not capacidade_df.empty
    ):
        story += [
            Spacer(1,8),
            Paragraph(
                "9. CAPACIDADE DE CONDUÇÃO — VERIFICAÇÃO PRELIMINAR",
                secao
            )
        ]

        cols_cap_pdf = [
            c
            for c in [
                "Nº",
                "Circuito",
                "Ambiente",
                "Ib (A)",
                "Bitola atual (mm²)",
                "Método",
                "Circuitos agrupados",
                "Fator agrup.",
                "Fator temp.",
                "Iz corrigida (A)",
                "Bitola recomendada (mm²)",
                "Status",
            ]
            if c in capacidade_df.columns
        ]

        larguras_cap = {
            "Nº": 0.8*cm,
            "Circuito": 1.5*cm,
            "Ambiente": 3.0*cm,
            "Ib (A)": 1.2*cm,
            "Bitola atual (mm²)": 1.6*cm,
            "Método": 1.1*cm,
            "Circuitos agrupados": 1.8*cm,
            "Fator agrup.": 1.4*cm,
            "Fator temp.": 1.4*cm,
            "Iz corrigida (A)": 1.7*cm,
            "Bitola recomendada (mm²)": 2.1*cm,
            "Status": 1.4*cm,
        }

        story.append(
            _pdf_tabela(
                capacidade_df[cols_cap_pdf],
                [
                    larguras_cap.get(c, 1.5*cm)
                    for c in cols_cap_pdf
                ],
                fonte=5.6
            )
        )

        story.append(
            Paragraph(
                "Verificação preliminar para cobre/PVC 70 °C. Nesta fase a "
                "bitola recomendada não é aplicada automaticamente. O projeto "
                "executivo deve confirmar método de instalação, condutores "
                "carregados, temperatura real, agrupamento e dados de fabricante.",
                texto
            )
        )

    if (
        trechos_capacidade_df is not None
        and not trechos_capacidade_df.empty
    ):
        story += [
            Spacer(1,8),
            Paragraph(
                "10. CAPACIDADE DE CONDUÇÃO POR TRECHO FÍSICO",
                secao
            )
        ]

        cols_trechos_pdf = [
            c
            for c in [
                "Trecho",
                "Nº",
                "Circuito",
                "Ambiente",
                "Comprimento (m)",
                "Circuitos no trecho",
                "Fator agrup.",
                "Ib (A)",
                "Bitola (mm²)",
                "Iz corrigida (A)",
                "Status",
            ]
            if c in trechos_capacidade_df.columns
        ]

        larguras_trechos = {
            "Trecho": 1.0*cm,
            "Nº": 0.7*cm,
            "Circuito": 1.4*cm,
            "Ambiente": 3.0*cm,
            "Comprimento (m)": 1.6*cm,
            "Circuitos no trecho": 1.8*cm,
            "Fator agrup.": 1.4*cm,
            "Ib (A)": 1.1*cm,
            "Bitola (mm²)": 1.4*cm,
            "Iz corrigida (A)": 1.7*cm,
            "Status": 1.3*cm,
        }

        story.append(
            _pdf_tabela(
                trechos_capacidade_df[cols_trechos_pdf],
                [larguras_trechos.get(c, 1.5*cm) for c in cols_trechos_pdf],
                fonte=5.5
            )
        )

        story.append(
            Paragraph(
                "O agrupamento é calculado somente nos trechos em que os "
                "circuitos realmente compartilham o mesmo caminho. O trecho "
                "governante é aquele que apresenta a menor Iz corrigida.",
                texto
            )
        )

    if (
        correcoes_capacidade_df is not None
        and not correcoes_capacidade_df.empty
    ):
        story += [
            Spacer(1,8),
            Paragraph(
                "11. CORREÇÕES AUTOMÁTICAS POR CAPACIDADE DE CONDUÇÃO",
                secao
            )
        ]

        cols_corr_cap_pdf = [
            c
            for c in [
                "Nº",
                "Circuito",
                "Ambiente",
                "Ib (A)",
                "Bitola antes (mm²)",
                "Bitola final (mm²)",
                "Trecho crítico",
                "Circuitos no trecho",
                "Fator agrup.",
                "Iz antes (A)",
                "Iz final (A)",
                "Status",
            ]
            if c in correcoes_capacidade_df.columns
        ]

        larguras_corr_cap = {
            "Nº": 0.8*cm,
            "Circuito": 1.4*cm,
            "Ambiente": 2.8*cm,
            "Ib (A)": 1.1*cm,
            "Bitola antes (mm²)": 1.7*cm,
            "Bitola final (mm²)": 1.7*cm,
            "Trecho crítico": 1.4*cm,
            "Circuitos no trecho": 1.8*cm,
            "Fator agrup.": 1.4*cm,
            "Iz antes (A)": 1.5*cm,
            "Iz final (A)": 1.5*cm,
            "Status": 1.3*cm,
        }

        story.append(
            _pdf_tabela(
                correcoes_capacidade_df[
                    cols_corr_cap_pdf
                ],
                [
                    larguras_corr_cap.get(
                        c,
                        1.5*cm
                    )
                    for c in cols_corr_cap_pdf
                ],
                fonte=5.5
            )
        )

        story.append(
            Paragraph(
                "As seções acima foram elevadas automaticamente quando a "
                "capacidade corrigida do trecho governante ficou abaixo da "
                "corrente de projeto. Após cada alteração, o roteamento e a "
                "ocupação dos eletrodutos foram recalculados.",
                texto
            )
        )

    if (
        iteracoes_df is not None
        and not iteracoes_df.empty
    ):
        story += [
            Spacer(1,8),
            Paragraph(
                "12. HISTÓRICO DO DIMENSIONAMENTO ITERATIVO",
                secao
            )
        ]

        cols_iter_pdf = [
            c
            for c in [
                "Iteração",
                "Trechos",
                "Bitolas alteradas",
                "Alterações",
            ]
            if c in iteracoes_df.columns
        ]

        story.append(
            _pdf_tabela(
                iteracoes_df[
                    cols_iter_pdf
                ],
                [
                    1.4*cm,
                    1.6*cm,
                    2.2*cm,
                    20.0*cm,
                ][:len(cols_iter_pdf)],
                fonte=6.0
            )
        )

    if (
        auditoria_final_df is not None
        and not auditoria_final_df.empty
    ):
        story += [
            Spacer(1,8),
            Paragraph(
                "13. AUDITORIA FINAL DO DIMENSIONAMENTO",
                secao
            )
        ]

        cols_af = [
            c
            for c in [
                "Circuito",
                "Tipo",
                "Ambiente",
                "Ib (A)",
                "Disjuntor In (A)",
                "Bitola final (mm²)",
                "Percurso máx. (m)",
                "Queda (%)",
                "Agrupamento",
                "Iz corrigida (A)",
                "Ib ≤ In ≤ Iz",
                "Resultado",
            ]
            if c in auditoria_final_df.columns
        ]

        larg_af = {
            "Circuito": 1.0*cm,
            "Tipo": 1.4*cm,
            "Ambiente": 3.1*cm,
            "Ib (A)": 1.1*cm,
            "Disjuntor In (A)": 1.6*cm,
            "Bitola final (mm²)": 1.7*cm,
            "Percurso máx. (m)": 1.7*cm,
            "Queda (%)": 1.2*cm,
            "Agrupamento": 1.4*cm,
            "Iz corrigida (A)": 1.7*cm,
            "Ib ≤ In ≤ Iz": 1.5*cm,
            "Resultado": 1.3*cm,
        }

        story.append(
            _pdf_tabela(
                auditoria_final_df[
                    cols_af
                ],
                [
                    larg_af.get(
                        c,
                        1.5*cm
                    )
                    for c in cols_af
                ],
                fonte=5.4
            )
        )

    if (
        auditoria_trechos_df is not None
        and not auditoria_trechos_df.empty
    ):
        story += [
            Spacer(1,8),
            Paragraph(
                "14. AUDITORIA FINAL DOS TRECHOS DE ELETRODUTO",
                secao
            )
        ]

        cols_at = [
            c
            for c in [
                "Trecho",
                "Circuitos transportados",
                "Qtd. circuitos",
                "Condutores",
                "Eletroduto",
                "Ocupação (%)",
                "Comprimento (m)",
                "Resultado",
            ]
            if c in auditoria_trechos_df.columns
        ]

        larg_at = {
            "Trecho": 1.0*cm,
            "Circuitos transportados": 5.0*cm,
            "Qtd. circuitos": 1.5*cm,
            "Condutores": 1.4*cm,
            "Eletroduto": 1.4*cm,
            "Ocupação (%)": 1.5*cm,
            "Comprimento (m)": 1.6*cm,
            "Resultado": 1.3*cm,
        }

        story.append(
            _pdf_tabela(
                auditoria_trechos_df[
                    cols_at
                ],
                [
                    larg_at.get(
                        c,
                        1.5*cm
                    )
                    for c in cols_at
                ],
                fonte=5.6
            )
        )

    if (
        auditoria_qdc_df is not None
        and not auditoria_qdc_df.empty
    ):
        story += [
            Spacer(1,8),
            Paragraph(
                "15. CONSISTÊNCIA ELÉTRICA DO QDC",
                secao
            )
        ]

        story.append(
            _pdf_tabela(
                auditoria_qdc_df,
                [
                    5.0*cm,
                    2.0*cm,
                    18.0*cm,
                ],
                fonte=6.0
            )
        )

        story.append(
            Paragraph(
                "A auditoria cruza a estrutura do unifilar com o quantitativo "
                "do quadro: capacidade DIN, polos, grupos DR, separação de "
                "neutros, barramento PE, pente, DG, DPS e sequência funcional.",
                texto
            )
        )

    if (
        mapa_qdc_df is not None
        and not mapa_qdc_df.empty
    ):
        story += [
            Spacer(1,8),
            Paragraph(
                "16. MAPA FÍSICO DO QDC",
                secao
            )
        ]

        colunas_mapa = len(
            mapa_qdc_df.columns
        )
        largura_col = (
            26.0 * cm
            / max(
                1,
                colunas_mapa
            )
        )

        story.append(
            _pdf_tabela(
                mapa_qdc_df,
                [
                    largura_col
                    for _ in mapa_qdc_df.columns
                ],
                fonte=5.6
            )
        )

        if (
            mapa_qdc_dispositivos_df is not None
            and not mapa_qdc_dispositivos_df.empty
        ):
            story += [
                Spacer(1,6),
                Paragraph(
                    "Lista de dispositivos e posições DIN",
                    texto
                )
            ]

            story.append(
                _pdf_tabela(
                    mapa_qdc_dispositivos_df,
                    [
                        2.2*cm,
                        1.5*cm,
                        5.8*cm,
                        2.0*cm,
                        1.5*cm,
                        1.5*cm,
                        2.0*cm,
                        2.0*cm,
                    ],
                    fonte=5.3
                )
            )

    story += [
        Spacer(1,8),
        Paragraph(
            "Observação geral: os comprimentos de cabos/eletrodutos passam a usar "
            "o roteamento físico quando disponível. Os dispositivos e verificações "
            "de proteção permanecem pré-dimensionados porque ainda dependem de método "
            "de instalação, agrupamento e dados reais dos fabricantes. O dimensionamento executivo deve "
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

    resumo_rotas = None

    if (
        st.session_state.get(
            "dimensionamento_rotas_projeto"
        )
        == st.session_state.get(
            "projeto_ativo"
        )
        and st.session_state.get(
            "dimensionamento_rotas_versao"
        )
        == VERSAO_SISTEMA
    ):
        resumo_rotas = st.session_state.get(
            "dimensionamento_rotas"
        )

    materiais, circuitos = (
        calcular_quantitativo_materiais(
            tabela_editada,
            config_interruptores_usuario,
            local_qdc,
            tensao_projeto,
            pe_direito,
            resumo_rotas=resumo_rotas
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

    # Fase 13.2:
    # os números definitivos dos circuitos só existem depois do balanceamento.
    # Por isso, as correções por queda de tensão são reaplicadas neste ponto
    # para refletirem corretamente na tabela de circuitos, Excel e PDF.
    if isinstance(resumo_rotas, dict):
        correcoes_por_numero_ui = {
            int(item.get("numero", 0) or 0): item
            for item in (resumo_rotas.get("correcoes_bitola", []) or [])
            if int(item.get("numero", 0) or 0) > 0
        }

        for circuito in circuitos:
            numero = int(circuito.get("numero", 0) or 0)
            correcao = correcoes_por_numero_ui.get(numero)

            if correcao and correcao.get("status") == "CORRIGIDA":
                circuito["bitola_original"] = correcao.get("bitola_original_mm2")
                circuito["bitola"] = correcao.get("bitola_final_mm2")
                circuito["queda_tensao_antes_pct"] = correcao.get("queda_antes_pct")
                circuito["queda_tensao_depois_pct"] = correcao.get("queda_depois_pct")
                circuito["criterio_bitola"] = (
                    "Seção elevada automaticamente por queda de tensão"
                )
    # Fase 13.2:
    # reaplica a seção FINAL calculada pelo ciclo iterativo
    # (queda de tensão + capacidade de condução + reroteamento).
    if isinstance(resumo_rotas, dict):
        finais_por_numero = {
            int(item.get("numero", 0) or 0): item
            for item in (
                resumo_rotas.get(
                    "circuitos_dimensionados_finais",
                    []
                )
                or []
            )
            if int(item.get("numero", 0) or 0) > 0
        }

        for circuito in circuitos:
            numero = int(
                circuito.get(
                    "numero",
                    0
                )
                or 0
            )

            final = finais_por_numero.get(
                numero
            )

            if not final:
                continue

            bitola_final = float(
                final.get(
                    "bitola",
                    circuito.get(
                        "bitola",
                        0.0
                    )
                )
                or 0.0
            )

            if bitola_final > 0:
                circuito[
                    "bitola"
                ] = bitola_final

            criterio_final = final.get(
                "criterio_bitola"
            )

            if criterio_final:
                circuito[
                    "criterio_bitola"
                ] = criterio_final

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

    # Fase 13.2 — componentes físicos do QDC derivados do unifilar.
    # Conectores genéricos ficam deliberadamente fora desta fase.
    resumo_qdc_executivo = _adicionar_componentes_qdc_executivo(
        materiais,
        circuitos,
        resumo_drs,
        resumo_protecao,
        resultado_demanda_materiais,
        local_qdc
    )

    auditoria_qdc = _auditar_consistencia_qdc(
        circuitos,
        resumo_drs,
        resumo_protecao,
        resultado_demanda_materiais,
        resumo_qdc_executivo
    )

    mapa_fisico_qdc = gerar_mapa_fisico_qdc(
        circuitos,
        resumo_drs,
        resumo_protecao,
        resultado_demanda_materiais,
        qdc_posicoes=resumo_qdc_executivo.get(
            "qdc_posicoes"
        )
    )

    if resumo_rotas:
        st.success(
            "📐 Comprimentos de cabos e eletrodutos atualizados pelo "
            "roteamento físico calculado automaticamente antes da geração do DXF."
        )
        st.caption(
            "O diâmetro dos eletrodutos é um pré-dimensionamento por ocupação. "
            "Diâmetros reais dos cabos/eletrodutos, método de instalação, "
            "agrupamento, temperatura, queda de tensão e dados do fabricante "
            "ainda precisam ser confirmados no dimensionamento executivo."
        )
    else:
        st.caption(
            f"Parâmetros usados: tensão derivada do perfil de fornecimento | "
            f"pé-direito {float(pe_direito):.2f} m. "
            "O roteamento físico ainda não pôde ser calculado. Confira se o DXF "
            "do projeto e o posicionamento do QDC estão válidos."
        )

    materiais_df, df_circuitos = _dataframes_materiais_circuitos(
        materiais,
        circuitos
    )

    if isinstance(resumo_rotas, dict):
        iterativo = (
            resumo_rotas.get(
                "dimensionamento_iterativo",
                {}
            )
            or {}
        )

        if iterativo:
            st.markdown(
                "#### 🔁 Dimensionamento iterativo automático"
            )

            status_iter = str(
                iterativo.get(
                    "status",
                    ""
                )
                or ""
            )

            qtd_iter = int(
                iterativo.get(
                    "iteracoes",
                    0
                )
                or 0
            )

            metodo_iter = iterativo.get(
                "metodo_instalacao",
                "B1"
            )

            temp_iter = iterativo.get(
                "temperatura_ambiente_c",
                30
            )

            c_it1, c_it2, c_it3 = st.columns(3)
            c_it1.metric(
                "Status",
                status_iter
            )
            c_it2.metric(
                "Iterações",
                qtd_iter
            )
            c_it3.metric(
                "Parâmetros",
                f"{metodo_iter} / {temp_iter} °C"
            )

            historico_iter = (
                iterativo.get(
                    "historico",
                    []
                )
                or []
            )

            if historico_iter:
                linhas_iter = []

                for item in historico_iter:
                    alteracoes = (
                        item.get(
                            "alteracoes",
                            []
                        )
                        or []
                    )

                    alteracoes_txt = ", ".join(
                        (
                            f"C{int(a.get('numero', 0))}: "
                            f"{a.get('bitola_antes_mm2')}→"
                            f"{a.get('bitola_depois_mm2')} mm²"
                        )
                        for a in alteracoes
                    ) or "Sem alteração"

                    linhas_iter.append({
                        "Iteração":
                            item.get(
                                "iteracao"
                            ),
                        "Trechos":
                            item.get(
                                "qtd_trechos"
                            ),
                        "Bitolas alteradas":
                            item.get(
                                "qtd_alteracoes_bitola"
                            ),
                        "Alterações":
                            alteracoes_txt,
                    })

                with st.expander(
                    "🔎 Ver histórico de convergência",
                    expanded=False
                ):
                    st.dataframe(
                        pd.DataFrame(
                            linhas_iter
                        ),
                        use_container_width=True,
                        hide_index=True
                    )

            validacao_ib_in_iz = (
                resumo_rotas.get(
                    "validacao_ib_in_iz",
                    {}
                )
                or {}
            )

            alertas_ibin = int(
                validacao_ib_in_iz.get(
                    "qtd_alertas",
                    0
                )
                or 0
            )

            if (
                status_iter == "CONVERGIU"
                and alertas_ibin == 0
            ):
                st.success(
                    "O ciclo convergiu e a relação preliminar "
                    "Ib ≤ In ≤ Iz está atendida nos circuitos avaliados."
                )
            elif alertas_ibin:
                st.warning(
                    f"{alertas_ibin} circuito(s) ainda exigem revisão da relação "
                    "Ib ≤ In ≤ Iz. O sistema não aumenta automaticamente o disjuntor."
                )

    st.markdown(
        "#### 📦 Quantitativo físico do projeto"
    )

    st.success(
        "A Fase 13.2 mantém o quantitativo físico do projeto e acrescenta "
        "os componentes do QDC que já podem ser derivados do unifilar."
    )

    st.caption(
        "QDC, disjuntores, IDRs, quantidade de DPS, barramentos N/PE, "
        "barramento pente, trilho DIN e terminais por bitola são calculados "
        "a partir da estrutura elétrica já definida. Conectores genéricos "
        "continuam fora do quantitativo. Parâmetros de DPS que dependem de "
        "rede/Icc permanecem explicitamente 'a definir', sem valores inventados."
    )

    if resumo_qdc_executivo:
        st.markdown(
            "##### 🧰 QDC executivo"
        )
        q1, q2, q3, q4 = st.columns(4)
        q1.metric(
            "Posições do QDC",
            resumo_qdc_executivo.get(
                "qdc_posicoes",
                0
            )
        )
        q2.metric(
            "Módulos ocupados",
            resumo_qdc_executivo.get(
                "modulos_ocupados",
                0
            )
        )
        q3.metric(
            "IDRs",
            resumo_qdc_executivo.get(
                "quantidade_drs",
                0
            )
        )
        q4.metric(
            "DPS",
            resumo_qdc_executivo.get(
                "quantidade_dps",
                0
            )
        )

    if auditoria_qdc:
        st.markdown(
            "##### 🛡️ Consistência elétrica do QDC"
        )

        status_qdc = auditoria_qdc.get(
            "status",
            "ATENÇÃO"
        )
        alertas_qdc = int(
            auditoria_qdc.get(
                "qtd_alertas",
                0
            )
            or 0
        )

        a1, a2, a3 = st.columns(3)
        a1.metric(
            "Resultado",
            status_qdc
        )
        a2.metric(
            "Posições livres",
            auditoria_qdc.get(
                "posicoes_livres",
                0
            )
        )
        a3.metric(
            "Alertas",
            alertas_qdc
        )

        df_auditoria_qdc = pd.DataFrame(
            auditoria_qdc.get(
                "verificacoes",
                []
            )
        )

        st.dataframe(
            df_auditoria_qdc,
            use_container_width=True,
            hide_index=True
        )

        if alertas_qdc == 0:
            st.success(
                "QDC consistente na auditoria automática desta fase."
            )
        else:
            st.warning(
                "O QDC possui ponto(s) que exigem revisão antes da montagem."
            )

        st.caption(
            "A auditoria cruza a mesma estrutura usada no unifilar e no "
            "quantitativo: módulos DIN, polos, grupos DR, neutro, PE, pente, "
            "DG, DPS e sequência funcional."
        )

    if mapa_fisico_qdc:
        st.markdown(
            "##### 🧩 Mapa físico do QDC"
        )

        m1, m2, m3 = st.columns(3)
        m1.metric(
            "Configuração",
            (
                f"{mapa_fisico_qdc.get('linhas', 0)} trilho(s) × "
                f"{mapa_fisico_qdc.get('colunas', 0)} posições"
            )
        )
        m2.metric(
            "Módulos de dispositivos",
            mapa_fisico_qdc.get(
                "modulos_dispositivos",
                0
            )
        )
        m3.metric(
            "Posições livres",
            mapa_fisico_qdc.get(
                "posicoes_livres",
                0
            )
        )

        mapa_slots_df = pd.DataFrame(
            dataframe_slots(
                mapa_fisico_qdc
            )
        )

        st.dataframe(
            mapa_slots_df,
            use_container_width=True,
            hide_index=True
        )

        with st.expander(
            "🔎 Ver lista de dispositivos e posições",
            expanded=False
        ):
            dispositivos_mapa_df = pd.DataFrame(
                [
                    {
                        "Dispositivo": d.get(
                            "identificador"
                        ),
                        "Tipo": d.get(
                            "tipo"
                        ),
                        "Descrição": d.get(
                            "descricao"
                        ),
                        "Grupo": d.get(
                            "grupo"
                        ),
                        "Fase": d.get(
                            "fase"
                        ),
                        "Módulos": d.get(
                            "modulos"
                        ),
                        "Posição inicial": d.get(
                            "posicao_inicial"
                        ),
                        "Posição final": d.get(
                            "posicao_final"
                        ),
                    }
                    for d in (
                        mapa_fisico_qdc.get(
                            "dispositivos",
                            []
                        )
                        or []
                    )
                ]
            )

            st.dataframe(
                dispositivos_mapa_df,
                use_container_width=True,
                hide_index=True
            )

        st.caption(
            "O mapa usa a mesma estrutura de DG, DPS, IDRs e disjuntores "
            "do unifilar. Dispositivos com mais de um módulo não são divididos "
            "entre fileiras; as posições restantes ficam identificadas como LIVRE."
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
            "Fase 13.2: corrente nominal pré-dimensionada pelo maior "
            "disjuntor a jusante e sensibilidade de 30 mA para os grupos "
            "de tomadas. A seletividade completa depende das curvas e "
            "dados do fabricante."
        )
    else:
        st.info("Nenhum circuito de tomada/TUE foi identificado para agrupamento em DR.")

    if resumo_rotas:
        st.markdown(
            "#### 📐 Dimensionamento dos trechos roteados"
        )

        st.write(
            f"**{int(resumo_rotas.get('total_trechos', 0))} "
            "trecho(s) físico(s)** analisados."
        )

        diametros = (
            resumo_rotas.get(
                "eletrodutos",
                []
            )
            or []
        )

        if diametros:
            df_eletrodutos_rota = pd.DataFrame(
                diametros
            ).rename(
                columns={
                    "diametro_mm":
                        "Ø nominal (mm)",
                    "comprimento_rota_m":
                        "Traçado (m)",
                    "comprimento_com_folga_m":
                        "Com folga (m)",
                }
            )

            st.dataframe(
                df_eletrodutos_rota,
                use_container_width=True,
                hide_index=True
            )

        correcoes_queda = (
            resumo_rotas.get(
                "correcoes_bitola",
                []
            )
            or []
        )

        corrigidas = [
            item
            for item in correcoes_queda
            if item.get(
                "status"
            )
            == "CORRIGIDA"
        ]

        if corrigidas:
            st.markdown(
                "#### 🔧 Correções automáticas por queda de tensão"
            )

            df_correcoes = pd.DataFrame(
                corrigidas
            ).rename(
                columns={
                    "numero": "Nº",
                    "tipo": "Circuito",
                    "ambiente": "Ambiente",
                    "comprimento_max_m": "Percurso máx. (m)",
                    "corrente_a": "Corrente (A)",
                    "bitola_original_mm2": "Bitola anterior (mm²)",
                    "bitola_final_mm2": "Bitola corrigida (mm²)",
                    "queda_antes_pct": "Queda antes (%)",
                    "queda_depois_pct": "Queda depois (%)",
                    "status": "Status",
                }
            )

            cols_corr = [
                c
                for c in [
                    "Nº",
                    "Circuito",
                    "Ambiente",
                    "Percurso máx. (m)",
                    "Corrente (A)",
                    "Bitola anterior (mm²)",
                    "Bitola corrigida (mm²)",
                    "Queda antes (%)",
                    "Queda depois (%)",
                    "Status",
                ]
                if c in df_correcoes.columns
            ]

            st.dataframe(
                df_correcoes[
                    cols_corr
                ],
                use_container_width=True,
                hide_index=True
            )

            st.success(
                f"{len(corrigidas)} circuito(s) tiveram a seção elevada "
                "automaticamente para atender ao limite preliminar de "
                "queda de tensão. Os eletrodutos dos trechos afetados "
                "foram recalculados com as novas seções."
            )

        validacao = (
            resumo_rotas.get(
                "validacao_eletrica",
                {}
            )
            or {}
        )

        if validacao:
            st.markdown(
                "#### 📉 Queda de tensão e consistência dos circuitos"
            )

            max_compartilhados = int(
                validacao.get(
                    "max_circuitos_mesmo_trecho",
                    0
                )
                or 0
            )

            st.caption(
                f"Maior concentração encontrada: "
                f"{max_compartilhados} circuito(s) no mesmo trecho. "
                "A correção de capacidade por agrupamento será aplicada "
                "quando o método de instalação e os dados reais dos cabos "
                "forem definidos."
            )

            dados_validacao = (
                validacao.get(
                    "circuitos",
                    []
                )
                or []
            )

            if dados_validacao:
                df_validacao = pd.DataFrame(
                    dados_validacao
                ).rename(
                    columns={
                        "numero": "Nº",
                        "tipo": "Circuito",
                        "ambiente": "Ambiente",
                        "corrente_a": "Corrente (A)",
                        "bitola_mm2": "Bitola (mm²)",
                        "disjuntor_a": "Disjuntor (A)",
                        "comprimento_max_m": "Percurso máx. (m)",
                        "queda_tensao_pct": "Queda (%)",
                        "status": "Status",
                    }
                )

                colunas = [
                    c
                    for c in [
                        "Nº",
                        "Circuito",
                        "Ambiente",
                        "Corrente (A)",
                        "Bitola (mm²)",
                        "Disjuntor (A)",
                        "Percurso máx. (m)",
                        "Queda (%)",
                        "Status",
                    ]
                    if c in df_validacao.columns
                ]

                st.dataframe(
                    df_validacao[
                        colunas
                    ],
                    use_container_width=True,
                    hide_index=True
                )

                if (
                    validacao.get(
                        "status"
                    )
                    == "alerta"
                ):
                    st.warning(
                        "Há circuitos com alerta preliminar de queda de "
                        "tensão, proteção ou seção mínima. Revise a tabela "
                        "antes do dimensionamento executivo."
                    )
                else:
                    st.success(
                        "Os circuitos passaram nas verificações preliminares "
                        "implementadas nesta fase."
                    )

            st.caption(
                "A queda de tensão é estimada pelo maior percurso físico "
                "do circuito. A validação final depende também do método "
                "de instalação, temperatura, agrupamento, capacidade de "
                "condução, curto-circuito e dados do fabricante."
            )

    if resumo_rotas:
        diagnostico_agrupamento = (
            resumo_rotas.get(
                "diagnostico_agrupamento",
                {}
            )
            or {}
        )

        if diagnostico_agrupamento:
            st.markdown(
                "#### 🧵 Diagnóstico de agrupamento nos eletrodutos"
            )

            st.caption(
                "Esta fase identifica onde vários circuitos compartilham o "
                "mesmo trecho físico. A classificação BAIXA / MÉDIA / ALTA "
                "é uma prioridade de revisão, não um fator normativo de correção."
            )

            max_comp = int(
                diagnostico_agrupamento.get(
                    "max_circuitos_mesmo_trecho",
                    0
                )
                or 0
            )

            alta = int(
                diagnostico_agrupamento.get(
                    "qtd_trechos_alta_prioridade",
                    0
                )
                or 0
            )

            c1, c2 = st.columns(2)
            c1.metric(
                "Máx. circuitos no mesmo trecho",
                max_comp
            )
            c2.metric(
                "Trechos de alta prioridade",
                alta
            )

            dados_diag = (
                diagnostico_agrupamento.get(
                    "circuitos",
                    []
                )
                or []
            )

            if dados_diag:
                df_diag = pd.DataFrame(
                    dados_diag
                ).rename(
                    columns={
                        "numero": "Nº",
                        "tipo": "Circuito",
                        "ambiente": "Ambiente",
                        "corrente_a": "Corrente (A)",
                        "bitola_mm2": "Bitola (mm²)",
                        "max_circuitos_compartilhados":
                            "Máx. circuitos no trecho",
                        "max_condutores_trecho":
                            "Máx. condutores no trecho",
                        "max_ocupacao_pct":
                            "Máx. ocupação (%)",
                        "qtd_trechos_compartilhados":
                            "Trechos compartilhados",
                        "prioridade_revisao":
                            "Prioridade",
                        "avaliacao_capacidade":
                            "Capacidade de condução",
                    }
                )

                cols_diag = [
                    c
                    for c in [
                        "Nº",
                        "Circuito",
                        "Ambiente",
                        "Corrente (A)",
                        "Bitola (mm²)",
                        "Máx. circuitos no trecho",
                        "Máx. condutores no trecho",
                        "Máx. ocupação (%)",
                        "Trechos compartilhados",
                        "Prioridade",
                        "Capacidade de condução",
                    ]
                    if c in df_diag.columns
                ]

                st.dataframe(
                    df_diag[
                        cols_diag
                    ],
                    use_container_width=True,
                    hide_index=True
                )

            if alta > 0:
                st.warning(
                    "Há trechos com alta concentração física de circuitos. "
                    "Nesta fase o sistema não aumenta a bitola por agrupamento: "
                    "a capacidade de condução permanece pendente até serem "
                    "definidos método de instalação, temperatura e dados reais "
                    "dos cabos/eletrodutos."
                )
            else:
                st.info(
                    "Nenhum trecho foi classificado como alta prioridade de "
                    "agrupamento pelo diagnóstico preliminar."
                )

    if resumo_rotas:
        rotas_redistribuidas = [
            rota
            for rota in (
                resumo_rotas.get(
                    "rotas",
                    []
                )
                or []
            )
            if rota.get(
                "criterio"
            )
            in {
                "REDISTRIBUICAO_CAIXA_OCTOGONAL",
                "REDISTRIBUICAO_NOVA_SAIDA_QDC",
            }
        ]

        if rotas_redistribuidas:
            st.markdown(
                "#### 🔀 Redistribuição física automática aplicada"
            )

            st.success(
                f"{len(rotas_redistribuidas)} novo(s) caminho(s) foram criados "
                "fisicamente para aliviar trechos que ultrapassariam a ocupação "
                "permitida em Ø25 mm."
            )

            linhas_rerota = []

            for rota in rotas_redistribuidas:
                criterio = rota.get(
                    "criterio",
                    ""
                )

                linhas_rerota.append({
                    "Trecho":
                        rota.get(
                            "trecho_id"
                        ),
                    "Origem":
                        rota.get(
                            "origem_ambiente",
                            ""
                        ),
                    "Destino":
                        rota.get(
                            "destino_ambiente",
                            ""
                        ),
                    "Circuitos transportados":
                        ", ".join(
                            f"C{n}"
                            for n in (
                                rota.get(
                                    "circuitos",
                                    []
                                )
                                or []
                            )
                        ),
                    "Qtd. circuitos":
                        len(
                            rota.get(
                                "circuitos",
                                []
                            )
                            or []
                        ),
                    "Condutores":
                        int(
                            rota.get(
                                "qtd_condutores",
                                0
                            )
                            or sum(
                                1
                                for _ in (
                                    rota.get(
                                        "condutores",
                                        []
                                    )
                                    or []
                                )
                            )
                        ),
                    "Comprimento (m)":
                        round(
                            float(
                                rota.get(
                                    "comprimento_m",
                                    0.0
                                )
                                or 0.0
                            ),
                            2
                        ),
                    "Estratégia":
                        (
                            "Via caixa octogonal"
                            if criterio
                            == "REDISTRIBUICAO_CAIXA_OCTOGONAL"
                            else "Nova saída do QDC"
                        ),
                    "Desvio vs. direto (%)":
                        rota.get(
                            "desvio_vs_direto_pct",
                            0.0
                        ),
                })

            st.dataframe(
                pd.DataFrame(
                    linhas_rerota
                ),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info(
                "A rede atual não precisou criar um caminho físico adicional "
                "por excesso de ocupação em Ø25 mm."
            )

        otimizacao_eletrodutos = otimizar_eletrodutos_preliminar(
            resumo_rotas,
            limite_ocupacao_pct=40.0,
            limite_circuitos_preferencial=3,
        )
        resumo_rotas[
            "otimizacao_eletrodutos"
        ] = otimizacao_eletrodutos

        st.markdown(
            "#### 🛠️ Otimização preliminar dos eletrodutos"
        )

        st.caption(
            "Depois da redistribuição física, o sistema reavalia cada trecho e escolhe "
            "o caminho considerando o percurso total desde o QDC. "
            "Nos circuitos terminais o limite permanece Ø25 mm; se a ocupação "
            "passar de 40%, o roteamento procura outra caixa octogonal ou "
            "uma nova saída do QDC."
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Manter", int(otimizacao_eletrodutos.get("qtd_manter", 0) or 0))
        c2.metric("Aumentar eletroduto", int(otimizacao_eletrodutos.get("qtd_aumentar", 0) or 0))
        c3.metric("Novo caminho via caixa", int(otimizacao_eletrodutos.get("qtd_dividir", 0) or 0))

        dados_otimizacao = otimizacao_eletrodutos.get("trechos", []) or []
        if dados_otimizacao:
            linhas_otimizacao = []
            for item in dados_otimizacao:
                grupos = item.get("divisao_grupos", []) or []
                divisao_txt = " | ".join(
                    f"G{g.get('grupo')}: C{','.join(str(x) for x in g.get('circuitos', []))} "
                    f"→ Ø{g.get('eletroduto_mm')} ({g.get('ocupacao_pct')}%)"
                    for g in grupos
                )
                linhas_otimizacao.append({
                    "Trecho": item.get("trecho_id"),
                    "Comprimento (m)": item.get("comprimento_m"),
                    "Circuitos": item.get("qtd_circuitos"),
                    "Condutores": item.get("qtd_condutores"),
                    "Eletroduto atual": (
                        f"Ø{item.get('eletroduto_atual_mm')}"
                        if item.get("eletroduto_atual_mm")
                        else ""
                    ),
                    "Ocupação atual (%)": item.get("ocupacao_atual_pct"),
                    "Próximo eletroduto": (
                        f"Ø{item.get('proximo_eletroduto_mm')}"
                        if item.get("proximo_eletroduto_mm")
                        else ""
                    ),
                    "Ocup. próximo (%)": item.get("ocupacao_proximo_pct"),
                    "Simulação por caixas": divisao_txt,
                    "Recomendação": item.get("recomendacao"),
                })

            df_otimizacao = pd.DataFrame(linhas_otimizacao)
            st.dataframe(
                df_otimizacao,
                use_container_width=True,
                hide_index=True
            )

            with st.expander(
                "ℹ️ Como interpretar as recomendações?",
                expanded=True
            ):
                st.markdown(
                    """
**MANTER** — o trecho está adequado no diagnóstico preliminar.

**AUMENTAR ELETRODUTO** — o problema principal é a ocupação física; o próximo
diâmetro reduz a taxa de ocupação, limitado a **Ø25 mm** nos circuitos terminais.

**NOVO CAMINHO VIA CAIXA** — quando Ø25 mm não é suficiente ou há concentração
elevada, o sistema prefere redistribuir os circuitos usando outra caixa octogonal
de iluminação, em vez de subir para Ø32/Ø40/Ø50 nos circuitos terminais.

Cada caixa octogonal 4x4 é tratada com até **8 entradas/saídas** de eletroduto.
Na Fase 13.2 a redistribuição deixa de ser somente uma recomendação: o novo
caminho é criado fisicamente no roteamento quando a ocupação em Ø25 ultrapassa 40%.
                    """
                )

        st.markdown(
            "#### 🌡️ Capacidade de condução — verificação preliminar"
        )

        st.caption(
            "Fase 13.2: a verificação abaixo usa uma referência preliminar "
            "para condutores de cobre com isolação PVC 70 °C. "
            "Nesta fase o sistema apenas verifica e recomenda; não altera "
            "automaticamente a bitola por capacidade de condução."
        )

        col_metodo, col_temp = st.columns(2)

        with col_metodo:
            opcoes_metodo = {
                "B1 — Condutores isolados em eletroduto embutido na parede": "B1",
                "B2 — Cabo multipolar em eletroduto embutido na parede": "B2",
            }

            rotulo_metodo = st.selectbox(
                "Método de instalação:",
                list(opcoes_metodo.keys()),
                index=0,
                key="fase12_1_metodo_instalacao_rotulo",
                help=(
                    "O método de instalação interfere diretamente na capacidade "
                    "de condução de corrente dos cabos."
                )
            )

            metodo_capacidade = opcoes_metodo[
                rotulo_metodo
            ]

        with col_temp:
            temperatura_capacidade = st.selectbox(
                "Temperatura ambiente de referência:",
                [
                    25,
                    30,
                    35,
                    40,
                    45,
                    50,
                    55,
                    60,
                ],
                index=1,
                format_func=lambda x: f"{x} °C",
                key="fase12_1_temperatura_ambiente"
            )

        with st.expander(
            "ℹ️ Como escolher entre B1 e B2?",
            expanded=True
        ):
            st.markdown(
                """
**B1 — Condutores isolados em eletroduto embutido na parede**

Use quando fase, neutro e terra são **fios/cabos individuais**
passando dentro do eletroduto.  
É o cenário mais próximo do padrão atualmente modelado pelo
**AutoElétrica** para instalações residenciais embutidas.

**B2 — Cabo multipolar em eletroduto embutido na parede**

Use quando o circuito é executado com **um cabo multipolar**
contendo seus condutores dentro do mesmo invólucro, instalado no
eletroduto.

**Recomendação do sistema:** para o padrão residencial atual do
AutoElétrica, mantenha **B1**, salvo quando o responsável técnico
definir explicitamente outro método de instalação.
                """
            )

        capacidade_preliminar = (
            verificar_capacidade_conducao_preliminar(
                resumo_rotas.get(
                    "diagnostico_agrupamento",
                    {}
                ),
                circuitos,
                metodo_instalacao=metodo_capacidade,
                temperatura_ambiente_c=temperatura_capacidade,
            )
        )

        resumo_rotas[
            "capacidade_conducao_preliminar"
        ] = capacidade_preliminar

        dados_capacidade = (
            capacidade_preliminar.get(
                "circuitos",
                []
            )
            or []
        )

        if dados_capacidade:
            df_capacidade = pd.DataFrame(
                dados_capacidade
            ).rename(
                columns={
                    "numero": "Nº",
                    "tipo": "Circuito",
                    "ambiente": "Ambiente",
                    "corrente_a": "Ib (A)",
                    "bitola_atual_mm2": "Bitola atual (mm²)",
                    "metodo_instalacao": "Método",
                    "temperatura_ref_c": "Temp. ref. (°C)",
                    "trecho_critico_id": "Trecho crítico",
                    "comprimento_trecho_critico_m": "Comp. trecho crítico (m)",
                    "qtd_circuitos_agrupados": "Circuitos agrupados",
                    "fator_agrupamento": "Fator agrup.",
                    "fator_temperatura": "Fator temp.",
                    "iz_base_a": "Iz base (A)",
                    "iz_corrigida_a": "Iz corrigida (A)",
                    "bitola_recomendada_mm2": "Bitola recomendada (mm²)",
                    "status": "Status",
                }
            )

            cols_capacidade = [
                c
                for c in [
                    "Nº",
                    "Circuito",
                    "Ambiente",
                    "Ib (A)",
                    "Bitola atual (mm²)",
                    "Método",
                    "Trecho crítico",
                    "Comp. trecho crítico (m)",
                    "Circuitos agrupados",
                    "Fator agrup.",
                    "Fator temp.",
                    "Iz base (A)",
                    "Iz corrigida (A)",
                    "Bitola recomendada (mm²)",
                    "Status",
                ]
                if c in df_capacidade.columns
            ]

            st.dataframe(
                df_capacidade[
                    cols_capacidade
                ],
                use_container_width=True,
                hide_index=True
            )

        dados_trechos_capacidade = (
            capacidade_preliminar.get(
                "trechos",
                []
            )
            or []
        )

        if dados_trechos_capacidade:
            with st.expander(
                "🔎 Ver análise trecho a trecho",
                expanded=False
            ):
                st.caption(
                    "O agrupamento abaixo é calculado somente nos trechos "
                    "físicos em que os circuitos realmente coexistem. "
                    "O trecho crítico é aquele que produz a menor Iz corrigida."
                )

                df_trechos_capacidade = pd.DataFrame(
                    dados_trechos_capacidade
                ).rename(
                    columns={
                        "trecho_id": "Trecho",
                        "numero": "Nº",
                        "tipo": "Circuito",
                        "ambiente": "Ambiente",
                        "comprimento_trecho_m": "Comprimento (m)",
                        "qtd_circuitos_agrupados": "Circuitos no trecho",
                        "fator_agrupamento": "Fator agrup.",
                        "fator_temperatura": "Fator temp.",
                        "corrente_a": "Ib (A)",
                        "bitola_atual_mm2": "Bitola (mm²)",
                        "iz_base_a": "Iz base (A)",
                        "iz_corrigida_a": "Iz corrigida (A)",
                        "status": "Status",
                    }
                )

                cols_trechos = [
                    c
                    for c in [
                        "Trecho",
                        "Nº",
                        "Circuito",
                        "Ambiente",
                        "Comprimento (m)",
                        "Circuitos no trecho",
                        "Fator agrup.",
                        "Ib (A)",
                        "Bitola (mm²)",
                        "Iz corrigida (A)",
                        "Status",
                    ]
                    if c in df_trechos_capacidade.columns
                ]

                st.dataframe(
                    df_trechos_capacidade[cols_trechos],
                    use_container_width=True,
                    hide_index=True
                )

        st.info(
            "Fase 13.2: um trecho com 7 circuitos não faz o sistema assumir "
            "que todo o percurso possui 7 circuitos. Cada trecho é calculado "
            "separadamente e o circuito informa qual trecho é o governante."
        )

        qtd_alertas_capacidade = int(
            capacidade_preliminar.get(
                "qtd_alertas",
                0
            )
            or 0
        )

        if qtd_alertas_capacidade:
            st.warning(
                f"{qtd_alertas_capacidade} circuito(s) ficaram com capacidade "
                "de condução preliminar inferior à corrente de projeto após "
                "os fatores considerados. A bitola recomendada é mostrada "
                "na tabela, mas ainda não é aplicada automaticamente."
            )
        else:
            st.success(
                "Todos os circuitos passaram nesta verificação preliminar "
                "de capacidade de condução para os parâmetros selecionados."
            )

        st.caption(
            "A validação executiva deve confirmar método de instalação, "
            "número de condutores carregados, temperatura real, tipo de isolação, "
            "forma de agrupamento e dados do fabricante."
        )

    if isinstance(resumo_rotas, dict):
        correcoes_capacidade_ui = [
            item
            for item in (
                resumo_rotas.get(
                    "correcoes_capacidade",
                    []
                )
                or []
            )
            if item.get(
                "status"
            )
            == "CORRIGIDA"
        ]

        if correcoes_capacidade_ui:
            st.markdown(
                "#### 🌡️ Correções automáticas por capacidade de condução"
            )

            df_corr_cap = pd.DataFrame(
                correcoes_capacidade_ui
            ).rename(
                columns={
                    "numero": "Nº",
                    "tipo": "Circuito",
                    "ambiente": "Ambiente",
                    "corrente_a": "Ib (A)",
                    "bitola_original_mm2": "Bitola antes (mm²)",
                    "bitola_final_mm2": "Bitola final (mm²)",
                    "trecho_critico_id": "Trecho crítico",
                    "comprimento_trecho_critico_m": "Comp. crítico (m)",
                    "qtd_circuitos_agrupados": "Circuitos no trecho",
                    "fator_agrupamento": "Fator agrup.",
                    "iz_antes_a": "Iz antes (A)",
                    "iz_recomendada_a": "Iz final (A)",
                    "status": "Status",
                }
            )

            cols_corr_cap = [
                c
                for c in [
                    "Nº",
                    "Circuito",
                    "Ambiente",
                    "Ib (A)",
                    "Bitola antes (mm²)",
                    "Bitola final (mm²)",
                    "Trecho crítico",
                    "Circuitos no trecho",
                    "Fator agrup.",
                    "Iz antes (A)",
                    "Iz final (A)",
                    "Status",
                ]
                if c in df_corr_cap.columns
            ]

            st.dataframe(
                df_corr_cap[
                    cols_corr_cap
                ],
                use_container_width=True,
                hide_index=True
            )

            st.caption(
                "Depois de cada correção de seção, a Fase 13.2 recalcula "
                "ocupação, redistribuição dos eletrodutos, queda de tensão "
                "e capacidade de condução até estabilizar."
            )

    if isinstance(resumo_rotas, dict):
        circuitos_finais_auditoria = (
            resumo_rotas.get(
                "circuitos_dimensionados_finais",
                []
            )
            or []
        )

        validacao_ibin = (
            resumo_rotas.get(
                "validacao_ib_in_iz",
                {}
            )
            or {}
        )

        capacidade_final_auditoria = (
            resumo_rotas.get(
                "capacidade_conducao_preliminar",
                {}
            )
            or {}
        )

        validacao_rotas_auditoria = (
            resumo_rotas.get(
                "validacao_eletrica",
                {}
            )
            or {}
        )

        cap_por_numero = {
            int(item.get("numero", 0) or 0): item
            for item in (
                capacidade_final_auditoria.get(
                    "circuitos",
                    []
                )
                or []
            )
            if int(item.get("numero", 0) or 0) > 0
        }

        valid_por_numero = {
            int(item.get("numero", 0) or 0): item
            for item in (
                validacao_rotas_auditoria.get(
                    "circuitos",
                    []
                )
                or []
            )
            if int(item.get("numero", 0) or 0) > 0
        }

        ibin_por_numero = {
            int(item.get("numero", 0) or 0): item
            for item in (
                validacao_ibin.get(
                    "circuitos",
                    []
                )
                or []
            )
            if int(item.get("numero", 0) or 0) > 0
        }

        linhas_auditoria_final = []

        for circuito in circuitos_finais_auditoria:
            numero = int(
                circuito.get(
                    "numero",
                    0
                )
                or 0
            )

            if numero <= 0:
                continue

            cap = cap_por_numero.get(
                numero,
                {}
            )

            val = valid_por_numero.get(
                numero,
                {}
            )

            ibin = ibin_por_numero.get(
                numero,
                {}
            )

            status_queda = (
                "OK"
                if float(
                    val.get(
                        "queda_pct",
                        0.0
                    )
                    or 0.0
                )
                <= 4.0
                else "ATENÇÃO"
            )

            status_ibin = str(
                ibin.get(
                    "status",
                    "PENDENTE"
                )
                or "PENDENTE"
            )

            status_final = (
                "OK"
                if (
                    status_queda == "OK"
                    and status_ibin == "OK"
                )
                else "ATENÇÃO"
            )

            linhas_auditoria_final.append({
                "Circuito":
                    f"C{numero}",
                "Tipo":
                    circuito.get(
                        "tipo",
                        ""
                    ),
                "Ambiente":
                    circuito.get(
                        "ambiente",
                        ""
                    ),
                "Ib (A)":
                    round(
                        float(
                            circuito.get(
                                "corrente",
                                0.0
                            )
                            or 0.0
                        ),
                        2
                    ),
                "Disjuntor In (A)":
                    round(
                        float(
                            circuito.get(
                                "disjuntor",
                                0.0
                            )
                            or 0.0
                        ),
                        2
                    ),
                "Bitola final (mm²)":
                    float(
                        circuito.get(
                            "bitola",
                            0.0
                        )
                        or 0.0
                    ),
                "Percurso máx. (m)":
                    round(
                        float(
                            val.get(
                                "comprimento_max_m",
                                0.0
                            )
                            or 0.0
                        ),
                        2
                    ),
                "Queda (%)":
                    round(
                        float(
                            val.get(
                                "queda_pct",
                                0.0
                            )
                            or 0.0
                        ),
                        2
                    ),
                "Trecho crítico":
                    cap.get(
                        "trecho_critico_id"
                    ),
                "Agrupamento":
                    cap.get(
                        "qtd_circuitos_agrupados"
                    ),
                "Iz corrigida (A)":
                    round(
                        float(
                            cap.get(
                                "iz_corrigida_a",
                                0.0
                            )
                            or 0.0
                        ),
                        2
                    ),
                "Ib ≤ In ≤ Iz":
                    status_ibin,
                "Resultado":
                    status_final,
            })

        if linhas_auditoria_final:
            st.markdown(
                "#### ✅ Auditoria final do dimensionamento"
            )

            st.caption(
                "Resumo executivo dos circuitos após a convergência do ciclo "
                "iterativo. A tabela reúne queda de tensão, capacidade de "
                "condução e relação Ib ≤ In ≤ Iz."
            )

            df_auditoria_final = pd.DataFrame(
                linhas_auditoria_final
            )

            st.dataframe(
                df_auditoria_final,
                use_container_width=True,
                hide_index=True
            )

            qtd_ok = int(
                (
                    df_auditoria_final[
                        "Resultado"
                    ]
                    == "OK"
                ).sum()
            )

            qtd_atencao = int(
                (
                    df_auditoria_final[
                        "Resultado"
                    ]
                    != "OK"
                ).sum()
            )

            c_af1, c_af2, c_af3 = st.columns(3)
            c_af1.metric(
                "Circuitos auditados",
                len(
                    df_auditoria_final
                )
            )
            c_af2.metric(
                "OK",
                qtd_ok
            )
            c_af3.metric(
                "Atenção",
                qtd_atencao
            )

            if qtd_atencao == 0:
                st.success(
                    "Todos os circuitos passaram pela auditoria final "
                    "preliminar desta fase."
                )
            else:
                st.warning(
                    f"{qtd_atencao} circuito(s) ainda apresentam ponto(s) "
                    "que exigem revisão técnica."
                )

        # Auditoria por trecho físico
        rotas_auditoria = (
            resumo_rotas.get(
                "rotas",
                []
            )
            or []
        )

        linhas_trechos_final = []

        for rota in rotas_auditoria:
            circuitos_rota = sorted(
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

            ocupacao = round(
                float(
                    rota.get(
                        "ocupacao_pct",
                        0.0
                    )
                    or 0.0
                ),
                1
            )

            diametro = rota.get(
                "diametro_eletroduto_mm"
            )

            status_trecho = (
                "OK"
                if (
                    ocupacao <= 40.0
                    and (
                        diametro is None
                        or int(
                            diametro
                        )
                        <= 25
                    )
                )
                else "ATENÇÃO"
            )

            linhas_trechos_final.append({
                "Trecho":
                    rota.get(
                        "trecho_id"
                    ),
                "Circuitos transportados":
                    ", ".join(
                        f"C{n}"
                        for n in circuitos_rota
                    ),
                "Qtd. circuitos":
                    len(
                        circuitos_rota
                    ),
                "Condutores":
                    int(
                        rota.get(
                            "qtd_condutores",
                            0
                        )
                        or len(
                            rota.get(
                                "condutores",
                                []
                            )
                            or []
                        )
                    ),
                "Eletroduto":
                    (
                        f"Ø{diametro}"
                        if diametro
                        else ""
                    ),
                "Ocupação (%)":
                    ocupacao,
                "Comprimento (m)":
                    round(
                        float(
                            rota.get(
                                "comprimento_m",
                                0.0
                            )
                            or 0.0
                        ),
                        2
                    ),
                "Critério":
                    rota.get(
                        "criterio",
                        ""
                    ),
                "Resultado":
                    status_trecho,
            })

        if linhas_trechos_final:
            with st.expander(
                "🧵 Auditoria final por trecho de eletroduto",
                expanded=False
            ):
                st.caption(
                    "Confere circuitos transportados, ocupação física, "
                    "diâmetro e comprimento de cada trecho."
                )

                st.dataframe(
                    pd.DataFrame(
                        linhas_trechos_final
                    ),
                    use_container_width=True,
                    hide_index=True
                )

    st.markdown(
        "#### ⚡ Circuitos considerados no quantitativo"
    )

    st.caption(
        "Fase 13.2: os circuitos abaixo já usam as bitolas finais do ciclo iterativo. "
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


    validacao_export_df = None
    correcoes_export_df = None
    agrupamento_export_df = None
    capacidade_export_df = None
    trechos_capacidade_export_df = None
    correcoes_capacidade_export_df = None
    iteracoes_export_df = None
    auditoria_final_export_df = None
    auditoria_trechos_export_df = None
    auditoria_qdc_export_df = None
    mapa_qdc_export_df = None
    mapa_qdc_dispositivos_export_df = None

    if resumo_rotas:
        dados_validacao_export = (
            (
                resumo_rotas.get(
                    "validacao_eletrica",
                    {}
                )
                or {}
            ).get(
                "circuitos",
                []
            )
            or []
        )

        if dados_validacao_export:
            validacao_export_df = pd.DataFrame(
                dados_validacao_export
            ).rename(
                columns={
                    "numero": "Nº",
                    "tipo": "Circuito",
                    "ambiente": "Ambiente",
                    "corrente_a": "Corrente (A)",
                    "bitola_mm2": "Bitola (mm²)",
                    "disjuntor_a": "Disjuntor (A)",
                    "comprimento_max_m": "Percurso máx. (m)",
                    "queda_tensao_pct": "Queda (%)",
                    "status": "Status",
                }
            )

        dados_correcoes_export = [
            item
            for item in (
                resumo_rotas.get(
                    "correcoes_bitola",
                    []
                )
                or []
            )
            if item.get(
                "status"
            )
            == "CORRIGIDA"
        ]

        if dados_correcoes_export:
            correcoes_export_df = pd.DataFrame(
                dados_correcoes_export
            ).rename(
                columns={
                    "numero": "Nº",
                    "tipo": "Circuito",
                    "ambiente": "Ambiente",
                    "comprimento_max_m": "Percurso máx. (m)",
                    "corrente_a": "Corrente (A)",
                    "bitola_original_mm2": "Bitola anterior (mm²)",
                    "bitola_final_mm2": "Bitola corrigida (mm²)",
                    "queda_antes_pct": "Queda antes (%)",
                    "queda_depois_pct": "Queda depois (%)",
                    "status": "Status",
                }
            )

        dados_agrupamento_export = (
            (
                resumo_rotas.get(
                    "diagnostico_agrupamento",
                    {}
                )
                or {}
            ).get(
                "circuitos",
                []
            )
            or []
        )

        if dados_agrupamento_export:
            agrupamento_export_df = pd.DataFrame(
                dados_agrupamento_export
            ).rename(
                columns={
                    "numero": "Nº",
                    "tipo": "Circuito",
                    "ambiente": "Ambiente",
                    "corrente_a": "Corrente (A)",
                    "bitola_mm2": "Bitola (mm²)",
                    "max_circuitos_compartilhados":
                        "Máx. circuitos no trecho",
                    "max_condutores_trecho":
                        "Máx. condutores no trecho",
                    "max_ocupacao_pct":
                        "Máx. ocupação (%)",
                    "qtd_trechos_compartilhados":
                        "Trechos compartilhados",
                    "prioridade_revisao":
                        "Prioridade",
                    "avaliacao_capacidade":
                        "Capacidade de condução",
                }
            )

        dados_capacidade_export = (
            (
                resumo_rotas.get(
                    "capacidade_conducao_preliminar",
                    {}
                )
                or {}
            ).get(
                "circuitos",
                []
            )
            or []
        )

        if dados_capacidade_export:
            capacidade_export_df = pd.DataFrame(
                dados_capacidade_export
            ).rename(
                columns={
                    "numero": "Nº",
                    "tipo": "Circuito",
                    "ambiente": "Ambiente",
                    "corrente_a": "Ib (A)",
                    "bitola_atual_mm2": "Bitola atual (mm²)",
                    "metodo_instalacao": "Método",
                    "temperatura_ref_c": "Temp. ref. (°C)",
                    "trecho_critico_id": "Trecho crítico",
                    "comprimento_trecho_critico_m": "Comp. trecho crítico (m)",
                    "qtd_circuitos_agrupados": "Circuitos agrupados",
                    "fator_agrupamento": "Fator agrup.",
                    "fator_temperatura": "Fator temp.",
                    "iz_base_a": "Iz base (A)",
                    "iz_corrigida_a": "Iz corrigida (A)",
                    "bitola_recomendada_mm2": "Bitola recomendada (mm²)",
                    "iz_recomendada_a": "Iz recomendada (A)",
                    "status": "Status",
                }
            )

        dados_trechos_capacidade_export = (
            (
                resumo_rotas.get(
                    "capacidade_conducao_preliminar",
                    {}
                )
                or {}
            ).get(
                "trechos",
                []
            )
            or []
        )

        if dados_trechos_capacidade_export:
            trechos_capacidade_export_df = pd.DataFrame(
                dados_trechos_capacidade_export
            ).rename(
                columns={
                    "trecho_id": "Trecho",
                    "numero": "Nº",
                    "tipo": "Circuito",
                    "ambiente": "Ambiente",
                    "comprimento_trecho_m": "Comprimento (m)",
                    "qtd_circuitos_agrupados": "Circuitos no trecho",
                    "fator_agrupamento": "Fator agrup.",
                    "fator_temperatura": "Fator temp.",
                    "corrente_a": "Ib (A)",
                    "bitola_atual_mm2": "Bitola (mm²)",
                    "iz_base_a": "Iz base (A)",
                    "iz_corrigida_a": "Iz corrigida (A)",
                    "status": "Status",
                }
            )


    if isinstance(resumo_rotas, dict):
        dados_corr_cap_export = [
            item
            for item in (
                resumo_rotas.get(
                    "correcoes_capacidade",
                    []
                )
                or []
            )
            if item.get(
                "status"
            )
            == "CORRIGIDA"
        ]

        if dados_corr_cap_export:
            correcoes_capacidade_export_df = pd.DataFrame(
                dados_corr_cap_export
            ).rename(
                columns={
                    "numero": "Nº",
                    "tipo": "Circuito",
                    "ambiente": "Ambiente",
                    "corrente_a": "Ib (A)",
                    "bitola_original_mm2": "Bitola antes (mm²)",
                    "bitola_final_mm2": "Bitola final (mm²)",
                    "trecho_critico_id": "Trecho crítico",
                    "comprimento_trecho_critico_m": "Comp. crítico (m)",
                    "qtd_circuitos_agrupados": "Circuitos no trecho",
                    "fator_agrupamento": "Fator agrup.",
                    "fator_temperatura": "Fator temp.",
                    "iz_antes_a": "Iz antes (A)",
                    "iz_recomendada_a": "Iz final (A)",
                    "metodo_instalacao": "Método",
                    "temperatura_ref_c": "Temp. (°C)",
                    "status": "Status",
                }
            )

        historico_export = (
            (
                resumo_rotas.get(
                    "dimensionamento_iterativo",
                    {}
                )
                or {}
            ).get(
                "historico",
                []
            )
            or []
        )

        if historico_export:
            linhas_hist_export = []

            for item in historico_export:
                alteracoes = (
                    item.get(
                        "alteracoes",
                        []
                    )
                    or []
                )

                linhas_hist_export.append({
                    "Iteração":
                        item.get(
                            "iteracao"
                        ),
                    "Trechos":
                        item.get(
                            "qtd_trechos"
                        ),
                    "Bitolas alteradas":
                        item.get(
                            "qtd_alteracoes_bitola"
                        ),
                    "Alterações":
                        ", ".join(
                            (
                                f"C{int(a.get('numero', 0))}: "
                                f"{a.get('bitola_antes_mm2')}→"
                                f"{a.get('bitola_depois_mm2')} mm²"
                            )
                            for a in alteracoes
                        )
                        or "Sem alteração",
                })

            iteracoes_export_df = pd.DataFrame(
                linhas_hist_export
            )

    if isinstance(resumo_rotas, dict):
        if "linhas_auditoria_final" in locals() and linhas_auditoria_final:
            auditoria_final_export_df = pd.DataFrame(
                linhas_auditoria_final
            )

        if "linhas_trechos_final" in locals() and linhas_trechos_final:
            auditoria_trechos_export_df = pd.DataFrame(
                linhas_trechos_final
            )

    if "auditoria_qdc" in locals() and auditoria_qdc:
        auditoria_qdc_export_df = pd.DataFrame(
            auditoria_qdc.get(
                "verificacoes",
                []
            )
        )

    if "mapa_fisico_qdc" in locals() and mapa_fisico_qdc:
        mapa_qdc_export_df = pd.DataFrame(
            dataframe_slots(
                mapa_fisico_qdc
            )
        )

        mapa_qdc_dispositivos_export_df = pd.DataFrame(
            [
                {
                    "Dispositivo": d.get("identificador"),
                    "Tipo": d.get("tipo"),
                    "Descrição": d.get("descricao"),
                    "Grupo": d.get("grupo"),
                    "Fase": d.get("fase"),
                    "Módulos": d.get("modulos"),
                    "Posição inicial": d.get("posicao_inicial"),
                    "Posição final": d.get("posicao_final"),
                }
                for d in (
                    mapa_fisico_qdc.get(
                        "dispositivos",
                        []
                    )
                    or []
                )
            ]
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
        df_circuitos,
        validacao_df=validacao_export_df,
        correcoes_df=correcoes_export_df,
        agrupamento_df=agrupamento_export_df,
        capacidade_df=capacidade_export_df,
        trechos_capacidade_df=trechos_capacidade_export_df,
        correcoes_capacidade_df=correcoes_capacidade_export_df,
        iteracoes_df=iteracoes_export_df,
        auditoria_final_df=auditoria_final_export_df,
        auditoria_trechos_df=auditoria_trechos_export_df,
        auditoria_qdc_df=auditoria_qdc_export_df,
        mapa_qdc_df=mapa_qdc_export_df,
        mapa_qdc_dispositivos_df=mapa_qdc_dispositivos_export_df
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
        parametros_rede=parametros_rede,
        validacao_df=validacao_export_df,
        correcoes_df=correcoes_export_df,
        agrupamento_df=agrupamento_export_df,
        capacidade_df=capacidade_export_df,
        trechos_capacidade_df=trechos_capacidade_export_df,
        correcoes_capacidade_df=correcoes_capacidade_export_df,
        iteracoes_df=iteracoes_export_df,
        auditoria_final_df=auditoria_final_export_df,
        auditoria_trechos_df=auditoria_trechos_export_df,
        auditoria_qdc_df=auditoria_qdc_export_df,
        mapa_qdc_df=mapa_qdc_export_df,
        mapa_qdc_dispositivos_df=mapa_qdc_dispositivos_export_df
    )

    col_excel, col_pdf = st.columns(2)

    with col_excel:
        st.download_button(
            "📊 Exportar para Excel",
            data=excel_bytes,
            file_name=f"{nome_arquivo}_Circuitos_Materiais_Fase_13_2.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col_pdf:
        st.download_button(
            "📄 Gerar PDF",
            data=pdf_bytes,
            file_name=f"{nome_arquivo}_Circuitos_Materiais_Fase_13_2.pdf",
            mime="application/pdf",
            use_container_width=True
        )
