# 007. Painel em FastAPI + Plotly, não Streamlit

**Contexto.** O painel precisa rodar na Vercel. Streamlit mantém um servidor
com WebSocket por sessão; a Vercel executa funções sob demanda e não sustenta
isso.

**Decisão.** FastAPI renderiza HTML (Jinja2) e as figuras são montadas em
Python com `plotly.graph_objects`; o navegador só recebe o JSON e desenha com
plotly.js. Filtros (região/UF) são query string, então toda visão tem URL.

**Consequências.**
- Cada gráfico tem uma tabela equivalente (`<details>`), para leitor de tela e
  para quem quer copiar os números.
- Paleta categórica validada com o validador de daltonismo (3 cores; natureza
  administrativa tem exatamente 3 categorias). Rampa sequencial de um matiz só.
- Sem estado no servidor. O chat do agente guarda o histórico no navegador.
- O mapa usa a malha do IBGE, que vem com orientação de anel RFC 7946; o d3-geo
  do Plotly espera o contrário. `consumo/geo.py` reorienta (com teste).
