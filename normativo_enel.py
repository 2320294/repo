"""Cadastro e auditoria inicial Enel SP. Sem motor automático publicado."""
FONTE_PORTAL = 'https://www.enel.com.br/pt-saopaulo/normas-tecnicas.html'
FONTE_MUNICIPIOS = 'https://www.enel.com.br/pt-saopaulo/cidades-atendidas-pela-enel-distribuicao.html'
FONTE_OFICIAL = 'https://www.eneldistribuicao.com.br/rj/documentos/CNC-OMBR-MAT-24-1569-EDBR%20(GRI-EDBR-CNC-GRI-0017)%20%E2%80%93%20Conex%C3%A3o%20Individual%20BT.pdf'
DOCUMENTO = 'GRI-EDBR-CNC-GRI-0017'
MUNICIPIOS_ENEL_SP = [
    'Barueri', 'Cajamar', 'Carapicuíba', 'Cotia', 'Diadema', 'Embu das Artes',
    'Embu-Guaçu', 'Itapecerica da Serra', 'Itapevi', 'Jandira', 'Juquitiba',
    'Mauá', 'Osasco', 'Pirapora do Bom Jesus', 'Ribeirão Pires',
    'Rio Grande da Serra', 'Santana de Parnaíba', 'Santo André',
    'São Bernardo do Campo', 'São Caetano do Sul', 'São Lourenço da Serra',
    'São Paulo', 'Taboão da Serra', 'Vargem Grande Paulista',
]


def perfil_enel_sp(perfil):
    return str((perfil or {}).get('concessionaria') or '').strip().casefold() == 'enel são paulo'


def enel_sp_atende_localidade(uf, municipio):
    return (str(uf or '').strip().upper() == 'SP'
            and str(municipio or '').strip().casefold() in {n.casefold() for n in MUNICIPIOS_ENEL_SP})


def preparar_rascunho_enel_sp(criado_por=''):
    # Dados documentais próprios, sem herdar fatores de demanda CPFL/Elektro.
    return dict(
        concessionaria='Enel São Paulo', uf='SP', municipio='',
        municipios_atendidos=list(MUNICIPIOS_ENEL_SP), documento=DOCUMENTO,
        revisao='02', vigencia='06/03/2025', fonte_oficial=FONTE_OFICIAL,
        status='RASCUNHO', criado_por=criado_por,
        regras={
            'schema': 'autoeletrica.perfil_normativo.v2',
            'tipo_instalacao': 'Residencial individual',
            'fornecimento': {}, 'demanda': {}, 'fonte_conferida': False,
            'observacoes': (
                'Cadastro documental inicial Enel São Paulo. Norma versão 02 de 06/03/2025; '
                'código de capa GRI-EDBR-CNC-GRI-0017 / CNC-NDBR-DBR-24-1569-EDBR. '
                'O portal conserva o nome CNC-OMBR-MAT-24-1569-EDBR. '
                '24 municípios conforme mapa oficial; Embu normalizado como Embu das Artes. '
                'A área municipal não confirma distribuidora, tensão ou topologia no endereço. '
                'Confirmar sistema estrela ou delta, tensões reais e rede aérea/subterrânea. '
                'Tabela 2, Enel SP: bifásico acima de 12 até 20 kW e trifásico aéreo '
                '127/220 V a partir de 15,1 até 75 kW; sobreposição de modalidades '
                '15,1–20 kW exige análise, sem escolha automática. '
                'Item 7.8.2: demanda sob responsabilidade do responsável técnico. '
                'Metodologia de demanda e tabelas de entrada ainda em auditoria; não ativar. '
                'Fontes: ' + FONTE_PORTAL + ' ; ' + FONTE_MUNICIPIOS
            ),
        },
    )


def pendencias_ativacao_enel_sp(perfil):
    pendencias = ['Concluir a auditoria da metodologia de demanda Enel SP e a integração/testes no projeto antes de publicar.']
    if (perfil.get('regras') or {}).get(CHAVE_AUDITORIA) != registro_entrada_enel_sp():
        pendencias.append('Registrar a auditoria atual das modalidades e do Anexo B.')
    if not (perfil.get('regras') or {}).get('fonte_conferida'):
        pendencias.append('Conferir a fonte oficial versão 02 de 06/03/2025.')
    if (perfil.get('documento') != DOCUMENTO or perfil.get('revisao') != '02'
            or perfil.get('fonte_oficial') != FONTE_OFICIAL):
        pendencias.append('Confirmar documento, revisão e URL atuais do portal oficial.')
    cidades = perfil.get('municipios_atendidos')
    if (not isinstance(cidades, list) or not cidades or
            any(not enel_sp_atende_localidade(perfil.get('uf'), n) for n in cidades)):
        pendencias.append('Restringir a lista aos municípios confirmados da Enel São Paulo.')
    return pendencias


