// Before a deploy: does the page still work on ordinary graphics cards?   node tools/check.mjs
//  1. every file the page loads carries the same release version (index.html, js/mood.js imports), and the version
//     was raised if the page or its data changed since the last push (or a browser mixes cached old files with new)
//  2. the page loads in headless Chromium (software GL), with furniture moved, a door shut and curtains drawn,
//     so every kind of shader gets built; no errors in the console
//  3. every shader stays within what most phones and Chrome on Windows allow: 16 textures, and a modest number of
//     uniform vectors (the floor once failed on Taras's card with 19 textures, and was simply not drawn)
// Needs: npm i playwright (Chromium: npx playwright install chromium, or PLAYWRIGHT_CHROMIUM=path to a chrome)
import http from 'http';
import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const MAX_TEX = 16, MAX_VEC = 224;          // WebGL 2 minimums: texture units, fragment uniform vectors
let failed = false;
const fail = (m) => { failed = true; console.log('FAIL  ' + m); };
const ok = (m) => console.log('ok    ' + m);
const warn = (m) => console.log('warn  ' + m);

// ---------------------------------------------------------------- 1. versions
const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8'), js = fs.readFileSync(path.join(ROOT, 'js/mood.js'), 'utf8');
const vs = [...html.matchAll(/\?v=(\d+)/g), ...js.matchAll(/from '\.\/[\w.]+\?v=(\d+)'/g)].map((m) => m[1]);
const ver = vs[0];
if (!vs.length) fail('no ?v= version stamps found');
else if (new Set(vs).size > 1) fail('version stamps differ: ' + [...new Set(vs)].join(', ') + ' (index.html and the imports in js/mood.js must match)');
else ok(`version ${ver} everywhere (${vs.length} stamps)`);
try {
  const remote = execSync('git show origin/main:index.html', { cwd: ROOT, stdio: ['ignore', 'pipe', 'ignore'] }).toString();
  const rv = (remote.match(/mood\.js\?v=(\d+)/) || [])[1];
  const changed = execSync('git diff --name-only origin/main -- index.html js css mood design', { cwd: ROOT }).toString().trim();
  if (changed && rv === ver) fail(`the page changed since the last push but the version is still ${ver}: raise it (${changed.split('\n').length} files changed)`);
  else ok(changed ? `version raised from ${rv} to ${ver}` : 'nothing changed since the last push');
} catch (e) { warn('could not compare with origin/main: ' + e.message.split('\n')[0]); }

// ---------------------------------------------------------------- 2. load the page
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.gltf': 'model/gltf+json', '.bin': 'application/octet-stream', '.webp': 'image/webp', '.ktx2': 'image/ktx2', '.wasm': 'application/wasm', '.woff2': 'font/woff2', '.jpg': 'image/jpeg', '.png': 'image/png', '.svg': 'image/svg+xml' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]).replace(/\/$/, '/index.html'));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(res);
}).listen(0);
const port = server.address().port;
const { chromium } = await import('playwright');
const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM || undefined, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 640, height: 400 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error' && !/favicon/.test(m.location()?.url || '') && !/status of 404/.test(m.text())) errors.push(m.text().slice(0, 300)); });
page.on('pageerror', (e) => errors.push('page error: ' + e.message));
page.on('response', (r) => { if (r.status() >= 400 && !/favicon/.test(r.url())) errors.push(`${r.status()} ${r.url().replace(/^.*?:\d+\//, '')}`); });
await page.goto(`http://localhost:${port}/?noenv#e=5.6%2C7.2%2C-0.6%2C0.0%2C-0.6&t=1.00&s=evening`);
const t0 = Date.now();
try {
  await page.waitForFunction(() => window.__mood && Object.keys(window.__mood.parts || {}).length >= 3 && window.__mood.renderer.info.render.frame > 5, null, { timeout: 420000 });
  ok(`page loaded in ${Math.round((Date.now() - t0) / 1000)} s (software GL)`);
  // every kind of shader: a moved piece (the empty-room light), a shut door, drawn sheers
  await page.evaluate(() => {
    const M = window.__mood; const ps = Object.values(M.FURN.pieces); const q = ps.find((p) => !p.def.rug) || ps[0];
    M.FURN.load(`${q.id},${Math.round(q.x0 * 100 + 10)},${Math.round(q.y0 * 100)},0`);
    if (M.OPEN.doors[0]) M.OPEN.click({ object: M.OPEN.doors[0].mesh });
    if (M.OPEN.windows[0]) M.OPEN.click({ object: M.OPEN.windows[0].sheers[0].mesh });
  });
  await page.waitForTimeout(90000);
} catch (e) { fail('the page did not finish loading: ' + e.message.split('\n')[0]); }

// ---------------------------------------------------------------- 3. the shaders
const report = await page.evaluate(([MAX_TEX, MAX_VEC]) => {
  const r = window.__mood.renderer, gl = r.getContext();
  const SAMPLERS = [gl.SAMPLER_2D, gl.SAMPLER_2D_ARRAY, gl.SAMPLER_CUBE, gl.SAMPLER_3D, gl.SAMPLER_2D_SHADOW, gl.INT_SAMPLER_2D, gl.UNSIGNED_INT_SAMPLER_2D];
  const SLOTS = { [gl.FLOAT_MAT2]: 2, [gl.FLOAT_MAT3]: 3, [gl.FLOAT_MAT4]: 4 };
  const out = { programs: r.info.programs.length, broken: [], tex: 0, texName: '', vec: 0, vecName: '', over: [], lost: gl.isContextLost() };
  for (const pi of r.info.programs) {
    const p = pi.program;
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) { out.broken.push(pi.name); continue; }
    const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS); let tex = 0, vec = 0;
    for (let i = 0; i < n; i++) { const u = gl.getActiveUniform(p, i); if (SAMPLERS.includes(u.type)) tex += u.size; else vec += (SLOTS[u.type] || 1) * u.size; }
    if (tex > out.tex) { out.tex = tex; out.texName = pi.name; }
    if (vec > out.vec) { out.vec = vec; out.vecName = pi.name; }
    if (tex > MAX_TEX) out.over.push(`${pi.name}: ${tex} textures`);
  }
  return out;
}, [MAX_TEX, MAX_VEC]);
if (report.lost) fail('the graphics context was lost');
if (report.broken.length) fail('shaders that did not link: ' + report.broken.join(', '));
if (report.over.length) fail(`shaders over ${MAX_TEX} textures: ` + report.over.join('; '));
else ok(`${report.programs} shaders, at most ${report.tex} textures (${report.texName || '-'})`);
// vertex and fragment uniforms counted together: an upper bound for the fragment shader
if (report.vec > MAX_VEC) warn(`up to ${report.vec} uniform vectors (vertex + fragment) in ${report.vecName}: phones allow ${MAX_VEC} per stage`);
else ok(`at most ${report.vec} uniform vectors (${report.vecName})`);
if (errors.length) fail('console: ' + [...new Set(errors)].slice(0, 6).join(' | ')); else ok('no errors in the console');

await browser.close(); server.close();
console.log(failed ? '\nNOT READY to deploy' : '\nready to deploy');
process.exit(failed ? 1 : 0);
