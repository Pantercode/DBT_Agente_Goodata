{#
  Dimensão de museus, SCD tipo 2, incremental.

  Por que não `dbt snapshot`: o snapshot carimba a vigência com a hora da
  execução e não reconstrói o passado. Aqui a vigência vem da data da
  partição, então reprocessar é idempotente e backfill funciona (ADR 003).

  Como o incremental funciona
    1. Observações = linhas das partições novas (dt > última confirmação)
                     + a versão aberta atual de cada museu ("âncora").
    2. Por museu, em ordem de data, uma linha só vira versão nova se o hash
       dos atributos rastreados mudou em relação à linha anterior. A âncora
       sempre fica (é a versão que pode ser fechada).
    3. lead() fecha a vigência; museu que não aparece nas partições novas tem
       a versão fechada no último dia em que foi visto.
    4. delete+insert por museu_sk: a âncora é regravada (com valido_ate, se
       fechou) e as versões novas entram. Versões já fechadas nunca são lidas
       de novo.
  Custo por build: ~4 mil versões abertas + as partições novas. Não relê o
  histórico. No full-refresh as observações são todas as partições válidas e
  o resultado é o mesmo.

  Partição em quarentena nunca chega aqui (int_museus__enriquecido não a
  contém), então uma coleta faltando metade dos museus não "fecha" metade
  dos museus.
#}

{{ config(
    materialized = 'incremental',
    incremental_strategy = 'delete+insert',
    unique_key = 'museu_sk',
    on_schema_change = 'append_new_columns',
    cluster_by = ['museu_id'] if target.type == 'bigquery' else none
) }}

{% set atributos_rastreados = [
    'nome_museu', 'tipo_museu', 'tematica', 'status_funcionamento',
    'esfera_administrativa', 'municipio_id', 'possui_plano_museologico',
    'possui_regimento_interno', 'possui_politica_aquisicao',
    'possui_politica_descarte', 'indice_gestao'
] %}

{% set descritivos = [
    'codigo_ibram', 'nome_museu', 'tipo_museu', 'tematica', 'status_funcionamento', 'is_aberto',
    'esfera_administrativa', 'natureza_administrativa', 'nivel_governo', 'subtipo_privado',
    'is_comunitario', 'ano_abertura', 'decada_abertura', 'municipio_id', 'municipio_nome',
    'uf_sigla', 'regiao_sigla', 'possui_plano_museologico', 'possui_regimento_interno',
    'possui_politica_aquisicao', 'possui_politica_descarte', 'indice_gestao', 'faixa_gestao',
    'url_cadastro'
] %}

with novas as (

    select
        museu_id,
        {{ descritivos | join(', ') }},
        dt,
        dt                                           as visto_em,
        {{ hash_colunas(atributos_rastreados) }}     as hash_atributos,
        0                                            as e_ancora
    from {{ ref('int_museus__enriquecido') }}
    {% if is_incremental() %}
    where dt > (select max(ultima_confirmacao) from {{ this }})
    {% endif %}

),

observacoes as (

    select * from novas
    {% if is_incremental() %}
    union all
    select
        museu_id,
        {{ descritivos | join(', ') }},
        valido_de          as dt,
        ultima_confirmacao as visto_em,
        hash_atributos,
        1                  as e_ancora
    from {{ this }}
    where is_versao_atual
    {% endif %}

),

marcadas as (

    select
        *,
        -- na mesma data, a âncora vem antes da observação nova
        lag(hash_atributos) over (partition by museu_id order by dt, e_ancora desc) as hash_anterior,
        max(visto_em) over (partition by museu_id)                                  as ultima_aparicao
    from observacoes

),

versoes as (

    select *
    from marcadas
    where e_ancora = 1 or hash_anterior is null or hash_anterior <> hash_atributos

),

vigencias as (

    select
        *,
        lead(dt) over (partition by museu_id order by dt) as inicio_proxima_versao
    from versoes

),

ultima_particao as (

    -- só avança se houve partição nova; sem partição nova, nada fecha
    select max(visto_em) as dt from observacoes

)

select
    {{ hash_colunas(['museu_id', 'dt']) }}                   as museu_sk,
    museu_id,
    {{ descritivos | join(',\n    ') }},
    dt                                                       as valido_de,
    case
        when inicio_proxima_versao is not null then {{ somar_dias('inicio_proxima_versao', -1) }}
        when ultima_aparicao < (select dt from ultima_particao) then ultima_aparicao
    end                                                      as valido_ate,
    inicio_proxima_versao is null
        and ultima_aparicao = (select dt from ultima_particao) as is_versao_atual,
    inicio_proxima_versao is null
        and ultima_aparicao < (select dt from ultima_particao) as is_removido_do_cadastro,
    case
        when inicio_proxima_versao is not null then {{ somar_dias('inicio_proxima_versao', -1) }}
        else ultima_aparicao
    end                                                      as ultima_confirmacao,
    hash_atributos
from vigencias
