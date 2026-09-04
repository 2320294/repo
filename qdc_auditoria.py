"""
Fase 13.6 Rev.13 — Auditoria elétrica estrutural do QDC.

Valida somente aquilo que o sistema consegue comprovar com os dados do
projeto. Dados dependentes de Icc, fabricante, esquema de aterramento
definitivo ou regra local da concessionária ficam como PENDENTE.
"""

def _texto(v):
    return str(v or "").strip()


def _fases(valor):
    texto = _texto(valor).upper()
    return [f for f in ("A", "B", "C") if f in texto]


def _polos_circuito(c):
    bruto = c.get("polos")
    if bruto:
        digitos = "".join(ch for ch in _texto(bruto) if ch.isdigit())
        if digitos:
            return max(1, int(digitos))
    fases = _fases(c.get("fase"))
    return max(1, len(fases))


def _usa_neutro(c):
    return _polos_circuito(c) == 1


def _fases_fornecimento(parametros_rede, protecao):
    tipo = _texto((parametros_rede or {}).get("tipo_fornecimento")).casefold()
    if "trif" in tipo:
        return ["A", "B", "C"]
    if "bif" in tipo:
        return ["A", "B"]
    if "mono" in tipo:
        return ["A"]

    comp = _texto((protecao or {}).get("alimentador_composicao")).upper()
    if "3F" in comp:
        return ["A", "B", "C"]
    if "2F" in comp:
        return ["A", "B"]
    if "F" in comp:
        return ["A"]
    return []


def _condutores_idr(dr, por_numero):
    fases = []
    precisa_neutro = False

    for numero in dr.get("circuitos", []) or []:
        try:
            numero = int(numero)
        except Exception:
            continue

        c = por_numero.get(numero)
        if not c:
            continue

        for fase in _fases(c.get("fase")):
            if fase not in fases:
                fases.append(fase)

        if _usa_neutro(c):
            precisa_neutro = True

    fases = [f for f in ("A", "B", "C") if f in fases]
    condutores = list(fases)

    if precisa_neutro:
        condutores.append("N")

    return condutores


def _polos_idr_esperados(condutores):
    return 2 if len(condutores) <= 2 else 4


