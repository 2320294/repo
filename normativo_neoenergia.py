"""Cadastro documental em lote. Regras elétricas regionais ainda não liberadas."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import math

CHAVE_ENTRADA = 'auditoria_entrada_bloco_neoenergia_v1'


def tabela_entrada_neoenergia(perfil):
    """Recorte das Tabelas 1/2: não é dimensionamento do alimentador do QDC."""
    if not perfil_bloco_neoenergia(perfil):
        return []
    coelba = str(perfil.get('concessionaria') or '').strip().casefold() == 'neoenergia coelba'
    # Categoria, FF/FN, modalidade, carga mínima/máxima kW, demanda mínima/máxima
    # kVA, proteção A, entrada subterrânea Cu XLPE/HEPR fase/neutro mm²,
    # eletroduto mínimo fases/neutro em polegadas, medição.
    dados = [
        ('M2','380/220 V','Monofásico',0,10,None,None,40,6,'1 1/4','Direta'),
        ('M3','380/220 V','Monofásico',10.1,15,None,None,63,16,'1 1/4','Direta'),
        ('T6','380/220 V','Trifásico',0,75,0,21,32,6,'1 1/4','Direta'),
        ('T7','380/220 V','Trifásico',0,75,21.2,26,40,6,'1 1/4','Direta'),
        ('T8','380/220 V','Trifásico',0,75,26.1,33,50,10,'1 1/4','Direta'),
        ('T9','380/220 V','Trifásico',0,75,33.1,40,63,16,'1 1/4','Direta'),
        ('T10','380/220 V','Trifásico',0,75,40.1,52,80,25,'2','Direta'),
        ('T11','380/220 V','Trifásico',0,75,52.1,66,100,35,'2','Direta'),
        ('T12','380/220 V','Trifásico',0,75,66.1,75,125,50,'2','Direta'),
    ]
    if coelba:
        dados = [
            ('M0','220/127 V','Monofásico',0,5,None,None,40,None,'1 1/4','Direta'),
            ('M1','220/127 V','Monofásico',5.1,10,None,None,63,10,'1 1/4','Direta'),
            ('B0','220/127 V','Bifásico',0,11,None,None,50,10,'1 1/4','Direta'),
            ('B2','220/127 V','Bifásico',11.1,15,None,None,70,16,'2','Direta'),
            ('T0','220/127 V','Trifásico',0,75,0,19,50,10,'1 1/4','Direta'),
            ('T1','220/127 V','Trifásico',0,75,19.1,24,63,16,'1 1/4','Direta'),
            ('T2','220/127 V','Trifásico',0,75,24.1,38,100,35,'2','Direta'),
            ('T3','220/127 V','Trifásico',0,75,38.1,47,125,50,'2','Direta'),
            ('T4','220/127 V','Trifásico',0,75,47.1,57,150,70,'2','Direta'),
            ('T5','220/127 V','Trifásico',0,75,57.1,75,200,95,'2 1/2','Indireta'),
        ] + dados
    return [dict(categoria=c,tensao_ff_fn=v,modalidade=m,carga_min_kw=lo,carga_max_kw=hi,
        demanda_min_kva=dlo,demanda_max_kva=dhi,disjuntor_referencia_a=dg,
        entrada_subterranea_cu_xlpe_hepr_fase_mm2=s,entrada_subterranea_cu_xlpe_hepr_neutro_mm2=s,
        eletroduto_fases_neutro_min_pol=t,medicao=med,tabela=1 if coelba else 2,
        pagina=61 if coelba else 62) for c,v,m,lo,hi,dlo,dhi,dg,s,t,med in dados]


def registro_entrada_neoenergia(perfil):
    if not perfil_bloco_neoenergia(perfil):
        raise ValueError('Distribuidora fora do bloco Neoenergia.')
    empresa = next(e for e in EMPRESAS if e['concessionaria'].casefold()==str(perfil['concessionaria']).strip().casefold())
    return dict(schema=1, concessionaria=empresa['concessionaria'], uf=empresa['uf'],
        documento=DOCUMENTO,revisao=REVISAO,fonte=empresa['pdf'],
        entrada=tabela_entrada_neoenergia(perfil),
        referencias=['6.2.4–6.2.8: tensão local e modalidades, páginas 11–13',
            '6.27: demanda trifásica, páginas 47–49; 6.28: enquadramento, página 50',
            'Anexo I, notas 1–18, páginas 59–60'],
        demanda_documental=[
            'Método 6.27: D em kVA; residencial trifásico a: Tabela 6 e FP 1,00.',
            'b: Tabela 7, FP 1,00; c: Tabela 8, FP 1,00; d: Tabela 9, FP 0,92 ou fabricante; e: Tabela 9, FP 1,00.',
            'f: Tabelas 11/12; g: Tabelas 18/14; h: Tabela 15 e FP de placa; i: Tabela 16, FP 1,00.',
            'Recarga j consta no item 6.27.10, mas não na soma impressa a–i: manter fora do escopo automático até análise específica.',
            'Fatores e classificações TUE ainda não auditados neste bloco; cálculo de demanda e integração permanecem bloqueados.'
        ],
        limites=[
            'Consulta isolada de tabela. Não libera o perfil nem aprova entrada, rede ou instalação.',
            'Tensão em ordem FF/FN. Município não confirma tensão disponível no endereço.',
            'Condutores mostrados apenas do ramal de entrada subterrâneo Cu XLPE/HEPR; não representam PVC, PE, aterramento ou alimentador do QDC. M0 não possui valor nesta coluna.',
            'Faixas literais: lacunas decimais não são interpoladas. Coelba bifásico acima de 15 até 18 kW exige esclarecimento entre item geral e Tabela 1.',
            'B0 depende da condição de diferença de medição da nota 14. Ligações abaixo da carga usual não são autorização de modalidade.',
            'Motores, soldas, cargas especiais, simultaneidade, caixas homologadas e demais notas exigem conferência adicional. Brasília: DIS-ETE-145 e NDB-PTC-001 enquanto vigente.',
        ],libera_calculo=False)


def auditoria_entrada_neoenergia_registrada(perfil):
    if not perfil_bloco_neoenergia(perfil):return False
    r=((perfil or {}).get('regras') or {}).get(CHAVE_ENTRADA) or {}
    return r.get('referencia')==registro_entrada_neoenergia(perfil) and bool(r.get('responsavel')) and bool(r.get('registrado_em'))


def registrar_entrada_neoenergia(perfil,responsavel):
    if not territorio_neoenergia_registrado(perfil) or perfil.get('status')!='RASCUNHO':
        raise ValueError('Requer perfil RASCUNHO com vínculo territorial registrado.')
    if not str(responsavel or '').strip():raise ValueError('Responsável ausente.')
    empresa=next(e for e in EMPRESAS if e['uf']==perfil['uf'])
    if perfil.get('documento')!=DOCUMENTO or perfil.get('revisao')!=REVISAO or perfil.get('fonte_oficial')!=empresa['pdf']:
        raise ValueError('Documento, revisão ou fonte regional divergente.')
    regras=deepcopy(perfil.get('regras') or {})
    existente=regras.get(CHAVE_ENTRADA)
    if existente:
        if not auditoria_entrada_neoenergia_registrada(perfil):raise ValueError('Auditoria existente divergente; preservada para conferência.')
        return regras
    regras[CHAVE_ENTRADA]=dict(referencia=registro_entrada_neoenergia(perfil),responsavel=str(responsavel).strip(),registrado_em=datetime.now(timezone.utc).isoformat())
    return regras


def cadastrar_auditorias_entrada_neoenergia(listar,salvar,responsavel):
    saida=[]
    for empresa in EMPRESAS:
        try:
            perfis=[p for p in listar() if str(p.get('concessionaria') or '').strip().casefold()==empresa['concessionaria'].casefold() and p.get('uf')==empresa['uf']]
            if len(perfis)!=1 or not perfis[0].get('id'):raise ValueError('Necessário um único perfil salvo por distribuidora/UF.')
            p=perfis[0]
            if p.get('status')!='RASCUNHO':raise ValueError('Perfil fora de RASCUNHO; preservado.')
            regras=registrar_entrada_neoenergia(p,responsavel)
            if auditoria_entrada_neoenergia_registrada(p):resultado='JÁ REGISTRADA — PRESERVADA'
            else:
                if not salvar({'regras':regras},perfil_id=p['id']):raise ValueError('Gravação não confirmada pelo banco.')
                resultado='REFERÊNCIA REGISTRADA EM RASCUNHO'
            saida.append({'Distribuidora':empresa['concessionaria'],'Resultado':resultado})
        except Exception as exc:saida.append({'Distribuidora':empresa['concessionaria'],'Resultado':'PENDENTE','Detalhe':str(exc)})
    return saida


def consultar_entrada_neoenergia(perfil,tensao,modalidade,carga_kw,demanda_kva=None):
    saida=dict(status='conferencia_tecnica',motivo='',referencia=None,aprovacao_automatica=False)
    def pendencia(texto):saida['motivo']=texto;return saida
    if not auditoria_entrada_neoenergia_registrada(perfil):return pendencia('Referência regional ainda não registrada ou divergente.')
    def numero(n):
        if isinstance(n,bool):return None
        try:x=float(n)
        except (TypeError,ValueError):return None
        return x if math.isfinite(x) and x>0 else None
    carga=numero(carga_kw)
    if carga is None or carga>75:return pendencia('Carga deve ser positiva e até 75 kW; demais casos exigem análise específica.')
    linhas=[r for r in tabela_entrada_neoenergia(perfil) if r['tensao_ff_fn']==tensao and r['modalidade']==modalidade]
    if not linhas:return pendencia('Tensão ou modalidade não mapeada nesta tabela regional.')
    if modalidade=='Bifásico' and 15<carga<=18:return pendencia('Faixa conflitante da Coelba: limite geral de 18 kW versus Tabela 1 até 15 kW. Conferência técnica obrigatória.')
    demanda=numero(demanda_kva) if modalidade=='Trifásico' else None
    if modalidade=='Trifásico' and (demanda is None or demanda>75):return pendencia('Informe demanda previamente calculada, positiva e até 75 kVA. Esta consulta não calcula demanda.')
    candidatas=[r for r in linhas if r['carga_min_kw']<=carga<=r['carga_max_kw'] and (modalidade!='Trifásico' or r['demanda_min_kva']<=demanda<=r['demanda_max_kva'])]
    if len(candidatas)!=1:return pendencia('Valor em lacuna ou fora das faixas literais; não arredondar para enquadrar.')
    saida.update(status='referencia_isolada',referencia=deepcopy(candidatas[0]),motivo='Referência de tabela localizada. Não verifica motores, cargas especiais, viabilidade, cálculo de demanda nem dimensionamento do QDC; sem aprovação da entrada.')
    return saida


def testar_entrada_bloco_neoenergia():
    casos=[]
    def verifica(nome,ok):casos.append({'Caso':nome,'Resultado':'PASSOU' if ok else 'FALHOU'})
    def rejeita(nome,fn):
        try:fn()
        except ValueError:verifica(nome,True)
        else:verifica(nome,False)
    perfis=[]
    for i,p in enumerate(preparar_bloco_neoenergia('TESTE')):
        p['id']=str(i+1);p=preparar_territorio_neoenergia(p,'TESTE');antes=deepcopy(p)
        p['regras']=registrar_entrada_neoenergia(p,'TESTE')
        perfis.append(p)
        prefixo=p['concessionaria']+': '
        verifica(prefixo+'referência registrada',auditoria_entrada_neoenergia_registrada(p))
        verifica(prefixo+'território e status preservados',p['municipios_atendidos']==antes['municipios_atendidos'] and p['status']=='RASCUNHO')
        verifica(prefixo+'cálculos e fonte geral não liberados',p['regras']['demanda']=={} and p['regras']['fornecimento']=={} and p['regras']['fonte_conferida'] is False and bool(pendencias_bloco_neoenergia(p)))
        verifica(prefixo+'repetição preserva registro',registrar_entrada_neoenergia(p,'OUTRO')==p['regras'])
        for valor,cat,dg,secao in [(21,'T6',32,6),(21.2,'T7',40,6),(26,'T7',40,6),(26.1,'T8',50,10),(33.1,'T9',63,16),(40.1,'T10',80,25),(52.1,'T11',100,35),(66.1,'T12',125,50),(75,'T12',125,50)]:
            r=consultar_entrada_neoenergia(p,'380/220 V','Trifásico',60,valor);ref=r.get('referencia') or {}
            verifica(prefixo+f'{valor} kVA → {cat}',r['status']=='referencia_isolada' and ref.get('categoria')==cat and ref.get('disjuntor_referencia_a')==dg and ref.get('entrada_subterranea_cu_xlpe_hepr_fase_mm2')==secao and r['aprovacao_automatica'] is False)
        for valor in [21.001,21.1,21.199,26.001,33.01,40.01,52.01,66.01,75.001,None,0,-1,float('nan'),float('inf'),True]:
            verifica(prefixo+f'demanda {valor} pendente',consultar_entrada_neoenergia(p,'380/220 V','Trifásico',60,valor)['referencia'] is None)
        for valor in [None,0,-1,75.001,float('nan'),True]:
            verifica(prefixo+f'carga {valor} recusada',consultar_entrada_neoenergia(p,'380/220 V','Trifásico',valor,20)['referencia'] is None)
        verifica(prefixo+'monofásico M2 por carga',consultar_entrada_neoenergia(p,'380/220 V','Monofásico',10)['referencia']['categoria']=='M2')
        verifica(prefixo+'lacuna monofásica',consultar_entrada_neoenergia(p,'380/220 V','Monofásico',10.001)['referencia'] is None)
        verifica(prefixo+'monofásico M3 por carga',consultar_entrada_neoenergia(p,'380/220 V','Monofásico',10.1)['referencia']['categoria']=='M3')
        verifica(prefixo+'bifásico 380 não presumido',consultar_entrada_neoenergia(p,'380/220 V','Bifásico',20)['referencia'] is None)
        rejeita(prefixo+'ativo não alterado',lambda:registrar_entrada_neoenergia(dict(p,status='ATIVO'),'TESTE'))
        adulterado=deepcopy(p);adulterado['regras'][CHAVE_ENTRADA]['referencia']['entrada'][0]['disjuntor_referencia_a']=999
        verifica(prefixo+'referência adulterada bloqueada',consultar_entrada_neoenergia(adulterado,'380/220 V','Trifásico',60,20)['referencia'] is None)
    ba=perfis[0]
    for valor,cat,dg in [(19,'T0',50),(19.1,'T1',63),(24.1,'T2',100),(38.1,'T3',125),(47.1,'T4',150),(57.1,'T5',200)]:
        r=consultar_entrada_neoenergia(ba,'220/127 V','Trifásico',60,valor)['referencia']
        verifica(f'Coelba 220: {valor} kVA → {cat}',r['categoria']==cat and r['disjuntor_referencia_a']==dg)
    r=consultar_entrada_neoenergia(ba,'220/127 V','Bifásico',12)['referencia']
    verifica('Coelba B2 é 70 A; não copiar B1 Elektro',r['categoria']=='B2' and r['disjuntor_referencia_a']==70)
    verifica('Coelba M0 sem seção subterrânea presumida',consultar_entrada_neoenergia(ba,'220/127 V','Monofásico',5)['referencia']['entrada_subterranea_cu_xlpe_hepr_fase_mm2'] is None)
    for carga in [11.001,15.001,18]:verifica(f'Coelba bifásico {carga} bloqueado',consultar_entrada_neoenergia(ba,'220/127 V','Bifásico',carga)['referencia'] is None)
    for p in perfis[1:]:verifica(p['concessionaria']+': 220/127 não copiado da Coelba',consultar_entrada_neoenergia(p,'220/127 V','Trifásico',60,20)['referencia'] is None)
    db=[preparar_territorio_neoenergia(p,'TESTE') for p in preparar_bloco_neoenergia('TESTE')]
    for i,p in enumerate(db):p['id']=str(i+1)
    chamadas=[]
    def salvar(dados,perfil_id):
        chamadas.append(perfil_id);p=next(x for x in db if x['id']==perfil_id);p.update(deepcopy(dados));return [p]
    r=cadastrar_auditorias_entrada_neoenergia(lambda:db,salvar,'TESTE')
    verifica('Lote registra quatro referências',len(chamadas)==4 and all(t['Resultado']=='REFERÊNCIA REGISTRADA EM RASCUNHO' for t in r))
    antes=deepcopy(db);r=cadastrar_auditorias_entrada_neoenergia(lambda:db,salvar,'OUTRO')
    verifica('Lote repetido preserva registros',db==antes and len(chamadas)==4 and all(t['Resultado']=='JÁ REGISTRADA — PRESERVADA' for t in r))
    verifica('Elektro fora desta auditoria',not auditoria_entrada_neoenergia_registrada({'concessionaria':'Neoenergia Elektro'}))
    return casos

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
        ('Concluir auditoria de demanda, motores, cargas especiais e condições de aplicação; entrada registrada apenas como referência isolada.' if auditoria_entrada_neoenergia_registrada(perfil) else 'Auditar tensões, modalidades, tabelas de entrada, demanda e exceções da distribuidora.'),
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
