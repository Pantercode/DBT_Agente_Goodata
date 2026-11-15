{#
  Saúde da coleta, para o painel e o agente: cada partição de cada fonte,
  se entrou ou ficou em quarentena e por quê, e qual partição os números
  publicados estão usando.
#}

with validacao as (
    select * from {{ ref('int_particoes__validacao') }}
),

em_uso as (
    select fonte, max(dt) as dt_em_uso
    from validacao
    where status = 'valida'
    group by fonte
),

registros_fora as (
    select count(*) as qtd from {{ ref('int_museus__registros_quarentena') }}
)

select
    v.fonte,
    v.dt,
    v.status,
    v.motivo_quarentena,
    v.registros_lidos,
    v.registros_manifesto,
    v.regua_volume,
    v.pct_sem_uf,
    v.dt = u.dt_em_uso                                  as is_particao_em_uso,
    u.dt_em_uso,
    v.dt > u.dt_em_uso                                  as is_mais_nova_que_a_publicada,
    case when v.fonte = 'museus' and v.dt = u.dt_em_uso then (select qtd from registros_fora) else 0 end
                                                        as registros_fora_por_valor_invalido,
    v.validado_em
from validacao as v
left join em_uso as u on u.fonte = v.fonte
