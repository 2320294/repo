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

from materiais import (
    calcular_quantitativo_materiais
)

from unifilar_qdc import (
    desenhar_unifilar_qdc
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
    pe_direito=2.80
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
            "PROJ_ELETRICA_COMANDO": 6,
            "PROJ_ELETRICA_UNIFILAR_QDC": 7,
            "PROJ_ELETRICA_UNIFILAR_QDC_TEXTO": 7,
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

            ambientes_geom.append({
                "nome": nome_busca,
                "nome_base": nome,
                "centro": (
                    ponto_central_interno(
                        polilinha
                    )
                ),
                "bbox": (min_x, max_x, min_y, max_y),
                "polilinha": list(polilinha),
            })

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
                # Fase 11.2:
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
                )
            )

            if pontos_tomadas:
                for ponto in pontos_tomadas:
                    # Garante o identificador único do ambiente também
                    # para a futura distribuição de circuitos.
                    ponto["ambiente"] = nome_busca
                    pontos_eletricos.append(ponto)

        # ====================================================
        # FASE 11.2 — REDE TRONCAL COMPARTILHADA
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

        # Rede física compartilhada:
        # QDC -> árvore troncal -> pontos de iluminação/distribuição.
        # Cada trecho físico é desenhado uma única vez, mesmo quando
        # transporta vários circuitos. Somente entidades ARC.
        desenhar_rotas_qdc_iluminacao(
            msp=msp,
            qdc_info=qdc_info,
            pontos_eletricos=pontos_eletricos,
            circuitos=circuitos_unifilar,
        )

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
            circuitos=circuitos_unifilar,
            polilinhas_ambientes=polilinhas,
            tensao_projeto=tensao_projeto,
            parametros_rede=parametros_rede_unifilar,
            resultado_demanda=resultado_demanda_unifilar,
            resumo_balanceamento=resumo_balanceamento_unifilar,
            resumo_drs=resumo_drs_unifilar,
            resumo_protecao=resumo_protecao_unifilar
        )

        doc.saveas(
            tmp_in_path
        )

        with open(
            tmp_in_path,
            "rb"
        ) as f:
            out_bytes = f.read()

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
