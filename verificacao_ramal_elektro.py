"""Conferência aritmética isolada; parâmetros documentados pelo responsável."""
import math


def verificar_ramal(auditoria, componentes, dados):
    resultado = {"status": "pendente", "aprovado": False, "criterios": [], "pendencias": []}
    def pendencia(texto):
        resultado["pendencias"].append(texto)
    def positivo(chave):
        valor = dados.get(chave)
        if isinstance(valor, bool):
            return None
        try:
            valor = float(valor)
            return valor if math.isfinite(valor) and valor > 0 else None
        except (TypeError, ValueError):
            return None
    candidato = auditoria.get("candidato") or {}
    cabo = componentes.get("selecoes", {}).get("Ramal de distribuição")
    if auditoria.get("status") != "candidato" or not cabo:
        pendencia("Selecione um enquadramento candidato e a isolação do ramal de distribuição.")
        return resultado
    resultado["cabo"] = cabo
    if dados.get("sem_dados") is True:
        pendencia("Dados do ramal não disponíveis. A prévia de demanda pode continuar; capacidade e queda de tensão aguardam conferência técnica.")
        dados = {}
    ib, iz, comprimento, coef, tensao, limite = [positivo(k) for k in
        ("corrente_a", "iz_corrigida_a", "comprimento_m", "coeficiente_mv_am", "tensao_v", "limite_percentual")]
    metodo_ok = bool(str(dados.get("metodo") or "").strip())
    fonte_ok = bool(str(dados.get("fonte") or "").strip())
    if not metodo_ok:
        pendencia("Falta informar o método de instalação e as condições reais do ramal.")
    if not fonte_ok:
        pendencia("Falta informar a fonte técnica: fabricante, documento, revisão e tabela/página.")
    for valor, mensagem in [
        (ib, "Falta informar a corrente de projeto do trecho crítico (A)."),
        (iz, "Falta informar a capacidade de condução corrigida — Iz (A)."),
        (comprimento, "Falta informar o comprimento de ida do ramal (m)."),
        (coef, "Falta informar o coeficiente de queda aplicável ao circuito (mV/A/m)."),
        (tensao, "Falta informar a tensão de referência do trecho (V)."),
        (limite, "Falta informar o limite de queda disponível para este trecho (%).")]:
        if valor is None:
            pendencia(mensagem)
    if dados.get("confirmado") is not True:
        pendencia("A aplicabilidade dos dados ao cabo, circuito e condições reais ainda não foi confirmada.")
    if not metodo_ok or not fonte_ok or dados.get("confirmado") is not True:
        return resultado
    nominal = candidato.get("disjuntor_tabela_a")
    if ib and iz:
        atende = ib <= nominal <= iz
        resultado["criterios"].append({"Critério": "Corrente de projeto e capacidade corrigida", "Resultado": "Atende ao critério informado" if atende else "Não atende", "Cálculo": f"Ib={ib:g} A; In={nominal:g} A; Iz corrigida={iz:g} A; verificar Ib ≤ In ≤ Iz"})
    if ib and comprimento and coef and tensao and limite:
        queda = coef * ib * comprimento / 1000
        percentual = 100 * queda / tensao
        if math.isfinite(percentual) and math.isfinite(queda):
            resultado["criterios"].append({"Critério": "Queda de tensão no trecho", "Resultado": "Atende ao critério informado" if percentual <= limite else "Não atende", "Cálculo": f"ΔV={queda:.3f} V ({percentual:.3f}%); limite informado={limite:g}%; ΔV=k×Ib×L/1000"})
        else:
            pendencia("Valores fora da faixa calculável para queda de tensão.")
    if any(c["Resultado"] == "Não atende" for c in resultado["criterios"]):
        resultado["status"] = "nao_atende"
    elif len(resultado["criterios"]) == 2 and not resultado["pendencias"]:
        resultado["status"] = "criterios_informados_atendidos"
    return resultado