def auditar_cadastro_enel_sp(perfil):
    cidades = perfil.get('municipios_atendidos') or []
    testes = [{'Verificação': 'Município: ' + n,
               'Resultado': 'PASSOU' if n in cidades and enel_sp_atende_localidade(perfil.get('uf'), n) else 'FALHOU'}
              for n in MUNICIPIOS_ENEL_SP]
    verificacoes = [
        ('24 municípios únicos', len(cidades) == len(set(cidades)) == 24),
        ('Documento atual', perfil.get('documento') == DOCUMENTO),
        ('Revisão 02', perfil.get('revisao') == '02'),
        ('Data 06/03/2025', perfil.get('vigencia') == '06/03/2025'),
        ('Fonte oficial', perfil.get('fonte_oficial') == FONTE_OFICIAL),
        ('UF SP', perfil.get('uf') == 'SP'),
        ('Sem demanda de outra distribuidora', not (perfil.get('regras') or {}).get('demanda')),
        ('Sem modalidade/tensão presumida', not (perfil.get('regras') or {}).get('fornecimento')),
        ('Publicação bloqueada', bool(pendencias_ativacao_enel_sp(perfil))),
    ]
    testes += [{'Verificação': nome, 'Resultado': 'PASSOU' if ok else 'FALHOU'} for nome, ok in verificacoes]
    return testes

# Referências conferidas visualmente no PDF v02: Tabela 1 (p18),
# Tabela 2 (p21–22), Anexo B (p75–76). Ramal de entrada ≠ alimentador do QDC.
CHAVE_AUDITORIA = 'auditoria_enel_sp_entrada_v1'
REFERENCIAS_ENTRADA = [
    ('A1', 50, 10, 10), ('A2', 63, 16, 16),
    ('B3', 50, 10, 10), ('B4', 63, 16, 16), ('B5', 80, 25, 16),
    ('B6', 100, 35, 16), ('B7', 125, 50, 25), ('B8', 160, 70, 35),
    ('B9', 200, 95, 50), ('B10', 225, 120, 70), ('B11', 275, 150, 95), ('B12', 300, 185, 95),
    ('C3', 50, 10, 10), ('C4', 63, 16, 16), ('C5', 80, 25, 16),
    ('C6', 100, 35, 16), ('C7', 125, 50, 25), ('C8', 160, 70, 35),
    ('C9', 200, 95, 50), ('C10', 225, 120, 70), ('C11', 275, 150, 95), ('C12', 300, 185, 95),
]


def registro_entrada_enel_sp():
    return {
        'documento': DOCUMENTO, 'revisao': '02', 'fonte': FONTE_OFICIAL,
        'referencias': ['Tabela 1 — p.18', 'Tabela 2 — p.21–22', 'Anexo B — p.75–76', 'Item 7.8.2 — p.35–36'],
        'escopo': 'Prévia isolada: residencial individual urbano, rede aérea, estrela 127/220 V',
        'entrada': [dict(categoria=n, disjuntor_referencia_a=a,
                         ramal_entrada_cobre_mm2=s, aterramento_cobre_mm2=t)
                    for n, a, s, t in REFERENCIAS_ENTRADA],
        'restricoes': [
            '15,1 ≤ carga instalada ≤ 20 kW: modalidades B/C sobrepostas; conferência técnica.',
            'Delta 120/240 V, rede subterrânea, rural e cargas especiais fora da prévia.',
            'Corrente de demanda deve ser informada pelo responsável técnico; não é calculada nesta prévia.',
            'Valores do ramal de entrada e aterramento são referências mínimas; não dimensionam o alimentador do QDC.',
            'Sem aprovação automática do padrão de entrada, proteção ou ligação.',
            'IT 263 v01 de 02/03/2018: escopo Distribuição Rio; não aplicada em São Paulo.',
        ],
    }


def registrar_auditoria_entrada_enel_sp(perfil):
    from copy import deepcopy
    regras = deepcopy(perfil.get('regras') or {})
    regras[CHAVE_AUDITORIA] = registro_entrada_enel_sp()
    regras['observacoes'] = str(regras.get('observacoes') or '').replace(
        'Tabela 2, Enel SP:', 'Tabela 2, Enel SP:')
    return regras


