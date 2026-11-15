{#
  Painel-síntese por UF. Uma linha por UF (27).

  Todas as razões são calculadas aqui, uma vez. Ferramenta de BI que somar
  `museus_por_100k_hab` entre UFs está errada; para totais nacionais use
  agg_cobertura_brasil (ou as métricas do semantic layer, que recalculam
  numerador/denominador).
#}

with municipios as (

    select
        uf_sigla,
        max(regiao_sigla)                                           as regiao_sigla,
        max(regiao_nome)                                            as regiao_nome,
        count(*)                                                    as qtd_municipios,
        count(*) filter (where tem_museu_ativo)                     as qtd_municipios_com_museu,
        sum(populacao)                                              as populacao,
        -- coalesce: no DF todo município (só um) tem museu e o sum filtrado vira null
        coalesce(sum(populacao) filter (where not tem_museu_ativo), 0) as populacao_sem_museu,
        sum(qtd_museus_cadastrados)                                 as qtd_museus_cadastrados,
        sum(qtd_museus_ativos)                                      as qtd_museus_ativos
    from {{ ref('agg_cobertura_municipio') }}
    group by uf_sigla

),

museus as (

    select
        uf_sigla,
        avg(indice_gestao)                                          as indice_gestao_medio,
        avg(case when possui_plano_museologico then 1.0 else 0.0 end) filter (where possui_plano_museologico is not null) as pct_plano_museologico,
        avg(case when qtd_recursos_acess_fisica > 0 then 1.0 else 0.0 end) as pct_com_acessibilidade_fisica,
        avg(case when qtd_recursos_acess_sensorial > 0 then 1.0 else 0.0 end) as pct_com_acessibilidade_sensorial,
        avg(case when natureza_administrativa = 'Pública' then 1.0 else 0.0 end) as pct_publicos
    from {{ ref('int_museus__atual') }}
    where is_aberto
    group by uf_sigla

),

pontos as (

    select uf_sigla, count(*) as qtd_pontos_memoria
    from {{ ref('int_pontos_memoria__atual') }}
    group by uf_sigla

)

select
    mu.uf_sigla,
    mu.regiao_sigla,
    mu.regiao_nome,
    mu.populacao,
    mu.qtd_municipios,
    mu.qtd_municipios_com_museu,
    round(mu.qtd_municipios_com_museu * 1.0 / mu.qtd_municipios, 4)    as pct_municipios_com_museu,
    mu.qtd_museus_cadastrados,
    mu.qtd_museus_ativos,
    coalesce(p.qtd_pontos_memoria, 0)                                  as qtd_pontos_memoria,
    round(mu.qtd_museus_ativos * 100000.0 / mu.populacao, 2)           as museus_por_100k_hab,
    mu.populacao_sem_museu,
    round(mu.populacao_sem_museu * 1.0 / mu.populacao, 4)              as pct_populacao_sem_museu,
    round(m.indice_gestao_medio, 1)                                    as indice_gestao_medio,
    round(m.pct_plano_museologico, 4)                                  as pct_plano_museologico,
    round(m.pct_com_acessibilidade_fisica, 4)                          as pct_com_acessibilidade_fisica,
    round(m.pct_com_acessibilidade_sensorial, 4)                       as pct_com_acessibilidade_sensorial,
    round(m.pct_publicos, 4)                                           as pct_museus_publicos,
    rank() over (order by mu.qtd_museus_ativos * 1.0 / mu.populacao desc) as ranking_museus_per_capita
from municipios as mu
left join museus as m on m.uf_sigla = mu.uf_sigla
left join pontos as p on p.uf_sigla = mu.uf_sigla
