{#
  Resolve o município de cada museu para o código IBGE.

  O cadastro guarda município como texto (taxonomia livre do Tainacan), então a
  junção com o IBGE é por (UF, nome normalizado). Três caminhos, em ordem:
    1. exato      nome normalizado bate com o IBGE na mesma UF
    2. de_para    correção manual mantida no seed de_para_municipios
                  (grafias antigas: "Parati", "Embu", "Mogi-Mirim"...)
    3. nao_resolvido  fica sem municipio_id; o teste de cobertura avisa se
                  passar do limite

  Grão: museu x partição (mesmo do staging).
#}

with museus as (

    select
        museu_id,
        dt,
        uf_sigla,
        municipio_nome,
        {{ normalizar_nome('municipio_nome') }} as municipio_chave
    from {{ ref('stg_tainacan__museus') }}

),

ibge as (

    select municipio_id, uf_sigla, municipio_chave
    from {{ ref('stg_ibge__municipios') }}

),

de_para as (

    select
        upper(uf_sigla) as uf_sigla,
        {{ normalizar_nome('nome_no_cadastro') }} as municipio_chave,
        cast(municipio_id as integer) as municipio_id
    from {{ ref('de_para_municipios') }}

)

select
    m.museu_id,
    m.dt,
    m.uf_sigla,
    m.municipio_nome as municipio_informado,
    coalesce(exato.municipio_id, dp.municipio_id) as municipio_id,
    case
        when exato.municipio_id is not null then 'exato'
        when dp.municipio_id is not null then 'de_para'
        else 'nao_resolvido'
    end as metodo_resolucao
from museus as m
left join ibge as exato
    on  exato.uf_sigla = m.uf_sigla
    and exato.municipio_chave = m.municipio_chave
left join de_para as dp
    on  dp.uf_sigla = m.uf_sigla
    and dp.municipio_chave = m.municipio_chave
