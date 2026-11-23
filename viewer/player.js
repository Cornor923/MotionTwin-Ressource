// Lecture des animations stockées en planche (clips Flash rendus, animations GraphicsGale, planches SVG des
// symboles de .fla) dans un canvas. Une planche vectorielle est dessinée plus finement que son cadre (zoom net).
MT.SheetPlayer = class {
  constructor(item, canvas, onFrame) {
    this.item = item;
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.onFrame = onFrame || (() => {});
    this.frame = 0;
    this.speed = 1;
    this.playing = false;
    this.sheet = null;
    this.raf = 0;
    this.q = item.vec ? Math.min(3, 2048 / Math.max(item.w, item.h)) : 1;
    canvas.width = Math.max(1, Math.round(item.w * this.q));
    canvas.height = Math.max(1, Math.round(item.h * this.q));
  }

  async load() {
    this.sheet = await MT.loadImage(this.item.sh);
    this.draw();
    return this;
  }

  draw() {
    if (!this.sheet) return;
    const { w, h, cols } = this.item;
    const sx = (this.frame % cols) * w;
    const sy = Math.floor(this.frame / cols) * h;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.ctx.drawImage(this.sheet, sx, sy, w, h, 0, 0, this.canvas.width, this.canvas.height);
    this.onFrame(this.frame);
  }

  seek(frame) {
    const n = this.item.f;
    this.frame = ((frame % n) + n) % n;
    this.draw();
  }

  play() {
    if (this.playing) return;
    this.playing = true;
    let last = performance.now();
    let acc = 0;
    const step = (now) => {
      if (!this.playing) return;
      acc += (now - last) * this.speed;
      last = now;
      let delay = MT.frameDelay(this.item, this.frame);
      if (acc >= delay) {
        while (acc >= delay) {
          acc -= delay;
          this.frame = (this.frame + 1) % this.item.f;
          delay = MT.frameDelay(this.item, this.frame);
        }
        this.draw();
      }
      this.raf = requestAnimationFrame(step);
    };
    this.raf = requestAnimationFrame(step);
  }

  pause() {
    this.playing = false;
    cancelAnimationFrame(this.raf);
  }

  stop() {
    this.pause();
    this.sheet = null;
  }
};
