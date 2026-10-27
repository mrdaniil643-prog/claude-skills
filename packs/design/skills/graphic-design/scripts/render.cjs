#!/usr/bin/env node
// Render an HTML or SVG design to PNG, JPG, PDF or ICO at an exact size.
//
//   node render.cjs design.html out.png --size 1280x720 [--scale 2]
//   node render.cjs design.html out.jpg --size 1280x720 --quality 88
//   node render.cjs poster.html out.pdf --mm 420x594 --bleed 3
//   node render.cjs poster.html out.png --mm 420x594 --bleed 3 --dpi 150
//   node render.cjs logo.svg icon.png --size 1024x1024 --sizes 16,32,64,512
//   node render.cjs logo.svg favicon.ico --sizes 16,32,48
//
// --size WxH        CSS pixel size of the canvas (SVG defaults to its viewBox)
// --mm WxH          trim size in millimetres; the page gets --bleed mm on every side
// --bleed N         bleed in mm (default 0); exposed to the page as CSS variables
// --dpi N           raster resolution for --mm designs (default 150; 300 for print)
// --scale N         device pixel ratio for --size designs (default 1)
// --sizes a,b,c     longest side in px: writes out-<n>.png per size, or packs them into .ico
// --transparent     keep the background transparent (PNG/ICO)
// --guides          load the page with ?guides=1 (trim, bleed, safe zones)
//
// The page sees :root { --trim-w; --trim-h; --bleed } (mm designs) and can add
// guides itself when loaded with ?guides=1. Fonts and images are awaited.
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
const flag = (name) => {
  const i = argv.indexOf(name);
  return i >= 0 ? (argv.splice(i, 1), true) : false;
};
const pair = (s) => s.split('x').map(Number);

const sizeArg = opt('--size');
const mmArg = opt('--mm');
const bleed = Number(opt('--bleed', '0'));
const dpi = Number(opt('--dpi', '150'));
const scale = Number(opt('--scale', '1'));
const quality = Number(opt('--quality', '90'));
const sizes = opt('--sizes');
const transparent = flag('--transparent');
const guides = flag('--guides');
const [input, output] = argv;
if (!input || !output) {
  console.error('usage: node render.cjs <design.html|logo.svg> <out.png|jpg|pdf|ico> [options]; see header');
  process.exit(1);
}
const ext = path.extname(output).toLowerCase();
const isSvg = path.extname(input).toLowerCase() === '.svg';
const MM_PX = 96 / 25.4; // CSS px per mm

function svgSize(file) {
  const src = fs.readFileSync(file, 'utf8');
  const vb = src.match(/viewBox\s*=\s*["']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)/);
  if (vb) return [Number(vb[1]), Number(vb[2])];
  const w = src.match(/\swidth\s*=\s*["']([\d.]+)/), h = src.match(/\sheight\s*=\s*["']([\d.]+)/);
  if (w && h) return [Number(w[1]), Number(h[1])];
  return [1024, 1024];
}

async function open(browser, w, h, dsf) {
  const page = await browser.newPage({ viewport: { width: Math.round(w), height: Math.round(h) }, deviceScaleFactor: dsf });
  const url = pathToFileURL(path.resolve(input)).href + (guides && !isSvg ? '?guides=1' : '');
  if (isSvg) {
    // Wrap so the SVG fills the canvas exactly and transparency survives. The
    // wrapper must be a file: an about:blank page may not load file:// images.
    const wrapper = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'render-')), 'wrap.html');
    fs.writeFileSync(wrapper, `<!doctype html><style>html,body{margin:0;background:transparent}
      img{display:block;width:100vw;height:100vh;object-fit:contain}</style><img src="${url}">`);
    await page.goto(pathToFileURL(wrapper).href, { waitUntil: 'load' });
  } else {
    await page.goto(url, { waitUntil: 'networkidle' });
  }
  if (mmArg) {
    const [tw, th] = pair(mmArg);
    await page.addStyleTag({ content: `:root{--trim-w:${tw}mm;--trim-h:${th}mm;--bleed:${bleed}mm}` });
  }
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].map((im) => im.complete ? 0 : new Promise((r) => { im.onload = im.onerror = r; })));
  });
  await warnOverflow(page);
  return page;
}

