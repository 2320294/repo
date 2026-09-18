from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
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
    # TUE: usa o equipamento real associado ao circuito.
    for k in ('equipamento','descricao_tue','carga','descricao'):
        v = _txt(c.get(k))
        if v and v not in ('-', '—') and not v.upper().startswith('C0') and v.upper() != 'TUE':
            return v
    if tipo == 'CHUVEIRO': return 'Chuveiro'
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

def _quebrar_linhas(c, text, maxw, font='Helvetica', size=4.6, max_linhas=3, minsize=2.8):
    """Quebra por palavras e reduz a fonte até NENHUMA linha ultrapassar a etiqueta."""
    text = _txt(text) or '-'
    palavras = text.replace(' + ', ', ').split()
    fs = size
    while fs >= minsize:
        linhas=[]; atual=''
        for palavra in palavras:
            teste = palavra if not atual else atual + ' ' + palavra
            if c.stringWidth(teste, font, fs) <= maxw:
                atual=teste
            else:
                if atual: linhas.append(atual)
                atual=palavra
        if atual: linhas.append(atual)
        if len(linhas) <= max_linhas and all(c.stringWidth(l,font,fs) <= maxw for l in linhas):
            return linhas, fs
        fs -= 0.15
    # Último recurso: reparte tokens longos por caracteres, sempre dentro da largura.
    fs=minsize; linhas=[]; atual=''
    for ch in text:
        teste=atual+ch
        if c.stringWidth(teste,font,fs) <= maxw or not atual:
            atual=teste
        else:
            linhas.append(atual.rstrip()); atual=ch.lstrip()
    if atual: linhas.append(atual.rstrip())
    return linhas[:max_linhas], fs

def _descricao(circ, tipo):
    nome = _nome_tipo(circ,tipo)
    amb = _txt(circ.get('ambiente')) or '-'
    return f'{nome} — {amb}'

def _fases_ordem(c):
    fase = _txt(c.get('fase')).upper().replace('/', '-').replace(' ', '')
    tokens = tuple(x for x in ('A','B','C') if x in fase)
    return {
        ('A',): 0, ('B',): 1, ('C',): 2,
        ('A','B'): 3, ('A','C'): 4, ('B','C'): 5,
        ('A','B','C'): 6,
    }.get(tokens, 99)

def _ordem_fisica_qdc(c):
    """Mesma chave usada no diagrama de montagem do QDC (mapa_qdc).

    A faixa de etiquetas deve sair na sequência física em que os DJs aparecem:
    SEM DR, DR1, DR2...; dentro do grupo, fase; depois número do circuito.
    """
    grupo = _txt(c.get('dr') or c.get('grupo') or 'SEM DR').upper() or 'SEM DR'
    if grupo == 'SEM DR':
        ordem_grupo = 0
    else:
        import re
        m = re.search(r'(\d+)', grupo)
        ordem_grupo = int(m.group(1)) if m else 999
    try:
        numero = int(c.get('numero', 0) or 0)
    except Exception:
        numero = 9999
    return (ordem_grupo, grupo, _fases_ordem(c), numero)

def _ordem_dispositivo_qdc(d):
    """Replica a ordenação aplicada em desenhar_mapa_fisico_qdc()."""
    grupo = _txt(d.get('grupo') or 'SEM DR').upper() or 'SEM DR'
    if grupo == 'SEM DR':
        ordem_grupo = 0
    else:
        import re
        m = re.search(r'(\d+)', grupo)
        ordem_grupo = int(m.group(1)) if m else 999
    fase = _txt(d.get('fase')).upper().replace('/', '-').replace(' ', '')
    tokens = tuple(x for x in ('A','B','C') if x in fase)
    assinatura = {('A',):0,('B',):1,('C',):2,('A','B'):3,('A','C'):4,('B','C'):5,('A','B','C'):6}.get(tokens,99)
    import re
    ident=_txt(d.get('identificador')).upper()
    m=re.search(r'(\d+)',ident)
    numero=int(m.group(1)) if m else 9999
    return (ordem_grupo, grupo, assinatura, numero)

