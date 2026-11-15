{#
  Os números de capa do país, recalculados do zero (não é soma de razões das UFs).
  Uma linha. É a tabela que o painel usa nos indicadores do topo e que o
  agente consulta para "quantos museus o Brasil tem".
#}

with m as (

    select
        count(*)                                            as qtd_museus_cadastrados,
        count(*) filter (where is_aberto)                   as qtd_museus_ativos,
        count(*) filter (where not is_aberto)               as qtd_museus_fechados,
        avg(indice_gestao) filter (where is_aberto)         as indice_gestao_medio,
        avg(case when possui_plano_museologico then 1.0 else 0.0 end)
            filter (where is_aberto and possui_plano_museologico is not null) as pct_plano_museologico,
        avg(case when dimensoes_acessibilidade = 0 then 1.0 else 0.0 end)
            filter (where is_aberto)                        as pct_sem_acessibilidade,
        max(dt)                                             as dt_referencia
    from {{ ref('int_museus__atual') }}

),

t as (

    select
        sum(populacao)                                      as populacao,
        count(*)                                            as qtd_municipios,
        count(*) filter (where tem_museu_ativo)             as qtd_municipios_com_museu,
        sum(populacao) filter (where not tem_museu_ativo)   as populacao_sem_museu
    from {{ ref('agg_cobertura_municipio') }}

),

p as (

    select count(*) as qtd_pontos_memoria from {{ ref('int_pontos_memoria__atual') }}

)

select
    m.dt_referencia,
    m.qtd_museus_cadastrados,
    m.qtd_museus_ativos,
    m.qtd_museus_fechados,
    p.qtd_pontos_memoria,
    t.populacao,
    t.qtd_municipios,
    t.qtd_municipios_com_museu,
    round(t.qtd_municipios_com_museu * 1.0 / t.qtd_municipios, 4)  as pct_municipios_com_museu,
    t.populacao_sem_museu,
    round(t.populacao_sem_museu * 1.0 / t.populacao, 4)            as pct_populacao_sem_museu,
    round(m.qtd_museus_ativos * 100000.0 / t.populacao, 2)         as museus_por_100k_hab,
    round(m.indice_gestao_medio, 1)                                as indice_gestao_medio,
    round(m.pct_plano_museologico, 4)                              as pct_plano_museologico,
    round(m.pct_sem_acessibilidade, 4)                             as pct_sem_acessibilidade
from m
cross join t
cross join p
