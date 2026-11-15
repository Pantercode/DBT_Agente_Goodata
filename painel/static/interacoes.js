// Interações do painel: gaveta do agente, paleta de comandos, mapa clicável,
// atalhos de teclado, luz que segue o cursor e contagem dos números de capa.
(() => {
  const semMovimento = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const recorte = document.body.dataset.recorte || 'Brasil';

  /* ---------------------------------------------------------- gaveta */
  const gaveta = document.getElementById('gaveta');
  const abrirGaveta = () => {
    if (!gaveta) return;
    gaveta.hidden = false;
    requestAnimationFrame(() => gaveta.classList.add('aberta'));
    document.getElementById('campo')?.focus();
  };
  const fecharGaveta = () => {
    if (!gaveta) return;
    gaveta.classList.remove('aberta');
    setTimeout(() => { gaveta.hidden = true; }, semMovimento ? 0 : 220);
  };
  document.querySelectorAll('[data-abrir-gaveta]').forEach(el =>
    el.addEventListener('click', ev => { if (gaveta) { ev.preventDefault(); abrirGaveta(); } }));
  gaveta?.querySelector('[data-fechar]')?.addEventListener('click', fecharGaveta);

  // "Perguntar sobre isto": o agente recebe o gráfico e o recorte como contexto
  document.querySelectorAll('[data-perguntar]').forEach(b => b.addEventListener('click', () => {
    if (!window.perguntarAgente) { location.href = '/agente'; return; }
    abrirGaveta();
    window.perguntarAgente(b.dataset.perguntar);
  }));

  /* ------------------------------------------------ paleta de comandos */
  const paleta = document.getElementById('paleta');
  const entrada = document.getElementById('paleta-busca');
  const listaPaleta = document.getElementById('paleta-itens');
  const itens = JSON.parse(document.getElementById('itens-paleta')?.textContent || '[]');
  let selecionado = 0;

  function normalizar(t) { return t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }

  function renderizarPaleta() {
    const termo = normalizar(entrada.value.trim());
    const achados = itens.filter(i => !termo || normalizar(i.rotulo + ' ' + (i.busca || '')).includes(termo)).slice(0, 8);
    if (entrada.value.trim()) {
      achados.push({tipo: 'Perguntar', rotulo: `Perguntar ao agente: "${entrada.value.trim()}"`, pergunta: entrada.value.trim()});
    }
    selecionado = Math.min(selecionado, achados.length - 1);
    listaPaleta.innerHTML = achados.map((i, n) =>
      `<li role="option" aria-selected="${n === selecionado}" data-n="${n}">
         <span class="paleta-tipo">${i.tipo}</span><span>${i.rotulo.replace(/</g, '&lt;')}</span></li>`).join('');
    listaPaleta._achados = achados;
  }

  function executar(i) {
    if (!i) return;
    if (i.pergunta) {
      paleta.close();
      if (window.perguntarAgente && gaveta) { abrirGaveta(); window.perguntarAgente(i.pergunta); }
      else location.href = '/agente';
    } else {
      location.href = i.href;
    }
  }

  function abrirPaleta() {
    if (!paleta) return;
    entrada.value = '';
    selecionado = 0;
    renderizarPaleta();
    paleta.showModal();
    entrada.focus();
  }

  entrada?.addEventListener('input', () => { selecionado = 0; renderizarPaleta(); });
  entrada?.addEventListener('keydown', ev => {
    const n = listaPaleta._achados?.length || 0;
    if (ev.key === 'ArrowDown') { selecionado = (selecionado + 1) % n; renderizarPaleta(); ev.preventDefault(); }
    if (ev.key === 'ArrowUp') { selecionado = (selecionado - 1 + n) % n; renderizarPaleta(); ev.preventDefault(); }
    if (ev.key === 'Enter') { executar(listaPaleta._achados[selecionado]); ev.preventDefault(); }
  });
  listaPaleta?.addEventListener('click', ev => {
    const li = ev.target.closest('li');
    if (li) executar(listaPaleta._achados[+li.dataset.n]);
  });
  paleta?.addEventListener('click', ev => { if (ev.target === paleta) paleta.close(); });
  document.querySelectorAll('[data-abrir-paleta]').forEach(b => b.addEventListener('click', abrirPaleta));

  /* ------------------------------------------------------- teclado */
  document.addEventListener('keydown', ev => {
    const digitando = ev.target.closest('input, textarea, select');
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k') { ev.preventDefault(); abrirPaleta(); return; }
    if (ev.key === 'Escape' && gaveta && !gaveta.hidden) { fecharGaveta(); return; }
    if (digitando || paleta?.open) return;
    if (ev.key === 'ArrowLeft') document.querySelector('[data-recorte-anterior]')?.click();
    if (ev.key === 'ArrowRight') document.querySelector('[data-recorte-proximo]')?.click();
  });

  /* ------------------------------------------------- mapa clicável */
  document.addEventListener('plotly-pronto', ev => {
    const el = ev.detail;
    if (el.dataset.clicavel !== 'uf') return;
    el.on('plotly_click', d => {
      const uf = d.points?.[0]?.location;
      if (uf) location.href = `${location.pathname}?uf=${uf}`;
    });
    el.style.cursor = 'pointer';
  });

  /* ---------------------------------------- luz que segue o cursor */
  document.querySelectorAll('.destaque-luz').forEach(card => {
    if (semMovimento) return;
    card.addEventListener('pointermove', ev => {
      const r = card.getBoundingClientRect();
      card.style.setProperty('--luz-x', `${((ev.clientX - r.left) / r.width) * 100}%`);
      card.style.setProperty('--luz-y', `${((ev.clientY - r.top) / r.height) * 100}%`);
    });
    card.addEventListener('pointerleave', () => {
      card.style.removeProperty('--luz-x');
      card.style.removeProperty('--luz-y');
    });
  });

  /* ------------------------------------ contagem dos números de capa */
  const fmt = (v, casas) => v.toLocaleString('pt-BR', {minimumFractionDigits: casas, maximumFractionDigits: casas});
  document.querySelectorAll('[data-contar]').forEach(el => {
    const alvo = parseFloat(el.dataset.contar);
    const casas = +(el.dataset.casas || 0);
    const sufixo = el.dataset.sufixo || '';
    if (semMovimento || !isFinite(alvo)) return;
    const inicio = performance.now();
    const dur = 900;
    const passo = t => {
      const p = Math.min(1, (t - inicio) / dur);
      const e = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(alvo * e, casas) + sufixo;
      if (p < 1) requestAnimationFrame(passo);
    };
    requestAnimationFrame(passo);
  });


  /* ------------------------------------------- barras que crescem até o valor */
  // Desenha a figura com as barras zeradas e anima até os valores reais, uma vez.
  window.animarBarras = (el, fig) => {
    if (semMovimento || !fig?.data?.some(t => t.type === 'bar') || !el._fullLayout) return;
    // A figura já foi desenhada com os valores reais: guarda a escala final dos eixos
    // e anima a partir do zero dentro dela (sem isso o eixo fica na escala do zero).
    const fixo = eixo => {
      const a = el._fullLayout[eixo];
      return a && a.type !== 'category' ? {...(el.layout[eixo] || {}), range: a.range.slice(), autorange: false} : el.layout[eixo];
    };
    const layout = {...el.layout, xaxis: fixo('xaxis'), yaxis: fixo('yaxis')};
    const zerado = fig.data.map(t => {
      if (t.type !== 'bar') return t;
      const h = t.orientation === 'h';
      const vals = (h ? t.x : t.y) || [];
      return {...t, [h ? 'x' : 'y']: vals.map(() => 0)};
    });
    Plotly.react(el, zerado, layout).then(() =>
      Plotly.animate(el, {data: fig.data}, {transition: {duration: 750, easing: 'cubic-out'}, frame: {duration: 750, redraw: false}}));
  };
  document.addEventListener('plotly-pronto', ev => {
    const el = ev.detail;
    if (el.dataset.fig) window.animarBarras(el, JSON.parse(el.dataset.fig));
  });

  /* --------------------------------------------- inclinação 3D nos destaques */
  document.querySelectorAll('.destaque').forEach(card => {
    if (semMovimento) return;
    card.addEventListener('pointermove', ev => {
      const r = card.getBoundingClientRect();
      const px = (ev.clientX - r.left) / r.width - 0.5;
      const py = (ev.clientY - r.top) / r.height - 0.5;
      card.style.transform = `perspective(900px) rotateX(${(-py * 5).toFixed(2)}deg) rotateY(${(px * 6).toFixed(2)}deg) translateY(-2px)`;
    });
    card.addEventListener('pointerleave', () => { card.style.transform = ''; });
  });

  /* ------------------------------------ borda que acende perto do cursor */
  let quadro = 0;
  document.addEventListener('pointermove', ev => {
    if (semMovimento || quadro) return;
    quadro = requestAnimationFrame(() => {
      quadro = 0;
      document.querySelectorAll('.cartao, .painel-bloco, .destaque').forEach(el => {
        const r = el.getBoundingClientRect();
        el.style.setProperty('--brilho-x', `${ev.clientX - r.left}px`);
        el.style.setProperty('--brilho-y', `${ev.clientY - r.top}px`);
      });
    });
  }, {passive: true});

  /* -------------------------------------------- entrada orquestrada da página */
  if (!semMovimento) {
    document.querySelectorAll('main > *, .destaques > *, .grade > *, .evento').forEach((el, i) => {
      el.classList.add('anima-entrada');
      el.style.setProperty('--i', Math.min(i, 12));
    });
    requestAnimationFrame(() => requestAnimationFrame(() => document.body.classList.add('entrou')));
    // terminada a entrada, a inclinação do destaque responde sem atraso
    setTimeout(() => document.querySelectorAll('.destaque').forEach(d => d.classList.add('ja-entrou')), 1400);
  }
  document.querySelectorAll('.destaque-ambar').forEach(d => {
    const faixa = document.createElement('span');
    faixa.className = 'faixa-luz';
    d.prepend(faixa);
  });

  document.body.dataset.js = 'ok';
  void recorte;
})();
