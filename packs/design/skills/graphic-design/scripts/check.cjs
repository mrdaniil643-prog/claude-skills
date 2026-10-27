#!/usr/bin/env node
// Measure a design instead of eyeballing it: text contrast against the pixels
// actually behind it, text size, safe zones, fonts and colours in use.
//
//   node check.cjs thumb.html  --kind thumb  [--size 1280x720]
//   node check.cjs cover.html  --kind cover  [--size 1080x1920]
//   node check.cjs poster.html --kind poster --mm 420x594 --bleed 3 [--safe 12]
//   node check.cjs page.html   [--size WxH]                (generic checks only)
//   --query "format=story&layout=lineup"   same query string as render.cjs, for data-driven templates
//
// Exit code 1 when anything FAILs, so it can gate delivery. Text that sits on
// a photo is measured against its 10th-percentile worst background pixel, and an
// outline (-webkit-text-stroke) or a centred drop-shadow halo counts when it is thick enough.
const { chromium } = require('playwright');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const argv = process.argv.slice(2);
const opt = (name, def) => {
  const i = argv.indexOf(name);
  return i >= 0 ? argv.splice(i, 2)[1] : def;
};
const kind = opt('--kind', 'generic');
const mmArg = opt('--mm');
const bleed = Number(opt('--bleed', '0'));
const safeMm = Number(opt('--safe', mmArg && Math.max(...mmArg.split('x').map(Number)) >= 590 ? '12' : '5'));
const defaults = { thumb: '1280x720', cover: '1080x1920' };
const sizeArg = opt('--size', defaults[kind]);
const query = opt('--query', '');
const [input] = argv;
if (!input) {
  console.error('usage: node check.cjs <design.html> [--kind thumb|cover|poster] [--size WxH | --mm WxH --bleed N] [--query "a=b"]');
  process.exit(1);
}
const MM = 96 / 25.4;
let W, H;
if (mmArg) {
  const [tw, th] = mmArg.split('x').map(Number);
  W = (tw + 2 * bleed) * MM; H = (th + 2 * bleed) * MM;
} else {
  [W, H] = (sizeArg || '1280x720').split('x').map(Number);
}

const results = [];
const add = (level, what, detail) => results.push({ level, what, detail });

