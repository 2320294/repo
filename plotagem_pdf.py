"""Plotagem PDF do projeto elétrico a partir do DXF final.

Fase 13.6 Rev.156 — PDF A3 paisagem normalizado em 2 pranchas; planta e legenda com escalas independentes.
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
        legenda=_expandir(legenda, px=0.05, py=0.025, minimo=0.22)

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
    # Planta e legenda: desenhar somente entidades cuja caixa toca a região.
    # Isso evita que a página 3 volte a desenhar o QDC/planta inteira.
    return lambda ent: _intersecta(fb(ent), regiao)


def _aplicar_monocromatico(ax):
    """Converte somente a saída PDF para preto, preservando o DXF colorido."""
    import matplotlib.colors as mcolors
    preto="black"
    for ln in ax.lines:
        try: ln.set_color(preto)
        except Exception: pass
    for txt in ax.texts:
        try: txt.set_color(preto)
        except Exception: pass
    for patch in ax.patches:
        try: patch.set_edgecolor(preto)
        except Exception: pass
        try:
            fc=patch.get_facecolor()
            if len(fc) >= 4 and fc[3] > 0:
                patch.set_facecolor(preto)
        except Exception: pass
    for col in ax.collections:
        try: col.set_edgecolor(preto)
        except Exception: pass
        try:
            fcs=col.get_facecolors()
            if len(fcs): col.set_facecolor(preto)
        except Exception: pass

def gerar_pdf_projeto(dxf_bytes, nome_projeto="Projeto", versao=""):
    """Rev.156: PDF A3 monocromático em 2 pranchas.

    Prancha 1 reúne planta elétrica e legenda de fiação, cada uma com
    enquadramento/escala independente. Prancha 2 mantém o Diagrama/QDC.
    O DXF original não é alterado.
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

        regioes,titulos=_regioes_semanticas(msp)
        mapa={t:b for t,b in zip(titulos,regioes)}
        planta=mapa.get("Planta elétrica")
        qdc=mapa.get("Diagrama / QDC")
        legenda=mapa.get("Tabelas e legendas")
        projeto_txt=str(nome_projeto or "Projeto").strip()
        buffer=BytesIO()

        def desenhar_regiao(fig, pos, regiao, titulo):
            if not regiao:
                return
            x0,y0,x1,y1=regiao
            ax=fig.add_axes(pos)
            ax.set_aspect("equal",adjustable="box")
            ax.set_axis_off(); ax.set_facecolor("white")
            ctx=RenderContext(doc); out=MatplotlibBackend(ax)
            Frontend(ctx,out).draw_layout(
                msp, finalize=True,
                filter_func=_filtro_prancha(msp,regiao,titulo),
            )
            _aplicar_monocromatico(ax)
            ax.set_xlim(x0,x1); ax.set_ylim(y0,y1)

        def rodape(fig, esquerda, pagina, total=2):
            fig.add_artist(Rectangle((0.02,0.025),0.96,0.95,fill=False,linewidth=0.8,
                                     transform=fig.transFigure,clip_on=False))
            fig.text(0.035,0.043,esquerda,fontsize=7.2,ha="left",va="center")
            fig.text(0.50,0.043,f"Prancha {pagina}/{total}",fontsize=7.2,ha="center",va="center")
            if versao:
                fig.text(0.965,0.043,str(versao),fontsize=7.2,ha="right",va="center")

        # Rev.156: dimensões físicas explícitas da folha A3 em PAISAGEM.
        # O bbox_inches=None é intencional: em ambientes Streamlit/Matplotlib que
        # configuram savefig.bbox="tight", o PDF era recortado ao conteúdo e a
        # folha acabava estreita/vertical. Aqui a MediaBox permanece 420 x 297 mm.
        A3_LARGURA_POL = 420.0 / 25.4
        A3_ALTURA_POL = 297.0 / 25.4

        def nova_folha_a3():
            fig = plt.figure(figsize=(A3_LARGURA_POL, A3_ALTURA_POL), facecolor="white")
            fig.set_size_inches(A3_LARGURA_POL, A3_ALTURA_POL, forward=True)
            return fig

        def salvar_a3(pdf, fig):
            pdf.savefig(fig, dpi=300, facecolor="white", bbox_inches=None, pad_inches=0)

        # Rev.156: cada prancha é primeiro produzida isoladamente e, em seguida,
        # normalizada para uma MediaBox A3 paisagem real. Isso evita que uma
        # prancha herde/sofra recorte de tamanho diferente dentro do PdfPages.
        paginas=[]

        def gerar_pagina(fig):
            pagina=BytesIO()
            fig.savefig(pagina, format="pdf", dpi=300, facecolor="white",
                        bbox_inches=None, pad_inches=0)
            plt.close(fig)
            pagina.seek(0)
            return pagina.getvalue()

        # PRANCHA 1 — planta e legenda em áreas independentes da MESMA A3 horizontal.
        fig=nova_folha_a3()
        if planta:
            desenhar_regiao(fig,[0.035,0.085,0.715,0.865],planta,"Planta elétrica")
        if legenda:
            desenhar_regiao(fig,[0.765,0.085,0.200,0.865],legenda,"Tabelas e legendas")
        rodape(fig,f"Projeto elétrico — {projeto_txt} — Planta elétrica + Legenda de fiação",1)
        paginas.append(gerar_pagina(fig))

        # PRANCHA 2 — QDC preservado.
        if qdc:
            fig=nova_folha_a3()
            desenhar_regiao(fig,[0.035,0.075,0.93,0.885],qdc,"Diagrama / QDC")
            rodape(fig,f"Projeto elétrico — {projeto_txt} — Diagrama / QDC",2)
            paginas.append(gerar_pagina(fig))

        # Une as páginas sem permitir que o tamanho da página seja recalculado
        # pelo conteúdo. A3 paisagem = 1190.551 x 841.890 pontos PDF.
        try:
            from pypdf import PdfReader, PdfWriter
            from pypdf.generic import RectangleObject
            largura_pt=420.0/25.4*72.0
            altura_pt=297.0/25.4*72.0
            writer=PdfWriter()
            for raw in paginas:
                reader=PdfReader(BytesIO(raw))
                page=reader.pages[0]
                # Matplotlib já desenha na proporção A3; aqui apenas travamos
                # fisicamente MediaBox/CropBox/TrimBox na mesma folha horizontal.
                caixa=RectangleObject([0,0,largura_pt,altura_pt])
                page.mediabox=caixa
                page.cropbox=RectangleObject([0,0,largura_pt,altura_pt])
                page.trimbox=RectangleObject([0,0,largura_pt,altura_pt])
                writer.add_page(page)
            writer.write(buffer)
        except Exception:
            # Compatibilidade com ambientes sem pypdf: união tradicional.
            with PdfPages(buffer) as pdf:
                for raw in paginas:
                    # Esta contingência só é usada se pypdf não estiver disponível.
                    pass
            raise RuntimeError("Dependência pypdf ausente para normalização A3 da Rev.156.")

        buffer.seek(0); dados=buffer.getvalue()
        if not dados.startswith(b"%PDF"):
            raise RuntimeError("Falha ao produzir um PDF válido.")
        return dados
    finally:
        if tmp_path:
            try: os.remove(tmp_path)
            except Exception: pass
