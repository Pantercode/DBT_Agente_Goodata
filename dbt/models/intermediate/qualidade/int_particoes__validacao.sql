{#
  Validação de cada partição do lake, antes de ela entrar nos marts.

  Grão: fonte x dt. Uma partição é `valida` ou fica em `quarentena`, com o
  motivo por extenso. Partição em quarentena não entra em nenhum modelo a
  jusante (int_museus__enriquecido filtra por aqui), então:
    - os marts continuam mostrando a última coleta coerente;
    - os testes bloqueantes dos marts passam, e a publicação acontece;
    - o painel avisa qual dia ficou de fora e por quê.
  Bloquear a publicação inteira por causa de uma coleta ruim (o comportamento
  anterior) deixava o painel parado; quarentena deixa ele atualizado com o que
  é confiável. Ver docs/decisoes/009.

  Regras (todas precisam passar):
    reconciliacao   linhas lidas = linhas que a ingestão diz ter gravado (_manifest)
    duplicidade     uma linha por item
    volume          entre -tol e +3*tol da maior contagem das 7 partições válidas anteriores
                    (o máximo, não a média: uma coleta ruim anterior não rebaixa a régua)
    completude      até 2% sem UF; até 5% sem status (museus)
    minimo          piso absoluto de sanidade

  Incremental: só valida partições novas (e a janela de reprocessamento). A
  régua de volume vem das partições já validadas em {{ this }}.
#}

{{ config(
    materialized = 'incremental',
    incremental_strategy = 'delete+insert',
    unique_key = ['fonte', 'dt'],
    on_schema_change = 'append_new_columns',
    pre_hook = "{% if is_incremental() %}delete from {{ this }} where (fonte, dt) not in (select entidade, dt from {{ source('tainacan', 'manifestos') }} where fonte = 'tainacan'){% endif %}"
) }}
{#- pre_hook: partição apagada do lake (reextração, simulação desfeita) sai também daqui. -#}

{% set tol = var('tolerancia_volume') %}

with ufs_validas as (

    select distinct uf_sigla from {{ ref('stg_ibge__municipios') }}

),

perfil as (

    select
        'museus'                                                            as fonte,
        dt,
        count(*)                                                            as registros_lidos,
        count(distinct museu_id)                                            as itens_distintos,
        count(*) filter (where uf_sigla is null or uf_sigla not in (select uf_sigla from ufs_validas)) as sem_uf,
        count(*) filter (where status_funcionamento is null)                as sem_status,
        count(*) filter (where nome_museu is null)                          as sem_nome
    from {{ ref('stg_tainacan__museus') }}
    where dt >= {{ inicio_janela() }}
    group by dt

    union all

    select
        'pontos_memoria', dt, count(*), count(distinct ponto_memoria_id),
        count(*) filter (where uf_sigla is null or uf_sigla not in (select uf_sigla from ufs_validas)),
        0,
        count(*) filter (where nome_ponto is null)
    from {{ ref('stg_tainacan__pontos_memoria') }}
    where dt >= {{ inicio_janela() }}
    group by dt

),

manifesto as (

    select entidade as fonte, dt, registros as registros_manifesto, total_informado_pela_origem
    from {{ source('tainacan', 'manifestos') }}
    where fonte = 'tainacan' and entidade in ('museus', 'pontos_memoria')

),

{% if is_incremental() %}
historico as (
    -- partições já validadas antes da janela: só as válidas servem de régua
    select fonte, dt, registros_lidos
    from {{ this }}
    where dt < {{ inicio_janela() }} and status = 'valida'
),
{% endif %}

serie as (

    select fonte, dt, registros_lidos, true as nova from perfil
    {% if is_incremental() %}
    union all
    select fonte, dt, registros_lidos, false as nova from historico
    {% endif %}

),

com_regua as (

    select
        *,
        max(registros_lidos) over (
            partition by fonte order by dt rows between 7 preceding and 1 preceding
        ) as regua_volume
    from serie

),

avaliada as (

    select
        p.fonte,
        p.dt,
        p.registros_lidos,
        p.itens_distintos,
        m.registros_manifesto,
        m.total_informado_pela_origem,
        r.regua_volume,
        round(p.sem_uf * 1.0 / nullif(p.registros_lidos, 0), 4)          as pct_sem_uf,
        round(p.sem_status * 1.0 / nullif(p.registros_lidos, 0), 4)      as pct_sem_status,

        m.registros_manifesto is not null
            and p.registros_lidos = m.registros_manifesto                as ok_reconciliacao,
        p.itens_distintos = p.registros_lidos                            as ok_duplicidade,
        r.regua_volume is null
            or p.registros_lidos between r.regua_volume * (1 - {{ tol }}) and r.regua_volume * (1 + 3 * {{ tol }})
                                                                         as ok_volume,
        p.sem_uf * 1.0 / nullif(p.registros_lidos, 0) <= 0.02
            and p.sem_status * 1.0 / nullif(p.registros_lidos, 0) <= 0.05
            and p.sem_nome = 0                                           as ok_completude,
        p.registros_lidos >= case p.fonte
            when 'museus' then {{ var('minimo_museus_particao') }}
            else {{ var('minimo_pontos_particao') }} end                 as ok_minimo

    from perfil as p
    left join manifesto as m on m.fonte = p.fonte and m.dt = p.dt
    inner join com_regua as r on r.fonte = p.fonte and r.dt = p.dt and r.nova

)

select
    fonte,
    dt,
    registros_lidos,
    itens_distintos,
    registros_manifesto,
    total_informado_pela_origem,
    regua_volume,
    pct_sem_uf,
    pct_sem_status,
    ok_reconciliacao,
    ok_duplicidade,
    ok_volume,
    ok_completude,
    ok_minimo,
    case
        when ok_reconciliacao and ok_duplicidade and ok_volume and ok_completude and ok_minimo then 'valida'
        else 'quarentena'
    end as status,
    nullif(concat_ws('; ',
        case when not ok_reconciliacao then 'lidas ' || registros_lidos || ' linhas, manifesto diz ' || coalesce(cast(registros_manifesto as varchar), 'nada') end,
        case when not ok_duplicidade then (registros_lidos - itens_distintos) || ' itens duplicados' end,
        case when not ok_volume then 'volume ' || registros_lidos || ' fora da faixa (régua ' || regua_volume || ')' end,
        case when not ok_completude then 'campos obrigatórios vazios (sem UF ' || round(pct_sem_uf * 100, 1) || '%)' end,
        case when not ok_minimo then 'abaixo do mínimo de sanidade' end
    ), '') as motivo_quarentena,
    {{ dbt.current_timestamp() }} as validado_em
from avaliada
