{#
  Tabela-ponte museu x tipologia de acervo (foto atual).

  `peso` = 1 / nº de tipologias do museu. Somando `peso` em vez de contar
  linhas, o total de museus por tipologia fecha com o total de museus (um
  museu com 3 tipologias conta 1/3 em cada). Contar linhas responde outra
  pergunta: "quantos museus têm acervo de X".
#}

with atual as (
    select museu_id, tipologias_acervo, {{ tamanho_lista('tipologias_acervo') }} as n
    from {{ ref('int_museus__atual') }}
    where {{ tamanho_lista('tipologias_acervo') }} > 0
),

explodida as (
    select museu_id, n, unnest(tipologias_acervo) as tipologia
    from atual
)

select
    e.museu_id,
    t.tipologia_sk,
    e.tipologia,
    round(1.0 / e.n, 6)     as peso
from explodida as e
inner join {{ ref('dim_tipologia_acervo') }} as t
    on t.tipologia = e.tipologia
