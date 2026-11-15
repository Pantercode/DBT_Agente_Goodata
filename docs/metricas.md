# Catálogo de métricas

Uma métrica, uma definição. Onde ela é calculada está na coluna "mora em"; as
outras ferramentas só leem ou repetem a mesma conta sobre as mesmas colunas.
`tests/test_metricas_consistentes.py` falha se uma métrica `core` do GoodData
não estiver documentada aqui.

## Conceitos

**Museu ativo.** Status de funcionamento "Aberto" no cadastro do Ibram. Fechado
ou sem status entra em "cadastrados", nunca em "ativos". Toda métrica de
cobertura usa ativos.

**População.** Censo 2022 (SIDRA, tabela 4709), por município. É o denominador
de toda métrica per capita.

**Município com museu.** Município com pelo menos um museu ativo cujo cadastro
foi resolvido para um código IBGE (99,8% dos museus; o restante entra no
de-para manual, ver `dbt/seeds/de_para_municipios.csv`).

## Métricas

| métrica | definição | mora em | painel | GoodData | agente |
|---|---|---|---|---|---|
| `museus_ativos` | contagem de museus com `is_aberto` | `agg_cobertura_*`, semantic layer | capa | MAQL | `agg_cobertura_brasil` |
| `museus_cadastrados` | contagem de museus no cadastro, qualquer status | `agg_cobertura_*`, semantic layer | — | MAQL | idem |
| `museus_por_100k_hab` | `museus_ativos × 100.000 / população` | `agg_cobertura_uf`, `agg_cobertura_brasil` | capa, mapa, ranking | MAQL (mesma conta) | idem |
| `pct_municipios_com_museu` | municípios com ≥ 1 museu ativo / total de municípios | `agg_cobertura_*` | capa | MAQL | idem |
| `pct_populacao_sem_museu` | população de municípios sem museu ativo / população total | `agg_cobertura_*` | manchete da capa | MAQL | idem |
| `indice_gestao_medio` | média do índice de gestão (0-100) entre museus ativos | `agg_cobertura_*`, semantic layer | capa, Gestão | MAQL | idem |
| `pct_museus_sem_acessibilidade` | museus ativos que não declararam nenhum recurso em nenhuma das 3 dimensões / museus ativos | `agg_cobertura_brasil`, semantic layer | Acessibilidade | MAQL | idem |

### Índice de gestão

Soma ponderada de seis critérios do formulário. Pesos no seed
`pesos_indice_gestao` (editável pela área de negócio; o teste `soma_igual_a`
garante que somam 100):

| critério | peso | por quê |
|---|---|---|
| plano museológico | 30 | exigido pelo Estatuto de Museus (Lei 11.904/2009, art. 44) |
| regimento interno | 20 | pré-requisito para registro no Ibram |
| documentação do acervo | 15 | ao menos um instrumento (livro de tombo, ficha, sistema) |
| política de aquisição | 15 | Lei 11.904/2009, art. 38 |
| política de descarte | 10 | menos comum; sinal de gestão de acervo madura |
| equipe própria | 10 | ao menos uma pessoa, sem contar terceirizados |

Critério não respondido conta como não atendido. `criterios_respondidos`
mostra quanto do índice é resposta e quanto é ausência dela: um museu com
índice 0 e 0 critérios respondidos é um cadastro incompleto, não um museu sem
gestão. O painel separa os dois na aba Qualidade.

## Armadilhas conhecidas

- **Média de razões.** `museus_por_100k_hab` do Nordeste não é a média das nove
  UFs. O painel e o GoodData recalculam com numerador e denominador; o agente
  é instruído a fazer o mesmo (`agente/prompts/sistema.md`).
- **Cadastro ≠ universo.** O cadastro é declaratório. Museu que nunca se
  cadastrou não existe para estes números. "Município sem museu" quer dizer
  "sem museu no cadastro do Ibram".
- **DF.** Um município só (Brasília) com museu: 100% de cobertura municipal.
  Não compare DF com UFs na métrica de municípios; use a per capita.
