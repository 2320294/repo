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
    pendencias = pendencias_base_publicacao_enel_sp(perfil)
    if not publicacao_enel_registrada(perfil):
        pendencias.append('Preparar a publicação restrita do fluxo declaratório após conferir a fonte e os testes.')
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

CHAVE_MOTORES = 'auditoria_enel_sp_motores_v1'
# Tabela 11 p179: células mescladas conferidas no PDF renderizado.
# Valores em cv, por ligação FN / FF / FFF; não são potências elétricas em kW.
MOTORES_ESTRELA = {
    'A1': (1, None, None), 'A2': (2, None, None),
    '3': (1, 2, 5), '4': (2, 3, 10), '5': (2, 5, 15),
    '6': (3, 7.5, 20), '7': (5, 7.5, 25), '8': (7.5, 10, 30),
    '9': (7.5, 10, 30), '10': (7.5, 10, 40),
    '11': (7.5, 10, 50), '12': (7.5, 10, 60),
}
MOTORES_DELTA = {
    'A1': (1, None, None), 'A2': (2, None, None),
    '3': (1, 2, 5), '4': (1, 3, 7.5), '5': (1, 3, 10),
    '6': (1, 3, 15), '7': (1, 3, 20), '8': (1, 3, 25),
    '9': (1, 3, 30), '10': (1, 3, 40), '11': (1, 3, 40), '12': (1, 3, 40),
}


def registro_motores_enel_sp():
    tabelas=[]
    for sistema, tensao, tabela in [('Estrela','127/220 V',MOTORES_ESTRELA),
                                    ('Delta','120/240 V',MOTORES_DELTA)]:
        for categoria, _, _, _ in REFERENCIAS_ENTRADA:
            valores = tabela.get(categoria) or tabela[categoria[1:]]
            tabelas.append(dict(sistema=sistema, tensao=tensao, categoria=categoria,
                                FN_cv=valores[0], FF_cv=valores[1], FFF_cv=valores[2]))
    return {
        'documento':DOCUMENTO, 'revisao':'02', 'fonte':FONTE_OFICIAL,
        'referencias':['Item 7.4.4 — p.24–25', 'Tabela 11 — p.179', 'Tabela 2, nota 2 — p.22'],
        'tabela':tabelas,
        'restricoes':[
            'Potência nominal do motor em cv; não converter diretamente carga elétrica em W para cv.',
            'Trifásico até 5 cv: partida direta permitida; acima de 5 cv: redução da corrente de partida obrigatória.',
            'Verificar o maior motor ou a soma das potências dos motores com partidas simultâneas.',
            'Consulta implementada: estrela 127/220 V, rede aérea; um motor ou grupo de motores idênticos. Delta permanece para análise específica.',
            'FFF requer fornecimento trifásico no escopo estrela; a tabela não autoriza ligação FFF em entrada bifásica.',
            'Redução de partida e proteções precisam de verificação técnica conforme placa, ABNT e item 7.4.4.',
            'A exceção Enel SP do item 7.4.4 admite referências acima de 30 cv; não direcionar automaticamente para média tensão.',
            'A vedação de partida simultânea do item 7.4.3 pertence ao atendimento rural daquele item; não generalizar.',
            'Consulta de limites não dimensiona proteção do motor, partida, demanda ou padrão de entrada.',
        ],
    }


def registrar_auditoria_motores_enel_sp(perfil):
    from copy import deepcopy
    regras=deepcopy(perfil.get('regras') or {})
    regras[CHAVE_MOTORES]=registro_motores_enel_sp()
    return regras


