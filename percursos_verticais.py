"""Alturas de projeto e quantitativo vertical, sem modificar entidades CAD."""
from collections import Counter
import math

CHAVE = "alturas_instalacao"
PADROES = {"baixa_m": 0.30, "media_m": 1.20, "alta_m": 2.20,
           "interruptor_m": 1.20, "qdc_m": None, "percurso": "Teto", "confirmado": False}


def validar(registro, pe_direito):
    r = {**PADROES, **(registro or {})}
    if not r.get("confirmado"):
        return False
    if r["percurso"] not in ("Teto", "Piso"):
        return False
    try:
        return all(math.isfinite(float(r[k])) and 0 <= float(r[k]) <= float(pe_direito)
                   for k in ("baixa_m", "media_m", "alta_m", "interruptor_m", "qdc_m"))
    except (ValueError, TypeError):
        return False


def renderizar(salvo, pe_direito, chave, salvar):
    import streamlit as st
    r = {**PADROES, **(salvo or {})}
    with st.expander("Alturas e percurso da instalação"):
        st.caption("Alturas em relação ao piso acabado. Os valores sugeridos são convenções "
                   "de projeto, editáveis conforme acessibilidade, bancadas e equipamentos.")
        with st.form(chave("form_alturas")):
            r["percurso"] = st.selectbox("Distribuição horizontal", ["Teto", "Piso"],
                index=0 if r["percurso"] == "Teto" else 1, key=chave("alturas_percurso"))
            campos = [("baixa_m", "Tomada baixa (m)"), ("media_m", "Tomada média (m)"),
                      ("alta_m", "Tomada alta (m)"), ("interruptor_m", "Interruptor (m)"),
                      ("qdc_m", "Entrada dos eletrodutos no QDC (m)")]
            for campo, titulo in campos:
                r[campo] = st.number_input(titulo, min_value=0.0, step=0.05,
                    value=None if r[campo] is None else float(r[campo]), format="%.2f",
                    key=chave("alturas_" + campo))
            st.caption(f"Iluminação no teto: pé-direito cadastrado de {pe_direito:.2f} m. "
                       "QDC: informe a entrada dos eletrodutos, e não o centro do quadro.")
            r["confirmado"] = st.checkbox("Confirmo as alturas e o percurso previstos no projeto",
                value=bool(r["confirmado"]), key=chave("alturas_confirmado"))
            if st.form_submit_button("Salvar alturas e percurso"):
                if r["confirmado"] and not validar(r, pe_direito):
                    st.error("Informe todas as alturas entre zero e o pé-direito do projeto.")
                else:
                    try:
                        salvar(r)
                    except Exception as exc:
                        st.error(f"Não foi possível salvar as alturas do projeto: {exc}")
                    else:
                        st.success("Alturas e percurso salvos.")
                        st.rerun()
        if not validar(salvo, pe_direito):
            st.info("Quantitativo preliminar: percursos verticais aguardam confirmação das alturas e do percurso.")


def aplicar(resumo, registro, pe_direito, pontos, interruptores, qdc, circuitos):
    """Cada conexão vertical entra uma vez; condutores compartilhados usam união com multiplicidade."""
    import dimensionamento_rotas as dr
    if resumo.get("auditoria_vertical", {}).get("aplicado"):
        return resumo
    resumo["auditoria_vertical"] = {"aplicado": False, "status": "Alturas e percurso pendentes"}
    if not validar(registro, pe_direito):
        return resumo
    r = {**PADROES, **registro}
    nivel = float(pe_direito) if r["percurso"] == "Teto" else 0.0
    def coord(p):
        return tuple(round(float(v), 4) for v in p[:2])
    nos, aliases = {}, {}
    for ponto in list(pontos or []) + list(interruptores or []):
        xy = ponto.get("ponto")
        if not xy:
            continue
        tipo = str(ponto.get("tipo", "")).upper()
        if tipo in ("ILUMINACAO", "ILUMINAÇÃO"):
            altura = float(pe_direito)
        elif tipo == "INTERRUPTOR":
            altura = r["interruptor_m"]
        else:
            altura = r.get({"BAIXA": "baixa_m", "MEDIA": "media_m", "ALTA": "alta_m"}.get(
                ponto.get("altura"), ""))
        if altura is None:
            continue
        ident = (coord(xy), float(altura))
        nos[ident] = {"ponto": coord(xy), "altura_m": float(altura), "tipo": tipo, "condutores": Counter()}
        for campo in ("ponto", "ponto_conexao_parede", "ponto_conexao_ambiente", "ponto_tangencia",
                      "ponto_tangencia_simbolo"):
            if ponto.get(campo):
                aliases[coord(ponto[campo])] = ident
    qxy = (qdc or {}).get("centro_externo") or (qdc or {}).get("centro")
    if qxy:
        ident = (coord(qxy), float(r["qdc_m"]))
        nos[ident] = {"ponto": coord(qxy), "altura_m": float(r["qdc_m"]), "tipo": "QDC", "condutores": Counter()}
        aliases[coord(qxy)] = ident
    por_numero = {int(c["numero"]): c for c in circuitos if c.get("numero")}
    for rota in resumo.get("rotas", []):
        itens = []
        for num in rota.get("circuitos", []):
            if int(num) in por_numero:
                for c in dr._condutores_circuito_rota(por_numero[int(num)], rota):
                    itens.append((int(num), float(c["bitola_mm2"]), c["funcao"], c["cor"]))
        multiplicidade = Counter(itens)
        for campo in ("inicio", "fim"):
            if rota.get(campo) and coord(rota[campo]) in aliases:
                no = nos[aliases[coord(rota[campo])]]
                no["condutores"] |= multiplicidade
    cabos = {(int(c["circuito"]), float(c["bitola_mm2"]), c["funcao"], c["cor"]):
             float(c["comprimento_rota_m"]) for c in resumo.get("cabos", [])}
    tubos = {int(t["diametro_mm"]): float(t["comprimento_rota_m"]) for t in resumo.get("eletrodutos", [])}
    verticais = []
    for no in nos.values():
        comprimento = abs(nivel - no["altura_m"])
        if comprimento < 0.0001 or not no["condutores"]:
            continue
        condutores = []
        for k, qtd in no["condutores"].items():
            cabos[k] = cabos.get(k, 0.0) + comprimento * qtd
            condutores.extend([{"bitola_mm2": k[1]}] * qtd)
        diametro = dr._eletroduto_por_ocupacao(condutores).get("diametro_nominal_mm")
        if diametro:
            tubos[int(diametro)] = tubos.get(int(diametro), 0.0) + comprimento
        verticais.append({"ponto": no["ponto"], "tipo": no["tipo"], "altura_m": no["altura_m"],
                          "comprimento_m": round(comprimento, 4), "diametro_mm": diametro,
                          "condutores": [{"circuito": k[0], "bitola_mm2": k[1], "funcao": k[2],
                                          "cor": k[3], "quantidade": qtd}
                                         for k, qtd in sorted(no["condutores"].items())]})
    resumo["cabos"] = [{"circuito": k[0], "bitola_mm2": k[1], "funcao": k[2], "cor": k[3],
                        "comprimento_rota_m": round(v, 2),
                        "comprimento_com_folga_m": round(v * dr.FOLGA_CABOS_ROTA, 2)}
                       for k, v in sorted(cabos.items())]
    resumo["eletrodutos"] = [{"diametro_mm": k, "comprimento_rota_m": round(v, 2),
                             "comprimento_com_folga_m": round(v * dr.FOLGA_ELETRODUTO_ROTA, 2)}
                            for k, v in sorted(tubos.items())]
    resumo["auditoria_vertical"] = {"aplicado": True, "status": "Percursos verticais incluídos no quantitativo",
        "parametros": dict(r), "pe_direito_m": float(pe_direito), "trechos": verticais,
        "comprimento_total_m": round(sum(v["comprimento_m"] for v in verticais), 4),
        "criterio": "Derivações pelo teto/piso; uma conexão vertical por ponto; "
                    "condutores compartilhados sem duplicação. Não altera verificação elétrica dos circuitos."}
    return resumo


