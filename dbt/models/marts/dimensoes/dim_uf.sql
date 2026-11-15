{# Dimensão de UF (27), com região e população agregada do Censo. #}

select
    uf_sigla,
    min(uf_id)              as uf_id,
    min(uf_nome)            as uf_nome,
    min(regiao_sigla)       as regiao_sigla,
    min(regiao_nome)        as regiao_nome,
    count(*)                as qtd_municipios,
    sum(populacao)          as populacao
from {{ ref('int_municipios__com_populacao') }}
group by uf_sigla