def consultar_motor_enel_sp(categoria, potencia_cv, ligacao, partida,
                           quantidade=1, partida_simultanea=None,
                           reducao_confirmada=None, protecoes_confirmadas=None,
                           sistema='Estrela', fn=127, ff=220, rede='Aérea',
                           uf='SP', municipio='São Paulo'):
    import math
    r=dict(status='pendente', limite_cv=None, potencia_verificada_cv=None,
           aprovacao_automatica=False, demanda_calculada=False)
    if not enel_sp_atende_localidade(uf,municipio):
        return dict(r,motivo='Localidade fora do escopo Enel SP.')
    if sistema!='Estrela' or fn!=127 or ff!=220 or rede!='Aérea':
        return dict(r,motivo='Consulta implementada somente para rede aérea estrela 127/220 V; demais sistemas exigem análise específica.')
    categoria=str(categoria or '').strip().upper()
    if categoria not in {a[0] for a in REFERENCIAS_ENTRADA} or ligacao not in ('FN','FF','FFF'):
        return dict(r,motivo='Categoria ou ligação do motor desconhecida.')
    try:
        if isinstance(potencia_cv,bool) or isinstance(quantidade,bool):raise ValueError()
        potencia=float(potencia_cv); n=float(quantidade)
        if not math.isfinite(potencia) or potencia<=0 or not math.isfinite(n) or n<1 or not n.is_integer():raise ValueError()
        n=int(n)
    except (TypeError,ValueError,OverflowError):
        return dict(r,motivo='Informe potência nominal positiva em cv e quantidade inteira positiva.')
    if categoria.startswith('A') and ligacao!='FN' or categoria.startswith('B') and ligacao=='FFF':
        return dict(r,motivo='Ligação do motor incompatível com a modalidade de fornecimento estrela.')
    if n>1 and partida_simultanea is not True and partida_simultanea is not False:
        return dict(r,motivo='Confirme a simultaneidade de partida do grupo de motores idênticos.')
    valores=MOTORES_ESTRELA.get(categoria) or MOTORES_ESTRELA[categoria[1:]]
    limite=valores[('FN','FF','FFF').index(ligacao)]
    verificada=potencia*n if n>1 and partida_simultanea is True else potencia
    r.update(limite_cv=limite,potencia_verificada_cv=verificada)
    if limite is None or verificada>limite:
        return dict(r,motivo='Potência do maior motor ou do grupo simultâneo excede a referência da Tabela 11; conferir tecnicamente, sem elevar categoria automaticamente.')
    if partida not in ('Direta','Redução de corrente'):
        return dict(r,motivo='Tipo de partida não confirmado.')
    # Limite de 5 cv é por motor; a soma simultânea verifica a capacidade da categoria.
    if ligacao=='FFF' and potencia>5 and partida!='Redução de corrente':
        return dict(r,motivo='Motor trifásico acima de 5 cv exige redução de corrente de partida (7.4.4).')
    if partida=='Redução de corrente' and reducao_confirmada is not True:
        return dict(r,motivo='Confirmar tecnicamente o dispositivo de redução de partida conforme fabricante e ABNT.')
    if protecoes_confirmadas is not True:
        return dict(r,motivo='Confirmar proteções e condições de comando exigidas no item 7.4.4.')
    return dict(r,status='compativel_referencia',motivo='Compatível apenas com os limites de potência e as condições de partida declaradas nesta consulta; não aprova demanda, proteção ou entrada.')


def testar_motores_enel_sp():
    casos=[]
    # Verificação das células mescladas e dos limites exatos/estritamente superiores.
    for categoria,_,_,_ in REFERENCIAS_ENTRADA:
        limites=MOTORES_ESTRELA.get(categoria) or MOTORES_ESTRELA[categoria[1:]]
        for ligacao,limite in zip(('FN','FF','FFF'),limites):
            if limite is None or (categoria.startswith('B') and ligacao=='FFF'):continue
            partida='Redução de corrente' if ligacao=='FFF' and limite>5 else 'Direta'
            for delta,status in [(0,'compativel_referencia'),(.001,'pendente')]:
                casos.append((f'{categoria} {ligacao}: {limite+delta} cv',
                              dict(categoria=categoria,potencia_cv=limite+delta,ligacao=ligacao,partida=partida,
                                   reducao_confirmada=True,protecoes_confirmadas=True),status))
    base=dict(categoria='C4',potencia_cv=5,ligacao='FFF',partida='Direta',protecoes_confirmadas=True)
    for nome,alteracoes,status in [
        ('5 cv: direta',{},'compativel_referencia'),
        ('5,001 cv: direta',{'potencia_cv':5.001},'pendente'),
        ('5,001 cv: redução confirmada',{'potencia_cv':5.001,'partida':'Redução de corrente','reducao_confirmada':True},'compativel_referencia'),
        ('Redução sem confirmação',{'potencia_cv':5.001,'partida':'Redução de corrente'},'pendente'),
        ('Proteções desconhecidas',{'protecoes_confirmadas':None},'pendente'),
        ('B4 não admite FFF',{'categoria':'B4'},'pendente'),
        ('A2 não admite FF',{'categoria':'A2','ligacao':'FF','potencia_cv':1},'pendente'),
        ('2x5 cv simultâneos C4',{'quantidade':2,'partida_simultanea':True},'compativel_referencia'),
        ('3x5 cv simultâneos C4',{'quantidade':3,'partida_simultanea':True},'pendente'),
        ('3x5 cv não simultâneos C4',{'quantidade':3,'partida_simultanea':False},'compativel_referencia'),
        ('Simultaneidade desconhecida',{'quantidade':2},'pendente'),
        ('Delta encaminhado',{'sistema':'Delta','fn':120,'ff':240},'pendente'),
        ('Subterrânea encaminhada',{'rede':'Subterrânea'},'pendente'),
        ('Localidade fora',{'municipio':'Santos'},'pendente'),
        ('Potência desconhecida',{'potencia_cv':None},'pendente'),
        ('Potência infinita',{'potencia_cv':float('inf')},'pendente'),
        ('Quantidade fracionária',{'quantidade':1.5},'pendente'),
        ('Categoria desconhecida',{'categoria':'C0'},'pendente'),
        ('C10 40 cv: exceção SP',{'categoria':'C10','potencia_cv':40,'partida':'Redução de corrente','reducao_confirmada':True},'compativel_referencia'),
    ]:
        casos.append((nome,dict(base,**alteracoes),status))
    resultados=[]
    for nome,args,esperado in casos:
        obtido=consultar_motor_enel_sp(**args)
        ok=obtido['status']==esperado and not obtido['aprovacao_automatica'] and not obtido['demanda_calculada']
        resultados.append({'Caso':nome,'Esperado':esperado,'Obtido':obtido['status'],'Resultado':'PASSOU' if ok else 'FALHOU'})
    return resultados

