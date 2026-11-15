    /* ===================== DBT ===================== */
    /* Cole este bloco dentro de `projects: [ ... ]` em assets/data.js do portfólio.
       Troque RENDER_URL pelo endereço que o Render gerar. */
    {
      id: "museus-brasil", cat: "dbt", title: "Museus do Brasil · dbt com Write-Audit-Publish, Agente de IA e GoodData",
      live: true,
      summary: "Pipeline completo de Analytics Engineering sobre o Cadastro Nacional de Museus (Ibram) cruzado com o Censo 2022: lake particionado, dbt com esquema estrela, SCD2 incremental e quarentena de coletas ruins, painel em Python publicado no Render, agente de IA (Gemini) que responde em português com gráficos, e o mesmo modelo no GoodData montado via MCP. Mostra que 31,5% dos brasileiros (64 milhões) vivem em cidade sem museu.",
      stack: ["dbt-core 1.12", "DuckDB", "Python 3.12", "FastAPI", "Plotly", "Google Gemini", "GoodData (MCP)", "Render"],
      links: [
        { label: "Painel publicado", url: "https://museus-do-brasil.onrender.com/", primary: true },
        { label: "Repositório no GitHub", url: "https://github.com/Pantercode/DBT_Agente_Goodata" },
        { label: "Dashboard no GoodData (PDF)", url: "https://github.com/Pantercode/DBT_Agente_Goodata/blob/main/docs/gooddata-dashboard.pdf" }
      ],
      // embed: { type: "app", url: "https://museus-do-brasil.onrender.com/" },   // ver docs/deploy-render.md (opcional)
      intro: ["3.775 museus ativos, mas em só 25% dos municípios. O projeto responde onde há museu no Brasil, onde não há e como eles se organizam, com qualidade de dados que impede número errado de chegar ao painel."],
      sections: [
        { h: "Objetivos do Projeto", ul: [
          "Transformar a API pública do Ibram (4.159 museus) e o Censo 2022 em indicadores confiáveis de cobertura, gestão e acessibilidade.",
          "Garantir que dado ruim nunca chegue ao consumidor: Write-Audit-Publish, 112 testes e quarentena por coleta.",
          "Processar só o que é novo: validação, enriquecimento, SCD2 e fato incrementais por partição.",
          "Manter a mesma métrica em todas as ferramentas: painel, agente de IA e GoodData batem número a número."
        ] },
        { h: "Arquitetura da Solução", ol: [
          "<b>Coleta:</b> API Tainacan do Ibram e APIs do IBGE, gravadas por dia com manifesto (contagem e hash).",
          "<b>Validação:</b> cada coleta é conferida (manifesto, volume, completude, duplicidade); se falhar, vai para quarentena com o motivo.",
          "<b>dbt:</b> staging → intermediate → marts, com esquema estrela (8 dimensões e tabela-ponte), SCD2 incremental e One Big Table com STRUCT/ARRAY.",
          "<b>Publicação:</b> os marts só são publicados se os testes passarem (circuit breaker em dois pontos).",
          "<b>Consumo:</b> painel FastAPI + Plotly no Render, agente Gemini com SQL validado e GoodData via MCP."
        ] },
        { h: "Destaques", ul: [
          "<b>Quarentena:</b> uma coleta com metade dos museus foi isolada sozinha e o painel continuou correto.",
          "<b>Agente de IA:</b> respostas em streaming, gráficos na conversa e 8 de 8 acertos na avaliação com gabarito em SQL.",
          "<b>UX:</b> IA no contexto de cada gráfico, paleta de comandos (Ctrl+K), mapa clicável e paleta validada para daltonismo.",
          "<b>GoodData:</b> modelo lógico, 11 métricas MAQL e dashboard criados por código e pelo servidor MCP."
        ] },
        { h: "Tecnologias Utilizadas", ul: [
          "<b>dbt-core + DuckDB</b> → transformação, testes, contratos e semantic layer (BigQuery como target preparado).",
          "<b>Python</b> → coleta com retry, orquestração e painel (FastAPI + Plotly).",
          "<b>Google Gemini</b> → agente com function calling, memória de exemplos verificados e avaliação.",
          "<b>GoodData Cloud + MCP</b> → modelo semântico e dashboard publicados por código.",
          "<b>Render</b> → hospedagem do painel, com deploy automático a cada push."
        ] }
      ]
    },
