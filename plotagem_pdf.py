"""Plotagem PDF do projeto elétrico a partir do DXF final.

Fase 13.6 Rev.164 — PDF A3 com arquitetura/layer 0 em cinza claro, elétrica preta e recorte estrito da legenda.
Não altera o DXF: apenas renderiza uma cópia em memória.
"""
from io import BytesIO
import os
import tempfile
import math

import ezdxf


def _bbox_entidade(ent, bbox_mod):
    try:
        b = bbox_mod.extents([ent], fast=True)
        if not b.has_data:
            return None
        x0, y0 = float(b.extmin.x), float(b.extmin.y)
        x1, y1 = float(b.extmax.x), float(b.extmax.y)
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
            return None
        return (min(x0,x1), min(y0,y1), max(x0,x1), max(y0,y1))
    except Exception:
        return None


def _texto_entidade(ent):
    try:
        if ent.dxftype() == "TEXT":
            return str(ent.dxf.text or "")
        if ent.dxftype() == "MTEXT":
            return str(ent.text or "")
    except Exception:
        pass
    return ""


def _bbox_camadas(msp, predicado):
    from ezdxf import bbox
    caixas=[]
    for ent in msp:
        try:
            layer=str(ent.dxf.layer or "")
        except Exception:
            layer=""
        if not predicado(layer, ent):
            continue
        b=_bbox_entidade(ent,bbox)
        if b: caixas.append(b)
    if not caixas:
        return None
    return (min(b[0] for b in caixas), min(b[1] for b in caixas),
            max(b[2] for b in caixas), max(b[3] for b in caixas))


def _expandir(b, px=0.08, py=0.08, minimo=0.35):
    if not b: return None
    x0,y0,x1,y1=b
    w=max(x1-x0,1e-6); h=max(y1-y0,1e-6)
    mx=max(w*px,minimo); my=max(h*py,minimo)
    return (x0-mx,y0-my,x1+mx,y1+my)


