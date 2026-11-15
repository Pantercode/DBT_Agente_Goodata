{#
  Cobertura museal por município: todos os 5.571, inclusive os sem museu.

  "Museu ativo" = status de funcionamento "Aberto" no cadastro. É a mesma
  definição em todo o projeto (ver docs/metricas.md); museu fechado conta no
  total cadastrado, não na cobertura.
#}

with museus as (

    select
        municipio_id,
        count(*)                                        as qtd_museus_cadastrados,
        count(*) filter (where is_aberto)               as qtd_museus_ativos,
        count(*) filter (where is_aberto and natureza_administrativa = 'Pública') as qtd_museus_ativos_publicos,
        avg(indice_gestao) filter (where is_aberto)     as indice_gestao_medio
    from {{ ref('int_museus__atual') }}
    where municipio_id is not null
    group by municipio_id

)

select
    d.municipio_id,
    d.municipio_nome,
    d.municipio_rotulo,
    d.uf_sigla,
    d.regiao_sigla,
    d.regiao_nome,
    d.faixa_populacional,
    d.populacao,
    coalesce(m.qtd_museus_cadastrados, 0)           as qtd_museus_cadastrados,
    coalesce(m.qtd_museus_ativos, 0)                as qtd_museus_ativos,
    coalesce(m.qtd_museus_ativos_publicos, 0)       as qtd_museus_ativos_publicos,
    round(m.indice_gestao_medio, 1)                 as indice_gestao_medio,
    coalesce(m.qtd_museus_ativos, 0) > 0            as tem_museu_ativo,
    round(coalesce(m.qtd_museus_ativos, 0) * 100000.0 / nullif(d.populacao, 0), 2) as museus_por_100k_hab,
    case
        when coalesce(m.qtd_museus_ativos, 0) = 0 then 'Sem museu ativo'
        when coalesce(m.qtd_museus_ativos, 0) = 1 then '1 museu'
        when m.qtd_museus_ativos <= 5            then '2 a 5 museus'
        else 'Mais de 5 museus'
    end                                             as classe_cobertura
from {{ ref('dim_municipio') }} as d
left join museus as m
    on m.municipio_id = d.municipio_id
