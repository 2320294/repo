import json
import streamlit as st
from perfis_normativos import listar_perfis, salvar_perfil, atualizar_status
from concessionarias import UFS

from municipios_brasil import municipios_da_uf
CATEGORIAS_DEMANDA = [
    ("iluminacao_tug", "Iluminação + TUG"),
    ("chuveiros", "Chuveiros / aquecimento elétrico"),
    ("boiler", "Boiler / aquecedor central elétrico"),
    ("eletrodomesticos", "Secadora, forno, lava-louças e micro-ondas"),
    ("fogoes", "Fogões / cooktops elétricos"),
    ("ar_condicionado", "Ar-condicionado"),
    ("motores", "Motores"),
    ("equipamentos_especiais", "Equipamentos especiais"),
    ("hidromassagem", "Hidromassagem / banheira elétrica"),
    ("demais_tues", "Demais TUEs / outras cargas"),
]


def _emails_admin_secrets():
    try:
        bloco = st.secrets.get("admin", {})
        valor = bloco.get("emails", []) if hasattr(bloco, "get") else []
        if isinstance(valor, str):
            return {x.strip().lower() for x in valor.split(",") if x.strip()}
        return {str(x).strip().lower() for x in valor if str(x).strip()}
    except Exception:
        return set()


def usuario_e_admin(email):
    email = str(email or "").strip().lower()
    if not email:
        return False
    if email in _emails_admin_secrets():
        return True
    try:
        from config import obter_supabase
        r = obter_supabase().table("usuarios").select("role").eq("email", email).limit(1).execute()
        return bool(r.data and str(r.data[0].get("role", "")).upper() == "ADMIN")
    except Exception:
        return False


def _numero(txt):
    txt = str(txt or "").strip().replace(".", "").replace(",", ".") if "," in str(txt or "") else str(txt or "").strip()
    if not txt:
        return None
    try:
        return float(txt)
    except Exception:
        return None


def _texto_numero(valor):
    if valor in (None, ""):
        return ""
    try:
        n = float(valor)
        return str(int(n)) if n.is_integer() else str(n).replace(".", ",")
    except Exception:
        return str(valor)


def _regras_base(regras=None):
    r = regras if isinstance(regras, dict) else {}
    return {
        "schema": "autoeletrica.perfil_normativo.v2",
        "tipo_instalacao": r.get("tipo_instalacao", "Residencial individual"),
        "fornecimento": dict(r.get("fornecimento") or {}),
        "demanda": dict(r.get("demanda") or {}),
        "observacoes": r.get("observacoes", ""),
        "fonte_conferida": bool(r.get("fonte_conferida", False)),
    }



