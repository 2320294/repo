
BITOLAS_COBRE_MM2 = (1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95)
AMPACIDADE_REFERENCIA_A = {
    1.5: 15.5, 2.5: 21.0, 4: 28.0, 6: 36.0, 10: 50.0,
    16: 68.0, 25: 89.0, 35: 110.0, 50: 134.0, 70: 171.0, 95: 207.0,
}

def _f(v, d=0.0):
    try: return float(v)
    except Exception: return float(d)

def _bitola_por_corrente(corrente):
    i=max(0.0,_f(corrente))
    for b in BITOLAS_COBRE_MM2:
        if AMPACIDADE_REFERENCIA_A[b] >= i:
            return b
    return None

def _pe_por_fase(sf):
    if sf is None: return None
    sf=float(sf)
    if sf <= 16: return sf
    if sf <= 35: return 16.0
    return sf/2.0

def _polos_dg(tipo):
    if tipo=="Monofásico": return "1P"
    if tipo=="Bifásico": return "2P"
    if tipo=="Trifásico": return "3P"
    return ""

def avaliar_protecoes_alimentador(resultado_demanda, parametros_rede, circuitos, resumo_drs):
    """
    Fase 13.6 Rev.124: consolidação preliminar das proteções e alimentador.
    A bitola usa uma ampacidade de referência conservadora interna apenas para
    pré-dimensionamento. O resultado fica explicitamente condicionado à forma
    de instalação, temperatura, agrupamento, queda de tensão e perfil normativo.
    """
    resultado_demanda=dict(resultado_demanda or {})
    parametros_rede=dict(parametros_rede or {})
    circuitos=list(circuitos or [])
    resumo_drs=list(resumo_drs or [])

    ib=resultado_demanda.get("corrente_demanda_a")
    dg=resultado_demanda.get("disjuntor_geral_a")
    tipo=str(parametros_rede.get("tipo_fornecimento",""))
    polos=_polos_dg(tipo)

    sf=_bitola_por_corrente(dg if dg is not None else ib)
    spe=_pe_por_fase(sf)
    sn=sf

    if tipo=="Monofásico":
        composicao="F + N + PE"
    elif tipo=="Bifásico":
        composicao="2F + N + PE"
    elif tipo=="Trifásico":
        composicao="3F + N + PE"
    else:
        composicao=""

    maior_dj=max([int(c.get("disjuntor",0) or 0) for c in circuitos] or [0])
    hierarquia_dj = (dg is not None and dg >= maior_dj)

    dr_ok=True
    for dr in resumo_drs:
        nominal=dr.get("corrente_nominal_a")
        maior=dr.get("maior_dj_a")
        if nominal is None or maior is None or nominal < maior:
            dr_ok=False

    pendencias=[]
    if ib is None: pendencias.append("corrente de demanda")
    if dg is None: pendencias.append("disjuntor geral")
    if sf is None: pendencias.append("seção preliminar do alimentador")
    pendencias += [
        "método de instalação do alimentador",
        "temperatura/agrupamento",
        "queda de tensão",
        "corrente de curto-circuito presumida no QDC",
        "capacidade de interrupção dos disjuntores",
        "curvas/tabelas de seletividade do fabricante",
    ]

    return {
        "corrente_projeto_a": ib,
        "dg_a": dg,
        "dg_polos": polos,
        "alimentador_fase_mm2": sf,
        "alimentador_neutro_mm2": sn,
        "alimentador_pe_mm2": spe,
        "alimentador_composicao": composicao,
        "maior_disjuntor_circuito_a": maior_dj,
        "hierarquia_dg_circuitos": "OK" if hierarquia_dj else "REVISAR",
        "hierarquia_dr_circuitos": "OK" if dr_ok else "REVISAR",
        "capacidade_interrupcao": "A definir pelo Icc e fabricante",
        "seletividade": "A validar por curvas/tabelas do fabricante",
        "status": "pre_dimensionado" if dg is not None and sf is not None else "incompleto",
        "pendencias": pendencias,
    }


# FASE 13.6 REV.208 — DIMENSIONAMENTO AUTOMÁTICO DO ALIMENTADOR GERAL
# Critério técnico preliminar do AutoElétrica. As ampacidades são referências
# internas já usadas pelo sistema; a validação executiva permanece do RT.
AMPACIDADE_ALIMENTADOR = {
    "B1": {1.5:17.5,2.5:24.0,4.0:32.0,6.0:41.0,10.0:57.0,16.0:76.0,25.0:101.0,35.0:125.0,50.0:151.0,70.0:192.0,95.0:232.0},
    "B2": {1.5:16.5,2.5:23.0,4.0:30.0,6.0:38.0,10.0:52.0,16.0:69.0,25.0:90.0,35.0:111.0,50.0:133.0,70.0:168.0,95.0:201.0},
}
FATOR_TEMP_ALIMENTADOR = {25:1.03,30:1.00,35:0.94,40:0.87,45:0.79,50:0.71,55:0.61,60:0.50}

