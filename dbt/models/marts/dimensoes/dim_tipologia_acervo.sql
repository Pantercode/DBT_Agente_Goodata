{#
  Tipologia de acervo (História, Artes Visuais, Arqueologia...). Um museu tem
  várias, então a ligação com o museu é por bridge_museu_tipologia.
#}

with tipologias as (
    select distinct unnest(tipologias_acervo) as tipologia
    from {{ ref('int_museus__enriquecido') }}
)

select
    {{ hash_colunas(['tipologia']) }}   as tipologia_sk,
    tipologia
from tipologias
where tipologia is not null
