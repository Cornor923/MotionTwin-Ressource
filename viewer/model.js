// Vue 3D d'un modèle (WebGL, sans bibliothèque) : glisser pour tourner, molette pour zoomer, double-clic pour recadrer.
MT.loadMesh = (item) => new Promise((resolve, reject) => {
  const have = () => window.MT_MESH && window.MT_MESH[item.i];
  if (have()) return resolve(have());
  const script = MT.el('script', { src: item.x.mesh });
  script.onload = () => (have() ? resolve(have()) : reject(new Error('maillage absent')));
  script.onerror = reject;
  document.head.append(script);
});

const VERT = `attribute vec3 p; attribute vec3 n; attribute vec2 t; attribute float s;
uniform mat4 mvp; uniform mat4 mv; varying vec3 vn; varying vec2 vt; varying float vs;
void main() { gl_Position = mvp * vec4(p, 1.0); vn = (mv * vec4(n, 0.0)).xyz; vt = t; vs = s; }`;
const FRAG = `precision mediump float; uniform int mode; uniform sampler2D tex;
varying vec3 vn; varying vec2 vt; varying float vs;
void main() {
  if (mode == 1) { vec4 c = texture2D(tex, vt); if (c.a < 0.5) discard; gl_FragColor = vec4(c.rgb * vs, 1.0); return; }
  float d = mode == 2 ? vs : 0.38 + 0.62 * abs(dot(normalize(vn), normalize(vec3(-0.45, 0.55, 0.7))));
  gl_FragColor = vec4(vec3(0.74, 0.75, 0.79) * d, 1.0);
}`;

const M4 = {
  mul: (a, b) => {
    const o = new Float32Array(16);
    for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) {
      o[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1] + a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3];
    }
    return o;
  },
  persp: (fov, aspect, near, far) => {
    const f = 1 / Math.tan(fov / 2), d = near - far;
    return new Float32Array([f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) / d, -1, 0, 0, 2 * far * near / d, 0]);
  },
  rotX: (a) => new Float32Array([1, 0, 0, 0, 0, Math.cos(a), Math.sin(a), 0, 0, -Math.sin(a), Math.cos(a), 0, 0, 0, 0, 1]),
  rotY: (a) => new Float32Array([Math.cos(a), 0, -Math.sin(a), 0, 0, 1, 0, 0, Math.sin(a), 0, Math.cos(a), 0, 0, 0, 0, 1]),
  move: (x, y, z) => new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]),
};

