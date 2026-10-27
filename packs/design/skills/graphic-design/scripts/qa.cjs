#!/usr/bin/env node
// Build a QA contact sheet that shows a design the way people will actually see it.
//
//   node qa.cjs logo logo.svg sheet.png
//   node qa.cjs thumb thumb.png sheet.png [--title "Название видео"] [--channel "Канал"]
//   node qa.cjs cover cover.png sheet.png          (Reels/Shorts/TikTok 9:16 cover)
//   node qa.cjs poster poster.png sheet.png
//
// logo   : colour on light and dark, one-colour black and white, greyscale,
//          16–128 px ladder, favicon in a browser tab, app icon on a home screen.
// thumb  : YouTube cards at real sizes (home, sidebar, mobile) in light and dark UI
//          with a timestamp badge over the corner, plus greyscale and a squint blur.
// cover  : 9:16 frame with the UI overlays, the 3:4 and 1:1 grid crops, small size.
// poster : full view, greyscale, squint blur, and how it reads from across a room.
//
// Open the sheet with the Read tool and judge it; the checklist sits in SKILL.md.
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
const title = opt('--title', 'Как я сделал это за 7 дней — полный разбор без воды');
const channel = opt('--channel', 'Мой канал');
const [kind, input, output] = argv;
if (!['logo', 'thumb', 'cover', 'poster'].includes(kind) || !input || !output) {
  console.error('usage: node qa.cjs <logo|thumb|cover|poster> <input> <sheet.png> [--title ...] [--channel ...]');
  process.exit(1);
}
const src = pathToFileURL(path.resolve(input)).href;
const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const BASE = `
*{box-sizing:border-box} body{margin:0;padding:28px;background:#e9e9ec;font:13px/1.35 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:#111}
h2{margin:26px 0 10px;font-size:15px;letter-spacing:.02em;text-transform:uppercase;color:#555}
h2:first-child{margin-top:0}
.row{display:flex;flex-wrap:wrap;gap:18px;align-items:flex-end}
.cap{font-size:11px;color:#666;margin-top:6px}
.tile{display:flex;flex-direction:column;align-items:flex-start}
img{display:block}
.grey{filter:grayscale(1)} .squint{filter:blur(3px)}
.mono-black{filter:brightness(0)} .mono-white{filter:brightness(0) invert(1)}
`;

function logoSheet() {
  const box = (bg, cls, label) => `<div class="tile"><div style="background:${bg};width:260px;height:180px;display:flex;align-items:center;justify-content:center;border-radius:6px">
    <img src="${src}" class="${cls}" style="max-width:200px;max-height:120px"></div><div class="cap">${label}</div></div>`;
  const ladder = (bg, color) => `<div class="row" style="background:${bg};padding:16px;border-radius:6px;color:${color}">${[16, 24, 32, 48, 64, 128]
    .map((n) => `<div class="tile"><img src="${src}" style="width:${n}px;height:${n}px;object-fit:contain"><div class="cap" style="color:${color}">${n}px</div></div>`).join('')}</div>`;
  return `<style>${BASE}</style>
  <h2>Цвет и фон</h2><div class="row">${box('#fff', '', 'на белом')}${box('#f3efe6', '', 'на тёплом светлом')}${box('#111', '', 'на тёмном')}${box('#2d5bff', '', 'на цветном')}</div>
  <h2>Одноцветные версии</h2><div class="row">${box('#fff', 'mono-black', 'чёрный (печать, гравировка)')}${box('#111', 'mono-white', 'белый на тёмном')}${box('#fff', 'grey', 'оттенки серого')}${box('#fff', 'squint', 'прищур: силуэт читается?')}</div>
  <h2>Мелкие размеры</h2>${ladder('#fff', '#666')}<div style="height:10px"></div>${ladder('#18181b', '#aaa')}
  <h2>В контексте</h2><div class="row">
    <div class="tile"><div style="width:300px;background:#dfe1e5;border-radius:8px 8px 0 0;padding:8px 10px 0">
      <div style="background:#fff;border-radius:8px 8px 0 0;padding:7px 10px;display:flex;gap:8px;align-items:center;width:210px">
      <img src="${src}" style="width:16px;height:16px;object-fit:contain"><span style="font-size:12px;white-space:nowrap;overflow:hidden">Главная страница</span></div></div>
      <div class="cap">фавикон 16 px во вкладке</div></div>
    <div class="tile"><div style="width:220px;height:200px;border-radius:18px;background:linear-gradient(160deg,#6b7cff,#c86bff);display:grid;grid-template-columns:repeat(3,52px);gap:18px;padding:20px;justify-content:center">
      ${[0, 1, 2, 3, 4, 5].map((i) => i === 4 ? `<div style="width:52px;height:52px;border-radius:12px;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden"><img src="${src}" style="width:40px;height:40px;object-fit:contain"></div>` : '<div style="width:52px;height:52px;border-radius:12px;background:rgba(255,255,255,.35)"></div>').join('')}
      </div><div class="cap">иконка приложения среди других</div></div>
    <div class="tile"><div style="width:120px;height:120px;border-radius:50%;background:#fff;overflow:hidden;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 1px #ccc">
      <img src="${src}" style="width:78px;height:78px;object-fit:contain"></div><div class="cap">аватар (круглая обрезка)</div></div>
  </div>`;
}

