"""Cadastro documental em lote. Regras elétricas regionais ainda não liberadas."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import math

CHAVE_ENTRADA = 'auditoria_entrada_bloco_neoenergia_v1'
CHAVE_DEMANDA = 'auditoria_demanda_bloco_neoenergia_v1'
CHAVE_CONSOLIDACAO = 'consolidacao_ensaios_bloco_neoenergia_v1'


def consolidar_ensaio_neoenergia(perfil,responsavel,confirmacao=False):
    if confirmacao is not True:raise ValueError('Confirme somente os ensaios executados neste perfil.')
    registrar_demanda_neoenergia(perfil,responsavel)
    if not auditoria_demanda_neoenergia_registrada(perfil):raise ValueError('Demanda isolada não registrada.')
    regras=deepcopy(perfil['regras'])
    if regras.get(CHAVE_CONSOLIDACAO):return regras
    casos=testar_integracao_bloco_neoenergia()
    if any(r['Resultado']!='PASSOU' for r in casos):raise ValueError('Testes de integração não passaram.')
    referencia=dict(entrada=registro_entrada_neoenergia(perfil),demanda=registro_demanda_neoenergia(perfil))
    assinatura=hashlib.sha256(json.dumps(referencia,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    regras[CHAVE_CONSOLIDACAO]=dict(schema=1,responsavel=str(responsavel).strip(),
        registrado_em=datetime.now(timezone.utc).isoformat(),versao_ensaiada='13.6.345',
        origem='Confirmação administrativa dos ensaios de interface; não é homologação técnica.',
        assinatura_referencias=assinatura,testes_software=len(casos),
        casos_confirmados=[
            'Demanda fictícia de 19,500 kVA recuperada após bloqueio por cargas excluídas.',
            'Quantidade zero com 11.000 W no grupo b bloqueada; quantidade 2 restaurou 19,500 kVA.',
            'Integração 380/220 V: 26,420 kW, 19,500 kVA, corrente informada 31 A, T6 / 32 A.',
            'Corrente de 33 A bloqueou a referência; retorno a 31 A restaurou T6 / 32 A.'
        ],limites=['Somente os dados fictícios e o perfil em que os ensaios foram confirmados.',
            'Não registra teste com projeto real nem libera status VALIDADO/ATIVO.',
            'Fogões, motores, cargas especiais e demais exclusões continuam pendentes.'],
        libera_calculo=False)
    return regras


def preparar_cargas_projeto_neoenergia(tabela):
    """Cópia para conferência: mantém os VA originais e não os converte em W."""
    if not isinstance(tabela,list) or not tabela or any(not isinstance(r,dict) for r in tabela):
        raise ValueError('Abra um projeto com tabela de cargas válida antes desta conferência.')
    itens=[]
    def numero(x):
        if isinstance(x,bool):return None
        try:x=float(x)
        except (ValueError,TypeError,OverflowError):return None
        return x if math.isfinite(x) and x>=0 else None
    campos=[('Iluminação',['Qtd Ilum.'],'Carga Ilum. (W)','Pot. Unit. Ilum (W)','Carga Ilum. (VA)'),
        ('TUG',['Qtd TUG','TUGs (Qtd)'],'Carga TUGs (W)','Pot. Unit. TUG (W)','Carga TUGs (VA)'),
        ('TUE',['Qtd TUE'],'Carga TUE (W)','Pot. Unit. TUE (W)','Carga TUE (VA)')]
    for i,ambiente in enumerate(tabela):
        for tipo,chaves_q,chave_w,chave_unit,chave_va in campos:
            q=next((ambiente[k] for k in chaves_q if k in ambiente),None)
            quantidade=numero(q)
            # Se um total W existe mas é inválido, não esconder o problema com outro campo.
            w=numero(ambiente[chave_w]) if chave_w in ambiente else None
            if chave_w not in ambiente and chave_unit in ambiente:
                unit=numero(ambiente[chave_unit])
                if unit is not None and quantidade is not None:w=unit*quantidade
            grupo='a' if tipo!='TUE' else ('Ausente' if quantidade==0 and w==0 else 'Pendente')
            itens.append({'ID':f'{i}:{tipo}','Ambiente':str(ambiente.get('Ambiente') or f'Linha {i+1}'),
                'Tipo':tipo,'Equipamento':str(ambiente.get('Equipamento TUE') or '') if tipo=='TUE' else tipo,
                'Quantidade original':q,'Previsão legada (VA)':ambiente.get(chave_va),
                'Total original (W)':ambiente.get(chave_w),'Grupo':grupo,'Quantidade conferida':quantidade,
                'Potência total conferida (W)':w,'FP para grupos d/f':None})
    return itens


def agrupar_cargas_projeto_neoenergia(tabela,itens):
    """Agrupa cópia explicitamente classificada pelo administrador; não escreve projeto."""
    saida=dict(status='conferencia_tecnica',motivo='',linhas=None,fp_d=None,fp_f=None,carga_conferida_kw=None)
    def pendencia(msg):saida['motivo']=msg;return saida
    try:originais=preparar_cargas_projeto_neoenergia(tabela)
    except ValueError as exc:return pendencia(str(exc))
    if not isinstance(itens,list) or any(not isinstance(r,dict) for r in itens):return pendencia('Tabela de conferência inválida.')
    ids=[r.get('ID') for r in itens]
    if any(not isinstance(i,str) for i in ids) or len(ids)!=len(set(ids)) or set(ids)!={r['ID'] for r in originais}:
        return pendencia('Linhas ausentes, duplicadas ou divergentes do projeto atual. Recarregue a conferência.')
    def numero(x):
        if isinstance(x,bool):return None
        try:x=float(x)
        except (ValueError,TypeError,OverflowError):return None
        return x if math.isfinite(x) and x>=0 else None
    acumulados={g:dict(q=0,p=0.0,s=0.0) for g in ['a','b','c','d','e','f','i']}
    for r in itens:
        g=r.get('Grupo');local=f"{r.get('Ambiente','')} / {r.get('Tipo','')}"
        if g not in list(acumulados)+['Ausente']:return pendencia(local+': classifique o equipamento. Cargas fora do escopo não podem ser ignoradas.')
        q=numero(r.get('Quantidade conferida'));pot=numero(r.get('Potência total conferida (W)'))
        if q is None or not q.is_integer() or q>100000 or pot is None:return pendencia(local+': confira quantidade inteira e potência ativa em W; VA não foi convertido automaticamente.')
        if (q==0)!=(pot==0):return pendencia(local+': quantidade e potência devem ser ambas zero ou ambas positivas.')
        if g=='Ausente':
            if q!=0 or pot!=0:return pendencia(local+': carga positiva não pode ser declarada ausente.')
            continue
        if not q:continue
        fp=1.0
        if g in ('d','f'):
            fp=numero(r.get('FP para grupos d/f'))
            if fp is None or not 0<fp<=1:return pendencia(local+': informe FP positivo até 1,00; grupo d usa 0,92 normativo ou fabricante, grupo f exige placa/catálogo.')
        s=pot/fp
        if not math.isfinite(s):return pendencia(local+': potência aparente excede a capacidade numérica.')
        acumulados[g]['q']+=int(q);acumulados[g]['p']+=pot;acumulados[g]['s']+=s
    linhas=dados_ensaio_demanda_neoenergia()
    for r in linhas:
        g=r['Grupo'];a=acumulados[g]
        r['Quantidade']=(1 if a['p'] else 0) if g=='a' else a['q']
        r['Potência total']=a['s'] if g=='f' else a['p']
    carga=sum(a['p'] for a in acumulados.values())/1000
    if not math.isfinite(carga) or carga<=0:return pendencia('A soma das cargas conferidas deve ser positiva e finita.')
    saida.update(status='conferencia_preparada',motivo='Cópia agrupada para ensaio; classificação e dados elétricos são declarados pelo administrador.',linhas=linhas,
        fp_d=acumulados['d']['p']/acumulados['d']['s'] if acumulados['d']['s'] else .92,
        fp_f=acumulados['f']['p']/acumulados['f']['s'] if acumulados['f']['s'] else None,
        carga_conferida_kw=carga)
    return saida


def testar_preparacao_projeto_neoenergia():
    casos=[]
    def verifica(nome,ok):casos.append({'Caso':nome,'Resultado':'PASSOU' if ok else 'FALHOU'})
    def rejeita(nome,fn):
        try:fn()
        except ValueError:verifica(nome,True)
        else:verifica(nome,False)
    def ambiente(nome,q,w,equip,ilum=0):
        return {'Ambiente':nome,'Qtd Ilum.':1 if ilum else 0,'Carga Ilum. (W)':ilum,'Qtd TUG':0,'Carga TUGs (W)':0,
            'Qtd TUE':q,'Carga TUE (W)':w,'Equipamento TUE':equip}
    origem=[ambiente('Banheiro',2,11000,'Chuveiro',10000),ambiente('Cozinha',1,2000,'Forno Elétrico'),ambiente('Quarto',2,3420,'Ar Condicionado')]
    antes=deepcopy(origem);itens=preparar_cargas_projeto_neoenergia(origem)
    verifica('Preparação preserva origem',origem==antes)
    verifica('TUEs positivas ficam pendentes',all(r['Grupo']=='Pendente' for r in itens if r['Tipo']=='TUE'))
    verifica('Sem classificação não calcula',agrupar_cargas_projeto_neoenergia(origem,itens)['linhas'] is None)
    conferidos=deepcopy(itens)
    for r in conferidos:
        if r['ID']=='0:TUE':r['Grupo']='b'
        if r['ID']=='1:TUE':r['Grupo']='e'
        if r['ID']=='2:TUE':r['Grupo']='f';r['FP para grupos d/f']=.9
    resultado=agrupar_cargas_projeto_neoenergia(origem,conferidos)
    verifica('Cargas conferidas preparam sete grupos',resultado['status']=='conferencia_preparada' and len(resultado['linhas'])==7)
    verifica('Ar 3420 W / 0,9 produz 3800 VA',math.isclose(next(r['Potência total'] for r in resultado['linhas'] if r['Grupo']=='f'),3800))
    verifica('Carga ativa preservada 26,42 kW',math.isclose(resultado['carga_conferida_kw'],26.42))
    verifica('Nenhum dado original alterado pelo agrupamento',origem==antes)
    legado=deepcopy(origem);legado[0]['Carga Ilum. (VA)']=legado[0].pop('Carga Ilum. (W)')
    copias=preparar_cargas_projeto_neoenergia(legado)
    verifica('VA legado não convertido em W',copias[0]['Potência total conferida (W)'] is None and copias[0]['Previsão legada (VA)']==10000)
    verifica('W legado ausente bloqueia agrupamento',agrupar_cargas_projeto_neoenergia(legado,copias)['linhas'] is None)
    so_unit=deepcopy(origem);so_unit[0]['Pot. Unit. TUE (W)']=5500;so_unit[0].pop('Carga TUE (W)')
    verifica('Potência unitária W é multiplicada pela quantidade',next(r for r in preparar_cargas_projeto_neoenergia(so_unit) if r['ID']=='0:TUE')['Potência total conferida (W)']==11000)
    for nome,mutacao in [
        ('Quantidade fracionária',{'Quantidade conferida':1.5}),('Quantidade negativa',{'Quantidade conferida':-1}),
        ('Potência ausente',{'Potência total conferida (W)':None}),('Potência NaN',{'Potência total conferida (W)':float('nan')}),
        ('Potência infinita',{'Potência total conferida (W)':float('inf')}),('Quantidade zero com potência',{'Quantidade conferida':0}),
        ('Carga positiva como ausente',{'Grupo':'Ausente'}),('Classificação excluída',{'Grupo':'Fora do escopo'}),
        ('FP f ausente',{'FP para grupos d/f':None}),('FP f zero',{'FP para grupos d/f':0}),('FP f acima de 1',{'FP para grupos d/f':1.01}),
    ]:
        x=deepcopy(conferidos);next(r for r in x if r['ID']=='2:TUE').update(mutacao)
        verifica(nome+' bloqueia',agrupar_cargas_projeto_neoenergia(origem,x)['linhas'] is None)
    verifica('Linha omitida bloqueia',agrupar_cargas_projeto_neoenergia(origem,conferidos[:-1])['linhas'] is None)
    verifica('Linha duplicada bloqueia',agrupar_cargas_projeto_neoenergia(origem,conferidos+[conferidos[0]])['linhas'] is None)
    outra=deepcopy(origem)+[ambiente('Outro',1,1000,'Lavadora')]
    verifica('Conferência antiga não vale após mudança do projeto',agrupar_cargas_projeto_neoenergia(outra,conferidos)['linhas'] is None)
    dados_d=[ambiente('Serviço',1,1000,'Lavadora'),ambiente('Serviço 2',1,1000,'Secadora')]
    itens_d=preparar_cargas_projeto_neoenergia(dados_d)
    for r in itens_d:
        if r['Tipo']=='TUE':r['Grupo']='d';r['FP para grupos d/f']=.92 if r['ID']=='0:TUE' else .8
    grupo_d=agrupar_cargas_projeto_neoenergia(dados_d,itens_d)
    verifica('FP efetivo do grupo d respeita soma W/FP',math.isclose(2000/grupo_d['fp_d'],1000/.92+1000/.8))
    for i,p in enumerate(preparar_bloco_neoenergia('TESTE')):
        p['id']=str(i+1);p=preparar_territorio_neoenergia(p,'TESTE');p['regras']=registrar_entrada_neoenergia(p,'TESTE');p['regras']=registrar_demanda_neoenergia(p,'TESTE');original=deepcopy(p)
        r=calcular_ensaio_integrado_neoenergia(p,resultado['linhas'],'380/220 V',resultado['fp_d'],resultado['fp_f'],31,True,False,True)
        verifica(p['concessionaria']+': cópia do projeto reproduz 19,5 kVA / T6',r['status']=='ensaio_integrado' and math.isclose(r['demanda_total_kva'],19.5) and r['referencia']['categoria']=='T6')
        rejeita(p['concessionaria']+': consolidação sem confirmação recusada',lambda:consolidar_ensaio_neoenergia(p,'TESTE'))
        regras=consolidar_ensaio_neoenergia(p,'TESTE',True)
        verifica(p['concessionaria']+': consolidação não altera original',p==original)
        verifica(p['concessionaria']+': entradas preservadas',regras[CHAVE_ENTRADA]==p['regras'][CHAVE_ENTRADA] and regras[CHAVE_DEMANDA]==p['regras'][CHAVE_DEMANDA])
        verifica(p['concessionaria']+': sem ativação/cálculo liberados',regras[CHAVE_CONSOLIDACAO]['libera_calculo'] is False and p['status']=='RASCUNHO' and not regras['demanda'] and not regras['fornecimento'])
        consolidado=deepcopy(p);consolidado['regras']=regras
        verifica(p['concessionaria']+': repetir preserva consolidação',consolidar_ensaio_neoenergia(consolidado,'OUTRO',True)==regras)
        rejeita(p['concessionaria']+': ativo preservado',lambda:consolidar_ensaio_neoenergia(dict(p,status='ATIVO'),'TESTE',True))
    rejeita('Elektro fora da consolidação',lambda:consolidar_ensaio_neoenergia({'concessionaria':'Neoenergia Elektro'},'TESTE',True))
    return casos


def registro_demanda_neoenergia(perfil):
    if not perfil_bloco_neoenergia(perfil):raise ValueError('Distribuidora fora do bloco.')
    empresa=next(e for e in EMPRESAS if e['concessionaria'].casefold()==str(perfil['concessionaria']).strip().casefold())
    return dict(schema=1,concessionaria=empresa['concessionaria'],uf=empresa['uf'],
        documento=DOCUMENTO,revisao=REVISAO,fonte=empresa['pdf'],
        escopo='Ensaio isolado residencial individual trifásico; cargas mínimas previamente conferidas pelo responsável.',
        grupos=['a','b','c','d','e','f','i'],
        fatores=dict(
            tabela6=[.86,.75,.66,.59,.52,.45,.40,.35,.31,.27,.24],
            tabela7=[1,1,.84,.76,.70,.65,.60,.57,.54,.52,.49,.48,.46,.45,.44,.43,.42,.41,.40,.40,.39,.39,.39,.38,.38],
            tabela8=[1,.72,.62],
            tabela9=[{'ate':1,'fd':1},{'ate':4,'fd':.70},{'ate':6,'fd':.60},{'ate':None,'fd':.50}],
            tabela12_residencial=[{'ate':10,'fd':1},{'ate':20,'fd':.86},{'ate':30,'fd':.80},{'ate':40,'fd':.78},{'ate':50,'fd':.75},{'ate':75,'fd':.70},{'ate':100,'fd':.65},{'ate':None,'fd':.60}],
            tabela16=[1,.56,.47,.39]),
        referencias=['6.27, páginas 47–49: demanda em kVA e FP por grupo',
            'Tabela 6, página 65: FD sobre a carga total do grupo a; acima de 10 kW, 0,24',
            'Tabelas 7/8/9, página 66; Tabela 11, página 67, nota 1; Tabelas 12/16, página 68'],
        restricoes=[
            'Sem integração com projetos, enquadramento de entrada, corrente, disjuntor ou aprovação de instalação.',
            'Potência total do grupo: W para a/b/c/d/e/i; VA para f. Informar potência elétrica, não capacidade térmica em BTU/h.',
            'Grupo b reúne chuveiros, torneiras, aquecedores de passagem e ferros; somar quantidades e potências antes de aplicar o FD.',
            'Grupo d: secadoras/lavadoras/lava-louças/micro-ondas, FP 0,92 ou fabricante; grupo e neste ensaio: somente fornos elétricos, FP 1,00.',
            'Fogões bloqueados: item 6.27.5 remete à Tabela 9, mas a Tabela 10 é específica para fogões. Não resolver a divergência silenciosamente.',
            'Motores, soldas, equipamentos especiais, recarga veicular, climatização central, vestiários e usos coletivos/comerciais exigem outra análise.',
            'Dados mínimos do item 6.25.7 devem estar conferidos. Quantidade zero exige potência zero; dados ausentes não são assumidos como ausência de carga.',
            'Dados de placa/catálogo do ar condicionado prevalecem sobre estimativas da Tabela 11. Neste ensaio o total em VA deve estar previamente determinado.',
        ],libera_calculo=False)


def auditoria_demanda_neoenergia_registrada(perfil):
    if not perfil_bloco_neoenergia(perfil):return False
    r=((perfil or {}).get('regras') or {}).get(CHAVE_DEMANDA) or {}
    return r.get('referencia')==registro_demanda_neoenergia(perfil) and bool(r.get('responsavel')) and bool(r.get('registrado_em'))


def registrar_demanda_neoenergia(perfil,responsavel):
    # Reutiliza as validações documentais, sem alterar o registro de entrada salvo.
    registrar_entrada_neoenergia(perfil,responsavel)
    if not auditoria_entrada_neoenergia_registrada(perfil):raise ValueError('Registre primeiro as referências de entrada.')
    regras=deepcopy(perfil['regras'])
    if regras.get(CHAVE_DEMANDA):
        if not auditoria_demanda_neoenergia_registrada(perfil):raise ValueError('Auditoria de demanda divergente; preservada para conferência.')
        return regras
    regras[CHAVE_DEMANDA]=dict(referencia=registro_demanda_neoenergia(perfil),responsavel=str(responsavel).strip(),registrado_em=datetime.now(timezone.utc).isoformat())
    return regras


def cadastrar_auditorias_demanda_neoenergia(listar,salvar,responsavel):
    resultados=[]
    for empresa in EMPRESAS:
        try:
            encontrados=[p for p in listar() if str(p.get('concessionaria') or '').strip().casefold()==empresa['concessionaria'].casefold() and p.get('uf')==empresa['uf']]
            if len(encontrados)!=1 or not encontrados[0].get('id'):raise ValueError('Necessário um único perfil salvo por distribuidora/UF.')
            p=encontrados[0];regras=registrar_demanda_neoenergia(p,responsavel)
            if auditoria_demanda_neoenergia_registrada(p):resultado='JÁ REGISTRADA — PRESERVADA'
            else:
                if not salvar({'regras':regras},perfil_id=p['id']):raise ValueError('Banco não confirmou a gravação.')
                resultado='DEMANDA ISOLADA REGISTRADA EM RASCUNHO'
            resultados.append({'Distribuidora':empresa['concessionaria'],'Resultado':resultado})
        except Exception as exc:resultados.append({'Distribuidora':empresa['concessionaria'],'Resultado':'PENDENTE','Detalhe':str(exc)})
    return resultados


def dados_ensaio_demanda_neoenergia():
    return [
        {'Grupo':'a','Descrição':'Iluminação e tomadas','Quantidade':1,'Potência total':10000.0,'Unidade':'W'},
        {'Grupo':'b','Descrição':'Chuveiros, torneiras, passagem e ferros','Quantidade':2,'Potência total':11000.0,'Unidade':'W'},
        {'Grupo':'c','Descrição':'Boiler','Quantidade':0,'Potência total':0.0,'Unidade':'W'},
        {'Grupo':'d','Descrição':'Secadoras, lavadoras, lava-louças e micro-ondas','Quantidade':0,'Potência total':0.0,'Unidade':'W'},
        {'Grupo':'e','Descrição':'Somente forno elétrico','Quantidade':1,'Potência total':2000.0,'Unidade':'W'},
        {'Grupo':'f','Descrição':'Ar condicionado individual — potência elétrica aparente','Quantidade':2,'Potência total':3800.0,'Unidade':'VA'},
        {'Grupo':'i','Descrição':'Bombas e hidromassagem','Quantidade':0,'Potência total':0.0,'Unidade':'W'},
    ]


def calcular_ensaio_demanda_neoenergia(perfil,linhas,fp_d=.92,escopo_confirmado=False,cargas_fora_escopo=False):
    saida=dict(status='conferencia_tecnica',demanda_total_kva=None,memoria=[],aprovacao_automatica=False,motivo='')
    def pendencia(msg):saida['motivo']=msg;return saida
    if not auditoria_demanda_neoenergia_registrada(perfil):return pendencia('Referências de demanda ainda não registradas ou divergentes.')
    if escopo_confirmado is not True or cargas_fora_escopo is not False:return pendencia('Confirme o escopo residencial individual trifásico e a ausência das cargas excluídas.')
    if not isinstance(linhas,list) or len(linhas)!=7 or any(not isinstance(r,dict) for r in linhas):return pendencia('Informe os sete grupos; declare explicitamente zero para os ausentes.')
    grupos=[r.get('Grupo') for r in linhas]
    if any(not isinstance(g,str) for g in grupos) or sorted(grupos)!=['a','b','c','d','e','f','i']:return pendencia('Grupos ausentes, duplicados ou fora do escopo.')
    def numero(valor):
        if isinstance(valor,bool):return None
        try:valor=float(valor)
        except (TypeError,ValueError,OverflowError):return None
        return valor if math.isfinite(valor) and valor>=0 else None
    fatores=registro_demanda_neoenergia(perfil)['fatores'];memoria=[]
    def faixa(tabela,n):return next(r['fd'] for r in tabela if r['ate'] is None or n<=r['ate'])
    for r in sorted(linhas,key=lambda r:r['Grupo']):
        g=r['Grupo'];q=numero(r.get('Quantidade'));pot=numero(r.get('Potência total'))
        if q is None or not q.is_integer() or q>100000 or pot is None:return pendencia(f'Grupo {g}: quantidade inteira e potência finitas são obrigatórias.')
        q=int(q)
        if (q==0)!=(pot==0):return pendencia(f'Grupo {g}: quantidade e potência devem ser ambas zero ou ambas positivas.')
        unidade='VA' if g=='f' else 'W'
        if r.get('Unidade')!=unidade:return pendencia(f'Grupo {g}: unidade obrigatória {unidade}. Não informar BTU/h.')
        if g=='a' and q not in (0,1):return pendencia('Grupo a: use uma carga total agregada, com quantidade 1 ou zero se ausente.')
        fd=0.0;fp=None if g=='f' else 1.0
        if q:
            if g=='a':fd=fatores['tabela6'][min(10,max(0,math.ceil(pot/1000)-1))]
            elif g=='b':fd=fatores['tabela7'][min(q,25)-1]
            elif g=='c':fd=fatores['tabela8'][min(q,3)-1]
            elif g in ('d','e'):fd=faixa(fatores['tabela9'],q)
            elif g=='f':fd=faixa(fatores['tabela12_residencial'],q)
            elif g=='i':fd=fatores['tabela16'][min(q,4)-1]
            if g=='d':
                fp=numero(fp_d)
                if fp is None or not 0<fp<=1:return pendencia('Grupo d: FP deve ser positivo e até 1,00, conforme norma ou fabricante.')
        parcela=pot*fd/(fp if fp is not None else 1)/1000
        if not math.isfinite(parcela):return pendencia('Valor excede a capacidade numérica do ensaio.')
        memoria.append({'Grupo':g,'Quantidade':q,'Potência total':pot,'Unidade':unidade,'FD':fd,'FP':fp,'Demanda (kVA)':parcela})
    total=sum(r['Demanda (kVA)'] for r in memoria)
    if not math.isfinite(total) or total<=0:return pendencia('Demanda total deve ser positiva e finita.')
    saida.update(status='ensaio_isolado',demanda_total_kva=total,memoria=memoria,motivo='Ensaio dos grupos a+b+c+d+e+f+i. Grupos g/h/j e cargas excluídas não abrangidos. Não altera o projeto nem seleciona proteção ou categoria de entrada.')
    return saida


def testar_demanda_bloco_neoenergia():
    casos=[]
    def verifica(nome,ok):casos.append({'Caso':nome,'Resultado':'PASSOU' if ok else 'FALHOU'})
    def perto(a,b):return a is not None and math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10)
    def isolado(g,q,pot):
        linhas=dados_ensaio_demanda_neoenergia()
        for r in linhas:r.update(Quantidade=0,**{'Potência total':0.0})
        next(r for r in linhas if r['Grupo']==g).update(Quantidade=q,**{'Potência total':pot})
        return linhas
    perfis=[]
    for i,p in enumerate(preparar_bloco_neoenergia('TESTE')):
        p['id']=str(i+1);p=preparar_territorio_neoenergia(p,'TESTE');p['regras']=registrar_entrada_neoenergia(p,'TESTE');antes=deepcopy(p)
        p['regras']=registrar_demanda_neoenergia(p,'TESTE');perfis.append(p)
        nome=p['concessionaria']+': '
        verifica(nome+'registro canônico',auditoria_demanda_neoenergia_registrada(p))
        verifica(nome+'entrada e território preservados',p['regras'][CHAVE_ENTRADA]==antes['regras'][CHAVE_ENTRADA] and p['regras'][CHAVE_TERRITORIO]==antes['regras'][CHAVE_TERRITORIO])
        verifica(nome+'continua rascunho sem motor de projeto',p['status']=='RASCUNHO' and not p['regras']['demanda'] and not p['regras']['fornecimento'] and p['regras']['fonte_conferida'] is False)
        verifica(nome+'registro repetido preservado',registrar_demanda_neoenergia(p,'OUTRO')==p['regras'])
        r=calcular_ensaio_demanda_neoenergia(p,dados_ensaio_demanda_neoenergia(),escopo_confirmado=True)
        verifica(nome+'ensaio de referência 19,5 kVA',r['status']=='ensaio_isolado' and perto(r['demanda_total_kva'],19.5) and r['aprovacao_automatica'] is False)
        for kw,fd in [(1,.86),(1.001,.75),(2,.75),(2.001,.66),(3,.66),(3.001,.59),(4,.59),(4.001,.52),(5,.52),(5.001,.45),(6,.45),(6.001,.40),(7,.40),(7.001,.35),(8,.35),(8.001,.31),(9,.31),(9.001,.27),(10,.27),(10.001,.24)]:
            r=calcular_ensaio_demanda_neoenergia(p,isolado('a',1,kw*1000),escopo_confirmado=True)
            verifica(nome+f'Tabela 6: {kw} kW FD {fd}',perto(r['demanda_total_kva'],kw*fd))
        for g,q,pot,esperado in [('b',7,29000,17.4),('b',26,26000,9.88),('c',2,2000,1.44),('c',4,4000,2.48),('d',1,1000,1/.92),('d',4,4000,2.8/.92),('d',5,5000,3/.92),('d',7,7000,3.5/.92),('e',2,4000,2.8),('f',11,11000,9.46),('f',21,21000,16.8),('f',31,31000,24.18),('f',41,41000,30.75),('f',51,51000,35.7),('f',76,76000,49.4),('f',101,101000,60.6),('i',2,2000,1.12),('i',3,3000,1.41),('i',4,4000,1.56)]:
            r=calcular_ensaio_demanda_neoenergia(p,isolado(g,q,pot),escopo_confirmado=True)
            verifica(nome+f'grupo {g}, {q} aparelhos',perto(r['demanda_total_kva'],esperado))
        r=calcular_ensaio_demanda_neoenergia(p,isolado('d',1,1000),fp_d=.8,escopo_confirmado=True)
        verifica(nome+'FP fabricante prevalece no grupo d',perto(r['demanda_total_kva'],1.25))
        for q,pot in [(None,1000),(1.5,1000),(True,1000),(-1,1000),(1,float('nan')),(1,float('inf')),(0,1000),(1,0),(1,None)]:
            r=calcular_ensaio_demanda_neoenergia(p,isolado('b',q,pot),escopo_confirmado=True)
            verifica(nome+f'dados inválidos {q}/{pot}',r['demanda_total_kva'] is None)
        for fp in [0,-1,1.01,None,True,float('nan')]:
            verifica(nome+f'FP inválido {fp}',calcular_ensaio_demanda_neoenergia(p,isolado('d',1,1000),fp_d=fp,escopo_confirmado=True)['demanda_total_kva'] is None)
        verifica(nome+'escopo não confirmado bloqueado',calcular_ensaio_demanda_neoenergia(p,dados_ensaio_demanda_neoenergia())['demanda_total_kva'] is None)
        verifica(nome+'cargas excluídas bloqueadas',calcular_ensaio_demanda_neoenergia(p,dados_ensaio_demanda_neoenergia(),escopo_confirmado=True,cargas_fora_escopo=True)['demanda_total_kva'] is None)
        linhas=dados_ensaio_demanda_neoenergia();linhas[5]['Unidade']='BTU/h'
        verifica(nome+'BTU não tratado como potência elétrica',calcular_ensaio_demanda_neoenergia(p,linhas,escopo_confirmado=True)['demanda_total_kva'] is None)
        linhas=dados_ensaio_demanda_neoenergia();linhas[1]['Grupo']='a'
        verifica(nome+'grupo duplicado bloqueado',calcular_ensaio_demanda_neoenergia(p,linhas,escopo_confirmado=True)['demanda_total_kva'] is None)
        verifica(nome+'grupo ausente bloqueado',calcular_ensaio_demanda_neoenergia(p,dados_ensaio_demanda_neoenergia()[:-1],escopo_confirmado=True)['demanda_total_kva'] is None)
        linhas=isolado('a',0,0)
        verifica(nome+'todos zero não liberam ensaio',calcular_ensaio_demanda_neoenergia(p,linhas,escopo_confirmado=True)['demanda_total_kva'] is None)
        adulterado=deepcopy(p);adulterado['regras'][CHAVE_DEMANDA]['referencia']['fatores']['tabela6'][0]=1
        verifica(nome+'referência alterada bloqueada',calcular_ensaio_demanda_neoenergia(adulterado,dados_ensaio_demanda_neoenergia(),escopo_confirmado=True)['demanda_total_kva'] is None)
    db=deepcopy(perfis)
    for p in db:p['regras'].pop(CHAVE_DEMANDA)
    chamadas=[]
    def salvar(dados,perfil_id):
        chamadas.append(perfil_id);p=next(r for r in db if r['id']==perfil_id);p.update(deepcopy(dados));return [p]
    r=cadastrar_auditorias_demanda_neoenergia(lambda:db,salvar,'TESTE')
    verifica('Lote registra demanda isolada nos quatro',len(chamadas)==4 and all(x['Resultado']=='DEMANDA ISOLADA REGISTRADA EM RASCUNHO' for x in r))
    antes=deepcopy(db);r=cadastrar_auditorias_demanda_neoenergia(lambda:db,salvar,'OUTRO')
    verifica('Lote repetido não regrava',len(chamadas)==4 and db==antes)
    verifica('Elektro fora deste ensaio',calcular_ensaio_demanda_neoenergia({'concessionaria':'Neoenergia Elektro'},dados_ensaio_demanda_neoenergia(),escopo_confirmado=True)['demanda_total_kva'] is None)
    return casos


def calcular_ensaio_integrado_neoenergia(perfil,linhas,tensao,fp_d=.92,fp_f=None,corrente_max_a=None,
        escopo_confirmado=False,cargas_fora_escopo=False,dados_entrada_confirmados=False):
    """Demanda → faixa trifásica → comparação com corrente de fase declarada.

    O quociente S/(sqrt(3)*Vff) é apenas corrente equivalente balanceada;
    não substitui a corrente máxima das fases informada pelo responsável.
    Não altera configurações, projeto ou registros de auditoria.
    """
    saida=dict(status='conferencia_tecnica',demanda_total_kva=None,carga_instalada_kw=None,
        corrente_equivalente_balanceada_a=None,corrente_max_informada_a=None,
        referencia=None,memoria=[],aprovacao_automatica=False,motivo='')
    def pendencia(msg):saida['motivo']=msg;return saida
    if not territorio_neoenergia_registrado(perfil) or not auditoria_entrada_neoenergia_registrada(perfil):
        return pendencia('Vínculo territorial ou referência de entrada ausente/divergente.')
    if dados_entrada_confirmados is not True:
        return pendencia('Confirme a tensão FF/FN, os dados de potência elétrica e a corrente máxima de fase do ensaio.')
    tensoes={r['tensao_ff_fn'] for r in tabela_entrada_neoenergia(perfil)}
    if tensao not in tensoes:return pendencia('Tensão fora da tabela regional; não inferir pelo município.')
    demanda=calcular_ensaio_demanda_neoenergia(perfil,linhas,fp_d,escopo_confirmado,cargas_fora_escopo)
    if demanda['status']!='ensaio_isolado':return pendencia(demanda['motivo'])
    def positivo(x):
        if isinstance(x,bool):return None
        try:x=float(x)
        except (TypeError,ValueError,OverflowError):return None
        return x if math.isfinite(x) and x>0 else None
    corrente=positivo(corrente_max_a)
    if corrente is None:return pendencia('Informe corrente máxima de fase positiva e finita, previamente conferida. Não usar a média das fases.')
    memoria=demanda['memoria']
    total_va_f=next(r['Potência total'] for r in memoria if r['Grupo']=='f')
    fator_f=positivo(fp_f) if total_va_f>0 else 1.0
    if fator_f is None or fator_f>1:return pendencia('Ar condicionado em VA: informe FP de placa/catálogo, positivo e até 1,00, para apurar carga instalada em kW.')
    carga=(sum(r['Potência total'] for r in memoria if r['Unidade']=='W')+total_va_f*fator_f)/1000
    if not math.isfinite(carga) or not 0<carga<=75:return pendencia('Carga instalada fora do escopo positivo até 75 kW; análise específica necessária.')
    kva=demanda['demanda_total_kva']
    entrada=consultar_entrada_neoenergia(perfil,tensao,'Trifásico',carga,kva)
    if entrada['status']!='referencia_isolada':return pendencia(entrada['motivo'])
    referencia=entrada['referencia']
    vff={'220/127 V':220.0,'380/220 V':380.0}[tensao]
    equivalente=kva*1000/(math.sqrt(3)*vff)
    if corrente+0.005<equivalente:
        return pendencia('Corrente máxima informada inferior à equivalente balanceada da demanda. Confira unidade, tensão, demanda e correntes de fase (arredondamento admitido: 0,005 A).')
    if corrente>referencia['disjuntor_referencia_a']:
        return pendencia('Corrente máxima informada supera o disjuntor da categoria por demanda. Não subir categoria automaticamente; conferir distribuição das fases e condições de atendimento.')
    saida.update(status='ensaio_integrado',demanda_total_kva=kva,carga_instalada_kw=carga,
        corrente_equivalente_balanceada_a=equivalente,corrente_max_informada_a=corrente,
        referencia=deepcopy(referencia),memoria=deepcopy(memoria),
        motivo='Ensaio demanda → tabela de entrada concluído, com comparação da corrente máxima de fase declarada. Não verifica viabilidade, partida de motores, caixa homologada, alimentador do QDC, queda de tensão ou instalação; não libera perfil ou projeto.')
    return saida


def testar_integracao_bloco_neoenergia():
    casos=[]
    def verifica(nome,ok):casos.append({'Caso':nome,'Resultado':'PASSOU' if ok else 'FALHOU'})
    for i,p in enumerate(preparar_bloco_neoenergia('TESTE')):
        p['id']=str(i+1);p=preparar_territorio_neoenergia(p,'TESTE')
        p['regras']=registrar_entrada_neoenergia(p,'TESTE');p['regras']=registrar_demanda_neoenergia(p,'TESTE')
        nome=p['concessionaria']+': ';linhas=dados_ensaio_demanda_neoenergia();antes=deepcopy(p);antes_linhas=deepcopy(linhas)
        def calcular(**alteracoes):
            args=dict(perfil=p,linhas=linhas,tensao='380/220 V',fp_f=.9,corrente_max_a=31,escopo_confirmado=True,dados_entrada_confirmados=True)
            args.update(alteracoes);return calcular_ensaio_integrado_neoenergia(**args)
        r=calcular()
        verifica(nome+'demanda 19,5 kVA / T6 / 32 A',r['status']=='ensaio_integrado' and math.isclose(r['demanda_total_kva'],19.5) and r['referencia']['categoria']=='T6' and r['referencia']['disjuntor_referencia_a']==32)
        verifica(nome+'carga ativa 26,42 kW sem somar VA como W',math.isclose(r['carga_instalada_kw'],26.42))
        verifica(nome+'corrente equivalente separada da máxima',math.isclose(r['corrente_equivalente_balanceada_a'],19500/(math.sqrt(3)*380)) and r['corrente_max_informada_a']==31)
        verifica(nome+'entrada subterrânea 6 mm², sem alimentador QDC',r['referencia']['entrada_subterranea_cu_xlpe_hepr_fase_mm2']==6 and 'alimentador_qdc' not in r)
        verifica(nome+'sem alteração de dados/registro',p==antes and linhas==antes_linhas and r['aprovacao_automatica'] is False)
        for corrente in [0,-1,None,True,float('nan'),float('inf'),20,32.001,55]:
            falha=calcular(corrente_max_a=corrente)
            verifica(nome+f'corrente {corrente} bloqueia referência',falha['referencia'] is None and falha['demanda_total_kva'] is None)
        verifica(nome+'corrente no limite 32 A',calcular(corrente_max_a=32)['status']=='ensaio_integrado')
        for fp in [None,0,-1,1.01,True,float('nan')]:
            verifica(nome+f'FP do ar {fp} pendente',calcular(fp_f=fp)['referencia'] is None)
        for chave,valor in [('escopo_confirmado',False),('dados_entrada_confirmados',False),('cargas_fora_escopo',True),('tensao','127/220 V')]:
            verifica(nome+chave+' divergente bloqueado',calcular(**{chave:valor})['referencia'] is None)
        alteradas=deepcopy(linhas);alteradas[1]['Quantidade']=0
        verifica(nome+'inconsistência não reutiliza referência anterior',calcular(linhas=alteradas)['referencia'] is None)
        verifica(nome+'restauração recupera T6',calcular()['referencia']['categoria']=='T6')
        alteradas=deepcopy(linhas);alteradas[1]['Potência total']=80000
        verifica(nome+'carga acima de 75 kW bloqueada',calcular(linhas=alteradas)['referencia'] is None)
        sem_entrada=deepcopy(p);sem_entrada['regras'].pop(CHAVE_ENTRADA)
        verifica(nome+'auditoria de entrada ausente',calcular(perfil=sem_entrada)['referencia'] is None)
        sem_demanda=deepcopy(p);sem_demanda['regras'].pop(CHAVE_DEMANDA)
        verifica(nome+'auditoria de demanda ausente',calcular(perfil=sem_demanda)['referencia'] is None)
        sem_territorio=deepcopy(p);sem_territorio['municipios_atendidos']=[]
        verifica(nome+'território divergente',calcular(perfil=sem_territorio)['referencia'] is None)
        # Demanda 21,1 kVA cai na lacuna T6/T7; não arredondar.
        lacuna=deepcopy(linhas);lacuna[4]['Potência total']=3600
        verifica(nome+'lacuna 21,1 kVA bloqueada',calcular(linhas=lacuna,corrente_max_a=33)['referencia'] is None)
        if p['uf']=='BA':
            r220=calcular(tensao='220/127 V',corrente_max_a=55)
            verifica(nome+'220/127 usa T1 / 63 A / 16 mm²',r220['status']=='ensaio_integrado' and r220['referencia']['categoria']=='T1' and r220['referencia']['disjuntor_referencia_a']==63 and r220['referencia']['entrada_subterranea_cu_xlpe_hepr_fase_mm2']==16)
        else:verifica(nome+'220/127 fora da tabela bloqueado',calcular(tensao='220/127 V',corrente_max_a=55)['referencia'] is None)
    verifica('Elektro permanece fora deste ensaio',calcular_ensaio_integrado_neoenergia({'concessionaria':'Neoenergia Elektro'},[],'380/220 V')['referencia'] is None)
    return casos


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
