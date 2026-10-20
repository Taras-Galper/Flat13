// Rearranging the furniture, like a moodboard that builds the room: drag a piece in from the catalog, pick
// up any loose piece and move it (10 cm grid, it snaps to the walls and never goes through the walls,
// the built-ins or other furniture), scroll or press Turn to rotate it, Remove it, undo.
// The light stays right: a rearranged room switches its shell to an "empty room" bake, every piece in it
// gets a soft contact shadow, and a moved piece takes the brightness of the floor where it now stands.
import * as THREE from 'three';

const GRID = 0.1, SNAP = 0.15, STEP = 15;
// the names people know them by (and IKEA's article numbers)
const NAMES = [
  [/^HYLTARP/, 'HYLTARP sofa', '09489637'], [/^STOCKHOLM 2025/, 'STOCKHOLM armchair', '10594755'], [/^BESTA/, 'BESTÅ TV bench', '99188343'],
  [/^LISTERBY side/, 'LISTERBY side table', ''], [/^LISTERBY/, 'LISTERBY coffee table', ''], [/^LOHALS/, 'LOHALS rug', '00277395'],
  [/^ROSENTORP/, 'ROSENTORP bar stool', '10619930'], [/^NAMMARO easy/, 'NÄMMARÖ 3-seat sofa, outdoor', '79584363'], [/^NAMMARO armchair/, 'NÄMMARÖ armchair', '90511105'],
  [/^NAMMARO table/, 'NÄMMARÖ table, outdoor', '20510307'], [/^Low table/, 'Low table, outdoor', ''], [/^FEJKA/, 'FEJKA eucalyptus', ''], [/^potted_plant/, 'Olive tree', ''],
  [/^TONSTAD bedside/, 'TONSTAD bedside table', '80489322'], [/^TONSTAD bed/, 'TONSTAD bed', '49496674'], [/^Main bed throw/, 'Throw', ''],
  [/^LINDKNUD/, 'LINDKNUD rug', '90415689'], [/^Teen bed/, 'Teen bed 140', ''], [/^LAGKAPTEN/, 'LAGKAPTEN / ALEX desk', '69521620'],
  [/^FLINTAN/, 'FLINTAN office chair', '30492204'], [/^VILHATTEN/, 'VILHATTEN wardrobe', '70530609'], [/^KNAPPER/, 'KNAPPER mirror', '00396242'],
  [/^ARENDE/, 'ÄRENDE rug', '20576435'], [/^ALEFJALL/, 'ÄLEFJÄLL office chair', '90320224'], [/^LYCKSELE/, 'LYCKSELE sofa bed', '09387021'],
  [/^BILLY/, 'BILLY bookcase', '10508932'], [/^KURA/, 'KURA bed', '80253809'], [/^SMAGORA/, 'SMÅGÖRA wardrobe', '10460888'], [/^TROFAST/, 'TROFAST storage', '39574865'],
  [/^FLISAT table/, 'FLISAT children’s table', '50298418'], [/^FLISAT stool/, 'FLISAT stool', ''], [/^FLADIS/, 'FLADIS basket', '60322173'],
  [/^STAPPSPARV/, 'STAPPSPARV rug', '60603026'], [/^Walk runner/, 'Jute runner', ''],
];
export const nameOf = (n) => { for (const [re, name, art] of NAMES) if (re.test(n)) return { name, art }; return { name: n.replace(/ (office|teen|toddler)$/, ''), art: '' }; };
const fmtArt = (n) => (n ? `${n.slice(0, 3)}.${n.slice(3, 6)}.${n.slice(6)}` : '');

