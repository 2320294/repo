from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors

MODULO_MM = 17.5
ALTURA_ETIQUETA_MM = 12.0

CORES = {
    'GERAL': colors.HexColor('#C8102E'),
    'ILUMINACAO': colors.HexColor('#E57200'),
    'TUG': colors.HexColor('#2E8540'),
    'TUE': colors.HexColor('#7B2C91'),
    'CHUVEIRO': colors.HexColor('#2166B1'),
}

def _txt(v): return str(v or '').strip()
def _tipo(c):
    t = _txt(c.get('tipo') or c.get('tipo_circuito')).upper()
    amb = _txt(c.get('ambiente')).upper()
    desc = _txt(c.get('descricao')).upper()
    s = ' '.join((t, amb, desc))
    if 'CHUVEIR' in s: return 'CHUVEIRO'
    if 'ILUM' in s: return 'ILUMINACAO'
    if 'TUG' in s or 'TOMADA' in s: return 'TUG'
    if 'TUE' in s or any(x in s for x in ('AR ', 'AR-', 'MICRO', 'FORNO', 'COOKTOP', 'MAQUINA', 'MÁQUINA')): return 'TUE'
    return 'TUE'

def _polos(c):
    try:
        p = int(c.get('polos', 0) or 0)
        if p: return max(1, min(3, p))
    except Exception: pass
    fase = _txt(c.get('fase'))
    return 2 if '-' in fase else 1

def _nome_tipo(c, tipo):
    if tipo == 'ILUMINACAO': return 'Iluminação'
    if tipo == 'TUG': return 'Tomadas'
    if tipo == 'CHUVEIRO': return 'Chuveiro'
    # TUE: tenta preservar o equipamento real
    for k in ('equipamento','descricao_tue','carga','descricao'):
        v = _txt(c.get(k))
        if v and not v.upper().startswith('C0'):
            return v[:18]
    return 'TUE'

def _icone(c, cx, cy, tipo, cor=colors.black):
    c.setStrokeColor(cor); c.setFillColor(cor); c.setLineWidth(0.35)
    if tipo == 'ILUMINACAO':
        c.circle(cx, cy+0.35*mm, 1.25*mm, stroke=1, fill=0)
        c.line(cx-0.7*mm, cy-1.05*mm, cx+0.7*mm, cy-1.05*mm)
        c.line(cx, cy+1.8*mm, cx, cy+2.5*mm)
    elif tipo == 'TUG':
        c.roundRect(cx-1.5*mm, cy-1.2*mm, 3*mm, 2.4*mm, 0.35*mm, stroke=1, fill=0)
        c.circle(cx-0.55*mm, cy, 0.22*mm, stroke=0, fill=1); c.circle(cx+0.55*mm, cy, 0.22*mm, stroke=0, fill=1)
    elif tipo == 'CHUVEIRO':
        c.arc(cx-1.5*mm, cy-0.2*mm, cx+1.5*mm, cy+2.1*mm, 0, 180)
        for dx in (-0.9,0,0.9): c.line(cx+dx*mm, cy-0.2*mm, cx+dx*mm-0.25*mm, cy-1.0*mm)
    else:
        c.rect(cx-1.4*mm, cy-1.25*mm, 2.8*mm, 2.5*mm, stroke=1, fill=0)
        c.line(cx-0.7*mm, cy+0.5*mm, cx+0.7*mm, cy+0.5*mm); c.line(cx-0.7*mm, cy-0.2*mm, cx+0.7*mm, cy-0.2*mm)

def _fit(c, text, maxw, size=6.4, minsize=4.3, bold=False):
    font = 'Helvetica-Bold' if bold else 'Helvetica'
    s=size
    while s>minsize and c.stringWidth(text,font,s)>maxw: s-=0.2
    return font,s

def _quebrar_linhas(c, text, maxw, font='Helvetica', size=4.6, max_linhas=2):
    """Quebra o texto por palavras para ocupar melhor a largura da etiqueta."""
    text = _txt(text) or '-'
    # vírgulas continuam visíveis, mas passam a ser bons pontos de quebra
    palavras = text.replace(' + ', ', ').split()
    linhas=[]; atual=''
    for palavra in palavras:
        teste = palavra if not atual else atual + ' ' + palavra
        if c.stringWidth(teste, font, size) <= maxw or not atual:
            atual=teste
        else:
            linhas.append(atual)
            atual=palavra
            if len(linhas) == max_linhas-1:
                break
    if len(linhas) < max_linhas and atual:
        # Se ainda houver conteúdo não processado, reconstrói a última linha com o restante
        idx=sum(len(x.split()) for x in linhas)
        resto=' '.join(palavras[idx:])
        linhas.append(resto if resto else atual)
    linhas=linhas[:max_linhas]
    # reduz a fonte só se uma linha isolada ainda exceder a largura
    fs=size
    while fs > 3.3 and any(c.stringWidth(l,font,fs)>maxw for l in linhas):
        fs -= 0.15
    return linhas, fs

def _descricao(circ, tipo):
    nome = _nome_tipo(circ,tipo)
    amb = _txt(circ.get('ambiente')) or '-'
    return f'{nome} — {amb}'

