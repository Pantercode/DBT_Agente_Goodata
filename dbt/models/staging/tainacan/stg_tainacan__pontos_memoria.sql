{# Um registro por Ponto de Memória por partição. Mesmo contrato do stg de museus. #}

with fonte as (

    select * from {{ source('tainacan', 'pontos_memoria') }}
    -- A API anônima só devolve itens publicados, e o fetch_only não traz o campo
    -- status (chega null). O filtro protege contra uma extração autenticada futura.
    where coalesce(status_publicacao, 'publish') = 'publish'

),

campos as (

    select
        item_id                                                              as ponto_memoria_id,
        slug,
        url                                                                  as url_cadastro,
        trim(titulo)                                                         as nome_ponto,
        nullif(trim(descricao), '')                                          as historico_atuacao,
        {{ json_lista_nomes('metadados', 'tematica') }}                      as tematicas,
        {{ json_texto('metadados', '$."tipo-de-entidade"') }}                as tipo_entidade,
        {{ json_texto('metadados', '$."natureza-juridica"') }}               as natureza_juridica,
        try_cast(left({{ json_texto('metadados', '$."data-de-criacao"') }}, 10) as date) as criado_em,

        {{ json_texto('metadados', '$."estado".nome') }}                     as _estado_bruto,
        {{ json_texto('metadados', '$."endereco-da-sede"') }}                as endereco_sede,
        {{ json_texto('metadados', '$."localizacao"') }}                     as _localizacao_bruta,

        {{ sim_nao(json_texto('metadados', '$."o-ponto-possui-acervo"')) }}                          as possui_acervo,
        {{ sim_nao(json_texto('metadados', '$."o-acervo-ja-foi-inventariado"')) }}                   as acervo_inventariado,
        {{ sim_nao(json_texto('metadados', '$."o-ponto-possui-acervos-digitais"')) }}                as possui_acervo_digital,
        {{ sim_nao(json_texto('metadados', '$."o-ponto-ja-realizou-o-inventario-participativo"')) }} as fez_inventario_participativo,
        {{ sim_nao(json_texto('metadados', '$."o-ponto-possui-sede-propria"')) }}                    as possui_sede_propria,
        {{ sim_nao(json_texto('metadados', '$."o-espaco-da-sede-e-aberto-ao-publico"')) }}           as sede_aberta_ao_publico,
        {{ sim_nao(json_texto('metadados', '$."ja-foi-contemplado-em-algum-edital-do-ibram"')) }}    as contemplado_edital_ibram,
        {{ sim_nao(json_texto('metadados', '$."o-ponto-faz-parte-de-alguma-rede"')) }}               as participa_de_rede,
        {{ sim_nao(json_texto('metadados', '$."o-ponto-possui-parceria-com-poder-publico"')) }}      as tem_parceria_poder_publico,
        {{ sim_nao(json_texto('metadados', '$."o-ponto-promove-atividades-regulares"')) }}           as promove_atividades_regulares,
        {{ json_lista_nomes('metadados', 'acervos') }}                                               as tipos_acervo,

        dt,
        _extraido_em

    from fonte

)

select
    * exclude (_localizacao_bruta, _estado_bruto),
    upper(_estado_bruto) as uf_sigla,
    {{ coordenada('_localizacao_bruta', 1) }} as latitude,
    {{ coordenada('_localizacao_bruta', 2) }} as longitude
from campos
