// Panneau d'informations de la fenêtre de détail.
MT.detailInfo = (item, $) => {
  const el = MT.el;
  const game = MT.catalog.games.find((g) => g.id === item.g);
  $('d-name').textContent = item.n;
  $('d-badges').replaceChildren(
    el('span', { class: `badge t-${item.t}`, text: MT.TYPES[item.t].label }),
    el('span', { class: 'badge plain', text: `${game.name} (${game.year})` }));

  const rows = [['Collection', item.c]];
  if (item.w) {
    const k = MT.renderScale(item);
    rows.push(['Dimensions', k > 1
      ? `${MT.dims(item)} px Flash (rendu ×${k} : ${item.w}×${item.h})`
      : `${MT.dims(item)} px${item.vec ? ' (vectoriel)' : ''}`]);
  }
  if (item.f > 1) {
    let anim = `${item.f}`;
    if (item.d) anim += ` · ${item.d.reduce((a, b) => a + b, 0)} ms au total`;
    if (item.fps) anim += ` · ${Math.round(item.fps * 100) / 100} img/s`;
    rows.push(['Images', anim]);
  }
  if (item.fmt) rows.push(['Format', item.fmt]);
  if (item.z && !item.x) rows.push(['Poids', MT.bytes(item.z)]);
  const x = item.x || {};
  if (x.swf) {
    rows.push(['SWF', x.swf]);
    rows.push(['Caractère', `#${x.id}` + (item.t === 'clip' ? ` · timeline de ${x.timeline} image${x.timeline > 1 ? 's' : ''}` : '')]);
  }
  if (x.labels && x.labels.length) rows.push(['Étiquettes', x.labels.join(', ')]);
  if (x.owners && x.owners.length) {
    rows.push(['Utilisée par', el('span', {}, x.owners.map((name, i) => [i ? ', ' : '',
      el('a', { href: '#', text: name, onclick: (e) => { e.preventDefault(); MT.searchFor(name); } })]))]);
  }
  if (x.same && x.same.length) rows.push(['Formes identiques', x.same.map((id) => `#${id}`).join(', ')]);
  rows.push(['Archive', el('a', { href: item.u, target: '_blank', rel: 'noopener', text: x.swf ? x.swf : item.p })]);
  $('d-meta').replaceChildren(...rows.flatMap(([k, v]) => [el('dt', { text: k }), el('dd', {}, v)]));

  const ext = item.s.slice(item.s.lastIndexOf('.'));
  const actions = [
    el('a', { class: 'primary', href: item.s, download: MT.fileName(item, ext),
      text: item.t === 'svg' ? 'Télécharger le SVG' : item.f > 1 && item.sh ? 'Télécharger (PNG, 1re image)' : 'Télécharger' }),
  ];
  if (item.o) {
    const oext = item.o.slice(item.o.lastIndexOf('.'));
    actions.push(el('a', { href: item.o, download: MT.fileName(item, oext), text: `Fichier source (${oext})` }));
  }
  if (item.sh) {
    actions.push(el('a', { href: item.sh, download: MT.fileName(item, '_planche.png'), text: 'Planche d\'animation' }));
    actions.push(el('button', { text: 'Image courante (PNG)', onclick: () => MT.saveFrame(item) }));
  }
  actions.push(el('a', { href: item.s, target: '_blank', rel: 'noopener', text: 'Ouvrir' }));
  actions.push(el('button', { text: 'Copier l\'attribution', onclick: () => MT.copy(MT.attribution(item), 'Attribution copiée') }));
  actions.push(el('button', { text: 'Copier le chemin', onclick: () => MT.copy(item.p, 'Chemin copié') }));
  $('d-actions').replaceChildren(...actions);

  const dups = item.dup || [];
  $('d-dups').replaceChildren(...(dups.length ? [
    el('h3', { text: `Aussi dans l'archive (${dups.length})` }),
    el('ul', {}, dups.map((p) => el('li', { text: p }))),
  ] : []));
};

MT.saveFrame = (item) => {
  const canvas = document.querySelector('#stage canvas');
  try {
    canvas.toBlob((blob) => {
      const a = MT.el('a', { href: URL.createObjectURL(blob), download: MT.fileName(item, `_${+document.getElementById('a-frame').value + 1}.png`) });
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    });
  } catch {
    MT.toast('Indisponible en file:// : ouvrir la page via un serveur local');
  }
};
