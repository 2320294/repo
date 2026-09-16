"""Plotagem PDF do projeto elétrico a partir do DXF final.

Fase 13.6 Rev.150 — PDF multipágina com enquadramento automático por regiões.
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


def _regioes_automaticas(msp):
    """Separa visualmente o modelspace em até 3 regiões sem alterar entidades.

    Usa centros das caixas das entidades e k-means leve. Entidades muito longas
    (eletrodutos/linhas de ligação) têm peso reduzido para não unir planta,
    diagrama e tabelas em uma única prancha.
    """
    from ezdxf import bbox
    itens=[]
    geral=bbox.extents(msp, fast=True)
    if not geral.has_data:
        return []
    gx0,gy0,gx1,gy1=map(float,(geral.extmin.x,geral.extmin.y,geral.extmax.x,geral.extmax.y))
    gw=max(gx1-gx0,1e-6); gh=max(gy1-gy0,1e-6)
    for ent in msp:
        b=_bbox_entidade(ent,bbox)
        if not b: continue
        x0,y0,x1,y1=b
        w=x1-x0; h=y1-y0
        # ignora, para fins de agrupamento, entidades que atravessam quase todo
        # o desenho; elas continuam aparecendo normalmente na renderização.
        if w > 0.72*gw or h > 0.72*gh:
            continue
        cx=(x0+x1)/2; cy=(y0+y1)/2
        itens.append((cx,cy,b))
    if len(itens)<8:
        return [(gx0,gy0,gx1,gy1)]

    # k=3 quando há conteúdo suficiente; isso tende a separar planta, QDC e
    # tabelas/legendas. Se um grupo ficar insignificante, ele é descartado.
    k=3 if len(itens)>=24 else 2
    pts=[(a,b) for a,b,_ in itens]
    # sementes espaciais determinísticas: esquerda-superior, direita-superior,
    # esquerda/inferior, adequadas ao arranjo usual do gerador AutoElétrica.
    seeds=[(gx0+0.25*gw, gy0+0.75*gh),(gx0+0.75*gw,gy0+0.75*gh),(gx0+0.25*gw,gy0+0.25*gh)][:k]
    centers=list(seeds)
    labels=[0]*len(pts)
    for _ in range(20):
        new=[]
        for x,y in pts:
            # normaliza eixos para a proporção global não distorcer o agrupamento
            ds=[((x-cx)/gw)**2+((y-cy)/gh)**2 for cx,cy in centers]
            new.append(min(range(k), key=lambda j: ds[j]))
        ncent=[]
        for j in range(k):
            group=[pts[i] for i,v in enumerate(new) if v==j]
            if group:
                ncent.append((sum(p[0] for p in group)/len(group),sum(p[1] for p in group)/len(group)))
            else: ncent.append(centers[j])
        if new==labels: break
        labels=new; centers=ncent

    regs=[]
    for j in range(k):
        bs=[itens[i][2] for i,v in enumerate(labels) if v==j]
        if len(bs)<2: continue
        x0=min(b[0] for b in bs); y0=min(b[1] for b in bs)
        x1=max(b[2] for b in bs); y1=max(b[3] for b in bs)
        # margem proporcional ao próprio conteúdo
        mx=max((x1-x0)*0.055, gw*0.006); my=max((y1-y0)*0.055, gh*0.006)
        regs.append((x0-mx,y0-my,x1+mx,y1+my,len(bs)))
    regs.sort(key=lambda r:(-((r[1]+r[3])/2), (r[0]+r[2])/2))
    return [(r[0],r[1],r[2],r[3]) for r in regs] or [(gx0,gy0,gx1,gy1)]


def gerar_pdf_projeto(dxf_bytes, nome_projeto="Projeto", versao=""):
    """Renderiza o DXF em PDF A3 multipágina, com regiões autoenquadradas."""
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

        regioes=_regioes_automaticas(msp)
        projeto_txt=str(nome_projeto or "Projeto").strip()
        titulos=["Planta elétrica","Diagrama / QDC","Tabelas e legendas"]
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
