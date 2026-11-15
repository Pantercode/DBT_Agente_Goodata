{#
  Tipo de museu (taxonomia do Ibram: clássico, ecomuseu, virtual...).
  Montada a partir dos valores que já apareceram em qualquer partição válida,
  então um tipo novo criado no cadastro entra sozinho.
#}

select
    {{ hash_colunas(['tipo_museu']) }}      as tipo_museu_sk,
    tipo_museu,
    tipo_museu in ('Virtual')               as is_virtual,
    tipo_museu in ('Unidade de conservação da natureza',
                   'Jardim zoológico, botânico, herbário, oceanário ou planetário') as is_acervo_vivo,
    count(distinct museu_id)                as qtd_museus_historico
from {{ ref('int_museus__enriquecido') }}
group by tipo_museu
