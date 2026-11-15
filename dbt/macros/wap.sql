{#
  Write-Audit-Publish.

  WRITE   dbt build materializa os marts em `auditoria`.
  AUDIT   os testes rodam contra `auditoria` (o build já faz isso em ordem).
  PUBLISH esta macro copia `auditoria` -> `publicado`, mas só se a última
          execução do build não tiver nenhuma falha bloqueante.

  Se o audit falhar, `publicado` continua com a última versão boa. Consumidor
  nunca vê dado que não passou nos testes.

  A checagem de falhas aqui é redundante com o circuit breaker do orquestrador
  (orquestracao/pipeline.py) de propósito: quem rodar
  `dbt run-operation publicar_marts` na mão também é barrado.

  Uso:
      dbt run-operation publicar_marts
      dbt run-operation publicar_marts --args '{forcar: true}'   # ignora o breaker (registrado no log)
#}

{% macro publicar_marts(forcar=false) %}
    {% if not execute %}{{ return('') }}{% endif %}

    {% set modelos = [] %}
    {% for no in graph.nodes.values() %}
        {% if no.resource_type == 'model' and no.config.meta.get('publicar') and no.config.materialized != 'ephemeral' %}
            {% do modelos.append(no) %}
        {% endif %}
    {% endfor %}
    {% if modelos | length == 0 %}
        {{ exceptions.raise_compiler_error("Nenhum modelo com meta.publicar = true.") }}
    {% endif %}

    {# --- circuit breaker --- #}
    {% set ultima_execucao %}
        select invocation_id
        from observabilidade.resultados
        where comando = 'build'
        order by executado_em desc
        limit 1
    {% endset %}
    {% set inv = run_query(ultima_execucao).columns[0].values() %}
    {% if inv | length == 0 %}
        {{ exceptions.raise_compiler_error("Nenhum `dbt build` registrado em observabilidade.resultados. Rode o build antes de publicar.") }}
    {% endif %}

    {% set bloqueios_sql %}
        select nome, status, coalesce(falhas, 0) as falhas
        from observabilidade.resultados
        where invocation_id = '{{ inv[0] }}'
          and (
                status in ('error', 'runtime error')
             or (status = 'fail' and (bloqueante or severidade = 'ERROR'))
             or status = 'skipped'
          )
    {% endset %}
    {% set bloqueios = run_query(bloqueios_sql) %}

    {% if bloqueios.rows | length > 0 %}
        {% for b in bloqueios.rows %}
            {{ log("  bloqueio: " ~ b[0] ~ " (" ~ b[1] ~ ", " ~ b[2] ~ " linhas)", info=true) }}
        {% endfor %}
        {% if not forcar %}
            {{ exceptions.raise_compiler_error(
                "Circuit breaker: " ~ (bloqueios.rows | length) ~ " falha(s) bloqueante(s) no build " ~ inv[0]
                ~ ". `publicado` mantém a versão anterior.") }}
        {% else %}
            {{ log("ATENÇÃO: publicação forçada com falhas bloqueantes.", info=true) }}
        {% endif %}
    {% endif %}

    {# --- publish --- #}
    {% do adapter.create_schema(api.Relation.create(database=target.database, schema='publicado')) %}
    {{ adapter.dispatch('publicar_relacoes', 'museus_br')(modelos) }}

    {% set historico %}
        insert into observabilidade.historico_publicacoes
        {% for no in modelos %}
            select '{{ invocation_id }}', {{ dbt.current_timestamp() }}, '{{ no.alias or no.name }}', count(*)
            from publicado.{{ no.alias or no.name }}
            {{ "union all" if not loop.last }}
        {% endfor %}
    {% endset %}
    {% do run_query(historico) %}

    {{ log("Publicados " ~ (modelos | length) ~ " marts a partir do build " ~ inv[0], info=true) }}
{% endmacro %}


{# DuckDB: cópia física dentro de uma transação. Ou publica tudo, ou nada. #}
{% macro default__publicar_relacoes(modelos) %}
    {% set sql %}
        begin transaction;
        {% for no in modelos %}
        create or replace table publicado.{{ no.alias or no.name }} as
            select * from {{ no.schema }}.{{ no.alias or no.name }};
        {% endfor %}
        commit;
    {% endset %}
    {% do run_query(sql) %}
{% endmacro %}


{#
  BigQuery: CLONE é metadata-only (sem custo de bytes processados nem de
  storage até os dados divergirem). Multi-statement transaction garante o
  "tudo ou nada" entre os marts, que é o que mantém os KPIs consistentes entre si.
  Partição e cluster são herdados da tabela de origem.
#}
{% macro bigquery__publicar_relacoes(modelos) %}
    {% set sql %}
        begin transaction;
        {% for no in modelos %}
        create or replace table `{{ target.project }}.publicado.{{ no.alias or no.name }}`
            clone `{{ target.project }}.{{ no.schema }}.{{ no.alias or no.name }}`;
        {% endfor %}
        commit transaction;
    {% endset %}
    {% do run_query(sql) %}
{% endmacro %}
