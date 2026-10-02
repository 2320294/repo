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
    if not str(dados.get("metodo") or "").strip() or not str(dados.get("fonte") or "").strip() or dados.get("confirmado") is not True:
        pendencia("Informe método de instalação e fonte técnica; confirme sua aplicabilidade ao cabo, circuito e condições reais.")
        return resultado
    ib, iz, comprimento, coef, tensao, limite = [positivo(k) for k in
        ("corrente_a", "iz_corrigida_a", "comprimento_m", "coeficiente_mv_am", "tensao_v", "limite_percentual")]
    nominal = candidato.get("disjuntor_tabela_a")
    if not ib:
        pendencia("Informe a corrente de projeto do trecho crítico, com desequilíbrio considerado quando aplicável.")
    if ib and iz:
        atende = ib <= nominal <= iz
        resultado["criterios"].append({"Critério": "Corrente de projeto e capacidade corrigida", "Resultado": "Atende ao critério informado" if atende else "Não atende", "Cálculo": f"Ib={ib:g} A; In={nominal:g} A; Iz corrigida={iz:g} A; verificar Ib ≤ In ≤ Iz"})
    elif not iz:
        pendencia("Informe a capacidade de condução já corrigida para temperatura, agrupamento e demais condições aplicáveis.")
    if ib and comprimento and coef and tensao and limite:
        queda = coef * ib * comprimento / 1000
        percentual = 100 * queda / tensao
        if math.isfinite(percentual) and math.isfinite(queda):
            resultado["criterios"].append({"Critério": "Queda de tensão no trecho", "Resultado": "Atende ao critério informado" if percentual <= limite else "Não atende", "Cálculo": f"ΔV={queda:.3f} V ({percentual:.3f}%); limite informado={limite:g}%; ΔV=k×Ib×L/1000"})
        else:
            pendencia("Valores fora da faixa calculável para queda de tensão.")
    else:
        pendencia("Para a queda de tensão, informe comprimento de ida, coeficiente aplicável, tensão de referência e limite disponível para este trecho.")
    if any(c["Resultado"] == "Não atende" for c in resultado["criterios"]):
        resultado["status"] = "nao_atende"
    elif len(resultado["criterios"]) == 2 and not resultado["pendencias"]:
        resultado["status"] = "criterios_informados_atendidos"
    return resultado
