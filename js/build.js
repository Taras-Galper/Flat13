// Builds the apartment from DATA (plan metres: x east, y north)  →  world (x, height, -y).
import * as THREE from 'three';
import { DATA } from './data.js';

export const WALL_H = 2.7;
export const EYE = 1.6;

// ---------- edge collection (all ink lines of static geometry end up in one buffer)
export class EdgeBin {
  constructor() { this.pos = []; this.dashed = []; }
  addGeometry(geo, threshold = 30) {
    const e = new THREE.EdgesGeometry(geo, threshold);
    const a = e.attributes.position.array; for (let i = 0; i < a.length; i++) this.pos.push(a[i]);
    e.dispose();
  }
  seg(a, b, dashed = false) { (dashed ? this.dashed : this.pos).push(a.x, a.y, a.z, b.x, b.y, b.z); }
  boxEdges(x0, x1, y0, y1, z0, z1) { // plan box
    const g = new THREE.BoxGeometry(x1 - x0, z1 - z0, y1 - y0); g.translate((x0 + x1) / 2, (z0 + z1) / 2, -(y0 + y1) / 2);
    this.addGeometry(g, 1); g.dispose();
  }
}

// world-space UVs in metres (triplanar by face normal); textures repeat 1/size
export function metreUV(geo) {
  geo = geo.index ? geo.toNonIndexed() : geo;
  const p = geo.attributes.position, n = geo.attributes.normal;
  if (!n) geo.computeVertexNormals();
  const N = geo.attributes.normal, uv = new Float32Array(p.count * 2);
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i), ax = Math.abs(N.getX(i)), ay = Math.abs(N.getY(i)), az = Math.abs(N.getZ(i));
    let u, v;
    if (ay >= ax && ay >= az) { u = x; v = -z; } else if (ax >= az) { u = -z * Math.sign(N.getX(i) || 1); v = y; } else { u = x * Math.sign(N.getZ(i) || 1); v = y; }
    uv[i * 2] = u; uv[i * 2 + 1] = v;
  }
  geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  return geo;
}

export function planBox(x0, x1, y0, y1, z0, z1) {
  const g = new THREE.BoxGeometry(Math.max(1e-3, x1 - x0), Math.max(1e-3, z1 - z0), Math.max(1e-3, y1 - y0));
  g.translate((x0 + x1) / 2, (z0 + z1) / 2, -(y0 + y1) / 2);
  return g;
}
export function prism(poly, z0, z1, holes = []) {
  const s = new THREE.Shape(poly.map(([x, y]) => new THREE.Vector2(x, y)));
  for (const h of holes) s.holes.push(new THREE.Path(h.map(([x, y]) => new THREE.Vector2(x, y))));
  const g = new THREE.ExtrudeGeometry(s, { depth: z1 - z0, bevelEnabled: false });
  g.rotateX(-Math.PI / 2); g.translate(0, z0, 0);
  return g;
}

function mesh(geo, mat, { cast = true, receive = true, base = 0 } = {}) {
  const m = new THREE.Mesh(geo, mat); m.castShadow = cast; m.receiveShadow = receive; m.userData.base = base; return m;
}

