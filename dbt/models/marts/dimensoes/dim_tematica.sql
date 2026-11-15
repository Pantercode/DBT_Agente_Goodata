{# Temática principal do museu (taxonomia do Ibram). #}

select
    {{ hash_colunas(['tematica']) }}    as tematica_sk,
    tematica,
    count(distinct museu_id)            as qtd_museus_historico
from {{ ref('int_museus__enriquecido') }}
group by tematica