// Report text that leaves the canvas or overflows its own box: the usual way a
// wider font (Cyrillic, a heavier weight) quietly clips a headline.
let warned = false;
async function warnOverflow(page) {
  if (warned || isSvg) return;
  warned = true;
  const issues = await page.evaluate(() => {
    const out = [];
    const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
    for (const el of document.querySelectorAll('body *')) {
      const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
      if (!own || getComputedStyle(el).visibility === 'hidden' || el.closest('.guides')) continue;
      const range = document.createRange();
      range.selectNodeContents(el);
      const r = range.getBoundingClientRect();
      if (!r.width) continue;
      const label = el.textContent.trim().replace(/\s+/g, ' ').slice(0, 40);
      if (r.left < -1 || r.top < -1 || r.right > vw + 1 || r.bottom > vh + 1) out.push(`за краем холста: "${label}"`);
      else if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflow !== 'visible') out.push(`не влезает в блок: "${label}"`);
    }
    return out;
  });
  for (const msg of issues) console.warn(`WARN ${msg}`);
}

function ico(pngs) {
  // ICO container with PNG payloads (supported by every current browser and OS).
  const head = Buffer.alloc(6 + 16 * pngs.length);
  head.writeUInt16LE(0, 0); head.writeUInt16LE(1, 2); head.writeUInt16LE(pngs.length, 4);
  let offset = head.length;
  pngs.forEach(({ size, buf }, i) => {
    const e = 6 + i * 16;
    head.writeUInt8(size >= 256 ? 0 : size, e); head.writeUInt8(size >= 256 ? 0 : size, e + 1);
    head.writeUInt16LE(1, e + 4); head.writeUInt16LE(32, e + 6);
    head.writeUInt32LE(buf.length, e + 8); head.writeUInt32LE(offset, e + 12);
    offset += buf.length;
  });
  return Buffer.concat([head, ...pngs.map((p) => p.buf)]);
}

(async () => {
  fs.mkdirSync(path.dirname(path.resolve(output)), { recursive: true });
  const browser = await chromium.launch();
  const shot = (page, extra = {}) => page.screenshot({
    type: ext === '.jpg' || ext === '.jpeg' ? 'jpeg' : 'png',
    quality: ext === '.jpg' || ext === '.jpeg' ? quality : undefined,
    omitBackground: transparent, ...extra,
  });

  if (sizes) {
    const list = sizes.split(',').map(Number);
    const [bw, bh] = sizeArg ? pair(sizeArg) : isSvg ? svgSize(input) : [512, 512];
    const out = [];
    for (const n of list) {
      // Render at the design size, scaled so the output is exactly n px.
      const page = await open(browser, bw, bh, n / Math.max(bw, bh));
      out.push({ size: n, buf: await shot(page, { type: 'png', quality: undefined }) });
      await page.close();
    }
    if (ext === '.ico') {
      fs.writeFileSync(output, ico(out));
      console.log(`saved ${output} (${list.join(', ')} px)`);
    } else {
      const base = output.replace(/\.[^.]+$/, '');
      for (const { size, buf } of out) fs.writeFileSync(`${base}-${size}.png`, buf);
      console.log(`saved ${list.map((n) => `${base}-${n}.png`).join(', ')}`);
    }
  } else if (mmArg) {
    const [tw, th] = pair(mmArg);
    const pw = tw + 2 * bleed, ph = th + 2 * bleed;
    if (ext === '.pdf') {
      const page = await open(browser, pw * MM_PX, ph * MM_PX, 1);
      await page.pdf({ path: output, width: `${pw}mm`, height: `${ph}mm`, printBackground: true, pageRanges: '1' });
      console.log(`saved ${output} (${pw}×${ph} mm incl. ${bleed} mm bleed)`);
    } else {
      const page = await open(browser, pw * MM_PX, ph * MM_PX, dpi / 96);
      fs.writeFileSync(output, await shot(page));
      console.log(`saved ${output} (${Math.round(pw / 25.4 * dpi)}×${Math.round(ph / 25.4 * dpi)} px @ ${dpi} dpi)`);
    }
  } else {
    const [w, h] = sizeArg ? pair(sizeArg) : isSvg ? svgSize(input) : [1280, 720];
    const page = await open(browser, w, h, scale);
    if (ext === '.pdf') {
      await page.pdf({ path: output, width: `${w}px`, height: `${h}px`, printBackground: true, pageRanges: '1' });
    } else {
      fs.writeFileSync(output, await shot(page));
    }
    console.log(`saved ${output} (${w * scale}×${h * scale})`);
  }
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
