# Arquitetura

## Visão geral

```mermaid
flowchart LR
    subgraph fontes[Fontes públicas]
        T[MuseusBr / Tainacan<br/>4.159 museus<br/>536 pontos de memória]
        I[IBGE<br/>localidades + SIDRA 4709<br/>+ malha de UFs]
    end

    subgraph lake[Landing zone · data/lake/raw]
        L[(JSONL.gz<br/>particionado por dt=<br/>+ _manifest.json)]
    end

    subgraph wh[Warehouse · DuckDB local / BigQuery]
        RAW[raw<br/>views / external tables]
        STG[staging<br/>view]
        INT[intermediate<br/>view]
        AUD[auditoria<br/>marts: table / incremental]
        PUB[(publicado)]
        OBS[(observabilidade)]
    end

    subgraph consumo[Consumo]
        SRV[data/serving<br/>Parquet + catalogo.json]
        P[Painel FastAPI + Plotly<br/>Vercel]
        A[Agente Gemini<br/>function calling]
        GD[GoodData Cloud<br/>LDM + MAQL + dashboards]
    end

    T -- ingestao --> L
    I -- ingestao --> L
    L --> RAW --> STG --> INT --> AUD
    AUD -- testes --> OBS
    AUD == publicar_marts<br/>só se o audit passar ==> PUB
    PUB --> SRV --> P
    SRV --> A
    P <--> A
    PUB -- carregar_destino --> GD
```

## Camadas do dbt

```mermaid
flowchart LR
    s1[stg_tainacan__museus] --> i1[int_museus__indicadores]
    s1 --> i2[int_museus__municipio_resolvido]
    s3[stg_ibge__municipios] --> i2
    s4[stg_ibge__populacao] --> i4[int_municipios__com_populacao]
    s3 --> i4
    seed1([pesos_indice_gestao]) --> i1
    seed2([de_para_municipios]) --> i2
    seed3([classificacao_esfera]) --> i3
    i1 --> i3[int_museus__enriquecido]
    i2 --> i3
    i3 --> i5[int_museus__atual]
    i3 --> d1[dim_museu<br/>SCD2]
    i3 --> f1[fct_museus_diario<br/>incremental]
    d1 --> f1
    i4 --> d2[dim_municipio]
    i5 --> o1[obt_museus<br/>STRUCT + ARRAY]
    d2 --> a1[agg_cobertura_municipio]
    i5 --> a1
    a1 --> a2[agg_cobertura_uf]
    a1 --> a3[agg_cobertura_brasil]
    a1 --> g1[gd_municipio]
    i5 --> g2[gd_museu]
    s2[stg_tainacan__pontos_memoria] --> i6[int_pontos_memoria__atual] --> a2
```

Regras que o desenho garante:

- **Uma junção, um lugar.** `int_museus__enriquecido` é o único modelo que junta
  staging, indicadores, município e esfera. Todo mart lê dele. Se a regra de
  "museu ativo" mudar, muda num arquivo.
- **Razão calculada uma vez.** `museus_por_100k_hab`, `pct_*` nascem nos `agg_*`.
  Painel, agente e GoodData leem prontas ou refazem a mesma conta sobre as
  mesmas colunas (`docs/metricas.md`).
- **Nenhum consumidor lê `auditoria`.** A conexão do painel/agente só tem
  `publicado`; o GoodData só recebe `gd_*` de `publicado`.

## Write-Audit-Publish

```mermaid
sequenceDiagram
    participant O as orquestracao.pipeline
    participant D as dbt
    participant A as auditoria
    participant Obs as observabilidade
    participant P as publicado

    O->>D: dbt source freshness
    D-->>O: fontes dentro do SLA? (senão: bloqueia)
    O->>D: dbt build
    D->>A: write (marts)
    D->>A: audit (112 testes + 3 unit tests)
    D->>Obs: on-run-end: resultado de cada nó
    O->>O: circuit breaker lê run_results
    alt falha bloqueante
        O-->>O: exit 2, status "bloqueado"<br/>publicado intocado
    else tudo ok
        O->>D: run-operation publicar_marts
        D->>Obs: confere de novo a última execução
        D->>P: cópia em transação (DuckDB) / CLONE (BigQuery)
        D->>Obs: historico_publicacoes (base do teste de volume)
        O->>O: exporta serving (Parquet + catálogo)
    end
```

