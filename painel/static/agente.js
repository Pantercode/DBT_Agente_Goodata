// Chat do agente. Funciona na página /agente e na gaveta lateral presente em
// todas as outras páginas. O histórico fica só no navegador.
(() => {
  const lista = document.getElementById('mensagens');
  const form = document.getElementById('form-pergunta');
  const campo = document.getElementById('campo');
  if (!lista || !form) return;
  const historico = [];

  const nomeFerramenta = {
    listar_tabelas: 'Listou as tabelas',
    descrever_tabela: 'Leu a estrutura de',
    consultar_sql: 'Consultou',
    definicao_metrica: 'Buscou a definição de',
    status_qualidade: 'Checou a qualidade dos dados',
    obter_exemplo_canonico: 'Leu o exemplo canônico de',
  };

  function adicionar(classe, html) {
    const li = document.createElement('li');
    li.className = `msg ${classe}`;
    li.innerHTML = html;
    lista.appendChild(li);
    li.scrollIntoView({behavior: 'smooth', block: 'end'});
    return li;
  }

  function escapar(t) {
    const d = document.createElement('div');
    d.textContent = t;
    return d.innerHTML;
  }

  function rastro(passos) {
    if (!passos.length) return '';
    const itens = passos.map(p => {
      const alvo = p.argumentos.tabela || p.argumentos.termo || p.argumentos.camada || p.argumentos.objetivo || '';
      const sql = p.sql ? `<pre><code>${escapar(p.sql)}</code></pre>` : '';
      return `<li class="${p.erro ? 'passo-erro' : ''}">${nomeFerramenta[p.ferramenta] || p.ferramenta} ${escapar(alvo)}
              <span class="mudo">${p.duracao_ms} ms</span>${sql}</li>`;
    }).join('');
    return `<details class="rastro"><summary>Como cheguei nessa resposta (${passos.length} passos)</summary><ol>${itens}</ol></details>`;
  }

  async function perguntar(texto) {
    adicionar('msg-usuario', escapar(texto));
    const pensando = adicionar('msg-agente msg-carregando', 'Consultando os dados');
    const botao = form.querySelector('button');
    botao.disabled = true;
    try {
      const r = await fetch('/api/agente', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({pergunta: texto, historico}),
      });
      const corpo = await r.json();
      if (!r.ok) throw new Error(corpo.erro || `Erro ${r.status}`);
      const html = DOMPurify.sanitize(marked.parse(corpo.texto));
      pensando.classList.remove('msg-carregando');
      pensando.innerHTML = html + rastro(corpo.passos) +
        `<p class="meta">${corpo.modelo} · ${corpo.tokens_entrada + corpo.tokens_saida} tokens</p>`;
      historico.push({papel: 'usuario', texto}, {papel: 'agente', texto: corpo.texto});
    } catch (e) {
      pensando.classList.remove('msg-carregando');
      pensando.classList.add('msg-erro');
      pensando.textContent = e.message;
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

  document.querySelectorAll('#sugestoes button').forEach(b =>
    b.addEventListener('click', () => perguntar(b.textContent)));

  // usado pela gaveta, pelos botões "Perguntar sobre isto" e pela paleta de comandos
  window.perguntarAgente = perguntar;
})();
