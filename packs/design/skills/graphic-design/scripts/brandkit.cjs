#!/usr/bin/env node
// Turn finished logo SVGs into a delivery kit and a one-page brand sheet.
//
//   node brandkit.cjs --logo logo.svg --mark mark.svg [--logo-dark logo-on-dark.svg]
//     --colors "#13213C:Ночь,#D9541E:Ржавчина,#F3ECE0:Крем" [--fonts "Unbounded,Manrope"]
//     [--name "Север"] [--out kit] [--fonts-css fonts/fonts.css]
//
// Writes:
//   svg/   logo, mark, on-dark, one-colour black and white versions (fills swapped)
//   png/   logo 512/1024/2048, mark 512/1024 (transparent), on-dark 1024
//   web/   favicon.ico (16/32/48), apple-touch-icon.png (180), icon-512.png
//          (maskable: mark inside the 80 % safe circle), og-image.png (1200×630)
//   brand-sheet.png + brand-sheet.pdf: versions, clear space, minimum size,
//          palette with HEX / RGB / CMYK (≈, confirm with the printer), fonts.
// One-colour versions recolour every fill/stroke; check them in the sheet, since
// a logo that relies on colour alone will lose detail there.
const { chromium } = require('playwright');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const argv = process.argv.slice(2);
const opt = (name, def) => {
  const i = argv.indexOf(name);
  return i >= 0 ? argv.splice(i, 2)[1] : def;
};
const logo = opt('--logo'), mark = opt('--mark'), logoDark = opt('--logo-dark');
const name = opt('--name', 'Бренд'), out = opt('--out', 'kit');
const fonts = opt('--fonts', '').split(',').map((s) => s.trim()).filter(Boolean);
// fonts.css from fonts.py, so the sheet shows the real typefaces.
const fontsCss = opt('--fonts-css', fs.existsSync('fonts/fonts.css') ? 'fonts/fonts.css' : '');
const colors = opt('--colors', '').split(',').filter(Boolean).map((c) => { const [hex, label] = c.split(':'); return { hex: hex.trim(), label: (label || '').trim() }; });
if (!logo || !mark || !colors.length) {
  console.error('usage: node brandkit.cjs --logo logo.svg --mark mark.svg --colors "#hex:Имя,..." [--logo-dark f.svg] [--fonts "A,B"] [--name N] [--out kit]');
  process.exit(1);
}

const read = (f) => fs.readFileSync(f, 'utf8');
const viewBox = (svg) => {
  const m = svg.match(/viewBox\s*=\s*["']([^"']+)/);
  const [, , w, h] = m ? m[1].trim().split(/[\s,]+/).map(Number) : [0, 0, 100, 100];
  return { w, h };
};
// Swap every paint for one colour; keeps "none" and url() references intact.
const mono = (svg, c) => svg
  .replace(/(fill|stroke)\s*=\s*["'](?!none|url)[^"']*["']/g, `$1="${c}"`)
  .replace(/(fill|stroke)\s*:\s*(?!none|url)[^;"']+/g, `$1:${c}`)
  .replace(/stop-color\s*=\s*["'][^"']*["']/g, `stop-color="${c}"`);
const hexRgb = (h) => { h = h.replace('#', ''); if (h.length === 3) h = [...h].map((c) => c + c).join(''); return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)); };
const cmyk = ([r, g, b]) => {
  const [R, G, B] = [r / 255, g / 255, b / 255], k = 1 - Math.max(R, G, B);
  if (k >= 1) return [0, 0, 0, 100];
  return [(1 - R - k) / (1 - k), (1 - G - k) / (1 - k), (1 - B - k) / (1 - k), k].map((v) => Math.round(v * 100));
};
const lum = (rgb) => { const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }; const [r, g, b] = rgb.map(f); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const dark = colors.reduce((a, c) => (lum(hexRgb(c.hex)) < lum(hexRgb(a.hex)) ? c : a)).hex;
const light = colors.reduce((a, c) => (lum(hexRgb(c.hex)) > lum(hexRgb(a.hex)) ? c : a)).hex;

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'brandkit-'));
for (const d of ['svg', 'png', 'web']) fs.mkdirSync(path.join(out, d), { recursive: true });
const svgs = {
  'logo.svg': read(logo), 'mark.svg': read(mark),
  'logo-black.svg': mono(read(logo), '#000000'), 'logo-white.svg': mono(read(logo), '#FFFFFF'),
  'mark-black.svg': mono(read(mark), '#000000'), 'mark-white.svg': mono(read(mark), '#FFFFFF'),
};
if (logoDark) svgs['logo-on-dark.svg'] = read(logoDark);
for (const [f, s] of Object.entries(svgs)) fs.writeFileSync(path.join(out, 'svg', f), s);
const url = (f) => pathToFileURL(path.resolve(out, 'svg', f)).href;

