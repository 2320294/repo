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
    pontos_iluminacao_internos
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


def gerar_cad_unifilar(
    dxf_bytes,
    dados_editados,
    local_qdc,
    config_interruptores=None
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
            "PROJ_ELETRICA_COMANDO": 6,
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
                    "PROJ_ELETRICA_COMANDO",
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

            # Fase 8.1:
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
                    # Fase 8.1:
                    # usa o interior real do ambiente, inclusive em
                    # polígonos côncavos e geometrias em L.
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
                centro_y=centro_y
            )

            if qdc_resultado:
                qdc_info = qdc_resultado

            # Tomadas
            pontos_tomadas = desenhar_tomadas(
                msp=msp,
                row_data=row_data,
                nome=nome,
                polilinha=polilinha,
                logical_walls=logical_walls,
                segmentos_crus=segmentos_crus,
                comp_total=comp_total,
                unique_portas=unique_portas,
                portas_raw=portas_raw,
                soleiras_raw=soleiras_raw,
                centro_x=centro_x,
                centro_y=centro_y
            )

            if pontos_tomadas:
                # A função de tomadas usa o nome base recebido; normalizamos
                # para o mesmo identificador empregado em dados_editados.
                for ponto in pontos_tomadas:
                    ponto["ambiente"] = nome_busca
                    pontos_eletricos.append(ponto)

        # Rede física/simbólica de eletrodutos / circuitos
        desenhar_rede_eletrodutos(
            msp=msp,
            dados_editados=dados_editados,
            ambientes_geom=ambientes_geom,
            qdc_info=qdc_info,
            pontos_eletricos=pontos_eletricos,
            soleiras_raw=soleiras_raw,
            pontos_interruptores=pontos_interruptores,
        )

        # Fase 8.1: limpar conduítes/comandos para foco nos pontos elétricos.
        camadas_ocultar = {"PROJ_ELETRICA_ELETRODUTO", "PROJ_ELETRICA_ELETRODUTO_TEXTO", "PROJ_ELETRICA_COMANDO"}
        for entidade in list(msp):
            if entidade.dxf.layer in camadas_ocultar:
                msp.delete_entity(entidade)
        
        
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
