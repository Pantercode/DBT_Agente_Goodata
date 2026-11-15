# GoodData

O GoodData é o segundo consumidor dos marts, para quem quer montar a própria
análise sem SQL. Mesmo dado, mesmas métricas do painel (`docs/metricas.md`).

```mermaid
flowchart LR
    P[(publicado.gd_municipio<br/>publicado.gd_museu)] -- carregar_destino --> D[(MotherDuck ou<br/>PostgreSQL<br/>schema museus_gd)]
    D -- data source --> W[Workspace museus_br]
    C[gooddata/modelo_logico.py] -- put_declarative_ldm --> W
    M[gooddata/metricas.yaml] -- put_declarative_analytics_model --> W
    MCP[Claude Code + MCP do GoodData] -- cria visualizações e dashboard --> W
    W -- provisionar --exportar --> L[gooddata/layout/*.json<br/>versionado]
```

## Passo a passo

1. **Destino.** O GoodData Cloud não lê o DuckDB local. Escolha um:
   - MotherDuck: crie um token em app.motherduck.com e ponha `MOTHERDUCK_TOKEN` no `.env`;
   - PostgreSQL (Neon, Supabase...): ponha `GD_PG_URL=postgresql://...` e `GD_DESTINO=postgres`.

   ```bash
   python -m gooddata.carregar_destino motherduck
   ```

2. **Workspace.** Com `GOODDATA_HOST` e `GOODDATA_TOKEN` no `.env`:

   ```bash
   python -m gooddata.provisionar --validar   # offline: LDM + MAQL
   python -m gooddata.provisionar             # cria fonte, workspace, LDM e métricas
   ```

3. **Dashboard via MCP.** O `.mcp.json` na raiz registra o servidor MCP do
   GoodData para o Claude Code, lendo `GOODDATA_HOST`, `GOODDATA_WORKSPACE` e
   `GOODDATA_TOKEN` do ambiente. Abra o Claude Code na pasta do projeto com
   essas variáveis definidas, aprove o servidor `gooddata` e peça o dashboard.
   Depois:

   ```bash
   python -m gooddata.provisionar --exportar  # traz visualizações e dashboard para gooddata/layout/
   ```

## Modelo lógico

| dataset | tabela | grão | atributos | fatos |
|---|---|---|---|---|
| Município | `gd_municipio` | `municipio_id` | município, UF, região, porte, cobertura | população, museus ativos, tem museu (0/1), população sem museu |
| Museu | `gd_museu` | `museu_id` | nome, tipo, temática, status, natureza, perfil, faixa de gestão, década | ativo (0/1), índice de gestão, plano (0/1), sem acessibilidade (0/1), equipe, bens |

Museu → Município pela coluna `municipio_id`. Por isso "museus ativos por UF"
funciona: o MAQL sobe do museu para o município e do município para a UF.

## Métricas

As 10 métricas estão em `gooddata/metricas.yaml`. As marcadas `core` são as
mesmas do painel e do dbt Semantic Layer; `tests/test_metricas_consistentes.py`
falha se uma delas sumir de um dos lados ou não estiver documentada.

## Dashboard sugerido

| bloco | visualização | métrica × atributo |
|---|---|---|
| capa | 4 headlines | museus ativos, museus por 100 mil, % municípios com museu, % população sem museu |
| território | mapa de UF ou barras ordenadas | museus por 100 mil × UF |
| porte | barras 100% empilhadas | contagem de municípios × porte × cobertura museal |
| gestão | tabela com cor | índice de gestão médio e % com plano × natureza administrativa |
| acessibilidade | barras | % sem acessibilidade × tipo de museu |
