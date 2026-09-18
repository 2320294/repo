import math

from perfis_normativos import perfil_por_id

DISJUNTORES_PADRAO = [10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125]


def _float(valor, padrao=0.0):
    try:
        return float(valor)
    except Exception:
        return float(padrao)


def potencia_instalada(tabela_editada):
    total_ilum = 0.0
    total_tug = 0.0
    total_tue = 0.0
    for row in tabela_editada or []:
        qi = int(_float(row.get("Qtd Ilum.", 0)))
        qt = int(_float(row.get("Qtd TUG", row.get("TUGs (Qtd)", 0))))
        qe = int(_float(row.get("Qtd TUE", 0)))
        pi = _float(row.get("Pot. Unit. Ilum (W)", row.get("Pot. Unit. Ilum (VA)", 0)))
        pt = _float(row.get("Pot. Unit. TUG (W)", row.get("Pot. Unit. TUG (VA)", 0)))
        pe = _float(row.get("Pot. Unit. TUE (W)", row.get("Pot. Unit. TUE (VA)", 0)))
        total_ilum += qi * pi
        total_tug += qt * pt
        total_tue += qe * pe
    return {
        "iluminacao_w": total_ilum,
        "tug_w": total_tug,
        "tue_w": total_tue,
        "total_w": total_ilum + total_tug + total_tue,
    }


def corrente_demanda_equivalente(potencia_demanda_w, tipo_fornecimento, tensao_fornecimento):
    p = max(0.0, _float(potencia_demanda_w))
    tipo = str(tipo_fornecimento or "")
    tensao = str(tensao_fornecimento or "")
    if p <= 0:
        return 0.0
    if tipo == "Monofásico":
        v = 127.0 if tensao == "127 V" else 220.0 if tensao == "220 V" else None
        return None if not v else p / v
    if tipo == "Bifásico":
        if tensao == "127/220 V":
            return p / (2.0 * 127.0)
        if tensao == "220 V":
            return p / 220.0
        return None
    if tipo == "Trifásico":
        vlinha = 220.0 if tensao == "127/220 V" else 380.0 if tensao == "220/380 V" else None
        return None if not vlinha else p / (math.sqrt(3.0) * vlinha)
    return None


def proximo_disjuntor(corrente_a):
    if corrente_a is None:
        return None
    corrente = max(0.0, _float(corrente_a))
    for valor in DISJUNTORES_PADRAO:
        if valor >= corrente:
            return valor
    return None


def _fator_faixa_kw(regra, carga_kw):
    for faixa in regra.get("faixas", []) or []:
        minimo = _float(faixa.get("min_kw"), 0)
        maximo = faixa.get("max_kw")
        # Mantém a convenção da tabela persistida: limite inferior inclusive
        # e superior exclusivo; acima da última faixa usa max_kw=None.
        if carga_kw >= minimo and (maximo in (None, "") or carga_kw < _float(maximo)):
            return _float(faixa.get("fator"), 0)
    return None


def _fator_quantidade(regra, quantidade):
    q = int(max(0, quantidade))
    if q <= 0:
        return 0.0
    for item in regra.get("fatores_por_quantidade", []) or []:
        if int(_float(item.get("quantidade"), -1)) == q:
            return _float(item.get("fator"), 0)
    for item in regra.get("faixas_quantidade", []) or []:
        mn = int(_float(item.get("min"), 0))
        mx = item.get("max")
        if q >= mn and (mx in (None, "") or q <= int(_float(mx))):
            return _float(item.get("fator"), 0)
    for chave, limite in (("acima_de_25", 25), ("acima_de_3", 3)):
        if q > limite and isinstance(regra.get(chave), dict):
            return _float(regra[chave].get("fator"), 0)
    return None


def _nome_tue(row):
    return str(
        row.get("Equipamento TUE")
        or row.get("Equipamento")
        or row.get("TUE")
        or ""
    ).strip()


