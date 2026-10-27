#!/usr/bin/env node
// Real 3D lettering: extruded, bevelled glyphs from any TTF/OTF (Cyrillic included),
// physically based materials, studio reflections, bloom, drips as geometry.
//
//   node text3d.cjs --text "КРОВЬ" --font fonts/DelaGothicOne-400.ttf --preset blood --out blood.png
//   node text3d.cjs --text "ПУЗЫРЬ" --font fonts/RubikBubbles-400.ttf --preset y2k --bg transparent --out y2k.png
//   node text3d.cjs --svg word.svg --preset chrome --out word.png   lettering from letterforms.py (or any SVG)
//   node text3d.cjs --list                                   presets and what they look like
//
// --size WxH (1600x900)  --scale N pixel ratio (2)   --bg "#hex" | "a,b" vertical gradient | transparent
// --yaw deg (-8) --tilt deg (10)  turn the text   --depth em (0.28)  --bevel em (preset)
// --tracking em (default 0.02 + 2×bevel, so bevels don't touch)  --lines "a|b" for two lines   --seed N (drips)   --drips N   --color "#hex" (tint)
// --bloom N (preset)    --shadow 0|1 (1)   --html keep the generated page for editing
// --svg file.svg  extrude prepared lettering instead of --text/--font (filled paths)
//
// First run installs three@0.170.0 into ~/.cache/graphic-design/three (npm, ~30 MB).
// Rendering uses the GPU when present; headless servers fall back to SwiftShader (slower).
const { chromium } = require('playwright');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const { execSync } = require('node:child_process');

const PRESETS = {
  chrome: 'зеркальный хром, студийные блики',
  gold: 'полированное золото, тёплые блики',
  steel: 'тёмная шлифованная сталь, тяжёлый металл',
  rust: 'ржавое железо: шершавое, пятнистое',
  blood: 'глянцевая кровь с объёмными подтёками',
  slime: 'полупрозрачная токсичная слизь с подтёками',
  ice: 'матовый светящийся лёд с сосульками',
  glass: 'дымчатое стекло с бликами (лучше на тёмном фоне)',
  y2k: 'надутый перламутровый хром (Y2K, бабл)',
  candy: 'глянцевый пластик/игрушка (--color)',
  neon: 'неоновые трубки по контуру букв с ореолом (--color)',
  lava: 'раскалённый металл/лава, свечение изнутри',
  stone: 'тёсаный камень, мягкий свет',
};

const argv = process.argv.slice(2);
const opt = (name, def) => { const i = argv.indexOf(name); return i >= 0 ? argv.splice(i, 2)[1] : def; };
const flag = (name) => { const i = argv.indexOf(name); return i >= 0 ? (argv.splice(i, 1), true) : false; };
if (flag('--list')) { for (const [k, v] of Object.entries(PRESETS)) console.log(`${k.padEnd(7)} ${v}`); process.exit(0); }
const o = {
  text: opt('--text'), lines: opt('--lines'), font: opt('--font'), svg: opt('--svg'), preset: opt('--preset', 'chrome'), out: opt('--out', 'text3d.png'),
  size: opt('--size', '1600x900'), scale: Number(opt('--scale', '2')), bg: opt('--bg'), yaw: Number(opt('--yaw', '-8')),
  tilt: Number(opt('--tilt', '10')), depth: Number(opt('--depth', '0.28')), bevel: opt('--bevel'), tracking: opt('--tracking'),
  seed: Number(opt('--seed', '7')), drips: opt('--drips'), color: opt('--color'), bloom: opt('--bloom'), shadow: opt('--shadow', '1') !== '0',
  html: flag('--html'),
};
if (!((o.text || o.lines) && o.font) && !o.svg || !PRESETS[o.preset]) {
  console.error('usage: node text3d.cjs (--text "ТЕКСТ" --font font.ttf | --svg word.svg) --preset <' + Object.keys(PRESETS).join('|') + '> --out out.png  (--list)');
  process.exit(1);
}
const [W, H] = o.size.split('x').map(Number);

