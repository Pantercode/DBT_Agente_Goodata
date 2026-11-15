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

O que foi aplicado no workspace `Goodata_agentes` (trial), em 15/11/2026:

1. **Dados no armazenamento gerenciado do GoodData** (fonte `GDSTORAGE`, id `museus_br`).
   Não precisa de banco externo: `gd_municipio` e `gd_museu` sobem como CSV pela API.
2. **Modelo lógico + 11 métricas** por código, mesclando com o que já existe no workspace:
   ```bash
   python -m gooddata.provisionar            # GD_DESTINO=gdstorage é o padrão
   ```
   As métricas executadas no GoodData batem com o painel em Python (3.775 museus ativos,
   4.159 cadastrados, 25,1% dos municípios com museu, 31,5% da população sem museu).
3. **Dashboard "Museus do Brasil" pelo MCP do GoodData** (10 visualizações, filtros de
   região e UF, 4 seções), declarado em [`gooddata/dashboard.py`](../gooddata/dashboard.py):
   ```bash
   python -m gooddata.dashboard              # cria pelo MCP; o que já existe é atualizado via REST
   python -m gooddata.dashboard --validar    # executa cada visualização e mostra os números
   ```
4. **Exportar o estado do workspace** para revisão em PR:
   ```bash
   python -m gooddata.provisionar --exportar
   ```

Variáveis no `.env`: `GOODDATA_HOST`, `GOODDATA_WORKSPACE`, `GOODDATA_TOKEN`.
O `.mcp.json` usa as mesmas para o Claude Code falar com o MCP; `gooddata/mcp_cliente.py`
faz o mesmo em Python.

Limitações do trial: as ferramentas `execute_visualization` do MCP não estão liberadas
(a conferência usa a API de execução). MotherDuck/PostgreSQL continuam suportados
(`GD_DESTINO=motherduck|postgres`) para quando o GoodData ler de um warehouse.

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
