{#
  Primeira partição que um modelo incremental precisa (re)processar.

    - var `reprocessar_desde` definida  -> essa data (backfill pontual, sem full-refresh)
    - execução incremental              -> última partição já processada - janela
    - primeira carga / full-refresh      -> sem limite

  Uso: where dt >= {{ inicio_janela('dt') }}
  O filtro em `dt` vira partition pruning no lake: o DuckDB só abre as pastas
  dt= do intervalo, e no BigQuery a external table só lê as partições pedidas.
#}
{% macro inicio_janela(coluna_watermark='dt') %}
    {%- if var('reprocessar_desde', none) -%}
        date '{{ var("reprocessar_desde") }}'
    {%- elif is_incremental() -%}
        (select coalesce({{ somar_dias('max(' ~ coluna_watermark ~ ')', -var('janela_reprocessamento_dias')) }}, date '1900-01-01') from {{ this }})
    {%- else -%}
        date '1900-01-01'
    {%- endif -%}
{% endmacro %}
