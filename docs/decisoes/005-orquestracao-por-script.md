# 005. Orquestração em script Python, sem Airflow/Dagster

**Contexto.** O pipeline tem seis passos lineares (ingestão, freshness, build,
publish, docs, serving), roda uma vez por dia e leva menos de três minutos.

**Decisão.** `orquestracao/pipeline.py`: cada etapa é uma função idempotente,
o estado vai para `data/serving/status_pipeline.json` e o código de saída
distingue falha (1) de bloqueio por qualidade (2). Agendamento fica com quem
roda o script (cron, GitHub Actions agendado, Cloud Scheduler).

**Consequências.**
- Zero infraestrutura para manter.
- Sem retry por etapa, sem backfill paralelo, sem UI de histórico. Quando o
  projeto tiver dependência entre pipelines ou várias fontes com SLA
  diferente, a migração é direta: cada `etapa_*` vira uma task/asset, e o
  estado em JSON vira o metadata store do orquestrador.
