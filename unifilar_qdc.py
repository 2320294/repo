
LAYER_UNIFILAR = "PROJ_ELETRICA_UNIFILAR_QDC"
LAYER_UNIFILAR_TEXTO = "PROJ_ELETRICA_UNIFILAR_QDC_TEXTO"

def _line(msp,p1,p2):
    msp.add_line(p1,p2,dxfattribs={"layer":LAYER_UNIFILAR})

def _rect(msp,x1,y1,x2,y2):
    msp.add_lwpolyline(
        [(x1,y1),(x2,y1),(x2,y2),(x1,y2),(x1,y1)],
        dxfattribs={"layer":LAYER_UNIFILAR}
    )

def _text(msp,text,x,y,h=0.15):
    if text is None or str(text).strip()=="":
        return
    msp.add_text(
        str(text),
        dxfattribs={"layer":LAYER_UNIFILAR_TEXTO,"height":h,"insert":(x,y)}
    )

def _breaker(msp,x,y,w=0.56,h=0.32):
    _rect(msp,x-w/2,y-h/2,x+w/2,y+h/2)
    _line(msp,(x-w*0.32,y-h*0.28),(x+w*0.32,y+h*0.28))

def _cabo_texto(c):
    bit=float(c.get("bitola",0) or 0)
    if bit<=0:
        return ""
    tipo=str(c.get("tipo","")).upper()
    if tipo=="TUE":
        return f"2F {bit:g} mm2 + PE {bit:g} mm2"
    return f"F+N {bit:g} mm2 + PE {bit:g} mm2"

def _linha_circuito(msp,c,x_bus,x_dj,x_info,y):
    numero=int(c.get("numero",0) or 0)
    tipo=str(c.get("tipo","Circuito"))
    amb=str(c.get("ambiente",""))
    fase=str(c.get("fase","") or "").strip()
    polos=str(c.get("polos","") or "").strip()
    pot=float(c.get("potencia",0) or 0)
    cor=float(c.get("corrente",0) or 0)
    dj=int(c.get("disjuntor",0) or 0)

    # Trecho de saída com espaço reservado real para a bitola.
    _line(msp,(x_bus,y),(x_dj-0.34,y))
    cabo=_cabo_texto(c)
    if cabo:
        _text(msp,cabo,x_bus+0.22,y+0.13,0.075)

    _breaker(msp,x_dj,y)
    if dj>0:
        txt=f"DJ {dj} A"
        if polos and polos!="A definir":
            txt+=f" {polos}"
        _text(msp,txt,x_dj-0.27,y-0.31,0.080)

    _line(msp,(x_dj+0.28,y),(x_info-0.18,y))

    cab=f"C{numero:02d} | {tipo} | {amb}"
    if fase and fase!="A definir":
        cab+=f" | FASE {fase}"
    _text(msp,cab,x_info,y+0.10,0.115)
    _text(msp,f"{pot:.0f} W | {cor:.2f} A",x_info,y-0.13,0.090)