def relatorio_auditoria(projeto, resumo, materiais, circuitos, pe_direito):
    """Snapshot dos dados usados no quantitativo, para conferência externa."""
    from versao import VERSAO_SISTEMA
    return {"formato": "autoeletrica_auditoria_cabos_v1", "versao": VERSAO_SISTEMA,
            "projeto": str(projeto or ""), "pe_direito_m": float(pe_direito),
            "folga_cabos": 1.15, "reserva_eletrodutos": 1.10,
            "arredondamento": "Cabos agrupados por seção, função e cor; quantidade final arredondada para cima em metros.",
            "rotas_horizontais": (resumo or {}).get("rotas", []),
            "auditoria_vertical": (resumo or {}).get("auditoria_vertical", {}),
            "cabos_por_circuito": (resumo or {}).get("cabos", []),
            "eletrodutos": (resumo or {}).get("eletrodutos", []),
            "contexto_queda_vertical": (resumo or {}).get("contexto_queda_vertical", {}),
            "validacao_eletrica": (resumo or {}).get("validacao_eletrica", {}),
            "correcoes_bitola": (resumo or {}).get("correcoes_bitola", []),
            "circuitos": circuitos, "materiais": materiais,
            "escopo": "Conferência de quantitativos. Não constitui validação normativa nem liberação da instalação."}


def contexto_queda(registro, pe_direito, pontos, interruptores, qdc):
    """Alturas nos pontos de conexão; percurso horizontal fica no teto/piso escolhido."""
    if not validar(registro, pe_direito):
        return {"aplicado": False, "status": "Alturas e percurso pendentes"}
    r = {**PADROES, **registro}
    qxy = (qdc or {}).get("centro_externo") or (qdc or {}).get("centro")
    if not qxy:
        return {"aplicado": False, "status": "Origem do QDC pendente"}
    nivel = float(pe_direito) if r["percurso"] == "Teto" else 0.0
    descidas = {}
    for p in list(pontos or []) + list(interruptores or []):
        tipo = str(p.get("tipo", "")).upper()
        if tipo in ("ILUMINACAO", "ILUMINAÇÃO"):
            altura = float(pe_direito)
        elif tipo == "INTERRUPTOR":
            altura = r["interruptor_m"]
        else:
            altura = r.get({"BAIXA": "baixa_m", "MEDIA": "media_m", "ALTA": "alta_m"}.get(p.get("altura"), ""))
        if altura is None:
            continue
        for campo in ("ponto", "ponto_conexao_parede", "ponto_conexao_ambiente",
                      "ponto_tangencia", "ponto_tangencia_simbolo"):
            if p.get(campo):
                xy = tuple(round(float(v), 4) for v in p[campo][:2])
                descidas[xy] = abs(nivel - float(altura))
    return {"aplicado": True, "qdc": list(qxy[:2]),
            "subida_qdc_m": abs(nivel - float(r["qdc_m"])),
            "conexoes": [{"ponto": list(k), "vertical_m": v} for k, v in sorted(descidas.items())],
            "criterio": "Percurso horizontal acumulado desde o QDC mais subida/descida do QDC "
                        "e conexão vertical do ponto atendido; ramificações independentes não são somadas. "
                        "A folga de compra de cabos não entra na queda de tensão."}
