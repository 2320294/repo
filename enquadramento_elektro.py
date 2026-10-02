"""Auditoria isolada da Tabela 3. Não dimensiona nem publica um perfil."""

import math

from neoenergia_elektro import eh_perfil_elektro, motivo_conferencia

# Limites literais do documento: os espaços entre linhas não são arredondados.
FAIXAS_TRIFASICAS = (
    ("T0", 0.0, 19.0, 50), ("T1", 19.1, 24.0, 63),
    ("T2", 24.1, 38.0, 100), ("T3", 38.1, 47.0, 125),
    ("T4", 47.1, 57.0, 150), ("T5", 57.1, 75.0, 200),
)


def auditar_enquadramento(tabela, perfil, previa, contexto=None):
    """Só informa candidato quando contexto e números foram conferidos.

    As confirmações pertencem à simulação administrativa; não alteram dados
    persistidos, status do perfil, QDC, DG ou alimentador.
    """
    c = contexto or {}
    pendencias = []
    carga_w = 0.0
    if not eh_perfil_elektro(perfil):
        pendencias.append("Perfil diferente da DIS-NOR-030 Rev. 07 da Elektro.")
    if not c.get("municipio_vinculado"):
        pendencias.append("Município não vinculado ao perfil selecionado.")
    if c.get("tensao") != "220/127 V":
        pendencias.append("Confirmar tensão local 220/127 V; outras tensões exigem auditoria própria.")
    if not c.get("atendimento_confirmado"):
        pendencias.append("Confirmar atendimento Elektro e tensão no endereço do projeto.")
    if not c.get("urbano_individual"):
        pendencias.append("Confirmar instalação residencial individual urbana para esta auditoria.")
    if not c.get("cargas_conferidas"):
        pendencias.append("Conferir potências ativas em W, quantidades e dados usados na prévia.")
    if not c.get("equipamentos_conferidos"):
        pendencias.append("Conferir motores, cargas especiais e equipamentos que exigem estudo específico.")
    for i, row in enumerate(tabela or [], 1):
        for qtd_key, w_key, va_key, alias in (
            ("Qtd Ilum.", "Pot. Unit. Ilum (W)", "Pot. Unit. Ilum (VA)", None),
            ("Qtd TUG", "Pot. Unit. TUG (W)", "Pot. Unit. TUG (VA)", "TUGs (Qtd)"),
            ("Qtd TUE", "Pot. Unit. TUE (W)", "Pot. Unit. TUE (VA)", None),
        ):
            try:
                qtd = float(row.get(qtd_key, row.get(alias, 0) if alias else 0))
                if not math.isfinite(qtd) or qtd < 0 or not qtd.is_integer():
                    raise ValueError
                if not qtd:
                    continue
                # Não converter silenciosamente VA em W para enquadrar a entrada.
                if w_key not in row:
                    pendencias.append(f"Linha {i}: informar potência ativa em W; {va_key} não substitui W.")
                    continue
                watts = float(row[w_key])
                if not math.isfinite(watts) or watts <= 0:
                    raise ValueError
                carga_w += qtd * watts
            except (TypeError, ValueError, OverflowError):
                pendencias.append(f"Linha {i}: quantidade ou potência inválida em {qtd_key}.")
    kw = carga_w / 1000.0
    motivo = motivo_conferencia(carga_w, perfil)
    if motivo:
        pendencias.append(motivo)
    if kw > 75:
        pendencias.append("Carga instalada acima de 75 kW: fora do escopo deste perfil.")
    demanda = (previa or {}).get("demanda_kva")
    try:
        demanda = float(demanda)
        if not math.isfinite(demanda) or demanda <= 0:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        demanda = None
    if (previa or {}).get("status") != "calculado" or demanda is None:
        pendencias.append("Prévia de demanda incompleta ou inválida.")
    elif demanda > 75:
        pendencias.append("Demanda acima de 75 kVA: fora do limite trifásico em 220/127 V.")

    candidato = None
    if not pendencias:
        if kw <= 10:
            if kw >= 5.1:
                candidato = {"categoria": "M1", "modalidade": "Monofásico", "disjuntor_tabela_a": 63}
            else:
                pendencias.append("Carga inferior a 5,1 kW: não inferir M1 pela modalidade; conferir a Tabela 3.")
        elif 11.1 <= kw <= 13:
            candidato = {"categoria": "B1", "modalidade": "Bifásico", "disjuntor_tabela_a": 63}
        elif kw > 18:
            for categoria, minimo, maximo, disjuntor in FAIXAS_TRIFASICAS:
                if minimo <= demanda <= maximo:
                    candidato = {"categoria": categoria, "modalidade": "Trifásico", "disjuntor_tabela_a": disjuntor}
                    break
            if candidato is None:
                pendencias.append("Demanda em lacuna decimal da Tabela 3: conferir sem arredondamento automático.")
    return {"status": "candidato" if candidato else "conferencia_tecnica",
            "carga_instalada_kw": kw, "demanda_kva": demanda,
            "candidato": candidato, "pendencias": list(dict.fromkeys(pendencias)),
            "fonte": "DIS-NOR-030 Rev. 07, item 6.28.1 e Tabela 3, página 63",
            "aprovado": False}
