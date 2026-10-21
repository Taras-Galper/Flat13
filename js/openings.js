// Doors and curtains you can click: a door swings shut on its hinge (and stops you walking through), the sheers
// draw across the window or gather back to the side. The light is baked with every door open and the curtains as
// built, so the page dims the daylight of a room by how much of its glass the sheers cover.
import * as THREE from 'three';

const JAMB = 0.04, STACK = 0.36, DUR = 0.9;
const SHEER = 0.45;            // the share of daylight a drawn linen sheer holds back
const ease = (k) => (k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2);

export function createOpenings(ctx) {
  const { scene, DATA } = ctx;
  const doors = [], curtains = [], windows = [], anims = [];
  const box = new THREE.Box3();

  // ---------------------------------------------------------------- doors: a pivot at the hinge, like build_scene.py made them
  function addDoor(mesh) {
    const room = mesh.userData.src.replace(/^Door leaf /, '');
    const o = DATA.openings.find((q) => (q.kind === 'door' || q.kind === 'entry') && q.room === room && q.hinge);
    if (!o) return;
    const [x0, x1, y0, y1] = o.rect, alongX = x1 - x0 > y1 - y0;
    const a0 = alongX ? x0 : y0, a1 = alongX ? x1 : y1, c = alongX ? (y0 + y1) / 2 : (x0 + x1) / 2;
    const hA0 = alongX ? o.hinge[0] : o.hinge[1], sign = Math.abs(hA0 - a0) < Math.abs(hA0 - a1) ? 1 : -1;
    const hA = sign > 0 ? a0 + JAMB : a1 - JAMB, hp = alongX ? [hA, c] : [c, hA];
    const shut = alongX ? [sign, 0] : [0, sign];
    let d = Math.atan2(shut[1], shut[0]) - Math.atan2(o.swing[1], o.swing[0]);
    d = Math.atan2(Math.sin(d), Math.cos(d));
    const g = new THREE.Group(); g.name = 'door ' + room; g.position.set(hp[0], 0, -hp[1]); scene.add(g); g.updateMatrixWorld(true);
    g.attach(mesh);
    // its own material: shut, each face takes the light of the floor in front of it (the bake has it open)
    const base = mesh.material, key = base.customProgramCacheKey;
    mesh.material = ctx.cloneMat(base); mesh.material.customProgramCacheKey = () => key.call(base) + 'D';
    Object.assign(mesh.material.userData, { uDoor: { value: new THREE.Vector4(o.swing[0], o.swing[1], 0, 0) }, uDoorT: { value: 0 } });
    // a patch of floor on each side: across the doorway, 30 cm to 1.1 m out
    const patch = (sg) => { const pts = []; for (const f of [0.2, 0.5, 0.8]) for (const out of [0.3, 0.55, 0.8, 1.1]) {
      const a = a0 + (a1 - a0) * f; const p = alongX ? [a, c] : [c, a]; pts.push([p[0] + sg * o.swing[0] * out, p[1] + sg * o.swing[1] * out]); } return pts; };
    const door = { kind: 'door', id: room, mesh, group: g, shutAngle: d, open: true, t: 0, sideA: patch(1), sideB: patch(-1) };
    mesh.userData.opening = door; doors.push(door);
  }

  // ---------------------------------------------------------------- curtains: each sheer belongs to a window; it scales along the rail from its outer edge
  function addCurtain(mesh) {
    box.setFromObject(mesh);
    const cx = (box.min.x + box.max.x) / 2, cy = -(box.min.z + box.max.z) / 2, room = mesh.userData.room || '';
    let best = null, bd = 1e9;
    for (const o of DATA.openings) {
      if (o.kind !== 'window' && o.kind !== 'slider') continue;
      const [x0, x1, y0, y1] = o.rect;
      const dx = Math.max(x0 - cx, 0, cx - x1), dy = Math.max(y0 - cy, 0, cy - y1), dist = Math.hypot(dx, dy) - (o.room === room ? 0.3 : 0);
      if (dist < bd) { bd = dist; best = o; }
    }
    if (!best || bd > 1.2) return;
    let w = windows.find((q) => q.o === best);
    if (!w) {
      const [x0, x1, y0, y1] = best.rect, alongX = x1 - x0 > y1 - y0;
      w = { o: best, alongX, a0: alongX ? x0 : y0, a1: alongX ? x1 : y1, room: best.room, sheers: [] };
      windows.push(w);
    }
    const c0 = w.alongX ? box.min.x : -box.max.z, c1 = w.alongX ? box.max.x : -box.min.z;
    const sh = { kind: 'curtain', mesh, w, c0, c1 };
    mesh.userData.opening = sh; w.sheers.push(sh); curtains.push(sh);
  }
  function settleWindows() {
    windows.filter((w) => !w.id).forEach((w) => {
      w.id = String(windows.indexOf(w));
      const mid = (w.a0 + w.a1) / 2, span = w.a1 - w.a0;
      // drawn: a single sheer across most of the glass, or a pair whose inner edges meet in the middle
      const drawn = (s) => (w.sheers.length > 1 ? Math.min(Math.abs(s.c0 - mid), Math.abs(s.c1 - mid)) < 0.12 : s.c1 - s.c0 > 0.7 * span);
      w.open = !w.sheers.every(drawn);                       // as built: gathered at the sides (or one drawn sheer)
      for (const s of w.sheers) {
        const left = (s.c0 + s.c1) / 2 < mid, pair = w.sheers.length > 1;
        const outer = left ? s.c0 : s.c1;                    // the edge that stays put
        const openW = drawn(s) ? STACK : s.c1 - s.c0;
        const closedW = pair ? Math.abs(mid - outer) + 0.04 : Math.max(s.c1 - s.c0, Math.abs((left ? w.a1 : w.a0) - outer));
        const builtW = s.c1 - s.c0;
        // a pivot at the outer edge, on the rail
        box.setFromObject(s.mesh);
        const px = w.alongX ? outer : (box.min.x + box.max.x) / 2, py = w.alongX ? -(box.min.z + box.max.z) / 2 : outer;
        const g = new THREE.Group(); g.name = 'curtain'; g.position.set(px, 0, -py); scene.add(g); g.updateMatrixWorld(true);
        g.attach(s.mesh);
        Object.assign(s, { group: g, kOpen: openW / builtW, kClosed: closedW / builtW, k: 1 });
      }
      w.t = w.open ? 0 : 1;
      for (const s of w.sheers) { s.k = w.open ? s.kOpen : s.kClosed; scaleSheer(s); }
    });
  }
  const scaleSheer = (s) => { if (s.w.alongX) s.group.scale.x = s.k; else s.group.scale.z = s.k; s.group.updateMatrixWorld(true); };

  function addMeshes(list) {
    for (const m of list) {
      const src = m.userData.src || '';
      if (/^Door leaf /.test(src) && !m.userData.opening) addDoor(m);
      else if (/curtain/i.test(src) && !/pocket/i.test(src) && /sheer/i.test(m.material?.name || '') && !m.userData.opening) addCurtain(m);
    }
    settleWindows();
    dayK();
  }

  // ---------------------------------------------------------------- toggling, animated
  function toggleDoor(door, open = !door.open, now = false) {
    if (door.open === open) return;
    door.open = open; animate(door, 'door', open ? 0 : 1, now);
  }
  function toggleWindow(w, open = !w.open, now = false) {
    if (w.open === open) return;
    w.open = open; animate(w, 'window', open ? 0 : 1, now); dayK();
  }
  function animate(obj, kind, to, now) {
    for (let i = anims.length - 1; i >= 0; i--) if (anims[i].obj === obj) anims.splice(i, 1);
    anims.push({ obj, kind, from: obj.t, to, t0: performance.now(), dur: now ? 0 : DUR * 1000 });
    step(performance.now());
  }
  function apply(obj, kind, t) {
    obj.t = t;
    if (kind === 'door') { obj.group.rotation.y = obj.shutAngle * t; obj.group.updateMatrixWorld(true); obj.mesh.material.userData.uDoorT.value = t; }
    else for (const s of obj.sheers) { s.k = s.kOpen + (s.kClosed - s.kOpen) * t; scaleSheer(s); }
  }
  function step(now) {
    for (let i = anims.length - 1; i >= 0; i--) {
      const a = anims[i], k = a.dur ? Math.min(1, (now - a.t0) / a.dur) : 1;
      apply(a.obj, a.kind, a.from + (a.to - a.from) * ease(k));
      if (k >= 1) anims.splice(i, 1);
    }
    return anims.length > 0;
  }

  // ---------------------------------------------------------------- daylight: per room, by how much of its glass is covered
  function dayK() {
    const share = {};
    for (const w of windows) {
      const width = w.a1 - w.a0, cov = w.open ? 0 : 1;
      const s = (share[w.room] ||= { all: 0, cov: 0 }); s.all += width; s.cov += width * cov;
    }
    const k = {}; for (const [r, s] of Object.entries(share)) k[r] = 1 - SHEER * (s.all ? s.cov / s.all : 0);
    ctx.setDayK(k);
  }

  // the light on each side of the doors, from the bake of the floor (again whenever the lighting changes)
  function refreshLight() {
    const light = (pts) => { const v = pts.map((p) => ctx.floorLight(...p)).sort((a, b) => a - b); return v[Math.floor(v.length * 0.75)]; };   // the brighter end: not the floor under a bed
    for (const d of doors) { const u = d.mesh.material.userData.uDoor.value; u.z = 0.8 * light(d.sideA); u.w = 0.8 * light(d.sideB); }
  }

  // ---------------------------------------------------------------- what the page asks
  const openingOf = (o) => { for (; o; o = o.parent) if (o.userData && o.userData.opening) return o.userData.opening; return null; };
  function click(hit) {
    const op = hit && openingOf(hit.object); if (!op) return false;
    if (op.kind === 'door') toggleDoor(op); else toggleWindow(op.w);
    ctx.onChange(); return true;
  }
  const serialize = () => [...doors.filter((d) => !d.open).map((d) => 'd' + d.id), ...windows.filter((w) => w.open !== w.built).map((w) => 'c' + w.id)].join('.');
  function load(s) {
    const set = new Set((s || '').split('.').filter(Boolean));
    for (const d of doors) toggleDoor(d, !set.has('d' + d.id), true);
    for (const w of windows) toggleWindow(w, set.has('c' + w.id) ? !w.built : w.built, true);
  }
  // the built state of each window, for the link
  const markBuilt = () => windows.forEach((w) => { if (w.built === undefined) w.built = w.open; });

  return {
    addMeshes: (l) => { addMeshes(l); markBuilt(); },
    click, step, serialize, load, doors, windows, refreshLight,
    isOpening: (hit) => !!(hit && openingOf(hit.object)),
    meshes: () => [...doors.map((d) => d.mesh), ...curtains.map((c) => c.mesh)],
    get busy() { return anims.length > 0; },
  };
}
