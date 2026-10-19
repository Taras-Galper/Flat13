// What is outside the glass: a Haifa tower, 13 floors up. The balcony faces north over Haifa Bay,
// the open sea is to the west, the Carmel slope climbs to the east. Mid-October, 18:25 — blue hour:
// the sun has just set behind the sea (azimuth ~256°, ~4° below the horizon), the city lights are coming on.
// This matches the rendered walk, so the drawing dissolves into it without a jump in the time of day.
import * as THREE from 'three';
import { DATA } from './data.js';
import { prism } from './build.js';
import { rawColor } from './shading.js';

// world axes: +x east, -z north (plan up = north), y up
const AZ = THREE.MathUtils.degToRad(256), EL = THREE.MathUtils.degToRad(-4);
export const SUN_DIR = new THREE.Vector3(Math.sin(AZ) * Math.cos(EL), Math.sin(EL), -Math.cos(AZ) * Math.cos(EL)).normalize();
export const FLOOR_DROP = 39.0;          // 13 floors × 3 m
const GROUND = -FLOOR_DROP - 0.5;        // street level at the tower
const SEA = GROUND - 6;                  // the tower stands a few metres above the sea

// ------------------------------------------------------------------ geography (metres, around the tower)
const coastX = (z) => -170 + 70 * Math.sin(z / 700);                         // sea to the west
const bayZ = (x) => (x < 2600 ? -430 + 90 * Math.sin(x / 900) : -430 - (x - 2600) * 0.95); // bay to the north, shore turns NE
const n2 = makeNoise(7);
function land(x, z) { return x > coastX(z) && z > bayZ(x); }
function terrain(x, z) {
  if (!land(x, z)) return SEA - 8;
  const d = Math.min(x - coastX(z), z - bayZ(x));
  const beach = 6 * smooth(Math.min(d, 80) / 80);
  // Carmel: rises to the east and south-east, ridge ~450 m
  let carmel = Math.max(0, x - 380) * 0.17 + Math.max(0, z - 150) * 0.07;
  carmel += (n2(x / 900, z / 900) - 0.5) * 70 * smooth(Math.min(1, carmel / 120));
  carmel = 470 * (1 - Math.exp(-Math.max(0, carmel) / 470));
  // Galilee hills far to the north-east, beyond the bay
  const gal = z < -14000 ? (300 + 450 * n2(x / 4000, z / 4000)) * smooth(Math.min(1, (-14000 - z) / 5000)) : 0;
  return SEA + beach + carmel + gal;
}

