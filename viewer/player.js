// Lecture des animations stockées en planche (clips Flash rendus, animations GraphicsGale) dans un canvas.
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
    canvas.width = item.w;
    canvas.height = item.h;
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
    this.ctx.clearRect(0, 0, w, h);
    this.ctx.drawImage(this.sheet, sx, sy, w, h, 0, 0, w, h);
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
