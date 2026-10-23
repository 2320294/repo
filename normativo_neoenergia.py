"""Cadastro documental em lote. Regras elétricas regionais ainda não liberadas."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path

CHAVE_TERRITORIO = 'territorio_bloco_neoenergia_v1'
FONTE_TERRITORIO = 'https://www.neoenergia.com/distribuicao'
FONTE_EXCLUSOES_BA = 'https://agrese.se.gov.br/distribuidorasepermissionarias/'
FONTE_CATALOGO = 'https://github.com/kelvins/municipios-brasileiros'
HASH_CATALOGO = '7c8a2882044fa649593ef0402375a25f8ed7e2c60a48280af6746a9d07c4c219'


def referencias_regionais_neoenergia(perfil):
    """Índice documental; não contém parâmetros executáveis de dimensionamento."""
    nome = (perfil or {}).get('concessionaria')
    if nome == 'Neoenergia Coelba':
        return ['Anexo I, Tabela 1, página 61: entrada Coelba; conferir tensões por localidade.']
    if nome in ('Neoenergia Pernambuco', 'Neoenergia Cosern', 'Neoenergia Brasília'):
        return ['Anexo I, Tabela 2, página 62: entrada Pernambuco/Cosern/Brasília.']
    return []


def _validar_catalogo_neoenergia(conteudo, uf):
    if hashlib.sha256(conteudo).hexdigest() != HASH_CATALOGO:
        raise ValueError('Catálogo territorial divergente do pacote; reinstale o arquivo municipios_neoenergia.json.')
    dados = json.loads(conteudo)
    codigo_uf = {'BA':'29','PE':'26','RN':'24','DF':'53'}.get(uf)
    if not codigo_uf or dados.get('schema') != 1 or dados.get('fonte_nomes') != FONTE_CATALOGO:
        raise ValueError('Catálogo territorial incompatível.')
    itens = dados.get('ufs', {}).get(uf, [])
    codigos = [str(item.get('codigo_ibge','')) for item in itens]
    if len(codigos) != len(set(codigos)) or any(len(c)!=7 or not c.isdigit() or not c.startswith(codigo_uf) for c in codigos):
        raise ValueError('Códigos municipais inválidos para a UF.')
    return [item['nome'] for item in itens]


def _carregar_municipios_neoenergia(uf):
    try:
        conteudo = Path(__file__).with_name('municipios_neoenergia.json').read_bytes()
    except OSError as exc:
        raise ValueError('Catálogo territorial ausente. Inclua municipios_neoenergia.json junto aos arquivos do sistema.') from exc
    return _validar_catalogo_neoenergia(conteudo, uf)


def preparar_territorio_neoenergia(perfil, responsavel, buscar=None):
    """Atualiza cópia do rascunho, sem inferir tensão nem incluir outras UFs."""
    if not perfil_bloco_neoenergia(perfil) or perfil.get('status') != 'RASCUNHO':
        raise ValueError('Somente os quatro rascunhos deste bloco podem receber este vínculo.')
    if not str(responsavel or '').strip():
        raise ValueError('Identifique o responsável pelo registro.')
    empresa = next(e for e in EMPRESAS if e['concessionaria'].casefold() == str(perfil['concessionaria']).strip().casefold())
    uf = empresa['uf']
    if str(perfil.get('uf') or '').upper() != uf:
        raise ValueError('UF divergente do rascunho; cadastro preservado.')
    nomes = (buscar or _carregar_municipios_neoenergia)(uf)
    quantidade = {'BA':417, 'PE':185, 'RN':167, 'DF':1}[uf]
    if not isinstance(nomes, list) or any(not isinstance(n, str) or not n.strip() for n in nomes):
        raise ValueError('Lista de municípios inválida; vínculo não realizado.')
    nomes = [n.strip() for n in nomes]
    if len(nomes) != quantidade or len(set(n.casefold() for n in nomes)) != quantidade:
        raise ValueError(f'Catálogo municipal incompleto ou duplicado para {uf}; esperados {quantidade} registros. Cadastro preservado.')
    obrigatorios = {'BA':{'Salvador','Jandaíra','Rio Real'}, 'PE':{'Recife','Fernando de Noronha'}, 'RN':{'Natal','Mossoró'}, 'DF':{'Brasília'}}[uf]
    if not obrigatorios.issubset(set(nomes)):
        raise ValueError('Lista incompatível com a UF; cadastro preservado.')
    exclusoes = ['Jandaíra','Rio Real'] if uf == 'BA' else []
    nomes = sorted(set(nomes)-set(exclusoes), key=str.casefold)
    p = deepcopy(perfil)
    p['municipios_atendidos'] = nomes
    p['municipio'] = ''
    regras = p.setdefault('regras', {})
    observacao = {
        'BA':'Escopo deste perfil: somente BA. Delmiro Gouveia/AL e Dianópolis/TO, citados pela distribuidora, exigem perfis separados. Jandaíra e Rio Real excluídos conforme AGRESE; tabela de tensão não comprova concessão.',
        'PE':'Escopo deste perfil: PE, incluindo o distrito estadual Fernando de Noronha no cadastro IBGE. Pedras de Fogo/PB exige perfil separado. Atendimento territorial não confirma tensão ou padrão disponível na ilha.',
        'RN':'Escopo deste perfil: 167 municípios/RN. Município não determina a tensão disponível no endereço.',
        'DF':'Brasília é a unidade territorial do cadastro IBGE. Regiões administrativas do DF não são municípios adicionais. Município não determina tensão no endereço.',
    }[uf]
    regras[CHAVE_TERRITORIO] = dict(schema=1, concessionaria=empresa['concessionaria'], uf=uf,
        municipios=nomes, fonte_concessao=FONTE_TERRITORIO,
        fonte_nomes=FONTE_CATALOGO, origem_nomes='Catálogo local de contingência; não obtido da API IBGE nesta operação',
        consulta_catalogo='23/10/2026', hash_catalogo=HASH_CATALOGO,
        fonte_exclusoes=FONTE_EXCLUSOES_BA if uf=='BA' else '', exclusoes=exclusoes,
        responsavel=str(responsavel).strip(), registrado_em=datetime.now(timezone.utc).isoformat(),
        observacao=observacao, libera_calculo=False)
    return p


def territorio_neoenergia_registrado(perfil):
    if not perfil_bloco_neoenergia(perfil):
        return False
    r = ((perfil or {}).get('regras') or {}).get(CHAVE_TERRITORIO) or {}
    uf = perfil.get('uf')
    quantidade = {'BA':415,'PE':185,'RN':167,'DF':1}.get(uf)
    nomes = perfil.get('municipios_atendidos')
    return (r.get('schema') == 1 and r.get('concessionaria') == perfil.get('concessionaria')
        and r.get('uf') == uf and isinstance(nomes, list) and len(nomes) == quantidade
        and all(isinstance(n,str) and n.strip() for n in nomes)
        and len(set(nomes)) == quantidade and r.get('municipios') == nomes
        and r.get('fonte_concessao') == FONTE_TERRITORIO and bool(r.get('responsavel'))
        and bool(r.get('registrado_em')) and r.get('libera_calculo') is False
        and (uf != 'BA' or not {'Jandaíra','Rio Real'}.intersection(nomes)))


def vincular_territorios_neoenergia(listar, salvar, responsavel, buscar=None):
    resultados = []
    for empresa in EMPRESAS:
        try:
            encontrados = [p for p in listar() if str(p.get('concessionaria') or '').strip().casefold()==empresa['concessionaria'].casefold() and p.get('uf')==empresa['uf']]
            if len(encontrados)!=1 or not encontrados[0].get('id'):
                raise ValueError('Necessário um único perfil salvo para esta empresa/UF.')
            p = encontrados[0]
            if p.get('status') != 'RASCUNHO':
                raise ValueError('Perfil fora de RASCUNHO; preservado.')
            if territorio_neoenergia_registrado(p):
                resultado = 'JÁ VINCULADO — PRESERVADO'
            else:
                novo = preparar_territorio_neoenergia(p, responsavel, buscar)
                if not salvar({'municipios_atendidos':novo['municipios_atendidos'], 'municipio':'', 'regras':novo['regras']}, perfil_id=p['id']):
                    raise ValueError('Banco não confirmou a gravação; confira antes de repetir.')
                resultado = 'VINCULADO EM RASCUNHO'
            resultados.append({'Distribuidora':empresa['concessionaria'], 'UF':empresa['uf'], 'Resultado':resultado})
        except Exception as exc:
            resultados.append({'Distribuidora':empresa['concessionaria'], 'UF':empresa['uf'], 'Resultado':'PENDENTE', 'Detalhe':str(exc)})
    return resultados

DOCUMENTO = 'DIS-NOR-030'
REVISAO = '07'
DATA_APROVACAO = '17/04/2026'
CHAVE_BLOCO = 'cadastro_bloco_neoenergia_v1'
EMPRESAS = (
    dict(concessionaria='Neoenergia Coelba', uf='BA', portal='https://www.neoenergia.com/web/bahia/sua-casa/normas-tecnicas', pdf='https://www.neoenergia.com/documents/d/bahia/dis-nor-030-rev07?download=true'),
    dict(concessionaria='Neoenergia Pernambuco', uf='PE', portal='https://www.neoenergia.com/web/pernambuco/normas-tecnicas', pdf='https://www.neoenergia.com/documents/d/pernambuco/dis-nor-030-rev07?download=true'),
    dict(concessionaria='Neoenergia Cosern', uf='RN', portal='https://www.neoenergia.com/web/rn/normas-tecnicas', pdf='https://www.neoenergia.com/documents/d/rn/dis-nor-030-rev07?download=true'),
    dict(concessionaria='Neoenergia Brasília', uf='DF', portal='https://www.neoenergia.com/pt/web/brasilia/sua-casa/normas-tecnicas', pdf='https://www.neoenergia.com/documents/d/brasilia/dis-nor-030-rev07?download=true'),
)


def perfil_bloco_neoenergia(perfil):
    nome = str((perfil or {}).get('concessionaria') or '').strip().casefold()
    return any(nome == item['concessionaria'].casefold() for item in EMPRESAS)


def pendencias_bloco_neoenergia(perfil):
    if not perfil_bloco_neoenergia(perfil):
        return []
    return ([] if territorio_neoenergia_registrado(perfil) else [
        'Conferir e vincular municípios atendidos com fonte territorial específica; não presumir toda a UF.',
    ]) + [
        'Auditar tensões, modalidades, tabelas de entrada, demanda e exceções da distribuidora.',
        'Executar testes elétricos e integrados próprios antes de validar ou ativar.',
        'Conferir a aplicabilidade e eventuais documentos regionais complementares.',
    ]


def preparar_bloco_neoenergia(criado_por=''):
    perfis = []
    for empresa in EMPRESAS:
        perfil = dict(concessionaria=empresa['concessionaria'], uf=empresa['uf'], municipio='',
            municipios_atendidos=[], documento=DOCUMENTO, revisao=REVISAO, vigencia='',
            fonte_oficial=empresa['pdf'], status='RASCUNHO', criado_por=criado_por,
            regras=dict(schema='autoeletrica.perfil_normativo.v2', tipo_instalacao='Residencial individual',
                fornecimento={}, demanda={}, fonte_conferida=False,
                observacoes='Cadastro documental em lote. Aprovação do documento: 17/04/2026; vigência de aplicação ainda a conferir. Município e tensão não presumidos. Sem regras copiadas da Elektro ou CPFL.'))
        perfil['regras'][CHAVE_BLOCO] = dict(schema=1, grupo='Neoenergia',
            concessionaria=empresa['concessionaria'], uf=empresa['uf'],
            documento=DOCUMENTO, revisao=REVISAO, data_aprovacao=DATA_APROVACAO,
            portal=empresa['portal'], pdf=empresa['pdf'], paginas=142,
            consulta_documental='23/10/2026', etapa='CADASTRO DOCUMENTAL',
            pendencias=pendencias_bloco_neoenergia(perfil))
        perfis.append(perfil)
    return perfis


def planejar_bloco_neoenergia(existentes, criado_por=''):
    chaves = {(str(p.get('concessionaria') or '').strip().casefold(),str(p.get('uf') or '').strip().upper())
              for p in (existentes or [])}
    return [dict(perfil=deepcopy(p), acao='JÁ EXISTE — PRESERVAR' if
        (p['concessionaria'].casefold(),p['uf']) in chaves else 'CRIAR RASCUNHO')
        for p in preparar_bloco_neoenergia(criado_por)]


def cadastrar_bloco_neoenergia(listar, salvar, criado_por):
    """Retomável por empresa: relê antes de inserir e reporta falhas parciais."""
    resultados = []
    for modelo in preparar_bloco_neoenergia(criado_por):
        nome = modelo['concessionaria']
        try:
            plano = planejar_bloco_neoenergia(listar(), criado_por)
            item = next(p for p in plano if p['perfil']['concessionaria'] == nome)
            if item['acao'].startswith('JÁ EXISTE'):
                resultado = 'JÁ EXISTE — PRESERVADO'
            else:
                gravado = salvar(item['perfil'])
                if not gravado:
                    raise ValueError('Gravação não confirmada pelo banco; confira o cadastro antes de repetir.')
                resultado = 'CRIADO EM RASCUNHO'
            resultados.append({'Distribuidora':nome, 'UF':modelo['uf'], 'Resultado':resultado})
        except Exception as exc:
            resultados.append({'Distribuidora':nome, 'UF':modelo['uf'], 'Resultado':'ERRO', 'Detalhe':str(exc)})
    return resultados


def testar_bloco_neoenergia():
    casos = []
    def verifica(nome, condicao):
        casos.append({'Caso':nome,'Resultado':'PASSOU' if condicao else 'FALHOU'})
    modelos = preparar_bloco_neoenergia('TESTE')
    for p, empresa in zip(modelos, EMPRESAS):
        prefixo = p['concessionaria']+': '
        verifica(prefixo+'identificação e UF', p['concessionaria']==empresa['concessionaria'] and p['uf']==empresa['uf'])
        verifica(prefixo+'rascunho não publicado', p['status']=='RASCUNHO')
        verifica(prefixo+'sem abrangência estadual presumida', p['municipios_atendidos']==[])
        verifica(prefixo+'sem cópia de cálculo', p['regras']['fornecimento']=={} and p['regras']['demanda']=={})
        verifica(prefixo+'fonte regional individual', p['fonte_oficial']==empresa['pdf'])
        verifica(prefixo+'documento conferido', p['documento']==DOCUMENTO and p['revisao']=='07' and p['regras'][CHAVE_BLOCO]['paginas']==142)
        verifica(prefixo+'data de aprovação não é vigência',p['vigencia']=='' and p['regras'][CHAVE_BLOCO]['data_aprovacao']==DATA_APROVACAO)
        verifica(prefixo+'ativação pendente', bool(pendencias_bloco_neoenergia(p)))
    db=[]
    def salvar(p):db.append(deepcopy(p));return [p]
    primeiro=cadastrar_bloco_neoenergia(lambda:db,salvar,'TESTE')
    segundo=cadastrar_bloco_neoenergia(lambda:db,salvar,'TESTE')
    verifica('Lote cria quatro',len(db)==4 and all(t['Resultado']=='CRIADO EM RASCUNHO' for t in primeiro))
    verifica('Repetição preserva existentes',len(db)==4 and all(t['Resultado']=='JÁ EXISTE — PRESERVADO' for t in segundo))
    ativos=[dict(modelos[0],status='ATIVO')];antes=deepcopy(ativos)
    plano=planejar_bloco_neoenergia(ativos)
    verifica('Perfil existente ativo não sobrescrito',plano[0]['acao'].startswith('JÁ EXISTE') and ativos==antes)
    modelos[0]['regras']['demanda']['teste']=1
    verifica('Dicionários independentes',not modelos[1]['regras']['demanda'] and not preparar_bloco_neoenergia()[0]['regras']['demanda'])
    db2=[]
    def falha(p):
        if p['uf']=='PE':raise ValueError('Falha simulada')
        db2.append(deepcopy(p));return [p]
    erros=cadastrar_bloco_neoenergia(lambda:db2,falha,'TESTE')
    verifica('Falha parcial reportada sem desfazer sucessos',len(db2)==3 and sum(t['Resultado']=='ERRO' for t in erros)==1)
    verifica('Elektro fora deste lote',not perfil_bloco_neoenergia({'concessionaria':'Neoenergia Elektro'}))
    return casos


def testar_territorios_neoenergia():
    """Fixtures sintéticas testam gravação e travas, não a lista geográfica real."""
    casos = []
    def verifica(nome, ok):
        casos.append({'Caso':nome, 'Resultado':'PASSOU' if ok else 'FALHOU'})
    def rejeita(nome, fn):
        try:
            fn()
        except (ValueError, OSError):
            verifica(nome, True)
        else:
            verifica(nome, False)
    sentinelas = {'BA':['Salvador','Jandaíra','Rio Real'], 'PE':['Recife','Fernando de Noronha'], 'RN':['Natal','Mossoró'], 'DF':['Brasília']}
    def fixture(uf):
        base = sentinelas[uf]
        qtd = {'BA':417,'PE':185,'RN':167,'DF':1}[uf]
        return base + [f'Município sintético {uf} {i}' for i in range(qtd-len(base))]
    modelos = preparar_bloco_neoenergia('TESTE')
    for i,p in enumerate(modelos):
        p['id'] = str(i)
        antes = deepcopy(p)
        novo = preparar_territorio_neoenergia(p, 'TESTE', fixture)
        nome = p['concessionaria']+': '
        verifica(nome+'vínculo documental válido na fixture', territorio_neoenergia_registrado(novo))
        verifica(nome+'original preservado', p==antes)
        verifica(nome+'rascunho e cálculos vazios', novo['status']=='RASCUNHO' and not novo['regras']['fornecimento'] and not novo['regras']['demanda'])
        verifica(nome+'fonte normativa não confirmada pelo vínculo', novo['regras']['fonte_conferida'] is False)
        verifica(nome+'auditoria elétrica continua pendente', len(pendencias_bloco_neoenergia(novo))==3)
        rejeita(nome+'lista incompleta recusada', lambda:preparar_territorio_neoenergia(p,'TESTE',lambda uf:[]))
        rejeita(nome+'ativo preservado',lambda:preparar_territorio_neoenergia(dict(p,status='ATIVO'),'TESTE',fixture))
        adulterado = deepcopy(novo); adulterado['municipios_atendidos'] = []
        verifica(nome+'vínculo adulterado recusado', not territorio_neoenergia_registrado(adulterado))
    ba = preparar_territorio_neoenergia(modelos[0],'TESTE',fixture)
    verifica('Bahia exclui Jandaíra e Rio Real', len(ba['municipios_atendidos'])==415 and not set(['Jandaíra','Rio Real']).intersection(ba['municipios_atendidos']))
    rejeita('UF divergente recusada',lambda:preparar_territorio_neoenergia(dict(modelos[0],uf='PB'),'TESTE',fixture))
    rejeita('Responsável ausente recusado',lambda:preparar_territorio_neoenergia(modelos[0],'',fixture))
    def duplicada(uf):
        nomes=fixture(uf);nomes[-1]=nomes[0];return nomes
    rejeita('Duplicação recusada',lambda:preparar_territorio_neoenergia(modelos[0],'TESTE',duplicada))
    db=deepcopy(modelos); chamadas=[]
    def salvar(dados,perfil_id):
        chamadas.append(perfil_id)
        next(p for p in db if p['id']==perfil_id).update(deepcopy(dados))
        return [next(p for p in db if p['id']==perfil_id)]
    r=vincular_territorios_neoenergia(lambda:db,salvar,'TESTE',fixture)
    verifica('Lote atualiza quatro rascunhos',len(chamadas)==4 and all(x['Resultado']=='VINCULADO EM RASCUNHO' for x in r))
    anterior=deepcopy(db)
    r=vincular_territorios_neoenergia(lambda:db,salvar,'TESTE',fixture)
    verifica('Repetição não regrava',len(chamadas)==4 and db==anterior and all(x['Resultado'].startswith('JÁ VINCULADO') for x in r))
    def indisponivel(uf):raise OSError('IBGE indisponível (simulação)')
    chamadas.clear()
    r=vincular_territorios_neoenergia(lambda:modelos,salvar,'TESTE',indisponivel)
    verifica('Falha externa não grava listas',not chamadas and all(x['Resultado']=='PENDENTE' for x in r))
    duplicados=deepcopy(modelos)+[deepcopy(modelos[0])]
    r=vincular_territorios_neoenergia(lambda:duplicados,salvar,'TESTE',indisponivel)
    verifica('Cadastro duplicado não escolhido silenciosamente',r[0]['Resultado']=='PENDENTE' and 'único' in r[0]['Detalhe'])
    verifica('Elektro sem alteração territorial',not territorio_neoenergia_registrado({'concessionaria':'Neoenergia Elektro'}))
    for p in modelos:
        novo = preparar_territorio_neoenergia(p,'TESTE COM CATÁLOGO DO PACOTE')
        verifica(p['concessionaria']+': catálogo real permite vínculo sem rede externa', territorio_neoenergia_registrado(novo))
        verifica(p['concessionaria']+': procedência do catálogo registrada', novo['regras'][CHAVE_TERRITORIO]['fonte_nomes']==FONTE_CATALOGO and novo['regras'][CHAVE_TERRITORIO]['hash_catalogo']==HASH_CATALOGO)
    conteudo = Path(__file__).with_name('municipios_neoenergia.json').read_bytes()
    rejeita('Catálogo alterado recusado por integridade',lambda:_validar_catalogo_neoenergia(conteudo+b' ', 'RN'))
    rejeita('UF fora do catálogo recusada',lambda:_validar_catalogo_neoenergia(conteudo, 'SP'))
    return casos