// ---------------------------------------------------------------- build
export function buildApartment(M, edges) {
  const root = new THREE.Group(); root.name = 'apartment';
  const dyn = { doors: {}, ceilings: [], baseGated: [], lobbyLights: [] };

  // walls (traced from the hatched poché of the DXF)
  for (const w of DATA.walls) {
    const g = metreUV(prism(w.outer, 0, WALL_H, w.holes));
    root.add(mesh(g, M.wall));
    edges.addGeometry(g, 25);
  }

  // openings: sills, lintels, frames, glass, door leaves
  for (const o of DATA.openings) {
    const [x0, x1, y0, y1] = o.rect;
    const alongX = (x1 - x0) >= (y1 - y0);
    if (o.sill > 0.001) { const g = metreUV(planBox(x0, x1, y0, y1, 0, o.sill)); root.add(mesh(g, M.wall)); edges.addGeometry(g, 25); }
    if (o.head < WALL_H) { const g = metreUV(planBox(x0, x1, y0, y1, o.head, WALL_H)); const m = mesh(g, M.wall, { base: o.head }); root.add(m); dyn.baseGated.push(m); edges.addGeometry(g, 25); }
    if (o.kind === 'window' || o.kind === 'slider' || o.kind === 'glassdoor') addGlazing(root, edges, M, o, alongX);
    else addDoor(root, edges, M, o, alongX, dyn);
  }

  // floors per room
  for (const r of DATA.rooms) {
    for (const [x0, x1, y0, y1] of r.rects) {
      const top = r.floor === 'deck' ? -0.03 : 0;
      const g = metreUV(planBox(x0, x1, y0, y1, top - 0.03, top));
      const m = mesh(g, M.floor[r.floor] || M.floor.tile, { cast: false }); root.add(m);
    }
  }
  // structural slab under everything
  for (const s of DATA.slabs) {
    const g = metreUV(prism(s, -0.3, -0.031));
    root.add(mesh(g, M.slab, { cast: false }));
    // outline of the slab edge (top perimeter) — the heavy outer line of the plan
    for (let i = 0; i < s.length; i++) {
      const a = s[i], b = s[(i + 1) % s.length];
      edges.seg(new THREE.Vector3(a[0], -0.031, -a[1]), new THREE.Vector3(b[0], -0.031, -b[1]));
    }
  }
  // balcony slab nose + glass balustrade (13th floor)
  {
    const g = metreUV(planBox(-1.98, 8.07, 12.98, 13.25, -0.3, 0.0)); root.add(mesh(g, M.slab)); edges.addGeometry(g, 25);
    const up = metreUV(planBox(-1.73, 7.8, 12.98, 13.18, -0.03, 0.12)); root.add(mesh(up, M.stoneDark)); edges.addGeometry(up, 25);
    const gl = planBox(-1.73, 7.8, 13.06, 13.08, 0.12, 1.08); root.add(mesh(gl, M.glass, { cast: false }));
    const rail = planBox(-1.73, 7.8, 13.04, 13.10, 1.08, 1.12); root.add(mesh(rail, M.frame)); edges.addGeometry(rail, 25);
    for (let x = -1.73; x <= 7.8; x += 1.588) { edges.seg(new THREE.Vector3(x, 0.12, -13.07), new THREE.Vector3(x, 1.08, -13.07)); }
  }

  // lift lobby outside the front door (two lifts on the east wall, the neighbour's door to the north)
  {
    const parts = [[6.08, 10.65, 0.65, 0.90, 0, WALL_H], [10.40, 10.65, 0.65, 4.35, 0, WALL_H], [8.07, 10.65, 4.10, 4.35, 0, WALL_H]];
    for (const p of parts) { const g = metreUV(planBox(...p)); root.add(mesh(g, M.wall)); edges.addGeometry(g, 25); }
    for (const [y0, y1] of [[1.25, 2.30], [2.70, 3.75]]) {
      const lift = planBox(10.36, 10.40, y0, y1, 0, 2.15); root.add(mesh(lift, M.steel)); edges.addGeometry(lift, 25);
      const seam = planBox(10.355, 10.36, (y0 + y1) / 2 - 0.004, (y0 + y1) / 2 + 0.004, 0, 2.15); root.add(mesh(seam, M.frame));
      const fr = planBox(10.37, 10.40, y0 - 0.06, y1 + 0.06, 2.15, 2.25); root.add(mesh(fr, M.frame)); edges.addGeometry(fr, 25);
    }
    const nd = planBox(9.05, 10.05, 4.07, 4.10, 0, 2.1); root.add(mesh(metreUV(nd), M.doorEntry)); edges.addGeometry(nd, 25);
    for (const [x, y] of [[7.2, 2.5], [9.3, 2.5]]) {
      const dl = new THREE.CylinderGeometry(0.06, 0.06, 0.01, 24); dl.translate(x, WALL_H - 0.006, -y);
      const m = mesh(dl, M.downlight, { cast: false }); m.visible = false; root.add(m); dyn.ceilings.push(m);
      const L = new THREE.PointLight(0xffd6a8, 0, 7, 2); L.position.set(x, WALL_H - 0.15, -y); root.add(L); dyn.lobbyLights.push(L);
    }
  }

  // ceilings (interior rooms only), shown once the camera is inside
  const noCeil = new Set(['terrace', 'service']);
  for (const r of DATA.rooms) {
    if (noCeil.has(r.id)) continue;
    for (const [x0, x1, y0, y1] of r.rects) {
      const g = new THREE.PlaneGeometry(x1 - x0, y1 - y0); g.rotateX(Math.PI / 2); g.translate((x0 + x1) / 2, WALL_H, -(y0 + y1) / 2);
      const m = mesh(metreUV(g), M.ceiling, { cast: false }); m.visible = false; root.add(m); dyn.ceilings.push(m);
    }
  }
  return { root, dyn };
}

