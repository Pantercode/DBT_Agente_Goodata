{#
  EXEMPLO CANÔNICO: INTERMEDIATE
  Baseado em models/intermediate/museus/int_museus__municipio_resolvido.sql

  Grão: o mesmo do staging de origem (museu x partição). Intermediate que muda
  o grão diz isso no nome (ex.: int_museus__agregado_por_uf).
  Faz: joins, regras de negócio, resolução de chaves. Registra COMO resolveu
  (coluna metodo_*), para o teste de cobertura e para auditoria.
#}

with museus as (

    select
        museu_id,
        dt,
        uf_sigla,
        municipio_nome,
        {{ normalizar_nome('municipio_nome') }} as municipio_chave
    from {{ ref('stg_tainacan__museus') }}

),

ibge as (

    select municipio_id, uf_sigla, municipio_chave
    from {{ ref('stg_ibge__municipios') }}

),

-- correções manuais vivem em seed versionado, nunca em CASE WHEN no SQL
de_para as (

    select
        upper(uf_sigla) as uf_sigla,
        {{ normalizar_nome('nome_no_cadastro') }} as municipio_chave,
        cast(municipio_id as integer) as municipio_id
    from {{ ref('de_para_municipios') }}

)

select
    m.museu_id,
    m.dt,
    coalesce(exato.municipio_id, dp.municipio_id) as municipio_id,
    case
        when exato.municipio_id is not null then 'exato'
        when dp.municipio_id is not null then 'de_para'
        else 'nao_resolvido'
    end as metodo_resolucao
from museus as m
left join ibge as exato
    on exato.uf_sigla = m.uf_sigla and exato.municipio_chave = m.municipio_chave
left join de_para as dp
    on dp.uf_sigla = m.uf_sigla and dp.municipio_chave = m.municipio_chave
