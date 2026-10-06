"""Relatório de leitura: contexto atual e evidências salvas, sem aprovação."""
import copy
import html
import json
from datetime import datetime, timezone
from atendimento_endereco_elektro import linhas_registro
from resumo_auditoria_elektro import resumir, resumir_projeto



def identificar_perfil(perfil, resultado):
    dados = {k: perfil.get(k) for k in ('id', 'documento', 'revisao', 'status', 'fonte_oficial')}
    dados['distribuidora'] = perfil.get('concessionaria') or perfil.get('distribuidora')
    partes = [str(v) for v in (dados['distribuidora'], dados['documento']) if v]
    if dados['revisao']:
        partes.append('Rev. ' + str(dados['revisao']))
    dados['nome'] = perfil.get('nome') or (' — '.join(partes) if partes else resultado.get('perfil_normativo'))
    return dados


def comparar_contextos(rede, perfil, resultado):
    identificado = identificar_perfil(perfil, resultado)
    candidata = ((resultado.get('enquadramento_elektro') or {}).get('candidato') or {}).get('modalidade')
    pares = [('Distribuidora', rede.get('concessionaria_manual') or rede.get('concessionaria'), identificado['distribuidora']),
        ('Perfil normativo (ID)', rede.get('perfil_normativo_id'), identificado['id']),
        ('Modalidade de fornecimento', rede.get('tipo_fornecimento'), candidata)]
    linhas = []
    for campo, atual, teste in pares:
        if atual is None or atual == '' or teste is None or teste == '':
            situacao = 'Comparação pendente — dado ausente'
        else:
            situacao = 'Correspondente' if str(atual).strip().casefold() == str(teste).strip().casefold() else 'Divergente — conferir antes da aplicação'
        linhas.append({'Campo': campo, 'Parâmetro do projeto': atual,
            'Perfil ou candidato da simulação': teste, 'Situação': situacao})
    return linhas


def consolidar(atendimento, rede, perfil, entrada, contexto, resultado, projeto):
    etapas = resumir_projeto(atendimento, rede, perfil, entrada, contexto, resultado)
    textos = json.dumps([atendimento, (entrada or {}).get('dados_ramal')], ensure_ascii=False).casefold()
    indicios = any(p in textos for p in ('fictíci', 'fictici', 'simulação', 'simulacao', 'teste de software', 'teste-'))
    return copy.deepcopy({
        'projeto': projeto, 'emitido_em_utc': datetime.now(timezone.utc).isoformat(),
        'escopo': 'Consolidação para conferência técnica; não constitui aprovação',
        'aprovado': False, 'homologado': False, 'dg_liberado': False, 'alimentador_liberado': False,
        'indicacao_dados_teste': indicios,
        'nota_dados': 'Há indicação textual de dados fictícios ou simulação nos registros.' if indicios else 'A origem real dos dados exige conferência; ausência de indicação textual não confirma autenticidade.',
        'perfil': identificar_perfil(perfil, resultado),
        'comparacao_contextos': comparar_contextos(rede, perfil, resultado),
        'rede_atual': rede, 'assinatura_contexto_projeto': contexto,
        'situacao_registros': etapas, 'auditoria_perfil': resumir(perfil),
        'demanda_atual': resultado, 'atendimento_salvo': atendimento, 'entrada_ramal_salva': entrada,
        'pendencias_demanda': resultado.get('pendencias') or [],
        'pendencias_enquadramento': (resultado.get('enquadramento_elektro') or {}).get('pendencias') or [],
        'bloqueios': ['Faixas conflitantes permanecem sujeitas a conferência técnica.',
            'Validação do atendimento e tensão por endereço permanece técnica.',
            'Sem liberação automática de DG, alimentador, cabos ou materiais.',
            'Conferência de ramal limitada aos critérios informados de capacidade e queda.',
            'Curto-circuito, atuação da proteção, neutro, PE e aterramento não verificados nesta etapa.']})