def _sincronizar_regras_ged13_residencial(regras=None):
    """Materializa no JSON persistido as regras oficiais GED-13 usadas pelo editor.

    Rev.200: perfis criados antes das revisões 192–196 podiam exibir as tabelas
    pela interface sem tê-las gravadas em ``regras.demanda``. Esta função cria
    a representação canônica que também é consumida pelo validador.
    """
    r = _regras_base(regras)
    if r.get("tipo_instalacao") != "Residencial individual":
        return r

    # Rev.201 — materializa também os parâmetros de fornecimento no mesmo
    # schema canônico consumido pelo validador. Nas revisões anteriores esses
    # valores podiam aparecer nos widgets do editor, mas não existir no JSON
    # persistido de perfis antigos, resultando em ``None`` nos quatro testes.
    f = dict(r.get("fornecimento") or {})
    if f.get("tensao_fase_neutro_v") in (None, ""):
        f["tensao_fase_neutro_v"] = 127.0
    if f.get("tensao_fase_fase_v") in (None, ""):
        f["tensao_fase_fase_v"] = 220.0
    if f.get("limite_potencia_instalada_kw") in (None, ""):
        legado = f.get("limite_fornecimento_kva")
        f["limite_potencia_instalada_kw"] = float(legado) if legado not in (None, "") else 75.0
    modalidades = f.get("modalidades")
    if not isinstance(modalidades, list) or not modalidades:
        f["modalidades"] = ["Monofásico", "Bifásico", "Trifásico"]
    # GED-13 v46.0, itens 6.4.1–6.4.3 e Tabelas 1A/1B: classe 127/220 V.
    # Somente completa o perfil CPFL GED-13 sincronizado pelo chamador quando
    # nenhuma faixa foi gravada; preserva qualquer cadastro parcial ou existente.
    if (not f.get("faixas_modalidade_kw")
            and float(f.get("tensao_fase_neutro_v") or 0) == 127
            and float(f.get("tensao_fase_fase_v") or 0) == 220):
        f["faixas_modalidade_kw"] = [
            {"modalidade": "Monofásico", "min_kw": 0.0, "max_kw": 12.0,
             "inclui_min": True, "inclui_max": True},
            {"modalidade": "Bifásico", "min_kw": 12.0, "max_kw": 25.0,
             "inclui_min": False, "inclui_max": True},
            {"modalidade": "Trifásico", "min_kw": 25.0, "max_kw": 75.0,
             "inclui_min": False, "inclui_max": True},
        ]
    r["fornecimento"] = f

    d = dict(r.get("demanda") or {})
    d["iluminacao_tug"] = {
        "metodo":"Tabela por faixas","tabela_id":"GED13_TABELA_3","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":1.0,"variavel":"carga_instalada_iluminacao_tug_kw",
        "faixas":[
            {"min_kw":0.0,"max_kw":1.0,"fator":0.86},{"min_kw":1.0,"max_kw":2.0,"fator":0.75},{"min_kw":2.0,"max_kw":3.0,"fator":0.66},{"min_kw":3.0,"max_kw":4.0,"fator":0.59},{"min_kw":4.0,"max_kw":5.0,"fator":0.52},{"min_kw":5.0,"max_kw":6.0,"fator":0.45},{"min_kw":6.0,"max_kw":7.0,"fator":0.40},{"min_kw":7.0,"max_kw":8.0,"fator":0.35},{"min_kw":8.0,"max_kw":9.0,"fator":0.31},{"min_kw":9.0,"max_kw":10.0,"fator":0.27},{"min_kw":10.0,"max_kw":None,"fator":0.24}
        ]}
    fatores4=[(1,1.00),(2,1.00),(3,0.84),(4,0.76),(5,0.70),(6,0.65),(7,0.60),(8,0.57),(9,0.54),(10,0.52),(11,0.49),(12,0.48),(13,0.46),(14,0.45),(15,0.44),(16,0.43),(17,0.42),(18,0.41),(19,0.40),(20,0.40),(21,0.39),(22,0.39),(23,0.39),(24,0.38),(25,0.38)]
    d["chuveiros"]={"metodo":"Tabela por quantidade","tabela_id":"GED13_TABELA_4","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","variavel":"numero_aparelhos_chuveiros_torneiras_aquecedores_passagem_ferros","fatores_por_quantidade":[{"quantidade":n,"fator":fd} for n,fd in fatores4],"acima_de_25":{"fator":0.38}}
    d["boiler"]={"metodo":"Tabela por quantidade","tabela_id":"GED13_TABELA_5","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":1.0,"variavel":"numero_aquecedores_centrais_ou_acumulacao","fatores_por_quantidade":[{"quantidade":1,"fator":1.00},{"quantidade":2,"fator":0.72},{"quantidade":3,"fator":0.62}],"acima_de_3":{"fator":0.62}}
    d["eletrodomesticos"]={"metodo":"Tabela por quantidade","tabela_id":"GED13_TABELA_6","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":1.0,"variavel":"numero_secadoras_fornos_lava_loucas_microondas","faixas_quantidade":[{"min":1,"max":1,"fator":1.00},{"min":2,"max":4,"fator":0.70},{"min":5,"max":6,"fator":0.60},{"min":7,"max":8,"fator":0.50},{"min":9,"max":None,"fator":0.50}]}
    d["fogoes"]={"metodo":"Tabela por quantidade","tabela_id":"GED13_TABELA_7","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":1.0,"variavel":"numero_fogoes_eletricos","faixas_quantidade":[{"min":1,"max":1,"fator":1.00},{"min":2,"max":2,"fator":0.60},{"min":3,"max":3,"fator":0.48},{"min":4,"max":4,"fator":0.40},{"min":5,"max":5,"fator":0.37},{"min":6,"max":6,"fator":0.35},{"min":7,"max":7,"fator":0.33},{"min":8,"max":8,"fator":0.32},{"min":9,"max":9,"fator":0.31},{"min":10,"max":11,"fator":0.30},{"min":12,"max":15,"fator":0.28},{"min":16,"max":20,"fator":0.26},{"min":21,"max":25,"fator":0.26},{"min":26,"max":None,"fator":0.26}]}
    aparelhos=[(7100,1100,900),(8500,1550,1300),(10000,1650,1400),(12000,1900,1600),(14000,2100,1900),(18000,2860,2600),(21000,3080,2800),(30000,4000,3600)]
    d["ar_condicionado"]={"metodo":"Regra específica","tabela_id":"GED13_TABELAS_8_9","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","uso_residencial_fator_demanda":1.0,"unidade_central_fator_demanda":1.0,"tabela_potencias":[{"btu_h":b,"potencia_va":va,"potencia_w":w} for b,va,w in aparelhos],"tabela_9_comercial":[{"min":1,"max":10,"fator":1.00},{"min":11,"max":20,"fator":0.90},{"min":21,"max":30,"fator":0.82},{"min":31,"max":40,"fator":0.80},{"min":41,"max":50,"fator":0.77},{"min":51,"max":75,"fator":0.75},{"min":76,"max":100,"fator":0.75},{"min":101,"max":None,"fator":0.75}]}
    d["motores"]={"metodo":"Regra por ordem de potência","tabela_id":"GED13_TABELA_10","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fatores_ordem":{"primeiro":1.0,"segundo":0.9,"terceiro_quarto_quinto":0.8,"demais":0.7},"regra_motores_iguais":True,"regra_simultaneos_agrupar":True}
    d["equipamentos_especiais"]={"metodo":"Regra por tipo e ordem de potência","tabela_id":"GED13_TABELA_11","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":0.75,"regras":{"solda_arco_galvanizacao":{"primeiro":1.0,"segundo":0.7,"terceiro":0.4,"demais":0.3},"solda_resistencia":{"maior":1.0,"demais":0.6},"raios_x":{"maior":1.0,"demais":0.7}}}
    d["hidromassagem"]={"metodo":"GED-13 / Tabela 10 (motores)","tabela_id":"GED13_TABELA_10_HIDROMASSAGEM","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":1.0,"usar_regra_motores_tabela_10":True}
    d["demais_tues"]={"metodo":"Sem regra genérica","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","regra":"classificar_por_categoria_normativa","fator_generico":None}
    r["demanda"] = d
    return r

def _perfil_pronto(regras):
    if not isinstance(regras, dict) or regras.get("schema") not in ("autoeletrica.perfil_normativo.v1", "autoeletrica.perfil_normativo.v2"):
        return False
    if not regras.get("fonte_conferida"):
        return False
    f = regras.get("fornecimento") or {}
    return bool(f.get("tensao_fase_neutro_v") and f.get("tensao_fase_fase_v"))