function addGlazing(root, edges, M, o, alongX) {
  const [x0, x1, y0, y1] = o.rect;
  const z0 = o.sill, z1 = o.head, f = 0.05;
  const L = alongX ? x1 - x0 : y1 - y0;
  const c = alongX ? (y0 + y1) / 2 : (x0 + x1) / 2;
  const box = (a0, a1, b0, b1, h0, h1, mat) => {
    const g = alongX ? planBox(a0, a1, b0, b1, h0, h1) : planBox(b0, b1, a0, a1, h0, h1);
    const m = mesh(g, mat, { cast: mat !== M.glass }); root.add(m); if (mat !== M.glass) edges.addGeometry(g, 25); return m;
  };
  const a0 = alongX ? x0 : y0, a1 = alongX ? x1 : y1;
  const panes = o.kind === 'slider' ? 2 : (L > 1.25 ? 2 : 1);
  const t = 0.06;
  if (o.kind === 'slider') {
    // two sliding panels on two tracks
    const mid = (a0 + a1) / 2, ov = 0.05;
    for (const [p0, p1, off] of [[a0, mid + ov, -0.035], [mid - ov, a1, 0.035]]) {
      box(p0, p1, c + off - t / 2, c + off + t / 2, z0, z0 + f, M.frame);
      box(p0, p1, c + off - t / 2, c + off + t / 2, z1 - f, z1, M.frame);
      box(p0, p0 + f, c + off - t / 2, c + off + t / 2, z0 + f, z1 - f, M.frame);
      box(p1 - f, p1, c + off - t / 2, c + off + t / 2, z0 + f, z1 - f, M.frame);
      box(p0 + f, p1 - f, c + off - 0.006, c + off + 0.006, z0 + f, z1 - f, M.glass);
    }
    return;
  }
  // outer frame
  box(a0, a1, c - t / 2, c + t / 2, z0, z0 + f, M.frame);
  box(a0, a1, c - t / 2, c + t / 2, z1 - f, z1, M.frame);
  box(a0, a0 + f, c - t / 2, c + t / 2, z0 + f, z1 - f, M.frame);
  box(a1 - f, a1, c - t / 2, c + t / 2, z0 + f, z1 - f, M.frame);
  if (panes === 2) box((a0 + a1) / 2 - f / 2, (a0 + a1) / 2 + f / 2, c - t / 2, c + t / 2, z0 + f, z1 - f, M.frame);
  box(a0 + f, a1 - f, c - 0.006, c + 0.006, z0 + f, z1 - f, M.glass);
  // window sill board on the inside face
  if (o.sill > 0.3) {
    const [b0, b1] = alongX ? [y0, y1] : [x0, x1];
    box(a0, a1, b0, b1, z0 - 0.02, z0, M.stoneLight);
  }
}

