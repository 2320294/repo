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
                'Tabela 1, Enel SP: bifásico acima de 12 até 20 kW e trifásico aéreo '
                '127/220 V a partir de 15,1 até 75 kW; sobreposição de modalidades '
                '15,1–20 kW exige análise, sem escolha automática. '
                'Item 7.8.2: demanda sob responsabilidade do responsável técnico. '
                'Metodologia de demanda e tabelas de entrada ainda em auditoria; não ativar. '
                'Fontes: ' + FONTE_PORTAL + ' ; ' + FONTE_MUNICIPIOS
            ),
        },
    )


def pendencias_ativacao_enel_sp(perfil):
    pendencias = ['Concluir a auditoria da demanda e das tabelas de entrada Enel SP e implementar/testar o motor específico antes de publicar.']
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