def _editor_regras(prefixo, regras=None):
    r = _regras_base(regras)
    f = r["fornecimento"]
    demanda = r["demanda"]

    st.markdown("#### Aplicação e fornecimento")
    tipo = st.selectbox(
        "Tipo de instalação atendida pelo perfil",
        ["Residencial individual", "Comercial individual", "Misto", "Outro"],
        index=max(0, ["Residencial individual", "Comercial individual", "Misto", "Outro"].index(r["tipo_instalacao"])) if r["tipo_instalacao"] in ["Residencial individual", "Comercial individual", "Misto", "Outro"] else 0,
        key=f"{prefixo}_tipo",
    )
    c1, c2, c3 = st.columns(3)
    vfn = c1.text_input("Tensão fase-neutro (V)", value=_texto_numero(f.get("tensao_fase_neutro_v")), key=f"{prefixo}_vfn")
    vff = c2.text_input("Tensão fase-fase (V)", value=_texto_numero(f.get("tensao_fase_fase_v")), key=f"{prefixo}_vff")
    limite = c3.text_input("Limite de potência instalada (kW)", value=_texto_numero(f.get("limite_potencia_instalada_kw", f.get("limite_fornecimento_kva"))), key=f"{prefixo}_lim", help="Cadastre o limite em kW conforme o documento oficial da concessionária. Este campo não representa demanda em kVA.")
    fases = st.multiselect(
        "Modalidades permitidas",
        ["Monofásico", "Bifásico", "Trifásico"],
        default=f.get("modalidades", []),
        key=f"{prefixo}_fases",
    )

    st.markdown("##### Faixas de modalidade de fornecimento")
    st.caption("Cadastre os limites exatamente como constam na norma da concessionária. Se ficarem vazios, o AutoElétrica não inventa limites nem reutiliza regras de outra região.")
    faixas_atuais = f.get("faixas_modalidade_kw") or []
    def _max_faixa(mod):
        for _fx in faixas_atuais:
            if str((_fx or {}).get("modalidade") or "") == mod:
                return _texto_numero((_fx or {}).get("max_kw"))
        return ""
    fm1, fm2, fm3 = st.columns(3)
    max_mono = fm1.text_input("Máximo monofásico (kW)", value=_max_faixa("Monofásico"), key=f"{prefixo}_max_mono")
    max_bi = fm2.text_input("Máximo bifásico (kW)", value=_max_faixa("Bifásico"), key=f"{prefixo}_max_bi")
    max_tri = fm3.text_input("Máximo trifásico (kW)", value=_max_faixa("Trifásico"), key=f"{prefixo}_max_tri")

    st.markdown("#### Regras de demanda")
    st.caption("Cadastre somente fatores/faixas confirmados na norma oficial. Campos vazios permanecem sem regra e não são inventados pelo sistema.")
    eh_ged13_persistido = any(
        "GED13_" in str((v or {}).get("tabela_id") or "")
        for v in demanda.values() if isinstance(v, dict)
    )
    demanda_saida = {}
    for chave, rotulo in CATEGORIAS_DEMANDA:
        atual = demanda.get(chave) or {}
        with st.expander(rotulo, expanded=False):
            # GED-13 v46.0: tabelas oficiais residenciais estruturadas.
            # O método é fixado pela própria norma para evitar contradição entre a tela e os dados gravados.
            if chave == "iluminacao_tug" and tipo == "Residencial individual" and eh_ged13_persistido:
                metodo = "Tabela por faixas"
                st.selectbox(
                    "Método",
                    ["Tabela por faixas — GED-13 / Tabela 3"],
                    index=0,
                    key=f"{prefixo}_{chave}_metodo_ged13",
                    disabled=True,
                )
                faixas_ged13 = [
                    {"min_kw": 0.0, "max_kw": 1.0, "fator": 0.86},
                    {"min_kw": 1.0, "max_kw": 2.0, "fator": 0.75},
                    {"min_kw": 2.0, "max_kw": 3.0, "fator": 0.66},
                    {"min_kw": 3.0, "max_kw": 4.0, "fator": 0.59},
                    {"min_kw": 4.0, "max_kw": 5.0, "fator": 0.52},
                    {"min_kw": 5.0, "max_kw": 6.0, "fator": 0.45},
                    {"min_kw": 6.0, "max_kw": 7.0, "fator": 0.40},
                    {"min_kw": 7.0, "max_kw": 8.0, "fator": 0.35},
                    {"min_kw": 8.0, "max_kw": 9.0, "fator": 0.31},
                    {"min_kw": 9.0, "max_kw": 10.0, "fator": 0.27},
                    {"min_kw": 10.0, "max_kw": None, "fator": 0.24},
                ]
                st.caption("GED-13 v46.0 — Tabela 3: fatores de demanda de tomadas e iluminação residencial.")
                st.dataframe(
                    [{"Carga instalada (kW)": (f"{x['min_kw']:g} < C < {x['max_kw']:g}" if x['max_kw'] is not None else "C > 10"), "Fator de demanda": f"{x['fator']:.2f}".replace(".", ",")} for x in faixas_ged13],
                    use_container_width=True, hide_index=True,
                )
                st.info("Origem: GED-13, versão 46.0, publicação 19/03/2026, Tabela 3. Para instalação residencial, FP = 1.")
                demanda_saida[chave] = {
                    "metodo": metodo,
                    "tabela_id": "GED13_TABELA_3",
                    "documento": "GED-13",
                    "versao_documento": "46.0",
                    "publicacao": "19/03/2026",
                    "fator_potencia": 1.0,
                    "variavel": "carga_instalada_iluminacao_tug_kw",
                    "faixas": faixas_ged13,
                }
            elif chave == "chuveiros" and tipo == "Residencial individual" and eh_ged13_persistido:
                metodo = "Tabela por quantidade"
                st.selectbox(
                    "Método",
                    ["Tabela por quantidade — GED-13 / Tabela 4"],
                    index=0,
                    key=f"{prefixo}_{chave}_metodo_ged13",
                    disabled=True,
                )
                fatores = [
                    (1, 1.00), (2, 1.00), (3, 0.84), (4, 0.76), (5, 0.70),
                    (6, 0.65), (7, 0.60), (8, 0.57), (9, 0.54), (10, 0.52),
                    (11, 0.49), (12, 0.48), (13, 0.46), (14, 0.45), (15, 0.44),
                    (16, 0.43), (17, 0.42), (18, 0.41), (19, 0.40), (20, 0.40),
                    (21, 0.39), (22, 0.39), (23, 0.39), (24, 0.38), (25, 0.38),
                ]
                st.caption("GED-13 v46.0 — Tabela 4: chuveiros, torneiras, aquecedores de água de passagem e ferros elétricos.")
                st.dataframe(
                    [{"Nº de aparelhos": str(n), "Fator de demanda": f"{fd:.2f}".replace(".", ",")} for n, fd in fatores] + [{"Nº de aparelhos": "Acima de 25", "Fator de demanda": "0,38"}],
                    use_container_width=True, hide_index=True,
                )
                st.info("Origem: GED-13, versão 46.0, publicação 19/03/2026, Tabela 4. O fator é selecionado pelo número total de aparelhos abrangidos pela tabela.")
                demanda_saida[chave] = {
                    "metodo": metodo,
                    "tabela_id": "GED13_TABELA_4",
                    "documento": "GED-13",
                    "versao_documento": "46.0",
                    "publicacao": "19/03/2026",
                    "variavel": "numero_aparelhos_chuveiros_torneiras_aquecedores_passagem_ferros",
                    "fatores_por_quantidade": [{"quantidade": n, "fator": fd} for n, fd in fatores],
                    "acima_de_25": {"fator": 0.38},
                }
            elif chave == "boiler" and tipo == "Residencial individual" and eh_ged13_persistido:
                metodo = "Tabela por quantidade"
                st.selectbox(
                    "Método",
                    ["Tabela por quantidade — GED-13 / Tabela 5"],
                    index=0,
                    key=f"{prefixo}_{chave}_metodo_ged13",
                    disabled=True,
                )
                fatores = [
                    ("1", 1.00),
                    ("2", 0.72),
                    ("3", 0.62),
                    ("Acima de 3", 0.62),
                ]
                st.caption("GED-13 — Tabela 5: fatores de demanda de aquecedor central ou de acumulação (boiler).")
                st.dataframe(
                    [{"Nº de aparelhos": n, "Fator de demanda": f"{fd:.2f}".replace(".", ",")} for n, fd in fatores],
                    use_container_width=True, hide_index=True,
                )
                st.info("Origem: GED-13, Tabela 5. O fator é selecionado pelo número total de aquecedores centrais ou de acumulação (boilers).")
                demanda_saida[chave] = {
                    "metodo": metodo,
                    "tabela_id": "GED13_TABELA_5",
                    "documento": "GED-13",
                    "versao_documento": "46.0",
                    "publicacao": "19/03/2026",
                    "fator_potencia": 1.0,
                    "variavel": "numero_aquecedores_centrais_ou_acumulacao",
                    "fatores_por_quantidade": [
                        {"quantidade": 1, "fator": 1.00},
                        {"quantidade": 2, "fator": 0.72},
                        {"quantidade": 3, "fator": 0.62},
                    ],
                    "acima_de_3": {"fator": 0.62},
                }
            elif chave == "eletrodomesticos" and tipo == "Residencial individual" and eh_ged13_persistido:
                metodo = "Tabela por quantidade"
                st.selectbox(
                    "Método",
                    ["Tabela por quantidade — GED-13 / Tabela 6"],
                    index=0,
                    key=f"{prefixo}_{chave}_metodo_ged13",
                    disabled=True,
                )
                fatores = [
                    ("1", 1.00),
                    ("2 a 4", 0.70),
                    ("5 a 6", 0.60),
                    ("7 a 8", 0.50),
                    ("Acima de 8", 0.50),
                ]
                st.caption("GED-13 v46.0 — Tabela 6: fatores de demanda de secadora de roupa, forno elétrico, máquina de lavar louça e forno micro-ondas.")
                st.dataframe(
                    [{"Nº de aparelhos": n, "Fator de demanda": f"{fd:.2f}".replace(".", ",")} for n, fd in fatores],
                    use_container_width=True, hide_index=True,
                )
                st.info("Origem: GED-13, versão 46.0, publicação 19/03/2026, Tabela 6. O fator é selecionado pelo número total de aparelhos abrangidos pela tabela.")
                demanda_saida[chave] = {
                    "metodo": metodo,
                    "tabela_id": "GED13_TABELA_6",
                    "documento": "GED-13",
                    "versao_documento": "46.0",
                    "publicacao": "19/03/2026",
                    "fator_potencia": 1.0,
                    "variavel": "numero_secadoras_fornos_lava_loucas_microondas",
                    "faixas_quantidade": [
                        {"min": 1, "max": 1, "fator": 1.00},
                        {"min": 2, "max": 4, "fator": 0.70},
                        {"min": 5, "max": 6, "fator": 0.60},
                        {"min": 7, "max": 8, "fator": 0.50},
                        {"min": 9, "max": None, "fator": 0.50},
                    ],
                }
            elif chave == "fogoes" and tipo == "Residencial individual" and eh_ged13_persistido:
                metodo = "Tabela por quantidade"
                st.selectbox("Método", ["Tabela por quantidade — GED-13 / Tabela 7"], index=0, key=f"{prefixo}_{chave}_metodo_ged13", disabled=True)
                fatores = [("1",1.00),("2",0.60),("3",0.48),("4",0.40),("5",0.37),("6",0.35),("7",0.33),("8",0.32),("9",0.31),("10 a 11",0.30),("12 a 15",0.28),("16 a 20",0.26),("21 a 25",0.26),("Acima de 25",0.26)]
                st.caption("GED-13 v46.0 — Tabela 7: fatores de demanda de fogões elétricos.")
                st.dataframe([{"Nº de aparelhos": n, "Fator de demanda": f"{fd:.2f}".replace(".", ",")} for n,fd in fatores], use_container_width=True, hide_index=True)
                st.info("Origem: GED-13, versão 46.0, publicação 19/03/2026, Tabela 7. Carga instalada pela potência de placa; FP = 1.")
                demanda_saida[chave] = {"metodo":metodo,"tabela_id":"GED13_TABELA_7","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":1.0,"variavel":"numero_fogoes_eletricos","faixas_quantidade":[{"min":1,"max":1,"fator":1.00},{"min":2,"max":2,"fator":0.60},{"min":3,"max":3,"fator":0.48},{"min":4,"max":4,"fator":0.40},{"min":5,"max":5,"fator":0.37},{"min":6,"max":6,"fator":0.35},{"min":7,"max":7,"fator":0.33},{"min":8,"max":8,"fator":0.32},{"min":9,"max":9,"fator":0.31},{"min":10,"max":11,"fator":0.30},{"min":12,"max":15,"fator":0.28},{"min":16,"max":20,"fator":0.26},{"min":21,"max":25,"fator":0.26},{"min":26,"max":None,"fator":0.26}]}
            elif chave == "ar_condicionado" and tipo == "Residencial individual" and eh_ged13_persistido:
                metodo = "Regra específica"
                st.selectbox("Método", ["GED-13 / Tabelas 8 e 9 + regra residencial"], index=0, key=f"{prefixo}_{chave}_metodo_ged13", disabled=True)
                aparelhos = [(7100,1100,900),(8500,1550,1300),(10000,1650,1400),(12000,1900,1600),(14000,2100,1900),(18000,2860,2600),(21000,3080,2800),(30000,4000,3600)]
                st.caption("GED-13 v46.0 — Tabela 8: potência de referência dos aparelhos de ar-condicionado tipo janela.")
                st.dataframe([{"BTU/h":b,"Potência (VA)":va,"Potência (W)":w} for b,va,w in aparelhos], use_container_width=True, hide_index=True)
                st.info("Uso residencial: fator de demanda = 1,00. A Tabela 9 é destinada ao uso comercial. Unidade central de ar-condicionado: FD = 1,00.")
                demanda_saida[chave] = {"metodo":metodo,"tabela_id":"GED13_TABELAS_8_9","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","uso_residencial_fator_demanda":1.0,"unidade_central_fator_demanda":1.0,"tabela_potencias":[{"btu_h":b,"potencia_va":va,"potencia_w":w} for b,va,w in aparelhos],"tabela_9_comercial":[{"min":1,"max":10,"fator":1.00},{"min":11,"max":20,"fator":0.90},{"min":21,"max":30,"fator":0.82},{"min":31,"max":40,"fator":0.80},{"min":41,"max":50,"fator":0.77},{"min":51,"max":75,"fator":0.75},{"min":76,"max":100,"fator":0.75},{"min":101,"max":None,"fator":0.75}]}
            elif chave == "motores" and tipo == "Residencial individual" and eh_ged13_persistido:
                metodo = "Regra por ordem de potência"
                st.selectbox("Método", ["GED-13 / Tabela 10"], index=0, key=f"{prefixo}_{chave}_metodo_ged13", disabled=True)
                fatores=[("1º maior",1.00),("2º maior",0.90),("3º, 4º e 5º maiores",0.80),("Soma dos demais",0.70)]
                st.caption("GED-13 v46.0 — Tabela 10: fatores de demanda de motores.")
                st.dataframe([{"Ordem de potência":n,"Fator de demanda":f"{fd:.2f}".replace(".",",")} for n,fd in fatores], use_container_width=True, hide_index=True)
                st.info("Motores iguais: apenas um é tratado como maior; os demais seguem a ordem. Motores obrigatoriamente simultâneos têm suas potências somadas e são considerados como um só motor.")
                demanda_saida[chave]={"metodo":metodo,"tabela_id":"GED13_TABELA_10","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fatores_ordem":{"primeiro":1.0,"segundo":0.9,"terceiro_quarto_quinto":0.8,"demais":0.7},"regra_motores_iguais":True,"regra_simultaneos_agrupar":True}
            elif chave == "equipamentos_especiais" and tipo == "Residencial individual" and eh_ged13_persistido:
                metodo = "Regra por tipo e ordem de potência"
                st.selectbox("Método", ["GED-13 / Tabela 11"], index=0, key=f"{prefixo}_{chave}_metodo_ged13", disabled=True)
                linhas=[("Solda a arco / galvanização","1º maior",1.00),("Solda a arco / galvanização","2º maior",0.70),("Solda a arco / galvanização","3º maior",0.40),("Solda a arco / galvanização","Soma dos demais",0.30),("Solda a resistência","Maior",1.00),("Solda a resistência","Soma dos demais",0.60),("Raios-X","Maior",1.00),("Raios-X","Soma dos demais",0.70)]
                st.caption("GED-13 v46.0 — Tabela 11: fatores de demanda de equipamentos especiais.")
                st.dataframe([{"Equipamento":e,"Ordem":o,"Fator":f"{fd:.2f}".replace(".",",")} for e,o,fd in linhas], use_container_width=True, hide_index=True)
                st.info("Aplicação por tipo de aparelho; FP = 0,75. Se os maiores aparelhos forem iguais, somente um é considerado o maior.")
                demanda_saida[chave]={"metodo":metodo,"tabela_id":"GED13_TABELA_11","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":0.75,"regras":{"solda_arco_galvanizacao":{"primeiro":1.0,"segundo":0.7,"terceiro":0.4,"demais":0.3},"solda_resistencia":{"maior":1.0,"demais":0.6},"raios_x":{"maior":1.0,"demais":0.7}}}
            elif chave == "hidromassagem" and tipo == "Residencial individual" and eh_ged13_persistido:
                metodo = "GED-13 / Tabela 10 (motores)"
                st.selectbox("Método", ["GED-13 / Tabela 10 — motores"], index=0, key=f"{prefixo}_{chave}_metodo_ged13", disabled=True)
                st.info("GED-13 v46.0: hidromassagem usa potência de placa, fator de demanda da Tabela 10 (motores) e FP = 1. A antiga tabela específica de hidromassagem foi eliminada na revisão normativa.")
                demanda_saida[chave]={"metodo":metodo,"tabela_id":"GED13_TABELA_10_HIDROMASSAGEM","documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","fator_potencia":1.0,"usar_regra_motores_tabela_10":True}
            elif chave == "demais_tues" and tipo == "Residencial individual" and eh_ged13_persistido:
                metodo = "Sem regra genérica"
                st.selectbox("Método", ["Sem regra genérica — classificar pela categoria GED-13 aplicável"], index=0, key=f"{prefixo}_{chave}_metodo_ged13", disabled=True)
                st.info("O GED-13 não estabelece um único fator genérico para toda TUE. Cada carga deve ser enquadrada na categoria normativa correspondente; cargas não enquadradas permanecem pendentes de regra específica, sem fator inventado pelo AutoElétrica.")
                demanda_saida[chave]={"metodo":metodo,"documento":"GED-13","versao_documento":"46.0","publicacao":"19/03/2026","regra":"classificar_por_categoria_normativa","fator_generico":None}
            else:
                metodo = st.selectbox(
                    "Método",
                    ["Não cadastrado", "Fator único (%)", "Tabela por faixas", "Regra específica"],
                    index=["Não cadastrado", "Fator único (%)", "Tabela por faixas", "Regra específica"].index(atual.get("metodo", "Não cadastrado")) if atual.get("metodo", "Não cadastrado") in ["Não cadastrado", "Fator único (%)", "Tabela por faixas", "Regra específica"] else 0,
                    key=f"{prefixo}_{chave}_metodo",
                )
                fator = st.text_input("Fator de demanda (%)", value=_texto_numero(atual.get("fator_percentual")), key=f"{prefixo}_{chave}_fator", disabled=metodo != "Fator único (%)")
                tabela = st.text_area("Tabela/faixas ou regra oficial", value=atual.get("regra_texto", ""), height=90, key=f"{prefixo}_{chave}_regra", disabled=metodo not in ("Tabela por faixas", "Regra específica"), help="Transcreva de forma estruturada/resumida a regra confirmada no documento oficial; não é necessário editar JSON.")
                demanda_saida[chave] = {"metodo": metodo}
                if metodo == "Fator único (%)":
                    demanda_saida[chave]["fator_percentual"] = _numero(fator)
                elif metodo in ("Tabela por faixas", "Regra específica"):
                    demanda_saida[chave]["regra_texto"] = tabela.strip()

    obs = st.text_area("Observações normativas / exceções", value=r.get("observacoes", ""), height=90, key=f"{prefixo}_obs")
    # Rev.199 — a confirmação documental é uma etapa administrativa separada,
    # liberada somente depois que a validação automática passa 100%.
    # Aqui apenas preservamos o estado já gravado no perfil.
    conferida = bool(r.get("fonte_conferida"))
    faixas_modalidade = []
    anterior = 0.0
    for modalidade, texto_max in (("Monofásico", max_mono), ("Bifásico", max_bi), ("Trifásico", max_tri)):
        maximo = _numero(texto_max)
        if modalidade in fases and maximo not in (None, ""):
            faixas_modalidade.append({
                "modalidade": modalidade, "min_kw": anterior, "max_kw": float(maximo),
                "inclui_min": modalidade == "Monofásico", "inclui_max": True
            })
            anterior = float(maximo)
    return {
        "schema": "autoeletrica.perfil_normativo.v2",
        "tipo_instalacao": tipo,
        "fornecimento": {
            "tensao_fase_neutro_v": _numero(vfn),
            "tensao_fase_fase_v": _numero(vff),
            "limite_potencia_instalada_kw": _numero(limite),
            "modalidades": fases,
            "faixas_modalidade_kw": faixas_modalidade,
        },
        "demanda": demanda_saida,
        "observacoes": obs.strip(),
        "fonte_conferida": conferida,
    }



