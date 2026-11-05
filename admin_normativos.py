from normativo_neoenergia import perfil_bloco_neoenergia, planejar_bloco_neoenergia, cadastrar_bloco_neoenergia, testar_bloco_neoenergia, pendencias_bloco_neoenergia, CHAVE_BLOCO
from normativo_neoenergia import vincular_territorios_neoenergia, territorio_neoenergia_registrado, referencias_regionais_neoenergia, CHAVE_TERRITORIO as CHAVE_TERRITORIO_NEOENERGIA, testar_territorios_neoenergia
from normativo_neoenergia import CHAVE_ENTRADA as CHAVE_ENTRADA_NEOENERGIA, cadastrar_auditorias_entrada_neoenergia, auditoria_entrada_neoenergia_registrada, testar_entrada_bloco_neoenergia, consultar_entrada_neoenergia
from normativo_neoenergia import CHAVE_DEMANDA as CHAVE_DEMANDA_NEOENERGIA, cadastrar_auditorias_demanda_neoenergia, auditoria_demanda_neoenergia_registrada, testar_demanda_bloco_neoenergia, dados_ensaio_demanda_neoenergia, calcular_ensaio_demanda_neoenergia
from normativo_neoenergia import calcular_ensaio_integrado_neoenergia, testar_integracao_bloco_neoenergia, tabela_entrada_neoenergia
from normativo_neoenergia import CHAVE_CONSOLIDACAO as CHAVE_CONSOLIDACAO_NEOENERGIA, consolidar_ensaio_neoenergia, preparar_cargas_projeto_neoenergia, agrupar_cargas_projeto_neoenergia, testar_preparacao_projeto_neoenergia
from normativo_enel import CHAVE_MOTORES, registro_motores_enel_sp, registrar_auditoria_motores_enel_sp, testar_motores_enel_sp, consultar_motor_enel_sp
from normativo_enel import CHAVE_AUDITORIA, registrar_auditoria_entrada_enel_sp, registro_entrada_enel_sp, testar_entrada_enel_sp, previa_entrada_enel_sp
from normativo_enel import preparar_rascunho_enel_sp, perfil_enel_sp, auditar_cadastro_enel_sp, pendencias_ativacao_enel_sp
from normativo_cpfl import preparar_rascunho_rge, perfil_rge_ged13, perfil_ged13_380, pendencias_ativacao_rge
from normativo_cpfl import preparar_rascunho_santa_cruz, perfil_santa_cruz_ged13, pendencias_ativacao_santa_cruz, MUNICIPIOS_SANTA_CRUZ
from normativo_cpfl import _numero, _regras_base, _sincronizar_regras_ged13_residencial, _quase_igual, _validar_perfil_ged13, _resumo_auditoria_ged13
import json
from normativo_cpfl import preparar_rascunho_paulista_380, perfil_paulista_380
from normativo_cpfl import perfil_eh_piratininga, MUNICIPIOS_PIRATININGA, FONTE_MUNICIPIOS_PIRATININGA
from normativo_cpfl import preparar_rascunho_paulista, perfil_paulista_ged13, pendencias_ativacao_paulista
import streamlit as st
from perfis_normativos import listar_perfis, salvar_perfil, atualizar_status
from concessionarias import UFS

from municipios_brasil import municipios_da_uf
from normativo_elektro import municipios_MUNICIPIOS_ELEKTRO as MUNICIPIOS_ELEKTRO
from normativo_elektro import perfil_eh_perfil_elektro as eh_perfil_elektro, perfil_preparar_regras as preparar_regras, perfil_preparar_tabelas_demanda as preparar_tabelas_demanda, perfil_auditar_tabelas_demanda as auditar_tabelas_demanda, perfil_MUNICIPIO_TENSAO_ESPECIAL as MUNICIPIO_TENSAO_ESPECIAL
from normativo_elektro import demanda_calcular_previa as calcular_previa
from normativo_elektro import auditoria_CHAVE as CHAVE, auditoria_CASOS as CASOS, auditoria_registrar as registrar, auditoria_registro_atual as registro_atual
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




def _texto_numero(valor):
    if valor in (None, ""):
        return ""
    try:
        n = float(valor)
        return str(int(n)) if n.is_integer() else str(n).replace(".", ",")
    except Exception:
        return str(valor)






def _regras_confirmacao_fonte(perfil, regras_validacao):
    """Preserva tabelas e evidências Elektro ao confirmar somente a fonte."""
    from copy import deepcopy
    origem = (perfil.get("regras") or {}) if eh_perfil_elektro(perfil) else regras_validacao
    regras = deepcopy(origem)
    regras["fonte_conferida"] = True
    return regras


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







def _renderizar_validador_ged13(regras, prefixo, classe_380=False):
    passou, resultados = _validar_perfil_ged13(regras, classe_380=classe_380)
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



