#!/usr/bin/env node
// Record a single-file HTML animation to MP4 with Playwright + FFmpeg.
//
//   node record.cjs anim.html out.mp4 [--seconds 15] [--size 1080x1920] [--click] [--fps 30]
//
// --click   clicks the page centre once after load (for "click to play" pages)
// The page is captured in real time, so heavy WebGL scenes may drop frames;
// shrink --size or simplify the scene if the result stutters.
const { chromium } = require('playwright');
const { execFileSync } = require('node:child_process');
const { mkdtempSync, readdirSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join, resolve } = require('node:path');
const { pathToFileURL } = require('node:url');

const args = process.argv.slice(2);
const opt = (name, def) => {
  const i = args.indexOf(name);
  return i >= 0 ? args.splice(i, 2)[1] : def;
};
const flag = (name) => {
  const i = args.indexOf(name);
  return i >= 0 ? (args.splice(i, 1), true) : false;
};

const seconds = Number(opt('--seconds', '15'));
const [w, h] = opt('--size', '1080x1920').split('x').map(Number);
const fps = Number(opt('--fps', '30'));
const click = flag('--click');
const [input, output] = args;
if (!input || !output) {
  console.error('usage: node record.cjs anim.html out.mp4 [--seconds 15] [--size 1080x1920] [--click] [--fps 30]');
  process.exit(1);
}

(async () => {
const dir = mkdtempSync(join(tmpdir(), 'rec-'));
const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required', '--use-gl=angle'] });
const context = await browser.newContext({
  viewport: { width: w, height: h },
  recordVideo: { dir, size: { width: w, height: h } },
});
const page = await context.newPage();
const t0 = Date.now();
await page.goto(pathToFileURL(resolve(input)).href, { waitUntil: 'load' });
if (click) await page.mouse.click(w / 2, h / 2);
const lead = (Date.now() - t0) / 1000;
await page.waitForTimeout(seconds * 1000);
await context.close();
await browser.close();

const webm = join(dir, readdirSync(dir).find((f) => f.endsWith('.webm')));
// Drop the blank page-load lead-in, then re-encode to a widely playable MP4.
execFileSync('ffmpeg', [
  '-y', '-loglevel', 'error', '-ss', lead.toFixed(2), '-i', webm, '-t', String(seconds),
  '-vf', `fps=${fps},scale=${w}:${h}:flags=lanczos`, '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
  '-crf', '18', '-movflags', '+faststart', output,
], { stdio: 'inherit' });
rmSync(dir, { recursive: true, force: true });
console.log(`saved ${output} (${seconds}s, ${w}x${h})`);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
