{#
  Data quality como produto: quanto de cada campo-chave do cadastro está
  preenchido, por UF. Alimenta a aba "Qualidade" do painel e responde à
  pergunta que sempre aparece numa reunião ("esse número é confiável?").

  Formato longo (UF x campo) de propósito: adicionar um campo é adicionar uma
  linha no `campos`, não uma coluna.
#}

{% set campos = {
    'Coordenadas': 'latitude',
    'Ano de abertura': 'ano_abertura',
    'Tipo de museu': "nullif(tipo_museu, 'Não informado')",
    'Temática': "nullif(tematica, 'Não informada')",
    'Esfera administrativa': "nullif(esfera_administrativa, 'Não informada')",
    'Plano museológico': 'possui_plano_museologico',
    'Equipe (nº de pessoas)': 'qtd_pessoas_trabalham',
    'Total de bens culturais': 'qtd_bens_culturais',
    'Acessibilidade física': "case when qtd_recursos_acess_fisica > 0 or len(recursos_acessibilidade_fisica) > 0 then 1 end",
    'Município no IBGE': 'municipio_id'
} %}

with base as (
    select * from {{ ref('int_museus__atual') }}
)

{% for rotulo, expr in campos.items() %}
select
    uf_sigla,
    '{{ rotulo }}'                                  as campo,
    count(*)                                        as qtd_museus,
    count({{ expr }})                               as qtd_preenchidos,
    round(count({{ expr }}) * 1.0 / count(*), 4)    as pct_preenchido
from base
group by uf_sigla
{{ "union all" if not loop.last }}
{% endfor %}
