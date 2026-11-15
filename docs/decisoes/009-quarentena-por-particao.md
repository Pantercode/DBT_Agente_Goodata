# 009. Quarentena por partição e processamento só do que é novo

Revisa parte do [004](004-wap-com-circuit-breaker-duplo.md).

**Contexto.** Com o 004, qualquer teste bloqueante que falhasse barrava a
publicação inteira. Uma coleta ruim (API devolvendo metade dos itens, campos
vazios) deixava o painel parado na versão anterior até alguém intervir. E
como staging, dimensão SCD2 e o enriquecimento reliam todas as partições a
cada build, corrigir um dia significava reprocessar tudo.

O pedido era: se a coleta de amanhã vier quebrada, mostrar só o que é
coerente e não reprocessar tudo.

**Decisão.**

1. **Validação por partição** (`int_particoes__validacao`, incremental). Cada
   dia de cada fonte é comparado com o próprio manifesto, com a régua de
   volume (maior contagem das 7 partições válidas anteriores, -10% / +30%),
   com completude de campos obrigatórios e com duplicidade. Falhou uma regra:
   `quarentena`, com o motivo por extenso.
2. **Partição em quarentena não entra.** `int_museus__enriquecido` só lê
   partições válidas; tudo a jusante (SCD2, fato, agregados, GoodData) herda
   isso. A "foto atual" passa a ser a última partição **válida**, não a última
   partição. Registros com valor impossível dentro de partição válida (sem
   nome, sem status, UF inexistente) também ficam de fora e são listados.
3. **Os testes mudam de lugar.** Staging vê todas as partições, então os
   testes ali só avisam. Os bloqueantes ficam depois da quarentena. Assim uma
   coleta ruim não bloqueia mais a publicação: ela é isolada, e o resto
   publica.
4. **Incremental de ponta a ponta.** Validação, enriquecimento, SCD2 e fato
   processam só partições novas (mais a janela de 3 dias). O SCD2 incremental
   compara as partições novas com as versões abertas (~4 mil linhas), não com
   o histórico. Partição que sai de válida para quarentena dentro da janela é
   removida por `pre_hook`. Backfill pontual: `--vars '{reprocessar_desde: AAAA-MM-DD}'`.
5. **O circuit breaker continua** para o que não é problema de coleta: regra
   de negócio quebrada (pesos), erro de SQL, integridade entre dimensão e fato.

**Testado.**

- Coleta simulada de 15/11 com metade dos museus e 14% sem UF
  (`scripts/simular_coleta_ruim.py`): partição em quarentena com o motivo
  "volume 2079 fora da faixa (régua 4159); campos obrigatórios vazios (sem UF
  14.4%)"; pipeline saiu com código 0 e status `sucesso_com_quarentena`;
  publicou 22 marts com os dados de 14/11 (3.775 museus ativos, igual antes);
  o painel mostra o aviso no cabeçalho.
- CI: a amostra do lake tem um terceiro dia quebrado. O job verifica que ele
  vai para quarentena, que os marts ficam no dia anterior, e que um segundo
  build não muda nenhuma contagem (idempotência). A dimensão SCD2 não fecha
  as versões dos museus que "sumiram" na coleta quebrada.
- Unit test do caminho incremental do SCD2 (âncora fecha, versão nova abre,
  museu ausente fecha como removido, linha já processada é ignorada).

**Consequências.**

- O painel pode mostrar dado de ontem sem ninguém perceber. Por isso o aviso
  no cabeçalho, a aba "Saúde da coleta" e a ferramenta `status_qualidade` do
  agente; e o teste `atualizado_ha_no_maximo` avisa quando a última partição
  válida passa de 2 dias.
- A régua de volume usa o máximo recente: uma queda real e grande do cadastro
  (limpeza em massa pelo Ibram) também vai para quarentena. É o comportamento
  desejado: alguém confere e libera com `reprocessar_desde` depois de ajustar a
  tolerância ou o piso.
- Unit test de modelo incremental precisa da tabela existindo; num warehouse
  novo o pipeline (e o CI) fazem um bootstrap de `dim_museu` antes do build.