def _quase_igual(a, b, tol=1e-9):
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return False


def _validar_perfil_ged13(regras):
    """Valida estrutura e casos matemáticos do perfil GED-13 residencial.

    Não altera cálculo de projeto. Serve como trava administrativa antes de
    permitir VALIDADO/ATIVO.
    """
    resultados = []

    def teste(grupo, caso, esperado, obtido, ok=None):
        passou = _quase_igual(obtido, esperado, 1e-8) if ok is None else bool(ok)
        resultados.append({
            "Grupo": grupo,
            "Caso de teste": caso,
            "Esperado": esperado,
            "Obtido": obtido,
            "Status": "PASSOU" if passou else "FALHOU",
        })
        return passou

    if not isinstance(regras, dict):
        teste("Perfil", "Estrutura de regras", "dicionário válido", type(regras).__name__, False)
        return False, resultados

    f = regras.get("fornecimento") or {}
    teste("Fornecimento", "Tensão fase-neutro", 127.0, f.get("tensao_fase_neutro_v"))
    teste("Fornecimento", "Tensão fase-fase", 220.0, f.get("tensao_fase_fase_v"))
    teste("Fornecimento", "Limite de potência instalada", 75.0, f.get("limite_potencia_instalada_kw"))
    mods = set(f.get("modalidades") or [])
    teste("Fornecimento", "Modalidades M/B/T", "Monofásico, Bifásico, Trifásico", ", ".join(sorted(mods)), mods == {"Monofásico", "Bifásico", "Trifásico"})
    faixas_fornecimento = f.get("faixas_modalidade_kw") or []
    faixas_por_modalidade = {
        faixa.get("modalidade"): faixa for faixa in faixas_fornecimento
        if isinstance(faixa, dict)
    } if isinstance(faixas_fornecimento, list) else {}
    anterior = 0.0
    for modalidade in ("Monofásico", "Bifásico", "Trifásico"):
        faixa = faixas_por_modalidade.get(modalidade) or {}
        minimo = _numero(faixa.get("min_kw"))
        maximo = _numero(faixa.get("max_kw"))
        valido = (minimo is not None and maximo is not None
                  and abs(minimo - anterior) < 1e-8 and maximo > minimo)
        teste("Fornecimento", f"Faixa {modalidade} (kW)",
              "limites cadastrados e crescentes", faixa or "ausente", valido)
        if valido:
            anterior = maximo

    d = regras.get("demanda") or {}

    # Tabela 3 — caso documental já usado no cadastro: 4,2 kW x 0,52 = 2,184 kVA (FP=1).
    t3 = d.get("iluminacao_tug") or {}
    faixas = t3.get("faixas") or []
    fator_42 = next((x.get("fator") for x in faixas if _quase_igual(x.get("min_kw"), 4.0) and _quase_igual(x.get("max_kw"), 5.0)), None)
    teste("Tabela 3", "Fator para 4,2 kW", 0.52, fator_42)
    teste("Tabela 3", "Demanda para 4,2 kW", 2.184, 4.2 * float(fator_42 or 0))
    teste("Tabela 3", "Faixa acima de 10 kW", 0.24, next((x.get("fator") for x in faixas if _quase_igual(x.get("min_kw"), 10.0) and x.get("max_kw") is None), None))

    # Tabela 4
    t4 = d.get("chuveiros") or {}
    q4 = {int(x.get("quantidade")): x.get("fator") for x in (t4.get("fatores_por_quantidade") or []) if x.get("quantidade") is not None}
    teste("Tabela 4", "3 aparelhos", 0.84, q4.get(3))
    teste("Tabela 4", "25 aparelhos", 0.38, q4.get(25))
    teste("Tabela 4", "Acima de 25", 0.38, (t4.get("acima_de_25") or {}).get("fator"))

    # Tabela 5
    t5 = d.get("boiler") or {}
    q5 = {int(x.get("quantidade")): x.get("fator") for x in (t5.get("fatores_por_quantidade") or []) if x.get("quantidade") is not None}
    teste("Tabela 5", "2 boilers", 0.72, q5.get(2))
    teste("Tabela 5", "Acima de 3", 0.62, (t5.get("acima_de_3") or {}).get("fator"))

    # Tabela 6
    t6 = d.get("eletrodomesticos") or {}
    fq6 = t6.get("faixas_quantidade") or []
    def fator_faixas(lista, n):
        for x in lista:
            mn, mx = x.get("min"), x.get("max")
            if mn is not None and n >= mn and (mx is None or n <= mx):
                return x.get("fator")
        return None
    teste("Tabela 6", "4 aparelhos", 0.70, fator_faixas(fq6, 4))
    teste("Tabela 6", "6 aparelhos", 0.60, fator_faixas(fq6, 6))
    teste("Tabela 6", "9 aparelhos", 0.50, fator_faixas(fq6, 9))

    # Tabela 7
    t7 = d.get("fogoes") or {}
    fq7 = t7.get("faixas_quantidade") or []
    teste("Tabela 7", "3 fogões", 0.48, fator_faixas(fq7, 3))
    teste("Tabela 7", "10 fogões", 0.30, fator_faixas(fq7, 10))
    teste("Tabela 7", "26 fogões", 0.26, fator_faixas(fq7, 26))

    # Tabelas 8/9 — no perfil residencial a demanda dos aparelhos é integral.
    t89 = d.get("ar_condicionado") or {}
    teste("Tabelas 8/9", "FD residencial", 1.00, t89.get("uso_residencial_fator_demanda"))
    teste("Tabelas 8/9", "Unidade central", 1.00, t89.get("unidade_central_fator_demanda"))
    pot = {int(x.get("btu_h")): x for x in (t89.get("tabela_potencias") or []) if x.get("btu_h") is not None}
    teste("Tabela 8", "12.000 BTU/h — potência VA", 1900.0, (pot.get(12000) or {}).get("potencia_va"))

    # Tabela 10 — valida fatores e um caso matemático de ordenação.
    t10 = d.get("motores") or {}
    fo = t10.get("fatores_ordem") or {}
    teste("Tabela 10", "1º maior motor", 1.00, fo.get("primeiro"))
    teste("Tabela 10", "2º maior motor", 0.90, fo.get("segundo"))
    teste("Tabela 10", "3º ao 5º", 0.80, fo.get("terceiro_quarto_quinto"))
    teste("Tabela 10", "Demais", 0.70, fo.get("demais"))
    motores = [5.0, 3.0, 2.0, 1.0, 0.5, 0.25]
    demanda_motores = motores[0]*float(fo.get("primeiro") or 0) + motores[1]*float(fo.get("segundo") or 0) + sum(motores[2:5])*float(fo.get("terceiro_quarto_quinto") or 0) + sum(motores[5:])*float(fo.get("demais") or 0)
    teste("Tabela 10", "Caso 6 motores [5;3;2;1;0,5;0,25]", 10.675, demanda_motores)

    # Tabela 11
    t11 = d.get("equipamentos_especiais") or {}
    re = t11.get("regras") or {}
    solda = re.get("solda_arco_galvanizacao") or {}
    teste("Tabela 11", "Solda a arco — 1º maior", 1.00, solda.get("primeiro"))
    teste("Tabela 11", "Solda a arco — 2º maior", 0.70, solda.get("segundo"))
    teste("Tabela 11", "FP equipamentos especiais", 0.75, t11.get("fator_potencia"))

    # Hidromassagem e TUEs sem regra genérica.
    hid = d.get("hidromassagem") or {}
    teste("Hidromassagem", "Reutiliza Tabela 10", True, hid.get("usar_regra_motores_tabela_10"), hid.get("usar_regra_motores_tabela_10") is True)
    outros = d.get("demais_tues") or {}
    teste("Demais TUEs", "Sem fator genérico inventado", None, outros.get("fator_generico"), "fator_generico" in outros and outros.get("fator_generico") is None)

    # Metadados mínimos de rastreabilidade para todas as categorias normativas automáticas.
    for chave in ["iluminacao_tug", "chuveiros", "boiler", "eletrodomesticos", "fogoes", "ar_condicionado", "motores", "equipamentos_especiais", "hidromassagem"]:
        regra = d.get(chave) or {}
        ok_meta = regra.get("documento") == "GED-13" and regra.get("versao_documento") == "46.0" and regra.get("publicacao") == "19/03/2026"
        teste("Rastreabilidade", chave, "GED-13 v46.0 · 19/03/2026", f"{regra.get('documento')} v{regra.get('versao_documento')} · {regra.get('publicacao')}", ok_meta)

    passou = bool(resultados) and all(x["Status"] == "PASSOU" for x in resultados)
    return passou, resultados


