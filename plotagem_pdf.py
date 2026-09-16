"""Plotagem PDF do projeto elétrico a partir do DXF final.

Fase 13.6 Rev.151 — PDF multipágina com separação semântica por pranchas.
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
    """Rev.151: separa as pranchas por significado, não por proximidade.

    1) Planta: usa IA_AMBIENTES como âncora arquitetônica e inclui uma margem
       suficiente para símbolos/eletrodutos/balões pertencentes à planta.
    2) Diagrama/QDC: usa exclusivamente as camadas geradas para QDC/unifilar/mapa.
    3) Legenda de fiação: usa o texto 'LEGENDA DE FIAÇÃO' como âncora e captura
       a tabela abaixo dele. Linhas longas entre regiões deixam de unir páginas.
    """
    from ezdxf import bbox
    geral=bbox.extents(msp, fast=True)
    if not geral.has_data:
        return []
    gx0,gy0,gx1,gy1=map(float,(geral.extmin.x,geral.extmin.y,geral.extmax.x,geral.extmax.y))
    gw=max(gx1-gx0,1e-6); gh=max(gy1-gy0,1e-6)

    # Planta arquitetônica: a camada obrigatória IA_AMBIENTES é a âncora mais
    # estável do sistema e independe da disposição posterior do QDC/tabelas.
    planta=_bbox_camadas(msp, lambda layer, ent: layer.upper()=="IA_AMBIENTES")
    if planta:
        # margem generosa para tomadas, textos, balões e eletrodutos próximos
        planta=_expandir(planta, px=0.16, py=0.16, minimo=0.60)

    # Diagrama / mapa do QDC: todas as camadas explicitamente dedicadas ao QDC.
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

    # Legenda de fiação: localiza a própria identificação textual gerada pelo
    # AutoElétrica e usa sua posição para delimitar a tabela abaixo dela.
    ancora=None
    for ent in msp:
        txt=_texto_entidade(ent).upper().replace("\\P"," ")
        if "LEGENDA DE FIA" in txt:
            b=_bbox_entidade(ent,bbox)
            if b:
                ancora=b
                break
    legenda=None
    if ancora:
        ax0,ay0,ax1,ay1=ancora
        acx=(ax0+ax1)/2
        # largura da tabela é pequena comparada à planta; captura entidades
        # próximas ao eixo da legenda e abaixo do cabeçalho.
        faixa=max(gw*0.18, 6.0)
        caixas=[]
        for ent in msp:
            b=_bbox_entidade(ent,bbox)
            if not b: continue
            cx=(b[0]+b[2])/2; cy=(b[1]+b[3])/2
            if abs(cx-acx) <= faixa and cy <= ay1 + max(gh*0.015,0.5):
                # evita engolir regiões muito acima/ao lado da legenda
                if cy >= gy0 - 0.1:
                    caixas.append(b)
        if caixas:
            legenda=(min(b[0] for b in caixas), min(b[1] for b in caixas),
                     max(b[2] for b in caixas), max(b[3] for b in caixas))
            legenda=_expandir(legenda, px=0.06, py=0.04, minimo=0.30)

    regs=[]
    tit=[]
    for titulo,b in (("Planta elétrica",planta),("Diagrama / QDC",qdc),("Tabelas e legendas",legenda)):
        if b:
            regs.append(b); tit.append(titulo)
    if not regs:
        return [(gx0,gy0,gx1,gy1)], ["Projeto elétrico"]
    return regs,tit

def gerar_pdf_projeto(dxf_bytes, nome_projeto="Projeto", versao=""):
    """Renderiza o DXF em PDF A3 multipágina, com pranchas semânticas."""
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
            if os.path.isdir(font_dir): ezfonts.font_manager.build(folders=[font_dir],support_dirs=False)
        except Exception: pass

        regioes,titulos=_regioes_semanticas(msp)
        projeto_txt=str(nome_projeto or "Projeto").strip()
        buffer=BytesIO()
        with PdfPages(buffer) as pdf:
            for idx,(x0,y0,x1,y1) in enumerate(regioes):
                w=max(x1-x0,1e-6); h=max(y1-y0,1e-6)
                figsize=(16.54,11.69) if w>=h else (11.69,16.54)
                fig=plt.figure(figsize=figsize)
                ax=fig.add_axes([0.035,0.075,0.93,0.885])
                ax.set_aspect("equal",adjustable="box"); ax.set_axis_off(); ax.set_facecolor("white"); fig.patch.set_facecolor("white")
                ctx=RenderContext(doc); out=MatplotlibBackend(ax)
                Frontend(ctx,out).draw_layout(msp,finalize=True)
                ax.set_xlim(x0,x1); ax.set_ylim(y0,y1)
                fig.add_artist(Rectangle((0.02,0.025),0.96,0.95,fill=False,linewidth=0.8,transform=fig.transFigure,clip_on=False))
                titulo=titulos[idx] if idx<len(titulos) else f"Prancha {idx+1}"
                fig.text(0.035,0.043,f"Projeto elétrico — {projeto_txt} — {titulo}",fontsize=8,va="center")
                fig.text(0.50,0.043,f"Prancha {idx+1}/{len(regioes)}",fontsize=7,ha="center",va="center")
                if versao: fig.text(0.965,0.043,str(versao),fontsize=7,ha="right",va="center")
                pdf.savefig(fig,dpi=300,facecolor="white"); plt.close(fig)
        buffer.seek(0); dados=buffer.getvalue()
        if not dados.startswith(b"%PDF"): raise RuntimeError("Falha ao produzir um PDF válido.")
        return dados
    finally:
        if tmp_path:
            try: os.remove(tmp_path)
            except OSError: pass