METODO_DECLARADO = 'Enel SP — demanda declarada pelo responsável técnico'
CHAVE_DECLARACAO = 'enel_demanda_declarada'


def calcular_demanda_declarada_enel_sp(tabela, rede, perfil, potencias, ensaio_autorizado=False):
    """Ensaio integrado: dados declarados pelo RT; nenhum fator estimado."""
    import math
    r=dict(potencias, status='conferencia_tecnica', metodo=METODO_DECLARADO,
           perfil_normativo_id=(perfil or {}).get('id'),
           potencia_demanda_w=None,corrente_demanda_a=None,disjuntor_geral_a=None,
           fator_demanda_pct=None,detalhes_demanda=[],pendencias=[],
           tipo_fornecimento=rede.get('tipo_fornecimento'),
           tensao_fornecimento=rede.get('tensao_fornecimento'),
           perfil_normativo='Enel São Paulo — '+DOCUMENTO+' 02',
           aprovacao_automatica=False)
    def pendente(motivo):
        return dict(r,observacao=motivo,pendencias=[motivo])
    if not perfil_enel_sp(perfil or {}) or not enel_sp_atende_localidade(rede.get('uf'),rede.get('municipio')):
        return pendente('Perfil ou município incompatível com Enel São Paulo.')
    cidades={str(n).strip().casefold() for n in (perfil.get('municipios_atendidos') or [])}
    if str(rede.get('municipio') or '').strip().casefold() not in cidades:
        return pendente('Município não vinculado ao perfil selecionado.')
    publicado = perfil.get('status') == 'ATIVO' and not pendencias_ativacao_enel_sp(perfil)
    ensaio = (ensaio_autorizado and rede.get('enel_ensaio_admin') is True
              and perfil.get('status') in ('RASCUNHO','VALIDADO'))
    if not publicado and not ensaio:
        return pendente('Perfil Enel não liberado para este usuário. Utilize o ensaio administrativo ou publique o fluxo restrito.')
    if publicado and (str(rede.get('municipio') or '').strip().casefold() not in {n.casefold() for n in municipios_publicados_enel_sp(perfil)}
                       or rede.get('tipo_fornecimento') != 'Bifásico'):
        return pendente('Fluxo publicado restrito aos municípios liberados e fornecimento bifásico. Demais casos exigem análise técnica.')
    regras=perfil.get('regras') or {}
    if (perfil.get('documento')!=DOCUMENTO or perfil.get('revisao')!='02'
            or regras.get(CHAVE_AUDITORIA)!=registro_entrada_enel_sp()
            or regras.get(CHAVE_MOTORES)!=registro_motores_enel_sp()):
        return pendente('Registre as auditorias atuais de entrada e motores no perfil Enel.')
    if rede.get('metodo_demanda')!=METODO_DECLARADO:
        return pendente('Estimativa automática de demanda Enel SP bloqueada. Use a demanda declarada pelo responsável técnico.')
    d=rede.get(CHAVE_DECLARACAO) or {}
    if not isinstance(d,dict):return pendente('Declaração de demanda ausente.')
    if (not str(d.get('metodologia') or '').strip() or not str(d.get('responsavel') or '').strip()
            or d.get('confirmada_rt') is not True):
        return pendente('Informe responsável, metodologia e confirme a declaração técnica de demanda.')
    if d.get('escopo_confirmado') is not True or rede.get('tensao_fornecimento')!='127/220 V':
        return pendente('Confirme rede aérea urbana estrela 127/220 V e enquadramento sem cargas especiais pendentes.')
    if d.get('modalidade_confirmada') is not True:
        return pendente('Confirme tecnicamente a modalidade de fornecimento, inclusive eventual sobreposição B/C.')
    try:
        def positivo(v):
            if isinstance(v,bool):raise ValueError()
            f=float(v)
            if not math.isfinite(f) or f<=0:raise ValueError()
            return f
        valor=positivo(d.get('demanda'));corrente=positivo(d.get('corrente_max_a'))
        instalada=positivo(potencias.get('total_w'))/1000
        if d.get('unidade')=='kW':kw=valor
        elif d.get('unidade')=='kVA':
            fp=positivo(d.get('fator_potencia'))
            if fp>1:raise ValueError()
            kw=valor*fp
        else:raise ValueError()
    except (TypeError,ValueError,OverflowError):
        return pendente('Informe demanda/corrente positivas; para kVA, informe fator de potência maior que zero e até 1.')
    if corrente>100:
        return pendente('Fluxo declaratório limitado a 100 A; medição e atendimento acima desse valor exigem análise específica.')
    if kw>instalada+1e-6:
        return pendente('Demanda ativa declarada excede a carga instalada cadastrada. Confira cargas e metodologia.')
    if instalada>75:
        return pendente('Acima de 75 kW: fora do escopo deste ensaio; análise específica da distribuidora, sem direcionar automaticamente à média tensão.')
    modalidades=[]
    if instalada<=12:modalidades.append('Monofásico')
    if 12<instalada<=20:modalidades.append('Bifásico')
    if 15.1<=instalada<=75:modalidades.append('Trifásico')
    tipo=rede.get('tipo_fornecimento')
    if tipo not in modalidades:
        return pendente('Modalidade informada fora das faixas da Tabela 2 para este escopo.')
    n={'Monofásico':1,'Bifásico':2,'Trifásico':3}[tipo]
    # Limite físico conservador: I máxima declarada não pode ser inferior à
    # média mínima P/(n*Vfn). 1% apenas para arredondamento de dados declarados.
    potencia_minima_corrente = valor*1000 if d.get('unidade') == 'kVA' else kw*1000
    if corrente*n*127*1.01<potencia_minima_corrente:
        return pendente('Corrente máxima declarada incompatível com a demanda ativa e o número de fases. Confira o memorial de cálculo.')
    letra={'Monofásico':'A','Bifásico':'B','Trifásico':'C'}[tipo]
    refs=[x for x in registro_entrada_enel_sp()['entrada'] if x['categoria'].startswith(letra) and corrente<=x['disjuntor_referencia_a']]
    if not refs:return pendente('Corrente declarada acima das referências disponíveis da modalidade. Conferência técnica necessária.')
    ref=refs[0]
    obs=(('FLUXO DECLARATÓRIO RESTRITO Enel SP: ' if publicado else 'ENSAIO ADMINISTRATIVO Enel SP: ') + 'demanda e corrente declaradas pelo responsável técnico; '
         'sem estimativa automática. Categoria '+ref['categoria']+' é referência do Anexo B; '
         'não aprova padrão de entrada, proteção ou ligação. Ramal de entrada e alimentador do QDC são verificações distintas.')
    avisos=[]
    if instalada>15:avisos.append('Viabilidade da rede: carga acima de 15 kW (7.10.2).')
    else:avisos.append('Carga até 15 kW não implica dispensa automática de viabilidade; conferir rede próxima e impacto no transformador (7.10.2).')
    if instalada>38:avisos.append('Apresentar projeto de entrada para análise (7.8.1/Tabela 4).')
    if 50<instalada<=75:avisos.append('Nota 4 do item 7.4: eventual Grupo A depende de cargas perturbadoras e estudo da distribuidora; não é reenquadramento automático.')
    return dict(r,status='ok',potencia_demanda_w=kw*1000,corrente_demanda_a=corrente,
                enel_municipio=rede.get('municipio'),enel_fluxo_publicado=publicado,disjuntor_geral_a=ref['disjuntor_referencia_a'],observacao=obs+' '+' '.join(avisos),
                enel_declaracao=dict(d),enel_referencia_entrada=ref,enel_avisos=avisos)