// ------------------------------------------------------------------ 2D geometry (plan metres, y north)
function corners(x, y, hx, hy, a) {
  const c = Math.cos(a), s = Math.sin(a);
  return [[-hx, -hy], [hx, -hy], [hx, hy], [-hx, hy]].map(([u, v]) => [x + c * u - s * v, y + s * u + c * v]);
}
function overlap(A, B) {   // separating axis test for two convex quads
  for (const P of [A, B]) for (let i = 0; i < 4; i++) {
    const [x1, y1] = P[i], [x2, y2] = P[(i + 1) % 4], nx = y1 - y2, ny = x2 - x1;
    let a0 = Infinity, a1 = -Infinity, b0 = Infinity, b1 = -Infinity;
    for (const [x, y] of A) { const d = nx * x + ny * y; a0 = Math.min(a0, d); a1 = Math.max(a1, d); }
    for (const [x, y] of B) { const d = nx * x + ny * y; b0 = Math.min(b0, d); b1 = Math.max(b1, d); }
    if (a1 <= b0 || b1 <= a0) return false;
  }
  return true;
}
const inRect = ([x0, x1, y0, y1], x, y, m) => x >= x0 + m && x <= x1 - m && y >= y0 + m && y <= y1 - m;

function shadowTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d');
  g.fillStyle = '#000'; g.fillRect(0, 0, 128, 128);
  g.filter = 'blur(14px)'; g.fillStyle = '#fff'; g.beginPath(); g.roundRect(26, 26, 76, 76, 14); g.fill();
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.NoColorSpace; return t;
}

