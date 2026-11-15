# 001. DuckDB como warehouse local, BigQuery como target preparado

**Contexto.** O volume é pequeno (4 mil museus por dia, 5,5 mil municípios). O
alvo de produção natural para o tipo de trabalho é BigQuery, mas manter um
projeto GCP só para desenvolver e rodar CI custa dinheiro e credencial.

**Decisão.** DuckDB em arquivo é o warehouse do dia a dia e do CI. O
`profiles.yml` tem um target `bigquery`, e tudo que muda de sintaxe passa por
`adapter.dispatch` em `macros/cross_db.sql` (JSON, STRUCT, ARRAY, datas, hash).
Os modelos com configuração física diferente (`fct_museus_diario`,
`publicar_marts`, `criar_tabelas_externas`) têm ramo por `target.type`.

**Consequências.**
- O CI roda o projeto inteiro sem rede e sem segredo.
- O target BigQuery **não foi executado** neste repositório. As macros cobrem
  as diferenças conhecidas, mas o staging ainda usa `* exclude`, `split_part`
  e `regexp_replace(..., 'g')`, que precisam de dispatch antes da primeira
  execução real. Está anotado aqui para ninguém assumir que basta trocar o target.
- dbt Core continua em 1.x (1.12). Existe dbt v2, mas o adapter do DuckDB
  ainda é da linha 1.x; migrar fica para quando o adapter acompanhar.