function lum([r, g, b]) {
  const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
const parseRgb = (s) => (s.match(/[\d.]+/g) || []).map(Number);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: Math.round(W), height: Math.round(H) } });
  await page.goto(pathToFileURL(path.resolve(input)).href + (query ? `?${query.replace(/^\?/, '')}` : ''), { waitUntil: 'networkidle' });
  if (mmArg) {
    const [tw, th] = mmArg.split('x').map(Number);
    await page.addStyleTag({ content: `:root{--trim-w:${tw}mm;--trim-h:${th}mm;--bleed:${bleed}mm}` });
  }
  await page.evaluate(async () => {
    await document.fonts.ready;
    for (let i = 0; i < 100 && window.__pending; i++) await new Promise((r) => setTimeout(r, 50));
  });
  await page.addStyleTag({ content: '[data-check-hide] *{color:transparent!important;-webkit-text-stroke-color:transparent!important;text-shadow:none!important}' });

  // Every element that owns visible text, with its geometry and paint.
  const texts = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('body *').forEach((el, i) => {
      const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
      const cs = getComputedStyle(el);
      if (!own || cs.visibility === 'hidden' || cs.display === 'none' || el.closest('.guides')) return;
      const cropped = !!el.closest('[data-crop]'); // intentional bleed off the edge
      const range = document.createRange();
      range.selectNodeContents(el);
      const g = range.getBoundingClientRect();
      if (g.width < 1 || g.height < 1) return;
      // Glyph boxes include the font's ascent/descent, which can poke past the
      // line box; the element's own box clips that slack away.
      // Inline boxes (an <em> inside a headline) are as tall as the font's content
      // area, so clip against the nearest block-level ancestor instead.
      let blk = el;
      while (blk.parentElement && getComputedStyle(blk).display.startsWith('inline')) blk = blk.parentElement;
      const b = blk.getBoundingClientRect();
      const r = { left: g.left, right: g.right, top: Math.max(g.top, b.top), bottom: Math.min(g.bottom, b.bottom) };
      if (r.bottom - r.top < 1) { r.top = g.top; r.bottom = g.bottom; }
      el.dataset.checkId = String(i);
      const shadow = cs.textShadow !== 'none' ? cs.textShadow : '';
      // a centred drop-shadow filter on the element or an ancestor acts as a soft outline (halo)
      let halo = null;
      for (let a = el; a && a !== document.body && !halo; a = a.parentElement) {
        const f = getComputedStyle(a).filter || '';
        for (const m of f.matchAll(/drop-shadow\((rgba?\([^)]*\))\s+(-?[\d.]+)px\s+(-?[\d.]+)px\s+([\d.]+)px\)/g)) {
          const alpha = (m[1].match(/[\d.]+/g) || [])[3];
          if (Math.abs(+m[2]) < 1 && Math.abs(+m[3]) < 1 && (alpha === undefined || +alpha >= 0.6)) { halo = { color: m[1], blur: +m[4] }; break; }
        }
      }
      out.push({
        id: String(i), text: (el.innerText || el.textContent).trim().replace(/\s+/g, ' ').slice(0, 32),
        x: r.left, y: r.top, w: r.right - r.left, h: r.bottom - r.top,
        size: parseFloat(cs.fontSize), color: cs.color, family: cs.fontFamily.split(',')[0].replace(/["']/g, '').trim(),
        weight: cs.fontWeight, stroke: parseFloat(cs.webkitTextStrokeWidth) || 0, strokeColor: cs.webkitTextStrokeColor,
        shadow, halo, cropped,
        clipText: (() => { for (let a = el; a && a !== document.body; a = a.parentElement) { const c = getComputedStyle(a); if (c.webkitBackgroundClip === 'text' || c.backgroundClip === 'text') return true; } return false; })(),
      });
    });
    return out;
  });

  // Fonts actually used vs. loaded: a fallback font means a missing file or glyph.
  const fontInfo = await page.evaluate(() => [...document.fonts].map((f) => ({ family: f.family.replace(/["']/g, ''), status: f.status })));
  const families = [...new Set(texts.map((t) => t.family))];
  for (const fam of families) {
    const declared = fontInfo.filter((f) => f.family === fam);
    const generic = ['sans-serif', 'serif', 'system-ui', 'monospace', 'Arial', 'Helvetica'].includes(fam);
    if (!generic && declared.length && !declared.some((f) => f.status === 'loaded')) add('FAIL', `шрифт ${fam}`, 'объявлен, но не загрузился: текст рисуется запасным шрифтом');
    else if (!generic && !declared.length) add('WARN', `шрифт ${fam}`, 'нет @font-face: рендер зависит от шрифтов системы');
  }
  if (families.length > 3) add('WARN', 'гарнитуры', `${families.length} разных (${families.join(', ')}); сильный макет обычно держится на 1–2`);

  // Contrast: hide all text once, capture the bare background, then compare each
  // text colour (or its outline) with the worst 10 % of pixels behind it. Hiding
  // everything keeps neighbouring lines and nested accent words out of the sample.
  await page.evaluate(() => document.body.setAttribute('data-check-hide', ''));
  const bare = (await page.screenshot({ type: 'png' })).toString('base64');
  await page.evaluate(() => document.body.removeAttribute('data-check-hide'));
  const samples = await page.evaluate(async ({ b64, boxes }) => {
    const img = new Image(); img.src = `data:image/png;base64,${b64}`; await img.decode();
    const c = document.createElement('canvas'); c.width = img.width; c.height = img.height;
    const g = c.getContext('2d'); g.drawImage(img, 0, 0);
    return boxes.map(({ x, y, w, h }) => {
      x = Math.max(0, Math.floor(x)); y = Math.max(0, Math.floor(y));
      w = Math.max(1, Math.min(Math.ceil(w), c.width - x)); h = Math.max(1, Math.min(Math.ceil(h), c.height - y));
      if (w < 1 || h < 1 || x >= c.width || y >= c.height) return [];
      const d = g.getImageData(x, y, w, h).data, px = [];
      const step = Math.max(1, Math.floor(Math.sqrt(w * h / 4000)));
      for (let yy = 0; yy < h; yy += step) for (let xx = 0; xx < w; xx += step) { const i = (yy * w + xx) * 4; px.push([d[i], d[i + 1], d[i + 2]]); }
      return px;
    });
  }, { b64: bare, boxes: texts.map(({ x, y, w, h }) => ({ x, y, w, h })) });
  for (const [n, t] of texts.entries()) {
    const bg = samples[n];
    if (!bg.length) continue;
    if (t.clipText) { add('INFO', `«${t.text}»`, 'заливка градиентом/картинкой: контраст проверь глазами'); continue; }
    const fg = parseRgb(t.color).slice(0, 3);
    const ratios = bg.map((p) => ratio(fg, p)).sort((a, b) => a - b);
    let worst = ratios[Math.floor(ratios.length * 0.1)];
    let via = '';
    // An outline at least ~6 % of the font size, or a dense shadow, carries the edge.
    if (t.stroke >= Math.max(2, t.size * 0.06)) {
      const sc = parseRgb(t.strokeColor).slice(0, 3);
      const sr = bg.map((p) => ratio(sc, p)).sort((a, b) => a - b)[Math.floor(bg.length * 0.1)];
      const inner = ratio(fg, sc);
      if (Math.min(sr, inner) > worst) { worst = Math.min(Math.max(sr, worst), inner); via = ' (с обводкой)'; }
    } else if (t.halo && t.halo.blur >= Math.max(1, t.size * 0.03)) {
      const hc = parseRgb(t.halo.color).slice(0, 3);
      const hr = bg.map((p) => ratio(hc, p)).sort((a, b) => a - b)[Math.floor(bg.length * 0.1)];
      const inner = ratio(fg, hc);
      if (Math.min(hr, inner) > worst) { worst = Math.min(Math.max(hr, worst), inner); via = ' (с ореолом)'; }
    } else if (t.shadow && /\d+px\s+\d+px\s+(\d+)px/.test(t.shadow)) {
      via = ' (тень не учтена)';
    }
    const big = kind === 'poster' ? t.size * 0.75 >= 18 * 2 : t.size >= 24; // large text, WCAG sense
    const need = big ? 3 : 4.5, want = big ? 4.5 : 7;
    const lvl = worst < need ? 'FAIL' : worst < want ? 'WARN' : 'PASS';
    add(lvl, `контраст «${t.text}»`, `${worst.toFixed(1)}:1${via}, нужно ≥ ${need}:1, хорошо ≥ ${want}:1`);
  }

  // Size rules per format.
  for (const t of texts) {
    if (kind === 'thumb') {
      const capShare = (t.size * 0.7) / H;
      if (t.size >= 40 && capShare < 1 / 12) add('WARN', `размер «${t.text}»`, `высота прописной ≈ ${Math.round(t.size * 0.7)} px (${(capShare * 100).toFixed(0)} % кадра); главному тексту нужно ≥ 1/6 (~120 px)`);
      if (t.size < 40) add('WARN', `мелкий текст «${t.text}»`, `${Math.round(t.size)} px — в ленте 168 px это ${(t.size * 168 / W).toFixed(1)} px, не прочесть`);
    }
    if (kind === 'cover' && t.size < 44) add('WARN', `мелкий текст «${t.text}»`, `${Math.round(t.size)} px на 1080×1920 не читается в ленте`);
    if (kind === 'poster') {
      const pt = t.size * 0.75, mm = t.size / MM * 0.7;
      if (pt < 8) add('FAIL', `мелкий текст «${t.text}»`, `${pt.toFixed(1)} pt — меньше 8 pt в печати не читается`);
      else if (pt < 9) add('WARN', `мелкий текст «${t.text}»`, `${pt.toFixed(1)} pt; для деталей лучше ≥ 9 pt`);
      else add('INFO', `размер «${t.text}»`, `${pt.toFixed(0)} pt, прописная ≈ ${mm.toFixed(0)} мм, читается с ~${(mm / 25 * 3).toFixed(1)} м`);
    }
  }

  // Zones: thumbnail timestamp corner and progress bar, cover UI, poster safe area.
  const hits = (t, z) => t.x < z.x + z.w && t.x + t.w > z.x && t.y < z.y + z.h && t.y + t.h > z.y;
  const zones = [];
  // The timestamp badge has a fixed pixel size, so in the 168 px sidebar card it
  // covers ~25 % × 24 % of the frame, far more than on the big home card.
  if (kind === 'thumb') zones.push({ name: 'угол таймкода (в 168 px он закрывает ~25 % × 24 % кадра)', x: W * 0.75, y: H * 0.76, w: W * 0.25, h: H * 0.24 });
  if (kind === 'cover') {
    zones.push({ name: 'верхняя панель интерфейса', x: 0, y: 0, w: W, h: H * 0.115 });
    zones.push({ name: 'подпись и кнопки снизу', x: 0, y: H * 0.8, w: W, h: H * 0.2 });
    zones.push({ name: 'колонка кнопок справа', x: W * 0.87, y: H * 0.45, w: W * 0.13, h: H * 0.55 });
  }
  for (const z of zones) for (const t of texts) if (!t.cropped && hits(t, z)) add('FAIL', `«${t.text}»`, `попадает в зону «${z.name}»`);
  if (kind === 'poster') {
    const inset = (bleed + safeMm) * MM;
    for (const t of texts) if (!t.cropped && (t.x < inset - 1 || t.y < inset - 1 || t.x + t.w > W - inset + 1 || t.y + t.h > H - inset + 1))
      add('FAIL', `«${t.text}»`, `ближе ${safeMm} мм к обрезу (безопасное поле)`);
  }
  for (const t of texts) if (!t.cropped && (t.x < -1 || t.y < -1 || t.x + t.w > W + 1 || t.y + t.h > H + 1)) add('FAIL', `«${t.text}»`, 'выходит за край холста (если так задумано, пометь data-crop)');

  // Palette: distinct text colours (a rough proxy for visual noise).
  const colours = [...new Set(texts.map((t) => t.color))];
  if (colours.length > 4) add('WARN', 'цвета текста', `${colours.length} разных; держи 2–3`);

  await browser.close();
  const order = { FAIL: 0, WARN: 1, PASS: 2, INFO: 3 };
  results.sort((a, b) => order[a.level] - order[b.level]);
  for (const r of results) console.log(`${r.level.padEnd(4)}  ${r.what}: ${r.detail}`);
  const fails = results.filter((r) => r.level === 'FAIL').length, warns = results.filter((r) => r.level === 'WARN').length;
  console.log(`\n${fails} FAIL, ${warns} WARN, ${texts.length} текстовых блоков проверено`);
  process.exit(fails ? 1 : 0);
})().catch((e) => {
  console.error(e);
  process.exit(2);
});
