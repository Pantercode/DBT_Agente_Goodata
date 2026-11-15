{# Calendário diário exigido pelo dbt Semantic Layer (MetricFlow). #}

{{ config(materialized = 'table') }}

select cast(d as date) as date_day
from generate_series(date '2020-01-01', date '2030-12-31', interval 1 day) as t(d)
