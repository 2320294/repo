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

from qdc_auditoria import (
    auditar_qdc_normativo
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



def _normalizar_rotulo_unifilar(txt):
    import unicodedata
    base = unicodedata.normalize("NFKD", str(txt or ""))
    return " ".join("".join(c for c in base if not unicodedata.combining(c)).upper().split())


def _bitola_txt_unifilar(valor):
    try:
        v = float(valor or 0.0)
    except (TypeError, ValueError):
        v = 0.0
    if v <= 0:
        return ""
    return (f"{v:.1f}".replace(".", ",") if v % 1 else f"{int(v)}")


def _linha_vetorial(msp, p1, p2, layer="PROJ_ELETRICA_TEXTO"):
    msp.add_line(tuple(p1), tuple(p2), dxfattribs={"layer": layer})


def _simbolo_condutor_unifilar(msp, centro, tangente, normal, tipo, escala=0.085):
    """Desenha a convenção gráfica de condutor sobre o eletroduto.

    Referência visual adotada na Rev.111:
      F = traço transversal completo;
      N = traço transversal com pequeno gancho superior;
      R = traço transversal somente para um lado do eletroduto;
      PE = traço transversal com barra no topo (T).
    O símbolo é rotacionado automaticamente para ficar transversal ao trecho.
    """
    cx, cy = centro
    ux, uy = tangente
    nx, ny = normal
    def pt(du=0.0, dn=0.0):
        return (cx + ux*du + nx*dn, cy + uy*du + ny*dn)

    tipo = str(tipo or "F").upper()
    if tipo == "F":
        _linha_vetorial(msp, pt(0, -escala), pt(0, escala))
    elif tipo == "N":
        _linha_vetorial(msp, pt(0, -escala*0.55), pt(0, escala))
        _linha_vetorial(msp, pt(0, escala), pt(-escala*0.55, escala))
    elif tipo == "R":
        _linha_vetorial(msp, pt(0, 0), pt(0, escala))
    elif tipo == "PE":
        _linha_vetorial(msp, pt(0, -escala*0.35), pt(0, escala))
        _linha_vetorial(msp, pt(-escala*0.55, escala), pt(escala*0.55, escala))


def _condutores_circuito_unifilar(circuito, criterio=""):
    """Retorna somente os condutores representáveis com os dados do projeto."""
    tipo = str(circuito.get("tipo", "") or "").upper()
    criterio = str(criterio or "").upper()
    fase = str(circuito.get("fase", circuito.get("fases", "")) or "").upper()
    try:
        polos = int(circuito.get("polos", 0) or 0)
    except (TypeError, ValueError):
        polos = 0

    # Ramais de comando de iluminação.
    # Rev.117: three-way representado pela topologia física real.
    if tipo.startswith("ILUM"):
        if criterio in {
            "LUZ_PARA_INTERRUPTOR",
            "INTERRUPTOR_CONTROLADOR_PARA_ILUMINACAO_EXTERNA",
        }:
            return ["F", "R", "PE"]
        if criterio == "LUZ_PARA_INTERRUPTOR_PARALELO_1":
            return ["F", "R", "R"]
        if criterio == "INTERRUPTOR_PARA_INTERRUPTOR_PARALELO":
            return ["R", "R"]
        if criterio == "LUZ_PARA_INTERRUPTOR_PARALELO_2":
            # Rev.117: 2 viajantes + 1 retorno no eletroduto que liga a
            # caixa da luminária ao segundo interruptor paralelo.
            return ["R", "R", "R"]
        if criterio == "INTERRUPTOR_PARA_LUZ_PARALELO_2":
            # Compatibilidade com rotas antigas da Rev.117.
            return ["R"]
        if criterio in {
            "LUZ_PARA_INTERRUPTOR_PARALELO",
            "LUZ_PARA_INTERRUPTOR_PARALELO_EXTRA",
        }:
            return ["F", "R", "PE"]

    bifasico = polos >= 2 or any(sep in fase for sep in ("-", "/", "+"))
    return ["F", "F", "PE"] if bifasico else ["F", "N", "PE"]


def _descricao_condutores_unifilar(circuito, criterio=""):
    conds = _condutores_circuito_unifilar(circuito, criterio)
    return "+".join(conds)


def _criterio_legenda_unifilar(criterio):
    mapa = {
        "LUZ_PARA_INTERRUPTOR": "Iluminacao -> interruptor",
        "LUZ_PARA_INTERRUPTOR_PARALELO": "Iluminacao -> interruptor paralelo",
        "LUZ_PARA_INTERRUPTOR_PARALELO_1": "Luminaria -> 1o interruptor paralelo",
        "LUZ_PARA_INTERRUPTOR_PARALELO_2": "Luminaria -> 2o interruptor paralelo",
        "INTERRUPTOR_PARA_INTERRUPTOR_PARALELO": "1o -> 2o interruptor paralelo",
        "INTERRUPTOR_PARA_LUZ_PARALELO_2": "2o interruptor paralelo -> luminaria",
        "LUZ_PARA_INTERRUPTOR_PARALELO_EXTRA": "Luminaria -> interruptor paralelo extra",
        "LUZ_PARA_INTERRUPTOR_TUG": "Passagem TUG: luminaria -> caixa do interruptor",
        "INTERRUPTOR_CONTROLADOR_PARA_ILUMINACAO_EXTERNA": "Comando de iluminacao externa",
        "QDC_PARA_ILUMINACAO": "QDC -> iluminacao",
        "QDC_PARA_LUZ": "QDC -> iluminacao",
        "ILUMINACAO_PARA_TOMADA": "Iluminacao -> tomada",
        "TOMADA_PARA_TOMADA": "Tomada -> tomada",
        "TUE": "Circuito dedicado TUE",
    }
    chave = str(criterio or "").upper().strip()
    return mapa.get(chave, chave.replace("_", " ").title() if chave else "Trecho de eletroduto")


def _ponto_real_rota_unifilar(msp, rota):
    """Rev.112: devolve ponto e direção SOBRE a geometria física do eletroduto.

    A Rev.111 usava o meio da corda inicio-fim. Em eletrodutos desenhados como
    ARC, esse ponto não pertence ao arco e a chamada parecia flutuar.
    Agora a posição é calculada na entidade DXF efetivamente desenhada.
    """
    handle = rota.get("handle_entidade")
    entidade = None
    try:
        if handle:
            entidade = msp.doc.entitydb.get(str(handle))
    except Exception:
        entidade = None

    if entidade is not None:
        tipo = str(entidade.dxftype()).upper()

        if tipo == "ARC":
            try:
                cx, cy = float(entidade.dxf.center.x), float(entidade.dxf.center.y)
                r = float(entidade.dxf.radius)
                a1 = float(entidade.dxf.start_angle) % 360.0
                a2 = float(entidade.dxf.end_angle) % 360.0
                delta = (a2 - a1) % 360.0
                am = math.radians((a1 + delta * 0.5) % 360.0)
                ponto = (cx + r * math.cos(am), cy + r * math.sin(am))
                # Tangente ao arco no sentido CCW; para a chamada apenas a
                # perpendicular importa, portanto o sentido não altera a ancoragem.
                tang = (-math.sin(am), math.cos(am))
                normal = (-tang[1], tang[0])
                return ponto, tang, normal
            except Exception:
                pass

        if tipo == "LWPOLYLINE":
            try:
                pts = [(float(v[0]), float(v[1])) for v in entidade.get_points("xy")]
                if len(pts) >= 2:
                    segs=[]
                    total=0.0
                    for a,b in zip(pts[:-1],pts[1:]):
                        d=math.hypot(b[0]-a[0], b[1]-a[1])
                        if d>1e-9:
                            segs.append((a,b,d))
                            total += d
                    alvo=total*0.5
                    acum=0.0
                    for a,b,d in segs:
                        if acum+d >= alvo:
                            f=(alvo-acum)/d
                            ponto=(a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f)
                            tang=((b[0]-a[0])/d,(b[1]-a[1])/d)
                            normal=(-tang[1],tang[0])
                            return ponto,tang,normal
                        acum += d
            except Exception:
                pass

    # Fallback seguro para arquivos/rotas antigas sem handle.
    p1, p2 = rota.get("inicio"), rota.get("fim")
    if not p1 or not p2:
        return None
    dx=float(p2[0])-float(p1[0])
    dy=float(p2[1])-float(p1[1])
    comp=math.hypot(dx,dy)
    if comp < 1e-9:
        return None
    tang=(dx/comp,dy/comp)
    normal=(-tang[1],tang[0])
    ponto=((float(p1[0])+float(p2[0]))/2.0,(float(p1[1])+float(p2[1]))/2.0)
    return ponto,tang,normal



def _bbox_balao_unifilar(cx, cy, raio=0.10, folga=0.05):
    """Retorna a caixa de ocupação visual do balão, com folga anti-colisão."""
    r = float(raio) + float(folga)
    return (cx-r, cy-r, cx+r, cy+r)


def _bbox_intersecta_unifilar(a, b):
    return not (
        a[2] < b[0] or a[0] > b[2] or
        a[3] < b[1] or a[1] > b[3]
    )


def _desenhar_quadro_chamada_unifilar(
    msp,
    ponto,
    tangente,
    normal,
    numero,
    ocupados=None,
    indice_chamada=0,
):
    """Rev.117: balão circular numerado com anti-colisão e leader preso ao eletroduto.

    Regras:
    - o leader SEMPRE nasce no ponto real do eletroduto;
    - chamadas próximas alternam os lados do eletroduto;
    - antes de desenhar, a posição é testada contra todos os balões já criados;
    - se houver colisão, o balão caminha ao longo da tangente até encontrar espaço;
    - a ponta do leader termina na circunferência, nunca no centro.
    """
    if ocupados is None:
        ocupados = []

    ax, ay = float(ponto[0]), float(ponto[1])
    ux, uy = float(tangente[0]), float(tangente[1])
    nx, ny = float(normal[0]), float(normal[1])

    # Normaliza vetores para manter distâncias métricas reais.
    ct = math.hypot(ux, uy)
    cn = math.hypot(nx, ny)
    if ct > 1e-9:
        ux, uy = ux/ct, uy/ct
    if cn > 1e-9:
        nx, ny = nx/cn, ny/cn

    raio = 0.10
    folga = 0.055
    distancia_normal = 0.23
    layer = "PROJ_ELETRICA_TEXTO"

    # Alternância principal: 1ª para um lado, 2ª para o outro etc.
    lado_preferido = 1.0 if (int(indice_chamada) % 2 == 0) else -1.0

    # Deslocamentos progressivos ao longo do eletroduto.
    # Primeiro tenta exatamente no ponto de referência; depois abre para os lados.
    offsets_tang = [0.0, 0.22, -0.22, 0.44, -0.44, 0.66, -0.66, 0.88, -0.88]

    escolhido = None
    for tentativa_lado in (lado_preferido, -lado_preferido):
        for off in offsets_tang:
            bx = ax + ux*off + nx*distancia_normal*tentativa_lado
            by = ay + uy*off + ny*distancia_normal*tentativa_lado
            bb = _bbox_balao_unifilar(bx, by, raio, folga)
            if not any(_bbox_intersecta_unifilar(bb, existente) for existente in ocupados):
                escolhido = (bx, by, bb)
                break
        if escolhido:
            break

    # Fallback: continua afastando ao longo da tangente até achar posição livre.
    if escolhido is None:
        passo = 0.22
        k = 5
        while k < 30 and escolhido is None:
            off = passo * k
            for sinal in (1.0, -1.0):
                bx = ax + ux*off*sinal + nx*distancia_normal*lado_preferido
                by = ay + uy*off*sinal + ny*distancia_normal*lado_preferido
                bb = _bbox_balao_unifilar(bx, by, raio, folga)
                if not any(_bbox_intersecta_unifilar(bb, existente) for existente in ocupados):
                    escolhido = (bx, by, bb)
                    break
            k += 1

    if escolhido is None:
        bx = ax + nx*distancia_normal*lado_preferido
        by = ay + ny*distancia_normal*lado_preferido
        bb = _bbox_balao_unifilar(bx, by, raio, folga)
    else:
        bx, by, bb = escolhido

    ocupados.append(bb)

    # Leader: ponta inicial exatamente sobre o eletroduto; ponta final na circunferência.
    vx, vy = ax-bx, ay-by
    d = math.hypot(vx, vy)
    if d > 1e-9:
        ex = bx + vx/d * raio
        ey = by + vy/d * raio
    else:
        ex, ey = bx, by

    msp.add_line((ax, ay), (ex, ey), dxfattribs={"layer": layer})
    msp.add_circle((bx, by), raio, dxfattribs={"layer": layer})

    txt = msp.add_text(
        str(numero),
        dxfattribs={"layer": layer, "height": 0.085, "insert": (bx, by)},
    )
    try:
        txt.set_placement((bx, by), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    except Exception:
        pass


def _desenhar_tabela_legenda_condutos_unifilar(msp, registros, ambientes_geom):
    """Rev.117: LEGENDA DE FIAÇÃO gráfica, compacta e baseada na referência do usuário.

    Em vez de repetir textos longos, cada linha mostra:
      - balão circular numerado;
      - linha horizontal representando o trecho;
      - grupos gráficos dos condutores;
      - número do circuito acima;
      - seção em mm² abaixo.
    """
    if not registros:
        return

    bboxes = [a.get("bbox") for a in (ambientes_geom or []) if a.get("bbox")]
    if bboxes:
        min_x = min(b[0] for b in bboxes)
        max_x = max(b[1] for b in bboxes)
        min_y = min(b[2] for b in bboxes)
    else:
        min_x, max_x, min_y = 0.0, 12.0, 0.0

    layer = "PROJ_ELETRICA_TEXTO"

    # Fase 13.6 Rev.117 — dimensões automáticas por conteúdo.
    # A legenda deixa de herdar a largura da planta: cresce somente quando a
    # quantidade de circuitos/condutores daquela linha realmente exigir.
    x0 = min_x

    def _largura_texto_rev117(texto, altura, fator=0.62):
        return max(0.0, len(str(texto or "")) * float(altura) * float(fator))

    def _largura_grupo_rev117(grupo):
        conds = grupo.get("condutores") or []
        bit = str(grupo.get("bitola") or "-")
        circ = str(grupo.get("circuito") or "").replace("C", "")
        largura_cond = max(0.19, (max(1, len(conds)) - 1) * 0.115 + 0.19)
        largura_circ = _largura_texto_rev117(circ, 0.10)
        largura_bit = _largura_texto_rev117(f"{bit} mm²", 0.085)
        return max(0.48, largura_cond, largura_circ, largura_bit) + 0.22

    largura_num = max(0.62, _largura_texto_rev117("Nº", 0.11) + 0.26)
    largura_header_fiacao = _largura_texto_rev117("FIAÇÃO DO TRECHO", 0.11) + 0.50
    largura_conteudo_fiacao = 0.0
    for _reg_rev117 in registros:
        _grupos_rev117 = _reg_rev117.get("grupos") or []
        if not _grupos_rev117:
            largura_conteudo_fiacao = max(largura_conteudo_fiacao, 1.80)
            continue
        _larguras_rev117 = [_largura_grupo_rev117(g) for g in _grupos_rev117]
        _pacote_rev117 = sum(_larguras_rev117) + max(0, len(_larguras_rev117)-1) * 0.14
        largura_conteudo_fiacao = max(largura_conteudo_fiacao, _pacote_rev117 + 0.65)

    largura_fiacao = max(2.80, largura_header_fiacao, largura_conteudo_fiacao)
    largura = largura_num + largura_fiacao
    h_titulo = 0.50
    h_header = 0.42
    h_linha = 0.72
    altura = h_titulo + h_header + len(registros)*h_linha
    y_top = min_y - 0.70
    y_bot = y_top - altura

    def linha(p1, p2):
        msp.add_line(p1, p2, dxfattribs={"layer": layer})

    # Moldura
    linha((x0, y_top), (x0+largura, y_top))
    linha((x0, y_bot), (x0+largura, y_bot))
    linha((x0, y_top), (x0, y_bot))
    linha((x0+largura, y_top), (x0+largura, y_bot))

    # Título
    t = msp.add_text(
        "LEGENDA DE FIAÇÃO",
        dxfattribs={"layer": layer, "height": 0.18, "insert": (x0+largura/2, y_top-0.28)}
    )
    try:
        t.set_placement((x0+largura/2, y_top-0.28),
                        align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    except Exception:
        pass

    y_titulo_inf = y_top-h_titulo
    y_header_inf = y_titulo_inf-h_header
    x_sep = x0+largura_num

    linha((x0, y_titulo_inf), (x0+largura, y_titulo_inf))
    linha((x0, y_header_inf), (x0+largura, y_header_inf))
    linha((x_sep, y_titulo_inf), (x_sep, y_bot))

    h1 = msp.add_text("Nº", dxfattribs={"layer": layer, "height": 0.11,
                                        "insert": (x0+largura_num/2, y_titulo_inf-0.22)})
    h2 = msp.add_text("FIAÇÃO DO TRECHO", dxfattribs={"layer": layer, "height": 0.11,
                                                     "insert": (x_sep+largura_fiacao/2, y_titulo_inf-0.22)})
    for obj, pt in [(h1, (x0+largura_num/2, y_titulo_inf-0.22)),
                    (h2, (x_sep+largura_fiacao/2, y_titulo_inf-0.22))]:
        try:
            obj.set_placement(pt, align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        except Exception:
            pass

    for idx, reg in enumerate(registros):
        y_sup = y_header_inf - idx*h_linha
        y_inf = y_sup - h_linha
        yc = (y_sup+y_inf)/2.0
        linha((x0, y_inf), (x0+largura, y_inf))

        # Balão da legenda
        bx = x0 + largura_num/2.0
        msp.add_circle((bx, yc), 0.16, dxfattribs={"layer": layer})
        txt = msp.add_text(str(reg["numero"]), dxfattribs={
            "layer": layer, "height": 0.11, "insert": (bx, yc)
        })
        try:
            txt.set_placement((bx, yc), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        except Exception:
            pass

        # Linha base da fiação
        xa = x_sep + 0.28
        xb = x0 + largura - 0.20
        linha((xa, yc), (xb, yc))

        grupos = reg.get("grupos") or []
        if not grupos:
            continue

        # Fase 13.6 Rev.117 — cada grupo ocupa exatamente o espaço necessário
        # para número do circuito, símbolos dos condutores e bitola. O conjunto
        # é centralizado na linha, eliminando grandes vazios entre grupos.
        larguras_grupos = [_largura_grupo_rev117(g) for g in grupos]
        gap_grupos = 0.14
        largura_pacote = sum(larguras_grupos) + max(0, len(grupos)-1) * gap_grupos
        cursor_x = (xa + xb - largura_pacote) / 2.0

        for gi, grupo in enumerate(grupos):
            largura_g = larguras_grupos[gi]
            gx = cursor_x + largura_g / 2.0
            cursor_x += largura_g + gap_grupos
            conds = grupo.get("condutores") or []
            bit = str(grupo.get("bitola") or "-")
            circ = str(grupo.get("circuito") or "")

            # Número do circuito acima do conjunto
            tc = msp.add_text(circ.replace("C", ""), dxfattribs={
                "layer": layer, "height": 0.10, "insert": (gx, yc+0.19)
            })
            try:
                tc.set_placement((gx, yc+0.19),
                                 align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
            except Exception:
                pass

            # Símbolos dos condutores, transversalmente à linha base.
            esp = 0.115
            nconds = max(1, len(conds))
            x_ini = gx - (nconds-1)*esp/2.0
            for ci, cond in enumerate(conds):
                _simbolo_condutor_unifilar(
                    msp,
                    (x_ini + ci*esp, yc),
                    (1.0, 0.0),
                    (0.0, 1.0),
                    cond,
                    escala=0.095,
                )

            # Seção abaixo
            tb = msp.add_text(f"{bit} mm²", dxfattribs={
                "layer": layer, "height": 0.085, "insert": (gx, yc-0.19)
            })
            try:
                tb.set_placement((gx, yc-0.19),
                                 align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
            except Exception:
                pass


def _desenhar_identificacao_condutos_unifilar(msp, rotas_fisicas, circuitos, ambientes_geom):
    """Fase 13.6 Rev.117 — balões anti-colisão + legenda gráfica de fiação."""
    por_numero = {}
    for c in circuitos or []:
        try:
            n = int(c.get("numero", 0) or 0)
        except (TypeError, ValueError):
            n = 0
        if n > 0:
            por_numero[n] = c

    codigos = {}
    registros = []
    vistos_geom = set()
    ocupados = []
    indice_chamada = 0

    for rota in rotas_fisicas or []:
        p1, p2 = rota.get("inicio"), rota.get("fim")
        if not p1 or not p2:
            continue
        dx, dy = float(p2[0])-float(p1[0]), float(p2[1])-float(p1[1])
        comp = math.hypot(dx, dy)
        if comp < 0.25:
            continue

        ids = []
        for raw in rota.get("circuitos", []) or []:
            try:
                num = int(str(raw).upper().replace("C", ""))
            except (TypeError, ValueError):
                continue
            if num in por_numero and num not in ids:
                ids.append(num)
        if not ids:
            continue
        ids.sort()

        criterio = str(rota.get("criterio", "") or "")
        grupos = []
        chave_grupos = []

        criterios_por_circuito = rota.get("criterios_por_circuito", {}) or {}

        for num in ids:
            circ = por_numero[num]
            criterio_circuito = str(
                criterios_por_circuito.get(num)
                or criterios_por_circuito.get(str(num))
                or criterio
                or ""
            )
            conds = _condutores_circuito_unifilar(circ, criterio_circuito)
            bit = _bitola_txt_unifilar(circ.get("bitola", circ.get("bitola_mm2", 0))) or "-"
            grupo = {
                "circuito": f"C{num:02d}",
                "condutores": list(conds),
                "bitola": bit,
            }
            grupos.append(grupo)
            chave_grupos.append((num, tuple(conds), bit))

        # A identificação é da composição elétrica; trechos iguais reutilizam o mesmo número.
        chave = tuple(chave_grupos)
        if chave not in codigos:
            numero = len(codigos)+1
            codigos[chave] = numero
            registros.append({
                "numero": numero,
                "grupos": grupos,
                "trecho": _criterio_legenda_unifilar(criterio),
            })
        numero = codigos[chave]

        geom = tuple(sorted((
            (round(float(p1[0]), 3), round(float(p1[1]), 3)),
            (round(float(p2[0]), 3), round(float(p2[1]), 3))
        )))
        chave_geom = (geom, numero)
        if chave_geom in vistos_geom:
            continue
        vistos_geom.add(chave_geom)

        geo_real = _ponto_real_rota_unifilar(msp, rota)
        if geo_real is None:
            continue
        ponto_real, tang_real, normal_real = geo_real

        _desenhar_quadro_chamada_unifilar(
            msp,
            ponto_real,
            tang_real,
            normal_real,
            numero,
            ocupados=ocupados,
            indice_chamada=indice_chamada,
        )
        indice_chamada += 1

    _desenhar_tabela_legenda_condutos_unifilar(msp, registros, ambientes_geom)

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

            # Fase 13.6 Rev.117 — a geometria do ambiente só pode ser
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
                # Fase 13.6 Rev.117:
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
        # FASE 13.6 REV.1 — REDE TRONCAL HÍBRIDA + TODAS AS LUMINÁRIAS
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
        # FASE 13.6 REV.1 — DIMENSIONAMENTO ITERATIVO AUTOMÁTICO
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


        # Fase 13.6 Rev.117 — chamadas numeradas ancoradas na geometria real; detalhes elétricos
        # concentrados em tabela para manter a planta limpa.
        _desenhar_identificacao_condutos_unifilar(
            msp, rotas_fisicas, circuitos_dimensionados, ambientes_geom
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


        # Fase 13.6 Rev.117 — diagrama unifilar retirado do DXF.
        # Os cálculos elétricos continuam sendo executados normalmente
        # e alimentam o diagrama de montagem, auditoria e relatórios.


        mapa_fisico_qdc = gerar_mapa_fisico_qdc(
            circuitos_dimensionados,
            resumo_drs_unifilar,
            resumo_protecao_unifilar,
            resultado_demanda_unifilar
        )

        # ====================================================
        # FASE 13.6 REV.1 — AUDITORIA ELÉTRICA OBRIGATÓRIA DO QDC
        # ====================================================
        auditoria_normativa_qdc = auditar_qdc_normativo(
            circuitos_dimensionados,
            resumo_drs_unifilar,
            resumo_protecao_unifilar,
            resultado_demanda_unifilar,
            parametros_rede_unifilar,
            mapa_fisico=mapa_fisico_qdc
        )

        if auditoria_normativa_qdc.get(
            "qtd_bloqueios",
            0
        ):
            detalhes_bloqueio = "; ".join(
                (
                    item.get("Código", "")
                    + " — "
                    + item.get("Detalhe", "")
                )
                for item in auditoria_normativa_qdc.get(
                    "bloqueios",
                    []
                )
            )

            raise ValueError(
                "QDC bloqueado pela auditoria elétrica da Fase 13.6 Rev.117: "
                + detalhes_bloqueio
            )

        if isinstance(
            resumo_rotas,
            dict
        ):
            resumo_rotas[
                "auditoria_normativa_qdc"
            ] = auditoria_normativa_qdc

        desenhar_mapa_fisico_qdc(
            msp,
            mapa_fisico_qdc,
            polilinhas,
            parametros_rede=parametros_rede_unifilar,
            resumo_balanceamento=resumo_balanceamento_unifilar
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
