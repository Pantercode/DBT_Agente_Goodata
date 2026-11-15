{#
  Dimensão de municípios (conformada): usada por fato de museus, agregados
  de cobertura e pelo modelo lógico do GoodData. Inclui municípios sem museu;
  é isso que permite medir "onde não há".
#}

{{ config(
    materialized = 'table',
    cluster_by = ['uf_sigla'] if target.type == 'bigquery' else none
) }}

select
    municipio_id,
    municipio_nome,
    uf_sigla,
    uf_nome,
    regiao_sigla,
    regiao_nome,
    mesorregiao,
    microrregiao,
    regiao_intermediaria,
    regiao_imediata,
    populacao,
    ano_populacao,
    faixa_populacional,
    municipio_nome || ' - ' || uf_sigla as municipio_rotulo
from {{ ref('int_municipios__com_populacao') }}
