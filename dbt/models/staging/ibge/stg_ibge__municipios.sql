{#
  Municípios do IBGE na partição mais recente.

  Diferente do Tainacan, aqui não interessa histórico: a malha municipal muda
  raramente e, quando muda (município novo), queremos a versão atual. Por isso o
  filtro `dt = max(dt)` já no staging.
#}

with fonte as (

    select * from {{ source('ibge', 'municipios') }}
    where dt = (select max(dt) from {{ source('ibge', 'municipios') }})

)

select
    cast(municipio_id as integer)           as municipio_id,
    nome                                    as municipio_nome,
    {{ normalizar_nome('nome') }}           as municipio_chave,
    microrregiao,
    mesorregiao,
    regiao_imediata,
    regiao_intermediaria,
    cast(uf_id as integer)                  as uf_id,
    uf_sigla,
    uf_nome,
    regiao_sigla,
    regiao_nome,
    dt
from fonte
