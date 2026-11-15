{#
  Foto atual: só a partição mais recente.

  Museu que sumiu da origem (excluído do cadastro) não aparece aqui; o
  histórico dele continua em dim_museu, com a versão encerrada.
#}

select *
from {{ ref('int_museus__enriquecido') }}
where dt = (select max(dt) from {{ ref('int_museus__enriquecido') }})
