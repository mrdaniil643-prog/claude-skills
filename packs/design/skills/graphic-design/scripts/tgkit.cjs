#!/usr/bin/env node
// Telegram channel kit: avatar, sticker pack, and a preview of the channel in the app.
//
//   node tgkit.cjs avatar logo.svg out/            → avatar-640.png, avatar-1280.png, avatar-check.png
//   node tgkit.cjs stickers a.png b.svg c.png out/ [--outline 14] [--color "#fff"]
//                                                  → sticker-1.png … (512 px, transparent) + stickers-preview.png
//   node tgkit.cjs preview out/preview.png --avatar out/avatar-640.png --name "Канал" \
//        --posts post1.png,post2.png [--texts "Текст поста 1|Текст 2"] [--theme dark|light]
//
// Specs used: avatar square, shown as a circle (keep content inside the inner 80 %);
// stickers: PNG/WEBP, one side exactly 512 px, transparent, upload via @Stickers;
// post photos: Telegram shows them up to 1280 px on the long side (HD up to 2560),
// 4:5 (1280×1600) takes the most feed space, 1:1 and 16:9 work too; stories 1080×1920.
const { chromium } = require('playwright');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const argv = process.argv.slice(2);
const opt = (name, def) => { const i = argv.indexOf(name); return i >= 0 ? argv.splice(i, 2)[1] : def; };
const cmd = argv.shift();
const url = (f) => pathToFileURL(path.resolve(f)).href;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

async function shoot(html, w, h, file, { transparent = false, full = false } = {}) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  const f = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'tgkit-')), 'p.html');
  fs.writeFileSync(f, `<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:${transparent ? 'transparent' : '#fff'}}</style>${html}`);
  await page.goto(pathToFileURL(f).href, { waitUntil: 'load' });
  await page.evaluate(() => Promise.all([...document.images].map((im) => im.complete ? 0 : new Promise((r) => { im.onload = im.onerror = r; }))));
  fs.mkdirSync(path.dirname(path.resolve(file)), { recursive: true });
  await page.screenshot({ path: file, omitBackground: transparent, fullPage: full });
  await browser.close();
}

async function avatar() {
  const [src, out] = argv;
  if (!src || !out) throw new Error('usage: tgkit.cjs avatar <image|svg> <outdir> [--bg "#hex"] [--pad 0.12]');
  const bg = opt('--bg', 'transparent'), pad = Number(opt('--pad', '0.12'));
  const body = (n) => `<div style="width:${n}px;height:${n}px;background:${bg};display:flex;align-items:center;justify-content:center">
    <img src="${url(src)}" style="width:${n * (1 - 2 * pad)}px;height:${n * (1 - 2 * pad)}px;object-fit:contain"></div>`;
  for (const n of [640, 1280]) await shoot(body(n), n, n, path.join(out, `avatar-${n}.png`), { transparent: bg === 'transparent' });
  const a = url(path.join(out, 'avatar-640.png'));
  const row = (dark) => `<div style="background:${dark ? '#17212b' : '#fff'};color:${dark ? '#fff' : '#000'};padding:10px 14px;display:flex;gap:12px;align-items:center;width:360px;font:15px system-ui">
    <img src="${a}" style="width:54px;height:54px;border-radius:50%;object-fit:cover;background:#888">
    <div><b>Название канала</b><div style="opacity:.6;font-size:14px">Новый пост · 1,2K подписчиков</div></div></div>`;
  await shoot(`<div style="padding:20px;background:#e9e9ec;display:flex;gap:24px;align-items:flex-start;font:13px system-ui">
    <div><div style="position:relative;width:320px;height:320px;overflow:hidden"><img src="${a}" style="width:320px;height:320px">
      <div style="position:absolute;inset:0;border-radius:50%;box-shadow:0 0 0 999px rgba(255,0,100,.25)"></div>
      <div style="position:absolute;inset:32px;border-radius:50%;border:2px dashed #e0457b"></div></div>
      <div style="margin-top:6px;color:#666">розовое срежет круг; пунктир — безопасная зона 80 %</div></div>
    <div style="display:flex;flex-direction:column;gap:12px">${row(true)}${row(false)}
      <div style="display:flex;gap:16px;align-items:flex-end">${[160, 80, 40, 24].map((n) => `<div><img src="${a}" style="width:${n}px;height:${n}px;border-radius:50%;display:block"><div style="color:#666">${n}px</div></div>`).join('')}</div></div></div>`,
  760, 380, path.join(out, 'avatar-check.png'), { full: true });
  console.log(`saved ${out}/avatar-640.png, avatar-1280.png, avatar-check.png`);
}