def gerar_pdf_etiquetas_qdc(nome_projeto, circuitos, disjuntor_geral_a=None, polos_geral=2, versao=''):
    circuitos = sorted([dict(x) for x in (circuitos or []) if int(x.get('numero',0) or 0)>0], key=lambda x:int(x.get('numero',0) or 0))
    buf=BytesIO(); c=canvas.Canvas(buf,pagesize=A4); W,H=A4
    margem=14*mm; util=W-2*margem
    c.setTitle(f'{nome_projeto} - Etiquetas QDC')
    c.setFillColor(colors.black); c.setFont('Helvetica-Bold',13); c.drawString(margem,H-17*mm,'Etiquetas do quadro de distribuição')
    c.setFont('Helvetica',7.5); c.drawString(margem,H-22*mm,'Imprima em Tamanho real (100%). Não use “Ajustar à página”.')
    c.drawRightString(W-margem,H-22*mm,f'Cada módulo: {MODULO_MM:.1f} mm  |  Faixa: {ALTURA_ETIQUETA_MM:.0f} mm')

    itens=[]
    dg=int(disjuntor_geral_a or 0)
    itens.append({'id':'GERAL','tipo':'GERAL','polos':max(1,min(3,int(polos_geral or 1))),'linha1':'Disjuntor geral','linha2':f'{dg} A' if dg else ''})
    for x in circuitos:
        tipo=_tipo(x); n=int(x.get('numero',0)); amb=_txt(x.get('ambiente')) or '-'
        itens.append({'id':f'C{n:02d}','tipo':tipo,'polos':_polos(x),'linha1':_nome_tipo(x,tipo),'linha2':amb})

    y=H-31*mm; x=margem; linha=1; usados=0
    c.setFont('Helvetica',6.5); c.setFillColor(colors.grey); c.drawString(margem,y+3*mm,f'Linha {linha}')
    y-=1*mm
    for item in itens:
        w=item['polos']*MODULO_MM*mm
        if x+w > W-margem+0.1:
            y-=18*mm; x=margem; linha+=1; usados=0
            c.setFillColor(colors.grey); c.setFont('Helvetica',6.5); c.drawString(margem,y+3*mm,f'Linha {linha}'); y-=1*mm
        cor=CORES[item['tipo']]; h=ALTURA_ETIQUETA_MM*mm; topo=3.2*mm
        c.setStrokeColor(colors.HexColor('#B8B8B8')); c.setLineWidth(0.25); c.rect(x,y-h,w,h,stroke=1,fill=0)
        c.setFillColor(cor); c.rect(x,y-topo,w,topo,stroke=0,fill=1)
        c.setFillColor(colors.white); c.setFont('Helvetica-Bold',6.2); c.drawCentredString(x+w/2,y-2.35*mm,item['id'])
        # Rev.179: sem ícones na faixa física. O espaço liberado é usado pelos ambientes.
        c.setFillColor(colors.black)
        f,s=_fit(c,item['linha1'],w-1.6*mm,5.4,4.0,True); c.setFont(f,s); c.drawCentredString(x+w/2,y-6.25*mm,item['linha1'])
        linhas,fs=_quebrar_linhas(c,item['linha2'],w-1.8*mm,'Helvetica',4.5,2)
        c.setFont('Helvetica',fs)
        if len(linhas)==1:
            c.drawCentredString(x+w/2,y-9.45*mm,linhas[0])
        else:
            c.drawCentredString(x+w/2,y-8.65*mm,linhas[0])
            c.drawCentredString(x+w/2,y-10.65*mm,linhas[1])
        x+=w; usados+=item['polos']

    y-=20*mm
    if y < 95*mm: c.showPage(); y=H-20*mm
    c.setFillColor(colors.black); c.setFont('Helvetica-Bold',11); c.drawString(margem,y,'Quadro de distribuição — Identificação dos circuitos'); y-=5*mm
    c.setFont('Helvetica',7); c.drawString(margem,y,f'Local: ____________________   Responsável: ____________________   Data: ____/____/______'); y-=7*mm
    rowh=8.2*mm; col1=25*mm; tablew=util
    c.setFillColor(colors.HexColor('#182231')); c.rect(margem,y-rowh,tablew,rowh,stroke=0,fill=1)
    c.setFillColor(colors.white); c.setFont('Helvetica-Bold',8); c.drawCentredString(margem+col1/2,y-5.2*mm,'Nº'); c.drawString(margem+col1+4*mm,y-5.2*mm,'CIRCUITO'); y-=rowh
    rows=[({'id':'GERAL','tipo':'GERAL'},f'Disjuntor geral — {dg} A' if dg else 'Disjuntor geral')]
    rows += [({'id':f"C{int(q.get('numero',0)):02d}",'tipo':_tipo(q)},_descricao(q,_tipo(q))) for q in circuitos]
    for meta,desc in rows:
        if y-rowh < 18*mm:
            c.showPage(); y=H-20*mm
        c.setStrokeColor(colors.HexColor('#D0D3D8')); c.setLineWidth(0.3); c.rect(margem,y-rowh,tablew,rowh,stroke=1,fill=0)
        c.setFillColor(CORES[meta['tipo']]); c.rect(margem,y-rowh,col1,rowh,stroke=0,fill=1)
        c.setFillColor(colors.white); c.setFont('Helvetica-Bold',8); c.drawCentredString(margem+col1/2,y-5.2*mm,meta['id'])
        c.setFillColor(colors.black); f,s=_fit(c,desc,tablew-col1-8*mm,8,5.5,True); c.setFont(f,s); c.drawString(margem+col1+4*mm,y-5.2*mm,desc); y-=rowh
    y-=8*mm
    # régua física de conferência de 100 mm
    x0=margem; c.setStrokeColor(colors.black); c.setLineWidth(0.6); c.line(x0,y,x0+100*mm,y)
    for i in range(0,101,10):
        hh=3*mm if i in (0,50,100) else 2*mm; c.line(x0+i*mm,y,x0+i*mm,y+hh)
    c.setFont('Helvetica',6.5); c.drawString(x0,y-4*mm,'Confira: esta linha deve medir exatamente 100 mm com uma régua.')
    c.drawRightString(W-margem,8*mm,versao)
    c.save(); return buf.getvalue()
