{#
  Fato periódico (snapshot diário): um registro por museu por dia de extração.

  Carga incremental por partição, idempotente:
    - DuckDB:   delete+insert por `dt` (apaga e regrava as datas do lote)
    - BigQuery: insert_overwrite com partição diária em `dt`
  Nos dois casos cada execução reescreve as últimas N partições
  (var janela_reprocessamento_dias). Correção retroativa na origem entra sem
  full-refresh; rodar duas vezes o mesmo dia dá o mesmo resultado.

  No BigQuery a tabela exige filtro de partição: dashboard mal configurado no
  Looker Studio não consegue disparar full scan.
#}

{% if target.type == 'bigquery' %}
    {{ config(
        materialized = 'incremental',
        incremental_strategy = 'insert_overwrite',
        partition_by = {'field': 'dt', 'data_type': 'date', 'granularity': 'day'},
        cluster_by = ['uf_sigla', 'municipio_id', 'museu_id'],
        require_partition_filter = true,
        on_schema_change = 'append_new_columns'
    ) }}
{% else %}
    {{ config(
        materialized = 'incremental',
        incremental_strategy = 'delete+insert',
        unique_key = 'dt',
        on_schema_change = 'append_new_columns',
        pre_hook = "{% if is_incremental() %}delete from {{ this }} where dt not in (select dt from {{ ref('int_museus__enriquecido') }}){% endif %}"
    ) }}
{% endif %}

with fonte as (

    select *
    from {{ ref('int_museus__enriquecido') }}
    -- Só partições válidas chegam em int_museus__enriquecido. O pre_hook tira do
    -- fato qualquer partição que tenha saído de lá (foi para quarentena).
    where dt >= {{ inicio_janela() }}

),

versoes as (

    select museu_sk, museu_id, valido_de, valido_ate
    from {{ ref('dim_museu') }}

)

select
    f.dt,
    f.museu_id,
    v.museu_sk,
    cast(strftime(f.dt, '%Y%m%d') as integer)            as data_sk,
    f.municipio_id,
    f.uf_sigla,
    {{ hash_colunas(['f.esfera_administrativa']) }}     as esfera_sk,
    {{ hash_colunas(['f.tipo_museu']) }}                as tipo_museu_sk,
    {{ hash_colunas(['f.tematica']) }}                  as tematica_sk,
    f.is_aberto,
    f.indice_gestao,
    f.dimensoes_acessibilidade,
    f.qtd_pessoas_trabalham,
    f.qtd_terceirizados,
    f.qtd_bens_culturais,
    f.valor_entrada,
    f.criterios_respondidos,
    1 as qtd_museus
from fonte as f
left join versoes as v
    on  v.museu_id = f.museu_id
    and f.dt >= v.valido_de
    and (v.valido_ate is null or f.dt <= v.valido_ate)
