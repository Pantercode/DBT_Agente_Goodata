with fonte as (

    select * from {{ source('ibge', 'populacao') }}
    where dt = (select max(dt) from {{ source('ibge', 'populacao') }})

)

select
    cast(municipio_id as integer)   as municipio_id,
    cast(ano as integer)            as ano_referencia,
    -- SIDRA usa "-", "..." e "X" para ausente / sigiloso.
    try_cast(populacao as bigint)   as populacao
from fonte
where cast(ano as integer) = {{ var('ano_populacao') }}