CHAVE_INTEGRACAO = 'auditoria_enel_sp_integracao_v1'
CASOS_INTEGRACAO = (
    ('KW', '12,12 kW; 55 A; referência B4; DG 63 A bipolar.'),
    ('KVA', '12 kVA e FP 0,90 resultam em 10,80 kW; corrente declarada preservada em 55 A.'),
    ('MEMORIAL', 'Memorial identifica Enel, responsável, metodologia, unidade e valores declarados.'),
    ('ALIMENTADOR', '20 m; fase/neutro/PE 16 mm²; queda registrada 2,41 V (1,09%), limite configurado 2%.'),
    ('EXCESSO', 'Demanda 19798 kW bloqueia geração e downloads; retorno a dados válidos libera o fluxo.'),
    ('FP_ZERO', 'FP zero deixa demanda, corrente e DG pendentes; FP 0,90 restaura os resultados.'),
    ('PERSISTENCIA', '12 kVA, FP 0,90, 55 A e 20 m permanecem após salvar, trocar de projeto e retornar.'),
)


def consolidar_integracao_enel_sp(perfil, responsavel, confirmacao=False):
    """Registra confirmação administrativa; não executa nem homologa ensaios."""
    from copy import deepcopy
    from datetime import datetime, timezone
    if not perfil_enel_sp(perfil) or perfil.get('status') != 'RASCUNHO':
        raise ValueError('A consolidação exige perfil Enel São Paulo em RASCUNHO.')
    if confirmacao is not True or not str(responsavel or '').strip():
        raise ValueError('Confirme os testes e identifique o administrador responsável pelo registro.')
    regras = deepcopy(perfil.get('regras') or {})
    if regras.get(CHAVE_AUDITORIA) != registro_entrada_enel_sp() or regras.get(CHAVE_MOTORES) != registro_motores_enel_sp():
        raise ValueError('Registre primeiro as auditorias atuais de entrada e motores.')
    regras[CHAVE_INTEGRACAO] = {
        'schema': 1, 'versao_ensaiada': '13.6.335',
        'registrado_em': datetime.now(timezone.utc).isoformat(),
        'registrado_por': str(responsavel).strip(),
        'origem': 'Testes de interface e PDFs conferidos pelo usuário; persistência e bloqueio por excesso confirmados por relato.',
        'escopo': 'Ensaio administrativo; rede aérea urbana estrela 127/220 V; bifásico; Barueri/SP; carga instalada 19,798 kW; corrente 55 A.',
        'casos': [{'id': codigo, 'resultado': 'CONFIRMADO PELO ADMINISTRADOR', 'descricao': texto} for codigo, texto in CASOS_INTEGRACAO],
        'limites': ['Não equivale à aprovação técnica ou da distribuidora.',
                    'FP zero conferido no QDC; botão e downloads nesse cenário não documentados nos prints.',
                    'Não valida outros municípios, modalidades, tensões, correntes ou cargas especiais por este ensaio.',
                    'Estimativa automática de demanda continua bloqueada; publicação permanece pendente.'],
        'aprovacao_automatica': False,
    }
    return regras