def _regioes_semanticas(msp):
    """Rev.153: preserva as regiões semânticas rigorosas da Rev.152.

    A planta usa IA_AMBIENTES como âncora. O QDC usa somente camadas próprias.
    A legenda é localizada pelo cabeçalho e pelas entidades da mesma camada,
    imediatamente abaixo dele, evitando capturar novamente planta e QDC.
    """
    from ezdxf import bbox
    geral=bbox.extents(msp, fast=True)
    if not geral.has_data:
        return [], []
    gx0,gy0,gx1,gy1=map(float,(geral.extmin.x,geral.extmin.y,geral.extmax.x,geral.extmax.y))

    planta=_bbox_camadas(msp, lambda layer, ent: layer.upper()=="IA_AMBIENTES")
    if planta:
        x0,y0,x1,y1=planta
        w=max(x1-x0,1e-6); h=max(y1-y0,1e-6)
        # margem suficiente para símbolos/balões, mas sem alcançar a legenda abaixo
        planta=(x0-max(0.55,w*0.10), y0-max(0.40,h*0.07),
                x1+max(0.55,w*0.10), y1+max(0.40,h*0.07))

    qdc=_bbox_camadas(
        msp,
        lambda layer, ent: (
            "UNIFILAR_QDC" in layer.upper()
            or "MAPA_QDC" in layer.upper()
            or layer.upper().startswith("PROJ_ELETRICA_QDC_")
        ),
    )
    if qdc:
        qdc=_expandir(qdc, px=0.07, py=0.07, minimo=0.45)

    ancora=None; layer_legenda=None
    for ent in msp:
        txt=_texto_entidade(ent).upper().replace("\\P"," ")
        if "LEGENDA DE FIA" in txt:
            b=_bbox_entidade(ent,bbox)
            if b:
                ancora=b
                try: layer_legenda=str(ent.dxf.layer or "")
                except Exception: layer_legenda=""
                break

    legenda=None
    if ancora:
        ax0,ay0,ax1,ay1=ancora; acx=(ax0+ax1)/2.0
        # A tabela criada pelo sistema tem largura compacta. Primeiro localizamos
        # linhas horizontais da mesma layer que cruzam o eixo do título.
        linhas=[]
        for ent in msp:
            try:
                if ent.dxftype() != "LINE" or str(ent.dxf.layer or "") != layer_legenda:
                    continue
            except Exception:
                continue
            b=_bbox_entidade(ent,bbox)
            if not b: continue
            if b[0]-0.05 <= acx <= b[2]+0.05 and b[3] <= ay1+0.55:
                linhas.append(b)
        if linhas:
            # largura pela maior horizontal conectada ao eixo do cabeçalho
            lx0=min(b[0] for b in linhas); lx1=max(b[2] for b in linhas)
            # entidades da mesma layer contidas nessa largura e abaixo do título
            caixas=[]
            for ent in msp:
                try: layer=str(ent.dxf.layer or "")
                except Exception: layer=""
                if layer != layer_legenda: continue
                b=_bbox_entidade(ent,bbox)
                if not b: continue
                cx=(b[0]+b[2])/2.0
                if lx0-0.20 <= cx <= lx1+0.20 and b[3] <= ay1+0.55:
                    caixas.append(b)
            if caixas:
                legenda=(min(b[0] for b in caixas), min(b[1] for b in caixas),
                         max(b[2] for b in caixas), max(b[3] for b in caixas))
        if not legenda:
            legenda=_expandir(ancora, px=1.8, py=8.0, minimo=0.40)
        # Rev.164 — NÃO expandir verticalmente a região da legenda.
        # Na Rev.163 a expansão mínima de 0,22 unidade acima da tabela podia
        # capturar o centro de um balão da planta elétrica (ex.: balão 20),
        # fazendo-o aparecer acima da viewport da legenda. Mantemos apenas
        # uma folga horizontal mínima para evitar corte visual das bordas.
        legenda=_expandir(legenda, px=0.01, py=0.0, minimo=0.0)

    regs=[]; tit=[]
    for titulo,b in (("Planta elétrica",planta),("Diagrama / QDC",qdc),("Tabelas e legendas",legenda)):
        if b:
            regs.append(b); tit.append(titulo)
    if not regs:
        return [(gx0,gy0,gx1,gy1)], ["Projeto elétrico"]
    return regs,tit


def _intersecta(b, r):
    if not b or not r: return False
    return not (b[2] < r[0] or b[0] > r[2] or b[3] < r[1] or b[1] > r[3])


def _filtro_prancha(msp, regiao, titulo):
    """Filtro de desenho preservado da Rev.152: impede entidades de outras pranchas."""
    from ezdxf import bbox
    cache={}
    def fb(ent):
        k=id(ent)
        if k not in cache: cache[k]=_bbox_entidade(ent,bbox)
        return cache[k]
    t=titulo.lower()
    if "diagrama" in t:
        def filtro(ent):
            try: layer=str(ent.dxf.layer or "").upper()
            except Exception: layer=""
            return ("UNIFILAR_QDC" in layer or "MAPA_QDC" in layer or layer.startswith("PROJ_ELETRICA_QDC_"))
        return filtro
    # Planta: mantém a lógica consolidada de interseção da Rev.160.
    if "planta" in t:
        return lambda ent: _intersecta(fb(ent), regiao)

    # Rev.164 — legenda com recorte semântico rigoroso e sem folga vertical. Como a legenda e os
    # balões da planta compartilham PROJ_ELETRICA_TEXTO, testar apenas
    # interseção permite que um balão tangente ao limite "vaze" para a
    # viewport lateral. Para a legenda, o centro da entidade deve estar
    # efetivamente dentro da região calculada da tabela.
    def filtro_legenda(ent):
        b = fb(ent)
        if not b:
            return False
        cx = (b[0] + b[2]) / 2.0
        cy = (b[1] + b[3]) / 2.0
        return (regiao[0] <= cx <= regiao[2] and regiao[1] <= cy <= regiao[3])
    return filtro_legenda


