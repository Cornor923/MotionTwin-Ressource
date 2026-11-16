window.MT = window.MT || {};

MT.TYPES = {
  img: { label: 'Image', plural: 'Images' },
  gif: { label: 'GIF animé', plural: 'GIF animés' },
  anim: { label: 'Animation GraphicsGale', plural: 'Animations GraphicsGale' },
  clip: { label: 'Clip Flash', plural: 'Clips Flash (rendus)' },
  svg: { label: 'Forme vectorielle', plural: 'Formes vectorielles (SVG)' },
  snd: { label: 'Son', plural: 'Sons' },
  lch: { label: 'Réglage de son', plural: 'Réglages de son (LabChirp)' },
  mdl: { label: 'Modèle 3D', plural: 'Modèles 3D' },
};

MT.el = (tag, attrs, ...children) => {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child !== null && child !== undefined && child !== false) node.append(child);
  }
  return node;
};

MT.fold = (text) => String(text).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

MT.bytes = (n) => {
  if (!n) return '';
  if (n < 1024) return n + ' o';
  if (n < 1024 * 1024) return (n / 1024).toFixed(1).replace('.0', '') + ' Ko';
  return (n / 1024 / 1024).toFixed(2) + ' Mo';
};

MT.gameName = (id, sub) => {  // « CaféJeux · Anticorp's » pour un sous-jeu
  const game = MT.catalog.games.find((g) => g.id === id) || { name: id };
  const part = sub && (game.parts || []).find((p) => p.id === sub);
  return part ? `${game.name} · ${part.name}` : game.name;
};

// taille montrée à l'utilisateur : les clips sont rendus à 2 px par pixel Flash
MT.renderScale = (item) => (item.t === 'clip' ? 2 : 1);

MT.dims = (item) => {
  if (!item.w) return '';
  const k = MT.renderScale(item);
  return `${Math.round((item.w / k) * 100) / 100}×${Math.round((item.h / k) * 100) / 100}`;
};

MT.frameDelay = (item, frame) => {
  if (item.d) return item.d[frame] || 100;
  return 1000 / (item.fps || 24);
};

MT.fileName = (item, ext) => {
  const base = item.n.replace(/[^\w.-]+/g, '_');
  return `${item.g}_${base}${ext}`;
};

MT.copy = async (text, message) => {
  try {
    await navigator.clipboard.writeText(text);
    MT.toast(message || 'Copié');
  } catch {
    window.prompt('Copier :', text);
  }
};

MT.toast = (message) => {
  const node = document.getElementById('toast');
  node.textContent = message;
  node.hidden = false;
  clearTimeout(MT.toast.timer);
  MT.toast.timer = setTimeout(() => { node.hidden = true; }, 1600);
};

MT.loadImage = (src) => new Promise((resolve, reject) => {
  const image = new Image();
  image.onload = () => resolve(image);
  image.onerror = reject;
  image.src = src;
});

MT.attribution = (item) => {
  const lic = MT.catalog.license;
  return `« ${item.n} » – ${MT.gameName(item.g, item.sg)}, © Motion Twin (${item.u}) – ${lic.name} ${lic.url}`;
};
