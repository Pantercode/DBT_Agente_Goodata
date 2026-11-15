# 003. SCD2 derivado das partições, sem `dbt snapshot`

**Contexto.** Queremos o histórico de cada museu (abriu, fechou, mudou de
esfera, ganhou plano museológico). O caminho padrão é `dbt snapshot`.

O snapshot carimba a vigência com a hora da execução e guarda estado na
própria tabela. Isso tem três problemas aqui: não reconstrói o passado (backfill
de partições antigas não gera as versões), não é idempotente (rodar duas vezes
no mesmo dia pode abrir versão) e é difícil de testar.

**Decisão.** `dim_museu` é recalculada a partir de todas as partições do lake:
hash dos atributos rastreados por (museu, dt), `lag` para detectar mudança,
`lead` para fechar a vigência. Museu que some do cadastro tem a versão fechada
no último dia em que apareceu e `is_removido_do_cadastro = true`.

**Consequências.**
- Mesmo lake, mesma dimensão. Backfill funciona.
- Unit test (`scd2_abre_versao_quando_status_muda_e_fecha_quando_some`) e o
  CI (duas partições na fixture, com um museu que fecha e um que some)
  cobrem o comportamento.
- Custo: relê todas as partições a cada build. Hoje são ~4 mil linhas/dia; um
  ano dá 1,5 milhão de linhas, nada para DuckDB ou BigQuery. Se passar de
  dezenas de milhões, a troca é materializar `dim_museu` como incremental
  (merge pela versão aberta) mantendo a mesma lógica de hash.
- Mudança que acontece e desfaz entre duas extrações não é vista. Com carga
  diária, é a resolução que temos.
