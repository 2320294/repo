import math
import os
import tempfile

import ezdxf

from versao import VERSAO_SISTEMA

from dxf_io import (
    processar_dxf,
    validar_camadas,
    ler_elementos,
    nome_ambiente_para_polilinha
)

from geometria import (
    point_seg_dist,
    bbox_poligono,
    ponto_central_interno,
    ponto_interno_proximo,
    pontos_iluminacao_internos,
    pontos_iluminacao_por_decomposicao
)

from interruptores_cad import (
    desenhar_interruptores
)

from qdc_cad import (
    desenhar_qdc
)

from tomadas_cad import (
    desenhar_tomadas
)

from eletrodutos_cad import (
    desenhar_rede_eletrodutos
)

from roteamento_cad import (
    desenhar_rotas_qdc_iluminacao
)

from dimensionamento_rotas import (
    dimensionar_rotas,
    desenhar_dimensionamento_rotas,
    validar_eletrica_rotas,
    corrigir_bitolas_por_queda,
    diagnosticar_agrupamento_rotas,
    verificar_capacidade_conducao_preliminar,
    corrigir_bitolas_por_capacidade,
    validar_relacao_ib_in_iz
)

from materiais import (
    calcular_quantitativo_materiais
)

from unifilar_qdc import (
    desenhar_unifilar_qdc
)
from mapa_qdc import (
    gerar_mapa_fisico_qdc,
    desenhar_mapa_fisico_qdc
)

from concessionarias import (
    CHAVE_PARAMETROS_REDE
)

from demanda_qdc import (
    calcular_demanda_qdc
)

from balanceamento_fases import (
    balancear_circuitos
)

from agrupamento_dr import (
    agrupar_circuitos_dr
)

from protecao_alimentador import (
    avaliar_protecoes_alimentador
)