function thumbSheet() {
  const card = (w, dark, layout) => {
    const fg = dark ? '#f1f1f1' : '#0f0f0f', sub = dark ? '#aaa' : '#606060';
    const h = Math.round(w * 9 / 16);
    const img = `<div style="position:relative;width:${w}px;height:${h}px;border-radius:${w > 200 ? 12 : 8}px;overflow:hidden;flex:none">
      <img src="${src}" style="width:100%;height:100%;object-fit:cover">
      <span style="position:absolute;right:${w > 200 ? 8 : 4}px;bottom:${w > 200 ? 8 : 4}px;background:rgba(0,0,0,.8);color:#fff;font-size:${w > 200 ? 12 : 10}px;font-weight:600;padding:1px 4px;border-radius:4px">12:34</span>
      ${w > 300 ? '<div style="position:absolute;left:0;right:0;bottom:0;height:4px;background:rgba(255,255,255,.3)"><div style="width:35%;height:100%;background:#f00"></div></div>' : ''}</div>`;
    const meta = `<div style="min-width:0"><div style="color:${fg};font-weight:600;font-size:${w > 200 ? 15 : 13}px;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">${esc(title)}</div>
      <div style="color:${sub};font-size:12px;margin-top:4px">${esc(channel)}<br>48 тыс. просмотров · 2 дня назад</div></div>`;
    return layout === 'side'
      ? `<div style="display:flex;gap:8px;width:${w + 220}px">${img}${meta}</div>`
      : `<div style="width:${w}px;display:flex;flex-direction:column;gap:10px">${img}<div style="display:flex;gap:10px"><div style="width:36px;height:36px;border-radius:50%;background:${dark ? '#333' : '#ddd'};flex:none"></div>${meta}</div></div>`;
  };
  const feed = (dark) => `<div style="background:${dark ? '#0f0f0f' : '#fff'};padding:20px;border-radius:8px;display:flex;gap:28px;align-items:flex-start">
    ${card(360, dark, 'home')}${card(246, dark, 'home')}<div style="display:flex;flex-direction:column;gap:10px">${card(168, dark, 'side')}${card(168, dark, 'side')}</div></div>`;
  return `<style>${BASE}</style>
  <h2>Лента YouTube, светлая тема (главная 360 px, мобильная 246 px, рекомендации 168 px)</h2>${feed(false)}
  <h2>Тёмная тема</h2>${feed(true)}
  <h2>Проверки</h2><div class="row">
    <div class="tile"><img src="${src}" style="width:480px;height:270px;object-fit:cover"><div class="cap">оригинал 480 px; таймкод закрывает правый нижний угол</div></div>
    <div class="tile"><img src="${src}" class="grey" style="width:320px;height:180px;object-fit:cover"><div class="cap">оттенки серого: есть контраст без цвета?</div></div>
    <div class="tile"><img src="${src}" class="squint" style="width:320px;height:180px;object-fit:cover"><div class="cap">прищур: что видно за полсекунды?</div></div>
  </div>`;
}

