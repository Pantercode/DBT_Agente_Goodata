{#
  Numa tabela-ponte com pesos, a soma dos pesos tem que ser igual ao número de
  entidades distintas (cada museu soma 1 entre todas as suas tipologias).
  Tolerância de arredondamento: 0,01 por entidade.
#}
{% test soma_igual_a_contagem(model, coluna, chave) %}
    select sum({{ coluna }}) as soma, count(distinct {{ chave }}) as entidades
    from {{ model }}
    having abs(sum({{ coluna }}) - count(distinct {{ chave }})) > 0.01 * count(distinct {{ chave }})
{% endtest %}