def _preparar_hierarquia_grafica_pdf(doc, msp):
    """Rev.164: força cores RGB na cópia usada para o PDF.

    Evita o comportamento do ACI 7, que pode ser interpretado como branco pelo
    backend de renderização em fundo branco. A arquitetura (incluindo layer 0) fica em cinza claro e toda a
    instalação elétrica/QDC fica preto RGB real.
    """
    camadas_arquitetura = {
        "IA_AMBIENTES", "IA_TEXTOS", "IA_PORTAS", "IA_SOLEIRAS",
        "IA_JANELA", "IA_JANELAS", "0",
    }

    def eh_arquitetura(nome):
        return nome in camadas_arquitetura or "JANEL" in nome

    def eh_eletrica(nome):
        return (nome.startswith("PROJ_ELETRICA_") or
                nome.startswith("UNIFILAR_QDC") or
                nome.startswith("MAPA_QDC") or
                nome.startswith("AE_"))

    # Mantém as layers coerentes, mas a garantia para o PDF é feita também
    # entidade por entidade com true_color RGB abaixo.
    for layer_obj in doc.layers:
        try:
            nome = str(layer_obj.dxf.name or "").upper().strip()
            if eh_arquitetura(nome):
                layer_obj.color = 8
            elif eh_eletrica(nome):
                layer_obj.color = 7
        except Exception:
            pass

    for ent in msp:
        try:
            nome = str(ent.dxf.layer or "").upper().strip()
            if eh_arquitetura(nome):
                ent.dxf.color = 256
                ent.dxf.true_color = 0xB8B8B8  # cinza claro Rev.163
            elif eh_eletrica(nome):
                ent.dxf.color = 256
                ent.dxf.true_color = 0x000000  # preto RGB real; nunca ACI 7 branco
        except Exception:
            pass

