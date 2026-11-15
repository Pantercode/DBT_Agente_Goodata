{#
  Usa o nome do schema configurado sem o prefixo do target.

  Num time com vários devs compartilhando o warehouse o padrão do dbt
  (<target.schema>_<custom>) evita colisão; aqui o DuckDB é um arquivo por
  máquina, então o prefixo só atrapalharia os consumidores (painel, agente e
  GoodData apontam para `publicado`, fixo).
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
