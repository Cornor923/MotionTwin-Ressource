// État des filtres, facettes avec compteurs, tri, et synchronisation avec l'adresse (#…).
MT.state = { q: '', game: '', sub: '', types: new Set(), coll: '', sort: 'coll', anim: false, bg: 'checker', thumb: 136 };

MT.prepare = () => {
  const order = Object.fromEntries(MT.catalog.games.map((g, i) => [g.id, i]));
  const partOrder = Object.fromEntries(MT.catalog.games.flatMap((g) => (g.parts || []).map((p, i) => [`${g.id}|${p.id}`, i])));
  MT.items = MT.catalog.items;
  MT.items.forEach((item, index) => {
    item._i = index;
    item._g = order[item.g];
    item._sg = item.sg ? partOrder[`${item.g}|${item.sg}`] : -1;
    item._q = MT.fold([item.n, item.p, item.c, (item.k || []).join(' '), (item.dup || []).join(' ')].join(' '));
    item._area = (item.w || 0) * (item.h || 0) / MT.renderScale(item) ** 2;
    item._snd = item.t === 'snd' ? 1 : 0;  // tri par taille : les sons après les images, rangés par durée
    item._dur = item.dur || 0;
    item._anim = (item.f || 1) > 1;
  });
};

const collKey = (item) => `${item.g}|${item.c}`;
// jeux d'une plateforme où figure la ressource ('-' : hors de tout jeu) ; `sgx` : ses copies dans d'autres jeux
const subKeys = (item) => [item.sg || '-', ...(item.sgx || [])].map((k) => `${item.g}|${k}`);

MT.matches = (item, skip) => {
  const s = MT.state;
  if (skip !== 'game' && s.game && item.g !== s.game) return false;
  if (skip !== 'game' && s.sub && !subKeys(item).includes(`${s.game}|${s.sub}`)) return false;
  if (skip !== 'type' && s.types.size && !s.types.has(item.t)) return false;
  if (skip !== 'coll' && s.coll && collKey(item) !== s.coll) return false;
  if (s.anim && !item._anim) return false;
  if (s.q) {
    for (const word of MT.fold(s.q).split(/\s+/)) {
      if (word && !item._q.includes(word)) return false;
    }
  }
  return true;
};

MT.facets = () => {
  const games = {}, subs = {}, types = {}, colls = {};
  for (const item of MT.items) {
    if (MT.matches(item, 'game')) {
      games[item.g] = (games[item.g] || 0) + 1;
      for (const key of subKeys(item)) subs[key] = (subs[key] || 0) + 1;
    }
    if (MT.matches(item, 'type')) types[item.t] = (types[item.t] || 0) + 1;
    if (MT.matches(item, 'coll')) colls[collKey(item)] = (colls[collKey(item)] || 0) + 1;
  }
  return { games, subs, types, colls };
};

const byName = (a, b) => a.n.localeCompare(b.n, 'fr', { numeric: true, sensitivity: 'base' });
const byPath = (a, b) => a.p.localeCompare(b.p, 'fr', { numeric: true });

MT.SORTS = {
  coll: (a, b) => a._g - b._g || a._sg - b._sg || a.c.localeCompare(b.c, 'fr') || byPath(a, b),
  name: (a, b) => byName(a, b) || byPath(a, b),
  'name-desc': (a, b) => byName(b, a) || byPath(a, b),
  'area-desc': (a, b) => a._snd - b._snd || b._area - a._area || b._dur - a._dur || byName(a, b),
  'area-asc': (a, b) => a._snd - b._snd || a._area - b._area || a._dur - b._dur || byName(a, b),
  'frames-desc': (a, b) => (b.f || 1) - (a.f || 1) || byName(a, b),
  'weight-desc': (a, b) => (b.z || 0) - (a.z || 0) || byName(a, b),
};

MT.results = () => MT.items.filter((item) => MT.matches(item)).sort(MT.SORTS[MT.state.sort] || MT.SORTS.coll);

MT.collKey = collKey;

MT.writeHash = (itemId) => {
  const s = MT.state;
  const params = new URLSearchParams();
  if (s.q) params.set('q', s.q);
  if (s.game) params.set('jeu', s.game);
  if (s.game && s.sub) params.set('sous', s.sub);
  if (s.types.size) params.set('type', [...s.types].join(','));
  if (s.coll) params.set('coll', s.coll);
  if (s.sort !== 'coll') params.set('tri', s.sort);
  if (s.anim) params.set('animes', '1');
  if (itemId) params.set('res', itemId);
  const hash = params.toString();
  history.replaceState(null, '', hash ? `#${hash}` : location.pathname + location.search);
};

MT.readHash = () => {
  const params = new URLSearchParams(location.hash.slice(1));
  const s = MT.state;
  s.q = params.get('q') || '';
  s.game = params.get('jeu') || '';
  s.sub = (s.game && params.get('sous')) || '';
  s.types = new Set((params.get('type') || '').split(',').filter((t) => MT.TYPES[t]));
  s.coll = params.get('coll') || '';
  s.sort = MT.SORTS[params.get('tri')] ? params.get('tri') : 'coll';
  s.anim = params.get('animes') === '1';
  return params.get('res');
};
