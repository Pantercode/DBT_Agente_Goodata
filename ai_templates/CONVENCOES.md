# Convenções de modelagem

Contexto para geração assistida (agente deste repositório, Antigravity, Copilot).
Os exemplos desta pasta são cópias comentadas de modelos reais do projeto e
passam no `dbt build`. Ao gerar um modelo novo, siga o exemplo da camada.

## Camadas

| camada | prefixo | materialização | pode fazer | não pode fazer |
|---|---|---|---|---|
| staging | `stg_<fonte>__<entidade>` | view | renomear, tipar, limpar sentinelas, extrair JSON | join, regra de negócio, agregação |
| intermediate | `int_<entidade>__<verbo/qualidade>` | view | joins, regras, índices, deduplicação | ser lido por BI |
| mart | `dim_`, `fct_`, `agg_`, `obt_`, `mart_` | table / incremental | modelar para consumo | lógica que não esteja no intermediate |

## SQL

- CTEs no topo, uma por responsabilidade, nomes em português (`fonte`, `campos`, `final`).
- `select * from {{ ref() }}` só na primeira CTE. Depois, colunas explícitas.
- Toda função que muda entre DuckDB e BigQuery vai por macro de `macros/cross_db.sql`
  (`json_texto`, `struct_de`, `somar_dias`...). Nunca use `json_extract_string` direto.
- Booleanos começam com `is_`, `possui_`, `atende_`, `tem_`. Contagens com `qtd_`.
  Percentuais com `pct_` e guardados entre 0 e 1.
- Razões são calculadas no mart, uma vez. Nunca deixe o BI dividir.
- Grão declarado no comentário do topo ("um registro por ...").

## Incremental

- Particionado por `dt` (data de extração).
- DuckDB: `delete+insert` com `unique_key='dt'`. BigQuery: `insert_overwrite` + `partition_by`.
- Filtro incremental sempre com janela de reprocessamento (`var('janela_reprocessamento_dias')`).
- No BigQuery, fatos grandes com `require_partition_filter = true`.

## Testes (mínimo por modelo)

- Chave primária: `unique` + `not_null` (ou `unico_por` para chave composta).
- FK para dimensão: `relationships`.
- Marts publicados: `volume_estavel`.
- Testes que devem impedir a publicação recebem `tags: ["bloqueante"]`.

## Documentação

- `description` em todo modelo e em toda coluna que não seja autoexplicativa.
- Definição de negócio repetida em mais de um lugar vira `{% docs %}` em `models/docs.md`.
