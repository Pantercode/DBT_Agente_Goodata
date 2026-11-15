# Runbook

## Primeira vez

```powershell
# Python 3.12 (dbt ainda não suporta 3.14). Com uv:
uv python install 3.12
uv venv .venv --python 3.12
uv pip install --python .venv -r requirements-dev.txt
copy .env.example .env            # preencha GEMINI_API_KEY

.venv\Scripts\python -m orquestracao.pipeline     # ingestão + dbt + publish + serving (~3 min)
.venv\Scripts\uvicorn painel.app:app --reload     # http://127.0.0.1:8000
```

No Linux/macOS troque `.venv\Scripts\` por `.venv/bin/`.

## Comandos do dia a dia

| quero | comando |
|---|---|
| rodar tudo | `python -m orquestracao.pipeline` |
| rodar sem baixar de novo | `python -m orquestracao.pipeline --sem-ingestao` |
| só regerar os Parquet do painel | `python -m orquestracao.pipeline --so-exportar` |
| reextrair um dia específico | `python -m ingestao --dt 2026-11-14` |
| só uma fonte | `python -m ingestao museus` |
| um modelo e o que depende dele | `cd dbt && dbt build --profiles-dir . -s int_museus__indicadores+` |
| publicar na mão | `cd dbt && dbt run-operation publicar_marts --profiles-dir .` |
| documentação do dbt | `cd dbt && dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .` |
| perguntar ao agente pelo terminal | `python -m agente "pergunta" --rastro` |
| testes Python | `pytest` |
| capturas do README | `python scripts/capturar_telas.py` (com o painel rodando) |

## Quando o pipeline para

O código de saída diz o tipo de problema:

- **0** publicou. Se o status for `sucesso_com_quarentena`, uma coleta ficou
  de fora e o painel está com a anterior (ver abaixo).
- **1** falha técnica (API fora, erro de SQL). `publicado` intacto. Veja o log e
  `data/serving/status_pipeline.json`.
- **2** circuit breaker. Os dados chegaram mas não passaram no audit.
  `publicado` intacto. A lista de bloqueios está em `status_pipeline.json` e
  em `observabilidade.resultados`.

### Investigando um bloqueio

```sql
-- no DuckDB (data/warehouse/museus.duckdb)
select nome, status, falhas, mensagem
from observabilidade.resultados
where invocation_id = (select invocation_id from observabilidade.resultados
                       where comando = 'build' order by executado_em desc limit 1)
  and status not in ('pass', 'success');

-- linhas que falharam ficam guardadas (store_failures)
select * from observabilidade_falhas.<nome_do_teste>;
```

Casos conhecidos:

| teste | causa provável | o que fazer |
|---|---|---|
| `reconcilia_com_manifest` | partição gravada pela metade, ou mudança no formato da API | reextrair o dia (`python -m ingestao --dt ...`) |
| `volume_estavel` em `obt_museus` | API devolveu menos itens (paginação quebrou) ou houve limpeza real do cadastro | comparar `_manifest.json` com o dia anterior; se a queda for real, publicar com `--args '{forcar: true}'` e registrar o motivo |
| `cobertura_minima` de `municipio_id` | municípios novos escritos de outro jeito | ver `select * from intermediate.int_museus__municipio_resolvido where metodo_resolucao = 'nao_resolvido'` e incluir no seed `de_para_municipios` com `motivo` |
| `soma_igual_a` nos pesos | alguém editou o seed de pesos | corrigir o CSV; os pesos precisam somar 100 |
| freshness `error` | a ingestão não rodou há mais de 50 h | rodar a ingestão; se a API do Ibram estiver fora, esperar |

## Coleta em quarentena

O painel mostra "Coleta de DD/MM em quarentena" no cabeçalho e o motivo na aba
Qualidade. Nada precisa ser feito para o painel continuar certo: ele já está
com a última coleta coerente.

Para recuperar o dia:

1. Ver o motivo: `select * from publicado.mart_saude_coleta where status = 'quarentena'`.
2. Se foi falha da coleta (API instável): reextrair o dia e rodar de novo.
   ```bash
   python -m ingestao museus --dt 2026-11-15
   python -m orquestracao.pipeline --sem-ingestao
   ```
   A janela incremental (3 dias) revalida a partição sozinha.
3. Se o dia já saiu da janela: `cd dbt && dbt build --profiles-dir . --vars '{reprocessar_desde: 2026-11-15}'`.
4. Se a queda for real (o cadastro encolheu de verdade): ajustar `tolerancia_volume`
   ou `minimo_museus_particao` em `dbt_project.yml`, registrar o porquê no PR e rodar o passo 3.

Para ver a quarentena funcionando sem esperar um dia ruim:

```bash
python scripts/simular_coleta_ruim.py 2026-11-15          # grava uma coleta quebrada no lake
python -m orquestracao.pipeline --sem-ingestao            # vai para quarentena, publica com a anterior
python scripts/simular_coleta_ruim.py 2026-11-15 --apagar # desfaz
python -m orquestracao.pipeline --sem-ingestao
```

## Atualizar o painel publicado

1. `python -m orquestracao.pipeline`
2. `git add data/serving && git commit -m "dados: atualização AAAA-MM-DD"`
3. push. A Vercel publica (se o projeto estiver ligado ao repositório) ou rode `vercel --prod`.

## Vercel

O projeto vai para um app que já existe na sua conta:

```bash
npm i -g vercel
vercel link          # escolha o time e o projeto existente
vercel env add GEMINI_API_KEY production
vercel --prod
```

Variáveis em **Settings → Environment Variables**:

| variável | obrigatória | valor |
|---|---|---|
| `GEMINI_API_KEY` | para o agente | chave do Google AI Studio |
| `GEMINI_MODEL` | não | padrão `gemini-3.8-flash` |

O deploy usa `requirements.txt` (só runtime) e `vercel.json` (função única em
`api/index.py`, 60 s, 1 GB). `.vercelignore` tira dbt, lake e warehouse do upload.
Sem `GEMINI_API_KEY` o painel funciona e a aba do agente mostra que está desligada.

## BigQuery (quando for usar)

Ainda não executado (ver ADR 001). Passos previstos:

1. `pip install dbt-bigquery` e `gcloud auth application-default login`
2. subir o lake: `gsutil -m rsync -r data/lake/raw gs://$MUSEUS_GCS_BUCKET/raw`
3. carregar os `_manifest.json` numa tabela `raw._manifests` (usada pelo teste de reconciliação)
4. `dbt build --profiles-dir . --target bigquery`

O `profiles.yml` já tem `maximum_bytes_billed` de 2 GB.
