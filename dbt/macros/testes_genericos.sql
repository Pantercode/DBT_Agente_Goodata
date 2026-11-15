{#
  Testes genéricos do projeto. Escritos aqui em vez de puxar dbt_utils /
  dbt_expectations para manter o projeto sem dependência de rede no CI e
  porque cada um tem uma semântica específica que vale documentar.
#}


{#
  Anomalia de volume: compara a contagem atual com a da última publicação.
  Falha se a variação passar da tolerância (padrão: var tolerancia_volume).
  Na primeira publicação não há histórico e o teste passa.
#}
{% test volume_estavel(model, tolerancia=none) %}
    {% set tol = tolerancia if tolerancia is not none else var('tolerancia_volume') %}
    {% set historico = adapter.get_relation(database=target.database, schema='observabilidade', identifier='historico_publicacoes') %}
    {% if historico is none %}
        select 1 as sem_historico where 1 = 0
    {% else %}
        with atual as (
            select count(*) as linhas from {{ model }}
        ),
        anterior as (
            select linhas
            from {{ historico }}
            where modelo = '{{ model.identifier }}'
            order by publicado_em desc
            limit 1
        )
        select
            atual.linhas as linhas_atual,
            anterior.linhas as linhas_ultima_publicacao,
            round(abs(atual.linhas - anterior.linhas) * 1.0 / nullif(anterior.linhas, 0), 4) as variacao
        from atual
        cross join anterior
        where abs(atual.linhas - anterior.linhas) > anterior.linhas * {{ tol }}
    {% endif %}
{% endtest %}


{# Proporção mínima de valores preenchidos numa coluna. #}
{% test cobertura_minima(model, column_name, minimo=0.95, onde=none) %}
    with base as (
        select {{ column_name }} as valor
        from {{ model }}
        {% if onde %}where {{ onde }}{% endif %}
    )
    select
        count(*) as linhas,
        count(valor) as preenchidas,
        round(count(valor) * 1.0 / nullif(count(*), 0), 4) as cobertura
    from base
    having count(valor) * 1.0 / nullif(count(*), 0) < {{ minimo }}
{% endtest %}


{# Unicidade de uma combinação de colunas (ex.: museu_id + dt no fato diário). #}
{% test unico_por(model, colunas) %}
    select {{ colunas | join(', ') }}, count(*) as ocorrencias
    from {{ model }}
    group by {{ colunas | join(', ') }}
    having count(*) > 1
{% endtest %}


{# Valores numéricos fora do intervalo plausível. #}
{% test no_intervalo(model, column_name, minimo=none, maximo=none) %}
    select {{ column_name }}
    from {{ model }}
    where {{ column_name }} is not null
      and (
            {% if minimo is not none %}{{ column_name }} < {{ minimo }}{% else %}false{% endif %}
         or {% if maximo is not none %}{{ column_name }} > {{ maximo }}{% else %}false{% endif %}
      )
{% endtest %}


{#
  SCD2 bem formada: para cada chave natural, no máximo uma versão aberta e
  nenhuma sobreposição de vigência.
#}
{% test scd2_valida(model, chave, inicio='valido_de', fim='valido_ate') %}
    with versoes as (
        select
            {{ chave }} as chave,
            {{ inicio }} as inicio,
            {{ fim }} as fim,
            lead({{ inicio }}) over (partition by {{ chave }} order by {{ inicio }}) as proximo_inicio
        from {{ model }}
    ),
    abertas as (
        select chave from versoes where fim is null group by chave having count(*) > 1
    )
    select chave, 'mais de uma versão vigente' as problema from abertas
    union all
    select chave, 'vigências sobrepostas' as problema
    from versoes
    where proximo_inicio is not null and (fim is null or fim >= proximo_inicio)
{% endtest %}


{#
  Reconciliação origem x staging: o número de registros da partição mais
  recente tem que bater com o `_manifest.json` gravado pela ingestão.
  Pega perda silenciosa de linhas (parse de JSON, filtro errado no staging).
#}
{% test reconcilia_com_manifest(model, fonte, entidade, coluna_particao='dt') %}
    {{ adapter.dispatch('teste_reconcilia_com_manifest', 'museus_br')(model, fonte, entidade, coluna_particao) }}
{% endtest %}

{% macro default__teste_reconcilia_com_manifest(model, fonte, entidade, coluna_particao) %}
    with manifest as (
        select cast(dt as date) as dt, registros
        from read_json('{{ var("caminho_lake") }}/{{ fonte }}/{{ entidade }}/dt=*/_manifest.json')
    ),
    staging as (
        select {{ coluna_particao }} as dt, count(*) as linhas
        from {{ model }}
        group by 1
    )
    select m.dt, m.registros as no_manifest, coalesce(s.linhas, 0) as no_staging
    from manifest m
    left join staging s on s.dt = m.dt
    where m.registros <> coalesce(s.linhas, 0)
{% endmacro %}

{# No BigQuery o manifest vira a tabela raw._manifests (carregada junto com o lake). #}
{% macro bigquery__teste_reconcilia_com_manifest(model, fonte, entidade, coluna_particao) %}
    with manifest as (
        select dt, registros from `{{ target.project }}.raw._manifests`
        where fonte = '{{ fonte }}' and entidade = '{{ entidade }}'
    ),
    staging as (
        select {{ coluna_particao }} as dt, count(*) as linhas from {{ model }} group by 1
    )
    select m.dt, m.registros as no_manifest, coalesce(s.linhas, 0) as no_staging
    from manifest m left join staging s using (dt)
    where m.registros <> coalesce(s.linhas, 0)
{% endmacro %}


{# SLA de atualização de um modelo: a partição mais recente não pode ter mais de N dias. #}
{% test atualizado_ha_no_maximo(model, column_name, dias=2) %}
    select max({{ column_name }}) as ultima_particao
    from {{ model }}
    having max({{ column_name }}) < {{ somar_dias(dbt.current_timestamp() ~ '::date' if target.type != 'bigquery' else 'current_date()', -dias) }}
{% endtest %}