def gerar_cad_unifilar(
    dxf_bytes,
    dados_editados,
    local_qdc,
    config_interruptores=None,
    tensao_projeto=220,
    pe_direito=2.80,
    retornar_resumo_rotas=False,
    metodo_instalacao="B1",
    temperatura_ambiente_c=30
):
    tmp_in_path = ""

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".dxf"
        ) as tmp_in:
            tmp_in.write(
                dxf_bytes
            )
            tmp_in_path = (
                tmp_in.name
            )

        doc = ezdxf.readfile(
            tmp_in_path
        )

        msp = doc.modelspace()

        validar_camadas(
            msp,
            contexto="Geração do CAD"
        )

        camadas = {
            "PROJ_ELETRICA_LUZ": 2,
            "PROJ_ELETRICA_QDC": 1,
            "PROJ_ELETRICA_TEXTO": 2,
            "PROJ_ELETRICA_TOMADA": 4,
            "PROJ_ELETRICA_INTERRUPTOR": 5,
            "PROJ_ELETRICA_DEBUG": 6,
            "PROJ_ELETRICA_ELETRODUTO": 3,
            "PROJ_ELETRICA_ELETRODUTO_TEXTO": 3,
            "PROJ_ELETRICA_ROTEAMENTO": 3,
            "PROJ_ELETRICA_ROTEAMENTO_TEXTO": 3,
            "PROJ_ELETRICA_DIMENSIONAMENTO": 6,
            "PROJ_ELETRICA_COMANDO": 6,
            "PROJ_ELETRICA_UNIFILAR_QDC": 7,
            "PROJ_ELETRICA_UNIFILAR_QDC_TEXTO": 7,
            "PROJ_ELETRICA_MAPA_QDC": 7,
            "PROJ_ELETRICA_MAPA_QDC_TEXTO": 7,
            "PROJ_ELETRICA_QDC_FASE_A": 7,
            "PROJ_ELETRICA_QDC_FASE_B": 8,
            "PROJ_ELETRICA_QDC_FASE_C": 1,
            "PROJ_ELETRICA_QDC_NEUTRO": 5,
            "PROJ_ELETRICA_QDC_PE": 3,
            "PROJ_ELETRICA_QDC_PENTE": 30,
            "AE_VERSAO": 8
        }

        for nome_l, cor_l in camadas.items():
            if nome_l not in doc.layers:
                doc.layers.add(
                    name=nome_l,
                    color=cor_l
                )
            else:
                doc.layers.get(
                    nome_l
                ).color = cor_l

        elementos = ler_elementos(msp)

        polilinhas = elementos["polilinhas"]
        textos = elementos["textos"]
        portas_raw = elementos["portas_raw"]
        soleiras_raw = elementos["soleiras_raw"]

        # Limpa somente saídas antigas geradas pelo sistema
        for ent in list(msp):
            try:
                layer = str(
                    ent.dxf.layer
                ).upper().strip()

                if layer in {
                    "PROJ_ELETRICA_LUZ",
                    "PROJ_ELETRICA_QDC",
                    "PROJ_ELETRICA_TEXTO",
                    "PROJ_ELETRICA_TOMADA",
                    "PROJ_ELETRICA_INTERRUPTOR",
                    "PROJ_ELETRICA_DEBUG",
                    "PROJ_ELETRICA_ELETRODUTO",
                    "PROJ_ELETRICA_ELETRODUTO_TEXTO",
                    "PROJ_ELETRICA_ROTEAMENTO",
                    "PROJ_ELETRICA_ROTEAMENTO_TEXTO",
                    "PROJ_ELETRICA_COMANDO",
                    "PROJ_ELETRICA_UNIFILAR_QDC",
                    "PROJ_ELETRICA_UNIFILAR_QDC_TEXTO",
                    "PROJ_ELETRICA_MAPA_QDC",
                    "PROJ_ELETRICA_MAPA_QDC_TEXTO",
                    "PROJ_ELETRICA_QDC_FASE_A",
                    "PROJ_ELETRICA_QDC_FASE_B",
                    "PROJ_ELETRICA_QDC_FASE_C",
                    "PROJ_ELETRICA_QDC_NEUTRO",
                    "PROJ_ELETRICA_QDC_PE",
                    "PROJ_ELETRICA_QDC_PENTE",
                    "AE_VERSAO"
                }:
                    msp.delete_entity(ent)
            except Exception:
                pass

        # Identificador interno da fase dentro do próprio DXF. A camada
        # permanece congelada para não poluir a planta, mas permite auditar
        # qual versão efetivamente gerou o arquivo.
        try:
            layer_versao = doc.layers.get("AE_VERSAO")
            layer_versao.freeze()
        except Exception:
            pass
        msp.add_text(
            f"AutoEletrica {VERSAO_SISTEMA}",
            dxfattribs={"layer": "AE_VERSAO", "height": 0.05},
        ).set_placement((0.0, 0.0))

        # Interruptores
        pontos_interruptores = desenhar_interruptores(
            msp=msp,
            polilinhas=polilinhas,
            textos=textos,
            soleiras_raw=soleiras_raw,
            portas_raw=portas_raw,
            config_interruptores=(
                config_interruptores
                or {}
            )
        )

        ambientes_processados = {}
        ambientes_geom = []
        pontos_eletricos = []
        qdc_info = None

        dict_dados = {
            row["Ambiente"]:
                row
            for row in dados_editados
        }

        for polilinha in polilinhas:
            min_x, max_x, min_y, max_y = (
                bbox_poligono(
                    polilinha
                )
            )

            area = (
                (max_x - min_x)
                *
                (max_y - min_y)
            )

            if area < 0.5:
                continue

            nome = (
                nome_ambiente_para_polilinha(
                    polilinha,
                    textos
                )
            )

            if not nome:
                continue

            if nome in ambientes_processados:
                ambientes_processados[
                    nome
                ] += 1

                nome_busca = (
                    f"{nome} "
                    f"{ambientes_processados[nome]}"
                )

            else:
                ambientes_processados[
                    nome
                ] = 1

                nome_busca = nome

            row_data = dict_dados.get(
                nome_busca,
                dict_dados.get(
                    nome,
                    None
                )
            )

            # Fase 8.2:
            # centro operacional sempre DENTRO do ambiente.
            # Em geometrias côncavas/irregulares, o centro da bounding
            # box pode cair perto de um recorte ou até fora do polígono.
            centro_x, centro_y = (
                ponto_central_interno(
                    polilinha
                )
            )

            largura = (
                max_x - min_x
            )

            comprimento = (
                max_y - min_y
            )

            # Segmentos / paredes
            segmentos_crus = []
            comp_total = 0

            poly = list(
                polilinha
            )

            if poly[0] != poly[-1]:
                poly.append(
                    poly[0]
                )

            for i in range(
                len(poly) - 1
            ):
                dst = math.hypot(
                    poly[i + 1][0]
                    - poly[i][0],
                    poly[i + 1][1]
                    - poly[i][1]
                )

                if dst > 0.1:
                    segmentos_crus.append(
                        (
                            poly[i],
                            poly[i + 1],
                            dst
                        )
                    )

                    comp_total += dst

            # Fase 13.4 Rev.3 — a geometria do ambiente só pode ser
            # registrada depois que segmentos_crus e comp_total forem calculados.
            ambientes_geom.append({
                "nome": nome_busca,
                "nome_base": nome,
                "centro": (
                    ponto_central_interno(
                        polilinha
                    )
                ),
                "bbox": (
                    min_x,
                    max_x,
                    min_y,
                    max_y
                ),
                "polilinha": list(
                    polilinha
                ),
                "segmentos_crus": list(
                    segmentos_crus
                ),
                "comp_total": float(
                    comp_total
                ),
            })

            logical_walls = []

            for pt1, pt2, dst in (
                segmentos_crus
            ):
                logical_walls.append({
                    "p1": pt1,
                    "p2": pt2,
                    "length": dst,
                    "vx":
                        (
                            pt2[0] - pt1[0]
                        ) / dst,
                    "vy":
                        (
                            pt2[1] - pt1[1]
                        ) / dst
                })

            unique_portas = [
                p
                for p in portas_raw
                if (
                    min_x - 0.8
                    <= (
                        p["p1"][0]
                        + p["p2"][0]
                    ) / 2
                    <= max_x + 0.8
                    and
                    min_y - 0.8
                    <= (
                        p["p1"][1]
                        + p["p2"][1]
                    ) / 2
                    <= max_y + 0.8
                )
            ]

            # Iluminação
            if row_data:
                qtd_ilum = int(
                    row_data.get(
                        "Qtd Ilum.",
                        1
                    )
                )

                pot_ilum_unit = int(
                    row_data.get(
                        "Pot. Unit. Ilum (W)",
                        row_data.get(
                            "Pot. Unit. Ilum (VA)",
                            100
                        )
                    )
                )

                if qtd_ilum > 0:
                    # Fase 8.2:
                    # Em polígonos ortogonais irregulares (L/T/U),
                    # primeiro divide o ambiente em retângulos internos.
                    # Ex.: cozinha em L com 2 luminárias -> 1 em cada bloco.
                    pontos_luz = (
                        pontos_iluminacao_por_decomposicao(
                            polilinha,
                            qtd_ilum,
                            afastamento_minimo=
                                0.35
                        )
                    )

                    # Fallback para ambientes diagonais/orgânicos.
                    if not pontos_luz:
                        pontos_luz = (
                            pontos_iluminacao_internos(
                                polilinha,
                                qtd_ilum,
                                afastamento_minimo=
                                    0.35
                            )
                        )

                    for lx, ly in pontos_luz:
                        pontos_eletricos.append({
                            "ambiente": nome_busca,
                            "tipo": "ILUMINACAO",
                            "ponto": (lx, ly),
                            "potencia": pot_ilum_unit,
                        })

                        msp.add_circle(
                            center=(lx, ly),
                            radius=0.25,
                            dxfattribs={
                                "layer":
                                    "PROJ_ELETRICA_LUZ"
                            }
                        )

                        msp.add_text(
                            f"{pot_ilum_unit}W",
                            dxfattribs={
                                "layer":
                                    "PROJ_ELETRICA_TEXTO",
                                "height":
                                    0.15,
                                "insert":
                                    (
                                        lx + 0.3,
                                        ly - 0.07
                                    )
                            }
                        )

                        msp.add_text(
                            "a",
                            dxfattribs={
                                "layer":
                                    "PROJ_ELETRICA_TEXTO",
                                "height":
                                    0.15,
                                "color":
                                    2,
                                "insert":
                                    (
                                        lx + 0.3,
                                        ly + 0.15
                                    )
                            }
                        )

            # QDC
            qdc_resultado = desenhar_qdc(
                msp=msp,
                logical_walls=logical_walls,
                unique_portas=unique_portas,
                local_qdc=local_qdc,
                nome=nome,
                centro_x=centro_x,
                centro_y=centro_y,
                polilinhas_ambientes=polilinhas
            )

            if qdc_resultado:
                qdc_info = qdc_resultado

            # Tomadas
            pontos_tomadas = desenhar_tomadas(
                msp=msp,
                row_data=row_data,
                # Fase 13.4 Rev.3:
                # usar o identificador único do ambiente (ex.: "WC 2")
                # também dentro da lógica de tomadas.
                nome=nome_busca,
                polilinha=polilinha,
                logical_walls=logical_walls,
                segmentos_crus=segmentos_crus,
                comp_total=comp_total,
                unique_portas=unique_portas,
                portas_raw=portas_raw,
                soleiras_raw=soleiras_raw,
                centro_x=centro_x,
                centro_y=centro_y,
                config_tomadas_altas=(
                    (
                        config_interruptores
                        or {}
                    ).get(
                        "__tomadas_altas__",
                        {}
                    )
                ),
                pontos_interruptores=(
                    pontos_interruptores
                )
            )

            if pontos_tomadas:
                for ponto in pontos_tomadas:
                    # Garante o identificador único do ambiente também
                    # para a futura distribuição de circuitos.
                    ponto["ambiente"] = nome_busca
                    pontos_eletricos.append(ponto)

        # ====================================================
        # FASE 13.4 REV.3 — REDE TRONCAL HÍBRIDA + TODAS AS LUMINÁRIAS
        # ====================================================
        # A rede antiga permanece desativada. A partir desta fase o CAD usa
        # um novo roteamento, baseado nos circuitos consolidados.
        _, circuitos_unifilar = calcular_quantitativo_materiais(
            tabela_editada=dados_editados,
            config_interruptores_usuario=(config_interruptores or {}),
            local_qdc=local_qdc,
            tensao_projeto=tensao_projeto,
            pe_direito=pe_direito
        )

        parametros_rede_unifilar = (
            (config_interruptores or {}).get(
                CHAVE_PARAMETROS_REDE,
                {}
            )
        )

        resultado_demanda_unifilar = calcular_demanda_qdc(
            dados_editados,
            parametros_rede_unifilar
        )

        circuitos_unifilar, resumo_balanceamento_unifilar = (
            balancear_circuitos(
                circuitos_unifilar,
                parametros_rede_unifilar
            )
        )

        circuitos_unifilar, resumo_drs_unifilar = (
            agrupar_circuitos_dr(
                circuitos_unifilar,
                resultado_demanda_unifilar.get(
                    "disjuntor_geral_a"
                )
            )
        )

        resumo_protecao_unifilar = avaliar_protecoes_alimentador(
            resultado_demanda_unifilar,
            parametros_rede_unifilar,
            circuitos_unifilar,
            resumo_drs_unifilar
        )

        # ====================================================
        # FASE 13.4 REV.3 — DIMENSIONAMENTO ITERATIVO AUTOMÁTICO
        # ====================================================
        # O ciclo fecha quatro critérios:
        #   rota física -> queda -> capacidade -> ocupação/rerota.
        # Se a seção mudar, o roteamento é recalculado com a nova bitola.
        # O ciclo termina quando nenhuma seção muda ou ao atingir o limite
        # de segurança de iterações.
        circuitos_dimensionados = [
            dict(c)
            for c in circuitos_unifilar
        ]

        historico_iteracoes = []
        relatorio_queda_final = []
        relatorio_capacidade_final = []
        correcoes_queda_acumuladas = {}
        correcoes_capacidade_acumuladas = {}
        resumo_rotas = None
        rotas_fisicas = []
        convergiu = False

        MAX_ITERACOES_DIMENSIONAMENTO = 6

        for iteracao in range(
            1,
            MAX_ITERACOES_DIMENSIONAMENTO + 1
        ):
            # Remove apenas o traçado da iteração anterior.
            for entidade in list(msp):
                if str(
                    entidade.dxf.layer
                ).upper().strip() in {
                    "PROJ_ELETRICA_ROTEAMENTO",
                    "PROJ_ELETRICA_ROTEAMENTO_TEXTO",
                    "PROJ_ELETRICA_DIMENSIONAMENTO",
                }:
                    msp.delete_entity(
                        entidade
                    )

            bitolas_antes = {
                int(c.get("numero", 0) or 0):
                    float(c.get("bitola", 0.0) or 0.0)
                for c in circuitos_dimensionados
                if int(c.get("numero", 0) or 0) > 0
            }

            rotas_fisicas = desenhar_rotas_qdc_iluminacao(
                msp=msp,
                qdc_info=qdc_info,
                pontos_eletricos=pontos_eletricos,
                circuitos=circuitos_dimensionados,
                pontos_interruptores=pontos_interruptores,
                ambientes_geom=ambientes_geom,
                portas_raw=portas_raw,
                soleiras_raw=soleiras_raw,
            )

            (
                circuitos_pos_queda,
                relatorio_queda
            ) = corrigir_bitolas_por_queda(
                rotas_fisicas,
                circuitos_dimensionados
            )

            resumo_intermediario = dimensionar_rotas(
                rotas_fisicas,
                circuitos_pos_queda
            )

            diagnostico_intermediario = (
                diagnosticar_agrupamento_rotas(
                    resumo_intermediario,
                    circuitos_pos_queda
                )
            )

            (
                circuitos_pos_capacidade,
                relatorio_capacidade
            ) = corrigir_bitolas_por_capacidade(
                diagnostico_intermediario,
                circuitos_pos_queda,
                metodo_instalacao=metodo_instalacao,
                temperatura_ambiente_c=temperatura_ambiente_c
            )

            for item in relatorio_queda:
                numero_corr = int(
                    item.get(
                        "numero",
                        0
                    )
                    or 0
                )

                if (
                    numero_corr > 0
                    and item.get(
                        "status"
                    )
                    == "CORRIGIDA"
                ):
                    anterior = correcoes_queda_acumuladas.get(
                        numero_corr
                    )

                    if anterior is None:
                        correcoes_queda_acumuladas[
                            numero_corr
                        ] = dict(
                            item
                        )
                    else:
                        anterior[
                            "bitola_final_mm2"
                        ] = item.get(
                            "bitola_final_mm2"
                        )
                        anterior[
                            "queda_depois_pct"
                        ] = item.get(
                            "queda_depois_pct"
                        )

            for item in relatorio_capacidade:
                numero_corr = int(
                    item.get(
                        "numero",
                        0
                    )
                    or 0
                )

                if (
                    numero_corr > 0
                    and item.get(
                        "status"
                    )
                    == "CORRIGIDA"
                ):
                    anterior = correcoes_capacidade_acumuladas.get(
                        numero_corr
                    )

                    if anterior is None:
                        correcoes_capacidade_acumuladas[
                            numero_corr
                        ] = dict(
                            item
                        )
                    else:
                        anterior[
                            "bitola_final_mm2"
                        ] = item.get(
                            "bitola_final_mm2"
                        )
                        anterior[
                            "iz_recomendada_a"
                        ] = item.get(
                            "iz_recomendada_a"
                        )

            bitolas_depois = {
                int(c.get("numero", 0) or 0):
                    float(c.get("bitola", 0.0) or 0.0)
                for c in circuitos_pos_capacidade
                if int(c.get("numero", 0) or 0) > 0
            }

            alteracoes = []

            for numero, depois in bitolas_depois.items():
                antes = bitolas_antes.get(
                    numero,
                    depois
                )

                if depois > antes + 1e-9:
                    alteracoes.append({
                        "numero":
                            numero,
                        "bitola_antes_mm2":
                            antes,
                        "bitola_depois_mm2":
                            depois,
                    })

            historico_iteracoes.append({
                "iteracao":
                    iteracao,
                "qtd_alteracoes_bitola":
                    len(
                        alteracoes
                    ),
                "alteracoes":
                    alteracoes,
                "qtd_trechos":
                    len(
                        rotas_fisicas
                    ),
            })

            circuitos_dimensionados = [
                dict(c)
                for c in circuitos_pos_capacidade
            ]

            relatorio_queda_final = relatorio_queda
            relatorio_capacidade_final = relatorio_capacidade

            if not alteracoes:
                convergiu = True

                # A rota desenhada nesta iteração já usa as bitolas finais.
                resumo_rotas = dimensionar_rotas(
                    rotas_fisicas,
                    circuitos_dimensionados
                )

                diagnostico_final = (
                    diagnosticar_agrupamento_rotas(
                        resumo_rotas,
                        circuitos_dimensionados
                    )
                )

                capacidade_final = (
                    verificar_capacidade_conducao_preliminar(
                        diagnostico_final,
                        circuitos_dimensionados,
                        metodo_instalacao=metodo_instalacao,
                        temperatura_ambiente_c=temperatura_ambiente_c
                    )
                )

                resumo_rotas[
                    "diagnostico_agrupamento"
                ] = diagnostico_final

                resumo_rotas[
                    "capacidade_conducao_preliminar"
                ] = capacidade_final

                break

        if resumo_rotas is None:
            # Limite de iterações atingido: redesenha uma última vez com
            # as seções finais conhecidas para manter CAD e resumo coerentes.
            for entidade in list(msp):
                if str(
                    entidade.dxf.layer
                ).upper().strip() in {
                    "PROJ_ELETRICA_ROTEAMENTO",
                    "PROJ_ELETRICA_ROTEAMENTO_TEXTO",
                    "PROJ_ELETRICA_DIMENSIONAMENTO",
                }:
                    msp.delete_entity(
                        entidade
                    )

            rotas_fisicas = desenhar_rotas_qdc_iluminacao(
                msp=msp,
                qdc_info=qdc_info,
                pontos_eletricos=pontos_eletricos,
                circuitos=circuitos_dimensionados,
                pontos_interruptores=pontos_interruptores,
                ambientes_geom=ambientes_geom,
                portas_raw=portas_raw,
                soleiras_raw=soleiras_raw,
            )

            resumo_rotas = dimensionar_rotas(
                rotas_fisicas,
                circuitos_dimensionados
            )

            diagnostico_final = diagnosticar_agrupamento_rotas(
                resumo_rotas,
                circuitos_dimensionados
            )

            capacidade_final = (
                verificar_capacidade_conducao_preliminar(
                    diagnostico_final,
                    circuitos_dimensionados,
                    metodo_instalacao=metodo_instalacao,
                    temperatura_ambiente_c=temperatura_ambiente_c
                )
            )

            resumo_rotas[
                "diagnostico_agrupamento"
            ] = diagnostico_final

            resumo_rotas[
                "capacidade_conducao_preliminar"
            ] = capacidade_final

        resumo_rotas[
            "correcoes_bitola"
        ] = list(
            correcoes_queda_acumuladas.values()
        )

        resumo_rotas[
            "correcoes_capacidade"
        ] = list(
            correcoes_capacidade_acumuladas.values()
        )

        resumo_rotas[
            "circuitos_corrigidos"
        ] = circuitos_dimensionados

        resumo_rotas[
            "circuitos_dimensionados_finais"
        ] = circuitos_dimensionados

        resumo_rotas[
            "dimensionamento_iterativo"
        ] = {
            "status":
                (
                    "CONVERGIU"
                    if convergiu
                    else "LIMITE_DE_ITERACOES"
                ),
            "iteracoes":
                len(
                    historico_iteracoes
                ),
            "metodo_instalacao":
                metodo_instalacao,
            "temperatura_ambiente_c":
                temperatura_ambiente_c,
            "historico":
                historico_iteracoes,
        }

        resumo_rotas[
            "validacao_eletrica"
        ] = validar_eletrica_rotas(
            resumo_rotas,
            circuitos_dimensionados
        )

        resumo_rotas[
            "validacao_ib_in_iz"
        ] = validar_relacao_ib_in_iz(
            resumo_rotas.get(
                "capacidade_conducao_preliminar",
                {}
            ),
            circuitos_dimensionados
        )

        # Etiquetas de auditoria: Ø do eletroduto e circuitos por trecho.
        # Ficam em camada congelada para manter a planta limpa.
        desenhar_dimensionamento_rotas(
            msp,
            resumo_rotas,
            layer="PROJ_ELETRICA_DIMENSIONAMENTO"
        )

        try:
            layer_dim = doc.layers.get(
                "PROJ_ELETRICA_DIMENSIONAMENTO"
            )
            layer_dim.freeze()
        except Exception:
            pass

        # As camadas legadas continuam removidas para não misturar o
        # roteamento antigo com a nova rede da Fase 11.
        camadas_ocultar = {
            "PROJ_ELETRICA_ELETRODUTO",
            "PROJ_ELETRICA_ELETRODUTO_TEXTO",
            "PROJ_ELETRICA_COMANDO"
        }
        for entidade in list(msp):
            if entidade.dxf.layer in camadas_ocultar:
                msp.delete_entity(entidade)


        desenhar_unifilar_qdc(
            msp=msp,
            circuitos=circuitos_dimensionados,
            polilinhas_ambientes=polilinhas,
            tensao_projeto=tensao_projeto,
            parametros_rede=parametros_rede_unifilar,
            resultado_demanda=resultado_demanda_unifilar,
            resumo_balanceamento=resumo_balanceamento_unifilar,
            resumo_drs=resumo_drs_unifilar,
            resumo_protecao=resumo_protecao_unifilar
        )

        mapa_fisico_qdc = gerar_mapa_fisico_qdc(
            circuitos_dimensionados,
            resumo_drs_unifilar,
            resumo_protecao_unifilar,
            resultado_demanda_unifilar
        )

        desenhar_mapa_fisico_qdc(
            msp,
            mapa_fisico_qdc,
            polilinhas
        )

        doc.saveas(
            tmp_in_path
        )

        with open(
            tmp_in_path,
            "rb"
        ) as f:
            out_bytes = f.read()

        if retornar_resumo_rotas:
            return (
                out_bytes,
                resumo_rotas
            )

        return out_bytes

    finally:
        if (
            tmp_in_path
            and os.path.exists(
                tmp_in_path
            )
        ):
            os.remove(
                tmp_in_path
            )
