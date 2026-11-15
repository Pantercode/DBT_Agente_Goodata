{#
  Frequência de cada recurso de acessibilidade, por UF.

  Aqui é onde o ARRAY vira linhas (UNNEST). A explosão acontece depois da
  agregação de grão museu, então não há risco de contar museu duas vezes no
  denominador: `qtd_museus_ativos_uf` vem de uma CTE separada.
#}

with museus as (

    select museu_id, uf_sigla, recursos_acessibilidade_fisica, recursos_acessibilidade_sensorial
    from {{ ref('int_museus__atual') }}
    where is_aberto

),

recursos as (

    select museu_id, uf_sigla, 'Física' as dimensao, unnest(recursos_acessibilidade_fisica) as recurso
    from museus
    union all
    select museu_id, uf_sigla, 'Sensorial' as dimensao, unnest(recursos_acessibilidade_sensorial) as recurso
    from museus

),

denominador as (

    select uf_sigla, count(*) as qtd_museus_ativos_uf
    from museus
    group by uf_sigla

)

select
    r.uf_sigla,
    r.dimensao,
    r.recurso,
    count(distinct r.museu_id)                                          as qtd_museus_com_recurso,
    d.qtd_museus_ativos_uf,
    round(count(distinct r.museu_id) * 1.0 / d.qtd_museus_ativos_uf, 4) as pct_museus_com_recurso
from recursos as r
inner join denominador as d on d.uf_sigla = r.uf_sigla
group by r.uf_sigla, r.dimensao, r.recurso, d.qtd_museus_ativos_uf