// three.js, installed once per machine.
const LIB = path.join(os.homedir(), '.cache', 'graphic-design', 'three');
if (!fs.existsSync(path.join(LIB, 'node_modules', 'three', 'build', 'three.module.js'))) {
  fs.mkdirSync(LIB, { recursive: true });
  console.error('installing three@0.170.0 (one time)...');
  execSync('npm init -y && npm i -s three@0.170.0', { cwd: LIB, stdio: 'ignore', shell: true });
}

const page = `<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:transparent}canvas{display:block}</style>
<script type="importmap">{"imports":{"three":"/three/build/three.module.js","three/addons/":"/three/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import opentype from 'three/addons/libs/opentype.module.js';
import { SVGLoader } from 'three/addons/loaders/SVGLoader.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';
const O = ${JSON.stringify(o)};
const W = ${W}, H = ${H};
let s = O.seed * 9301 + 49297; const rnd = () => ((s = (s * 9301 + 49297) % 233280) / 233280);

// ---------- presets ----------
const tint = (c, d) => new THREE.Color(c || d);
const P = {
  chrome: { env: 'sky:chrome', mat: () => new THREE.MeshPhysicalMaterial({ color: 0xffffff, metalness: 1, roughness: 0.03 }), bevel: 0.05, bg: '#2a3442,#07090c', bloom: 0.25 },
  gold:   { env: 'sky:gold', mat: () => new THREE.MeshPhysicalMaterial({ color: tint(O.color, 0xffc55a), metalness: 1, roughness: 0.14 }), bevel: 0.05, bg: '#2a1c0c,#070402', bloom: 0.35 },
  steel:  { env: 'sky:steel', mat: () => new THREE.MeshPhysicalMaterial({ color: 0xc2c9d2, metalness: 1, roughness: 0.1, anisotropy: 0.5, clearcoat: 0.6 }), bevel: 0.035, bg: '#2b2f36,#08090b', bloom: 0.15 },
  rust:   { env: 'studio', mat: () => noiseMat('rust'), bevel: 0.025, bg: '#2b2520,#0d0b09', bloom: 0 },
  blood:  { env: 'studio', exposure: 1.3, mat: () => new THREE.MeshPhysicalMaterial({ color: tint(O.color, 0xa8000c), metalness: 0, roughness: 0.12, clearcoat: 1, clearcoatRoughness: 0.02 }), bevel: 0.035, bg: '#3a0606,#080000', bloom: 0.18, drips: 10 },
  slime:  { env: 'studio', exposure: 1.2, mat: () => new THREE.MeshPhysicalMaterial({ color: tint(O.color, 0x6cff12), metalness: 0, roughness: 0.12, clearcoat: 1, transmission: 0.35, thickness: 0.6, emissive: 0x1a5a00, emissiveIntensity: 0.6 }), bevel: 0.045, bg: '#10180a,#020401', bloom: 0.35, drips: 8 },
  ice:    { env: 'sky:ice', exposure: 1.15, mat: () => new THREE.MeshPhysicalMaterial({ color: 0xd4f1ff, metalness: 0, roughness: 0.28, transmission: 0.55, thickness: 1.2, ior: 1.31, attenuationColor: new THREE.Color(0x8fd3f5), attenuationDistance: 2, clearcoat: 1, clearcoatRoughness: 0.05, sheen: 0.6, sheenColor: new THREE.Color(0xffffff) }), bevel: 0.035, bg: '#2f6f9c,#0a2236', bloom: 0.3, icicles: 12 },
  glass:  { env: 'sky:chrome', mat: () => new THREE.MeshPhysicalMaterial({ color: 0xffffff, metalness: 0, roughness: 0, transmission: 1, thickness: 2, ior: 1.7, dispersion: 6, attenuationColor: new THREE.Color(O.color || '#9fe8ff'), attenuationDistance: 3, clearcoat: 1 }), bevel: 0.07, segs: 10, bg: '#1d2a44,#05070d', bloom: 0.3 },
  y2k:    { env: 'sky:y2k', mat: () => new THREE.MeshPhysicalMaterial({ color: 0xffffff, metalness: 1, roughness: 0.04, iridescence: 0.7, iridescenceIOR: 1.6, iridescenceThicknessRange: [200, 500] }), bevel: 0.11, segs: 14, bg: '#3b2a9e,#ff7ad9', bloom: 0.35 },
  candy:  { env: 'studio', mat: () => new THREE.MeshPhysicalMaterial({ color: tint(O.color, 0xff4fa3), metalness: 0, roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.05 }), bevel: 0.09, segs: 12, bg: '#fff1c9,#ffd3e6', bloom: 0.05 },
  neon:   { env: 'dark', tubes: true, mat: () => new THREE.MeshBasicMaterial({ color: new THREE.Color(O.color || '#ff3fd2').lerp(new THREE.Color('#ffffff'), 0.3).multiplyScalar(2.0) }), bevel: 0.02, bg: '#1a0b16,#040104', bloom: 0.35, bloomRadius: 0.2, bloomThreshold: 0.9, shadow: false },
  lava:   { env: 'dark', mat: () => noiseMat('lava'), bevel: 0.04, bg: '#1a0602,#030100', bloom: 1.1 },
  stone:  { env: 'studio', mat: () => noiseMat('stone'), bevel: 0.02, bg: '#5d5a55,#262421', bloom: 0 },
}[O.preset];

function noiseTex(kind) {
  const c = document.createElement('canvas'); c.width = c.height = 512; const g = c.getContext('2d');
  const img = g.createImageData(512, 512);
  // value noise, 4 octaves
  const grid = (n) => { const a = new Float32Array((n + 1) * (n + 1)); for (let i = 0; i < a.length; i++) a[i] = rnd(); return a; };
  const oct = [4, 16, 48, 128].map((n) => ({ n, a: grid(n) }));
  const smp = ({ n, a }, x, y) => { const fx = x * n, fy = y * n, ix = Math.floor(fx), iy = Math.floor(fy), tx = fx - ix, ty = fy - iy;
    const v = (i, j) => a[Math.min(n, iy + j) * (n + 1) + Math.min(n, ix + i)]; const sx = tx * tx * (3 - 2 * tx), sy = ty * ty * (3 - 2 * ty);
    return (v(0, 0) * (1 - sx) + v(1, 0) * sx) * (1 - sy) + (v(0, 1) * (1 - sx) + v(1, 1) * sx) * sy; };
  for (let y = 0; y < 512; y++) for (let x = 0; x < 512; x++) {
    const n = oct.reduce((t, o, i) => t + smp(o, x / 512, y / 512) / 2 ** i, 0) / 1.875, k = (y * 512 + x) * 4;
    let r, gg, b;
    if (kind === 'rust') { const t = Math.min(1, Math.max(0, (n - 0.35) * 2.2)); r = 60 + t * 150; gg = 30 + t * 62; b = 18 + t * 18; if (n > 0.72) { r = 120; gg = 110; b = 100; } }
    else if (kind === 'lava') { const t = Math.max(0, n - 0.42) * 3; r = 255 * Math.min(1, t * 1.4); gg = 200 * Math.min(1, t * t); b = 40 * t * t; if (n < 0.42) { r = 22; gg = 12; b = 10; } }
    else { const t = n; r = gg = 150 * t + 40; b = 140 * t + 40; }
    img.data[k] = r; img.data[k + 1] = gg; img.data[k + 2] = b; img.data[k + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(c); tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.colorSpace = THREE.SRGBColorSpace; return tex;
}
function noiseMat(kind) {
  const t = noiseTex(kind);
  if (kind === 'rust') return new THREE.MeshPhysicalMaterial({ map: t, roughnessMap: t, roughness: 0.95, metalness: 0.35, bumpMap: t, bumpScale: 3 });
  if (kind === 'lava') return new THREE.MeshPhysicalMaterial({ color: 0x2a0d06, emissiveMap: t, emissive: 0xffffff, emissiveIntensity: 2.4, roughness: 0.7, bumpMap: t, bumpScale: 4 });
  return new THREE.MeshPhysicalMaterial({ map: t, roughness: 0.92, metalness: 0, bumpMap: t, bumpScale: 5 });
}

// ---------- environment for reflections ----------
// Sky environments: bright sky, a crisp horizon and dark ground. Chrome only reads
// as chrome when it reflects that contrast.
function skyEnv(kind) {
  const C = {
    chrome: ['#f4f8ff', '#8fb3d9', '#ffffff', '#4a3d34', '#0a0807'],
    gold:   ['#fff6df', '#e9b45c', '#fffbe8', '#5a3510', '#120802'],
    steel:  ['#e6eaee', '#7d8794', '#ffffff', '#30343a', '#0b0c0e'],
    ice:    ['#ffffff', '#bfe8ff', '#ffffff', '#2a6f9e', '#06243a'],
    y2k:    ['#ffffff', '#9fd4ff', '#ffe6fb', '#7a5cff', '#1d0f5a'],
  }[kind];
  const cv = document.createElement('canvas'); cv.width = 1024; cv.height = 512; const g = cv.getContext('2d');
  // A front face tilted back by T reflects a ray 2T below the horizon, so put the
  // horizon exactly there: it then cuts through the letters like 80s chrome, with
  // steep colour changes on both sides to make the most of the small angle range.
  const HZ = Math.round(256 + (2 * O.tilt / 180) * 512);
  const sky = g.createLinearGradient(0, 0, 0, HZ);
  sky.addColorStop(0, C[1]); sky.addColorStop(Math.max(0, 1 - 70 / HZ), C[1]); sky.addColorStop(1, C[0]);
  g.fillStyle = sky; g.fillRect(0, 0, 1024, HZ);
  const gr = g.createLinearGradient(0, HZ, 0, 512);
  gr.addColorStop(0, C[4]); gr.addColorStop(Math.min(1, 50 / (512 - HZ)), C[3]); gr.addColorStop(1, C[4]);
  g.fillStyle = gr; g.fillRect(0, HZ, 1024, 512 - HZ);
  g.fillStyle = C[2]; g.fillRect(0, HZ - 3, 1024, 4);              // horizon glint
  g.fillStyle = 'rgba(255,255,255,.95)'; g.fillRect(380, 40, 260, 34); g.fillRect(120, 120, 60, 90); g.fillRect(840, 110, 60, 100); // softboxes
  const t = new THREE.CanvasTexture(cv); t.mapping = THREE.EquirectangularReflectionMapping; t.colorSpace = THREE.SRGBColorSpace; return t;
}
function envScene(kind) {
  const sc = new THREE.Scene();
  const base = { studio: 0x0d0f13, warm: 0x120a04, dark: 0x050505, cold: 0x06121d, pastel: 0x9fc3ff }[kind];
  sc.background = new THREE.Color(base);
  const box = (w, h, x, y, z, col, i) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(col).multiplyScalar(i), side: THREE.DoubleSide }));
    m.position.set(x, y, z); m.lookAt(0, 0, 0); sc.add(m); };
  const lights = {
    studio: [[14, 3, 0, 9, 3, 0xffffff, 6], [3, 10, -9, 2, 6, 0xffffff, 3], [3, 10, 9, 2, 6, 0xdde6ff, 3], [20, 2, 0, -6, 6, 0xffffff, 1.2], [10, 10, 0, 2, -10, 0x8899aa, 0.6]],
    warm: [[14, 3, 0, 9, 3, 0xfff1d6, 6], [3, 10, -9, 2, 6, 0xffcc88, 4], [3, 10, 9, 2, 6, 0xffe2b0, 2.5], [20, 2, 0, -6, 6, 0xff9a40, 1.5]],
    dark: [[10, 2, 0, 9, 4, 0xffffff, 5], [2, 8, -9, 2, 5, 0xff6060, 1.5], [2, 8, 9, 2, 5, 0xffffff, 2]],
    cold: [[14, 3, 0, 9, 3, 0xe8f6ff, 5], [3, 10, -9, 2, 6, 0x88ccff, 3], [3, 10, 9, 2, 6, 0xffffff, 2.5], [20, 3, 0, -6, 6, 0x4aa0ff, 1.5]],
    pastel: [[14, 3, 0, 9, 3, 0xffffff, 5], [4, 10, -9, 2, 6, 0xffb3ec, 3], [4, 10, 9, 2, 6, 0x9fffee, 3], [20, 3, 0, -6, 6, 0xc9b5ff, 2.5], [10, 10, 0, 2, -10, 0xfff3b0, 1.5]],
  }[kind];
  for (const l of lights) box(...l);
  return sc;
}

// ---------- text geometry with tracking, per-glyph so drips know where letters are ----------
// Glyphs come straight from opentype by codepoint. (three's TTFLoader keys glyphs by
// their first Unicode only, so Cyrillic letters that share a Latin glyph get lost.)
const buf = O.svg ? null : await (await fetch('/font')).arrayBuffer();
const otf = O.svg ? null : opentype.parse(buf);
const SIZE = 1, K = otf ? SIZE / otf.unitsPerEm : 1;
const cff = otf && otf.outlinesFormat === 'cff';   // CFF outlines wind the other way
function glyphShapes(glyph) {
  const sp = new THREE.ShapePath();
  for (const c of glyph.path.commands) {
    if (c.type === 'M') sp.moveTo(c.x * K, c.y * K);
    else if (c.type === 'L') sp.lineTo(c.x * K, c.y * K);
    else if (c.type === 'Q') sp.quadraticCurveTo(c.x1 * K, c.y1 * K, c.x * K, c.y * K);
    else if (c.type === 'C') sp.bezierCurveTo(c.x1 * K, c.y1 * K, c.x2 * K, c.y2 * K, c.x * K, c.y * K);
  }
  return sp.toShapes(cff);
}
const lines = O.svg ? [] : (O.lines || O.text).split('|');
const group = new THREE.Group();
const glyphMeta = [];
const bevel = Number(O.bevel ?? P.bevel);
const extrude = { depth: O.depth, bevelEnabled: true, bevelThickness: bevel * 0.9, bevelSize: bevel, bevelSegments: P.segs || 6, curveSegments: 10 };
const lineH = 1.18;
const TRACK = O.tracking != null ? Number(O.tracking) : 0.02 + 2 * bevel;
lines.forEach((line, li) => {
  let x = 0, prev = null;
  for (const ch of line) {
    const g = otf.charToGlyph(ch);
    if (g.index === 0 && ch.trim()) (window.__missing ||= []).push(ch);
    if (prev) x += otf.getKerningValue(prev, g) * K;
    prev = g;
    const adv = g.advanceWidth * K;
    if (ch.trim() && g.index !== 0) {
      const shapes = glyphShapes(g);
      const geo = new THREE.ExtrudeGeometry(shapes, extrude);
      geo.computeBoundingBox();
      const yOff = -li * lineH;
      geo.translate(x, yOff, 0);
      glyphMeta.push({ shapes, x, y: yOff, box: geo.boundingBox.clone() });
      const mesh = new THREE.Mesh(geo); mesh.userData.line = li; group.add(mesh);
    }
    x += adv + TRACK * SIZE;
  }
});
if (O.svg) {
  // Prepared lettering (letterforms.py or any SVG): every filled path becomes shapes,
  // y flipped, scaled so the artwork is ~1 unit tall like a line of type.
  const data = new SVGLoader().parse(await (await fetch('/svg')).text());
  const all = [];
  for (const path of data.paths) for (const sh of SVGLoader.createShapes(path)) all.push(sh);
  const pts = all.flatMap((sh) => sh.getPoints(4));
  const ys = pts.map((p) => p.y), xs = pts.map((p) => p.x);
  const hh = Math.max(...ys) - Math.min(...ys), ww = Math.max(...xs) - Math.min(...xs);
  const k = 1 / Math.max(hh, ww / 4);
  const flip = (sh) => { const m = new THREE.Matrix3().set(k, 0, 0, 0, -k, 0, 0, 0, 1);
    const tr = (curvePts) => curvePts.map((p) => p.clone().applyMatrix3(m));
    const ns = new THREE.Shape(tr(sh.getPoints(12)));
    ns.holes = sh.holes.map((h) => new THREE.Path(tr(h.getPoints(12))));
    return ns; };
  const shapes = all.map(flip);
  const geo = new THREE.ExtrudeGeometry(shapes, { ...extrude, curveSegments: 4 });
  const mesh = new THREE.Mesh(geo); group.add(mesh);
  glyphMeta.push({ shapes, x: 0, y: 0 });
}
const mat = P.mat();
group.children.forEach((m) => { m.material = mat; m.castShadow = true; });
if (P.tubes) {
  // Neon: glowing glass tubes along every glyph contour, over dim letter bodies.
  const body = new THREE.MeshPhysicalMaterial({ color: 0x150a12, roughness: 0.6, metalness: 0.2 });
  group.children.forEach((m) => { m.material = body; m.scale.z = 0.25; });
  const R = 0.022;
  const glowCol = new THREE.Color(O.color || '#ff3fd2');
  const halo = (a) => new THREE.MeshBasicMaterial({ color: glowCol, transparent: true, opacity: a, blending: THREE.AdditiveBlending, depthWrite: false });
  for (const gm of glyphMeta) for (const sh of gm.shapes) {
    for (const pts of [sh.getPoints(24), ...sh.holes.map((h) => h.getPoints(24))]) {
      const v = pts.map((p) => new THREE.Vector3(gm.x + p.x, gm.y + p.y, O.depth * 0.25 + bevel + R * 1.5));
      if (v.length < 3) continue;
      const inset = v; // tubes ride on the face edge
      const curve = new THREE.CatmullRomCurve3(inset, true, 'centripetal');
      const seg = Math.max(40, v.length * 3);
      group.add(new THREE.Mesh(new THREE.TubeGeometry(curve, seg, R, 10, true), mat));
      // Halo: wider additive tubes keep the glow local instead of a full-frame haze.
      for (const [k, a] of [[1.7, 0.16], [2.4, 0.1], [3.3, 0.07], [4.5, 0.045], [6.2, 0.03], [8.5, 0.02], [11.5, 0.012]])
        group.add(new THREE.Mesh(new THREE.TubeGeometry(curve, seg, R * k, 10, true), halo(a)));
    }
  }
}

// ---------- drips / icicles hanging from the lowest edges of letters ----------
const nDrips = Number(O.drips ?? (P.drips || P.icicles || 0));
if (nDrips) {
  const lows = [];
  for (const gm of glyphMeta) {
    for (const sh of gm.shapes) {
      const pts = sh.extractPoints(8).shape;
      const minY = Math.min(...pts.map((p) => p.y));
      for (let i = 0; i < pts.length; i++) {
        const a = pts[i], b = pts[(i + 1) % pts.length];
        // near-horizontal bottom edges of the glyph outline
        if (Math.abs(a.y - b.y) < 0.02 && a.y < minY + 0.06 && Math.abs(a.x - b.x) > 0.05) lows.push([gm.x + Math.min(a.x, b.x), gm.x + Math.max(a.x, b.x), gm.y + a.y]);
      }
    }
  }
  const zMid = O.depth / 2;
  for (let k = 0; k < nDrips && lows.length; k++) {
    const [x0, x1, y] = lows[Math.floor(rnd() * lows.length)];
    const x = x0 + (x1 - x0) * (0.15 + rnd() * 0.7);
    if (P.icicles) {
      const len = 0.18 + rnd() * 0.42, r = 0.03 + rnd() * 0.035;
      const cone = new THREE.Mesh(new THREE.ConeGeometry(r, len, 24), mat);
      cone.rotation.x = Math.PI; cone.position.set(x, y - len / 2 + 0.01, zMid + (rnd() - 0.5) * O.depth * 0.5); group.add(cone);
    } else {
      // One smooth teardrop: flared where it leaves the letter, thin neck, heavy bulb.
      const len = 0.12 + rnd() * 0.5, r = 0.024 + rnd() * 0.03;
      const prof = new THREE.SplineCurve([
        new THREE.Vector2(0.0001, -len - r * 2.9), new THREE.Vector2(r * 1.35, -len - r * 2.2), new THREE.Vector2(r * 1.6, -len - r * 1.1),
        new THREE.Vector2(r * 0.95, -len + r * 0.4), new THREE.Vector2(r * 0.85, -len * 0.55), new THREE.Vector2(r * 1.05, -len * 0.2),
        new THREE.Vector2(r * 2.3, -r * 0.2), new THREE.Vector2(r * 1.2, r * 0.6), new THREE.Vector2(0.0001, r * 0.8),
      ]).getPoints(60);
      const drip = new THREE.Mesh(new THREE.LatheGeometry(prof, 40), mat);
      drip.scale.z = 0.8; drip.position.set(x, y + bevel * 0.5, zMid); group.add(drip);
      if (rnd() > 0.55) { const sp = new THREE.Mesh(new THREE.SphereGeometry(r * (0.7 + rnd() * 0.5), 24, 18), mat);
        sp.position.set(x + (rnd() - 0.5) * 0.1, y - len - r * 5 - rnd() * 0.2, zMid); group.add(sp); }
    }
  }
}

// Centre by moving the group, not the geometries: scaled meshes (drops, necks)
// would scale a geometry offset and drift away from their letters.
const bb = new THREE.Box3().setFromObject(group);
group.position.copy(bb.getCenter(new THREE.Vector3()).negate());
const pivot = new THREE.Group(); pivot.add(group);
pivot.rotation.set(THREE.MathUtils.degToRad(O.tilt), THREE.MathUtils.degToRad(O.yaw), 0);

// ---------- scene, camera fitted to the text ----------
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: O.bg === 'transparent', preserveDrawingBuffer: true });
renderer.setPixelRatio(O.scale); renderer.setSize(W, H);
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = P.exposure || 1.1;
if (P.shadow === false) O.shadow = false;
renderer.shadowMap.enabled = O.shadow; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = P.env.startsWith('sky:') ? pmrem.fromEquirectangular(skyEnv(P.env.slice(4))).texture : pmrem.fromScene(envScene(P.env), 0.02).texture;
const bgSpec = O.bg || P.bg;
if (bgSpec !== 'transparent') {
  const [c1, c2] = bgSpec.split(',');
  const cv = document.createElement('canvas'); cv.width = 4; cv.height = 512; const gx = cv.getContext('2d');
  const gr = gx.createLinearGradient(0, 0, 0, 512); gr.addColorStop(0, c1); gr.addColorStop(1, c2 || c1); gx.fillStyle = gr; gx.fillRect(0, 0, 4, 512);
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; scene.background = t;
}
scene.add(pivot);
const key = new THREE.DirectionalLight(0xffffff, P.env === 'dark' ? 1.5 : 2.6);
const rim = new THREE.DirectionalLight(0xffffff, 1.6); rim.position.set(4, 3, -5); scene.add(rim);
key.position.set(-3, 6, 6); key.castShadow = O.shadow; key.shadow.mapSize.set(2048, 2048);
Object.assign(key.shadow.camera, { left: -8, right: 8, top: 8, bottom: -8 }); key.shadow.radius = 6;
scene.add(key);
const sz = new THREE.Box3().setFromObject(pivot).getSize(new THREE.Vector3());
if (O.shadow && bgSpec !== 'transparent') {
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.ShadowMaterial({ opacity: 0.35 }));
  ground.rotation.x = -Math.PI / 2; ground.position.y = -sz.y / 2 - 0.25; ground.receiveShadow = true; scene.add(ground);
}
const camera = new THREE.PerspectiveCamera(28, W / H, 0.1, 200);
const fitH = Math.max(sz.y * 1.45, (sz.x * 1.2) / (W / H));
const dist = fitH / 2 / Math.tan(THREE.MathUtils.degToRad(14));
camera.position.set(0, 0, dist); camera.lookAt(0, 0, 0);
// Multi-line sky reflections: each line sees the environment from a different
// vertical angle, so only one line would catch the horizon. Rotate the env map per
// line by that angle so every line gets its own horizon (classic chrome lettering).
if (lines.length > 1 && P.env.startsWith('sky:')) {
  const envTex = scene.environment;
  const mats = lines.map((_, li) => {
    const m = mat.clone(); m.envMap = envTex;
    pivot.updateMatrixWorld(true);
    const v = new THREE.Vector3(0, -li * lineH + 0.36, O.depth / 2); group.localToWorld(v);
    m.envMapRotation.x = -Math.atan2(v.y, dist);
    return m;
  });
  group.children.forEach((c) => { if (c.userData.line != null) c.material = mats[c.userData.line]; });
}

const bloomK = Number(O.bloom ?? P.bloom);
if (bloomK > 0 && bgSpec !== 'transparent') {
  const comp = new EffectComposer(renderer);
  comp.addPass(new RenderPass(scene, camera));
  comp.addPass(new UnrealBloomPass(new THREE.Vector2(W, H), bloomK, P.bloomRadius ?? 0.55, P.bloomThreshold ?? 0.82));
  comp.addPass(new OutputPass());
  comp.render();
} else {
  renderer.render(scene, camera);
}
window.__done = true;
</script>`;

