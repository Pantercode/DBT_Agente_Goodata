# Registro de decisões

Formato curto: contexto, decisão, consequências. Uma decisão revista ganha um
registro novo que aponta para o antigo; o antigo não é apagado.

| # | decisão | status |
|---|---|---|
| [001](001-duckdb-local-bigquery-target.md) | DuckDB como warehouse local, BigQuery como target preparado | aceita |
| [002](002-lake-com-payload-simplificado.md) | Lake guarda o item simplificado, não o JSON bruto da API | aceita |
| [003](003-scd2-a-partir-das-particoes.md) | SCD2 derivado das partições, sem `dbt snapshot` | aceita |
| [004](004-wap-com-circuit-breaker-duplo.md) | WAP com cópia física e circuit breaker em dois pontos | revista em parte pela 009 |
| [005](005-orquestracao-por-script.md) | Orquestração em script Python, sem Airflow/Dagster | aceita |
| [006](006-agente-sql-guardado.md) | Agente com function calling manual e SQL validado por AST | aceita |
| [007](007-painel-fastapi-plotly.md) | Painel em FastAPI + Plotly, não Streamlit | aceita |
| [008](008-ldm-gooddata-em-codigo.md) | Modelo lógico do GoodData declarado em código | aceita |
| [009](009-quarentena-por-particao.md) | Quarentena por partição e processamento só do que é novo | aceita |
| [010](010-agente-com-memoria-e-avaliacao.md) | Agente com memória de exemplos verificados, streaming e avaliação | aceita |