def _calcular_automatico(tabela_editada, rede, perfil):
    pot = potencia_instalada(tabela_editada)
    regras = (perfil or {}).get("regras") or {}
    demanda_cfg = regras.get("demanda") or {}
    detalhes = []
    pendencias = []
    demanda_total = 0.0

    # Iluminação + TUG: Tabela/faixa cadastrada no perfil ATIVO.
    carga_it_w = pot["iluminacao_w"] + pot["tug_w"]
    regra_it = demanda_cfg.get("iluminacao_tug") or {}
    fator_it = _fator_faixa_kw(regra_it, carga_it_w / 1000.0)
    if carga_it_w > 0 and fator_it is None:
        pendencias.append("Iluminação + TUG sem faixa normativa aplicável.")
    else:
        demanda_it = carga_it_w * (fator_it if fator_it is not None else 0.0)
        demanda_total += demanda_it
        detalhes.append({
            "categoria": "Iluminação + TUG",
            "carga_instalada_w": carga_it_w,
            "quantidade": None,
            "fator": fator_it,
            "demanda_w": demanda_it,
            "tabela_id": regra_it.get("tabela_id", ""),
        })

    # Agrupa as TUEs reconhecidas pelas categorias existentes no perfil.
    grupos = {
        "chuveiros": {"qtd": 0, "w": 0.0, "nomes": []},
        "boiler": {"qtd": 0, "w": 0.0, "nomes": []},
        "eletrodomesticos": {"qtd": 0, "w": 0.0, "nomes": []},
        "fogoes": {"qtd": 0, "w": 0.0, "nomes": []},
        "ar_condicionado": {"qtd": 0, "w": 0.0, "nomes": []},
        "hidromassagem": {"qtd": 0, "w": 0.0, "nomes": []},
    }
    nao_classificados = []

    for row in tabela_editada or []:
        qtd = int(_float(row.get("Qtd TUE", 0)))
        if qtd <= 0:
            continue
        unit = _float(row.get("Pot. Unit. TUE (W)", row.get("Pot. Unit. TUE (VA)", 0)))
        nome = _nome_tue(row)
        n = nome.casefold()
        categoria = None
        if any(x in n for x in ("chuve", "torneira elétrica", "torneira eletrica", "aquecedor de passagem", "ferro elétrico", "ferro eletrico")):
            categoria = "chuveiros"
        elif any(x in n for x in ("boiler", "aquecedor central", "acumulação", "acumulacao")):
            categoria = "boiler"
        elif any(x in n for x in ("lava e seca", "lava-e-seca", "lavaseca")):
            # Equipamento combinado de roupas: enquadrado no grupo da Tabela 6
            # pela função de SECAGEM. A memória de cálculo identifica o critério
            # para não afirmar que "lava e seca" é denominação literal do GED-13.
            categoria = "eletrodomesticos"
        elif any(x in n for x in ("micro", "forno", "lava-louça", "lava louça", "lava-louca", "lava louca", "secadora")):
            categoria = "eletrodomesticos"
        elif any(x in n for x in ("fogão", "fogao", "cooktop")):
            categoria = "fogoes"
        elif any(x in n for x in ("ar-condicionado", "ar condicionado", "split")):
            categoria = "ar_condicionado"
        elif any(x in n for x in ("hidromassagem", "banheira elétrica", "banheira eletrica")):
            categoria = "hidromassagem"

        if categoria:
            grupos[categoria]["qtd"] += qtd
            grupos[categoria]["w"] += qtd * unit
            grupos[categoria]["nomes"].append(nome)
        else:
            nao_classificados.append((nome or "TUE sem identificação", qtd, qtd * unit))

    rotulos = {
        "chuveiros": "Chuveiros / aquecimento elétrico",
        "boiler": "Boiler / aquecedor central",
        "eletrodomesticos": "Secadora / forno / lava-louças / micro-ondas",
        "fogoes": "Fogões / cooktops",
        "ar_condicionado": "Ar-condicionado",
        "hidromassagem": "Hidromassagem / banheira elétrica",
    }

    for chave, grupo in grupos.items():
        if grupo["qtd"] <= 0:
            continue
        regra = demanda_cfg.get(chave) or {}
        fator = None
        if chave == "ar_condicionado":
            fator = regra.get("uso_residencial_fator_demanda")
            if fator is not None:
                fator = _float(fator)
        elif chave == "hidromassagem" and regra.get("usar_regra_motores_tabela_10"):
            # Uma hidromassagem residencial isolada é o primeiro motor do grupo.
            motor = demanda_cfg.get("motores") or {}
            fator = _float((motor.get("fatores_ordem") or {}).get("primeiro"), 1.0)
        else:
            fator = _fator_quantidade(regra, grupo["qtd"])

        if fator is None:
            pendencias.append(f"{rotulos[chave]} sem regra aplicável no perfil.")
            continue
        dem = grupo["w"] * fator
        demanda_total += dem
        tabela_id = regra.get("tabela_id", "")
        categoria_rotulo = rotulos[chave]
        if chave == "eletrodomesticos" and any(
            any(t in (nome or "").casefold() for t in ("lava e seca", "lava-e-seca", "lavaseca"))
            for nome in grupo.get("nomes", [])
        ):
            categoria_rotulo = "Secadora / lava e seca (função secagem) / forno / lava-louças / micro-ondas"
            tabela_id = "GED13_TABELA_6_CRITERIO_FUNCAO_SECAGEM"
        detalhes.append({
            "categoria": categoria_rotulo,
            "carga_instalada_w": grupo["w"],
            "quantidade": grupo["qtd"],
            "fator": fator,
            "demanda_w": dem,
            "tabela_id": tabela_id,
        })

    # TUEs sem fator específico no GED-13 não são encaixadas artificialmente
    # em outra tabela. Para não subdimensionar a instalação, entram na soma
    # com 100% da potência instalada como CRITÉRIO TÉCNICO CONSERVADOR do
    # AutoElétrica. Isto NÃO é apresentado como fator normativo da CPFL.
    criterio_tecnico = []
    if nao_classificados:
        for nome, qtd, carga in nao_classificados:
            demanda_total += carga
            criterio_tecnico.append(
                f"{nome} ({qtd} un.; {carga/1000:.2f} kW): 100% da carga instalada"
            )
            detalhes.append({
                "categoria": f"TUE sem fator específico — {nome}",
                "carga_instalada_w": carga,
                "quantidade": qtd,
                "fator": 1.0,
                "demanda_w": carga,
                "tabela_id": "CRITERIO_TECNICO_CONSERVADOR_100%",
            })

    if pendencias:
        return {
            **pot,
            "status": "cargas_sem_regra",
            "metodo": rede.get("metodo_demanda", ""),
            "fator_demanda_pct": None,
            "potencia_demanda_w": None,
            "potencia_demanda_parcial_w": demanda_total,
            "corrente_demanda_a": None,
            "disjuntor_geral_a": None,
            "tipo_fornecimento": rede.get("tipo_fornecimento", "A definir"),
            "tensao_fornecimento": rede.get("tensao_fornecimento", "A definir"),
            "perfil_normativo_id": perfil.get("id"),
            "perfil_normativo": f"{perfil.get('concessionaria','')} — {perfil.get('documento','')} {perfil.get('revisao','')}".strip(),
            "detalhes_demanda": detalhes,
            "pendencias": pendencias,
            "observacao": "Demanda total não fechada: existem cargas sem regra normativa automática aplicável."
        }

    corrente = corrente_demanda_equivalente(
        demanda_total,
        rede.get("tipo_fornecimento"),
        rede.get("tensao_fornecimento"),
    )
    dg = proximo_disjuntor(corrente)
    status_base = "ok" if corrente is not None and dg is not None else ("fornecimento_incompleto" if corrente is None else "acima_da_faixa")
    status = "ok_com_criterio_tecnico" if criterio_tecnico and status_base == "ok" else status_base
    fator_global = (demanda_total / pot["total_w"] * 100.0) if pot["total_w"] > 0 else 0.0
    return {
        **pot,
        "status": status,
        "metodo": rede.get("metodo_demanda", ""),
        "fator_demanda_pct": fator_global,
        "potencia_demanda_w": demanda_total,
        "potencia_demanda_parcial_w": demanda_total,
        "corrente_demanda_a": corrente,
        "disjuntor_geral_a": dg,
        "tipo_fornecimento": rede.get("tipo_fornecimento", "A definir"),
        "tensao_fornecimento": rede.get("tensao_fornecimento", "A definir"),
        "perfil_normativo_id": perfil.get("id"),
        "perfil_normativo": f"{perfil.get('concessionaria','')} — {perfil.get('documento','')} {perfil.get('revisao','')}".strip(),
        "detalhes_demanda": detalhes,
        "pendencias": [],
        "criterio_tecnico_conservador": criterio_tecnico,
        "observacao": (
            "Demanda calculada com as regras persistidas no perfil normativo ATIVO; "
            "TUEs sem fator específico foram consideradas a 100% como critério técnico conservador, "
            "sem atribuir esse fator ao GED-13." if criterio_tecnico else
            "Demanda calculada exclusivamente com as regras persistidas no perfil normativo ATIVO."
        )
    }


