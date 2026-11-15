# 010. Agente com memória de exemplos verificados, streaming e avaliação

Complementa o [006](006-agente-sql-guardado.md).

**Contexto.** O pedido era um agente "mais inteligente e treinado". Fine-tuning
do Gemini não é viável neste projeto (custo, dados de treino, e o modelo muda
de versão a cada poucos meses). O que dá para fazer, e medir, é melhorar o que
o modelo vê antes de responder e checar a resposta contra um gabarito.

**Decisão.**

1. **Catálogo no prompt.** As tabelas de `publicado` com colunas e descrição de
   uma linha vão no prompt de sistema (gerado do manifest do dbt). O agente não
   gasta mais duas chamadas para descobrir nome de coluna.
2. **Exemplos verificados com recuperação** (`agente/exemplos_verificados.yaml`,
   `agente/memoria.py`). 17 pares pergunta → SQL conferidos contra o painel.
   Para cada pergunta, os 3 mais parecidos (sobreposição de radicais ponderada
   por IDF, sem embedding) entram no prompt com a nota do que é armadilha
   (média de razões, STRUCT, coluna que só existe na dimensão). O CI roda todos
   os SQL: exemplo quebrado falha o build.
3. **Aprende com o uso, com revisão.** 👍/👎 no chat gravam pergunta, resposta e
   SQL. `python -m agente.promover_feedback` lista os aprovados cujo SQL ainda
   roda e não duplicam um exemplo; `--gravar` acrescenta ao YAML para revisão
   em PR. Nada entra no "treino" sem passar por uma pessoa.
4. **Contexto da tela.** A pergunta vai com o recorte do filtro (UF, região);
   o agente usa esse recorte quando a pergunta não diz outro.
5. **Gráficos.** Ferramenta `criar_grafico`: o agente passa SQL e tipo; o
   servidor monta a figura no tema do painel e manda direto para o usuário. O
   modelo recebe só a confirmação e 5 linhas de amostra, para comentar.
6. **Streaming.** `/api/agente/stream` devolve NDJSON: cada ferramenta aparece
   ao vivo, o texto chega em pedaços, o gráfico aparece quando fica pronto.
7. **Avaliação** (`python -m agente.avaliacao`). 8 perguntas com gabarito em
   SQL (roda na hora, então acompanha os dados). Mede acerto do número, citação
   da fonte e passos.

**Resultado medido** (15/11/2026, `gemini-3.1-flash-lite` por fallback de cota):

| | antes (006) | agora |
|---|---|---|
| acerto do número | não medido | **8/8 (100%)** |
| cita a fonte | não medido | 100% |
| passos por pergunta | 4 (pergunta das UFs, medida à mão) | **1,5 em média** |

**Consequências.**
- O prompt ficou ~7 mil caracteres maior. No free tier isso pesa na cota por
  minuto; em troca, cada pergunta faz metade das chamadas.
- A recuperação por radicais erra com sinônimos distantes ("equipamentos
  culturais" não acha "museus"). Com algumas dezenas de exemplos ainda é
  suficiente; passando de ~200, trocar por embedding.
- 8 perguntas é pouco para afirmar mais do que "não regrediu". O conjunto cresce
  junto com os exemplos aprovados.
