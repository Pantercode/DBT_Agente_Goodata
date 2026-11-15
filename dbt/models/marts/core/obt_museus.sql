{#
  One Big Table: o estado atual de cada museu numa linha, com os grupos de
  atributos aninhados em STRUCT e as respostas multivaloradas em ARRAY.

  Para quê: consulta exploratória e o agente de IA. Uma linha por museu, sem
  join, e o aninhamento mantém o grão (um ARRAY de recursos de acessibilidade
  não multiplica linhas como um join com tabela-ponte faria). No BigQuery isso
  vira RECORD / REPEATED e só as subcolunas lidas são cobradas.

  O GoodData não lê campos aninhados; ele usa dim_* + fct_* e os agg_*.
#}

{{ config(
    cluster_by = ['uf_sigla', 'municipio_id'] if target.type == 'bigquery' else none
) }}

select
    museu_id,
    codigo_ibram,
    nome_museu,
    tipo_museu,
    tematica,
    status_funcionamento,
    is_aberto,
    natureza_administrativa,
    esfera_administrativa,
    uf_sigla,
    regiao_sigla,
    municipio_id,
    municipio_nome,
    ano_abertura,

    {{ struct_de({
        'logradouro_bairro': 'bairro',
        'cep': 'cep',
        'latitude': 'latitude',
        'longitude': 'longitude',
        'uf_cadastro': 'uf_sigla_cadastro',
        'uf_divergente': 'is_uf_divergente',
        'metodo_resolucao': 'metodo_resolucao_municipio'
    }) }} as localizacao,

    {{ struct_de({
        'indice': 'indice_gestao',
        'faixa': 'faixa_gestao',
        'plano_museologico': 'possui_plano_museologico',
        'regimento_interno': 'possui_regimento_interno',
        'politica_aquisicao': 'possui_politica_aquisicao',
        'politica_descarte': 'possui_politica_descarte',
        'documentacao_acervo': 'atende_documentacao_acervo',
        'criterios_respondidos': 'criterios_respondidos'
    }) }} as gestao,

    {{ struct_de({
        'pessoas_trabalham': 'qtd_pessoas_trabalham',
        'terceirizados': 'qtd_terceirizados',
        'voluntarios': 'possui_voluntarios',
        'estagiarios': 'possui_estagiarios'
    }) }} as equipe,

    {{ struct_de({
        'dimensoes_atendidas': 'dimensoes_acessibilidade',
        'recursos_fisicos': 'recursos_acessibilidade_fisica',
        'recursos_sensoriais': 'recursos_acessibilidade_sensorial',
        'recursos_turista': 'recursos_turista_estrangeiro'
    }) }} as acessibilidade,

    {{ struct_de({
        'entrada_cobrada': 'entrada_cobrada',
        'valor_entrada': 'valor_entrada',
        'visitas_mediadas': 'visitas_mediadas',
        'publicos_educativos': 'publicos_atividades_educativas',
        'possui_site': 'possui_site',
        'possui_redes_sociais': 'possui_redes_sociais'
    }) }} as visitacao,

    qtd_bens_culturais,
    tipologias_acervo,
    url_cadastro,
    atualizado_na_origem_em,
    dt as dt_referencia

from {{ ref('int_museus__atual') }}