def gerar_html(relatorio):
    def esc(v):
        if v is None or v == '':return 'Não informado'
        if isinstance(v, bool):return 'Sim' if v else 'Não'
        return html.escape(str(v))
    def tabela(linhas):
        if not linhas:return '<p>Não registrado.</p>'
        cab=list(linhas[0])
        return '<table><thead><tr>'+''.join('<th>'+esc(k)+'</th>' for k in cab)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(l.get(k))+'</td>' for k in cab)+'</tr>' for l in linhas)+'</tbody></table>'
    def pares(d):return tabela([{'Campo':k,'Valor':v} for k,v in d.items()])
    r=relatorio;dem=r['demanda_atual'];aud=dem.get('enquadramento_elektro') or {};cand=aud.get('candidato') or {}
    partes=['<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Auditoria do projeto — Elektro</title><style>body{font:14px Arial,sans-serif;max-width:1000px;margin:32px auto;padding:0 20px;color:#182433}h1{font-size:25px}h2{font-size:19px;margin-top:28px}table{border-collapse:collapse;width:100%;margin:12px 0}th,td{border:1px solid #bbc5d0;padding:9px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#edf2f7}.aviso{background:#fff1d6;padding:14px}pre{white-space:pre-wrap;overflow-wrap:anywhere}@media print{body{margin:0;font-size:10pt}tr{break-inside:avoid}thead{display:table-header-group}}</style><body><h1>Auditoria do projeto — Neoenergia Elektro</h1>',
        pares({'Projeto':r['projeto'],'Emissão (UTC)':r['emitido_em_utc'],'Escopo':r['escopo']}),
        '<p class="aviso">'+esc(r['nota_dados'])+' Este relatório não aprova o projeto nem homologa o perfil.</p>',
        '<h2>Situação dos registros deste projeto</h2>',tabela(r['situacao_registros']),
        '<h2>Contexto do projeto e da simulação</h2>',
        '<p class="aviso">O perfil de teste e a categoria candidata não alteram a distribuidora, o perfil ativo ou a modalidade de fornecimento cadastrados no projeto. Diferenças abaixo exigem conferência antes de qualquer aplicação.</p>',
        tabela(r.get('comparacao_contextos') or []),
        '<h2>Perfil normativo usado na simulação</h2>',pares({'Identificação':r['perfil'].get('nome'),'Distribuidora':r['perfil'].get('distribuidora'),'ID':r['perfil'].get('id'),'Documento':r['perfil'].get('documento'),'Revisão':r['perfil'].get('revisao'),'Situação':r['perfil'].get('status'),'Fonte oficial':r['perfil'].get('fonte_oficial')}),
        '<h2>Parâmetros atuais do projeto</h2>',pares(r['rede_atual']),
        '<h2>Demanda e enquadramento atuais — teste</h2>',pares({'Situação da demanda':dem.get('status'),'Demanda aparente (kVA)':dem.get('demanda_aparente_kva'),'Situação do enquadramento':aud.get('status'),'Categoria candidata':cand.get('categoria'),'Modalidade candidata':cand.get('modalidade'),'Disjuntor de referência da tabela (A), sem aplicação como DG':cand.get('disjuntor_tabela_a')}),
        '<h2>Evidência de atendimento salva</h2>']
    at=r['atendimento_salvo']
    if at:
        partes += [pares({'Registro (UTC)':at.get('registrado_em_utc')}),tabela(linhas_registro(at))]
        partes += ['<p>'+esc(p)+'</p>' for p in at.get('pendencias') or []]
    else:partes+=['<p>Não registrado.</p>']
    en=r['entrada_ramal_salva']
    partes+=['<h2>Conferência de entrada e ramal salva — histórico</h2><p>A situação de atualização consta no resumo acima. Um registro desatualizado não representa o contexto atual.</p>']
    if en:
        partes += [pares({'Registro (UTC)':en.get('registrado_em_utc')}),pares(en.get('selecoes_informadas') or {}),pares(en.get('dados_ramal') or {}),tabela((en.get('verificacao_ramal') or {}).get('criterios') or [])]
        partes += ['<p>'+esc(p)+'</p>' for p in (en.get('verificacao_ramal') or {}).get('pendencias') or []]
    else:partes+=['<p>Não salva.</p>']
    partes+=['<h2>Pendências da demanda e enquadramento atuais</h2>']
    pend=r['pendencias_demanda']+r['pendencias_enquadramento']
    partes+=['<p>'+esc(p)+'</p>' for p in pend] if pend else ['<p>Nenhuma pendência listada neste cálculo; permanecem os bloqueios técnicos abaixo.</p>']
    partes+=['<h2>Evidências e pendências do perfil</h2>',tabela(r['auditoria_perfil']),'<h2>Bloqueios e limites da conferência</h2>']
    partes+=['<p>'+esc(p)+'</p>' for p in r['bloqueios']]
    partes+=['<h2>Memória completa da demanda atual</h2><pre>'+html.escape(json.dumps(dem,ensure_ascii=False,indent=2,default=str))+'</pre></body></html>']
    return ''.join(partes)
