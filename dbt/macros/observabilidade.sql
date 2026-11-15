{#
  Observabilidade dentro do próprio warehouse.

  Toda execução do dbt grava o resultado de cada nó (modelo, teste, seed) em
  observabilidade.resultados. Isso alimenta três coisas:
    1. o circuit breaker do publish (publicar_marts lê daqui);
    2. a aba "Qualidade" do painel;
    3. a ferramenta `status_qualidade` do agente.

  Os tipos vêm de dbt.type_* para o DDL funcionar no DuckDB e no BigQuery.
#}

{% macro criar_tabelas_observabilidade() %}
    {% if not execute %}{{ return('') }}{% endif %}
    {% set schema = 'observabilidade' %}
    {% do adapter.create_schema(api.Relation.create(database=target.database, schema=schema)) %}

    {% set ddl_resultados %}
        create table if not exists {{ schema }}.resultados (
            invocation_id   {{ dbt.type_string() }},
            executado_em    {{ dbt.type_timestamp() }},
            comando         {{ dbt.type_string() }},
            unique_id       {{ dbt.type_string() }},
            tipo            {{ dbt.type_string() }},
            nome            {{ dbt.type_string() }},
            modelo_alvo     {{ dbt.type_string() }},
            status          {{ dbt.type_string() }},
            severidade      {{ dbt.type_string() }},
            bloqueante      {{ dbt.type_boolean() }},
            falhas          {{ dbt.type_int() }},
            tempo_s         {{ dbt.type_float() }},
            mensagem        {{ dbt.type_string() }}
        )
    {% endset %}
    {% do run_query(ddl_resultados) %}

    {% set ddl_publicacoes %}
        create table if not exists {{ schema }}.historico_publicacoes (
            invocation_id   {{ dbt.type_string() }},
            publicado_em    {{ dbt.type_timestamp() }},
            modelo          {{ dbt.type_string() }},
            linhas          {{ dbt.type_int() }}
        )
    {% endset %}
    {% do run_query(ddl_publicacoes) %}
    {{ return('') }}
{% endmacro %}


{% macro _texto_sql(valor, limite=500) -%}
    {%- if valor is none -%}null{%- else -%}'{{ (valor | string)[:limite] | replace("'", "''") | replace("\n", " ") }}'{%- endif -%}
{%- endmacro %}


{% macro registrar_resultados(results) %}
    {% if not execute or results | length == 0 %}{{ return('') }}{% endif %}

    {% set linhas = [] %}
    {% for r in results %}
        {% set no = r.node %}
        {# Para teste, o "alvo" é o primeiro model/seed/source de que ele depende. #}
        {% set ns = namespace(alvo=no.unique_id) %}
        {% if no.resource_type in ('test', 'unit_test') %}
            {% set ns.alvo = none %}
            {% for dep in no.depends_on.nodes %}
                {% if ns.alvo is none and dep.split('.')[0] in ('model', 'seed', 'source') %}
                    {% set ns.alvo = dep %}
                {% endif %}
            {% endfor %}
        {% endif %}
        {% set alvo = ns.alvo %}
        {% set bloqueante = 'bloqueante' in (no.tags or []) %}
        {% do linhas.append(
            "(" ~ _texto_sql(invocation_id) ~ ", "
            ~ dbt.current_timestamp() ~ ", "
            ~ _texto_sql(flags.WHICH) ~ ", "
            ~ _texto_sql(no.unique_id) ~ ", "
            ~ _texto_sql(no.resource_type) ~ ", "
            ~ _texto_sql(no.name) ~ ", "
            ~ _texto_sql(alvo) ~ ", "
            ~ _texto_sql(r.status) ~ ", "
            ~ _texto_sql(no.config.severity if no.resource_type == 'test' else none) ~ ", "
            ~ (bloqueante | string | lower) ~ ", "
            ~ (r.failures if r.failures is not none else 'null') ~ ", "
            ~ (r.execution_time | round(3)) ~ ", "
            ~ _texto_sql(r.message) ~ ")"
        ) %}
    {% endfor %}

    {% set sql %}
        insert into observabilidade.resultados values
        {{ linhas | join(",\n") }}
    {% endset %}
    {% do run_query(sql) %}
    {{ return('') }}
{% endmacro %}
