{#
  EXEMPLO CANÔNICO: MART (fato incremental particionado)
  Baseado em models/marts/core/fct_museus_diario.sql

  Grão: um registro por museu por dia de extração.
  Config por adapter: delete+insert no DuckDB, insert_overwrite no BigQuery.
  Sempre reprocessa uma janela (var janela_reprocessamento_dias): idempotente
  e sem full-refresh para corrigir dado retroativo.
#}

{% if target.type == 'bigquery' %}
    {{ config(
        materialized = 'incremental',
        incremental_strategy = 'insert_overwrite',
        partition_by = {'field': 'dt', 'data_type': 'date', 'granularity': 'day'},
        cluster_by = ['uf_sigla', 'municipio_id', 'museu_id'],
        require_partition_filter = true
    ) }}
{% else %}
    {{ config(materialized = 'incremental', incremental_strategy = 'delete+insert', unique_key = 'dt') }}
{% endif %}

with fonte as (

    select *
    from {{ ref('int_museus__enriquecido') }}
    {% if is_incremental() %}
    where dt >= (
        select {{ somar_dias('max(dt)', -var('janela_reprocessamento_dias')) }}
        from {{ this }}
    )
    {% endif %}

)

select
    dt,
    museu_id,
    municipio_id,
    uf_sigla,
    is_aberto,
    indice_gestao,
    1 as qtd_museus
from fonte