O breaker existe em dois lugares de propósito: no orquestrador e dentro da
macro `publicar_marts`. Quem rodar o publish na mão também é barrado.

Testado de verdade: com o seed de pesos somando 101, o build falhou no teste
`soma_igual_a`, 60 nós a jusante não rodaram, o pipeline saiu com código 2 e
`data/serving` não foi tocado.

### O que é bloqueante

| teste | onde | por quê |
|---|---|---|
| `unico_por` museu × dt | staging, intermediate, fato | duplicata infla toda contagem |
| `reconcilia_com_manifest` | staging | perda silenciosa de linhas entre lake e warehouse |
| `cobertura_minima` município ≥ 99% | intermediate | abaixo disso os agregados territoriais mentem |
| `scd2_valida` | dim_museu | vigências sobrepostas duplicam o fato no join |
| `volume_estavel` (±10%) | marts publicados | extração parcial ou filtro quebrado |
| `no_intervalo` museus ativos ≥ 1000 | agg_cobertura_brasil | piso de sanidade |
| `soma_igual_a` 100 | seed de pesos | índice de gestão fora da escala |
| `relationships` | dim → dim_municipio, gd_museu → gd_municipio | fato órfão some do BI |

Avisos (não bloqueiam, aparecem na aba Qualidade): cobertura de coordenadas,
status fora da lista conhecida, partição com mais de 2 dias.

## Quando a coleta vem quebrada

```mermaid
flowchart LR
    L[(partição nova<br/>dt=15/11)] --> V{int_particoes__validacao<br/>manifesto · volume · completude · duplicidade}
    V -- válida --> E[int_museus__enriquecido<br/>incremental]
    V -- quarentena --> Q[mart_saude_coleta<br/>motivo por extenso]
    E --> M[dim/fct/agg<br/>só partições novas]
    M --> P[(publicado)]
    Q --> A[aviso no painel<br/>+ aba Saúde da coleta<br/>+ agente]
    P -. usa a última<br/>partição válida .-> A
```

A coleta de um dia é validada antes de entrar. Se falha, vai para quarentena
com o motivo; os marts continuam com a última coleta coerente e a publicação
acontece normalmente (status `sucesso_com_quarentena`). O breaker de 004 fica
para o que não é problema de coleta. Detalhes e testes em
[decisões/009](decisoes/009-quarentena-por-particao.md).

| modelo | incremental por | o que relê a cada build |
|---|---|---|
| `int_particoes__validacao` | fonte × dt | só partições novas + janela de 3 dias |
| `int_museus__enriquecido` | dt | só partições novas **e válidas** (pruning no lake) |
| `dim_museu` (SCD2) | museu_sk | partições novas + ~4 mil versões abertas |
| `fct_museus_diario` | dt | só partições novas |

## Incremental e reprocessamento

`fct_museus_diario` é incremental por partição `dt`:

- DuckDB: `delete+insert` com `unique_key = 'dt'`
- BigQuery: `insert_overwrite`, `partition_by dt`, `cluster_by [uf_sigla, municipio_id, museu_id]`, `require_partition_filter = true`

Cada execução reescreve as últimas `janela_reprocessamento_dias` (3) partições.
Rodar duas vezes o mesmo dia dá o mesmo resultado (o CI verifica). Correção
retroativa na origem entra sem full-refresh.

## Serving e Vercel

A Vercel roda funções sem disco persistente, então o painel não pode abrir o
warehouse. `orquestracao/serving.py` exporta `publicado` para Parquet (1,3 MB
no total) e um `catalogo.json` (descrições, colunas, linhagem, métricas,
testes). Esses arquivos vão no deploy. Em memória, `consumo/dados.py` monta as
tabelas no schema `publicado` e desliga acesso a arquivos e rede
(`enable_external_access = false`, `lock_configuration = true`).

Atualizar o painel = rodar o pipeline + commitar `data/serving` + deploy.
