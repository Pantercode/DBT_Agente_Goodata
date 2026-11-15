{#
  Dataset "Município" do modelo lógico do GoodData.

  Camada de consumo para BI sem modelagem própria de agregação: tudo
  achatado, booleano vira 0/1 (fato somável) e o que o MAQL não consegue
  filtrar bem por fato (população sem museu) já vem calculado. As métricas
  em gooddata/metricas.yaml só fazem SUM/COUNT e divisões sobre estas colunas,
  o que mantém os números iguais aos do painel e do agente.
#}

select
    municipio_id,
    municipio_rotulo,
    municipio_nome,
    uf_sigla,
    regiao_sigla,
    regiao_nome,
    coalesce(faixa_populacional, 'Sem dado')                    as faixa_populacional,
    classe_cobertura,
    coalesce(populacao, 0)                                      as populacao,
    qtd_museus_cadastrados,
    qtd_museus_ativos,
    case when tem_museu_ativo then 1 else 0 end                 as tem_museu_ativo,
    case when tem_museu_ativo then 0 else coalesce(populacao, 0) end as populacao_sem_museu
from {{ ref('agg_cobertura_municipio') }}
