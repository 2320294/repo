
def _potencia(circuito):
    try:
        return max(0.0, float(circuito.get("potencia", 0) or 0))
    except Exception:
        return 0.0

def _fases(tipo):
    if tipo == "Monofásico":
        return ["A"]
    if tipo == "Bifásico":
        return ["A", "B"]
    if tipo == "Trifásico":
        return ["A", "B", "C"]
    return []

def balancear_circuitos(circuitos, parametros_rede):
    circuitos = [dict(c) for c in (circuitos or [])]
    tipo_fornecimento = str((parametros_rede or {}).get("tipo_fornecimento", ""))
    fases = _fases(tipo_fornecimento)

    if not fases:
        saida = []
        for i, c in enumerate(circuitos, start=1):
            c["numero"] = i
            c["fase"] = "A definir"
            c["polos"] = "A definir"
            saida.append(c)
        return saida, {
            "status": "fornecimento_incompleto",
            "fases": {},
            "diferenca_max_w": None,
            "desequilibrio_pct": None,
        }

    cargas = {f: 0.0 for f in fases}
    atribuicoes = {}

    # Maior carga primeiro melhora o resultado do balanceamento guloso.
    ordenados = sorted(
        enumerate(circuitos),
        key=lambda item: (-_potencia(item[1]), item[0])
    )

    for idx_original, c in ordenados:
        p = _potencia(c)
        tipo = str(c.get("tipo", "")).upper()

        if tipo == "TUE" and len(fases) >= 2:
            if len(fases) == 2:
                par = ("A", "B")
            else:
                pares = [("A","B"), ("B","C"), ("C","A")]
                par = min(
                    pares,
                    key=lambda pr: (
                        cargas[pr[0]] + cargas[pr[1]],
                        max(cargas[pr[0]], cargas[pr[1]]),
                        pr
                    )
                )
            cargas[par[0]] += p / 2.0
            cargas[par[1]] += p / 2.0
            atribuicoes[idx_original] = {
                "fase": f"{par[0]}-{par[1]}",
                "polos": "2P",
            }
        else:
            fase = min(cargas, key=lambda f: (cargas[f], f))
            cargas[fase] += p
            atribuicoes[idx_original] = {
                "fase": fase,
                "polos": "1P",
            }

    saida = []
    for i, c in enumerate(circuitos, start=1):
        c["numero"] = i
        c.update(atribuicoes.get(i-1, {"fase":"A definir","polos":"A definir"}))
        saida.append(c)

    vals = list(cargas.values())
    media = sum(vals) / len(vals) if vals else 0.0
    diferenca = max(vals) - min(vals) if vals else 0.0
    desequilibrio = (diferenca / media * 100.0) if media > 0 else 0.0

    return saida, {
        "status": "ok",
        "fases": cargas,
        "diferenca_max_w": diferenca,
        "desequilibrio_pct": desequilibrio,
    }