def _renderizar_validador_ged13(regras, prefixo):
    passou, resultados = _validar_perfil_ged13(regras)
    with st.expander("🧪 Validador do Perfil Normativo", expanded=True):
        st.caption("Verificação administrativa independente do cálculo dos projetos. Nenhuma demanda de projeto é alterada nesta etapa.")
        total = len(resultados)
        aprovados = sum(1 for x in resultados if x["Status"] == "PASSOU")
        if passou:
            st.success(f"Validação matemática concluída: {aprovados}/{total} verificações passaram.")
        else:
            st.error(f"Perfil ainda não pode ser validado: {aprovados}/{total} verificações passaram.")
        st.dataframe(resultados, use_container_width=True, hide_index=True)
    return passou

def _resumo_auditoria_ged13(regras):
    passou, resultados = _validar_perfil_ged13(regras)
    demanda = (regras or {}).get("demanda") or {}
    categorias = ["iluminacao_tug", "chuveiros", "boiler", "eletrodomesticos", "fogoes", "ar_condicionado", "motores", "equipamentos_especiais", "hidromassagem"]
    tabelas_ok = 0
    for chave in categorias:
        reg = demanda.get(chave) or {}
        if reg.get("documento") == "GED-13" and reg.get("versao_documento") == "46.0" and reg.get("publicacao") == "19/03/2026":
            tabelas_ok += 1
    total = len(resultados)
    aprovados = sum(1 for x in resultados if x.get("Status") == "PASSOU")
    pendencias = total - aprovados
    return passou, resultados, tabelas_ok, len(categorias), aprovados, total, pendencias


