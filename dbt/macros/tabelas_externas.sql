{#
  Registra o landing zone como schema `raw` no warehouse.

  Mesmo papel do pacote dbt-external-tables, sem a dependência:
    DuckDB   -> views sobre read_json() com hive partitioning (lê o lake local)
    BigQuery -> EXTERNAL TABLE com hive partitioning sobre gs://<bucket>/raw

  Roda no on-run-start, então qualquer `dbt build` já enxerga partições novas.
  Os sources (models/staging/**/_*__sources.yml) apontam para `raw.<tabela>`.
#}

{% macro tabelas_lake() %}
    {{ return([
        {'fonte': 'tainacan', 'tabela': 'museus', 'colunas_fixas': true},
        {'fonte': 'tainacan', 'tabela': 'pontos_memoria', 'colunas_fixas': true},
        {'fonte': 'tainacan', 'tabela': 'museus_metadados', 'colunas_fixas': false},
        {'fonte': 'tainacan', 'tabela': 'pontos_memoria_metadados', 'colunas_fixas': false},
        {'fonte': 'ibge', 'tabela': 'municipios', 'colunas_fixas': false},
        {'fonte': 'ibge', 'tabela': 'populacao', 'colunas_fixas': false},
    ]) }}
{% endmacro %}

{% macro criar_tabelas_externas() %}
    {% if not execute %}{{ return('') }}{% endif %}
    {% do adapter.create_schema(api.Relation.create(database=target.database, schema='raw')) %}
    {% for t in tabelas_lake() %}
        {% do run_query(adapter.dispatch('ddl_tabela_externa', 'museus_br')(t)) %}
    {% endfor %}
    {% do run_query(adapter.dispatch('ddl_manifestos', 'museus_br')()) %}
    {{ return('') }}
{% endmacro %}


{#
  Os _manifest.json de todas as partições, numa tabela só. É o "contrato" que
  a ingestão assina para cada partição (quantos registros a origem informou,
  quantos foram gravados, hash). A validação de partição compara o que o
  warehouse leu contra isso.
#}
{% macro default__ddl_manifestos() %}
    create or replace view raw.manifestos as
    select
        fonte,
        entidade,
        cast(dt as date)                        as dt,
        cast(extraido_em as timestamp)          as extraido_em,
        cast(registros as bigint)               as registros,
        cast(total_informado_pela_origem as bigint) as total_informado_pela_origem,
        sha256
    from read_json(
        '{{ var("caminho_lake") }}/*/*/dt=*/_manifest.json',
        columns = {
            fonte: 'VARCHAR', entidade: 'VARCHAR', dt: 'VARCHAR', extraido_em: 'VARCHAR',
            registros: 'BIGINT', total_informado_pela_origem: 'BIGINT', sha256: 'VARCHAR'
        }
    )
{% endmacro %}

{% macro bigquery__ddl_manifestos() %}
    {# No BigQuery os manifestos são carregados como tabela nativa raw._manifests pelo job de upload. #}
    create or replace view `{{ target.project }}.raw.manifestos` as
    select * from `{{ target.project }}.raw._manifests`
{% endmacro %}


{% macro default__ddl_tabela_externa(t) %}
    {% set caminho = var('caminho_lake') ~ '/' ~ t.fonte ~ '/' ~ t.tabela ~ '/dt=*/part-*.jsonl.gz' %}
    create or replace view raw.{{ t.tabela }} as
    select *
    from read_json(
        '{{ caminho }}',
        format = 'newline_delimited',
        hive_partitioning = true,
        hive_types = {'dt': DATE}
        {%- if t.colunas_fixas %},
        {#- metadados fica como JSON bruto: os valores mudam de tipo entre itens
            (string, objeto de taxonomia, lista) e a inferência do DuckDB geraria
            um STRUCT diferente a cada extração. #}
        columns = {
            item_id: 'BIGINT', slug: 'VARCHAR', url: 'VARCHAR', status_publicacao: 'VARCHAR',
            titulo: 'VARCHAR', descricao: 'VARCHAR', criado_em: 'VARCHAR', modificado_em: 'VARCHAR',
            metadados: 'JSON', _extraido_em: 'TIMESTAMP'
        }
        {%- endif %}
    )
{% endmacro %}


{% macro bigquery__ddl_tabela_externa(t) %}
    {% set bucket = env_var('MUSEUS_GCS_BUCKET', 'defina-MUSEUS_GCS_BUCKET') %}
    create or replace external table `{{ target.project }}.raw.{{ t.tabela }}`
    {%- if t.colunas_fixas %}
    (
        item_id INT64, slug STRING, url STRING, status_publicacao STRING,
        titulo STRING, descricao STRING, criado_em STRING, modificado_em STRING,
        metadados JSON, _extraido_em TIMESTAMP
    )
    {%- endif %}
    with partition columns (dt DATE)
    options (
        format = 'NEWLINE_DELIMITED_JSON',
        compression = 'GZIP',
        uris = ['gs://{{ bucket }}/raw/{{ t.fonte }}/{{ t.tabela }}/*'],
        hive_partition_uri_prefix = 'gs://{{ bucket }}/raw/{{ t.fonte }}/{{ t.tabela }}',
        require_hive_partition_filter = false
    )
{% endmacro %}
