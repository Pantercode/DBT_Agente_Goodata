{#
  Registros que ficaram fora dos marts por terem valor impossível, dentro de
  partições válidas. Só a partição válida mais recente: é o que está faltando
  "agora" no painel. Mesmas regras do filtro em int_museus__enriquecido.
#}

with ultima as (
    select max(dt) as dt
    from {{ ref('int_particoes__validacao') }}
    where fonte = 'museus' and status = 'valida'
),

ufs as (
    select distinct uf_sigla from {{ ref('stg_ibge__municipios') }}
)

select
    s.museu_id,
    s.dt,
    s.nome_museu,
    s.uf_sigla,
    concat_ws('; ',
        case when s.nome_museu is null then 'sem nome' end,
        case when s.status_funcionamento is null then 'sem status de funcionamento' end,
        case when s.uf_sigla is null or s.uf_sigla not in (select uf_sigla from ufs) then 'UF inválida' end
    ) as motivo
from {{ ref('stg_tainacan__museus') }} as s
where s.dt = (select dt from ultima)
  and (
        s.nome_museu is null
     or s.status_funcionamento is null
     or s.uf_sigla is null
     or s.uf_sigla not in (select uf_sigla from ufs)
  )
