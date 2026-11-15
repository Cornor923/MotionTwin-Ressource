// Fenêtre de détail : grande vue zoomable, lecture des animations, métadonnées, téléchargements.
MT.Detail = class {
  constructor(onMove) {
    this.dlg = document.getElementById('detail');
    this.stage = document.getElementById('stage');
    this.onMove = onMove;
    this.zoom = 'fit';
    this.player = null;
    this.$ = (id) => document.getElementById(id);
    this.$('d-close').onclick = () => this.dlg.close();
    this.$('d-prev').onclick = () => this.onMove(-1);
    this.$('d-next').onclick = () => this.onMove(1);
    this.dlg.addEventListener('close', () => this.unload());
    this.dlg.addEventListener('click', (e) => { if (e.target === this.dlg) this.dlg.close(); });
    this.bindSeg('zoom', 'z', (z) => { this.zoom = z; this.layout(); });
    this.bindSeg('dbg', 'bg', (bg) => { this.stage.dataset.bg = bg; });
    this.$('pixelated').onchange = () => this.layout();
    this.$('a-play').onclick = () => this.toggle();
    this.$('a-prev').onclick = () => this.step(-1);
    this.$('a-next').onclick = () => this.step(1);
    this.$('a-frame').oninput = (e) => { this.player.pause(); this.syncPlay(); this.player.seek(+e.target.value); };
    this.$('a-speed').onchange = (e) => { if (this.player) this.player.speed = +e.target.value; };
    this.stage.addEventListener('wheel', (e) => this.wheel(e), { passive: false });
    document.addEventListener('keydown', (e) => this.key(e));
    window.addEventListener('resize', () => this.dlg.open && this.layout());
  }

  bindSeg(id, attr, fn) {
    const seg = this.$(id);
    seg.addEventListener('click', (e) => {
      const btn = e.target.closest('button');
      if (!btn) return;
      seg.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', b === btn));
      fn(btn.dataset[attr]);
    });
  }

  press(id, value, attr) {
    this.$(id).querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', b.dataset[attr] === value));
  }

  open(item) {
    this.unload();
    this.item = item;
    this.stage.dataset.bg = MT.state.bg;
    this.press('dbg', MT.state.bg, 'bg');
    this.zoom = 'fit';
    this.press('zoom', 'fit', 'z');
    this.$('anim-bar').hidden = !item.sh;
    let view;
    if (item.t === 'snd') {
      view = MT.el('audio', { controls: true, src: item.s, preload: 'metadata' });
    } else if (item.sh) {
      view = MT.el('canvas', { class: 'view' });
      this.player = new MT.SheetPlayer(item, view, (f) => this.frameChanged(f));
      this.$('a-frame').max = item.f - 1;
      this.player.speed = +this.$('a-speed').value;
      this.player.load().then(() => { this.player.play(); this.syncPlay(); });
    } else {
      view = MT.el('img', { class: 'view', src: item.s, alt: item.n });
    }
    this.view = view;
    this.stage.replaceChildren(view);
    this.info(item);
    if (!this.dlg.open) this.dlg.showModal();
    this.layout();
  }

  unload() {
    if (this.player) this.player.stop();
    this.player = null;
  }

  layout() {
    const item = this.item;
    if (!item || !item.w || item.t === 'snd') return;
    const k = MT.renderScale(item);
    const w = item.w / k, h = item.h / k;
    let z = +this.zoom;
    if (this.zoom === 'fit') {
      const box = this.stage.getBoundingClientRect();
      z = Math.min((box.width - 32) / w, (box.height - 32) / h);
      const raster = !item.vec && k === 1;
      if (raster) z = z >= 1 ? Math.max(1, Math.floor(z)) : z;
      z = Math.min(z, item.vec ? 16 : raster ? 8 : 2 * k);
    }
    this.view.style.width = `${w * z}px`;
    this.view.style.height = `${h * z}px`;
    this.view.classList.toggle('px', this.$('pixelated').checked && !item.vec && k === 1 && z > 1);
    this.z = z;
  }

  wheel(e) {
    if (!e.ctrlKey && !e.altKey) return;
    e.preventDefault();
    const next = (this.z || 1) * (e.deltaY < 0 ? 1.25 : 0.8);
    this.zoom = String(Math.max(0.1, Math.min(32, next)));
    this.press('zoom', '', 'z');
    this.layout();
  }

  toggle() {
    if (!this.player) return;
    if (this.player.playing) this.player.pause(); else this.player.play();
    this.syncPlay();
  }

  step(delta) {
    if (!this.player) return;
    this.player.pause();
    this.syncPlay();
    this.player.seek(this.player.frame + delta);
  }

  syncPlay() {
    this.$('a-play').textContent = this.player && this.player.playing ? '⏸' : '▶';
  }

  frameChanged(frame) {
    this.$('a-frame').value = frame;
    this.$('a-label').textContent = `${frame + 1} / ${this.item.f}`;
  }

  key(e) {
    if (!this.dlg.open || ['INPUT', 'SELECT'].includes(e.target.tagName)) return;
    if (e.key === 'ArrowLeft') this.onMove(-1);
    else if (e.key === 'ArrowRight') this.onMove(1);
    else if (e.key === ' ') { e.preventDefault(); this.toggle(); }
    else if (e.key === ',') this.step(-1);
    else if (e.key === '.') this.step(1);
  }

  info(item) {
    MT.detailInfo(item, this.$);
  }
};
