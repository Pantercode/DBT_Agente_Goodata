{#
  Dimensão de calendário (role-playing: data do snapshot, início/fim de
  vigência, data de cadastro). Rótulos em português, para BI não precisar
  formatar data.
#}

{{ config(materialized = 'table') }}

{% set meses = ['janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro'] %}
{% set dias = ['domingo','segunda-feira','terça-feira','quarta-feira','quinta-feira','sexta-feira','sábado'] %}

with dias as (
    select date_day as data from {{ ref('metricflow_time_spine') }}
)

select
    data,
    cast(strftime(data, '%Y%m%d') as integer)                       as data_sk,
    extract(year from data)                                         as ano,
    extract(quarter from data)                                      as trimestre,
    extract(month from data)                                        as mes,
    case extract(month from data)
        {% for m in meses %}when {{ loop.index }} then '{{ m }}' {% endfor %}
    end                                                             as nome_mes,
    strftime(data, '%Y-%m')                                         as ano_mes,
    extract(day from data)                                          as dia,
    extract(dow from data)                                          as dia_semana,
    case extract(dow from data)
        {% for d in dias %}when {{ loop.index0 }} then '{{ d }}' {% endfor %}
    end                                                             as nome_dia_semana,
    extract(dow from data) in (0, 6)                                as is_fim_de_semana,
    extract(week from data)                                         as semana_iso,
    cast(floor(extract(year from data) / 10) * 10 as integer)       as decada
from dias
