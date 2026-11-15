{# Município + população do Censo. Base de todo denominador per capita do projeto. #}

select
    m.municipio_id,
    m.municipio_nome,
    m.municipio_chave,
    m.microrregiao,
    m.mesorregiao,
    m.regiao_imediata,
    m.regiao_intermediaria,
    m.uf_id,
    m.uf_sigla,
    m.uf_nome,
    m.regiao_sigla,
    m.regiao_nome,
    p.populacao,
    p.ano_referencia as ano_populacao,
    case
        when p.populacao is null then null
        when p.populacao <    10000 then '1. até 10 mil'
        when p.populacao <    50000 then '2. 10 a 50 mil'
        when p.populacao <   100000 then '3. 50 a 100 mil'
        when p.populacao <   500000 then '4. 100 a 500 mil'
        else                              '5. mais de 500 mil'
    end as faixa_populacional
from {{ ref('stg_ibge__municipios') }} as m
left join {{ ref('stg_ibge__populacao') }} as p
    on p.municipio_id = m.municipio_id
