// Assemblage : barre latérale (jeux, types, collections), barre d'outils, grille et détail.
(() => {
  const $ = (id) => document.getElementById(id);
  const el = MT.el;
  const s = MT.state;
  MT.catalog = window.MT_CATALOG;
  MT.prepare();
  let results = [];
  let current = -1;

  const grid = new MT.Grid($('grid'), $('sentinel'), (index) => openAt(index));
  const detail = new MT.Detail((delta) => {
    if (!results.length) return;
    openAt((current + delta + results.length) % results.length);
  });

  function openAt(index) {
    current = index;
    detail.open(results[index]);
    MT.writeHash(results[index].i);
  }
  $('detail').addEventListener('close', () => MT.writeHash());

  function row(label, count, pressed, onclick, cls) {
    return el('button', { class: cls || null, 'aria-pressed': String(pressed), onclick },
      label, el('span', { class: 'n', text: count }));
  }

  function gameRows(g, f) {  // une plateforme (CaféJeux…) déplie ses sous-jeux quand elle est choisie
    const open = s.game === g.id;
    const rows = [row(g.name, f.games[g.id] || 0, open && !s.sub,
      () => update({ game: open && !s.sub ? '' : g.id, sub: '', coll: '' }),
      g.parts ? `group${open ? ' open' : ''}` : null)];
    if (!g.parts || !open) return rows;
    const subs = (g.root ? [{ id: '-', name: g.root.name }] : []).concat(g.parts);
    for (const p of subs) {
      rows.push(row(p.name, f.subs[`${g.id}|${p.id}`] || 0, s.sub === p.id,
        () => update({ game: g.id, sub: s.sub === p.id ? '' : p.id, coll: '' }), 'sub'));
    }
    return rows;
  }

  const usedTypes = new Set(MT.items.map((item) => item.t));  // liste fixe : la colonne ne saute pas au filtrage

  function renderSide(f) {
    const total = Object.values(f.games).reduce((a, b) => a + b, 0);
    $('f-games').replaceChildren(
      row('Tous', total, !s.game, () => update({ game: '', sub: '', coll: '' })),
      ...MT.catalog.games.flatMap((g) => gameRows(g, f)));
    const game = MT.catalog.games.find((g) => g.id === s.game);
    $('f-game-info').replaceChildren(...(game ? [
      el('p', { text: `${game.summary} (${game.year})` }),
      el('ul', {}, game.notes.map((note) => el('li', { text: note }))),
    ] : []));

    $('f-types').replaceChildren(...Object.entries(MT.TYPES).filter(([t]) => usedTypes.has(t)).map(([t, def]) =>
      el('label', { class: f.types[t] || s.types.has(t) ? null : 'zero' },
        el('input', { type: 'checkbox', checked: s.types.has(t), onchange: (e) => {
          const types = new Set(s.types);
          if (e.target.checked) types.add(t); else types.delete(t);
          update({ types });
        } }),
        el('span', { class: `dot t-${t}`, style: 'background: var(--tc)' }),
        def.plural,
        el('span', { class: 'n', text: f.types[t] || 0 }))));

    const blocks = [];
    for (const g of MT.catalog.games) {
      if (s.game && s.game !== g.id) continue;
      const colls = Object.entries(f.colls).filter(([key]) => key.startsWith(`${g.id}|`))
        .sort(([a], [b]) => a.localeCompare(b, 'fr'));
      if (!colls.length) continue;
      blocks.push(el('h3', { text: g.name }));
      for (const [key, n] of colls) {
        blocks.push(el('button', { 'aria-pressed': String(s.coll === key), title: key.split('|')[1],
          onclick: () => update({ coll: s.coll === key ? '' : key }) },
          key.split('|')[1], el('span', { class: 'n', text: n })));
      }
    }
    $('f-colls').replaceChildren(...blocks);
  }

  function update(changes) {
    Object.assign(s, changes || {});
    results = MT.results();
    renderSide(MT.facets());
    $('count').textContent = `${results.length.toLocaleString('fr-FR')} ressource${results.length > 1 ? 's' : ''}`;
    $('empty').hidden = results.length > 0;
    grid.show(results);
    MT.writeHash();
  }

  MT.searchFor = (text) => {
    $('detail').close();
    $('q').value = text;
    update({ q: text, types: new Set(), coll: '' });
  };

  let typing;
  $('q').addEventListener('input', (e) => {
    clearTimeout(typing);
    typing = setTimeout(() => update({ q: e.target.value.trim() }), 120);
  });
  $('sort').addEventListener('change', (e) => update({ sort: e.target.value }));
  $('anim-only').addEventListener('change', (e) => update({ anim: e.target.checked }));
  $('thumb').addEventListener('input', (e) => {
    s.thumb = +e.target.value;
    document.documentElement.style.setProperty('--thumb', `${s.thumb}px`);
  });
  $('thumb').addEventListener('change', () => grid.show(results));
  $('bg').addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    s.bg = btn.dataset.bg;
    document.body.dataset.bg = s.bg;
    $('bg').querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', b === btn));
    try { localStorage.setItem('mt-bg', s.bg); } catch { /* stockage indisponible */ }
  });
  const top = document.querySelector('.top');
  new ResizeObserver(() => document.documentElement.style.setProperty('--top-h', `${top.offsetHeight}px`)).observe(top);
  const side = (open) => document.body.classList.toggle('side-open', open);
  $('toggle-side').addEventListener('click', () => side(true));
  $('close-side').addEventListener('click', () => side(false));
  $('scrim').addEventListener('click', () => side(false));

  const c = MT.catalog;
  $('source-line').replaceChildren('Archive officielle ',
    el('a', { href: c.repo, target: '_blank', rel: 'noopener', text: 'motion-twin/WebGamesArchives' }),
    ` · ${c.items.length.toLocaleString('fr-FR')} ressources · ${c.games.map((g) => g.name).join(', ')}`);
  $('licence').replaceChildren(
    el('strong', { text: 'Licence' }), el('br'),
    'Ressources © Motion Twin, publiées sous ',
    el('a', { href: c.license.url, target: '_blank', rel: 'noopener', text: c.license.name }),
    ' : attribution, pas d\'usage commercial, partage dans les mêmes conditions.',
    el('br'), el('br'),
    `Généré le ${c.generated}` + (c.commit ? ` depuis le commit ${c.commit.slice(0, 7)}.` : '.'));

  try { s.bg = localStorage.getItem('mt-bg') || s.bg; } catch { /* stockage indisponible */ }
  document.body.dataset.bg = s.bg;
  $('bg').querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', b.dataset.bg === s.bg));

  function fromHash() {
    const wanted = MT.readHash();
    $('q').value = s.q;
    $('sort').value = s.sort;
    $('anim-only').checked = s.anim;
    update();
    const index = wanted ? results.findIndex((item) => item.i === wanted) : -1;
    if (index >= 0) openAt(index);
    else if ($('detail').open) $('detail').close();
  }
  window.addEventListener('hashchange', fromHash);
  fromHash();
})();
