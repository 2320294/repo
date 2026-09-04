"""
Fase 13.6 — Auditoria elétrica estrutural do QDC.

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

    # Pendências executivas: não são inventadas.
    pendencias = [
        "Icc presumida no QDC e capacidade de interrupção dos disjuntores",
        "curvas/tabelas de seletividade e coordenação do fabricante",
        "classe/tipo e parâmetros Uc, Up, In e Imax dos DPS",
        "esquema de aterramento definitivo (TN/TT/IT) e ligação de DPS correspondente",
        "requisitos adicionais da concessionária para o padrão de entrada local",
    ]

    for i, texto in enumerate(pendencias, start=1):
        add(
            f"P{i:02d}",
            "Validação executiva pendente",
            "PENDENTE",
            texto,
            bloqueia=False,
        )

    bloqueios = [v for v in verificacoes if v["Bloqueia DXF"] == "SIM"]
    qtd_pendencias = sum(1 for v in verificacoes if v["Status"] == "PENDENTE")
    qtd_erros = sum(1 for v in verificacoes if v["Status"] == "ERRO")

    return {
        "status": (
            "BLOQUEADO"
            if bloqueios
            else "APROVADO COM PENDÊNCIAS"
        ),
        "qtd_bloqueios": len(bloqueios),
        "qtd_erros": qtd_erros,
        "qtd_pendencias": qtd_pendencias,
        "verificacoes": verificacoes,
        "bloqueios": bloqueios,
        "fases_fornecimento": fases_rede,
        "grupos_idr_com_neutro": grupos_neutro,
    }