def dimensionar_alimentador_geral(corrente_a, dg_a, tipo_fornecimento, tensao_linha_v,
                                  metodo="B1", temperatura_c=30, comprimento_m=0.0,
                                  limite_queda_pct=2.0, fator_agrupamento=1.0):
    metodo=str(metodo or "B1").upper().strip()
    if metodo not in AMPACIDADE_ALIMENTADOR: metodo="B1"
    temp=int(temperatura_c or 30)
    temp_ref=min(FATOR_TEMP_ALIMENTADOR, key=lambda x: abs(x-temp))
    ft=FATOR_TEMP_ALIMENTADOR[temp_ref]
    fg=max(0.10, min(1.00, _f(fator_agrupamento, 1.0)))
    alvo=max(_f(corrente_a), _f(dg_a))
    tabela=AMPACIDADE_ALIMENTADOR[metodo]
    secao=None; iz=None
    for s in sorted(tabela):
        izc=tabela[s]*ft*fg
        if izc+1e-9 >= alvo:
            secao=float(s); iz=float(izc); break
    if secao is None:
        secao=float(max(tabela)); iz=float(tabela[secao]*ft*fg)

    # Queda de tensão resistiva preliminar para cobre (rho=0,0175 ohm.mm²/m).
    # Só interfere na seção quando o usuário informa comprimento > 0.
    comprimento=max(0.0,_f(comprimento_m))
    limite=max(0.1,_f(limite_queda_pct,2.0))
    i=max(0.0,_f(corrente_a))
    v=max(1.0,_f(tensao_linha_v,220.0))
    trif=str(tipo_fornecimento)=="Trifásico"
    def queda(s):
        k=(3.0**0.5) if trif else 2.0
        dv=k*i*0.0175*comprimento/s
        return dv, 100.0*dv/v
    dv,dp=queda(secao)
    secao_amp=secao

    # REV.210 — fecha os dois critérios separadamente e adota a maior seção.
    # A seção por queda representa a menor seção padronizada da tabela interna
    # que atende ao limite informado, independentemente do critério de ampacidade.
    secao_queda=None
    if comprimento>0:
        for s in sorted(tabela):
            dv_q, dp_q = queda(float(s))
            if dp_q <= limite+1e-9:
                secao_queda=float(s)
                break

    if comprimento>0 and secao_queda is not None:
        secao=max(float(secao_amp), float(secao_queda))
        dv,dp=queda(secao)
    else:
        secao=float(secao_amp)
        dv,dp=queda(secao)

    if comprimento <= 0:
        criterio_determinante = "Capacidade de condução (queda de tensão aguardando comprimento)"
    elif secao_queda is None:
        criterio_determinante = "Queda de tensão fora da faixa da tabela interna"
    elif secao_queda > secao_amp:
        criterio_determinante = "Queda de tensão"
    elif secao_amp > secao_queda:
        criterio_determinante = "Capacidade de condução"
    else:
        criterio_determinante = "Capacidade de condução e queda de tensão (mesma seção)"

    # Iz da seção FINAL adotada, já corrigida pelos fatores.
    iz=float(tabela[secao]*ft*fg) if secao in tabela else iz
    sn=secao
    spe=_pe_por_fase(secao)
    tipo_txt=str(tipo_fornecimento or "")
    n_carregados = 3 if tipo_txt == "Trifásico" else (2 if tipo_txt == "Bifásico" else 2)
    ib=i
    inn=_f(dg_a)
    atende_ib_in_iz = (ib <= inn + 1e-9) and (inn <= iz + 1e-9)
    return {
        "metodo":metodo, "temperatura_c":temp, "temperatura_referencia_c":temp_ref,
        "material":"Cobre", "isolacao":"PVC 70 °C", "condutores_carregados":n_carregados,
        "fator_temperatura":ft, "fator_agrupamento":fg, "corrente_projeto_a":i, "ib_a":ib, "in_a":inn, "dg_a":dg_a,
        "atende_ib_in_iz":atende_ib_in_iz,
        "secao_por_capacidade_mm2":secao_amp, "secao_por_queda_mm2":secao_queda,
        "secao_final_mm2":secao, "criterio_determinante":criterio_determinante, "iz_corrigida_a":iz,
        "comprimento_m":comprimento, "limite_queda_pct":limite,
        "queda_tensao_v":dv if comprimento>0 else None,
        "queda_tensao_pct":dp if comprimento>0 else None,
        "fase_mm2":secao, "neutro_mm2":sn, "pe_mm2":spe,
        "status_queda":"OK" if comprimento>0 and dp<=limite else ("REVISAR" if comprimento>0 else "AGUARDANDO_COMPRIMENTO"),
        "criterio":"Pré-dimensionamento técnico AutoElétrica; validar condições reais da instalação e requisitos aplicáveis antes da execução."
    }