export function createFurniture(ctx) {
  const { scene, camera, canvas, renderer } = ctx;
  const defs = Object.fromEntries((ctx.pieces || []).map((d) => [d.id, d]));
  const P = {};                    // id → piece at runtime
  const obstacles = [];            // built-ins standing on the floor: [quad]
  let editing = false, selected = null, drag = null, addCount = 0, anyGain = false;
  const undoStack = [];
  const SHADOW = shadowTexture();
  const accent = new THREE.Color('#b4683d');

  // ---------------------------------------------------------------- building the pieces from the loaded meshes
  function addMeshes(list) {
    const by = {};
    for (const m of list) { const id = m.userData.piece; if (id && defs[id] && defs[id].movable) (by[id] ||= []).push(m); }
    for (const [id, ms] of Object.entries(by)) {
      const d = defs[id];
      const g = new THREE.Group(); g.name = 'piece ' + id; g.position.set(d.cx, 0, -d.cy); scene.add(g); g.updateMatrixWorld(true);
      for (const m of ms) g.attach(m);
      P[id] = make(id, d, g, false);
    }
    // what stays put but stands on the floor (kitchen runs, wardrobes, floor lamps…) blocks the furniture
    const box = new THREE.Box3();
    for (const m of list) {
      const d = defs[m.userData.piece];
      if (d && d.movable) continue;
      if (/curtain|sheer|Ceiling|Floor|Wall |Slab|Glass|Frame|Sill|Lintel|Jamb|Head |Door|Balustrade|Upstand|Rail/i.test(m.userData.src || '')) continue;
      box.setFromObject(m);
      if (box.min.y > 0.06 || box.max.y < 0.15) continue;
      const x0 = box.min.x, x1 = box.max.x, y0 = -box.max.z, y1 = -box.min.z;
      if ((x1 - x0) * (y1 - y0) > 8 || x1 - x0 < 0.03 || y1 - y0 < 0.03) continue;
      obstacles.push({ q: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], src: m.userData.src });
    }
    refreshShadows();
  }
  function make(id, d, g, added, srcId = id) {
    const p = { id, def: d, srcId, group: g, x: d.cx, y: d.cy, rot: 0, room: d.room, room0: d.room, x0: d.cx, y0: d.cy, removed: false, added, ...nameOf(d.name) };
    // a soft contact shadow, shown when the room switches to its "empty" bake
    const sh = new THREE.Mesh(new THREE.PlaneGeometry(d.w + 0.32, d.d + 0.32), new THREE.MeshBasicMaterial({ color: 0x000000, alphaMap: SHADOW, transparent: true, opacity: 0.5, depthWrite: false, toneMapped: false }));
    sh.rotation.x = -Math.PI / 2; sh.position.y = 0.012; sh.renderOrder = 2; sh.raycast = () => {}; sh.visible = false;
    if (!d.rug) g.add(sh);
    // the outline of the footprint while it is selected
    const hx = d.w / 2, hy = d.d / 2;
    const ol = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([V(-hx, 0, hy), V(hx, 0, hy), V(hx, 0, -hy), V(-hx, 0, -hy)]),
      new THREE.LineBasicMaterial({ color: accent, depthTest: false, transparent: true, toneMapped: false }));
    ol.position.y = 0.02; ol.renderOrder = 11; ol.raycast = () => {}; ol.visible = false; g.add(ol);
    Object.assign(p, { shadow: sh, outline: ol });
    return p;
  }
  const V = (x, y, z) => new THREE.Vector3(x, y, z);

  // ---------------------------------------------------------------- where a piece may stand
  const quadOf = (p, x = p.x, y = p.y, rot = p.rot) => corners(x, y, p.def.w / 2 - 0.01, p.def.d / 2 - 0.01, (rot * Math.PI) / 180);
  function fits(p, x, y, rot) {
    const room = ctx.roomAt(x, y);
    if (!room || room === 'landing') return null;
    const rects = ctx.ROOMS[room];
    const q = quadOf(p, x, y, rot);
    if (!q.every(([cx, cy]) => rects.some((r) => inRect(r, cx, cy, 0.005)))) return null;
    if (!p.def.rug) {
      for (const o of Object.values(P)) if (o !== p && !o.removed && !o.def.rug && overlap(q, quadOf(o))) return null;
      for (const o of obstacles) if (overlap(q, o.q)) return null;
    }
    return room;
  }
  function snap(p, x, y, rot) {
    x = Math.round(x / GRID) * GRID; y = Math.round(y / GRID) * GRID;
    const a = (rot * Math.PI) / 180, c = Math.abs(Math.cos(a)), s = Math.abs(Math.sin(a));
    const ex = c * p.def.w / 2 + s * p.def.d / 2, ey = s * p.def.w / 2 + c * p.def.d / 2;
    const room = ctx.roomAt(x, y); if (!room) return [x, y];
    for (const [x0, x1, y0, y1] of ctx.ROOMS[room]) {     // flush against a wall when it is close
      if (Math.abs(x - ex - x0) < SNAP) x = x0 + ex + 0.006; else if (Math.abs(x + ex - x1) < SNAP) x = x1 - ex - 0.006;
      if (Math.abs(y - ey - y0) < SNAP) y = y0 + ey + 0.006; else if (Math.abs(y + ey - y1) < SNAP) y = y1 - ey - 0.006;
    }
    return [x, y];
  }
  function place(p, x, y, rot, room) {
    p.x = x; p.y = y; p.rot = ((rot % 360) + 360) % 360; p.room = room || p.room;
    p.group.position.set(x, 0, -y); p.group.rotation.y = (p.rot * Math.PI) / 180;
    p.group.updateMatrixWorld(true);
  }
  const changed = (p) => p.added || p.removed || Math.abs(p.x - p.x0) > 0.005 || Math.abs(p.y - p.y0) > 0.005 || p.rot !== 0;

  // ---------------------------------------------------------------- the light follows
  function refreshShadows() {
    const rooms = new Set();
    for (const p of Object.values(P)) if (changed(p)) { rooms.add(p.room); rooms.add(p.room0); }
    ctx.setEmptyRooms(rooms);
    for (const p of Object.values(P)) p.shadow.visible = ctx.hasEmpty && rooms.has(p.room) && !p.removed;
    refreshGains();
  }
  function refreshGains() {
    anyGain = false;
    for (const p of Object.values(P)) {
      let gain = 1;
      if (changed(p) && !p.removed) {
        const a = ctx.sampleLight(p.x, p.y), b = ctx.sampleLight(p.x0, p.y0);
        if (a > 0 && b > 0) gain = THREE.MathUtils.clamp(Math.pow(a / b, 0.8), 0.35, 2.2);
      }
      if (gain !== 1) anyGain = true;
      p.group.traverse((m) => {
        if (!m.isMesh || !m.material?.userData?.uPiece) return;
        if (gain !== 1 && !m.userData.ownMat) { m.material = ctx.cloneMat(m.material); m.userData.ownMat = true; }   // its own copy, so the brightness is its own
        if (m.userData.ownMat) m.material.userData.uPiece.value = gain;
      });
    }
  }

  // ---------------------------------------------------------------- selection panel
  const sel = document.getElementById('sel');
  function select(p) {
    if (selected) selected.outline.visible = false;
    selected = p || null;
    if (selected) selected.outline.visible = true;
    sel.classList.toggle('is-on', !!selected);
    if (selected) {
      sel.querySelector('.sel__name').textContent = selected.name;
      sel.querySelector('.sel__art').textContent = selected.art ? 'IKEA ' + fmtArt(selected.art) : '';
    }
  }
  sel.querySelector('[data-a=turn]').addEventListener('click', () => selected && turn(selected, 90));
  sel.querySelector('[data-a=remove]').addEventListener('click', () => selected && remove(selected));
  sel.querySelector('[data-a=close]').addEventListener('click', () => select(null));

  function snapshot() { undoStack.push(serialize()); if (undoStack.length > 60) undoStack.shift(); }
  function commit() { refreshShadows(); ctx.onChange(); }
  function turn(p, deg, record = true) {
    const rot = p.rot + deg;
    const [x, y] = snap(p, p.x, p.y, rot);
    const room = fits(p, x, y, rot) || fits(p, p.x, p.y, rot);
    if (!room) return false;
    if (record) snapshot();
    const ok = fits(p, x, y, rot) ? [x, y] : [p.x, p.y];
    place(p, ok[0], ok[1], rot, room); commit(); return true;
  }
  function remove(p) {
    snapshot();
    if (p.added) { scene.remove(p.group); ctx.removeMeshes(p.group); delete P[p.id]; }
    else { p.removed = true; p.group.visible = false; }
    select(null); commit();
  }

  // ---------------------------------------------------------------- pointer: pick up, move, drop
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2(), plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), hitP = new THREE.Vector3();
  function floorAt(e) {
    const r = canvas.getBoundingClientRect(); ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    return ray.ray.intersectPlane(plane, hitP) ? { x: hitP.x, y: -hitP.z } : null;
  }
  function pieceAt(e) {
    const h = ctx.pick(e.clientX, e.clientY);
    if (!h) return null;
    let o = h.object; while (o && !(o.name || '').startsWith('piece ')) o = o.parent;
    return o ? Object.values(P).find((p) => p.group === o) || null : null;
  }
  function onPointerDown(e) {
    if (!editing || e.button !== 0) return false;
    const p = pieceAt(e); if (!p) { select(null); return false; }
    const f = floorAt(e); if (!f) return false;
    select(p);
    drag = { p, dx: p.x - f.x, dy: p.y - f.y, moved: false, x0: e.clientX, y0: e.clientY, snap: serialize() };
    canvas.setPointerCapture?.(e.pointerId);
    canvas.style.cursor = 'grabbing';
    return true;
  }
  function onPointerMove(e) {
    if (!editing) return;
    if (!drag) { canvas.style.cursor = pieceAt(e) ? 'grab' : ''; return; }
    if (Math.hypot(e.clientX - drag.x0, e.clientY - drag.y0) > 4) drag.moved = true;
    const f = floorAt(e); if (!f) return;
    const p = drag.p;
    const [x, y] = snap(p, f.x + drag.dx, f.y + drag.dy, p.rot);
    for (const [cx, cy] of [[x, y], [x, p.y], [p.x, y]]) {   // slide along a wall when the straight move is blocked
      const room = fits(p, cx, cy, p.rot);
      if (room) { place(p, cx, cy, p.rot, room); break; }
    }
  }
  function onPointerUp() {
    if (!drag) return false;
    const d = drag; drag = null; canvas.style.cursor = 'grab';
    if (d.moved && d.snap !== serialize()) { undoStack.push(d.snap); commit(); }
    return true;
  }
  function onWheel(e) {
    if (!editing || !(drag || (selected && pieceAt(e) === selected))) return false;
    turn((drag || {}).p || selected, e.deltaY > 0 ? STEP : -STEP);
    return true;
  }
  function onKey(e) {
    if (!editing && !selected) return false;
    if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z')) { undo(); return true; }
    if (!selected) return false;
    if (e.key === ',' || e.key === '<') { turn(selected, -STEP); return true; }
    if (e.key === '.' || e.key === '>') { turn(selected, STEP); return true; }
    if (e.key === 'Delete' || e.key === 'Backspace') { remove(selected); return true; }
    if (e.key === 'Escape') { select(null); return true; }
    return false;
  }

  // ---------------------------------------------------------------- the catalog: one card per kind of piece
  function catalog() {
    const seen = new Map();
    for (const p of Object.values(P)) if (!p.added && !seen.has(p.name)) seen.set(p.name, p);
    return [...seen.values()].sort((a, b) => a.room0.localeCompare(b.room0) || a.name.localeCompare(b.name));
  }
  // add a copy of a piece at a floor point (it shares the geometry and the baked light of the original)
  function addCopy(srcId, x, y, rot = 0, record = true) {
    const s = P[srcId]; if (!s) return null;
    const id = 'a' + ++addCount;
    const g = s.group.clone(true); g.name = 'piece ' + id; g.visible = true; scene.add(g);
    // the clone's own shadow and outline replace the copied ones
    g.children.filter((c) => c.isLine || (c.isMesh && c.material && c.material.alphaMap === SHADOW)).forEach((c) => g.remove(c));
    const p = make(id, s.def, g, true, srcId);
    Object.assign(p, { x0: s.x0, y0: s.y0, room0: s.room0 });
    g.traverse((m) => { if (m.isMesh) m.userData.piece = id; });
    const [sx, sy] = snap(p, x, y, rot);
    const room = fits(p, sx, sy, rot);
    if (!room) { scene.remove(g); return null; }
    if (record) snapshot();
    P[id] = p; place(p, sx, sy, rot, room); ctx.addMeshes(g);
    if (record) { select(p); commit(); }
    return p;
  }
  // drag a catalog card onto the floor
  let cardDrag = null;
  function startCardDrag(e, srcId, ghost) {
    cardDrag = { srcId, ghost, x0: e.clientX, y0: e.clientY, moved: false };
    const mv = (ev) => {
      ghost.style.transform = `translate(${ev.clientX - 46}px, ${ev.clientY - 46}px)`;
      if (Math.hypot(ev.clientX - cardDrag.x0, ev.clientY - cardDrag.y0) > 6) cardDrag.moved = true;
      const over = document.elementFromPoint(ev.clientX, ev.clientY) === canvas;
      const f = over && floorAt(ev);
      ghost.classList.toggle('is-ok', !!(f && ctx.roomAt(f.x, f.y)));
    };
    const up = (ev) => {
      window.removeEventListener('pointermove', mv); ghost.remove();
      const c = cardDrag; cardDrag = null;
      if (!c.moved) { addInView(c.srcId); return; }
      if (document.elementFromPoint(ev.clientX, ev.clientY) !== canvas) return;
      const f = floorAt(ev); if (!f) return;
      if (!addCopy(c.srcId, f.x, f.y)) ctx.toast('No room for it there');
    };
    mv(e);
    window.addEventListener('pointermove', mv); window.addEventListener('pointerup', up, { once: true });
  }
  // a click on a card: put it in front of you (or in the middle of the room you are styling)
  function addInView(srcId) {
    const fwd = new THREE.Vector3(); camera.getWorldDirection(fwd);
    const tries = [];
    for (const dist of [1.6, 1.2, 2.2, 0.9, 2.8]) for (const side of [0, 0.6, -0.6, 1.2, -1.2]) {
      const px = camera.position.x + fwd.x * dist - fwd.z * side, pz = camera.position.z + fwd.z * dist + fwd.x * side;
      tries.push([px, -pz]);
    }
    for (const [x, y] of tries) if (ctx.roomAt(x, y) && addCopy(srcId, x, y)) return;
    ctx.toast('No free spot in view — drag it onto the floor instead');
  }

  // ---------------------------------------------------------------- thumbnails of the catalog, rendered from the model itself
  const thumbs = {};
  function thumbnail(p) {
    if (thumbs[p.id]) return thumbs[p.id];
    const W = 200, H = 150, dpr = renderer.getPixelRatio();
    const box = new THREE.Box3().setFromObject(p.group), c = box.getCenter(new THREE.Vector3()), r = box.getSize(new THREE.Vector3()).length() / 2;
    const cam = new THREE.PerspectiveCamera(28, W / H, 0.05, 50);
    // seen from the middle of its room, a little to the side: the side that faces the room is the lit one
    const rr = ctx.ROOMS[p.room] || ctx.ROOMS[p.room0]; const q0 = rr ? rr[0] : [c.x - 1, c.x + 1, -c.z - 1, -c.z + 1];
    const toRoom = new THREE.Vector3((q0[0] + q0[1]) / 2 - c.x, 0, -(q0[2] + q0[3]) / 2 - c.z);
    if (toRoom.lengthSq() < 0.04) toRoom.set(1, 0, 1);
    toRoom.normalize().applyAxisAngle(new THREE.Vector3(0, 1, 0), 0.45);
    const dir = new THREE.Vector3(toRoom.x, 0.6, toRoom.z).normalize();
    cam.position.copy(c).addScaledVector(dir, (r / Math.sin((28 * Math.PI) / 360)) * 1.05); cam.lookAt(c);
    const layer = 7; const prev = [], vis = p.group.visible;
    p.group.visible = true; p.shadow.layers.set(0); p.outline.layers.set(0);
    p.group.traverse((o) => { if (o === p.shadow || o === p.outline) return; prev.push([o, o.layers.mask]); o.layers.set(layer); });
    cam.layers.set(layer);
    const size = renderer.getSize(new THREE.Vector2()), cc = renderer.getClearColor(new THREE.Color()), ca = renderer.getClearAlpha();
    renderer.setScissorTest(true); renderer.setScissor(0, 0, W, H); renderer.setViewport(0, 0, W, H);
    renderer.setClearColor(0xf3efe6, 1); renderer.clear();
    ctx.withThumbLight(() => renderer.render(scene, cam));
    const out = document.createElement('canvas'); out.width = W; out.height = H;
    out.getContext('2d').drawImage(renderer.domElement, 0, renderer.domElement.height - H * dpr, W * dpr, H * dpr, 0, 0, W, H);
    renderer.setScissorTest(false); renderer.setViewport(0, 0, size.x, size.y); renderer.setClearColor(cc, ca);
    for (const [o, m] of prev) o.layers.mask = m;
    p.group.visible = vis;
    return (thumbs[p.id] = out.toDataURL('image/jpeg', 0.85));
  }

  // ---------------------------------------------------------------- the layout as text (for the link and undo)
  function serialize() {
    const out = [];
    for (const p of Object.values(P)) {
      const c = (v) => Math.round(v * 100);
      if (p.added) out.push(`+${p.srcId},${c(p.x)},${c(p.y)},${Math.round(p.rot)}`);
      else if (p.removed) out.push(`${p.id},x`);
      else if (changed(p)) out.push(`${p.id},${c(p.x)},${c(p.y)},${Math.round(p.rot)}`);
    }
    return out.join(';');
  }
  function resetAll() {
    for (const p of Object.values(P)) {
      if (p.added) { scene.remove(p.group); ctx.removeMeshes(p.group); delete P[p.id]; continue; }
      p.removed = false; p.group.visible = true; place(p, p.x0, p.y0, 0, p.room0);
    }
  }
  function load(str, record = false) {
    if (record) snapshot();
    resetAll(); select(null);
    for (const part of (str || '').split(';')) {
      if (!part) continue;
      const f = part.split(',');
      if (f[0][0] === '+') { addCopy(f[0].slice(1), +f[1] / 100, +f[2] / 100, +f[3] || 0, false); continue; }
      const p = P[f[0]]; if (!p) continue;
      if (f[1] === 'x') { p.removed = true; p.group.visible = false; continue; }
      place(p, +f[1] / 100, +f[2] / 100, +f[3] || 0, ctx.roomAt(+f[1] / 100, +f[2] / 100) || p.room);
    }
    refreshShadows();
  }
  function undo() { if (!undoStack.length) return; load(undoStack.pop()); ctx.onChange(); }
  function reset() { snapshot(); load(''); ctx.onChange(); }

  return {
    addMeshes, onPointerDown, onPointerMove, onPointerUp, onWheel, onKey, catalog, thumbnail, startCardDrag, addInView,
    serialize, load, undo, reset, refreshGains, select,
    get editing() { return editing; }, set editing(v) { editing = v; if (!v) { select(null); canvas.style.cursor = ''; } },
    get dragging() { return !!drag || !!cardDrag; }, get count() { return Object.keys(P).length; },
    get changedCount() { return Object.values(P).filter(changed).length; }, pieces: P, fmtArt,
  };
}
