{#
  Funções que mudam de sintaxe entre DuckDB e BigQuery.

  Regra do projeto: nenhum modelo usa função específica de engine direto; passa
  por aqui. Assim o mesmo SQL compila nos dois targets e o diff de uma migração
  fica concentrado neste arquivo.
#}

{# ---------- JSON ---------- #}

{% macro json_texto(coluna, caminho) -%}
    {{ return(adapter.dispatch('json_texto', 'museus_br')(coluna, caminho)) }}
{%- endmacro %}

{#
  O formulário do Ibram usa sentinelas em vez de vazio: "- NÃO INFORMADO -",
  "- NÃO INFORMADA -". Isso é ausência de resposta e vira null aqui.
  "- NÃO POSSUI -" e "- NÃO SE APLICA -" são respostas e passam intactas;
  quem decide o que fazer com elas é o intermediate.
#}
{% macro sem_sentinela(expr) -%}
    case when upper({{ expr }}) like '- N_O INFORMAD_ -' then null else {{ expr }} end
{%- endmacro %}

{% macro default__json_texto(coluna, caminho) -%}
    {{ sem_sentinela("nullif(trim(json_extract_string(" ~ coluna ~ ", '" ~ caminho ~ "')), '')") }}
{%- endmacro %}

{% macro bigquery__json_texto(coluna, caminho) -%}
    {{ sem_sentinela("nullif(trim(json_value(" ~ coluna ~ ", '" ~ caminho ~ "')), '')") }}
{%- endmacro %}


{# Lista de nomes de termos de uma taxonomia multivalorada: [{"id","nome"}, ...] -> ARRAY<STRING> #}
{% macro json_lista_nomes(coluna, chave) -%}
    {{ return(adapter.dispatch('json_lista_nomes', 'museus_br')(coluna, chave)) }}
{%- endmacro %}

{# Lista vazia = não respondeu. ["- NÃO POSSUI -"] = respondeu que não tem. #}
{% macro default__json_lista_nomes(coluna, chave) -%}
    list_sort(list_filter(
        list_distinct(
            coalesce(json_extract_string({{ coluna }}, '$."{{ chave }}"[*].nome'), [])
        ),
        lambda x: x is not null and upper(x) not like '- N_O INFORMAD_ -'
    ))
{%- endmacro %}

{% macro bigquery__json_lista_nomes(coluna, chave) -%}
    array(
        select distinct json_value(t, '$.nome') as nome
        from unnest(json_query_array({{ coluna }}, '$."{{ chave }}"')) as t
        where json_value(t, '$.nome') is not null
          and upper(json_value(t, '$.nome')) not like '- N_O INFORMAD_ -'
        order by nome
    )
{%- endmacro %}


{#
  Valor de um filho dentro de metadado composto do Tainacan.
  O composto chega como [{"metadatum_id": 2131, "valor": "30000"}, ...].
#}
{% macro json_composto_valor(coluna, chave, metadatum_id) -%}
    {{ return(adapter.dispatch('json_composto_valor', 'museus_br')(coluna, chave, metadatum_id)) }}
{%- endmacro %}

{% macro default__json_composto_valor(coluna, chave, metadatum_id) -%}
    nullif(trim(list_filter(
        coalesce(
            try_cast(json_extract({{ coluna }}, '$."{{ chave }}"') as struct(metadatum_id bigint, valor varchar)[]),
            []
        ),
        lambda x: x.metadatum_id = {{ metadatum_id }}
    )[1].valor), '')
{%- endmacro %}

{% macro bigquery__json_composto_valor(coluna, chave, metadatum_id) -%}
    (
        select nullif(trim(json_value(t, '$.valor')), '')
        from unnest(json_query_array({{ coluna }}, '$."{{ chave }}"')) as t
        where json_value(t, '$.metadatum_id') = '{{ metadatum_id }}'
        limit 1
    )
{%- endmacro %}


{% macro json_tamanho_lista(coluna, chave) -%}
    {{ return(adapter.dispatch('json_tamanho_lista', 'museus_br')(coluna, chave)) }}
{%- endmacro %}

{% macro default__json_tamanho_lista(coluna, chave) -%}
    coalesce(json_array_length({{ coluna }}, '$."{{ chave }}"'), 0)
{%- endmacro %}

{% macro bigquery__json_tamanho_lista(coluna, chave) -%}
    coalesce(array_length(json_query_array({{ coluna }}, '$."{{ chave }}"')), 0)
{%- endmacro %}


{# ---------- Arrays ---------- #}

{% macro tamanho_lista(expr) -%}
    {{ return(adapter.dispatch('tamanho_lista', 'museus_br')(expr)) }}
{%- endmacro %}

{% macro default__tamanho_lista(expr) -%} coalesce(len({{ expr }}), 0) {%- endmacro %}
{% macro bigquery__tamanho_lista(expr) -%} array_length({{ expr }}) {%- endmacro %}


{% macro lista_contem(expr, valor) -%}
    {{ return(adapter.dispatch('lista_contem', 'museus_br')(expr, valor)) }}
{%- endmacro %}

{% macro default__lista_contem(expr, valor) -%} list_contains({{ expr }}, {{ valor }}) {%- endmacro %}
{% macro bigquery__lista_contem(expr, valor) -%} {{ valor }} in unnest({{ expr }}) {%- endmacro %}


{# Remove de uma lista os valores que significam "não possui" (vêm misturados com os recursos). #}
{% macro lista_sem_negativas(expr) -%}
    {{ return(adapter.dispatch('lista_sem_negativas', 'museus_br')(expr)) }}
{%- endmacro %}

{% macro default__lista_sem_negativas(expr) -%}
    list_filter({{ expr }}, lambda x: upper(x) not like '- N_O %')
{%- endmacro %}

{% macro bigquery__lista_sem_negativas(expr) -%}
    array(select x from unnest({{ expr }}) as x where upper(x) not like '- N_O %')
{%- endmacro %}


{# ---------- STRUCT ---------- #}

{# struct_de({'campo': 'expr', ...}) -> STRUCT nomeado nas duas engines #}
{% macro struct_de(campos) -%}
    {{ return(adapter.dispatch('struct_de', 'museus_br')(campos)) }}
{%- endmacro %}

{% macro default__struct_de(campos) -%}
    struct_pack(
    {%- for nome, expr in campos.items() %}
        {{ nome }} := {{ expr }}{{ "," if not loop.last }}
    {%- endfor %}
    )
{%- endmacro %}

{% macro bigquery__struct_de(campos) -%}
    struct(
    {%- for nome, expr in campos.items() %}
        {{ expr }} as {{ nome }}{{ "," if not loop.last }}
    {%- endfor %}
    )
{%- endmacro %}


{# ---------- Texto ---------- #}

{# Chave de junção para nomes de município: sem acento, minúsculo, só letras. #}
{% macro normalizar_nome(expr) -%}
    {{ return(adapter.dispatch('normalizar_nome', 'museus_br')(expr)) }}
{%- endmacro %}

{% macro default__normalizar_nome(expr) -%}
    regexp_replace(lower(strip_accents(trim({{ expr }}))), '[^a-z]', '', 'g')
{%- endmacro %}

{% macro bigquery__normalizar_nome(expr) -%}
    regexp_replace(lower(normalize(trim({{ expr }}), nfd)), r'[^a-z]', '')
{%- endmacro %}


{% macro hash_colunas(colunas) -%}
    {{ return(adapter.dispatch('hash_colunas', 'museus_br')(colunas)) }}
{%- endmacro %}

{% macro default__hash_colunas(colunas) -%}
    md5(concat_ws('||', {% for c in colunas %}coalesce(cast({{ c }} as varchar), '∅'){{ ", " if not loop.last }}{% endfor %}))
{%- endmacro %}

{% macro bigquery__hash_colunas(colunas) -%}
    to_hex(md5(concat({% for c in colunas %}coalesce(cast({{ c }} as string), '∅'){{ ", '||', " if not loop.last }}{% endfor %})))
{%- endmacro %}


{# ---------- Datas ---------- #}

{% macro data_br(expr) -%}
    {{ return(adapter.dispatch('data_br', 'museus_br')(expr)) }}
{%- endmacro %}

{% macro default__data_br(expr) -%} try_strptime({{ expr }}, '%d/%m/%Y')::date {%- endmacro %}
{% macro bigquery__data_br(expr) -%} safe.parse_date('%d/%m/%Y', {{ expr }}) {%- endmacro %}


{% macro somar_dias(expr, dias) -%}
    {{ return(adapter.dispatch('somar_dias', 'museus_br')(expr, dias)) }}
{%- endmacro %}

{% macro default__somar_dias(expr, dias) -%} ({{ expr }} + to_days({{ dias }}))::date {%- endmacro %}
{% macro bigquery__somar_dias(expr, dias) -%} date_add({{ expr }}, interval {{ dias }} day) {%- endmacro %}