function coverSheet() {
  const phone = (inner, label) => `<div class="tile"><div style="position:relative;width:225px;height:400px;border-radius:14px;overflow:hidden;background:#000">${inner}</div><div class="cap">${label}</div></div>`;
  const ui = `<div style="position:absolute;right:8px;bottom:70px;display:flex;flex-direction:column;gap:16px">${'<div style="width:28px;height:28px;border-radius:50%;background:rgba(255,255,255,.85)"></div>'.repeat(4)}</div>
    <div style="position:absolute;left:0;right:0;bottom:0;height:90px;background:linear-gradient(transparent,rgba(0,0,0,.7));color:#fff;padding:40px 10px 0;font-size:11px">@${esc(channel)}<br>${esc(title).slice(0, 60)}</div>
    <div style="position:absolute;left:0;right:0;top:0;height:44px;background:linear-gradient(rgba(0,0,0,.5),transparent)"></div>`;
  const full = `<img src="${src}" style="width:100%;height:100%;object-fit:cover">`;
  const crop = (ratio, label) => { const h = Math.round(150 / ratio); return `<div class="tile"><div style="width:150px;height:${h}px;overflow:hidden"><img src="${src}" style="width:150px;height:${Math.round(150 * 16 / 9)}px;margin-top:${-Math.round((150 * 16 / 9 - h) / 2)}px"></div><div class="cap">${label}</div></div>`; };
  return `<style>${BASE}</style>
  <h2>Экран телефона с интерфейсом</h2><div class="row">${phone(full + ui, 'Reels/Shorts: подписи и кнопки поверх')}${phone(full, 'чистый кадр')}
    <div class="tile"><img src="${src}" class="grey" style="width:225px;height:400px;object-fit:cover"><div class="cap">оттенки серого</div></div></div>
  <h2>Обрезки в сетке профиля</h2><div class="row">${crop(3 / 4, 'Instagram 3:4')}${crop(1, '1:1 (старая сетка, VK)')}${crop(9 / 16, 'TikTok/Shorts 9:16')}
    <div class="tile"><img src="${src}" style="width:72px;height:128px;object-fit:cover"><div class="cap">мелко в ленте</div></div></div>`;
}

function posterSheet() {
  return `<style>${BASE}</style>
  <h2>Постер</h2><div class="row">
    <div class="tile"><img src="${src}" style="height:620px"><div class="cap">целиком</div></div>
    <div class="tile"><img src="${src}" class="grey" style="height:420px"><div class="cap">оттенки серого: иерархия держится?</div></div>
    <div class="tile"><img src="${src}" class="squint" style="height:300px"><div class="cap">прищур: одно главное пятно</div></div>
    <div class="tile"><div style="width:420px;height:300px;background:linear-gradient(#8a8f98,#5e636b);display:flex;align-items:center;justify-content:center;border-radius:6px">
      <img src="${src}" style="height:110px;box-shadow:0 4px 14px rgba(0,0,0,.4)"></div><div class="cap">на стене с 5–7 метров: читается ли что, когда, где</div></div>
  </div>`;
}

const html = { logo: logoSheet, thumb: thumbSheet, cover: coverSheet, poster: posterSheet }[kind]();

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: kind === 'thumb' ? 1180 : 1240, height: 600 } });
  // Load from a file so the sheet may reference the design via file://.
  const sheet = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'qa-')), 'sheet.html');
  fs.writeFileSync(sheet, `<!doctype html><meta charset="utf-8"><body>${html}</body>`);
  await page.goto(pathToFileURL(sheet).href, { waitUntil: 'load' });
  await page.evaluate(() => Promise.all([...document.images].map((im) => im.complete ? 0 : new Promise((r) => { im.onload = im.onerror = r; }))));
  await page.screenshot({ path: output, fullPage: true });
  await browser.close();
  console.log(`saved ${output}`);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
