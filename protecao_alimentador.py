
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
    Fase 10.3: consolidação preliminar das proteções e alimentador.
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
