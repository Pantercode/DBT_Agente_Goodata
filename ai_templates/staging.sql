{#
  EXEMPLO CANÔNICO: STAGING
  Baseado em models/staging/tainacan/stg_tainacan__pontos_memoria.sql

  Grão: um registro por <entidade> por partição de extração (dt).
  Faz: renomeia, tipa, limpa sentinelas, extrai do JSON.
  Não faz: join, regra de negócio, agregação.
#}

with fonte as (

    -- única CTE que lê o source; filtros de escopo de origem ficam aqui
    select * from {{ source('tainacan', 'pontos_memoria') }}
    where coalesce(status_publicacao, 'publish') = 'publish'

),

campos as (

    select
        -- chaves primeiro, com nome de domínio (não `id`)
        item_id                                                       as ponto_memoria_id,

        -- texto: trim + sentinela -> null (json_texto já faz as duas coisas)
        trim(titulo)                                                  as nome_ponto,
        {{ json_texto('metadados', '$."natureza-juridica"') }}       as natureza_juridica,

        -- multivalorado: ARRAY ordenado e sem duplicata, nunca string concatenada
        {{ json_lista_nomes('metadados', 'tematica') }}               as tematicas,

        -- Sim/Não do formulário -> boolean
        {{ sim_nao(json_texto('metadados', '$."o-ponto-possui-acervo"')) }} as possui_acervo,

        -- campos de carga sempre por último
        dt,
        _extraido_em

    from fonte

)

select * from campos