def calcular_demanda_qdc(tabela_editada, parametros_rede):
    rede = dict(parametros_rede or {})
    pot = potencia_instalada(tabela_editada)
    metodo = str(rede.get("metodo_demanda", ""))

    if metodo.startswith("Automático"):
        perfil = None
        try:
            perfil = perfil_por_id(rede.get("perfil_normativo_id"))
        except Exception:
            perfil = None
        if not perfil or str(perfil.get("status", "")).upper() != "ATIVO":
            return {
                **pot,
                "status": "aguardando_perfil",
                "metodo": metodo,
                "fator_demanda_pct": None,
                "potencia_demanda_w": None,
                "corrente_demanda_a": None,
                "disjuntor_geral_a": None,
                "tipo_fornecimento": rede.get("tipo_fornecimento", "A definir"),
                "tensao_fornecimento": rede.get("tensao_fornecimento", "A definir"),
                "detalhes_demanda": [],
                "pendencias": [],
                "observacao": "Selecione um perfil normativo ATIVO nos Parâmetros do projeto."
            }
        return _calcular_automatico(tabela_editada, rede, perfil)

    fator = min(100.0, max(0.0, _float(rede.get("fator_demanda_manual", 100.0), 100.0)))
    demanda = pot["total_w"] * fator / 100.0
    corrente = corrente_demanda_equivalente(
        demanda,
        rede.get("tipo_fornecimento"),
        rede.get("tensao_fornecimento"),
    )
    dg = proximo_disjuntor(corrente)
    if corrente is None:
        status = "fornecimento_incompleto"
    elif dg is None:
        status = "acima_da_faixa"
    else:
        status = "ok"
    return {
        **pot,
        "status": status,
        "metodo": metodo,
        "fator_demanda_pct": fator,
        "potencia_demanda_w": demanda,
        "corrente_demanda_a": corrente,
        "disjuntor_geral_a": dg,
        "tipo_fornecimento": rede.get("tipo_fornecimento", "A definir"),
        "tensao_fornecimento": rede.get("tensao_fornecimento", "A definir"),
        "detalhes_demanda": [],
        "pendencias": [],
        "observacao": (
            "Pré-dimensionamento manual: validar perfil da concessionária, alimentador, "
            "capacidade de condução, queda de tensão, curto-circuito e coordenação."
        )
    }