async function shot(browser, html, w, h, file, { transparent = false, pdf = false } = {}) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  const f = path.join(tmp, `${Math.random().toString(36).slice(2)}.html`);
  const link = fontsCss ? `<link rel="stylesheet" href="${pathToFileURL(path.resolve(fontsCss)).href}">` : '';
  fs.writeFileSync(f, `<!doctype html><meta charset="utf-8">${link}<style>html,body{margin:0;background:${transparent ? 'transparent' : '#fff'}}</style>${html}`);
  await page.goto(pathToFileURL(f).href, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => Promise.all([...document.images].map((im) => im.complete ? 0 : new Promise((r) => { im.onload = im.onerror = r; }))));
  if (pdf) await page.pdf({ path: file, width: `${w}px`, height: `${h}px`, printBackground: true, pageRanges: '1' });
  else fs.writeFileSync(file, await page.screenshot({ type: 'png', omitBackground: transparent }));
  await page.close();
  return file;
}
const fit = (src, w, h, bg = 'transparent', pad = 0) => `<div style="width:${w}px;height:${h}px;background:${bg};display:flex;align-items:center;justify-content:center;box-sizing:border-box;padding:${pad}px">
  <img src="${src}" style="max-width:100%;max-height:100%;object-fit:contain"></div>`;

function ico(pngs) {
  const head = Buffer.alloc(6 + 16 * pngs.length);
  head.writeUInt16LE(1, 2); head.writeUInt16LE(pngs.length, 4);
  let off = head.length;
  pngs.forEach(({ size, buf }, i) => {
    const e = 6 + i * 16;
    head.writeUInt8(size, e); head.writeUInt8(size, e + 1); head.writeUInt16LE(1, e + 4); head.writeUInt16LE(32, e + 6);
    head.writeUInt32LE(buf.length, e + 8); head.writeUInt32LE(off, e + 12); off += buf.length;
  });
  return Buffer.concat([head, ...pngs.map((p) => p.buf)]);
}

function sheet() {
  const L = viewBox(svgs['logo.svg']);
  const chip = (c) => { const rgb = hexRgb(c.hex), [C, M, Y, K] = cmyk(rgb), txt = lum(rgb) > 0.35 ? '#111' : '#fff';
    return `<div style="flex:1;background:${c.hex};color:${txt};padding:18px;border-radius:10px;font:500 15px/1.5 system-ui;min-height:150px;display:flex;flex-direction:column;justify-content:flex-end">
      <b style="font-size:20px">${c.label || c.hex}</b>HEX ${c.hex.toUpperCase()}<br>RGB ${rgb.join(' ')}<br>CMYK ≈ ${C} ${M} ${Y} ${K}</div>`; };
  const panel = (title, body) => `<div style="background:#fff;border-radius:14px;padding:24px;display:flex;flex-direction:column;gap:12px"><div style="font:600 13px system-ui;letter-spacing:.08em;text-transform:uppercase;color:#888">${title}</div>${body}</div>`;
  const markH = 120, logoH = Math.round(markH);
  const clear = `<div style="position:relative;display:inline-block;padding:${logoH / 2}px;outline:2px dashed #e0457b;outline-offset:0">
      <img src="${url('logo.svg')}" style="height:${logoH}px;display:block">
      <div style="position:absolute;left:0;top:0;width:${logoH / 2}px;height:${logoH / 2}px;background:rgba(224,69,123,.15)"></div></div>
      <div style="font:14px system-ui;color:#666">Охранное поле = ½ высоты логотипа со всех сторон</div>`;
  const minSize = `<div style="display:flex;gap:40px;align-items:flex-end;font:14px system-ui;color:#666">
      <div><img src="${url('logo.svg')}" style="width:120px;display:block"><br>логотип ≥ 120 px / 25 мм</div>
      <div><img src="${url('mark.svg')}" style="width:24px;display:block"><br>знак ≥ 16 px / 6 мм</div></div>`;
  const accent = colors.find((c) => c.hex !== dark && c.hex !== light)?.hex || dark;
  const tw = 470, th = 172;
  const versions = `<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      ${fit(url('logo.svg'), tw, th, light, 30)}${fit(url(logoDark ? 'logo-on-dark.svg' : 'logo-white.svg'), tw, th, dark, 30)}
      ${fit(url('logo-black.svg'), tw, th, '#fff', 30)}${fit(url('logo-white.svg'), tw, th, '#111', 30)}
      <div style="display:flex;gap:12px">${fit(url('mark.svg'), (tw - 12) / 2, th, light, 30)}${fit(url('mark-white.svg'), (tw - 12) / 2, th, accent, 30)}</div>
      <div style="display:flex;gap:12px">${fit(url('mark-black.svg'), (tw - 12) / 2, th, '#fff', 30)}${fit(url('mark.svg'), (tw - 12) / 2, th, '#fff', 64)}</div></div>`;
  const type = fonts.length ? fonts.map((f, i) => `<div style="font-family:'${f}',system-ui;font-size:${i ? 22 : 44}px;font-weight:${i ? 500 : 800};line-height:1.15">${f}${i ? ' — основной текст, подписи, интерфейс. Аа Бб Вв 0123456789' : ' — заголовки'}</div>`).join('') : '<div style="font:15px system-ui;color:#666">Шрифты не указаны</div>';
  return `<div style="width:1920px;height:1080px;box-sizing:border-box;padding:48px;background:#f0efec;font-family:system-ui;display:grid;grid-template-columns:1.25fr 1fr;grid-template-rows:auto 1fr auto;gap:20px">
    <div style="grid-column:1/3;display:flex;justify-content:space-between;align-items:center">
      <img src="${url('logo.svg')}" style="height:56px"><div style="font:600 18px system-ui;color:#555">${name} · логотип и цвета</div></div>
    ${panel('Версии', versions)}
    <div style="display:flex;flex-direction:column;gap:20px">${panel('Охранное поле', clear)}${panel('Минимальный размер', minSize)}</div>
    <div style="grid-column:1/3;display:grid;grid-template-columns:1.25fr 1fr;gap:20px">
      ${panel('Цвета', `<div style="display:flex;gap:12px">${colors.map(chip).join('')}</div>`)}${panel('Шрифты', type)}</div></div>`;
}