export function buildWorld(scene) {
  const W = { uMix: { value: 0 } };
  const group = new THREE.Group(); group.name = 'world';

  // sky dome (also the "desk" behind the sheet when uMix = 0)
  const skyMat = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false, toneMapped: false,
    uniforms: { uMix: W.uMix, uSun: { value: SUN_DIR }, uDesk: { value: rawColor(0xe7e2d7) } },
    vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); vec4 p = modelViewMatrix*vec4(position,1.0); gl_Position = projectionMatrix*p; gl_Position.z = gl_Position.w*0.99999; }`,
    fragmentShader: `uniform float uMix; uniform vec3 uSun; uniform vec3 uDesk; varying vec3 vDir;
      void main(){
        vec3 d = normalize(vDir);
        float h = d.y;
        vec3 sd = normalize(uSun);
        float s = max(dot(d, sd), 0.0);
        float west = max(dot(normalize(d.xz+1e-4), normalize(sd.xz)), 0.0);
        // blue hour: deep blue overhead, a pale band at the horizon, the last warm glow over the sea in the west
        vec3 zen = vec3(0.10,0.17,0.36), hor = vec3(0.50,0.58,0.74);
        vec3 sky = mix(hor, zen, pow(clamp(h,0.0,1.0), 0.45));
        float glow = pow(west, 3.0) * exp(-max(h,0.0)*9.0);
        sky = mix(sky, vec3(0.93,0.62,0.48), glow*0.55);
        sky += vec3(0.95,0.55,0.40) * pow(s, 10.0) * 0.25 * smoothstep(-0.1,0.15,h+0.05);
        vec3 col = h > 0.0 ? sky : hor*0.55;
        gl_FragColor = vec4(mix(uDesk, col, uMix), 1.0);
      }`,
  });
  const sky = new THREE.Mesh(new THREE.SphereGeometry(4000, 48, 24), skyMat); sky.renderOrder = -10; sky.frustumCulled = false;
  scene.add(sky);

  // sea (open Mediterranean to the west, Haifa Bay to the north)
  const sea = new THREE.Mesh(new THREE.PlaneGeometry(90000, 90000).rotateX(-Math.PI / 2).translate(0, SEA, 0),
    new THREE.MeshStandardMaterial({ color: 0x1c3247, roughness: 0.12, metalness: 0.0, envMapIntensity: 0.9 }));
  group.add(sea);

  // land: a near mesh (city + Carmel) and a far mesh (the bay's far shore, Galilee hills)
  const landMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1 });
  const makeLand = (size, seg, cx, cz, drop) => {
    const g = new THREE.PlaneGeometry(size, size, seg, seg).rotateX(-Math.PI / 2); g.translate(cx, 0, cz);
    const p = g.attributes.position, c = new Float32Array(p.count * 3), C = new THREE.Color();
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), z = p.getZ(i), h = terrain(x, z) - drop;
      p.setY(i, h);
      const alt = h - SEA, nn = n2(x / 300, z / 300);
      if (alt < 8) C.setHex(0xd8c8a8);                                     // sand
      else if (alt > 140 && nn > 0.45) C.setHex(0x5d6a48);                 // Carmel pines
      else C.setHex(nn > 0.6 ? 0x8d8b70 : 0xc2b8a4);                        // dry scrub / built-up
      c.set([C.r, C.g, C.b], i * 3);
    }
    g.setAttribute('color', new THREE.BufferAttribute(c, 3)); g.computeVertexNormals();
    return new THREE.Mesh(g, landMat);
  };
  group.add(makeLand(14000, 280, 2500, 1500, 0));
  group.add(makeLand(70000, 160, 6000, -18000, 4));

  // city: white-stone blocks on the land, denser by the shore, climbing the slope
  const facade = makeFacade();
  const rnd = mulberry(1312);
  const N = 3200, geo = new THREE.BoxGeometry(1, 1, 1); geo.translate(0, 0.5, 0);
  const city = new THREE.InstancedMesh(geo, facade, N);
  const mtx = new THREE.Matrix4(), col = new THREE.Color(), q = new THREE.Quaternion(), e = new THREE.Euler();
  const tones = [0xece4d4, 0xe2d8c6, 0xf3eee4, 0xd6ccba, 0xe9dfcd, 0xc8bfae];
  let n = 0, guard = 0;
  while (n < N && guard++ < 60000) {
    const a = rnd() * Math.PI * 2, r = 55 + Math.pow(rnd(), 0.75) * 4800;
    const x = Math.cos(a) * r, z = Math.sin(a) * r;
    if (!land(x, z)) continue;
    const d = Math.min(x - coastX(z), z - bayZ(x)); if (d < 25) continue;
    const port = z < -150 && x > 150 && x < 2600;                      // the port strip along the bay
    const base = terrain(x, z) - 1;
    let h, w, dd;
    const northView = z < 40 && Math.abs(x) < 900 + Math.max(0, -z) && r < 1200;   // keep the bay view open
    if (northView && rnd() < 0.45) continue;
    if (port) { h = 5 + rnd() * 7; w = 30 + rnd() * 60; dd = 20 + rnd() * 30; }
    else if (northView) { h = 7 + rnd() * 14; w = 12 + rnd() * 18; dd = 10 + rnd() * 14; }
    else {
      const tall = rnd() < (base - SEA < 60 ? 0.12 : 0.04);
      h = tall ? 55 + rnd() * 85 : 10 + rnd() * 26; w = 14 + rnd() * 22; dd = 12 + rnd() * 18;
    }
    e.set(0, 0.35 + (rnd() - 0.5) * 0.25, 0); q.setFromEuler(e);
    mtx.compose(new THREE.Vector3(x, base, z), q, new THREE.Vector3(w, h + 2, dd));
    city.setMatrixAt(n, mtx); city.setColorAt(n, col.setHex(port ? 0xb9b4aa : tones[Math.floor(rnd() * tones.length)])); n++;
  }
  city.count = n;
  group.add(city);

  // our tower below the apartment
  for (const s of DATA.slabs) {
    const g = prism(s, GROUND, -0.31);
    const m = new THREE.Mesh(g, makeFacade(0xeee8dc)); m.receiveShadow = true; group.add(m);
  }
  scene.add(group);

  scene.fog = new THREE.FogExp2(0x58668a, 0);
  return { W, group, sky };
}

export function setWorldMix(world, scene, mix) {
  world.W.uMix.value = mix;
  world.group.visible = mix > 0.001;
  scene.fog.density = 0.000075 * mix;   // no haze on the plan (camera is ~1 km away there)
}

export function buildLights(scene) {
  // after sunset there is no direct sun: a faint warm afterglow from the west keeps the shapes readable
  const sun = new THREE.DirectionalLight(0xffb79a, 0.55);
  sun.castShadow = true;
  sun.shadow.mapSize.set(4096, 4096);
  const c = sun.shadow.camera; c.left = -13; c.right = 13; c.top = 13; c.bottom = -13; c.near = 1; c.far = 90;
  sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.025; sun.shadow.radius = 3;
  const center = new THREE.Vector3(0.6, 0, -6.6);
  sun.position.copy(center).addScaledVector(SUN_DIR, 45); sun.target.position.copy(center);
  scene.add(sun, sun.target);
  // north light: the living room faces the bright northern sky and the sunlit bay
  const hemi = new THREE.HemisphereLight(0x8ea6cf, 0x3b3a40, 0.85);
  scene.add(hemi);
  return { sun, hemi };
}

// ------------------------------------------------------------------ helpers
function makeFacade(base = 0xffffff) {
  const m = new THREE.MeshStandardMaterial({ color: base, roughness: 0.85 });
  m.onBeforeCompile = (sh) => {
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vFW;')
      .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\n vec4 fw = modelMatrix * vec4(transformed,1.0);\n #ifdef USE_INSTANCING\n fw = modelMatrix * instanceMatrix * vec4(transformed,1.0);\n #endif\n vFW = fw.xyz;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vFW;')
      .replace('#include <color_fragment>', `#include <color_fragment>
        { float fy = fract(vFW.y/3.0); float band = smoothstep(0.30,0.34,fy)*(1.0-smoothstep(0.80,0.84,fy));
          float u = fract((vFW.x + vFW.z)/2.6); float cc = smoothstep(0.18,0.22,u)*(1.0-smoothstep(0.78,0.82,u));
          vec3 fn = normalize(cross(dFdx(vFW), dFdy(vFW)));
          float win = band*cc; if (abs(fn.y) > 0.5) win = 0.0;
          diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.20,0.22,0.25), win*0.7); }`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        { // blue hour: about a third of the windows are lit, warm, a few cooler
          vec3 fn = normalize(cross(dFdx(vFW), dFdy(vFW)));
          vec2 cell = vec2(floor((vFW.x + vFW.z)/2.6), floor(vFW.y/3.0));
          float r = fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453);
          float fy = fract(vFW.y/3.0), u = fract((vFW.x + vFW.z)/2.6);
          float win = smoothstep(0.30,0.34,fy)*(1.0-smoothstep(0.80,0.84,fy)) * smoothstep(0.18,0.22,u)*(1.0-smoothstep(0.78,0.82,u));
          if (abs(fn.y) > 0.5 || vFW.y > -1.0) win = 0.0;
          vec3 warm = mix(vec3(1.0,0.66,0.36), vec3(1.0,0.85,0.66), fract(r*7.0));
          totalEmissiveRadiance += warm * win * step(0.66, r) * 2.4; }`);
  };
  return m;
}
function smooth(t) { t = Math.min(1, Math.max(0, t)); return t * t * (3 - 2 * t); }
function makeNoise(seed) {
  const r = mulberry(seed), P = new Float32Array(256 * 256); for (let i = 0; i < P.length; i++) P[i] = r();
  const at = (x, y) => P[((y & 255) << 8) | (x & 255)];
  const v = (x, y) => { const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi, u = xf * xf * (3 - 2 * xf), w = yf * yf * (3 - 2 * yf);
    const a = at(xi, yi), b = at(xi + 1, yi), c = at(xi, yi + 1), d = at(xi + 1, yi + 1); return a + (b - a) * u + (c - a) * w + (a - b - c + d) * u * w; };
  return (x, y) => v(x, y) * 0.6 + v(x * 2.1 + 5, y * 2.1) * 0.3 + v(x * 4.3, y * 4.3 + 9) * 0.1;
}
function mulberry(a) { return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