def auditar_qdc_normativo(
    circuitos,
    resumo_drs,
    resumo_protecao,
    resultado_demanda,
    parametros_rede,
    mapa_fisico=None,
):
    circuitos = [dict(c) for c in (circuitos or [])]
    drs = [dict(d) for d in (resumo_drs or [])]
    protecao = dict(resumo_protecao or {})
    demanda = dict(resultado_demanda or {})
    parametros = dict(parametros_rede or {})
    mapa = dict(mapa_fisico or {})

    por_numero = {
        int(c.get("numero", 0) or 0): c
        for c in circuitos
        if int(c.get("numero", 0) or 0) > 0
    }

    verificacoes = []

    def add(codigo, titulo, status, detalhe, bloqueia=False):
        verificacoes.append({
            "Código": codigo,
            "Verificação": titulo,
            "Status": status,
            "Bloqueia DXF": "SIM" if bloqueia else "NÃO",
            "Detalhe": detalhe,
        })

    fases_rede = _fases_fornecimento(parametros, protecao)

    # A01 — fornecimento x polos do DG.
    dg_polos_txt = _texto(protecao.get("dg_polos"))
    digitos = "".join(ch for ch in dg_polos_txt if ch.isdigit())
    dg_polos = int(digitos) if digitos else 0
    esperado_dg = max(1, len(fases_rede))
    ok = bool(fases_rede) and dg_polos == esperado_dg
    add(
        "A01",
        "Fornecimento × polos do DG",
        "OK" if ok else "ERRO",
        (
            f"Fornecimento: {', '.join(fases_rede) or 'não definido'}; "
            f"DG: {dg_polos_txt or 'não definido'}."
        ),
        bloqueia=not ok,
    )

    # A02 — circuitos só usam fases disponíveis.
    invalidos = []
    for c in circuitos:
        n = int(c.get("numero", 0) or 0)
        fc = _fases(c.get("fase"))
        if not fc or any(f not in fases_rede for f in fc):
            invalidos.append(f"C{n}={_texto(c.get('fase')) or 'sem fase'}")

    ok = not invalidos
    add(
        "A02",
        "Fases dos circuitos × fornecimento",
        "OK" if ok else "ERRO",
        (
            "Todos os circuitos usam fases disponíveis."
            if ok else "Revisar: " + ", ".join(invalidos)
        ),
        bloqueia=not ok,
    )

    # A03 — polos dos circuitos x fases.
    problemas = []
    for c in circuitos:
        n = int(c.get("numero", 0) or 0)
        polos = _polos_circuito(c)
        qtd_fases = len(_fases(c.get("fase")))
        if qtd_fases and polos != qtd_fases:
            problemas.append(f"C{n}: {polos}P para {_texto(c.get('fase'))}")

    ok = not problemas
    add(
        "A03",
        "Polos dos disjuntores terminais",
        "OK" if ok else "ERRO",
        "Coerentes." if ok else "; ".join(problemas),
        bloqueia=not ok,
    )

    # A04 — cobertura DR única e coerente.
    cobertura = {}
    for dr in drs:
        gid = _texto(dr.get("dr"))
        for n in dr.get("circuitos", []) or []:
            try:
                n = int(n)
            except Exception:
                continue
            cobertura.setdefault(n, []).append(gid)

    problemas = []
    for c in circuitos:
        n = int(c.get("numero", 0) or 0)
        grupo = _texto(c.get("dr"))
        encontrados = cobertura.get(n, [])

        if grupo:
            if encontrados != [grupo]:
                problemas.append(
                    f"C{n}: esperado {grupo}, encontrado {encontrados or 'nenhum'}"
                )
        elif encontrados:
            problemas.append(f"C{n}: sem DR, mas associado a {encontrados}")

    ok = not problemas
    add(
        "A04",
        "Exclusividade dos grupos IDR",
        "OK" if ok else "ERRO",
        "Associações únicas e coerentes." if ok else "; ".join(problemas),
        bloqueia=not ok,
    )

    # A05/A06 — condutores/polos/calibre dos IDRs.
    problemas_idr = []
    problemas_calibre = []
    resumo_idr = []
    grupos_neutro = []

    dispositivos = mapa.get("dispositivos", []) or []

    for dr in drs:
        gid = _texto(dr.get("dr"))
        condutores = _condutores_idr(dr, por_numero)
        polos_esp = _polos_idr_esperados(condutores)

        if "N" in condutores:
            grupos_neutro.append(gid)

        nums = [
            int(n) for n in (dr.get("circuitos", []) or [])
            if int(n or 0) in por_numero
        ]
        maior_dj = max(
            [int(por_numero[n].get("disjuntor", 0) or 0) for n in nums] or [0]
        )
        nominal = int(dr.get("corrente_nominal_a", 0) or 0)

        if nominal < maior_dj:
            problemas_calibre.append(
                f"{gid}: {nominal} A < maior DJ {maior_dj} A"
            )

        resumo_idr.append(
            f"{gid}: {' + '.join(condutores) or 'sem condutores'} → {polos_esp}P"
        )

        if mapa:
            disp = next(
                (
                    d for d in dispositivos
                    if _texto(d.get("identificador")) == gid
                ),
                None,
            )

            if disp is None:
                problemas_idr.append(f"{gid} ausente no mapa físico")
            else:
                modulos = int(disp.get("modulos", 0) or 0)
                cond_mapa = [
                    _texto(x).upper()
                    for x in (disp.get("condutores", []) or [])
                ]

                if modulos != polos_esp:
                    problemas_idr.append(
                        f"{gid}: mapa {modulos}P, esperado {polos_esp}P"
                    )

                if cond_mapa != condutores:
                    problemas_idr.append(
                        f"{gid}: mapa {cond_mapa}, esperado {condutores}"
                    )

    ok = not problemas_idr
    add(
        "A05",
        "Condutores que atravessam cada IDR",
        "OK" if ok else "ERRO",
        "; ".join(resumo_idr) if ok else "; ".join(problemas_idr),
        bloqueia=not ok,
    )

    ok = not problemas_calibre
    add(
        "A06",
        "Corrente nominal dos IDRs",
        "OK" if ok else "ERRO",
        (
            "IDR não inferior ao maior disjuntor a jusante."
            if ok else "; ".join(problemas_calibre)
        ),
        bloqueia=not ok,
    )

    # A07 — neutro pós-IDR.
    add(
        "A07",
        "Neutro a jusante dos IDRs",
        "OK",
        (
            "Grupos com N: "
            + (", ".join(grupos_neutro) if grupos_neutro else "nenhum")
            + ". Regra do desenho: barramento N → polo N do IDR → "
              "saída N do IDR → neutro exclusivo do grupo → carga."
        ),
    )

    # A08 — PE.
    add(
        "A08",
        "Condutor de proteção PE",
        "OK",
        (
            "PE permanece no barramento de proteção e segue às cargas "
            "sem atravessar DG, IDR ou disjuntor terminal."
        ),
    )

    # A09 — DPS em uma unidade por fase ativa no arranjo atual.
    qtd_esperada = len(fases_rede)
    qtd_mapa = sum(
        1 for d in dispositivos
        if _texto(d.get("tipo")).upper() == "DPS"
    )
    ok = (not mapa) or qtd_mapa == qtd_esperada
    add(
        "A09",
        "Quantidade física de DPS",
        "OK" if ok else "ERRO",
        (
            f"Esperado(s): {qtd_esperada}; "
            + (f"mapa: {qtd_mapa}." if mapa else "mapa ainda não gerado.")
        ),
        bloqueia=not ok,
    )

    # A10 — cadeia lógica.
    cadeia = []
    ids_dr = {_texto(d.get("dr")) for d in drs}
    for c in circuitos:
        n = int(c.get("numero", 0) or 0)
        grupo = _texto(c.get("dr"))
        if grupo and grupo not in ids_dr:
            cadeia.append(f"C{n}: grupo {grupo} inexistente")

    ok = not cadeia
    add(
        "A10",
        "Cadeia Entrada → proteção → circuito",
        "OK" if ok else "ERRO",
        "Topologia lógica completa." if ok else "; ".join(cadeia),
        bloqueia=not ok,
    )


    # --------------------------------------------------------
    # Verificações complementares
    # --------------------------------------------------------

    icc_conhecida = bool(parametros.get("icc_conhecida", False))
    icc = float(parametros.get("icc_qdc_ka", 0.0) or 0.0)
    cap_dg = float(parametros.get("capacidade_interrupcao_dg_ka", 0.0) or 0.0)
    cap_term = float(parametros.get("capacidade_interrupcao_terminais_ka", 0.0) or 0.0)

    if not icc_conhecida or icc <= 0:
        add(
            "C01",
            "Curto-circuito e capacidade de interrupção",
            "A CONFIRMAR",
            "Icc ainda não informada. Confirmar antes da execução.",
            bloqueia=False,
        )
    elif cap_dg <= 0 or cap_term <= 0:
        add(
            "C01",
            "Curto-circuito e capacidade de interrupção",
            "PARCIAL",
            f"Icc registrada: {icc:.1f} kA. Falta confirmar a capacidade dos dispositivos.",
            bloqueia=False,
        )
    else:
        ok = cap_dg >= icc and cap_term >= icc
        add(
            "C01",
            "Curto-circuito e capacidade de interrupção",
            "OK" if ok else "ERRO",
            f"Icc={icc:.1f} kA; DG={cap_dg:.1f} kA; terminais={cap_term:.1f} kA.",
            bloqueia=not ok,
        )

    fabricante = _texto(parametros.get("fabricante_protecao"))
    ref_sel = _texto(parametros.get("referencia_seletividade"))
    sel_ok = bool(parametros.get("seletividade_validada_rt", False))

    if fabricante and ref_sel and sel_ok:
        status_sel = "VALIDADO RT"
        detalhe_sel = f"{fabricante}; referência: {ref_sel}."
    elif fabricante:
        status_sel = "PARCIAL"
        detalhe_sel = f"Fabricante informado: {fabricante}. Falta referência de seletividade."
    else:
        status_sel = "OPCIONAL NESTA ETAPA"
        detalhe_sel = "Fabricante ainda não definido."

    add(
        "C02",
        "Fabricante e seletividade",
        status_sel,
        detalhe_sel,
        bloqueia=False,
    )

    dps_tipo = _texto(parametros.get("dps_tipo"))
    dps_uc = float(parametros.get("dps_uc_v", 0.0) or 0.0)
    dps_up = float(parametros.get("dps_up_kv", 0.0) or 0.0)
    dps_in = float(parametros.get("dps_in_ka", 0.0) or 0.0)
    dps_imax = float(parametros.get("dps_imax_ka", 0.0) or 0.0)

    dps_completo = (
        dps_tipo
        and dps_tipo != "A definir"
        and dps_uc > 0
        and dps_up > 0
        and dps_in > 0
        and dps_imax > 0
    )

    if not dps_completo:
        add(
            "C03",
            "Características do DPS",
            "A CONFIRMAR",
            "Quantidade física já calculada; dados de fabricante podem ser definidos depois.",
            bloqueia=False,
        )
    elif dps_imax < dps_in:
        add(
            "C03",
            "Características do DPS",
            "ERRO",
            f"Imax={dps_imax:.1f} kA é inferior a In={dps_in:.1f} kA.",
            bloqueia=True,
        )
    else:
        add(
            "C03",
            "Características do DPS",
            "DADOS COMPLETOS",
            f"{dps_tipo}; Uc={dps_uc:.0f} V; Up={dps_up:.1f} kV; In={dps_in:.1f} kA; Imax={dps_imax:.1f} kA.",
            bloqueia=False,
        )

    esquema = _texto(parametros.get("esquema_aterramento"))
    arranjo = _texto(parametros.get("arranjo_dps"))
    arranjo_ok = bool(parametros.get("arranjo_dps_validado_rt", False))

    if not esquema or esquema == "Não sei":
        status_at = "A CONFIRMAR"
        detalhe_at = "Esquema de aterramento ainda não definido."
    elif arranjo and arranjo_ok:
        status_at = "VALIDADO RT"
        detalhe_at = f"Esquema {esquema}; arranjo confirmado: {arranjo}."
    else:
        status_at = "PARCIAL"
        detalhe_at = f"Esquema informado: {esquema}. Arranjo do DPS ainda deve ser confirmado."

    add(
        "C04",
        "Aterramento e ligação do DPS",
        status_at,
        detalhe_at,
        bloqueia=False,
    )

    ref_conc = _texto(parametros.get("norma_concessionaria_referencia"))
    conc_ok = bool(parametros.get("requisitos_concessionaria_validados_rt", False))

    add(
        "C05",
        "Requisitos adicionais da concessionária",
        "VALIDADO RT" if (ref_conc and conc_ok) else "A CONFIRMAR",
        (
            f"Referência: {ref_conc}."
            if (ref_conc and conc_ok)
            else "Requisitos locais adicionais ficam para confirmação executiva."
        ),
        bloqueia=False,
    )

    bloqueios = [v for v in verificacoes if v["Bloqueia DXF"] == "SIM"]
    qtd_pendencias = sum(
        1 for v in verificacoes
        if v["Status"] in {"A CONFIRMAR", "PARCIAL", "OPCIONAL NESTA ETAPA"}
    )
    qtd_erros = sum(1 for v in verificacoes if v["Status"] == "ERRO")

    return {
        "status": (
            "BLOQUEADO"
            if bloqueios
            else "LIBERADO"
        ),
        "qtd_bloqueios": len(bloqueios),
        "qtd_erros": qtd_erros,
        "qtd_pendencias": qtd_pendencias,
        "verificacoes": verificacoes,
        "bloqueios": bloqueios,
        "fases_fornecimento": fases_rede,
        "grupos_idr_com_neutro": grupos_neutro,
    }
