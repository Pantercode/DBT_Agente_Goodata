{#
  Museu com tudo o que os marts precisam, ainda no grão museu x partição.

  É o único ponto em que staging, indicadores, município e classificação de
  esfera se juntam. Os marts leem daqui; nenhum mart refaz essas junções. Se
  uma regra mudar (ex.: o que conta como "museu ativo"), muda num lugar só.

  Incremental por partição: cada build lê só as partições novas (mais a
  janela de reprocessamento) e só as que int_particoes__validacao aprovou.
  Partição em quarentena não entra; se uma partição já processada passar a
  quarentena (revalidada na janela), o pre_hook remove as linhas dela.
  Registro com valor impossível (sem nome, UF fora da lista, sem status) fica
  de fora e aparece em int_museus__registros_quarentena.
#}

{{ config(
    materialized = 'incremental',
    incremental_strategy = 'delete+insert',
    unique_key = 'dt',
    on_schema_change = 'append_new_columns',
    pre_hook = "{% if is_incremental() %}delete from {{ this }} where dt in (select dt from {{ ref('int_particoes__validacao') }} where fonte = 'museus' and status = 'quarentena'){% endif %}"
) }}

with particoes as (
    select dt
    from {{ ref('int_particoes__validacao') }}
    where fonte = 'museus' and status = 'valida' and dt >= {{ inicio_janela() }}
),

museus as (
    select s.*
    from {{ ref('stg_tainacan__museus') }} as s
    where s.dt >= {{ inicio_janela() }}               -- pruning no lake
      and s.dt in (select dt from particoes)          -- só partições aprovadas
      and s.nome_museu is not null
      and s.status_funcionamento is not null
      and s.uf_sigla in (select distinct uf_sigla from {{ ref('stg_ibge__municipios') }})
),

indicadores as (
    select * from {{ ref('int_museus__indicadores') }}
    where dt >= {{ inicio_janela() }}
),

municipio as (
    select * from {{ ref('int_museus__municipio_resolvido') }}
    where dt >= {{ inicio_janela() }}
),

ibge as (
    select municipio_id, municipio_nome, uf_sigla, regiao_sigla, regiao_nome
    from {{ ref('stg_ibge__municipios') }}
),

esfera as (
    select * from {{ ref('classificacao_esfera') }}
)

select
    m.museu_id,
    m.dt,
    m.codigo_ibram,
    m.nome_museu,
    m.descricao,
    m.url_cadastro,
    coalesce(m.tipo_museu, 'Não informado')                 as tipo_museu,
    coalesce(m.tematica, 'Não informada')                   as tematica,
    m.status_funcionamento,
    m.status_funcionamento = 'Aberto'                       as is_aberto,
    coalesce(m.esfera_administrativa, 'Não informada')      as esfera_administrativa,
    coalesce(e.natureza, 'Não informada')                   as natureza_administrativa,
    e.nivel_governo,
    e.subtipo_privado,
    m.instituicao_mantenedora,
    m.is_comunitario,
    m.is_cadastrado,
    m.is_registrado,
    m.ano_abertura,
    case when m.ano_abertura is not null then cast(floor(m.ano_abertura / 10) * 10 as integer) end as decada_abertura,

    -- território: o IBGE é a fonte da verdade da UF. Quando o cadastro diverge
    -- (Londrina em RR...), a UF do IBGE vence e a divergência fica sinalizada.
    mun.municipio_id,
    mun.metodo_resolucao                                    as metodo_resolucao_municipio,
    coalesce(i.municipio_nome, m.municipio_nome)            as municipio_nome,
    coalesce(i.uf_sigla, m.uf_sigla)                        as uf_sigla,
    i.regiao_sigla,
    i.regiao_nome,
    m.uf_sigla                                              as uf_sigla_cadastro,
    i.uf_sigla is not null and i.uf_sigla <> m.uf_sigla     as is_uf_divergente,
    m.bairro,
    m.cep,
    m.latitude,
    m.longitude,

    -- pessoas e acervo
    m.qtd_pessoas_trabalham,
    m.qtd_terceirizados,
    m.possui_voluntarios,
    m.possui_estagiarios,
    m.qtd_bens_culturais,
    m.qtd_bens_culturais_precisao,
    m.tipologias_acervo,

    -- gestão
    m.possui_plano_museologico,
    m.possui_regimento_interno,
    m.possui_politica_aquisicao,
    m.possui_politica_descarte,
    m.possui_contrato_gestao,
    ind.atende_plano_museologico,
    ind.atende_regimento_interno,
    ind.atende_documentacao_acervo,
    ind.atende_politica_aquisicao,
    ind.atende_politica_descarte,
    ind.atende_equipe_propria,
    ind.criterios_respondidos,
    ind.indice_gestao,
    case
        when ind.indice_gestao >= 70 then 'Estruturada'
        when ind.indice_gestao >= 40 then 'Em estruturação'
        when ind.indice_gestao >  0  then 'Incipiente'
        else 'Sem instrumentos'
    end                                                     as faixa_gestao,

    -- visitação e acessibilidade
    m.entrada_cobrada,
    m.valor_entrada,
    m.visitas_mediadas,
    m.situacao_biblioteca,
    m.situacao_arquivo_historico,
    ind.qtd_recursos_acess_fisica,
    ind.qtd_recursos_acess_sensorial,
    ind.qtd_recursos_turista,
    ind.recursos_acessibilidade_fisica,
    ind.recursos_acessibilidade_sensorial,
    m.recursos_turista_estrangeiro,
    ind.dimensoes_acessibilidade,
    m.publicos_atividades_educativas,
    m.possui_site,
    m.possui_redes_sociais,

    m.cadastrado_em,
    m.atualizado_na_origem_em,
    m._extraido_em

from museus as m
inner join indicadores as ind
    on ind.museu_id = m.museu_id and ind.dt = m.dt
inner join municipio as mun
    on mun.museu_id = m.museu_id and mun.dt = m.dt
left join ibge as i
    on i.municipio_id = mun.municipio_id
left join esfera as e
    on e.esfera_administrativa = m.esfera_administrativa