def desenhar_unifilar_qdc(
    msp,circuitos,polilinhas_ambientes,tensao_projeto=220,
    parametros_rede=None,resultado_demanda=None,
    resumo_balanceamento=None,resumo_drs=None,
    resumo_protecao=None
):
    circuitos=list(circuitos or [])
    if not circuitos:
        return None

    pontos=[]
    for pol in polilinhas_ambientes or []:
        pontos.extend(list(pol or []))
    max_x=max((p[0] for p in pontos),default=0.0)
    max_y=max((p[1] for p in pontos),default=10.0)

    parametros_rede=dict(parametros_rede or {})
    resultado_demanda=dict(resultado_demanda or {})
    resumo_balanceamento=dict(resumo_balanceamento or {})
    resumo_drs=list(resumo_drs or [])
    resumo_protecao=dict(resumo_protecao or {})

    # Separa circuitos realmente por proteção.
    grupos={}
    sem_dr=[]
    for c in circuitos:
        dr=str(c.get("dr","") or "").strip()
        if dr:
            grupos.setdefault(dr,[]).append(c)
        else:
            sem_dr.append(c)

    ordem_drs=[g.get("dr") for g in resumo_drs if g.get("dr")]
    for dr in grupos:
        if dr not in ordem_drs:
            ordem_drs.append(dr)

    secoes=[]
    if sem_dr:
        secoes.append(("SEM_DR","CIRCUITOS SEM DR",sem_dr,None))
    resumo_por_id={g.get("dr"):g for g in resumo_drs}
    for dr in ordem_drs:
        itens=grupos.get(dr,[])
        if itens:
            secoes.append((dr,dr,itens,resumo_por_id.get(dr,{})))

    # Dimensões generosas para impedir encavalamento.
    x0=max_x+3.0
    y0=max_y
    largura=18.5
    header_h=2.15
    entrada_h=2.45
    sec_header=0.72
    circ_pitch=0.92
    gap_sec=0.42
    corpo=sum(sec_header+len(sec[2])*circ_pitch+gap_sec for sec in secoes)
    altura=max(11.0,header_h+entrada_h+corpo+0.80)
    ybase=y0-altura
    _rect(msp,x0,ybase,x0+largura,y0)

    tipo_for=str(parametros_rede.get("tipo_fornecimento","") or "")
    tensao_for=str(parametros_rede.get("tensao_fornecimento","") or "")

    _text(msp,"DIAGRAMA UNIFILAR DO QDC",x0+0.55,y0-0.42,0.24)
    linha_for="FASE 9.8"
    if tipo_for: linha_for+=f" | {tipo_for}"
    if tensao_for: linha_for+=f" | {tensao_for}"
    _text(msp,linha_for,x0+0.55,y0-0.82,0.13)
    _text(msp,f"TENSAO DOS CIRCUITOS: {int(tensao_projeto)} V",
          x0+0.55,y0-1.12,0.115)

    cargas=resumo_balanceamento.get("fases",{})
    if cargas:
        txt=" | ".join(f"{f}: {p/1000:.2f} kW" for f,p in cargas.items())
        _text(msp,f"BALANCEAMENTO | {txt}",x0+0.55,y0-1.43,0.105)

    # Entrada geral.
    x_main=x0+1.25
    yrede=y0-2.28
    _text(msp,"REDE",x_main-0.18,yrede+0.18,0.11)

    ydg=yrede-0.68
    _line(msp,(x_main,yrede+0.08),(x_main,ydg+0.16))
    _breaker(msp,x_main,ydg)
    _text(msp,"DG",x_main+0.48,ydg+0.08,0.13)

    dg=resultado_demanda.get("disjuntor_geral_a")
    polos=str(resumo_protecao.get("dg_polos","") or "")
    if dg is not None:
        txt=f"{int(dg)} A"
        if polos: txt+=f" {polos}"
        _text(msp,txt,x_main+0.48,ydg-0.12,0.10)

    pd=resultado_demanda.get("potencia_demanda_w")
    ic=resultado_demanda.get("corrente_demanda_a")
    if pd is not None:
        _text(msp,f"DEMANDA {pd/1000:.2f} kW",x0+4.0,ydg+0.08,0.10)
    if ic is not None:
        _text(msp,f"I DEMANDA {ic:.1f} A",x0+4.0,ydg-0.13,0.10)

    # Alimentador em área própria, sem atravessar o DG.
    sf=resumo_protecao.get("alimentador_fase_mm2")
    sn=resumo_protecao.get("alimentador_neutro_mm2")
    spe=resumo_protecao.get("alimentador_pe_mm2")
    comp=str(resumo_protecao.get("alimentador_composicao","") or "")
    if sf is not None:
        if comp.startswith("3F"): partes=[f"3F {sf:g} mm2"]
        elif comp.startswith("2F"): partes=[f"2F {sf:g} mm2"]
        else: partes=[f"F {sf:g} mm2"]
        if sn is not None: partes.append(f"N {sn:g} mm2")
        if spe is not None: partes.append(f"PE {spe:g} mm2")
        _text(msp,"ALIMENTADOR | "+" | ".join(partes),
              x0+7.0,ydg-0.02,0.095)

    ydps=ydg-0.75
    _line(msp,(x_main,ydg-0.16),(x_main,ydps+0.16))
    _rect(msp,x_main-0.28,ydps-0.16,x_main+0.28,ydps+0.16)
    _text(msp,"DPS",x_main-0.15,ydps-0.05,0.11)

    # Barramento principal alimenta visualmente cada seção/DR.
    y_start=ydps-0.72
    y_last=y_start-corpo+0.40
    _line(msp,(x_main,ydps-0.16),(x_main,y_last))

    x_dr=x0+3.05
    x_sec_bus=x0+4.45
    x_dj=x0+8.15
    x_info=x0+9.15

    y=y_start
    for sid,titulo,itens,resumo in secoes:
        # derivação horizontal do barramento principal
        _line(msp,(x_main,y),(x_dr-0.34,y))

        if sid=="SEM_DR":
            _text(msp,titulo,x_dr,y+0.09,0.12)
            # pequena ligação direta ao barramento da seção
            _line(msp,(x_dr+1.65,y),(x_sec_bus,y))
        else:
            _breaker(msp,x_dr,y,w=0.68,h=0.36)
            _text(msp,sid,x_dr-0.15,y-0.05,0.11)

            nominal=resumo.get("corrente_nominal_a")
            sens=resumo.get("sensibilidade_ma")
            spec=[]
            if nominal is not None: spec.append(f"{nominal} A")
            if sens is not None: spec.append(f"{sens} mA")
            if spec:
                _text(msp," / ".join(spec),x_dr+0.48,y+0.04,0.095)

            desc=str(resumo.get("descricao","") or "")
            if desc:
                _text(msp,desc,x_dr+0.48,y-0.16,0.082)
            _line(msp,(x_dr+0.34,y),(x_sec_bus,y))

        # barramento exclusivo da seção, deixando claro quem o DR alimenta
        first_y=y-sec_header
        last_y=first_y-(len(itens)-1)*circ_pitch
        _line(msp,(x_sec_bus,y),(x_sec_bus,last_y))

        for j,c in enumerate(itens):
            cy=first_y-j*circ_pitch
            _linha_circuito(msp,c,x_sec_bus,x_dj,x_info,cy)

        y=last_y-circ_pitch-gap_sec

    # Barramentos N e PE separados à direita.
    xn=x0+largura-1.35
    xpe=x0+largura-0.65
    _line(msp,(xn,y0-2.25),(xn,ybase+0.55))
    _line(msp,(xpe,y0-2.25),(xpe,ybase+0.55))
    _text(msp,"N",xn-0.05,y0-2.08,0.13)
    _text(msp,"PE",xpe-0.08,y0-2.08,0.13)

    return {
        "quantidade_circuitos":len(circuitos),
        "quantidade_drs":len([s for s in secoes if s[0]!="SEM_DR"]),
        "quantidade_secoes":len(secoes),
        "origem":(x0,ybase)
    }