MT.ModelViewer = class {
  constructor(item, canvas, onError) {
    this.item = item;
    this.canvas = canvas;
    this.onError = onError;
    this.reset();
    canvas.addEventListener('pointerdown', (e) => { this.drag = [e.clientX, e.clientY]; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener('pointerup', () => { this.drag = null; });
    canvas.addEventListener('pointermove', (e) => {
      if (!this.drag) return;
      this.az += (e.clientX - this.drag[0]) * 0.01;
      this.el = Math.max(-1.5, Math.min(1.5, this.el + (e.clientY - this.drag[1]) * 0.01));
      this.drag = [e.clientX, e.clientY];
      this.draw();
    });
    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      this.zoom = Math.max(0.2, Math.min(8, this.zoom * (e.deltaY < 0 ? 1.15 : 0.87)));
      this.draw();
    }, { passive: false });
    canvas.addEventListener('dblclick', () => { this.reset(); this.draw(); });
    this.resize = new ResizeObserver(() => this.draw());
    this.resize.observe(canvas);
  }

  reset() {
    this.az = -0.6;
    this.el = 0.35;
    this.zoom = 1;
  }

  async load() {
    const mesh = await MT.loadMesh(this.item);
    const gl = this.gl = this.canvas.getContext('webgl', { antialias: true, premultipliedAlpha: false });
    if (!gl) throw new Error('WebGL indisponible');
    const prog = gl.createProgram();
    for (const [type, src] of [[gl.VERTEX_SHADER, VERT], [gl.FRAGMENT_SHADER, FRAG]]) {
      const sh = gl.createShader(type);
      gl.shaderSource(sh, src);
      gl.compileShader(sh);
      gl.attachShader(prog, sh);
    }
    gl.linkProgram(prog);
    gl.useProgram(prog);
    this.prog = prog;
    this.parts = mesh.objects.map((o) => this.upload(o));
    this.up = mesh.up;
    const all = mesh.objects.flatMap((o) => o.pos);
    const lo = [0, 1, 2].map((k) => Math.min(...all.filter((_, i) => i % 3 === k)));
    const hi = [0, 1, 2].map((k) => Math.max(...all.filter((_, i) => i % 3 === k)));
    this.center = lo.map((v, k) => (v + hi[k]) / 2);
    this.radius = Math.hypot(...hi.map((v, k) => v - lo[k])) / 2 || 1;
    this.mode = 0;
    if (mesh.texture) this.mode = await this.texture(mesh.texture) ? 1 : 2;
    gl.enable(gl.DEPTH_TEST);
    this.draw();
  }

  upload(o) {
    const gl = this.gl, n = o.pos.length / 3;
    const buf = (data, size, name) => {
      const loc = gl.getAttribLocation(this.prog, name);
      const b = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, b);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW);
      return { b, size, loc };
    };
    return { n, attrs: [buf(o.pos, 3, 'p'), buf(o.nrm || new Array(n * 3).fill(0), 3, 'n'),
      buf(o.uv || new Array(n * 2).fill(0), 2, 't'), buf(o.shade || new Array(n).fill(1), 1, 's')] };
  }

  async texture(src) {
    const gl = this.gl;
    try {
      const image = await MT.loadImage(src);
      gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
      for (const p of [gl.TEXTURE_MIN_FILTER, gl.TEXTURE_MAG_FILTER]) gl.texParameteri(gl.TEXTURE_2D, p, gl.NEAREST);
      for (const p of [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T]) gl.texParameteri(gl.TEXTURE_2D, p, gl.CLAMP_TO_EDGE);
      return true;
    } catch {
      return false;  // file:// : le navigateur refuse l'image dans WebGL, la porte reste sans texture
    }
  }

  draw() {
    const gl = this.gl;
    if (!gl || !this.parts) return;
    const c = this.canvas, dpr = window.devicePixelRatio || 1;
    const w = Math.max(1, Math.round(c.clientWidth * dpr)), h = Math.max(1, Math.round(c.clientHeight * dpr));
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    gl.viewport(0, 0, w, h);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const fov = 0.6, dist = this.radius / Math.sin(fov / 2) / this.zoom;
    let model = M4.move(-this.center[0], -this.center[1], -this.center[2]);
    if (this.up === 'z') model = M4.mul(M4.rotX(-Math.PI / 2), model);
    const mv = M4.mul(M4.move(0, 0, -dist), M4.mul(M4.rotX(this.el), M4.mul(M4.rotY(this.az), model)));
    const mvp = M4.mul(M4.persp(fov, w / h, dist / 50, dist + this.radius * 4), mv);
    gl.uniformMatrix4fv(gl.getUniformLocation(this.prog, 'mvp'), false, mvp);
    gl.uniformMatrix4fv(gl.getUniformLocation(this.prog, 'mv'), false, mv);
    gl.uniform1i(gl.getUniformLocation(this.prog, 'mode'), this.mode);
    for (const part of this.parts) {
      for (const a of part.attrs) {
        if (a.loc < 0) continue;
        gl.bindBuffer(gl.ARRAY_BUFFER, a.b);
        gl.enableVertexAttribArray(a.loc);
        gl.vertexAttribPointer(a.loc, a.size, gl.FLOAT, false, 0, 0);
      }
      gl.drawArrays(gl.TRIANGLES, 0, part.n);
    }
  }

  stop() {
    this.resize.disconnect();
    const lose = this.gl && this.gl.getExtension('WEBGL_lose_context');
    if (lose) lose.loseContext();
    this.gl = null;
  }
};
