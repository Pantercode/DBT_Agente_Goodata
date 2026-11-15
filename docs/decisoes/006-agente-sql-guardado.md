# 006. Agente com function calling manual e SQL validado por AST

**Contexto.** O agente gera SQL a partir de linguagem natural e roda em
produção (Vercel), exposto na internet. Riscos: ler o que não deve, escrever,
inventar número, travar a função por minutos.

**Decisão.**
- **Modelo:** Gemini (chave do Google AI Studio), via SDK `google-genai`.
  `gemini-3.8-flash` com reserva automática para `gemini-3.5-flash` e
  `gemini-3.1-flash-lite` quando o principal devolve 503/504, o que acontece
  com frequência no free tier. Timeout de 45 s por chamada e no máximo 2
  tentativas: o padrão do SDK tenta por minutos e estoura o limite da função.
- **Loop manual**, não o `automatic_function_calling` do SDK: cada passo entra
  num rastro que o usuário vê ("como cheguei nessa resposta"), com o SQL que
  rodou. Teto de 8 iterações.
- **Ferramentas estreitas**: listar/descrever tabela (do `catalogo.json`),
  consultar SQL, definição de métrica, status de qualidade, exemplo canônico de
  modelo dbt. Nenhuma escreve.
- **Três camadas de defesa no SQL:**
  1. prompt: só `publicado`, nunca média de razões, todo número precisa vir de consulta;
  2. AST (sqlglot): um statement, só SELECT, só tabelas de `publicado` que
     existem, sem table functions, LIMIT obrigatório (≤ 1000);
  3. conexão: DuckDB em memória com só `publicado`, acesso a arquivo e rede
     desligados e configuração travada.

**Consequências.**
- A camada 3 sozinha já impede leitura de disco; a 2 dá mensagem de erro útil
  para o modelo se corrigir na mesma conversa.
- `tests/test_guarda_sql.py` tem 13 tentativas de escape que precisam ser recusadas.
- Testado com a pergunta "5 UFs com menos museus por 100 mil e população sem
  museu": o agente listou tabelas, leu `agg_cobertura_uf`, buscou a definição
  da métrica e fez uma consulta. Os números batem com o mart.
