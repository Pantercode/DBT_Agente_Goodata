{# Linha do tempo: museus (hoje cadastrados) pela década de abertura. #}

select
    decada_abertura,
    regiao_sigla,
    natureza_administrativa,
    count(*)                                    as qtd_museus,
    count(*) filter (where is_aberto)           as qtd_museus_ainda_ativos
from {{ ref('int_museus__atual') }}
where decada_abertura between 1800 and 2020
group by 1, 2, 3