function addDoor(root, edges, M, o, alongX, dyn) {
  const [x0, x1, y0, y1] = o.rect;
  const a0 = alongX ? x0 : y0, a1 = alongX ? x1 : y1;
  const c = alongX ? (y0 + y1) / 2 : (x0 + x1) / 2;
  const T = alongX ? y1 - y0 : x1 - x0;
  const frameMat = o.kind === 'entry' ? M.frame : M.doorWhite;
  const box = (p0, p1, q0, q1, h0, h1, mat) => {
    const g = alongX ? planBox(p0, p1, q0, q1, h0, h1) : planBox(q0, q1, p0, p1, h0, h1);
    root.add(mesh(g, mat)); edges.addGeometry(g, 25);
  };
  const jw = 0.04;
  box(a0, a0 + jw, c - T / 2 - 0.005, c + T / 2 + 0.005, 0, o.head, frameMat);
  box(a1 - jw, a1, c - T / 2 - 0.005, c + T / 2 + 0.005, 0, o.head, frameMat);
  box(a0, a1, c - T / 2 - 0.005, c + T / 2 + 0.005, o.head - jw, o.head, frameMat);

  // leaf: built closed along the wall, pivoting at the hinge
  const [hx, hy] = o.hinge;
  const hingeA = alongX ? hx : hy;
  const dirSign = Math.abs(hingeA - a0) < Math.abs(hingeA - a1) ? 1 : -1;
  const leafW = (a1 - a0) - 2 * jw - 0.01, lt = o.kind === 'entry' ? 0.06 : 0.04, lh = o.head - jw - 0.01;
  const leafGeo = metreUV(new THREE.BoxGeometry(leafW, lh, lt));
  leafGeo.translate(leafW / 2, lh / 2, 0);
  const leafMat = o.kind === 'entry' ? M.doorEntry : M.doorWhite;
  const leaf = mesh(leafGeo, leafMat);
  const pivot = new THREE.Group();
  const hA = dirSign > 0 ? a0 + jw : a1 - jw;
  const hingePos = alongX ? new THREE.Vector3(hA, 0.005, -c) : new THREE.Vector3(c, 0.005, -hA);
  pivot.position.copy(hingePos);
  // closed orientation: leaf points along +/-x (alongX) or +/-y plan (i.e. -/+ z world)
  const closedAngle = alongX ? (dirSign > 0 ? 0 : Math.PI) : (dirSign > 0 ? Math.PI / 2 : -Math.PI / 2);
  // open orientation: leaf points along swing vector
  const [sx, sy] = o.swing; const openAngle = Math.atan2(sy, sx); // plan angle; world rotation.y = plan angle (since z=-y)
  pivot.add(leaf);
  // handle
  if (o.kind === 'entry') {
    const hg = new THREE.BoxGeometry(0.02, 0.6, 0.03); hg.translate(leafW - 0.09, 1.05, lt / 2 + 0.03);
    const hm = mesh(hg, M.frame); pivot.add(hm);
    const hg2 = hg.clone(); hg2.translate(0, 0, -lt - 0.06); pivot.add(mesh(hg2, M.frame));
  } else {
    const hg = new THREE.CylinderGeometry(0.008, 0.008, lt + 0.12, 8); hg.rotateX(Math.PI / 2); hg.translate(leafW - 0.07, 1.0, 0);
    pivot.add(mesh(hg, M.frame));
  }
  // plan angle a → world rotation.y = a (x stays x, plan y → -z)
  const setAngle = (a) => { pivot.rotation.y = a; };
  const leafEdges = new THREE.EdgesGeometry(leafGeo, 25);
  pivot.userData = { setAngle, closedAngle, openAngle, leafEdges, leafW, room: o.room };
  setAngle(o.kind === 'entry' ? closedAngle : openAngle);
  root.add(pivot);
  dyn.doors[o.room + (o.kind === 'entry' ? ':entry' : '')] = pivot;

  // swing arc (drawing convention), dashed on the floor
  const n = 24, R = leafW;
  for (let i = 0; i < n; i++) {
    const t0 = closedAngle + (normAng(openAngle - closedAngle)) * (i / n), t1 = closedAngle + (normAng(openAngle - closedAngle)) * ((i + 1) / n);
    const p0 = new THREE.Vector3(hingePos.x + Math.cos(t0) * R, 0.004, hingePos.z - Math.sin(t0) * R);
    const p1 = new THREE.Vector3(hingePos.x + Math.cos(t1) * R, 0.004, hingePos.z - Math.sin(t1) * R);
    edges.seg(p0, p1, true);
  }
}
function normAng(a) { while (a > Math.PI) a -= 2 * Math.PI; while (a < -Math.PI) a += 2 * Math.PI; return a; }
