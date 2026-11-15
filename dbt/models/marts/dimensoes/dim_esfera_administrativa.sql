{#
  Esfera administrativa como aparece no cadastro, com a classificação do seed
  (natureza, nível de governo, subtipo privado). Inclui "Não informada" para
  a FK do fato nunca ficar órfã.
#}

with seed as (
    select esfera_administrativa, natureza, nivel_governo, subtipo_privado
    from {{ ref('classificacao_esfera') }}
),

com_nao_informada as (
    select * from seed
    union all
    select 'Não informada', 'Não informada', null, null
)

select
    {{ hash_colunas(['esfera_administrativa']) }}   as esfera_sk,
    esfera_administrativa,
    natureza                                        as natureza_administrativa,
    nivel_governo,
    subtipo_privado,
    case natureza when 'Pública' then 1 when 'Privada' then 2 when 'Mista' then 3 else 9 end as ordem
from com_nao_informada
