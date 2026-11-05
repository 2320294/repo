from versao import VERSAO_SISTEMA


def texto_rodape_pdf():
    return f"© 2026 AutoElétrica - Versão: {VERSAO_SISTEMA} - Todos os direitos reservados."


def desenhar_rodape_reportlab(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.drawCentredString(doc.pagesize[0] / 2.0, 14, texto_rodape_pdf())
    canvas.restoreState()
