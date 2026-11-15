# 004. WAP com cópia física e circuit breaker em dois pontos

**Contexto.** Três consumidores (painel, agente, GoodData) leem os marts. Um
build com dado ruim não pode chegar a eles. Opções avaliadas:

1. Views em `publicado` apontando para `auditoria`. Barato, mas não protege:
   o build reescreve `auditoria` antes do audit e a view já mostra o dado novo.
2. Blue/green com troca de nome de schema. Bom no BigQuery, desajeitado no DuckDB.
3. Cópia de `auditoria` para `publicado` depois do audit.

**Decisão.** Opção 3. No DuckDB, `create or replace table ... as select` de
todos os marts dentro de uma transação. No BigQuery, `CLONE` (metadata-only,
sem custo de bytes processados) numa transação multi-statement. Os marts são
publicados juntos ou nenhum é: KPIs de tabelas diferentes nunca ficam de
versões diferentes.

O circuit breaker roda no orquestrador (lê `run_results.json`) e de novo
dentro da macro (lê `observabilidade.resultados`). O que bloqueia: erro de
execução, nó pulado, teste reprovado com tag `bloqueante` ou severidade error,
fonte fora do SLA no `source freshness`.

**Consequências.**
- Dobra o armazenamento dos marts no DuckDB (2 MB). No BigQuery o CLONE não dobra.
- `--args '{forcar: true}'` existe para emergência e deixa registro no log.
- O teste de volume compara com `historico_publicacoes`, que só é escrito no
  publish: a referência é sempre a última versão que foi ao ar, não a última
  tentativa.