def gerar_pdf_projeto(dxf_bytes, nome_projeto="Projeto", versao=""):
    """Rev.164: PDF A3 horizontal fixo com arquitetura em cinza e elétrica em preto RGB.

    Prancha 1: planta elétrica + legenda de fiação lado a lado em A3 paisagem real,
    com viewports independentes e sem altura herdada da geometria da legenda.
    Prancha 2: diagrama/QDC enquadrado dentro do mesmo A3 horizontal físico. O DXF não é alterado.
    """
    if not dxf_bytes:
        raise ValueError("DXF vazio; gere o CAD antes de gerar o PDF.")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Rectangle
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    tmp_path=None
    try:
        with tempfile.NamedTemporaryFile(suffix=".dxf",delete=False) as tmp:
            tmp.write(bytes(dxf_bytes)); tmp_path=tmp.name
        doc=ezdxf.readfile(tmp_path); msp=doc.modelspace()
        try:
            from ezdxf.fonts import fonts as ezfonts
            font_dir=os.path.join(matplotlib.get_data_path(),"fonts","ttf")
            if os.path.isdir(font_dir):
                ezfonts.font_manager.build(folders=[font_dir],support_dirs=False)
        except Exception:
            pass

        _preparar_hierarquia_grafica_pdf(doc, msp)
        regioes,titulos=_regioes_semanticas(msp)
        mapa={t.lower(): r for r,t in zip(regioes,titulos)}
        planta=mapa.get("planta elétrica")
        qdc=mapa.get("diagrama / qdc")
        legenda=mapa.get("tabelas e legendas")
        if not planta:
            raise RuntimeError("Não foi possível localizar a região da planta elétrica no DXF.")

        projeto_txt=str(nome_projeto or "Projeto").strip()
        buffer=BytesIO()
        total_paginas=2 if qdc else 1

        def desenhar_regiao(fig, rect, regiao, titulo, margem_escala=0.0):
            ax=fig.add_axes(rect)
            ax.set_aspect("equal",adjustable="datalim")
            ax.set_axis_off(); ax.set_facecolor("white")
            ctx=RenderContext(doc); out=MatplotlibBackend(ax)
            Frontend(ctx,out).draw_layout(
                msp, finalize=True,
                filter_func=_filtro_prancha(msp,regiao,titulo),
            )
            x0,y0,x1,y1=regiao
            if margem_escala > 0:
                # Rev.159: mantém a escala visual reduzida da legenda, ampliando sua
                # janela de coordenadas ao redor do centro, sem alterar o DXF.
                cx=(x0+x1)/2.0; cy=(y0+y1)/2.0
                w=max(x1-x0,1e-6)*(1.0+margem_escala)
                h=max(y1-y0,1e-6)*(1.0+margem_escala)
                x0,x1=cx-w/2.0,cx+w/2.0
                y0,y1=cy-h/2.0,cy+h/2.0
            ax.set_xlim(x0,x1); ax.set_ylim(y0,y1)
            return ax

        def rodape(fig, numero, titulo):
            fig.add_artist(Rectangle((0.02,0.025),0.96,0.95,fill=False,linewidth=0.8,
                                     transform=fig.transFigure,clip_on=False))
            fig.text(0.035,0.043,f"Projeto elétrico — {projeto_txt} — {titulo}",
                     fontsize=7.2,ha="left",va="center")
            fig.text(0.50,0.043,f"Prancha {numero}/{total_paginas}",
                     fontsize=7.2,ha="center",va="center")
            if versao:
                fig.text(0.965,0.043,str(versao),fontsize=7.2,ha="right",va="center")

        # Evita que configurações externas do Streamlit/Matplotlib recortem a folha
        # ao redor do conteúdo. A mídia permanece A3 paisagem integral.
        with matplotlib.rc_context({"savefig.bbox": None, "savefig.pad_inches": 0.0}):
            with PdfPages(buffer) as pdf:
                # PRANCHA 1 — A3 PAISAGEM REAL.
                # Rev.159: a folha é criada e travada explicitamente em 420 x 297 mm.
                # Nenhuma dimensão do DXF/legenda pode alterar a mídia física.
                fig=plt.figure(figsize=(16.535433,11.692913),facecolor="white", constrained_layout=False)
                fig.set_size_inches(16.535433,11.692913,forward=True)
                if legenda:
                    # Planta recebe a maior área. A legenda usa uma faixa lateral e é
                    # deliberadamente reduzida (45%) para não comandar a composição.
                    desenhar_regiao(fig,[0.045,0.105,0.705,0.825],planta,"Planta elétrica")
                    desenhar_regiao(fig,[0.775,0.145,0.180,0.745],legenda,"Tabelas e legendas",margem_escala=0.45)
                else:
                    desenhar_regiao(fig,[0.035,0.075,0.93,0.885],planta,"Planta elétrica")
                rodape(fig,1,"Planta elétrica + Legenda de fiação" if legenda else "Planta elétrica")
                fig.set_size_inches(16.535433,11.692913,forward=True)
                pdf.savefig(fig,dpi=300,facecolor="white",bbox_inches=None,pad_inches=0.0); plt.close(fig)

                # PRANCHA 2 — Rev.160: mesma mídia física da Prancha 1.
                # A geometria do QDC nunca altera orientação nem tamanho da folha;
                # somente o conteúdo é enquadrado dentro do A3 horizontal fixo.
                if qdc:
                    fig=plt.figure(figsize=(16.535433,11.692913),facecolor="white", constrained_layout=False)
                    fig.set_size_inches(16.535433,11.692913,forward=True)
                    desenhar_regiao(fig,[0.035,0.075,0.93,0.885],qdc,"Diagrama / QDC")
                    rodape(fig,2,"Diagrama / QDC")
                    fig.set_size_inches(16.535433,11.692913,forward=True)
                    pdf.savefig(fig,dpi=300,facecolor="white",bbox_inches=None,pad_inches=0.0); plt.close(fig)

        buffer.seek(0); dados=buffer.getvalue()
        if not dados.startswith(b"%PDF"):
            raise RuntimeError("Falha ao produzir um PDF válido.")
        return dados
    finally:
        if tmp_path:
            try: os.remove(tmp_path)
            except OSError: pass
