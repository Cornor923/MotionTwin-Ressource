// Grille des ressources : rendu par paquets au défilement, en-têtes de collection, animation au survol.
MT.Grid = class {
  constructor(root, sentinel, onOpen) {
    this.root = root;
    this.onOpen = onOpen;
    this.list = [];
    this.shown = 0;
    this.lastGroup = '';
    this.hover = null;
    new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) this.more();
    }, { rootMargin: '1200px' }).observe(sentinel);
  }

  show(list) {
    this.list = list;
    this.shown = 0;
    this.lastGroup = '';
    this.root.replaceChildren();
    this.more();
  }

  more() {
    const end = Math.min(this.list.length, this.shown + 160);
    const frag = document.createDocumentFragment();
    const grouped = MT.state.sort === 'coll';
    for (let i = this.shown; i < end; i++) {
      const item = this.list[i];
      const key = MT.collKey(item);
      if (grouped && key !== this.lastGroup) {
        this.lastGroup = key;
        const count = this.list.filter((x) => MT.collKey(x) === key).length;
        frag.append(MT.el('div', { class: 'group' },
          MT.el('h3', { text: item.c }),
          MT.el('span', { text: `${MT.gameName(item.g)} · ${count} ressource${count > 1 ? 's' : ''}` })));
      }
      frag.append(this.card(item, i));
    }
    this.shown = end;
    this.root.append(frag);
  }

  // taille d'affichage : agrandissement entier (pixels nets) pour les petites images matricielles
  fit(item) {
    if (!item.w || !item.h) return null;
    const k = MT.renderScale(item);
    const w = item.w / k, h = item.h / k;
    let z = Math.min(MT.state.thumb * 0.88 / w, MT.state.thumb * 0.88 / h);
    const raster = !item.vec && k === 1;
    if (raster) z = z >= 2 ? Math.min(Math.floor(z), 8) : Math.min(z, 1);
    else z = Math.min(z, 6);
    return { w: Math.max(1, Math.round(w * z)), h: Math.max(1, Math.round(h * z)), up: raster && z >= 2 };
  }

  card(item, index) {
    const fit = this.fit(item);
    const up = fit && fit.up;
    const thumb = MT.el('div', { class: 'thumb' });
    if (item.t === 'snd' || item.t === 'lch') {
      thumb.append(MT.el('span', { class: item.t, text: item.t === 'snd' ? '♪' : '≋' }));
    } else {
      const img = MT.el('img', { src: item.s, alt: '', loading: 'lazy', decoding: 'async', class: up ? 'up' : null });
      if (fit) Object.assign(img.style, { width: `${fit.w}px`, height: `${fit.h}px` });
      thumb.append(img);
      thumb.fit = fit;
    }
    const sub = [MT.dims(item)];
    if (item.f > 1) sub.push(`${item.f} img`);
    if (item.t === 'mdl') sub.push(`${item.x.tris.toLocaleString('fr-FR')} triangles`);
    else if (item.t === 'snd' || !item.w) sub.push(MT.bytes(item.z));
    const card = MT.el('button', { class: 'card', title: item.p, onclick: () => this.onOpen(index) },
      thumb,
      MT.el('span', { class: `badge t-${item.t}`, text: MT.TYPES[item.t].label.split(' ')[0] }),
      MT.el('span', { class: 'meta' },
        MT.el('span', { class: 'name', text: item.n }),
        MT.el('span', { class: 'sub', text: sub.filter(Boolean).join(' · ') })));
    if (item.sh) {
      card.addEventListener('mouseenter', () => this.animate(item, thumb, up));
      card.addEventListener('mouseleave', () => this.stopHover());
    }
    return card;
  }

  animate(item, thumb, up) {
    this.stopHover();
    const canvas = MT.el('canvas', { class: up ? 'up' : null });
    Object.assign(canvas.style, { position: 'absolute', inset: '0', margin: 'auto' });
    if (thumb.fit) Object.assign(canvas.style, { width: `${thumb.fit.w}px`, height: `${thumb.fit.h}px` });
    const player = new MT.SheetPlayer(item, canvas);
    this.hover = { player, canvas, thumb };
    player.load().then(() => {
      if (this.hover?.player !== player) return;
      thumb.querySelector('img').style.visibility = 'hidden';
      thumb.append(canvas);
      player.play();
    }).catch(() => {});
  }

  stopHover() {
    if (!this.hover) return;
    const { player, canvas, thumb } = this.hover;
    player.stop();
    canvas.remove();
    const img = thumb.querySelector('img');
    if (img) img.style.visibility = '';
    this.hover = null;
  }
};
