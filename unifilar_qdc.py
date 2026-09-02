
LAYER_UNIFILAR = "PROJ_ELETRICA_UNIFILAR_QDC"
LAYER_UNIFILAR_TEXTO = "PROJ_ELETRICA_UNIFILAR_QDC_TEXTO"


def _line(msp, p1, p2):
    msp.add_line(p1, p2, dxfattribs={"layer": LAYER_UNIFILAR})


def _rect(msp, x1, y1, x2, y2):
    msp.add_lwpolyline(
        [(x1,y1),(x2,y1),(x2,y2),(x1,y2),(x1,y1)],
        dxfattribs={"layer": LAYER_UNIFILAR}
    )


def _text(msp, text, x, y, h=0.15):
    msp.add_text(
        str(text),
        dxfattribs={
            "layer": LAYER_UNIFILAR_TEXTO,
            "height": h,
            "insert": (x, y)
        }
    )


def _breaker(msp, x, y):
    _rect(msp, x-0.28, y-0.16, x+0.28, y+0.16)
    _line(msp, (x-0.18,y-0.09), (x+0.18,y+0.09))


def desenhar_unifilar_qdc(
    msp,
    circuitos,
    polilinhas_ambientes,
    tensao_projeto=220,
    parametros_rede=None,
    resultado_demanda=None,
    resumo_balanceamento=None
):
    circuitos = list(circuitos or [])
    if not circuitos:
        return None

    pontos = []
    for pol in (polilinhas_ambientes or []):
        pontos.extend(list(pol or []))

    max_x = max((p[0] for p in pontos), default=0.0)
    max_y = max((p[1] for p in pontos), default=10.0)

    x0 = max_x + 3.0
    y0 = max_y
    largura = 12.5
    espac = 0.80
    altura = max(8.5, 5.4 + len(circuitos)*espac)
    ybase = y0 - altura

    _rect(msp, x0, ybase, x0+largura, y0)
    _text(msp, "DIAGRAMA UNIFILAR DO QDC - PRELIMINAR", x0+0.45, y0-0.45, 0.24)
    _text(msp, f"ALIMENTACAO DO PROJETO: {int(tensao_projeto)} V", x0+0.45, y0-0.82, 0.16)
    parametros_rede = dict(parametros_rede or {})
    resultado_demanda = dict(resultado_demanda or {})

    tipo = str(parametros_rede.get("tipo_fornecimento", "A definir"))
    tensao = str(parametros_rede.get("tensao_fornecimento", "A definir"))

    _text(
        msp,
        f"FASE 9.3 - {tipo} - {tensao}",
        x0+0.45,
        y0-1.10,
        0.12
    )

    resumo_balanceamento = dict(resumo_balanceamento or {})
    cargas_fases = resumo_balanceamento.get("fases", {})
    if cargas_fases:
        texto_bal = " | ".join(
            f"{fase}: {pot/1000:.2f} kW"
            for fase, pot in cargas_fases.items()
        )
        _text(
            msp,
            f"BALANCEAMENTO: {texto_bal}",
            x0+0.45,
            y0-1.30,
            0.105
        )

    xp = x0 + 1.25
    y = y0 - 1.55
    _text(msp, "REDE", xp-0.18, y+0.18, 0.12)
    _line(msp, (xp,y+0.12), (xp,y-0.18))

    ydg = y-0.52
    _breaker(msp, xp, ydg)
    _text(msp, "DG", xp+0.42, ydg+0.02, 0.14)

    dg = resultado_demanda.get("disjuntor_geral_a")
    corrente_demanda = resultado_demanda.get("corrente_demanda_a")
    potencia_demanda = resultado_demanda.get("potencia_demanda_w")

    _text(
        msp,
        f"{int(dg)} A - PRE-SELECIONADO" if dg is not None else "DG A DEFINIR",
        xp+0.42,
        ydg-0.18,
        0.10
    )

    if corrente_demanda is not None and potencia_demanda is not None:
        _text(
            msp,
            f"DEMANDA {potencia_demanda/1000:.2f} kW | Ieq {corrente_demanda:.1f} A",
            xp+0.42,
            ydg-0.34,
            0.095
        )
    _line(msp, (xp,y-0.18), (xp,ydg+0.16))

    ydps = ydg-0.78
    _line(msp, (xp,ydg-0.16), (xp,ydps+0.18))
    _rect(msp, xp-0.28, ydps-0.18, xp+0.28, ydps+0.18)
    _text(msp, "DPS", xp-0.14, ydps-0.05, 0.12)

    ydr = ydps-0.72
    _line(msp, (xp,ydps-0.18), (xp,ydr+0.18))
    _rect(msp, xp-0.28, ydr-0.18, xp+0.28, ydr+0.18)
    _text(msp, "DR", xp-0.10, ydr-0.05, 0.12)
    _text(msp, "AGRUPAMENTO A DEFINIR", xp+0.42, ydr-0.05, 0.10)

    ybar = ydr-0.55
    yend = ybar - max(0, len(circuitos)-1)*espac
    _line(msp, (xp,ydr-0.18), (xp,ybar))
    _line(msp, (xp,ybar), (xp,yend))

    xdj = x0+3.05
    xt = x0+3.90

    for idx, c in enumerate(circuitos, start=1):
        cy = ybar - (idx-1)*espac
        _line(msp, (xp,cy), (xdj-0.28,cy))
        _breaker(msp, xdj, cy)
        _line(msp, (xdj+0.28,cy), (xt-0.15,cy))

        tipo = str(c.get("tipo","Circuito"))
        amb = str(c.get("ambiente",""))
        pot = float(c.get("potencia",0) or 0)
        cor = float(c.get("corrente",0) or 0)
        bit = float(c.get("bitola",0) or 0)
        dj = int(c.get("disjuntor",0) or 0)
        cond = "2F + PE" if tipo.upper()=="TUE" else "F + N + PE"
        fase = str(c.get("fase", "A definir"))
        polos = str(c.get("polos", "A definir"))
        numero = int(c.get("numero", idx))

        _text(
            msp,
            f"C{numero:02d}  {tipo} - {amb} - FASE {fase}",
            xt, cy+0.10, 0.135
        )
        _text(
            msp,
            f"{pot:.0f} W | {cor:.2f} A | DJ {dj} A {polos} | {bit:g} mm2 | {cond}",
            xt, cy-0.14, 0.105
        )

    # Barramentos esquemáticos.
    xn = x0+largura-1.25
    xpe = x0+largura-0.62
    ybt = y0-1.75
    ybb = ybase+0.60
    _line(msp, (xn,ybt), (xn,ybb))
    _line(msp, (xpe,ybt), (xpe,ybb))
    _text(msp, "N", xn-0.05, ybt+0.12, 0.14)
    _text(msp, "PE", xpe-0.08, ybt+0.12, 0.14)

    return {"quantidade_circuitos": len(circuitos), "origem": (x0,ybase)}