def _renderizar_resumo_auditoria(regras):
    passou, resultados, tabelas_ok, tabelas_total, aprovados, total, pendencias = _resumo_auditoria_ged13(regras)
    st.markdown("### 📋 Resumo da validação")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tabelas verificadas", f"{tabelas_ok}/{tabelas_total}")
    c2.metric("Testes matemáticos", f"{aprovados}/{total}")
    c3.metric("Pendências", str(pendencias))
    c4.metric("Documento", "GED-13 v46.0")
    if passou:
        st.success("Validação automática: 100% APROVADA. A conferência documental humana pode ser realizada como última etapa.")
    else:
        st.warning("Validação automática ainda possui pendências. A confirmação documental permanece bloqueada.")
    return passou, resultados


def renderizar_admin_normativos(email):
    st.title("⚙️ Administração — Perfis Normativos")
    st.caption("Somente perfis ATIVOS são disponibilizados aos usuários. O cadastro não altera automaticamente os cálculos da versão estável.")
    try:
        perfis = listar_perfis(False, administrativo=True)
    except Exception as e:
        st.error("Banco de perfis normativos ainda não preparado. Execute o arquivo supabase_perfis_normativos.sql no Supabase.")
        st.code(str(e))
        return

    with st.expander("➕ Novo perfil normativo", expanded=not bool(perfis)):
        with st.form("novo_perfil_normativo"):
            c1, c2, c3 = st.columns(3)
            concessionaria = c1.text_input("Concessionária")
            uf = c2.selectbox("UF", UFS)
            municipios_uf = municipios_da_uf(uf)
            municipio = c3.selectbox(
                "Município (opcional)",
                ["Toda a UF"] + municipios_uf,
                help="Selecione uma cidade para restringir o perfil. Use 'Toda a UF' somente quando a norma realmente se aplicar a todo o estado."
            )
            municipio = "" if municipio == "Toda a UF" else municipio
            documento = st.text_input("Documento / norma oficial")
            c4, c5 = st.columns(2)
            revisao = c4.text_input("Revisão")
            vigencia = c5.text_input("Data/vigência")
            fonte = st.text_input("Fonte / referência oficial")
            regras_json = _editor_regras("novo")
            if st.form_submit_button("Salvar como RASCUNHO", use_container_width=True):
                try:
                    salvar_perfil({"concessionaria": concessionaria.strip(), "uf": uf, "municipio": municipio.strip(), "documento": documento.strip(), "revisao": revisao.strip(), "vigencia": vigencia.strip(), "fonte_oficial": fonte.strip(), "regras": regras_json, "status": "RASCUNHO", "criado_por": email})
                    st.success("Perfil salvo como RASCUNHO.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Não foi possível salvar: {e}")

    if not perfis:
        st.info("Nenhum perfil cadastrado.")
        return

    st.subheader("Perfis cadastrados")
    for p in perfis:
        titulo = f"{p.get('concessionaria','')} — {p.get('municipio') or 'Toda a UF'}/{p.get('uf','')} — {p.get('documento') or 'Sem documento'} {p.get('revisao') or ''}"
        with st.expander(f"{titulo} · {p.get('status','RASCUNHO')}"):
            st.write(f"**Fonte:** {p.get('fonte_oficial') or '—'}")
            regras_atual = p.get("regras") or {}
            # Rev.201 — migração/sincronização do perfil GED-13 já existente, incluindo fornecimento.
            # O editor das revisões 192–196 exibia as tabelas canônicas, mas perfis
            # antigos podiam continuar com demanda vazia no Supabase. Aqui a mesma
            # estrutura oficial usada pela interface é materializada e persistida.
            regras_validacao = _regras_base(regras_atual)
            eh_ged13_cpfl = (
                str(p.get("concessionaria") or "").strip().casefold() == "cpfl piratininga"
                and "ged-13" in str(p.get("documento") or "").casefold()
                and regras_validacao.get("tipo_instalacao") == "Residencial individual"
            )
            if eh_ged13_cpfl:
                regras_sincronizadas = _sincronizar_regras_ged13_residencial(regras_validacao)
                if regras_sincronizadas != regras_validacao or str(p.get("revisao") or "").strip() != "46.0" or str(p.get("vigencia") or "").strip() != "19/03/2026":
                    try:
                        salvar_perfil({"regras": regras_sincronizadas, "revisao": "46.0", "vigencia": "19/03/2026"}, perfil_id=p.get("id"))
                        regras_validacao = regras_sincronizadas
                        p["regras"] = regras_sincronizadas
                        p["revisao"] = "46.0"
                        p["vigencia"] = "19/03/2026"
                        st.success("Perfil GED-13 sincronizado com a estrutura normativa v46.0. A auditoria abaixo já usa os dados persistidos.")
                    except Exception as e:
                        st.error(f"Não foi possível sincronizar o perfil GED-13 no banco: {e}")
                else:
                    regras_validacao = regras_sincronizadas
                regras_atual = p.get("regras") or regras_atual

            # Auditoria sempre visível antes da longa edição do perfil.
            validacao_resumo_ok, _ = _renderizar_resumo_auditoria(regras_validacao) if (regras_validacao.get("tipo_instalacao") == "Residencial individual") else (False, [])

            with st.form(f"editar_perfil_{p.get('id')}"):
                regras_editadas = _editor_regras(f"edit_{p.get('id')}", regras_atual)
                if st.form_submit_button("Salvar regras deste perfil", use_container_width=True):
                    try:
                        salvar_perfil({"regras": regras_editadas}, perfil_id=p.get("id"))
                        st.success("Regras salvas.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível atualizar: {e}")

            validacao_ok = _renderizar_validador_ged13(regras_validacao, f"val_{p.get('id')}") if (regras_validacao.get("tipo_instalacao") == "Residencial individual") else False

            # A confirmação humana é deliberadamente a última etapa.
            fonte_conferida = bool(regras_validacao.get("fonte_conferida"))
            st.markdown("#### Conferência documental final")
            if fonte_conferida:
                st.success("Fonte oficial confirmada pelo administrador.")
            elif validacao_ok:
                st.info("Todos os testes automáticos passaram. Confira o documento oficial e, somente depois, registre a confirmação abaixo.")
                if st.button("Confirmo a conferência no documento oficial", key=f"confirmar_fonte_{p.get('id')}", use_container_width=True):
                    try:
                        regras_confirmadas = dict(regras_validacao)
                        regras_confirmadas["fonte_conferida"] = True
                        salvar_perfil({"regras": regras_confirmadas}, perfil_id=p.get("id"))
                        st.success("Conferência documental registrada.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível registrar a conferência: {e}")
            else:
                st.caption("Confirmação documental bloqueada até 100% dos testes automáticos passarem.")

            pronto = _perfil_pronto(regras_validacao) and validacao_ok
            if not pronto:
                st.info("Perfil ainda incompleto ou com validação pendente: mantenha em RASCUNHO até todos os testes obrigatórios passarem e a fonte oficial estar confirmada.")
            cols = st.columns(4)
            for col, status in zip(cols, ["RASCUNHO", "VALIDADO", "ATIVO", "INATIVO"]):
                bloquear = status in ("VALIDADO", "ATIVO") and not pronto
                if col.button(status, key=f"status_{p.get('id')}_{status}", use_container_width=True, disabled=bloquear):
                    try:
                        atualizar_status(p.get("id"), status, email)
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