def _renderizar_resumo_auditoria(regras, classe_380=False):
    passou, resultados, tabelas_ok, tabelas_total, aprovados, total, pendencias = _resumo_auditoria_ged13(regras, classe_380=classe_380)
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
        st.markdown("#### Bloco Neoenergia — quatro distribuidoras")
        st.caption("Coelba/BA, Pernambuco/PE, Cosern/RN e Brasília/DF. Cadastro documental em RASCUNHO; municípios e regras elétricas regionais pendentes. Perfis existentes serão preservados.")
        plano_neoenergia = planejar_bloco_neoenergia(perfis, email)
        st.dataframe([{"Distribuidora":i["perfil"]["concessionaria"], "UF":i["perfil"]["uf"], "Norma":i["perfil"]["documento"] + " Rev. " + i["perfil"]["revisao"], "Ação":i["acao"]} for i in plano_neoenergia], hide_index=True, use_container_width=True)
        if st.button("Executar testes do cadastro em lote Neoenergia", key="testar_bloco_neoenergia"):
            testes_bloco = testar_bloco_neoenergia()
            st.dataframe(testes_bloco, hide_index=True, use_container_width=True)
            st.write(f"Cadastro: {sum(t['Resultado']=='PASSOU' for t in testes_bloco)}/{len(testes_bloco)} testes. Não valida cálculos elétricos.")
        if st.button("Cadastrar bloco Neoenergia — 4 rascunhos", key="cadastrar_bloco_neoenergia"):
            resultados_bloco = cadastrar_bloco_neoenergia(lambda:listar_perfis(False, administrativo=True), salvar_perfil, email)
            st.session_state["resultado_bloco_neoenergia"] = resultados_bloco
            st.rerun()
        if st.session_state.get("resultado_bloco_neoenergia"):
            st.dataframe(st.session_state["resultado_bloco_neoenergia"], hide_index=True, use_container_width=True)
            st.caption("O lote pode ser repetido para retomar erros: cadastros já existentes não são alterados. O banco confirma cada gravação individualmente.")

        st.caption("Enel São Paulo — 24 municípios: cadastro documental inicial, sem cálculo automático liberado.")
        if st.button("Preparar perfil Enel São Paulo (24 municípios)"):
            try:
                if any(perfil_enel_sp(item) for item in perfis):
                    st.info("Já existe um perfil Enel São Paulo. Nenhum registro foi alterado.")
                else:
                    salvar_perfil(preparar_rascunho_enel_sp(email))
                    st.success("Enel São Paulo cadastrada em RASCUNHO para auditoria documental.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível preparar o perfil Enel São Paulo: {exc}")

        st.caption("RGE — residencial 220/380 V: cadastro inicial dos 253 municípios confirmados na página oficial. As quatro exceções de tensão e os municípios ainda não conferidos ficam fora deste perfil.")
        if st.button("Preparar perfil RGE (RS — 220/380 V)"):
            try:
                if any(perfil_rge_ged13(item) for item in perfis):
                    st.info("Já existe um perfil RGE GED-13 v46.0. Nenhum registro foi alterado.")
                else:
                    salvar_perfil(preparar_rascunho_rge(email))
                    st.success("Perfil RGE criado em RASCUNHO. Confira testes e fonte oficial abaixo.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível preparar o perfil RGE: {exc}")

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
            municipios_atendidos = st.multiselect(
                "Municípios atendidos pela distribuidora (lista explícita)",
                municipios_uf,
                help="Selecione somente municípios confirmados na área de concessão. Uma lista vazia mantém o perfil indisponível no projeto.",
            )
            documento = st.text_input("Documento / norma oficial")
            c4, c5 = st.columns(2)
            revisao = c4.text_input("Revisão")
            vigencia = c5.text_input("Data/vigência")
            fonte = st.text_input("Fonte / referência oficial")
            regras_json = _editor_regras("novo")
            if st.form_submit_button("Salvar como RASCUNHO", use_container_width=True):
                try:
                    salvar_perfil({"concessionaria": concessionaria.strip(), "uf": uf, "municipio": municipio.strip(), "municipios_atendidos": municipios_atendidos, "documento": documento.strip(), "revisao": revisao.strip(), "vigencia": vigencia.strip(), "fonte_oficial": fonte.strip(), "regras": regras_json, "status": "RASCUNHO", "criado_por": email})
                    st.success("Perfil salvo como RASCUNHO.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Não foi possível salvar: {e}")

    if not perfis:
        st.info("Nenhum perfil cadastrado.")
        return

    st.subheader("Perfis cadastrados")
    if any(perfil_bloco_neoenergia(p) for p in perfis):
        st.markdown("#### Vínculo territorial — bloco Neoenergia")
        st.caption("Usa o catálogo municipal incluído no pacote, sem depender da disponibilidade do IBGE. Vincula somente os rascunhos já cadastrados: Coelba/BA (415), Pernambuco/PE (185 registros, incluindo Fernando de Noronha), Cosern/RN (167) e Brasília/DF (1). Área de concessão baseada nas fontes oficiais registradas; nomes e códigos provenientes do catálogo público identificado em cada perfil. Não ativa cálculos. Outras UFs exigem perfis separados.")
        if st.button("Executar testes do vínculo territorial Neoenergia"):
            testes_territorio = testar_territorios_neoenergia()
            st.dataframe(testes_territorio, hide_index=True, use_container_width=True)
            st.write(f"Vínculo territorial: {sum(t['Resultado']=='PASSOU' for t in testes_territorio)}/{len(testes_territorio)} testes de software. Não valida cálculos ou cobertura por endereço.")
        if st.button("Vincular municípios aos quatro rascunhos Neoenergia"):
            with st.spinner("Conferindo o catálogo municipal e registrando os vínculos..."):
                st.session_state['resultado_territorio_neoenergia'] = vincular_territorios_neoenergia(
                    lambda: listar_perfis(ativos_apenas=False, administrativo=True), salvar_perfil, email)
            st.rerun()
        if st.session_state.get('resultado_territorio_neoenergia'):
            st.dataframe(st.session_state['resultado_territorio_neoenergia'], hide_index=True, use_container_width=True)
            st.caption("Os vínculos já registrados são preservados. Se houver pendência, confira o detalhe; não é necessário aguardar a API do IBGE.")
        st.markdown("#### Auditoria de entrada — quatro perfis Neoenergia")
        st.caption("Tabela 1 da Coelba e Tabela 2 de Pernambuco/Cosern/Brasília. Referências isoladas; a demanda e a ativação dos perfis continuam pendentes. Condutores deste recorte: entrada subterrânea Cu XLPE/HEPR, separados do alimentador do QDC.")
        if st.button("Executar testes das tabelas de entrada Neoenergia"):
            testes_entrada_bloco = testar_entrada_bloco_neoenergia()
            st.dataframe(testes_entrada_bloco, hide_index=True, use_container_width=True)
            st.write(f"Tabelas de entrada: {sum(t['Resultado']=='PASSOU' for t in testes_entrada_bloco)}/{len(testes_entrada_bloco)} testes de software. Sem homologação elétrica.")
        if st.button("Registrar referências de entrada nos quatro rascunhos Neoenergia"):
            st.session_state['resultado_entrada_bloco_neoenergia'] = cadastrar_auditorias_entrada_neoenergia(
                lambda:listar_perfis(False, administrativo=True), salvar_perfil, email)
            st.rerun()
        if st.session_state.get('resultado_entrada_bloco_neoenergia'):
            st.dataframe(st.session_state['resultado_entrada_bloco_neoenergia'], hide_index=True, use_container_width=True)
        st.markdown("#### Auditoria de demanda — ensaio isolado Neoenergia")
        st.caption("Fatores residenciais trifásicos das Tabelas 6/7/8/9/12/16. Sem integração aos projetos. Fogões, motores, cargas especiais, recarga veicular, climatização central e usos coletivos/comerciais ficam fora deste ensaio.")
        if st.button("Executar testes de demanda isolada Neoenergia"):
            testes_demanda_bloco = testar_demanda_bloco_neoenergia()
            st.dataframe(testes_demanda_bloco, hide_index=True, use_container_width=True)
            st.write(f"Demanda isolada: {sum(t['Resultado']=='PASSOU' for t in testes_demanda_bloco)}/{len(testes_demanda_bloco)} testes de software. Não libera o perfil nem aprova instalações.")
        if st.button("Registrar demanda isolada nos quatro rascunhos Neoenergia"):
            st.session_state['resultado_demanda_bloco_neoenergia'] = cadastrar_auditorias_demanda_neoenergia(
                lambda:listar_perfis(False,administrativo=True),salvar_perfil,email)
            st.rerun()
        if st.session_state.get('resultado_demanda_bloco_neoenergia'):
            st.dataframe(st.session_state['resultado_demanda_bloco_neoenergia'],hide_index=True,use_container_width=True)
        st.markdown("#### Integração de auditoria — demanda e entrada Neoenergia")
        st.caption("Ensaio residencial individual trifásico dos grupos já auditados. Cruza demanda, carga instalada, tensão e corrente máxima de fase declarada com a tabela regional; não integra nem libera projetos dos usuários.")
        if st.button("Executar testes da integração demanda e entrada Neoenergia"):
            testes_integracao_bloco = testar_integracao_bloco_neoenergia()
            st.dataframe(testes_integracao_bloco,hide_index=True,use_container_width=True)
            st.write(f"Integração administrativa: {sum(t['Resultado']=='PASSOU' for t in testes_integracao_bloco)}/{len(testes_integracao_bloco)} testes de software. Sem homologação elétrica ou ativação de perfil.")
        if st.button("Executar testes da preparação de cargas do projeto Neoenergia"):
            testes_projeto_bloco = testar_preparacao_projeto_neoenergia()
            st.dataframe(testes_projeto_bloco,hide_index=True,use_container_width=True)
            st.write(f"Preparação de cargas: {sum(t['Resultado']=='PASSOU' for t in testes_projeto_bloco)}/{len(testes_projeto_bloco)} testes de software. Não valida projeto real.")
    for p in perfis:
        alcance = (f"{len(p.get('municipios_atendidos') or [])} municípios" if p.get("municipios_atendidos") is not None else (p.get("municipio") or "Toda a UF"))
        if perfil_bloco_neoenergia(p):
            alcance = f"{len(p.get('municipios_atendidos') or [])} registros territoriais" if territorio_neoenergia_registrado(p) else "território pendente"
        titulo = f"{p.get('concessionaria','')} — {alcance}/{p.get('uf','')} — {p.get('documento') or 'Sem documento'} {p.get('revisao') or ''}"
        with st.expander(f"{titulo} · {p.get('status','RASCUNHO')}"):
            st.write(f"**Fonte:** {p.get('fonte_oficial') or '—'}")
            if perfil_bloco_neoenergia(p):
                st.info("Cadastro documental do bloco Neoenergia. O vínculo territorial não libera cálculos; mantenha em RASCUNHO.")
                registro_bloco = (p.get("regras") or {}).get(CHAVE_BLOCO) or {}
                st.write({"Documento":p.get("documento"), "Revisão":p.get("revisao"), "Aprovação do documento":registro_bloco.get("data_aprovacao"), "Vigência":p.get("vigencia") or "A conferir", "Etapa":registro_bloco.get("etapa", "Cadastro pendente de auditoria")})
                if registro_bloco.get("portal"):
                    st.markdown("Portal oficial de normas: " + registro_bloco["portal"])
                if territorio_neoenergia_registrado(p):
                    territorio = p['regras'][CHAVE_TERRITORIO_NEOENERGIA]
                    st.success("Vínculo territorial registrado. Cálculos continuam pendentes de auditoria.")
                    st.caption(territorio['observacao'])
                    st.write({"Responsável":territorio['responsavel'], "Registrado em":territorio['registrado_em']})
                    with st.expander("Municípios e fontes do vínculo territorial"):
                        st.write(", ".join(p['municipios_atendidos']))
                        st.write(territorio['fonte_concessao'])
                        st.write(territorio['fonte_nomes'])
                        if territorio.get('origem_nomes'):
                            st.caption(territorio['origem_nomes'])
                        if territorio.get('fonte_exclusoes'):
                            st.write(territorio['fonte_exclusoes'])
                for referencia_regional in referencias_regionais_neoenergia(p):
                    st.write(referencia_regional)
                if auditoria_demanda_neoenergia_registrada(p):
                    registro_demanda_bloco = p['regras'][CHAVE_DEMANDA_NEOENERGIA]
                    st.success("Demanda residencial trifásica disponível para ensaio administrativo isolado.")
                    consolidacao_bloco = p['regras'].get(CHAVE_CONSOLIDACAO_NEOENERGIA)
                    with st.expander("Consolidar rodada de ensaios administrativos Neoenergia"):
                        if consolidacao_bloco:
                            st.write({"Responsável":consolidacao_bloco.get('responsavel'),"Data UTC":consolidacao_bloco.get('registrado_em'),"Versão ensaiada":consolidacao_bloco.get('versao_ensaiada')})
                            for caso_consolidado in consolidacao_bloco.get('casos_confirmados',[]):st.caption(caso_consolidado)
                            for limite_consolidado in consolidacao_bloco.get('limites',[]):st.caption(limite_consolidado)
                        else:
                            st.caption("Registra a confirmação dos ensaios fictícios 19,500 kVA, bloqueios por cargas excluídas e quantidade inconsistente, T6/32 A em 380/220 V e bloqueio em 33 A com recuperação em 31 A. Confirme apenas no perfil em que esses testes foram executados.")
                            confirmar_rodada_bloco = st.checkbox("Executei e conferi estes ensaios neste perfil, sem aprovação técnica de instalação ou teste com projeto real.",key=f"confirmar_rodada_neo_{p.get('id')}")
                            if st.button("Consolidar ensaios observados neste perfil",disabled=not confirmar_rodada_bloco,key=f"consolidar_rodada_neo_{p.get('id')}"):
                                try:
                                    regras_consolidadas_bloco = consolidar_ensaio_neoenergia(p,email,confirmar_rodada_bloco)
                                    salvar_perfil({'regras':regras_consolidadas_bloco},perfil_id=p.get('id'))
                                    st.rerun()
                                except Exception as exc:st.error(f"Não foi possível consolidar: {exc}")
                    with st.expander("Ensaio isolado de demanda — Neoenergia"):
                        import pandas as pd
                        for restricao_demanda in registro_demanda_bloco['referencia']['restricoes']:
                            st.caption(restricao_demanda)
                        st.info("Os valores iniciais são fictícios: resultado esperado de 19,500 kVA. Esta tabela não lê nem altera o projeto aberto.")
                        st.caption("Informe a potência TOTAL de cada grupo, e não a potência por aparelho. Grupo f: total em VA; demais grupos: total em W. Grupo ausente: quantidade e potência iguais a zero.")
                        dados_demanda_bloco = st.data_editor(pd.DataFrame(dados_ensaio_demanda_neoenergia()),
                            disabled=['Grupo','Descrição','Unidade'], num_rows='fixed',hide_index=True,use_container_width=True,
                            key=f"editor_demanda_neo_{p.get('id')}")
                        fp_d_bloco = st.number_input("FP do grupo d — norma 0,92 ou fabricante",min_value=0.0,max_value=1.0,value=0.92,step=0.01,key=f"fp_d_demanda_neo_{p.get('id')}")
                        excluidas_demanda_bloco = st.checkbox("Há fogões, motores, soldas, cargas especiais, recarga veicular, climatização central, vestiários ou uso coletivo/comercial.",key=f"excluidas_demanda_neo_{p.get('id')}")
                        confirma_demanda_bloco = st.checkbox("Confirmo ensaio residencial individual trifásico; conferi cargas mínimas do item 6.25.7, classificação, quantidades e potências elétricas dos sete grupos, com dados de placa/catálogo quando aplicáveis.",key=f"confirma_demanda_neo_{p.get('id')}")
                        if st.button("Calcular ensaio isolado de demanda",key=f"calcular_demanda_neo_{p.get('id')}"):
                            resultado_demanda_bloco = calcular_ensaio_demanda_neoenergia(p,dados_demanda_bloco.to_dict('records'),fp_d_bloco,confirma_demanda_bloco,excluidas_demanda_bloco)
                            st.write(resultado_demanda_bloco['motivo'])
                            if resultado_demanda_bloco['demanda_total_kva'] is not None:
                                st.write(f"Demanda do ensaio: {resultado_demanda_bloco['demanda_total_kva']:.3f} kVA")
                                st.dataframe(resultado_demanda_bloco['memoria'],hide_index=True,use_container_width=True)
                    with st.expander("Ensaio integrado — demanda e entrada Neoenergia"):
                        st.caption("Usa a tabela editável do ensaio de demanda acima e recalcula os dados atuais a cada clique. Somente auditoria; não lê nem modifica o projeto aberto.")
                        st.info("Teste fictício inicial: escolha 380/220 V, FP do ar 0,90 e corrente máxima 31 A. Esperado: 26,420 kW instalados, 19,500 kVA, categoria T6 e disjuntor de referência 32 A. Os cabos exibidos são da entrada subterrânea Cu XLPE/HEPR, não do alimentador do QDC.")
                        tensoes_integracao_bloco = sorted({r['tensao_ff_fn'] for r in tabela_entrada_neoenergia(p)})
                        tensao_integracao_bloco = st.selectbox("Tensão FF/FN do ensaio integrado",tensoes_integracao_bloco,index=tensoes_integracao_bloco.index('380/220 V'),key=f"tensao_integracao_neo_{p.get('id')}")
                        fp_f_integracao_bloco = st.number_input("FP do ar condicionado — placa/catálogo (0,90 apenas no exemplo fictício)",min_value=0.0,max_value=1.0,value=0.9,step=0.01,key=f"fp_f_integracao_neo_{p.get('id')}")
                        corrente_integracao_bloco = st.number_input("Maior corrente de fase conferida (A) — 31 A apenas no exemplo fictício",min_value=0.0,value=31.0,format="%.3f",key=f"corrente_integracao_neo_{p.get('id')}")
                        confirma_entrada_bloco = st.checkbox("Confirmo a tensão FF/FN, o FP elétrico do ar e a maior corrente de fase deste ensaio; a corrente média balanceada não substitui as correntes de fase.",key=f"confirma_integracao_neo_{p.get('id')}")
                        st.caption("Também são respeitadas a confirmação do escopo e a marcação de cargas excluídas no ensaio de demanda acima.")
                        if st.button("Calcular ensaio integrado de demanda e entrada",key=f"calcular_integracao_neo_{p.get('id')}"):
                            integrado_bloco = calcular_ensaio_integrado_neoenergia(p,dados_demanda_bloco.to_dict('records'),tensao_integracao_bloco,
                                fp_d_bloco,fp_f_integracao_bloco,corrente_integracao_bloco,confirma_demanda_bloco,excluidas_demanda_bloco,confirma_entrada_bloco)
                            st.write(integrado_bloco['motivo'])
                            if integrado_bloco['referencia'] is not None:
                                st.write({"Carga instalada (kW)":integrado_bloco['carga_instalada_kw'],"Demanda (kVA)":integrado_bloco['demanda_total_kva'],
                                    "Corrente equivalente balanceada (A)":integrado_bloco['corrente_equivalente_balanceada_a'],"Maior corrente informada (A)":integrado_bloco['corrente_max_informada_a']})
                                st.write(integrado_bloco['referencia'])
                    with st.expander("Conferir cargas do projeto selecionado — ensaio Neoenergia"):
                        nome_projeto_bloco = str(st.session_state.get('projeto_ativo') or '')
                        tabela_projeto_bloco = st.session_state.get(f"fase8_16_{nome_projeto_bloco}_tabela_editada")
                        if not nome_projeto_bloco or nome_projeto_bloco=='Selecione um projeto...':
                            st.info("Selecione um projeto na barra lateral. Abra Cargas com a Administração desligada e depois retorne aqui.")
                        elif not isinstance(tabela_projeto_bloco,list) or not tabela_projeto_bloco:
                            st.info("Abra a etapa Cargas deste projeto com a Administração desligada e depois retorne. Nenhum dado foi carregado de outro projeto.")
                        else:
                            import hashlib
                            contexto_projeto_bloco = hashlib.sha256(json.dumps([nome_projeto_bloco,tabela_projeto_bloco],sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()[:16]
                            chave_preparacao_bloco = f"projeto_neo_{p.get('id')}_{contexto_projeto_bloco}"
                            try:
                                copia_projeto_bloco = preparar_cargas_projeto_neoenergia(tabela_projeto_bloco)
                                st.write("**Projeto selecionado:** " + nome_projeto_bloco)
                                st.caption("Origem: tabela de cargas da sessão deste projeto, incluindo alterações ainda não salvas. Abaixo é uma cópia: nada será gravado no projeto. Mudanças na origem reiniciam esta conferência.")
                                st.caption("Classifique: a iluminação/TUG; b chuveiros/torneiras/passagem/ferros; c boiler; d secadoras/lavadoras/lava-louças/micro-ondas; e somente forno; f ar condicionado individual; i bombas/hidromassagem. Ausente exige quantidade e potência zero. Pendente ou Fora do escopo bloqueia o ensaio.")
                                st.caption("VA legados são uma previsão anterior, preservada apenas para rastreabilidade; não são a potência aparente atual nem servem para deduzir FP. Os totais atuais em W vêm da etapa Cargas; confira a potência ativa TOTAL em W. Para d, informe FP 0,92 normativo ou fabricante; para f, FP de placa/catálogo. TUEs não são classificadas automaticamente.")
                                df_preparacao_bloco = pd.DataFrame(copia_projeto_bloco)
                                for coluna_preparacao in ['Quantidade conferida','Potência total conferida (W)','FP para grupos d/f']:
                                    df_preparacao_bloco[coluna_preparacao]=pd.to_numeric(df_preparacao_bloco[coluna_preparacao],errors='coerce')
                                conferidas_projeto_bloco = st.data_editor(df_preparacao_bloco,
                                    disabled=['ID','Ambiente','Tipo','Equipamento','Quantidade original','Previsão legada (VA)','Total original (W)'],
                                    column_config={'Grupo':st.column_config.SelectboxColumn('Grupo',options=['Pendente','Ausente','a','b','c','d','e','f','i','Fora do escopo'])},
                                    num_rows='fixed',hide_index=True,use_container_width=True,key=chave_preparacao_bloco+'_cargas')
                                tensao_projeto_teste_bloco = st.selectbox("Tensão FF/FN conferida para este projeto",tensoes_integracao_bloco,index=tensoes_integracao_bloco.index('380/220 V'),key=chave_preparacao_bloco+'_tensao')
                                corrente_projeto_teste_bloco = st.number_input("Maior corrente de fase deste projeto, previamente conferida (A)",min_value=0.0,value=0.0,format="%.3f",key=chave_preparacao_bloco+'_corrente')
                                excluidas_projeto_bloco = st.checkbox("Este projeto contém fogões, motores, soldas, cargas especiais, recarga, climatização central, vestiários ou uso coletivo/comercial.",key=chave_preparacao_bloco+'_excluidas')
                                confirmar_projeto_bloco = st.checkbox("Conferi todas as linhas, cargas mínimas e dados elétricos; confirmo escopo residencial individual trifásico, tensão e maior corrente de fase. Este é um ensaio administrativo sem aprovação de instalação.",key=chave_preparacao_bloco+'_confirmar')
                                if st.button("Conferir demanda e entrada com estas cargas",key=chave_preparacao_bloco+'_calcular'):
                                    agrupado_projeto_bloco=agrupar_cargas_projeto_neoenergia(tabela_projeto_bloco,conferidas_projeto_bloco.to_dict('records'))
                                    if agrupado_projeto_bloco['linhas'] is None:st.warning(agrupado_projeto_bloco['motivo'])
                                    else:
                                        teste_projeto_bloco=calcular_ensaio_integrado_neoenergia(p,agrupado_projeto_bloco['linhas'],tensao_projeto_teste_bloco,
                                            agrupado_projeto_bloco['fp_d'],agrupado_projeto_bloco['fp_f'],corrente_projeto_teste_bloco,confirmar_projeto_bloco,excluidas_projeto_bloco,confirmar_projeto_bloco)
                                        st.write(teste_projeto_bloco['motivo'])
                                        if teste_projeto_bloco['referencia'] is not None:
                                            st.write({"Projeto":nome_projeto_bloco,"Carga instalada (kW)":teste_projeto_bloco['carga_instalada_kw'],"Demanda (kVA)":teste_projeto_bloco['demanda_total_kva'],"Maior corrente informada (A)":teste_projeto_bloco['corrente_max_informada_a']})
                                            st.write(teste_projeto_bloco['referencia'])
                            except ValueError as exc:st.warning(str(exc))
                if auditoria_entrada_neoenergia_registrada(p):
                    registro_entrada_bloco = p['regras'][CHAVE_ENTRADA_NEOENERGIA]
                    referencia_entrada_bloco = registro_entrada_bloco['referencia']
                    st.success("Referências regionais de entrada registradas. Perfil mantido em RASCUNHO.")
                    st.caption("Responsável: " + registro_entrada_bloco['responsavel'] + " · Data UTC: " + registro_entrada_bloco['registrado_em'])
                    with st.expander("Tabela de referência de entrada e limites da auditoria"):
                        st.dataframe(referencia_entrada_bloco['entrada'], hide_index=True, use_container_width=True)
                        for limite_bloco in referencia_entrada_bloco['limites']:
                            st.caption(limite_bloco)
                        st.write("**Demanda — mapeamento documental, cálculo ainda pendente:**")
                        for nota_demanda_bloco in referencia_entrada_bloco['demanda_documental']:
                            st.caption(nota_demanda_bloco)
                    with st.expander("Consultar entrada — ensaio isolado Neoenergia"):
                        tensoes_bloco = sorted({r['tensao_ff_fn'] for r in referencia_entrada_bloco['entrada']})
                        tensao_bloco = st.selectbox("Tensão FF/FN da consulta", tensoes_bloco, key=f"tensao_entrada_neo_{p.get('id')}")
                        modalidade_bloco = st.selectbox("Modalidade da consulta", ['Monofásico','Bifásico','Trifásico'], key=f"modo_entrada_neo_{p.get('id')}")
                        carga_bloco = st.number_input("Carga instalada da consulta (kW)", min_value=0.0, value=20.0, format="%.3f", key=f"carga_entrada_neo_{p.get('id')}")
                        demanda_bloco = None
                        if modalidade_bloco == 'Trifásico':
                            demanda_bloco = st.number_input("Demanda previamente calculada (kVA)", min_value=0.0, value=20.0, format="%.3f", key=f"demanda_entrada_neo_{p.get('id')}")
                        if st.button("Consultar referência de entrada Neoenergia", key=f"consultar_entrada_neo_{p.get('id')}"):
                            resultado_entrada_bloco = consultar_entrada_neoenergia(p,tensao_bloco,modalidade_bloco,carga_bloco,demanda_bloco)
                            st.write(resultado_entrada_bloco['motivo'])
                            if resultado_entrada_bloco.get('referencia'):
                                st.write(resultado_entrada_bloco['referencia'])
                for pendencia_bloco in pendencias_bloco_neoenergia(p):
                    st.warning(pendencia_bloco)
                st.caption("Este rascunho não aparece para usuários e não aplica regras da Elektro ou da CPFL. As referências de entrada são isoladas; a demanda, cargas especiais e a integração ainda precisam de auditoria elétrica.")
                continue
            if perfil_enel_sp(p):
                st.info("Auditorias de cadastro, entrada, motores e integração declaratória têm escopos distintos. O registro dos ensaios administrativos não ativa o perfil nem aprova a entrada.")
                st.write("**Municípios vinculados:** " + ", ".join(p.get("municipios_atendidos") or []))
                st.write((p.get("regras") or {}).get("observacoes", ""))
                if st.button("Conferir cadastro Enel SP", key=f"auditar_enel_{p.get('id')}"):
                    testes_enel = auditar_cadastro_enel_sp(p)
                    st.dataframe(testes_enel, hide_index=True, use_container_width=True)
                    passou = sum(t["Resultado"] == "PASSOU" for t in testes_enel)
                    st.write(f"Cadastro: {passou}/{len(testes_enel)} verificações. Sem aprovação de cálculo ou entrada.")
                for pendencia in pendencias_ativacao_enel_sp(p):
                    st.caption(pendencia)
                st.markdown("#### Auditoria elétrica Enel SP — rede aérea estrela 127/220 V")
                if st.button("Registrar auditoria de modalidades e Anexo B", key=f"registrar_entrada_enel_{p.get('id')}"):
                    try:
                        if p.get("status") != "RASCUNHO":
                            raise ValueError("O registro desta auditoria inicial exige perfil em RASCUNHO.")
                        salvar_perfil({"regras": registrar_auditoria_entrada_enel_sp(p)}, perfil_id=p.get("id"))
                        st.success("Auditoria de entrada registrada. Perfil mantido em RASCUNHO.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível registrar a auditoria: {exc}")
                if (p.get("regras") or {}).get(CHAVE_AUDITORIA) == registro_entrada_enel_sp():
                    registro_enel = registro_entrada_enel_sp()
                    st.write("**Referências:** " + "; ".join(registro_enel["referencias"]))
                    st.dataframe(registro_enel["entrada"], hide_index=True, use_container_width=True)
                    for restricao in registro_enel["restricoes"]:
                        st.caption(restricao)
                    if st.button("Executar testes elétricos isolados Enel SP", key=f"testar_entrada_enel_{p.get('id')}"):
                        casos_enel = testar_entrada_enel_sp()
                        st.dataframe(casos_enel, hide_index=True, use_container_width=True)
                        aprovados = sum(t["Resultado"] == "PASSOU" for t in casos_enel)
                        st.write(f"Prévia isolada: {aprovados}/{len(casos_enel)} testes. Demanda e aprovação da entrada não incluídas.")
                    with st.expander("Consultar prévia isolada de entrada Enel SP"):
                        st.caption("Somente residencial urbano, estrela 127/220 V, rede aérea, sem cargas especiais. Corrente de demanda previamente determinada pelo responsável técnico. Esta consulta não modifica o projeto aberto.")
                        carga_enel = st.number_input("Carga instalada (kW)", min_value=0.0, value=19.798, format="%.3f", key=f"carga_aud_enel_{p.get('id')}")
                        corrente_enel = st.number_input("Corrente de demanda informada (A)", min_value=0.0, value=27.6, key=f"corrente_aud_enel_{p.get('id')}")
                        if st.button("Consultar referência Enel", key=f"consultar_aud_enel_{p.get('id')}"):
                            resultado_enel = previa_entrada_enel_sp(carga_enel, corrente_enel)
                            st.write(resultado_enel["motivo"])
                            if resultado_enel.get("referencia"):
                                st.write(resultado_enel["referencia"])
                st.markdown("#### Auditoria de motores Enel SP — Tabela 11")
                if st.button("Registrar auditoria de motores Enel SP", key=f"registrar_motores_enel_{p.get('id')}"):
                    try:
                        if p.get("status") != "RASCUNHO":
                            raise ValueError("Esta auditoria inicial exige perfil em RASCUNHO.")
                        salvar_perfil({"regras": registrar_auditoria_motores_enel_sp(p)}, perfil_id=p.get("id"))
                        st.success("Referências de motores registradas; perfil mantido em RASCUNHO.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível registrar: {exc}")
                if (p.get("regras") or {}).get(CHAVE_MOTORES) == registro_motores_enel_sp():
                    registro_motor = registro_motores_enel_sp()
                    st.write("**Referências:** " + "; ".join(registro_motor["referencias"]))
                    st.dataframe(registro_motor["tabela"], hide_index=True, use_container_width=True)
                    for nota in registro_motor["restricoes"]:
                        st.caption(nota)
                    if st.button("Executar testes de motores Enel SP", key=f"testar_motores_enel_{p.get('id')}"):
                        testes_motor = testar_motores_enel_sp()
                        st.dataframe(testes_motor, hide_index=True, use_container_width=True)
                        passou_motor = sum(t["Resultado"] == "PASSOU" for t in testes_motor)
                        st.write(f"Motores: {passou_motor}/{len(testes_motor)} testes isolados. Sem aprovação do padrão de entrada.")
                    with st.expander("Consultar motor — estrela 127/220 V, rede aérea"):
                        st.caption("Um motor ou grupo de motores idênticos. Grupos diferentes e delta exigem análise específica. Nenhum dado do projeto é alterado por esta consulta.")
                        categoria_motor = st.selectbox("Categoria de entrada", [r["categoria"] for r in registro_motor["tabela"] if r["sistema"] == "Estrela"], key=f"cat_motor_enel_{p.get('id')}")
                        potencia_motor = st.number_input("Potência nominal de cada motor (cv)", min_value=0.0, value=1.0, step=0.1, key=f"cv_motor_enel_{p.get('id')}")
                        ligacao_motor = st.selectbox("Ligação do motor", ["FN", "FF", "FFF"], key=f"lig_motor_enel_{p.get('id')}")
                        partida_motor = st.selectbox("Partida", ["Não informada", "Direta", "Redução de corrente"], key=f"part_motor_enel_{p.get('id')}")
                        quantidade_motor = st.number_input("Quantidade de motores idênticos", min_value=1, value=1, step=1, key=f"qtd_motor_enel_{p.get('id')}")
                        simult_motor = st.selectbox("Partidas simultâneas no grupo", ["Não confirmado", "Sim", "Não"], key=f"sim_motor_enel_{p.get('id')}")
                        reducao_motor = st.checkbox("Dispositivo de redução de partida tecnicamente conferido", key=f"red_motor_enel_{p.get('id')}")
                        protecao_motor = st.checkbox("Proteções e condições de comando do item 7.4.4 tecnicamente conferidas", key=f"prot_motor_enel_{p.get('id')}")
                        if st.button("Conferir motor", key=f"consulta_motor_enel_{p.get('id')}"):
                            resultado_motor = consultar_motor_enel_sp(categoria_motor, potencia_motor, ligacao_motor, partida_motor, quantidade=quantidade_motor, partida_simultanea={"Sim":True,"Não":False}.get(simult_motor), reducao_confirmada=reducao_motor, protecoes_confirmadas=protecao_motor)
                            st.write(resultado_motor["motivo"])
                            st.write({"Limite da Tabela 11 (cv)":resultado_motor["limite_cv"], "Potência verificada (cv)":resultado_motor["potencia_verificada_cv"]})
                st.markdown("#### Consolidação dos testes integrados — demanda declarada")
                from normativo_enel import CHAVE_INTEGRACAO, CASOS_INTEGRACAO, consolidar_integracao_enel_sp
                st.dataframe([{"Teste": codigo, "Resultado observado": texto} for codigo, texto in CASOS_INTEGRACAO], hide_index=True, use_container_width=True)
                st.caption("Rodada 13.6.335: ensaio fictício bifásico em Barueri/SP. Registro por confirmação administrativa; não executa os testes novamente.")
                consolidado = (p.get("regras") or {}).get(CHAVE_INTEGRACAO)
                if consolidado:
                    st.success("Rodada de testes integrados registrada. Status atual: " + str(p.get("status", "RASCUNHO")))
                    st.write({"Versão ensaiada": consolidado.get("versao_ensaiada"), "Registrado por": consolidado.get("registrado_por"), "Data UTC": consolidado.get("registrado_em")})
                    for limite in consolidado.get("limites", []):
                        st.caption(limite)
                else:
                    confirma_integracao = st.checkbox("Confirmo os resultados acima e seus limites de ensaio administrativo, sem aprovação técnica da entrada.", key=f"confirma_integracao_enel_{p.get('id')}")
                    if st.button("Consolidar testes integrados Enel SP", disabled=not confirma_integracao, key=f"consolidar_integracao_enel_{p.get('id')}"):
                        try:
                            regras_consolidadas = consolidar_integracao_enel_sp(p, email, confirma_integracao)
                            salvar_perfil({"regras": regras_consolidadas}, perfil_id=p.get("id"))
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Não foi possível consolidar: {exc}")
                st.markdown("#### Preparação inicial — piloto Barueri/SP")
                from normativo_enel import ESCOPO_PUBLICACAO, preparar_publicacao_enel_sp, publicacao_enel_registrada, testar_publicacao_enel_sp
                st.write(ESCOPO_PUBLICACAO)
                st.caption("A preparação inicial libera somente Barueri. A ampliação territorial pode ser registrada abaixo, preservando as restrições elétricas. Não é homologação da distribuidora.")
                if st.button("Executar testes de publicação restrita", key=f"testar_pub_enel_{p.get('id')}"):
                    testes_publicacao = testar_publicacao_enel_sp()
                    st.dataframe(testes_publicacao, hide_index=True, use_container_width=True)
                    st.write(f"Software: {sum(t['Resultado'] == 'PASSOU' for t in testes_publicacao)}/{len(testes_publicacao)} casos. Não substitui validação técnica.")
                if p.get("status") == "RASCUNHO":
                    fonte_publicacao = st.checkbox("Conferi no documento oficial a revisão 02, vigência 06/03/2025 e as referências deste escopo declaratório.", key=f"fonte_pub_enel_{p.get('id')}")
                    if st.button("Preparar publicação declaratória restrita", disabled=not fonte_publicacao, key=f"preparar_pub_enel_{p.get('id')}"):
                        try:
                            regras_publicacao = preparar_publicacao_enel_sp(p, email, fonte_publicacao)
                            salvar_perfil({"regras": regras_publicacao}, perfil_id=p.get("id"))
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Publicação não preparada: {exc}")
                if publicacao_enel_registrada(p):
                    st.success("Preparação registrada para o fluxo declaratório restrito. Estimativa automática permanece bloqueada.")
                    destino_enel = "VALIDADO" if p.get("status") == "RASCUNHO" else ("ATIVO" if p.get("status") == "VALIDADO" else None)
                    if destino_enel and st.button("Marcar como " + destino_enel + " — fluxo restrito", key=f"status_pub_enel_{p.get('id')}"):
                        try:
                            atualizar_status(p.get("id"), destino_enel, validado_por=email)
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Não foi possível alterar o status: {exc}")
                    if p.get("status") in ("VALIDADO", "ATIVO") and st.button("Retornar a RASCUNHO", key=f"rascunho_pub_enel_{p.get('id')}"):
                        atualizar_status(p.get("id"), "RASCUNHO", validado_por=email)
                        st.rerun()
                if p.get("status") == "ATIVO" and not pendencias_ativacao_enel_sp(p):
                    st.markdown("#### Ampliação territorial — fluxo declaratório")
                    from normativo_enel import MUNICIPIOS_ENEL_SP, FONTE_MUNICIPIOS, CHAVE_TERRITORIO as CHAVE_TERRITORIO_ENEL, municipios_publicados_enel_sp, registrar_territorio_enel_sp, testar_territorio_enel_sp
                    st.write("Municípios atualmente liberados: " + ", ".join(municipios_publicados_enel_sp(p)))
                    st.markdown("Fonte territorial: " + FONTE_MUNICIPIOS)
                    st.caption("Escolha as cidades a liberar. Confirme a tensão e a rede de cada instalação; a cidade não determina automaticamente a tensão. Os testes abaixo verificam o software, não instalações reais em cada município.")
                    opcoes_territorio = [n for n in MUNICIPIOS_ENEL_SP if n in (p.get("municipios_atendidos") or [])]
                    cidades_territorio = st.multiselect("Municípios para o fluxo declaratório restrito", opcoes_territorio, default=opcoes_territorio, key=f"cidades_territorio_enel_{p.get('id')}")
                    if st.button("Executar testes territoriais Enel SP", key=f"testes_territorio_enel_{p.get('id')}"):
                        testes_territorio = testar_territorio_enel_sp()
                        st.dataframe(testes_territorio, hide_index=True, use_container_width=True)
                        st.write(f"Software: {sum(t['Resultado']=='PASSOU' for t in testes_territorio)}/{len(testes_territorio)} casos territoriais.")
                    confirma_territorio = st.checkbox("Conferi os municípios na fonte oficial e confirmo a ampliação apenas territorial, mantendo as restrições elétricas do fluxo declaratório.", key=f"confirmar_territorio_enel_{p.get('id')}")
                    if st.button("Registrar municípios liberados Enel SP", disabled=not confirma_territorio, key=f"registrar_territorio_enel_{p.get('id')}"):
                        try:
                            regras_territorio = registrar_territorio_enel_sp(p, cidades_territorio, email, confirma_territorio)
                            salvar_perfil({"regras": regras_territorio}, perfil_id=p.get("id"))
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Ampliação territorial não registrada: {exc}")
                    registro_territorio = (p.get("regras") or {}).get(CHAVE_TERRITORIO_ENEL)
                    if registro_territorio:
                        st.write({"Registrado por":registro_territorio.get("registrado_por"), "Data UTC":registro_territorio.get("registrado_em")})
                # Evita apresentar o editor genérico de fatores como regras Enel.
                continue
            if eh_perfil_elektro(p):
                st.info("Fornecimento 220/127 V preparado por faixas sem conflito. "
                        "Cargas acima de 10 e abaixo de 11,1 kW, e acima de 13 até 18 kW, "
                        "exigem conferência técnica, sem arredondamento automático. "
                        "A prévia de demanda trifásica já está disponível para auditoria, "
                        "mas ainda não está integrada ao cálculo dos projetos: mantenha RASCUNHO.")
                if auditar_tabelas_demanda(p.get("regras")):
                    st.success("Tabelas 6–16 registradas no rascunho. Prévia isolada disponível para auditoria.")
                    if st.button("Verificar prévia de demanda Elektro", key=f"testar_demanda_elektro_{p.get('id')}"):
                        linhas_auditoria = [
                            {"Qtd Ilum.": 1, "Pot. Unit. Ilum (W)": 2000,
                             "Qtd TUE": 2, "Pot. Unit. TUE (W)": 5500, "Equipamento TUE": "Chuveiro elétrico"},
                            {"Qtd TUE": 2, "Pot. Unit. TUE (W)": 1000,
                             "Equipamento TUE": "Máquina de lavar roupas"},
                        ]
                        previo = calcular_previa(linhas_auditoria, p.get("regras"))
                        esperado = 1.5 + 11 + 1.4 / .92
                        forno = calcular_previa([{"Qtd TUE": 1, "Pot. Unit. TUE (W)": 1000,
                                                 "Equipamento TUE": "Forno elétrico"}], p.get("regras"))
                        fogao = calcular_previa([{"Qtd TUE": 1, "Pot. Unit. TUE (W)": 1000,
                                                 "Equipamento TUE": "Fogão elétrico"}], p.get("regras"))
                        if (previo["status"] == "calculado" and
                                abs(previo["demanda_kva"] - esperado) < 1e-8 and
                                forno["status"] == "calculado" and forno["demanda_kva"] == 1.0 and
                                fogao["status"] == "pendente" and fogao["demanda_kva"] is None):
                            st.success(f"Prévia residencial: {previo['demanda_kva']:.4f} kVA. "
                                       "Forno elétrico pela Tabela 9; fogão elétrico encaminhado "
                                       "à conferência técnica.")
                            st.dataframe(previo["detalhes"], use_container_width=True, hide_index=True)
                        else:
                            st.error("Falha na verificação isolada da demanda Elektro.")
                else:
                    st.caption("Tabelas 6–16 da demanda ainda não preparadas neste rascunho.")
                if str(p.get("status") or "").upper() == "RASCUNHO":
                    if st.button("Preparar faixas Elektro e excluir São João da Boa Vista", key=f"preparar_elektro_{p.get('id')}"):
                        try:
                            cidades = list(p.get("municipios_atendidos") or [])
                            if not cidades:
                                raise ValueError("A lista de municípios atendidos está vazia.")
                            if str(p.get("uf") or "").upper() == "SP":
                                cidades = [x for x in cidades if str(x).strip().casefold() != MUNICIPIO_TENSAO_ESPECIAL.casefold()]
                            regras_preparadas = preparar_regras(p.get("regras"))
                            salvar_perfil({"municipios_atendidos": cidades, "regras": regras_preparadas}, perfil_id=p.get("id"))
                            st.success(f"Faixas preparadas; {len(cidades)} municípios vinculados. O perfil permanece RASCUNHO.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Não foi possível preparar o perfil: {e}")
                    if st.button("Registrar tabelas de demanda DIS-NOR-030", key=f"demanda_elektro_{p.get('id')}"):
                        try:
                            regras = preparar_tabelas_demanda(p.get("regras"))
                            if not auditar_tabelas_demanda(regras):
                                raise ValueError("Falha na auditoria das tabelas de demanda.")
                            salvar_perfil({"regras": regras}, perfil_id=p.get("id"))
                            st.success("Tabelas registradas. Perfil permanece RASCUNHO até integração do cálculo.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Não foi possível registrar a demanda: {e}")
            if p.get("municipios_atendidos") is not None:
                st.caption(f"Municípios vinculados: {len(p.get('municipios_atendidos') or [])}")
            with st.form(f"municipios_perfil_{p.get('id')}"):
                opcoes_cidades = municipios_da_uf(p.get("uf") or "")
                atuais = p.get("municipios_atendidos")
                if atuais is None:
                    atuais = [p.get("municipio")] if p.get("municipio") else []
                opcoes_cidades = sorted(set(opcoes_cidades) | set(atuais))
                cidades_editadas = st.multiselect(
                    "Municípios atendidos (vínculo explícito)",
                    opcoes_cidades,
                    default=atuais,
                    key=f"municipios_atendidos_{p.get('id')}",
                    help="Conferir a lista oficial antes de salvar. Uma lista vazia bloqueia este perfil em todos os municípios.",
                )
                if st.form_submit_button("Salvar municípios vinculados"):
                    try:
                        salvar_perfil({"municipios_atendidos": cidades_editadas}, perfil_id=p.get("id"))
                        st.success("Municípios vinculados atualizados.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível salvar os municípios: {e}")
            regras_atual = p.get("regras") or {}
            # Rev.201 — migração/sincronização do perfil GED-13 já existente, incluindo fornecimento.
            # O editor das revisões 192–196 exibia as tabelas canônicas, mas perfis
            # antigos podiam continuar com demanda vazia no Supabase. Aqui a mesma
            # estrutura oficial usada pela interface é materializada e persistida.
            regras_validacao = _regras_base(regras_atual)
            eh_ged13_cpfl = (
                (str(p.get("concessionaria") or "").strip().casefold() == "cpfl piratininga"
                 or perfil_paulista_380(p)
                 or perfil_rge_ged13(p)
                 or perfil_santa_cruz_ged13(p)
                 or (perfil_paulista_ged13(p)
                     and (regras_validacao.get("fornecimento") or {}).get("tensao_fase_neutro_v") == 127
                     and (regras_validacao.get("fornecimento") or {}).get("tensao_fase_fase_v") == 220))
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
            validacao_resumo_ok, _ = _renderizar_resumo_auditoria(regras_validacao, classe_380=perfil_ged13_380(p)) if eh_ged13_cpfl else (False, [])

            with st.form(f"editar_perfil_{p.get('id')}"):
                regras_editadas = _editor_regras(f"edit_{p.get('id')}", regras_atual)
                if st.form_submit_button("Salvar regras deste perfil", use_container_width=True):
                    try:
                        if eh_perfil_elektro(p):
                            # O editor comum pressupõe faixas contíguas e
                            # preencheria indevidamente os dois intervalos bloqueados.
                            regras_editadas["fornecimento"] = (regras_atual.get("fornecimento") or {})
                            regras_editadas["demanda"] = (regras_atual.get("demanda") or {})
                            if "demanda_elektro_auditoria" in regras_atual:
                                regras_editadas["demanda_elektro_auditoria"] = regras_atual["demanda_elektro_auditoria"]
                            if "conferencia_documental_parcial_elektro" in regras_atual:
                                regras_editadas["conferencia_documental_parcial_elektro"] = regras_atual["conferencia_documental_parcial_elektro"]
                            if "validacao_automatica_integracao_elektro" in regras_atual:
                                regras_editadas["validacao_automatica_integracao_elektro"] = regras_atual["validacao_automatica_integracao_elektro"]
                            if CHAVE in regras_atual:
                                regras_editadas[CHAVE] = regras_atual[CHAVE]
                            regras_editadas["fonte_conferida"] = False
                        salvar_perfil({"regras": regras_editadas}, perfil_id=p.get("id"))
                        st.success("Regras salvas.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível atualizar: {e}")

            validacao_ok = _renderizar_validador_ged13(regras_validacao, f"val_{p.get('id')}", classe_380=perfil_ged13_380(p)) if eh_ged13_cpfl else False
            eh_elektro = eh_perfil_elektro(p)
            if eh_elektro:
                from normativo_elektro import resumo_renderizar as renderizar_resumo_elektro
                renderizar_resumo_elektro(p, f"resumo_auditoria_perfil_{p.get('id')}")
                tabelas_ok = auditar_tabelas_demanda(regras_atual)
                from normativo_elektro import validacao_CHAVE as CHAVE_INTEGRACAO, validacao_executar as executar
                from normativo_elektro import auditoria_assinatura as assinatura_testes
                st.markdown("#### Validação automática da demanda integrada")
                st.caption("Executa o motor integrado com cargas fictícias e regras deste perfil. Verifica limites de 13 e 18 kW, dados incompletos, localidade e ausência de liberação de DG. Não homologação normativa.")
                if st.button("Executar e registrar testes da demanda integrada", key=f"testes_integrados_{p.get('id')}"):
                    try:
                        registro_integracao = executar(p, email)
                        novas_regras = dict(regras_atual)
                        novas_regras[CHAVE_INTEGRACAO] = registro_integracao
                        salvar_perfil({"regras": novas_regras}, perfil_id=p.get("id"))
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível executar ou registrar a validação: {e}")
                validacao_integrada = regras_atual.get(CHAVE_INTEGRACAO) or {}
                if validacao_integrada:
                    st.table([{k: ("Passou" if v else "Falhou") if k == "Passou" else ("—" if v is None else v)
                               for k, v in caso.items() if k != "erro"}
                              for caso in validacao_integrada.get("casos", [])])
                    if validacao_integrada.get("assinatura_perfil") != assinatura_testes(p):
                        st.warning("Validação integrada desatualizada: execute novamente após alterações do perfil.")
                    elif validacao_integrada.get("passou"):
                        st.success("Todos os testes automáticos do modo integrado passaram. O perfil continua sem homologação normativa.")
                    else:
                        st.error("A validação integrada possui falhas. Confira as regras antes de avançar.")
                    st.caption(f"Execução: {validacao_integrada.get('data_utc', '—')} · Responsável: {validacao_integrada.get('responsavel', '—')}")
                else:
                    st.info("Validação automática integrada ainda não executada neste perfil.")

                from normativo_elektro import documental_CHAVE as CHAVE_DOCUMENTAL, documental_FONTE as FONTE_DOCUMENTAL, documental_registrar as registrar_documental
                st.markdown("#### Conferência documental parcial Elektro")
                st.markdown(f"[Consultar DIS-NOR-030 Rev. 07 no site oficial]({FONTE_DOCUMENTAL})")
                st.caption("Documento aprovado em 17/04/2026. Confira a identificação na página 1, o item 6.27 nas páginas 47–49 e a Tabela 3 na página 63. A fonte estar disponível não equivale a homologação do projeto.")
                st.info("O item 6.27 descreve demanda de instalações trifásicas. Para candidatos monofásicos ou bifásicos, o valor em kVA do modo de teste é apenas simulação e não dimensiona a entrada. Permanecem as faixas conflitantes bloqueadas.")
                registro_documental = regras_atual.get(CHAVE_DOCUMENTAL) or {}
                if registro_documental:
                    if registro_documental.get("assinatura_perfil") == assinatura_testes(p):
                        st.success("Conferência documental parcial registrada para os dados atuais do perfil.")
                    else:
                        st.warning("Conferência documental parcial desatualizada: confira as alterações do perfil.")
                    st.caption(f"Registro: {registro_documental.get('data_utc', '—')} · Responsável: {registro_documental.get('responsavel', '—')}")
                    if registro_documental.get("notas"):
                        st.write(registro_documental["notas"])
                with st.form(f"conferencia_parcial_elektro_{p.get('id')}"):
                    conf_doc = st.checkbox("Conferi código, revisão e identificação da fonte oficial")
                    conf_escopo = st.checkbox("Conferi o escopo trifásico do item 6.27 e a unidade kVA")
                    conf_entrada = st.checkbox("Conferi as referências da Tabela 3 sem liberar faixas conflitantes")
                    notas_doc = st.text_area("Observações da conferência parcial", value="")
                    if st.form_submit_button("Registrar conferência documental parcial"):
                        try:
                            registro_doc = registrar_documental(p, email, {"documento": conf_doc, "escopo_demanda": conf_escopo, "tabela_entrada": conf_entrada}, notas_doc)
                            novas_regras = dict(regras_atual)
                            novas_regras[CHAVE_DOCUMENTAL] = registro_doc
                            salvar_perfil({"regras": novas_regras}, perfil_id=p.get("id"))
                            st.rerun()
                        except Exception as e:
                            st.error(f"Não foi possível registrar a conferência parcial: {e}")
                st.caption("Este registro não altera a confirmação documental final, VALIDADO ou ATIVO. Alimentador, proteções e atendimento por endereço continuam pendentes.")

                st.markdown("#### Auditoria do enquadramento Elektro")
                st.caption("Evidências dos testes de software em Guarujá/SP, 220/127 V, em 02/10/2026. Não são aprovação técnica nem homologação do perfil.")
                st.table([{"Carga instalada (kW)": f"{kw:.3f}",
                           "Resultado observado": cat or "Bloqueado — conferência técnica",
                           "Modalidade": mod, "Disjuntor da tabela (A)": amp or "—"}
                          for kw, cat, mod, amp in CASOS])
                registro = regras_atual.get(CHAVE) or {}
                if registro_atual(p):
                    st.success("Conferência dos testes registrada para os dados atuais deste perfil.")
                    st.caption(f"Registrado em {registro.get('data_utc', '—')} por {registro.get('registrado_por', '—')}.")
                else:
                    if registro:
                        st.warning("Registro de testes desatualizado: o perfil foi alterado. Confira novamente antes de registrar.")
                    else:
                        st.info("Resultados observados disponíveis; a conferência ainda não foi registrada neste perfil.")
                    st.caption("Registre somente após conferir que as evidências acima correspondem a este perfil. Os testes foram realizados em SP; não comprovam atendimento ou tensão em outros municípios ou UFs.")
                    if st.button("Registrar conferência destes testes de software", key=f"registrar_testes_elektro_{p.get('id')}"):
                        try:
                            regras_registradas = dict(regras_atual)
                            regras_registradas[CHAVE] = registrar(p, email)
                            salvar_perfil({"regras": regras_registradas}, perfil_id=p.get("id"))
                            st.success("Conferência registrada. Perfil continua sem homologação normativa.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Não foi possível registrar os testes: {e}")
                st.markdown("**Verificado nos testes de software**")
                st.write("• Candidata B1 abaixo da faixa conflitante; bloqueio dentro da faixa e em 18 kW; candidata T0 acima da faixa.")
                st.write("• Auditoria do projeto salva e recuperada; aviso de desatualização após alterar cargas e correspondência ao restaurá-las.")
                from normativo_elektro import ativacao_pendencias, ativacao_ESCOPO
                st.markdown("**Ativação operacional Elektro**")
                st.info(ativacao_ESCOPO + ". São João da Boa Vista e faixas conflitantes permanecem fora do enquadramento automático. A publicação não homologa DG ou alimentador.")
                pendencias_ativacao = ativacao_pendencias(p, exigir_fonte=False)
                validacao_ok = not pendencias_ativacao
                for pendencia_ativacao in pendencias_ativacao:
                    st.warning(pendencia_ativacao)
            elif not eh_ged13_cpfl:
                st.info("Auditoria normativa específica ainda não cadastrada para este documento. O perfil permanece em RASCUNHO.")

            # A confirmação humana é deliberadamente a última etapa.
            fonte_conferida = bool(regras_validacao.get("fonte_conferida"))
            st.markdown("#### Conferência documental final")
            if fonte_conferida:
                st.success("Fonte oficial confirmada pelo administrador.")
            elif validacao_ok:
                st.info("Testes e conferência documental do escopo operacional aprovados. Confirme a fonte oficial para publicar o perfil com as restrições indicadas." if eh_elektro else "Todos os testes automáticos passaram. Confira o documento oficial e, somente depois, registre a confirmação abaixo.")
                if st.button("Confirmo a conferência no documento oficial", key=f"confirmar_fonte_{p.get('id')}", use_container_width=True):
                    try:
                        regras_confirmadas = _regras_confirmacao_fonte(p, regras_validacao)
                        salvar_perfil({"regras": regras_confirmadas}, perfil_id=p.get("id"))
                        st.success("Conferência documental registrada.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível registrar a conferência: {e}")
            else:
                st.caption(
                    "Conclua os testes e a conferência documental do escopo operacional Elektro."
                    if eh_elektro else
                    "Confirmação documental bloqueada até 100% dos testes automáticos passarem."
                )

            pronto = _perfil_pronto(regras_validacao) and validacao_ok
            if perfil_paulista_ged13(p):
                pendencias_paulista = pendencias_ativacao_paulista(p)
                pronto = pronto and not pendencias_paulista
                for pendencia in pendencias_paulista:
                    st.caption(pendencia)
            if perfil_santa_cruz_ged13(p):
                pendencias_santa = pendencias_ativacao_santa_cruz(p)
                pronto = pronto and not pendencias_santa
                for pendencia in pendencias_santa:
                    st.caption(pendencia)
            if perfil_rge_ged13(p):
                pendencias_rge = pendencias_ativacao_rge(p)
                pronto = pronto and not pendencias_rge
                for pendencia in pendencias_rge:
                    st.caption(pendencia)
            if not pronto:
                st.info(
                    "Perfil Elektro pendente: conclua as etapas indicadas para liberar a ativação operacional."
                    if eh_elektro else
                    "Perfil ainda incompleto ou com validação pendente: mantenha em RASCUNHO até todos os testes obrigatórios passarem e a fonte oficial estar confirmada."
                )
            cols = st.columns(4)
            for col, status in zip(cols, ["RASCUNHO", "VALIDADO", "ATIVO", "INATIVO"]):
                bloquear = status in ("VALIDADO", "ATIVO") and not pronto
                if col.button(status, key=f"status_{p.get('id')}_{status}", use_container_width=True, disabled=bloquear):
                    try:
                        atualizar_status(p.get("id"), status, email)
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