async function stickers() {
  const outline = Number(opt('--outline', '14')), color = opt('--color', '#ffffff');
  const out = argv.pop(), files = argv;
  if (!files.length || !out) throw new Error('usage: tgkit.cjs stickers a.png b.svg … <outdir> [--outline px] [--color "#fff"]');
  const made = [];
  for (const [i, f] of files.entries()) {
    // 512×512 transparent, art inset by the outline, white die-cut border, soft shadow.
    const inner = 512 - 2 * (outline + 10);
    const html = `<svg width="0" height="0" style="position:absolute"><filter id="o" x="-20%" y="-20%" width="140%" height="140%">
      <feMorphology in="SourceAlpha" operator="dilate" radius="${outline}" result="fat"/><feFlood flood-color="${color}"/>
      <feComposite in2="fat" operator="in" result="ring"/><feGaussianBlur in="fat" stdDeviation="4" result="sh"/>
      <feOffset in="sh" dy="4" result="sho"/><feColorMatrix in="sho" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .35 0" result="shadow"/>
      <feMerge><feMergeNode in="shadow"/><feMergeNode in="ring"/><feMergeNode in="SourceGraphic"/></feMerge></filter></svg>
      <div style="width:512px;height:512px;display:flex;align-items:center;justify-content:center">
      <img src="${url(f)}" style="max-width:${inner}px;max-height:${inner}px;filter:url(#o)"></div>`;
    const file = path.join(out, `sticker-${i + 1}.png`);
    await shoot(html, 512, 512, file, { transparent: true });
    made.push(file);
  }
  const grid = made.map((f) => `<img src="${url(f)}" style="width:150px;height:150px">`).join('');
  await shoot(`<div style="padding:24px;background:#8fa88a url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2240%22 height=%2240%22><circle cx=%2220%22 cy=%2220%22 r=%222%22 fill=%22%23ffffff33%22/></svg>');display:flex;flex-wrap:wrap;gap:16px;width:${Math.min(4, made.length) * 166}px">${grid}</div>`,
    Math.min(4, made.length) * 166 + 48, 300, path.join(out, 'stickers-preview.png'), { full: true });
  console.log(`saved ${made.length} stickers + stickers-preview.png in ${out} (upload PNGs via @Stickers)`);
}

async function preview() {
  const out = argv[0];
  const av = opt('--avatar'), name = opt('--name', 'Канал'), theme = opt('--theme', 'dark');
  const posts = opt('--posts', '').split(',').filter(Boolean), texts = opt('--texts', '').split('|');
  if (!out || !posts.length) throw new Error('usage: tgkit.cjs preview out.png --posts a.png,b.png [--avatar a.png] [--name N] [--texts "t1|t2"] [--theme dark|light]');
  const dark = theme === 'dark';
  const C = dark ? { bg: '#0e1621', bar: '#17212b', bubble: '#182533', fg: '#f5f5f5', sub: '#7d8b99', link: '#6ab3f3' }
    : { bg: '#99b38f', bar: '#ffffff', bubble: '#ffffff', fg: '#000', sub: '#8a8a8a', link: '#168acd' };
  const avatarImg = av ? `<img src="${url(av)}" style="width:40px;height:40px;border-radius:50%;object-fit:cover">` : `<div style="width:40px;height:40px;border-radius:50%;background:#5288c1"></div>`;
  const bubbles = posts.map((p, i) => `<div style="background:${C.bubble};border-radius:14px;overflow:hidden;width:340px;margin:0 auto 10px;box-shadow:0 1px 1px rgba(0,0,0,.15)">
      <img src="${url(p)}" style="width:340px;display:block">
      ${texts[i] ? `<div style="padding:8px 12px 2px;color:${C.fg};font:15px/1.35 system-ui">${esc(texts[i])}</div>` : ''}
      <div style="padding:2px 12px 8px;color:${C.sub};font:12px system-ui;text-align:right">👁 12,4K · 19:${String(10 + i * 7).padStart(2, '0')}</div></div>`).join('');
  await shoot(`<style>html,body{background:${C.bg}!important}</style><div style="width:390px;background:${C.bg};font-family:system-ui">
    <div style="background:${C.bar};display:flex;gap:10px;align-items:center;padding:8px 12px;color:${C.fg}">${avatarImg}
      <div><b style="font-size:16px">${esc(name)}</b><div style="color:${C.sub};font-size:13px">48 312 подписчиков</div></div></div>
    <div style="padding:12px 0">${bubbles}</div></div>`, 390, 200, out, { full: true });
  console.log(`saved ${out} (${theme}, 390 px phone width)`);
}

({ avatar, stickers, preview }[cmd] || (async () => { console.error('commands: avatar | stickers | preview (see header)'); process.exit(1); }))()
  .catch((e) => { console.error(e.message || e); process.exit(1); });