(async () => {
  const browser = await chromium.launch();
  const L = viewBox(svgs['logo.svg']), M = viewBox(svgs['mark.svg']);
  for (const n of [512, 1024, 2048]) {
    const k = n / Math.max(L.w, L.h);
    await shot(browser, fit(url('logo.svg'), Math.round(L.w * k), Math.round(L.h * k)), Math.round(L.w * k), Math.round(L.h * k), path.join(out, 'png', `logo-${n}.png`), { transparent: true });
  }
  for (const n of [512, 1024]) await shot(browser, fit(url('mark.svg'), n, n), n, n, path.join(out, 'png', `mark-${n}.png`), { transparent: true });
  if (logoDark) { const k = 1024 / Math.max(L.w, L.h); await shot(browser, fit(url('logo-on-dark.svg'), Math.round(L.w * k), Math.round(L.h * k)), Math.round(L.w * k), Math.round(L.h * k), path.join(out, 'png', 'logo-on-dark-1024.png'), { transparent: true }); }

  const icons = [];
  for (const n of [16, 32, 48]) {
    const f = await shot(browser, fit(url('mark.svg'), n, n), n, n, path.join(tmp, `i${n}.png`), { transparent: true });
    icons.push({ size: n, buf: fs.readFileSync(f) });
  }
  fs.writeFileSync(path.join(out, 'web', 'favicon.ico'), ico(icons));
  await shot(browser, fit(url('mark.svg'), 180, 180, light, 22), 180, 180, path.join(out, 'web', 'apple-touch-icon.png'));
  await shot(browser, fit(url('mark.svg'), 512, 512, light, 112), 512, 512, path.join(out, 'web', 'icon-512.png'));
  await shot(browser, fit(url(logoDark ? 'logo-on-dark.svg' : 'logo-white.svg'), 1200, 630, dark, 170), 1200, 630, path.join(out, 'web', 'og-image.png'));

  await shot(browser, sheet(), 1920, 1080, path.join(out, 'brand-sheet.png'));
  await shot(browser, sheet(), 1920, 1080, path.join(out, 'brand-sheet.pdf'), { pdf: true });
  await browser.close();
  console.log(`saved ${out}/ (svg ${Object.keys(svgs).length}, png, web: favicon.ico, apple-touch-icon, icon-512, og-image; brand-sheet.png/pdf)`);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
