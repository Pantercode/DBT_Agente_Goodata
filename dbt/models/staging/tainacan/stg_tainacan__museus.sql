{#
  Um registro por museu por partição de extração.

  Staging só faz três coisas: renomeia, tipa e limpa. Nenhuma regra de negócio
  (índices, classificações, junções) entra aqui; isso é intermediate.

  As listas (tipologia de acervo, recursos de acessibilidade...) ficam como
  ARRAY<STRING>: o formulário é multivalorado e explodir em linhas aqui
  multiplicaria o grão. Quem precisar de uma linha por valor faz UNNEST no
  intermediate.
#}

with fonte as (

    select * from {{ source('tainacan', 'museus') }}
    -- A API anônima só devolve itens publicados, e o fetch_only não traz o campo
    -- status (chega null). O filtro protege contra uma extração autenticada futura.
    where coalesce(status_publicacao, 'publish') = 'publish'

),

campos as (

    select
        -- chaves
        item_id                                                             as museu_id,
        {{ json_texto('metadados', '$."codigo-identificador-ibram-2"') }}   as codigo_ibram,
        slug,
        url                                                                 as url_cadastro,

        -- identificação
        trim(titulo)                                                        as nome_museu,
        nullif(trim(descricao), '')                                         as descricao,
        {{ json_texto('metadados', '$."mus_tipo".nome') }}                  as tipo_museu,
        {{ json_texto('metadados', '$."mus_tipo_tematica".nome') }}         as tematica,
        {{ json_texto('metadados', '$."mus_status".nome') }}                as status_funcionamento,
        {{ json_texto('metadados', '$."esfera".nome') }}                    as esfera_administrativa,
        {{ json_texto('metadados', '$."vinculo-federal".nome') }}           as vinculo_federal,
        {{ json_texto('metadados', '$."instituicao-mantenedora"') }}        as instituicao_mantenedora,
        {{ json_texto('metadados', '$."instrumento-de-criacao".nome') }}    as instrumento_criacao,
        regexp_replace({{ json_texto('metadados', '$."cnpj"') }}, '[^0-9]', '', 'g') as cnpj,
        {{ json_texto('metadados', '$."cadastrado"') }} is not null         as is_cadastrado,
        {{ json_texto('metadados', '$."registrado"') }} is not null         as is_registrado,

        -- localização
        upper({{ json_texto('metadados', '$."uf".nome') }})                 as uf_sigla,
        -- A taxonomia de municípios desambigua homônimos com a UF entre parênteses:
        -- "Belém (Pará)", "Palmas (Tocantins)". Tira o sufixo para casar com o IBGE.
        regexp_replace({{ json_texto('metadados', '$."municipio".nome') }}, '\s*\([^)]*\)\s*$', '') as municipio_nome,
        {{ json_texto('metadados', '$."bairro-3"') }}                       as bairro,
        {{ json_texto('metadados', '$."logradouro"') }}                     as logradouro,
        regexp_replace({{ json_texto('metadados', '$."cep-4"') }}, '[^0-9]', '', 'g') as cep,
        {{ json_texto('metadados', '$."location"') }}                       as _localizacao_bruta,

        -- histórico
        {{ inteiro_livre(json_texto('metadados', '$."ano-de-abertura"'), 1500, 2100) }} as ano_abertura,

        -- pessoas
        {{ inteiro_livre(json_texto('metadados', '$."quantas-pessoas-trabalham-no-museu"'), 0, 20000) }} as qtd_pessoas_trabalham,
        {{ inteiro_livre(json_texto('metadados', '$."total-de-funcionarios-terceirizados-do-museu"'), 0, 20000) }} as qtd_terceirizados,
        {{ sim_nao(json_texto('metadados', '$."o-museu-possui-voluntarios"')) }}  as possui_voluntarios,
        {{ sim_nao(json_texto('metadados', '$."o-museu-possui-estagiarios"')) }}  as possui_estagiarios,

        -- gestão
        {{ sim_nao(json_texto('metadados', '$."o-museu-possui-possui-regimento-interno"')) }}   as possui_regimento_interno,
        {{ sim_nao(json_texto('metadados', '$."o-museu-possui-plano-museologico"')) }}         as possui_plano_museologico,
        {{ sim_nao(json_texto('metadados', '$."o-museu-possui-contrato-para-gestao"')) }}      as possui_contrato_gestao,
        {{ sim_nao(json_texto('metadados', '$."o-museu-possui-politica-de-aquisicao-de-acervo"')) }} as possui_politica_aquisicao,
        {{ sim_nao(json_texto('metadados', '$."o-museu-possui-politica-de-decarte-do-acervo"')) }}   as possui_politica_descarte,
        {{ sim_nao(json_texto('metadados', '$."o-museu-e-de-carater-comunitario"')) }}         as is_comunitario,

        -- acervo
        {{ inteiro_livre(json_composto_valor('metadados', 'total-de-bens-culturais', 2131), 0, 50000000) }} as qtd_bens_culturais,
        {{ json_composto_valor('metadados', 'total-de-bens-culturais', 2139) }}                 as qtd_bens_culturais_precisao,
        {{ json_lista_nomes('metadados', 'taxonomia') }}                                        as tipologias_acervo,
        {{ json_lista_nomes('metadados', 'instrumentos-de-documentacao-de-acervos-utilizados') }} as instrumentos_documentacao,

        -- visitação
        {{ sim_nao(json_texto('metadados', '$."a-entrada-ao-museu-e-cobrada"')) }}              as entrada_cobrada,
        -- multivalorado no formulário, mas na prática só o primeiro valor é usado
        {{ decimal_livre(json_texto('metadados', '$."valor-da-entrada"[0]')) }}                 as valor_entrada,
        {{ json_texto('metadados', '$."o-museu-promove-visitas-com-guia-mediador-monitor-educador-orientador"') }} as visitas_mediadas,
        {{ json_texto('metadados', '$."disponibilidade-de".nome') }}                            as situacao_biblioteca,
        {{ json_texto('metadados', '$."disponibilidade-de-arquivo-historico".nome') }}          as situacao_arquivo_historico,
        {{ inteiro_livre(json_texto('metadados', '$."capacidade-de-publico-do-teatro-ou-auditorio"'), 1, 100000) }} as capacidade_auditorio,

        -- acessibilidade e serviços (listas)
        {{ json_lista_nomes('metadados', 'acessibilidade_fisica') }}                            as recursos_acessibilidade_fisica,
        {{ json_lista_nomes('metadados', 'infraestrutura-para-pessoas-com-deficiencias-auditivas-e-ou-visuais') }} as recursos_acessibilidade_sensorial,
        {{ json_lista_nomes('metadados', 'infraestrutura-para-atendimento-a-turistas-estrangeiros') }} as recursos_turista_estrangeiro,
        {{ json_lista_nomes('metadados', 'instalacoes-basicas-e-servicos') }}                   as instalacoes_servicos,
        {{ json_lista_nomes('metadados', 'publicos-especificos-com-atividades-educativas-ou-culturais') }} as publicos_atividades_educativas,

        -- presença digital
        {{ json_tamanho_lista('metadados', 'site-4') }} > 0                                     as possui_site,
        {{ json_tamanho_lista('metadados', 'redes-sociais-3') }} > 0                            as possui_redes_sociais,

        -- metadados de carga
        {{ data_br('criado_em') }}                                          as cadastrado_em,
        {{ data_br('modificado_em') }}                                      as atualizado_na_origem_em,
        dt,
        _extraido_em

    from fonte

),

final as (

    select
        * exclude (_localizacao_bruta),
        {{ coordenada('_localizacao_bruta', 1) }} as latitude,
        {{ coordenada('_localizacao_bruta', 2) }} as longitude
    from campos

)

select * from final
