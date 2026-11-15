// Chat do agente, em streaming. Funciona na página /agente e na gaveta lateral
// das outras páginas. O histórico fica só no navegador.
//
// O servidor manda NDJSON (um evento JSON por linha): inicio, passo (rodando /
// ok / erro), grafico, texto (delta), fim (texto final + sugestões), erro.
(() => {
  const lista = document.getElementById('mensagens');
  const form = document.getElementById('form-pergunta');
  const campo = document.getElementById('campo');
  if (!lista || !form) return;
  const historico = [];
  const recorte = document.body.dataset.recorte || 'Brasil';

  const rotulo = {
    listar_tabelas: () => 'Conferindo as tabelas publicadas',
    descrever_tabela: a => `Lendo a estrutura de ${a.tabela}`,
    consultar_sql: a => a.objetivo ? `Consultando: ${a.objetivo}` : 'Consultando os dados',
    definicao_metrica: a => `Buscando a definição de “${a.termo}”`,
    status_qualidade: () => 'Checando a saúde dos dados',
    obter_exemplo_canonico: a => `Lendo o modelo canônico de ${a.camada}`,
    criar_grafico: a => `Desenhando: ${a.titulo}`,
  };

  const escapar = t => { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; };
  const md = t => DOMPurify.sanitize(marked.parse(t || ''));

  function bolha(classe, html) {
    document.querySelector('.comecar')?.remove();  // os temas iniciais saem quando a conversa começa
    const li = document.createElement('li');
    li.className = `msg ${classe}`;
    li.innerHTML = html;
    lista.appendChild(li);
    li.scrollIntoView({behavior: 'smooth', block: 'end'});
    return li;
  }

  function rolar(el) {
    const caixa = lista.closest('.gaveta') ? lista : document.scrollingElement;
    const perto = caixa.scrollHeight - caixa.scrollTop - caixa.clientHeight < 160;
    if (perto) el.scrollIntoView({block: 'end'});
  }

  function montarResposta() {
    const li = bolha('msg-agente msg-ao-vivo', `
      <ol class="passos-vivos" aria-label="O que o assistente está fazendo"></ol>
      <div class="graficos-msg"></div>
      <div class="corpo-msg"><span class="pensando">Pensando<span class="reticencias"></span></span></div>
      <div class="rodape-msg" hidden></div>`);
    return {
      li,
      passos: li.querySelector('.passos-vivos'),
      graficos: li.querySelector('.graficos-msg'),
      corpo: li.querySelector('.corpo-msg'),
      rodape: li.querySelector('.rodape-msg'),
      sqls: [],
      itensPasso: [],
    };
  }

  function passo(ui, ev) {
    if (ev.estado === 'rodando') {
      const item = document.createElement('li');
      item.className = 'passo passo-rodando';
      item.innerHTML = `<span class="passo-icone" aria-hidden="true"></span>
        <span class="passo-texto">${escapar((rotulo[ev.ferramenta] || (() => ev.ferramenta))(ev.argumentos || {}))}</span>
        <span class="passo-tempo"></span>`;
      ui.passos.appendChild(item);
      ui.itensPasso.push(item);
      rolar(item);
      return;
    }
    const item = ui.itensPasso.findLast(i => i.classList.contains('passo-rodando')) || ui.itensPasso.at(-1);
    if (!item) return;
    item.classList.remove('passo-rodando');
    item.classList.add(ev.estado === 'erro' ? 'passo-erro' : 'passo-ok');
    item.querySelector('.passo-tempo').textContent = `${ev.duracao_ms} ms`;
    if (ev.sql) {
      ui.sqls.push(ev.sql);
      const det = document.createElement('details');
      det.className = 'passo-sql';
      det.innerHTML = `<summary>SQL</summary><pre><code>${escapar(ev.sql)}</code></pre>`;
      item.appendChild(det);
    }
  }

  function grafico(ui, ev) {
    const cartao = document.createElement('figure');
    cartao.className = 'grafico-msg';
    cartao.innerHTML = `<figcaption>${escapar(ev.titulo || '')}</figcaption><div class="plot-msg"></div>`;
    ui.graficos.appendChild(cartao);
    const alvo = cartao.querySelector('.plot-msg');
    const fig = ev.figura;
    if (window.Plotly) {
      Plotly.newPlot(alvo, fig.data, fig.layout, {displayModeBar: false, responsive: true, scrollZoom: false})
        .then(() => window.animarBarras?.(alvo, fig));
    }
    rolar(cartao);
  }

  function finalizar(ui, ev, pergunta) {
    ui.finalizado = true;
    ui.li.classList.remove('msg-ao-vivo');
    ui.corpo.innerHTML = md(ev.texto);
    ui.passos.classList.add('passos-concluidos');
    if (ui.itensPasso.length) {
      const resumo = document.createElement('li');
      resumo.className = 'passos-resumo';
      resumo.textContent = `${ui.itensPasso.length} passo${ui.itensPasso.length > 1 ? 's' : ''} · ver como cheguei nisso`;
      resumo.addEventListener('click', () => ui.passos.classList.toggle('passos-abertos'));
      ui.passos.prepend(resumo);
    }
    ui.rodape.hidden = false;
    ui.rodape.innerHTML = `
      <div class="acoes-msg">
        ${ui.sqls.length ? '<button type="button" class="acao-msg" data-acao="copiar">Copiar SQL</button>' : ''}
        <button type="button" class="acao-msg" data-acao="util" aria-label="Resposta útil">👍</button>
        <button type="button" class="acao-msg" data-acao="inutil" aria-label="Resposta não ajudou">👎</button>
        <span class="meta">${escapar(ev.modelo || '')} · ${ev.tokens || 0} tokens</span>
      </div>
      ${ev.sugestoes?.length ? `<div class="sugestoes-msg">${ev.sugestoes.map(s =>
        `<button type="button" class="sugestao">${escapar(s)}</button>`).join('')}</div>` : ''}`;
    ui.rodape.querySelectorAll('.sugestao').forEach(b => b.addEventListener('click', () => perguntar(b.textContent)));
    ui.rodape.querySelector('[data-acao="copiar"]')?.addEventListener('click', async e => {
      await navigator.clipboard.writeText(ui.sqls.join(';\n\n') + ';');
      e.target.textContent = 'Copiado';
    });
    ui.rodape.querySelectorAll('[data-acao="util"], [data-acao="inutil"]').forEach(b => b.addEventListener('click', async () => {
      ui.rodape.querySelectorAll('[data-acao="util"], [data-acao="inutil"]').forEach(x => x.disabled = true);
      b.classList.add('acao-marcada');
      await fetch('/api/agente/feedback', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({pergunta, resposta: ev.texto, sqls: ui.sqls, util: b.dataset.acao === 'util'}),
      }).catch(() => {});
    }));
    historico.push({papel: 'usuario', texto: pergunta}, {papel: 'agente', texto: ev.texto});
    rolar(ui.rodape);
  }

  async function perguntar(texto) {
    bolha('msg-usuario', escapar(texto));
    const ui = montarResposta();
    const botao = form.querySelector('button');
    botao.disabled = true;
    let textoAoVivo = '';
    let agendado = false;
    // Enquanto o texto chega, o bloco "Próximas perguntas" fica de fora (no fim ele vira botões).
    const semSugestoes = t => t.replace(/\n\s*-{3,}\s*\n\s*\**Próximas perguntas[\s\S]*$/i, '');
    const renderTexto = () => {
      agendado = false;
      if (ui.finalizado) return;  // um quadro atrasado não pode sobrescrever a resposta final
      ui.corpo.innerHTML = md(semSugestoes(textoAoVivo)) + '<span class="cursor" aria-hidden="true"></span>';
      rolar(ui.corpo);
    };

    try {
      const r = await fetch('/api/agente/stream', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({pergunta: texto, historico, recorte}),
      });
      if (!r.ok || !r.body) throw new Error(`Erro ${r.status}`);
      const leitor = r.body.getReader();
      const dec = new TextDecoder();
      let buffer = '';
      for (;;) {
        const {value, done} = await leitor.read();
        if (done) break;
        buffer += dec.decode(value, {stream: true});
        let quebra;
        while ((quebra = buffer.indexOf('\n')) >= 0) {
          const linha = buffer.slice(0, quebra).trim();
          buffer = buffer.slice(quebra + 1);
          if (!linha) continue;
          const ev = JSON.parse(linha);
          if (ev.tipo === 'passo') passo(ui, ev);
          else if (ev.tipo === 'grafico') grafico(ui, ev);
          else if (ev.tipo === 'texto') {
            textoAoVivo += ev.delta;
            if (!agendado) { agendado = true; requestAnimationFrame(renderTexto); }
          } else if (ev.tipo === 'fim') finalizar(ui, ev, texto);
          else if (ev.tipo === 'erro') throw new Error(ev.mensagem);
        }
      }
    } catch (e) {
      ui.li.classList.remove('msg-ao-vivo');
      ui.li.classList.add('msg-erro');
      ui.corpo.textContent = e.message;
    } finally {
      botao.disabled = false;
    }
  }

  form.addEventListener('submit', ev => {
    ev.preventDefault();
    const texto = campo.value.trim();
    if (!texto) return;
    campo.value = '';
    perguntar(texto);
  });

  campo.addEventListener('keydown', ev => {
    if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); form.requestSubmit(); }
  });

  document.querySelectorAll('#sugestoes button, .sugestao-inicial').forEach(b =>
    b.addEventListener('click', () => perguntar(b.dataset.pergunta || b.textContent.trim())));

  // usado pela gaveta, pelos botões "Perguntar sobre isto" e pela paleta de comandos
  window.perguntarAgente = perguntar;
})();
