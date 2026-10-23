"""Cadastro documental em lote. Regras elétricas regionais ainda não liberadas."""
from copy import deepcopy

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
    return [
        'Conferir e vincular municípios atendidos com fonte territorial específica; não presumir toda a UF.',
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
