# Métricas para colar no GoodData

Em *Analisar > Métricas > Criar métrica*, cole o MAQL de cada uma. Os nomes entre
chaves (`{fact/museu.is_aberto}`) precisam bater com os IDs dos campos depois do
upload: confira em *Modelo de dados* e ajuste se o GoodData tiver gerado outro ID.
Crie na ordem desta lista (algumas usam métricas anteriores).

## Museus ativos
ID: `museus_ativos` · formato `#,##0`

```
SELECT SUM({fact/museu.is_aberto})
```

## Museus cadastrados
ID: `museus_cadastrados` · formato `#,##0`

```
SELECT COUNT({attribute/museu.museu_id})
```

## População (Censo 2022)
ID: `populacao` · formato `#,##0`

```
SELECT SUM({fact/municipio.populacao})
```

## Museus ativos por 100 mil habitantes
ID: `museus_por_100k_hab` · formato `#,##0.00`

```
SELECT {metric/museus_ativos} * 100000 / {metric/populacao}
```

## % de municípios com museu ativo
ID: `pct_municipios_com_museu` · formato `#,##0.0%`

```
SELECT SUM({fact/municipio.tem_museu_ativo}) / COUNT({attribute/municipio.municipio_id})
```

## População em municípios sem museu
ID: `populacao_sem_museu` · formato `#,##0`

```
SELECT SUM({fact/municipio.populacao_sem_museu})
```

## % da população em município sem museu
ID: `pct_populacao_sem_museu` · formato `#,##0.0%`

```
SELECT {metric/populacao_sem_museu} / {metric/populacao}
```

## Índice de gestão médio (museus ativos)
ID: `indice_gestao_medio` · formato `#,##0.0`

```
SELECT SUM({fact/museu.indice_gestao_se_ativo}) / {metric/museus_ativos}
```

## % com plano museológico (entre quem respondeu)
ID: `pct_plano_museologico` · formato `#,##0.0%`

```
SELECT SUM({fact/museu.possui_plano_museologico}) / SUM({fact/museu.respondeu_plano_museologico}) WHERE {label/museu.status_funcionamento} = "Aberto"
```

## % de museus ativos sem nenhum recurso de acessibilidade
ID: `pct_museus_sem_acessibilidade` · formato `#,##0.0%`

```
SELECT SUM({fact/museu.sem_acessibilidade}) / {metric/museus_ativos} WHERE {label/museu.status_funcionamento} = "Aberto"
```

## Municípios
ID: `qtd_municipios` · formato `#,##0`

```
SELECT COUNT({attribute/municipio.municipio_id})
```