def _fileiras_do_mapa(mapa_fisico, circuitos):
    """Retorna exatamente as fileiras visuais do diagrama de montagem.

    Linha 1 = DG + DPS + IDR/DR. As demais linhas usam a mesma ordem e a
    mesma capacidade modular (colunas) do desenho do QDC.
    """
    mapa=dict(mapa_fisico or {})
    dispositivos=[dict(d) for d in (mapa.get('dispositivos') or [])]
    if not dispositivos:
        return None
    gerais=[d for d in dispositivos if _txt(d.get('tipo')).upper() in {'DG','DPS','IDR'}]
    djs=sorted([d for d in dispositivos if _txt(d.get('tipo')).upper()=='DJ'], key=_ordem_dispositivo_qdc)
    colunas=max(1,int(mapa.get('colunas',0) or 0))
    linhas=[gerais]
    atual=[]; usados=0
    for d in djs:
        mod=max(1,int(d.get('modulos',1) or 1))
        if atual and usados+mod>colunas:
            linhas.append(atual); atual=[]; usados=0
        atual.append(d); usados+=mod
    if atual: linhas.append(atual)
    return linhas

def gerar_pdf_etiquetas_qdc(nome_projeto, circuitos, disjuntor_geral_a=None, polos_geral=2, versao='', mapa_fisico=None):
    circuitos=[dict(x) for x in (circuitos or []) if int(x.get('numero',0) or 0)>0]
    por_id={f"C{int(x.get('numero',0)):02d}":x for x in circuitos}
    fileiras=_fileiras_do_mapa(mapa_fisico,circuitos)
    # Fallback apenas para projetos antigos que ainda não regeneraram o CAD.
    if not fileiras:
        circuitos=sorted(circuitos,key=_ordem_fisica_qdc)
        fileiras=[[{'tipo':'DG','identificador':'DG','modulos':max(1,min(3,int(polos_geral or 1))),'corrente_a':int(disjuntor_geral_a or 0)}]]
        fileiras.append([{'tipo':'DJ','identificador':f"C{int(x.get('numero',0)):02d}",'modulos':_polos(x)} for x in circuitos])

    # A3 paisagem permite preservar fisicamente fileiras de até 18 módulos
    # (18 x 17,5 mm = 315 mm), sem reduzir a escala real das etiquetas.
    pagesize=landscape(A3)
    buf=BytesIO(); c=canvas.Canvas(buf,pagesize=pagesize); W,H=pagesize
    margem=14*mm; util=W-2*margem
    c.setTitle(f'{nome_projeto} - Etiquetas QDC')
    c.setFillColor(colors.black); c.setFont('Helvetica-Bold',13); c.drawString(margem,H-17*mm,'Etiquetas do quadro de distribuição')
    c.setFont('Helvetica',7.5); c.drawString(margem,H-22*mm,'Imprima em Tamanho real (100%). Não use “Ajustar à página”.')
    c.drawRightString(W-margem,H-22*mm,f'Cada módulo: {MODULO_MM:.1f} mm  |  Faixa: {ALTURA_ETIQUETA_MM:.0f} mm')

    def meta_dispositivo(d):
        tipo_d=_txt(d.get('tipo')).upper()
        ident=_txt(d.get('identificador')).upper()
        mod=max(1,int(d.get('modulos',1) or 1))
        if tipo_d=='DG':
            a=int(d.get('corrente_a') or disjuntor_geral_a or 0)
            return {'id':'GERAL','tipo':'GERAL','polos':mod,'linha1':'Disjuntor geral','linha2':f'{a} A' if a else ''}
        if tipo_d=='DPS':
            fase=_txt(d.get('fase')).upper()
            return {'id':ident or 'DPS','tipo':'GERAL','polos':mod,'linha1':'DPS','linha2':f'Fase {fase}' if fase else ''}
        if tipo_d=='IDR':
            corrente=d.get('corrente_a'); sens=d.get('sensibilidade_ma')
            l2=' / '.join(x for x in ((f'{int(corrente)} A' if corrente else ''),(f'{int(sens)} mA' if sens else '')) if x)
            return {'id':ident or 'IDR','tipo':'GERAL','polos':mod,'linha1':'IDR / DR','linha2':l2}
        circ=por_id.get(ident,{})
        tipo=_tipo(circ); amb=_txt(circ.get('ambiente')) or _txt(d.get('ambiente')) or '-'
        return {'id':ident,'tipo':tipo,'polos':mod,'linha1':_nome_tipo(circ,tipo),'linha2':amb}

    y=H-31*mm
    itens_tabela=[]
    for idx,fileira in enumerate(fileiras,1):
        x=margem
        c.setFont('Helvetica',6.5); c.setFillColor(colors.grey); c.drawString(margem,y+3*mm,f'Linha {idx}')
        y-=1*mm
        for d in fileira:
            item=meta_dispositivo(d); itens_tabela.append(item)
            w=item['polos']*MODULO_MM*mm; h=ALTURA_ETIQUETA_MM*mm; topo=3.2*mm
            # Segurança: nunca altera escala. Se uma fileira física exceder A3,
            # continua na mesma página horizontalmente até o limite útil.
            if x+w>W-margem+0.1:
                raise ValueError(f'Fileira {idx} do QDC excede a largura A3 em tamanho real.')
            cor=CORES[item['tipo']]
            c.setStrokeColor(colors.HexColor('#B8B8B8')); c.setLineWidth(0.25); c.rect(x,y-h,w,h,stroke=1,fill=0)
            c.setFillColor(cor); c.rect(x,y-topo,w,topo,stroke=0,fill=1)
            c.setFillColor(colors.white); c.setFont('Helvetica-Bold',6.2); c.drawCentredString(x+w/2,y-2.35*mm,item['id'])
            c.setFillColor(colors.black)
            linhas1,fs1=_quebrar_linhas(c,item['linha1'],w-1.8*mm,'Helvetica-Bold',5.4,2,3.0)
            linhas2,fs2=_quebrar_linhas(c,item['linha2'],w-1.8*mm,'Helvetica',4.4,3,2.6)
            if len(linhas1)==1:
                c.setFont('Helvetica-Bold',fs1); c.drawCentredString(x+w/2,y-6.15*mm,linhas1[0]); base_y=y-8.45*mm
            else:
                c.setFont('Helvetica-Bold',fs1); c.drawCentredString(x+w/2,y-5.55*mm,linhas1[0]); c.drawCentredString(x+w/2,y-7.15*mm,linhas1[1]); base_y=y-8.75*mm
            c.setFont('Helvetica',fs2)
            for j,linha_txt in enumerate(linhas2): c.drawCentredString(x+w/2,base_y-j*1.45*mm,linha_txt)
            x+=w
        y-=18*mm

    # Régua de conferência imediatamente abaixo das etiquetas físicas.
    # Ela valida a impressão 1:1 das etiquetas (17,5 mm por módulo x 12 mm),
    # portanto não deve ficar visualmente associada à tabela da porta.
    # Rev.186: cria uma separação visual clara entre a última fileira de
    # etiquetas, a régua de aferição e o quadro de identificação.
    y_regua = y + 2*mm
    x0 = margem
    c.setStrokeColor(colors.black); c.setLineWidth(0.6); c.line(x0,y_regua,x0+100*mm,y_regua)
    for i in range(0,101,10):
        hh=3*mm if i in (0,50,100) else 2*mm
        c.line(x0+i*mm,y_regua,x0+i*mm,y_regua+hh)
    c.setFillColor(colors.black); c.setFont('Helvetica',6.5)
    c.drawString(x0,y_regua-4*mm,'Confira: esta linha deve medir exatamente 100 mm com uma régua.')
    # Folga após a régua/legenda antes do quadro de identificação.
    y = y_regua - 14*mm

    # Tabela da porta: somente GERAL + circuitos finais. DPS e IDR/DR ficam
    # exclusivamente na faixa física de etiquetas da Linha 1.
    rows=[]
    for item in itens_tabela:
        ident=item['id'].upper()
        if ident=='GERAL':
            desc=item['linha1']+(f" — {item['linha2']}" if item['linha2'] else '')
            rows.append((item,desc))
        elif ident.startswith('C') and ident[1:].isdigit():
            circ=por_id.get(item['id'],{}); desc=_descricao(circ,_tipo(circ))
            rows.append((item,desc))

    # Mantém TODO o bloco "Identificação dos circuitos" na mesma página.
    # Primeiro tenta o tamanho normal no espaço restante. Se não couber, começa
    # em nova página. Em projetos maiores, compacta apenas tabela/fontes; a faixa
    # de etiquetas acima continua SEMPRE em escala física 1:1 (17,5 x 12 mm).
    # Rev.186: a tabela da porta não ocupa mais toda a largura da folha.
    # Cada coluna acompanha o conteúdo real, com limite para descrições longas;
    # nesses casos o texto quebra em linhas em vez de "esticar" a tabela.
    fonte_tabela = 8.0
    pad_x = 3.0*mm
    col1 = max(18*mm, c.stringWidth('GERAL','Helvetica-Bold',fonte_tabela)+2*pad_x)
    maior_desc = max([c.stringWidth(desc,'Helvetica-Bold',fonte_tabela) for _,desc in rows] +
                     [c.stringWidth('CIRCUITO','Helvetica-Bold',fonte_tabela)])
    col2 = min(max(58*mm, maior_desc+2*pad_x), 175*mm)
    tablew = col1 + col2

    # Calcula previamente a quebra de cada descrição e a altura real de cada
    # linha. Assim a tabela termina exatamente no conteúdo e continua inteira.
    linhas_rows=[]
    for meta,desc in rows:
        linhas,fs = _quebrar_linhas(c,desc,col2-2*pad_x,'Helvetica-Bold',fonte_tabela,3,5.0)
        rh=max(7.0*mm,(len(linhas)*3.2+3.0)*mm)
        linhas_rows.append((meta,desc,linhas,fs,rh))

    rowh_cab=8.2*mm
    altura_fixa=12*mm
    margem_inferior=16*mm
    altura_tabela=rowh_cab+sum(x[4] for x in linhas_rows)
    necessario=altura_fixa+altura_tabela+margem_inferior
    if y < necessario:
        c.showPage(); y=H-20*mm

    # Se um projeto excepcional ainda exceder uma página, compacta apenas a
    # tabela da porta. As etiquetas e a régua de 100 mm permanecem 1:1.
    disponivel=max(1*mm,y-altura_fixa-margem_inferior)
    escala_texto=min(1.0, disponivel/max(1*mm,altura_tabela))
    escala_altura=min(1.0, disponivel/max(1*mm,altura_tabela))
    rowh=rowh_cab*escala_altura

    c.setFillColor(colors.black); c.setFont('Helvetica-Bold',11*escala_texto); c.drawString(margem,y,'Quadro de distribuição — Identificação dos circuitos'); y-=5*mm
    c.setFont('Helvetica',7*escala_texto); c.drawString(margem,y,'Local: ____________________   Responsável: ____________________   Data: ____/____/______'); y-=7*mm

    c.setFillColor(colors.HexColor('#182231')); c.rect(margem,y-rowh,tablew,rowh,stroke=0,fill=1)
    c.setFillColor(colors.white); c.setFont('Helvetica-Bold',8*escala_texto)
    c.drawCentredString(margem+col1/2,y-rowh*0.64,'Nº')
    c.drawString(margem+col1+pad_x,y-rowh*0.64,'CIRCUITO'); y-=rowh

    for meta,desc,linhas,fs,rh_base in linhas_rows:
        rh=rh_base*escala_altura
        c.setStrokeColor(colors.HexColor('#D0D3D8')); c.setLineWidth(0.3); c.rect(margem,y-rh,tablew,rh,stroke=1,fill=0)
        c.setFillColor(CORES[meta['tipo']]); c.rect(margem,y-rh,col1,rh,stroke=0,fill=1)
        c.setFillColor(colors.white); c.setFont('Helvetica-Bold',8*escala_texto); c.drawCentredString(margem+col1/2,y-rh*0.58,meta['id'])
        c.setFillColor(colors.black); c.setFont('Helvetica-Bold',fs*escala_texto)
        line_h=3.2*mm*escala_altura
        bloco_h=len(linhas)*line_h
        yy=y-(rh-bloco_h)/2-line_h*0.78
        for linha in linhas:
            c.drawString(margem+col1+pad_x,yy,linha); yy-=line_h
        y-=rh

    c.setFillColor(colors.black); c.setFont('Helvetica',6.5)
    c.drawRightString(W-margem,8*mm,f'Versão: {versao}')
    c.save(); return buf.getvalue()
