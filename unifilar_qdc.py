
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
    msp.add_text(
        str(text),
        dxfattribs={"layer":LAYER_UNIFILAR_TEXTO,"height":h,"insert":(x,y)}
    )

def _breaker(msp,x,y):
    _rect(msp,x-0.28,y-0.16,x+0.28,y+0.16)
    _line(msp,(x-0.18,y-0.09),(x+0.18,y+0.09))

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

    # Layout 9.4: cabeçalho com linhas independentes e maior respiro.
    x0=max_x+3.0
    y0=max_y
    largura=15.5
    espac=0.88
    cabecalho=2.05
    bloco_protecao=3.00
    altura=max(10.0,cabecalho+bloco_protecao+len(circuitos)*espac+1.0)
    ybase=y0-altura
    _rect(msp,x0,ybase,x0+largura,y0)

    parametros_rede=dict(parametros_rede or {})
    resultado_demanda=dict(resultado_demanda or {})
    resumo_balanceamento=dict(resumo_balanceamento or {})
    resumo_drs=list(resumo_drs or [])
    resumo_protecao=dict(resumo_protecao or {})

    tipo_for=str(parametros_rede.get("tipo_fornecimento","A definir"))
    tensao_for=str(parametros_rede.get("tensao_fornecimento","A definir"))

    # Cabeçalho: corrigido para não sobrepor textos.
    _text(msp,"DIAGRAMA UNIFILAR DO QDC",x0+0.55,y0-0.42,0.24)
    _text(msp,f"FASE 9.7 | FORNECIMENTO: {tipo_for} | {tensao_for}",
          x0+0.55,y0-0.82,0.135)
    _text(msp,f"TENSAO DE PROJETO DOS CIRCUITOS: {int(tensao_projeto)} V",
          x0+0.55,y0-1.12,0.125)

    cargas=resumo_balanceamento.get("fases",{})
    if cargas:
        txt=" | ".join(f"{f}: {p/1000:.2f} kW" for f,p in cargas.items())
        _text(msp,f"BALANCEAMENTO INSTALADO | {txt}",
              x0+0.55,y0-1.42,0.12)
        des=resumo_balanceamento.get("desequilibrio_pct")
        if des is not None:
            _text(msp,f"DESEQUILIBRIO PRELIMINAR: {des:.1f}%",
                  x0+0.55,y0-1.70,0.105)

    xp=x0+1.30
    yrede=y0-2.35
    _text(msp,"REDE",xp-0.18,yrede+0.18,0.12)
    _line(msp,(xp,yrede+0.12),(xp,yrede-0.22))

    ydg=yrede-0.62
    _breaker(msp,xp,ydg)
    _text(msp,"DG",xp+0.48,ydg+0.08,0.14)
    dg=resultado_demanda.get("disjuntor_geral_a")
    pd=resultado_demanda.get("potencia_demanda_w")
    ic=resultado_demanda.get("corrente_demanda_a")
    polos_dg=str(resumo_protecao.get("dg_polos","") or "")
    if dg is not None:
        texto_dg=f"{int(dg)} A"
        if polos_dg:
            texto_dg += f" {polos_dg}"
        _text(msp,texto_dg,xp+0.48,ydg-0.12,0.105)

    if pd is not None:
        _text(msp,f"DEMANDA: {pd/1000:.2f} kW",xp+4.10,ydg+0.07,0.105)
    if ic is not None:
        _text(msp,f"CORRENTE EQUIVALENTE: {ic:.1f} A",xp+4.10,ydg-0.14,0.105)

    # Condutores do alimentador identificados no trecho antes do DG.
    sf=resumo_protecao.get("alimentador_fase_mm2")
    sn=resumo_protecao.get("alimentador_neutro_mm2")
    spe=resumo_protecao.get("alimentador_pe_mm2")
    comp=str(resumo_protecao.get("alimentador_composicao","") or "")
    if sf is not None:
        if comp.startswith("3F"):
            partes=[f"3F x {sf:g} mm2"]
        elif comp.startswith("2F"):
            partes=[f"2F x {sf:g} mm2"]
        else:
            partes=[f"F {sf:g} mm2"]
        if sn is not None:
            partes.append(f"N {sn:g} mm2")
        if spe is not None:
            partes.append(f"PE {spe:g} mm2")
        _text(
            msp,
            "ALIMENTADOR: " + " | ".join(partes),
            xp+0.48,
            yrede-0.15,
            0.090
        )

    _line(msp,(xp,yrede-0.22),(xp,ydg+0.16))

    ydps=ydg-0.82
    _line(msp,(xp,ydg-0.16),(xp,ydps+0.18))
    _rect(msp,xp-0.28,ydps-0.18,xp+0.28,ydps+0.18)
    _text(msp,"DPS",xp-0.15,ydps-0.05,0.12)

    # DRs reais da fase: blocos separados, com legenda.
    ydr=ydps-0.90
    _line(msp,(xp,ydps-0.18),(xp,ydr+0.18))
    if resumo_drs:
        xdr=xp
        for i,g in enumerate(resumo_drs):
            if i:
                _line(msp,(xdr-1.15,ydr),(xdr-0.30,ydr))
            _rect(msp,xdr-0.30,ydr-0.18,xdr+0.30,ydr+0.18)
            _text(msp,g["dr"],xdr-0.16,ydr-0.05,0.11)
            nums=", ".join(f"C{n:02d}" for n in g["circuitos"])
            nominal=g.get("corrente_nominal_a")
            sens=g.get("sensibilidade_ma",30)
            spec=(f"{nominal} A / {sens} mA" if nominal is not None else f"{sens} mA")
            _text(msp,f"{spec} | {nums}",xdr-0.30,ydr-0.42,0.085)
            xdr+=3.00
    else:
        _rect(msp,xp-0.30,ydr-0.18,xp+0.30,ydr+0.18)
        _text(msp,"DR",xp-0.10,ydr-0.05,0.12)
        _text(msp,"SEM GRUPOS DE TOMADAS",xp+0.48,ydr-0.05,0.10)

    # Saídas em uma seção própria, sem compartilhar a linha dos DRs.
    ybar=ydr-0.92
    yend=ybar-max(0,len(circuitos)-1)*espac
    _line(msp,(xp,ydr-0.18),(xp,ybar))
    _line(msp,(xp,ybar),(xp,yend))
    xdj=x0+3.20
    xt=x0+4.10

    for idx,c in enumerate(circuitos,start=1):
        cy=ybar-(idx-1)*espac

        tipo=str(c.get("tipo","Circuito"))
        amb=str(c.get("ambiente",""))
        pot=float(c.get("potencia",0) or 0)
        cor=float(c.get("corrente",0) or 0)
        bit=float(c.get("bitola",0) or 0)
        dj=int(c.get("disjuntor",0) or 0)
        fase=str(c.get("fase","A definir"))
        polos=str(c.get("polos","A definir"))
        dr=str(c.get("dr","") or "").strip()
        numero=int(c.get("numero",idx))
        cond="2F + PE" if tipo.upper()=="TUE" else "F + N + PE"

        _line(msp,(xp,cy),(xdj-0.28,cy))

        # Bitola fica no trecho a montante do disjuntor.
        if bit > 0:
            if tipo.upper()=="TUE":
                texto_cabo=f"2F x {bit:g} mm2 + PE {bit:g} mm2"
            else:
                texto_cabo=f"F+N {bit:g} mm2 + PE {bit:g} mm2"
            _text(msp,texto_cabo,xp+0.25,cy+0.13,0.082)

        _breaker(msp,xdj,cy)

        # Identificação do disjuntor junto ao símbolo.
        if dj > 0:
            texto_dj=f"DJ {dj} A"
            if polos and polos!="A definir":
                texto_dj += f" {polos}"
            _text(msp,texto_dj,xdj-0.27,cy-0.31,0.082)

        _line(msp,(xdj+0.28,cy),(xt-0.18,cy))

        linha1=f"C{numero:02d} | {tipo} | {amb} | FASE {fase}"
        if dr:
            linha1 += f" | {dr}"
        _text(msp,linha1,xt,cy+0.11,0.125)

        # Sem repetir bitola e DJ depois do símbolo.
        _text(msp,f"{pot:.0f} W | {cor:.2f} A | {cond}",
              xt,cy-0.13,0.10)

    xn=x0+largura-1.35
    xpe=x0+largura-0.68
    ybt=y0-2.30
    ybb=ybase+0.60
    _line(msp,(xn,ybt),(xn,ybb))
    _line(msp,(xpe,ybt),(xpe,ybb))
    _text(msp,"N",xn-0.05,ybt+0.12,0.14)
    _text(msp,"PE",xpe-0.08,ybt+0.12,0.14)

    return {
        "quantidade_circuitos":len(circuitos),
        "quantidade_drs":len(resumo_drs),
        "origem":(x0,ybase)
    }