def previa_entrada_enel_sp(carga_kw, corrente_demanda_a, uf='SP', municipio='São Paulo',
                          sistema='Estrela', fn=127, ff=220, rede='Aérea',
                          zona='Urbana', cargas_especiais=False):
    """Consulta isolada de referência; não altera o cálculo de nenhum projeto."""
    import math
    saida = dict(status='pendente', modalidades=[], categoria=None,
                 aprovacao_automatica=False, demanda_calculada=False)
    if not enel_sp_atende_localidade(uf, municipio):
        return dict(saida, motivo='Localidade fora do escopo Enel SP.')
    if (sistema != 'Estrela' or fn != 127 or ff != 220 or rede != 'Aérea'
            or zona != 'Urbana' or cargas_especiais is not False):
        return dict(saida, motivo='Condições fora da prévia residencial urbana aérea estrela 127/220 V.')
    try:
        if isinstance(carga_kw, bool) or isinstance(corrente_demanda_a, bool):
            raise ValueError()
        carga, corrente = float(carga_kw), float(corrente_demanda_a)
        if not math.isfinite(carga) or not math.isfinite(corrente) or carga <= 0 or corrente <= 0:
            raise ValueError()
    except (TypeError, ValueError, OverflowError):
        return dict(saida, motivo='Informe carga instalada e corrente de demanda positivas e finitas.')
    if carga > 75:
        return dict(saida, motivo='Carga instalada acima do limite de 75 kW desta prévia.')
    modalidades = []
    if carga <= 12:
        modalidades.append('A')
    if 12 < carga <= 20:
        modalidades.append('B')
    if 15.1 <= carga <= 75:
        modalidades.append('C')
    saida['modalidades'] = modalidades
    if len(modalidades) != 1:
        return dict(saida, motivo='Sobreposição B/C entre 15,1 e 20 kW: conferência técnica, sem escolha automática.')
    candidatas = [r for r in registro_entrada_enel_sp()['entrada']
                  if r['categoria'].startswith(modalidades[0]) and corrente <= r['disjuntor_referencia_a']]
    if not candidatas:
        return dict(saida, motivo='Corrente informada excede as categorias da modalidade; conferir tecnicamente.')
    ref = candidatas[0]
    return dict(saida, status='referencia', categoria=ref['categoria'], referencia=ref,
                motivo='Referência isolada do Anexo B. Exige verificação das notas, motores, capacidade dos condutores e condições reais; não aprova o padrão de entrada.')


def testar_entrada_enel_sp():
    casos = [
        ('12 kW / 50 A', (12, 50), {}, 'referencia', 'A1'),
        ('12 kW / 50,001 A', (12, 50.001), {}, 'referencia', 'A2'),
        ('12 kW / 63 A', (12, 63), {}, 'referencia', 'A2'),
        ('12 kW / 63,001 A', (12, 63.001), {}, 'pendente', None),
        ('12,001 kW', (12.001, 50), {}, 'referencia', 'B3'),
        ('15,099 kW', (15.099, 63), {}, 'referencia', 'B4'),
        ('15,1 kW: início sobreposição', (15.1, 50), {}, 'pendente', None),
        ('19,798 kW', (19.798, 27.6), {}, 'pendente', None),
        ('20 kW: fim sobreposição', (20, 50), {}, 'pendente', None),
        ('20,001 kW', (20.001, 50), {}, 'referencia', 'C3'),
        ('75 kW', (75, 200), {}, 'referencia', 'C9'),
        ('75,001 kW', (75.001, 200), {}, 'pendente', None),
        ('Delta bloqueado', (25, 50), {'sistema':'Delta'}, 'pendente', None),
        ('220/380 V bloqueado', (25, 50), {'fn':220, 'ff':380}, 'pendente', None),
        ('Subterrânea bloqueada', (25, 50), {'rede':'Subterrânea'}, 'pendente', None),
        ('Rural bloqueado', (25, 50), {'zona':'Rural'}, 'pendente', None),
        ('Motor/carga especial', (25, 50), {'cargas_especiais':True}, 'pendente', None),
        ('Cargas especiais desconhecidas', (25, 50), {'cargas_especiais':None}, 'pendente', None),
        ('Município fora da área', (25, 50), {'municipio':'Santos'}, 'pendente', None),
        ('UF fora da área', (25, 50), {'uf':'RJ'}, 'pendente', None),
        ('Sem corrente', (25, None), {}, 'pendente', None),
        ('Sem carga', (None, 50), {}, 'pendente', None),
        ('Carga zero', (0, 50), {}, 'pendente', None),
        ('Corrente negativa', (25, -1), {}, 'pendente', None),
        ('Carga NaN', (float('nan'), 50), {}, 'pendente', None),
        ('Corrente infinita', (25, float('inf')), {}, 'pendente', None),
    ]
    # Limiares das proteções: igualdade pertence à faixa anterior; sem arredondamento.
    for cat, a, _, _ in REFERENCIAS_ENTRADA:
        carga = 10 if cat[0] == 'A' else (14 if cat[0] == 'B' else 25)
        casos.append((f'Anexo B: {cat} em {a} A', (carga, a), {}, 'referencia', cat))
    for a, seguinte in [(50,'C4'),(63,'C5'),(80,'C6'),(100,'C7'),(125,'C8'),(160,'C9'),(200,'C10'),(225,'C11'),(275,'C12'),(300,None)]:
        casos.append((f'Acima de {a} A', (25,a+.001), {}, 'referencia' if seguinte else 'pendente', seguinte))
    testes=[]
    for nome, args, kwargs, status, categoria in casos:
        r=previa_entrada_enel_sp(*args, **kwargs)
        ok=(r['status']==status and r['categoria']==categoria and not r['aprovacao_automatica'] and not r['demanda_calculada'])
        testes.append({'Caso':nome, 'Esperado':categoria or 'Conferência técnica',
                       'Obtido':r['categoria'] or 'Conferência técnica',
                       'Resultado':'PASSOU' if ok else 'FALHOU'})
    return testes
