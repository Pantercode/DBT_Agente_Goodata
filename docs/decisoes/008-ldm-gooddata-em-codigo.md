# 008. Modelo lógico do GoodData declarado em código

**Contexto.** O GoodData gera um LDM automaticamente a partir do scan das
tabelas. Os IDs gerados dependem do nome das colunas e de convenções de
prefixo; métricas MAQL e dashboards referenciam esses IDs.

**Decisão.** O LDM é declarado em `gooddata/modelo_logico.py` (2 datasets:
Município e Museu, com referência Museu → Município) e aplicado com
`put_declarative_ldm`. As métricas ficam em `gooddata/metricas.yaml` e só
fazem SUM/COUNT/divisão sobre colunas que o dbt já entrega prontas
(`gd_municipio`, `gd_museu`, com contrato de tipos).

**Consequências.**
- `python -m gooddata.provisionar --validar` checa offline toda referência
  `{fact/...}`, `{label/...}`, `{metric/...}` do MAQL. Roda no CI.
- Renomear coluna no dbt quebra o contrato antes de quebrar o GoodData.
- Os dashboards são criados pelo servidor MCP do GoodData e exportados de
  volta para `gooddata/layout/` com `--exportar`, para entrar em PR como o resto.
