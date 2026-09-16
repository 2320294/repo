"""Plotagem PDF do projeto elétrico a partir do DXF final.

Fase 13.6 Rev.149 — correção de fontes para plotagem no Streamlit Cloud.
Não altera o DXF: apenas renderiza uma cópia em memória.
"""
from io import BytesIO
import os
import tempfile

import ezdxf


def gerar_pdf_projeto(dxf_bytes, nome_projeto="Projeto", versao=""):
    """Renderiza o modelspace do DXF em uma prancha PDF A3 auto-orientada."""
    if not dxf_bytes:
        raise ValueError("DXF vazio; gere o CAD antes de gerar o PDF.")

    # Import local para não interferir na geração CAD existente.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
            tmp.write(bytes(dxf_bytes))
            tmp_path = tmp.name

        doc = ezdxf.readfile(tmp_path)
        msp = doc.modelspace()

        # REV.149 — o Streamlit Cloud pode não ter fontes de sistema instaladas.
        # Registra no gerenciador do ezdxf as fontes DejaVu que acompanham o
        # próprio Matplotlib. Isso mantém TEXT/MTEXT renderizáveis sem depender
        # de Arial/SHX existentes no servidor. O DXF original não é alterado.
        try:
            from ezdxf.fonts import fonts as ezfonts
            font_dir = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
            if os.path.isdir(font_dir):
                ezfonts.font_manager.build(folders=[font_dir], support_dirs=False)
        except Exception:
            # A renderização ainda pode usar o fallback do backend; não deixa
            # uma falha de registro impedir a tentativa de gerar a prancha.
            pass

        # Descobre a proporção do desenho por extents, sem modificar entidades.
        try:
            from ezdxf import bbox
            ext = bbox.extents(msp, fast=True)
            w = max(float(ext.size.x), 1e-6)
            h = max(float(ext.size.y), 1e-6)
        except Exception:
            w, h = 1.414, 1.0

        # A3: escolhe automaticamente paisagem/retrato conforme o desenho.
        if w >= h:
            figsize = (16.54, 11.69)
        else:
            figsize = (11.69, 16.54)

        fig = plt.figure(figsize=figsize)
        # Reserva faixa inferior para identificação da prancha.
        ax = fig.add_axes([0.035, 0.075, 0.93, 0.885])
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_axis_off()
        ax.set_facecolor("white")
        fig.patch.set_facecolor("white")

        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        Frontend(ctx, out).draw_layout(msp, finalize=True)

        ax.autoscale(enable=True)
        ax.margins(x=0.025, y=0.025)

        # Moldura/carimbo básico fora da área do CAD.
        from matplotlib.patches import Rectangle
        fig.add_artist(Rectangle(
            (0.02, 0.025), 0.96, 0.95,
            fill=False, linewidth=0.8,
            transform=fig.transFigure, clip_on=False,
        ))
        projeto_txt = str(nome_projeto or "Projeto").strip()
        fig.text(0.035, 0.043, f"Projeto elétrico — {projeto_txt}", fontsize=8, va="center")
        if versao:
            fig.text(0.965, 0.043, str(versao), fontsize=7, ha="right", va="center")

        buffer = BytesIO()
        fig.savefig(
            buffer,
            format="pdf",
            dpi=300,
            facecolor="white",
            bbox_inches=None,
        )
        plt.close(fig)
        buffer.seek(0)
        dados = buffer.getvalue()
        if not dados.startswith(b"%PDF"):
            raise RuntimeError("Falha ao produzir um PDF válido.")
        return dados
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
