// Light maps → GPU-compressed KTX2 (Basis ETC1S), so the graphics card keeps them compressed:
// about 4–8× less graphics memory than the WebP maps, which the browser unpacks to full 32-bit colour.
//   daylight maps: RGB, one layer each
//   lamp maps: ONE GREY LAYER PER LAMP GROUP. Three groups packed in R, G, B leak into each other under
//   block compression (each 4×4 block shares one colour line), so each group gets its own layer.
//   Groups that barely reach an atlas (living-room lamps on the bedroom atlas…) are left out: the page
//   uses a black layer there.
// Writes mood/lm/<atlas>_<group>.ktx2 and adds to mood/lightmaps.json, per atlas: "ktx": [day…, slot…]
// (slot = lamp file index × 3 + channel, as in the page's lamp weights) and "black": {size: file}.
// Needs: npm i ktx2-encoder sharp      Run from the project folder:  node tools/lm_ktx2.mjs [atlas…]   (one atlas per process runs them in parallel)
import { encodeToKTX2 } from 'ktx2-encoder';
import sharp from 'sharp';
import fs from 'fs';
import path from 'path';
import os from 'os';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const MOOD = path.join(ROOT, 'mood'), MAN = path.join(MOOD, 'lightmaps.json');
const DAY_Q = 255, LAMP_Q = 128;          // ETC1S quality (1–255): daylight carries colour, lamp layers are grey
const SKIP = 0.03;                        // a group is left out of an atlas where its brightest texel is under 3 % of its brightest anywhere

const args = process.argv.slice(2);
const jobs = Number(args.includes('--jobs') ? args[args.indexOf('--jobs') + 1] : 1);
const only = args.filter((a, i) => !a.startsWith('--') && args[i - 1] !== '--jobs');
const M = JSON.parse(fs.readFileSync(MAN, 'utf8'));
const lampFiles = (A) => [...new Set(Object.values(A.channels).map((c) => c.file))].sort();

async function raw(file) { const { data, info } = await sharp(path.join(MOOD, file)).removeAlpha().raw().toBuffer({ resolveWithObject: true }); return { data, w: info.width, h: info.height }; }
const UASTC = args.includes('--uastc');
async function encode(rgba, w, h, q, out) {
  // the encoder takes PNG bytes; mipmaps are made here, since compressed textures cannot make their own
  const png = await sharp(Buffer.from(rgba), { raw: { width: w, height: h, channels: 4 } }).png({ compressionLevel: 1 }).toBuffer();
  const k = await encodeToKTX2(new Uint8Array(png), {
    ...(UASTC ? { isUASTC: true, uastcLDRQualityLevel: 2, needSupercompression: true, enableRDO: true, rdoQualityLevel: Number(process.env.RDO || 4) }
              : { isUASTC: false, qualityLevel: q, compressionLevel: 4 }),
    generateMipmap: true, isPerceptual: false, isSetKTX2SRGBTransferFunc: false,
    imageDecoder: async (buf) => { const r = await sharp(buf).ensureAlpha().raw().toBuffer({ resolveWithObject: true }); return { data: new Uint8Array(r.data), width: r.info.width, height: r.info.height }; },
  });
  fs.writeFileSync(path.join(MOOD, out), k); return k.length;
}
const rgbaOf = (d, w, h, ch) => {   // ch: -1 = RGB as is, 0..2 = that channel as grey
  const o = new Uint8Array(w * h * 4);
  for (let i = 0, j = 0; i < w * h; i++, j += 3) {
    if (ch < 0) { o[4 * i] = d[j]; o[4 * i + 1] = d[j + 1]; o[4 * i + 2] = d[j + 2]; } else o[4 * i] = o[4 * i + 1] = o[4 * i + 2] = d[j + ch];
    o[4 * i + 3] = 255;
  }
  return o;
};

// the brightest each group gets in any atlas (scale × brightest 8-bit code, decoded)
const peak = {}, local = {};
for (const [a, A] of Object.entries(M.atlases)) for (const [g, c] of Object.entries(A.channels)) {
  const { data } = await raw(c.file); let mx = 0; for (let i = c.channel; i < data.length; i += 3) mx = Math.max(mx, data[i]);
  local[a + '/' + g] = c.scale * Math.pow(mx / 255, 2.2); peak[g] = Math.max(peak[g] || 0, local[a + '/' + g]);
}

const tasks = [];
const sizes = new Set();
// --uastc: UASTC (BC7 on desktops, ASTC on phones, 8 bits a texel: no coloured blocks in dim light; but ~9× the download
// of the WebP maps, 6.6 MB for the shell alone, so not used yet), the same layers
// as the WebP maps (three lamp groups to a layer), written as <file>.u.ktx2 and listed per atlas as "ktxu"
if (UASTC) for (const [a, A] of Object.entries(M.atlases)) {
  if (only.length && !only.includes(a)) continue;
  const files = [...M.day.map((g) => A.maps[g]?.file || null), ...lampFiles(A)];
  A.ktxu = files.map((f) => (f ? f.replace(/\.webp$/, '.u.ktx2') : null));
  files.forEach((f, i) => { if (f) tasks.push(async () => { const { data, w, h } = await raw(f); sizes.add(w); return [A.ktxu[i], await encode(rgbaOf(data, w, h, -1), w, h, 0, A.ktxu[i])]; }); });
}
else for (const [a, A] of Object.entries(M.atlases)) {
  if (only.length && !only.includes(a)) continue;
  const files = lampFiles(A), layers = [];
  for (const g of M.day) {
    const m = A.maps[g]; if (!m) { layers.push(null); continue; }
    const out = m.file.replace(/\.webp$/, '.ktx2'); layers.push(out);
    tasks.push(async () => { const { data, w, h } = await raw(m.file); sizes.add(w); return [out, await encode(rgbaOf(data, w, h, -1), w, h, DAY_Q, out)]; });
  }
  const slots = Array(files.length * 3).fill(null);
  for (const [g, c] of Object.entries(A.channels)) {
    const s = files.indexOf(c.file) * 3 + c.channel;
    if (!(local[a + '/' + g] >= SKIP * peak[g])) { console.log('skip', a, g, (local[a + '/' + g] / peak[g]).toFixed(3)); continue; }
    const out = `lm/${a}_${g}.ktx2`; slots[s] = out;
    tasks.push(async () => { const { data, w, h } = await raw(c.file); sizes.add(w); return [out, await encode(rgbaOf(data, w, h, c.channel), w, h, LAMP_Q, out)]; });
  }
  A.ktx = [...layers, ...slots];
}
let next = 0, total = 0;
await Promise.all(Array.from({ length: jobs }, async () => {
  while (next < tasks.length) { const t = tasks[next++]; const [f, n] = await t(); total += n; console.log(f, (n / 1024).toFixed(0) + ' KB'); }
}));
// black layers, for left-out groups (an all-zero compressed block is not black in every format)
const BK = UASTC ? 'blacku' : 'black'; M[BK] = M[BK] || {};
for (const w of sizes) { const out = `lm/black_${w}${UASTC ? '.u' : ''}.ktx2`; const z = new Uint8Array(w * w * 4); for (let i = 3; i < z.length; i += 4) z[i] = 255; total += await encode(z, w, w, 1, out); M[BK][w] = out; }
fs.writeFileSync(MAN, JSON.stringify(M, null, 1));
console.log('KTX2 total', (total / 1048576).toFixed(1), 'MB');