CHAVE_PUBLICACAO = 'publicacao_enel_sp_declaratoria_v1'
ESCOPO_PUBLICACAO = {
    'uf': 'SP', 'municipios': ['Barueri'], 'tipo_fornecimento': 'Bifásico',
    'tensao': '127/220 V', 'rede': 'Aérea urbana estrela',
    'corrente_max_a': 100, 'carga_instalada_min_exclusiva_kw': 12,
    'carga_instalada_max_kw': 20, 'metodo': METODO_DECLARADO,
    'demanda_automatica': False, 'cargas_especiais': False,
}


def _assinatura_integracao(perfil):
    import hashlib, json
    return hashlib.sha256(json.dumps((perfil.get('regras') or {}).get(CHAVE_INTEGRACAO),
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def pendencias_base_publicacao_enel_sp(perfil):
    regras = perfil.get('regras') or {}
    pendencias = []
    if not perfil_enel_sp(perfil) or perfil.get('uf') != 'SP':
        pendencias.append('Perfil deve corresponder à Enel São Paulo/SP.')
    if (perfil.get('documento') != DOCUMENTO or perfil.get('revisao') != '02'
            or perfil.get('vigencia') != '06/03/2025' or perfil.get('fonte_oficial') != FONTE_OFICIAL):
        pendencias.append('Conferir documento, revisão, vigência e fonte oficial cadastrados.')
    if regras.get('fonte_conferida') is not True:
        pendencias.append('Confirmar a leitura da fonte oficial.')
    if regras.get(CHAVE_AUDITORIA) != registro_entrada_enel_sp():
        pendencias.append('Registrar a auditoria atual de modalidades e Anexo B.')
    if regras.get(CHAVE_MOTORES) != registro_motores_enel_sp():
        pendencias.append('Registrar a auditoria atual de motores.')
    cidades = perfil.get('municipios_atendidos')
    if (not isinstance(cidades, list) or 'Barueri' not in cidades
            or any(not enel_sp_atende_localidade('SP', n) for n in cidades)):
        pendencias.append('Conferir municípios de concessão, incluindo Barueri.')
    reg = regras.get(CHAVE_INTEGRACAO) or {}
    if (not isinstance(reg, dict) or reg.get('schema') != 1
            or reg.get('versao_ensaiada') != '13.6.335' or not reg.get('registrado_por')
            or not reg.get('registrado_em') or reg.get('aprovacao_automatica') is not False
            or reg.get('casos') != [{'id': codigo, 'resultado': 'CONFIRMADO PELO ADMINISTRADOR', 'descricao': texto}
                                    for codigo, texto in CASOS_INTEGRACAO]):
        pendencias.append('Consolidar a rodada completa de testes integrados declaratórios.')
    return pendencias


def publicacao_enel_registrada(perfil):
    reg = (perfil.get('regras') or {}).get(CHAVE_PUBLICACAO) or {}
    return (isinstance(reg, dict) and reg.get('schema') == 1
            and reg.get('escopo') == ESCOPO_PUBLICACAO
            and reg.get('integracao_assinatura') == _assinatura_integracao(perfil)
            and bool(reg.get('registrado_por')) and bool(reg.get('registrado_em'))
            and reg.get('testes_software') == 'PASSOU')


def preparar_publicacao_enel_sp(perfil, responsavel, fonte_confirmada=False, executar_testes=True):
    from copy import deepcopy
    from datetime import datetime, timezone
    if perfil.get('status') != 'RASCUNHO' or fonte_confirmada is not True or not str(responsavel or '').strip():
        raise ValueError('Exige RASCUNHO, administrador identificado e fonte oficial conferida.')
    novo = deepcopy(perfil)
    novo.setdefault('regras', {})['fonte_conferida'] = True
    pendencias = pendencias_base_publicacao_enel_sp(novo)
    if pendencias:
        raise ValueError(' '.join(pendencias))
    if executar_testes:
        resultados = testar_publicacao_enel_sp()
        if not all(t['Resultado'] == 'PASSOU' for t in resultados):
            raise ValueError('Falha nos testes de publicação restrita.')
    novo['regras']['observacoes'] = 'Fluxo declaratório restrito a Barueri/SP, bifásico 127/220 V aéreo urbano estrela, até 100 A, carga instalada acima de 12 até 20 kW. Demanda e corrente sob responsabilidade do RT; sem estimativa automática ou aprovação da entrada.'
    novo['regras'][CHAVE_PUBLICACAO] = {
        'schema': 1, 'escopo': deepcopy(ESCOPO_PUBLICACAO),
        'integracao_assinatura': _assinatura_integracao(novo),
        'registrado_por': str(responsavel).strip(),
        'registrado_em': datetime.now(timezone.utc).isoformat(),
        'testes_software': 'PASSOU', 'versao_preparacao': '13.6.337',
    }
    return novo['regras']


def testar_publicacao_enel_sp():
    """Casos sintéticos de acesso e limites; não são homologação elétrica."""
    from copy import deepcopy
    p = preparar_rascunho_enel_sp(); p['id'] = 999
    p['regras'] = registrar_auditoria_entrada_enel_sp(p)
    p['regras'] = registrar_auditoria_motores_enel_sp(p)
    p['regras'] = consolidar_integracao_enel_sp(p, 'TESTE AUTOMATIZADO', True)
    p['regras'] = preparar_publicacao_enel_sp(p, 'TESTE AUTOMATIZADO', True, executar_testes=False)
    p['status'] = 'ATIVO'
    rede = dict(uf='SP', municipio='Barueri', tipo_fornecimento='Bifásico',
        tensao_fornecimento='127/220 V', metodo_demanda=METODO_DECLARADO,
        enel_demanda_declarada=dict(demanda=12.12, unidade='kW', corrente_max_a=55,
        responsavel='TESTE', metodologia='TESTE', confirmada_rt=True,
        escopo_confirmado=True, modalidade_confirmada=True))
    casos = []
    def caso(nome, perfil=None, dados=None, total=19798, esperado=True):
        r = calcular_demanda_declarada_enel_sp([], dados or rede, perfil or p, {'total_w':total}, False)
        passou = ((r['status']=='ok') == esperado and r['aprovacao_automatica'] is False)
        casos.append({'Caso':nome, 'Resultado':'PASSOU' if passou else 'FALHOU'})
    caso('Usuário comum com perfil ativo e escopo válido')
    for campo, valor in [('municipio','São Paulo'),('uf','RJ'),('tipo_fornecimento','Trifásico'),
                         ('tensao_fornecimento','220/380 V'),('metodo_demanda','Automático')]:
        r=deepcopy(rede); r[campo]=valor; caso('Bloqueio: '+campo, dados=r, esperado=False)
    for campo, valor in [('corrente_max_a',0),('corrente_max_a',100.001),('demanda',19798),
                         ('confirmada_rt',False),('escopo_confirmado',False),('modalidade_confirmada',False)]:
        r=deepcopy(rede);r[CHAVE_DECLARACAO][campo]=valor;caso('Declaração inválida: '+campo, dados=r, esperado=False)
    for status in ['RASCUNHO','VALIDADO','INATIVO']:
        pp=deepcopy(p);pp['status']=status;caso('Status '+status, perfil=pp, esperado=False)
    for chave in [CHAVE_PUBLICACAO,CHAVE_INTEGRACAO,CHAVE_AUDITORIA,CHAVE_MOTORES,'fonte_conferida']:
        pp=deepcopy(p);pp['regras'].pop(chave);caso('Registro ausente: '+chave, perfil=pp, esperado=False)
    for total in [12000,20001,75001]:caso('Carga fora da faixa '+str(total),total=total,esperado=False)
    for corrente in [50,63,80,100]:
        r=deepcopy(rede);r[CHAVE_DECLARACAO]['corrente_max_a']=corrente
        caso('Referência de corrente '+str(corrente),dados=r)
    r=deepcopy(rede);r[CHAVE_DECLARACAO].update(unidade='kVA',demanda=12,fator_potencia=.9)
    caso('kVA válido',dados=r)
    r[CHAVE_DECLARACAO]['fator_potencia']=0;caso('FP zero',dados=r,esperado=False)
    for total in [12001,20000]:
        r=deepcopy(rede);r[CHAVE_DECLARACAO]['demanda']=10.8
        caso('Limite válido de carga '+str(total),dados=r,total=total)
    r=deepcopy(rede);r[CHAVE_DECLARACAO].update(unidade='kVA',demanda=20,fator_potencia=.5,corrente_max_a=50)
    caso('kVA incompatível com a corrente declarada',dados=r,esperado=False)
    r=deepcopy(rede);r[CHAVE_DECLARACAO].update(unidade='kVA',demanda=12,fator_potencia=1.01)
    caso('FP acima de um',dados=r,esperado=False)
    pp=deepcopy(p);pp['regras'][CHAVE_PUBLICACAO]['escopo']['municipios']=['São Paulo']
    caso('Escopo de publicação alterado',perfil=pp,esperado=False)
    pp=deepcopy(p);pp['regras'][CHAVE_INTEGRACAO]['registrado_por']='alterado'
    caso('Histórico alterado invalida preparação',perfil=pp,esperado=False)
    return casos


CHAVE_TERRITORIO = 'publicacao_enel_sp_territorio_v1'


def _assinatura_publicacao(perfil):
    import hashlib, json
    return hashlib.sha256(json.dumps((perfil.get('regras') or {}).get(CHAVE_PUBLICACAO),
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def municipios_publicados_enel_sp(perfil):
    """Sem registro territorial válido, preserva somente o piloto de Barueri."""
    if not publicacao_enel_registrada(perfil):
        return []
    reg = (perfil.get('regras') or {}).get(CHAVE_TERRITORIO) or {}
    cidades = reg.get('municipios') if isinstance(reg, dict) else None
    vinculadas = perfil.get('municipios_atendidos') or []
    valido = (isinstance(cidades, list) and bool(cidades) and len(cidades) == len(set(cidades))
        and all(n in MUNICIPIOS_ENEL_SP and n in vinculadas for n in cidades)
        and 'Barueri' in cidades and reg.get('schema') == 1
        and reg.get('fonte_municipios') == FONTE_MUNICIPIOS
        and reg.get('fonte_conferida') is True
        and reg.get('publicacao_assinatura') == _assinatura_publicacao(perfil)
        and bool(reg.get('registrado_por')) and bool(reg.get('registrado_em'))
        and reg.get('testes_software') == 'PASSOU')
    return list(cidades) if valido else ['Barueri']


def registrar_territorio_enel_sp(perfil, municipios, responsavel, fonte_confirmada=False, executar_testes=True):
    from copy import deepcopy
    from datetime import datetime, timezone
    if (perfil.get('status') != 'ATIVO' or pendencias_ativacao_enel_sp(perfil)
            or fonte_confirmada is not True or not str(responsavel or '').strip()):
        raise ValueError('Exige perfil ATIVO com preparação válida, administrador identificado e fonte territorial conferida.')
    if (not isinstance(municipios, list) or not municipios or 'Barueri' not in municipios
            or len(municipios) != len(set(municipios))
            or any(n not in MUNICIPIOS_ENEL_SP or n not in (perfil.get('municipios_atendidos') or []) for n in municipios)):
        raise ValueError('Selecione municípios oficiais vinculados ao perfil, mantendo Barueri.')
    if executar_testes and not all(t['Resultado'] == 'PASSOU' for t in testar_territorio_enel_sp()):
        raise ValueError('Falha nos testes territoriais.')
    regras = deepcopy(perfil.get('regras') or {})
    regras[CHAVE_TERRITORIO] = {
        'schema': 1, 'municipios': [n for n in MUNICIPIOS_ENEL_SP if n in municipios],
        'fonte_municipios': FONTE_MUNICIPIOS, 'fonte_conferida': True,
        'publicacao_assinatura': _assinatura_publicacao(perfil),
        'registrado_por': str(responsavel).strip(), 'registrado_em': datetime.now(timezone.utc).isoformat(),
        'versao_preparacao': '13.6.338', 'testes_software': 'PASSOU',
        'limites': 'Ampliação territorial do fluxo declaratório; sem validação de tensão por município ou aprovação de instalações. Mantém bifásico aéreo urbano estrela 127/220 V, acima de 12 até 20 kW e até 100 A.',
    }
    regras['observacoes'] = 'Fluxo declaratório restrito aos municípios liberados na Administração; bifásico aéreo urbano estrela 127/220 V, acima de 12 até 20 kW, até 100 A. Tensão e condições da rede devem ser confirmadas para cada instalação pelo RT. Sem demanda automática ou aprovação da entrada.'
    return regras


def testar_territorio_enel_sp():
    from copy import deepcopy
    p = preparar_rascunho_enel_sp();p['id'] = 999
    p['regras'] = registrar_auditoria_entrada_enel_sp(p)
    p['regras'] = registrar_auditoria_motores_enel_sp(p)
    p['regras'] = consolidar_integracao_enel_sp(p, 'TESTE AUTOMATIZADO', True)
    p['regras'] = preparar_publicacao_enel_sp(p, 'TESTE AUTOMATIZADO', True, executar_testes=False)
    p['status'] = 'ATIVO'
    p['regras'] = registrar_territorio_enel_sp(p, list(MUNICIPIOS_ENEL_SP), 'TESTE AUTOMATIZADO', True, executar_testes=False)
    rede = dict(uf='SP', municipio='Barueri', tipo_fornecimento='Bifásico', tensao_fornecimento='127/220 V',
        metodo_demanda=METODO_DECLARADO, enel_demanda_declarada=dict(demanda=12,unidade='kVA',fator_potencia=.9,
        corrente_max_a=55,responsavel='TESTE',metodologia='TESTE',confirmada_rt=True,escopo_confirmado=True,modalidade_confirmada=True))
    casos = []
    def caso(nome, cidade='Barueri', perfil=None, alteracoes=None, esperado=True):
        r = deepcopy(rede);r['municipio']=cidade;r.update(alteracoes or {})
        obtido = calcular_demanda_declarada_enel_sp([],r,perfil or p,{'total_w':19798},False)
        ok = ((obtido['status']=='ok')==esperado and obtido['aprovacao_automatica'] is False)
        casos.append({'Caso':nome,'Resultado':'PASSOU' if ok else 'FALHOU'})
    for cidade in MUNICIPIOS_ENEL_SP:
        caso('Município liberado: '+cidade,cidade)
    for cidade in ['Santos','Guarujá','Campinas','']:
        caso('Município não atendido: '+cidade,cidade,esperado=False)
    for campo,valor in [('uf','RJ'),('tensao_fornecimento','220/380 V'),('tipo_fornecimento','Trifásico'),('metodo_demanda','Automático')]:
        caso('Condições elétricas preservadas: '+campo,'São Paulo',alteracoes={campo:valor},esperado=False)
    b=deepcopy(p);b['regras'].pop(CHAVE_TERRITORIO)
    caso('Sem ampliação: Barueri preservada',perfil=b)
    caso('Sem ampliação: São Paulo bloqueada','São Paulo',perfil=b,esperado=False)
    b=deepcopy(p);b['regras'][CHAVE_TERRITORIO]['fonte_conferida']=False
    caso('Fonte territorial não confirmada','São Paulo',perfil=b,esperado=False)
    b=deepcopy(p);b['regras'][CHAVE_TERRITORIO]['publicacao_assinatura']='inválida'
    caso('Registro territorial desatualizado','São Paulo',perfil=b,esperado=False)
    b=deepcopy(p);b['regras'][CHAVE_TERRITORIO]['municipios'].append('Santos')
    caso('Município indevido invalida expansão','São Paulo',perfil=b,esperado=False)
    b=deepcopy(p);b['regras'][CHAVE_TERRITORIO]['municipios']=['Barueri','São Paulo']
    caso('Subconjunto: São Paulo liberada','São Paulo',perfil=b)
    caso('Subconjunto: Osasco bloqueada','Osasco',perfil=b,esperado=False)
    return casos