(async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'text3d-'));
  fs.writeFileSync(path.join(dir, 'index.html'), page);
  const fontBuf = o.font ? fs.readFileSync(o.font) : Buffer.alloc(0);
  const svgBuf = o.svg ? fs.readFileSync(o.svg) : Buffer.alloc(0);
  const three = path.join(LIB, 'node_modules', 'three');
  const types = { '.js': 'text/javascript', '.html': 'text/html' };
  // ES modules do not load from file://, so serve the page over loopback.
  const server = http.createServer((req, res) => {
    const u = decodeURIComponent(req.url.split('?')[0]);
    if (u === '/font') { res.writeHead(200, { 'content-type': 'application/octet-stream' }); return res.end(fontBuf); }
    if (u === '/svg') { res.writeHead(200, { 'content-type': 'image/svg+xml' }); return res.end(svgBuf); }
    const file = u.startsWith('/three/') ? path.join(three, u.slice(7)) : path.join(dir, u === '/' ? 'index.html' : u);
    fs.readFile(file, (err, data) => { if (err) { res.writeHead(404); return res.end(); }
      res.writeHead(200, { 'content-type': types[path.extname(file)] || 'application/octet-stream' }); res.end(data); });
  }).listen(0, '127.0.0.1');
  await new Promise((r) => server.on('listening', r));
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const pg = await browser.newPage({ viewport: { width: W, height: H } });
  let failed = null;
  pg.on('pageerror', (e) => { failed = e.message; console.error('page error:', e.message); });
  pg.on('console', (m) => m.type() === 'error' && console.error('console:', m.text()));
  const t0 = Date.now();
  await pg.goto(`http://127.0.0.1:${server.address().port}/`);
  // Stop at once on a script error instead of waiting out the timeout.
  const t1 = Date.now();
  while (!(await pg.evaluate(() => window.__done === true))) {
    if (failed) { await browser.close(); server.close(); process.exit(1); }
    if (Date.now() - t1 > 300000) throw new Error('render timed out');
    await new Promise((r) => setTimeout(r, 100));
  }
  const missing = await pg.evaluate(() => window.__missing || []);
  if (missing.length) {
    await browser.close(); server.close();
    console.error(`в шрифте нет символов: ${[...new Set(missing)].join(' ')} — возьми шрифт с кириллицей (typelib.py list <стиль> --cyr)`);
    process.exit(1);
  }
  await pg.locator('canvas').screenshot({ path: o.out, omitBackground: o.bg === 'transparent' });
  await browser.close(); server.close();
  if (o.html) console.log(`page kept: ${path.join(dir, 'index.html')} (serve it with font at /font)`); else fs.rmSync(dir, { recursive: true, force: true });
  console.log(`saved ${o.out} (${W * o.scale}×${H * o.scale}, ${o.preset}, ${((Date.now() - t0) / 1000).toFixed(1)} s)`);
})().catch((e) => { console.error(e); process.exit(1); });
