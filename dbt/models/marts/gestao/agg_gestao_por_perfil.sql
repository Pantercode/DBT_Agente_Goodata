{#
  Maturidade de gestão por perfil institucional (natureza x nível x tipo).
  Só museus ativos. Cada critério vira um percentual, para o painel montar o
  "heatmap de instrumentos" sem recalcular nada.
#}

select
    natureza_administrativa,
    coalesce(nivel_governo, subtipo_privado, 'Não se aplica')       as perfil,
    tipo_museu,
    count(*)                                                        as qtd_museus_ativos,
    round(avg(indice_gestao), 1)                                    as indice_gestao_medio,
    round(avg(case when atende_plano_museologico   then 1.0 else 0.0 end), 4) as pct_plano_museologico,
    round(avg(case when atende_regimento_interno   then 1.0 else 0.0 end), 4) as pct_regimento_interno,
    round(avg(case when atende_documentacao_acervo then 1.0 else 0.0 end), 4) as pct_documentacao_acervo,
    round(avg(case when atende_politica_aquisicao  then 1.0 else 0.0 end), 4) as pct_politica_aquisicao,
    round(avg(case when atende_politica_descarte   then 1.0 else 0.0 end), 4) as pct_politica_descarte,
    round(avg(case when atende_equipe_propria      then 1.0 else 0.0 end), 4) as pct_equipe_propria,
    round(avg(criterios_respondidos), 2)                            as media_criterios_respondidos
from {{ ref('int_museus__atual') }}
where is_aberto
group by 1, 2, 3
