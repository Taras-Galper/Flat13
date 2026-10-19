// Shared shading: one model, two looks.
//  - the "drawing": paper surfaces, ink edges, hatched poché where the cut plane slices solids
//  - the "building": PBR materials, revealed room by room by a sweeping front
// Every material samples the same plan textures, so the drawing and the building stay one object.
import * as THREE from 'three';
import { DATA } from './data.js';

const MAX_ROOMS = 24;

// raw sRGB triplets: the drawing is mixed in after tone mapping / colour conversion
const raw = (hex) => { const c = new THREE.Color(); c.setRGB(((hex >> 16) & 255) / 255, ((hex >> 8) & 255) / 255, (hex & 255) / 255, THREE.LinearSRGBColorSpace); return c; };
export const INK = { paper: raw(0xf3efe6), ink: raw(0x1b1a18) };
export { raw as rawColor };

// uniforms shared by every patched material (objects, not copies)
export const U = {
  uCut: { value: 1.2 },
  uRooms: { value: null },
  uWallDist: { value: null },
  uGrid: { value: new THREE.Vector4(DATA.grid.x0, DATA.grid.x1, DATA.grid.y0, DATA.grid.y1) },
  uRad: { value: new Float32Array(MAX_ROOMS) },
  uOrig: { value: Array.from({ length: MAX_ROOMS }, () => new THREE.Vector2()) },
  uPaper: { value: new THREE.Color().copy(INK.paper) },
  uInk: { value: new THREE.Color().copy(INK.ink) },
  uHatch: { value: 1.0 },
  uCeilY: { value: 2.7 },
};

// room index in the id texture = position in DATA.rooms + 1 ; 0 = outside
export const ROOM_INDEX = {};
DATA.rooms.forEach((r, i) => (ROOM_INDEX[r.id] = i + 1));

export function setRoomReveal(id, radius, ox, oy) {
  const i = id === 'outside' ? 0 : ROOM_INDEX[id];
  U.uRad.value[i] = radius;
  if (ox !== undefined) U.uOrig.value[i].set(ox, oy);
}

export async function loadPlanTextures() {
  const tl = new THREE.TextureLoader();
  const [rooms, dist] = await Promise.all([
    tl.loadAsync('assets/plan_rooms.png'),
    tl.loadAsync('assets/plan_walldist.png'),
  ]);
  for (const t of [rooms]) { t.magFilter = t.minFilter = THREE.NearestFilter; t.generateMipmaps = false; }
  dist.magFilter = dist.minFilter = THREE.LinearFilter; dist.generateMipmaps = false;
  rooms.colorSpace = dist.colorSpace = THREE.NoColorSpace;
  U.uRooms.value = rooms; U.uWallDist.value = dist;
}

const COMMON = /* glsl */`
uniform float uCut;
uniform sampler2D uRooms;
uniform sampler2D uWallDist;
uniform vec4 uGrid;
uniform float uRad[${MAX_ROOMS}];
uniform vec2 uOrig[${MAX_ROOMS}];
vec2 inkUV(vec2 p){ return vec2((p.x-uGrid.x)/(uGrid.y-uGrid.x), (p.y-uGrid.z)/(uGrid.w-uGrid.z)); }
float inkHash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
float inkNoise(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);
  return mix(mix(inkHash(i),inkHash(i+vec2(1,0)),f.x), mix(inkHash(i+vec2(0,1)),inkHash(i+vec2(1,1)),f.x), f.y); }
float inkRevealAt(vec2 p){
  vec2 uv = inkUV(p);
  int id = 0;
  if (uv.x>0.0 && uv.x<1.0 && uv.y>0.0 && uv.y<1.0) id = int(texture(uRooms, uv).r*255.0+0.5);
  float r = uRad[id];
  if (r <= 0.0) return 0.0;
  if (r > 60.0) return 1.0;
  float d = distance(p, uOrig[id]) + (inkNoise(p*1.1)-0.5)*0.7 + (inkNoise(p*6.0)-0.5)*0.08;
  return smoothstep(0.0, 1.0, (r - d)/0.3);
}
`;

// ---------------------------------------------------------------- meshes
export function patchMaterial(mat, opts = {}) {
  const kind = opts.kind || 'solid'; // solid | glass | decal | ceiling
  mat.userData.ink = kind;
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, U);
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', `#include <common>\n${COMMON}\nvarying vec3 vInkW; varying vec3 vInkN; varying float vInkCap;`)
      .replace('#include <project_vertex>', /* glsl */`
        vec4 mvPosition = vec4( transformed, 1.0 );
        #ifdef USE_INSTANCING
          mvPosition = instanceMatrix * mvPosition;
          vInkN = normalize(mat3(modelMatrix) * mat3(instanceMatrix) * objectNormal);
        #else
          vInkN = normalize(mat3(modelMatrix) * objectNormal);
        #endif
        vec4 inkW = modelMatrix * mvPosition;
        vInkCap = inkW.y >= uCut - 0.0005 ? 1.0 : 0.0;
        inkW.y = min(inkW.y, uCut);
        vInkW = inkW.xyz;
        mvPosition = viewMatrix * inkW;
        gl_Position = projectionMatrix * mvPosition;`);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', `#include <common>\n${COMMON}\nvarying vec3 vInkW; varying vec3 vInkN; varying float vInkCap;
        uniform vec3 uPaper; uniform vec3 uInk; uniform float uHatch; uniform float uCeilY;
        float inkContactAO(vec3 w, vec3 n){
          vec2 p = vec2(w.x, -w.z);
          float ao = 1.0;
          if (n.y > 0.5) {               // floors, tops
            float d = texture(uWallDist, inkUV(p)).r*1.2;
            ao = mix(0.45, 1.0, smoothstep(0.0, 0.55, d)) * mix(0.8,1.0,smoothstep(0.0,0.4,w.y+0.4));
          } else if (n.y < -0.5) {      // ceilings
            float d = texture(uWallDist, inkUV(p)).r*1.2;
            ao = mix(0.5, 1.0, smoothstep(0.0, 0.7, d));
          } else {                       // walls / sides
            vec2 q = p + vec2(n.x, -n.z)*0.32;
            float d = texture(uWallDist, inkUV(q)).r*1.2;
            ao = mix(0.55, 1.0, smoothstep(0.0, 0.3, d));
            ao *= mix(0.55, 1.0, smoothstep(0.0, 0.45, w.y));
            ao *= mix(0.6, 1.0, smoothstep(0.0, 0.45, uCeilY - w.y));
          }
          return ao;
        }`)
      .replace('#include <aomap_fragment>', `#include <aomap_fragment>
        { float inkAO = inkContactAO(vInkW, normalize(vInkN));
          reflectedLight.indirectDiffuse *= inkAO; reflectedLight.indirectSpecular *= mix(0.3,1.0,inkAO); }`)
      .replace('#include <dithering_fragment>', /* glsl */`#include <dithering_fragment>
        {
          vec3 n = normalize(vInkN);
          float rev = inkRevealAt(vec2(vInkW.x + n.x*0.07, -vInkW.z - n.z*0.07));
          float cap = vInkCap * step(0.7, n.y);
          float shade = 0.955 + 0.045*dot(n, normalize(vec3(-0.35, 0.8, 0.45)));
          vec3 paper = uPaper * shade;
          if (cap > 0.5) {
            float s = (vInkW.x - vInkW.z) / 0.085;
            float f = fract(s); float d0 = min(f, 1.0-f);
            float wv = fwidth(s);
            float h = 1.0 - smoothstep(0.07, 0.07 + wv*1.4, d0);
            h *= uHatch * clamp(1.4 - wv*1.2, 0.0, 1.0);
            paper = mix(uPaper*0.965, uInk, h*0.8);
            rev = 0.0;
          }
          ${kind === 'glass' ? 'gl_FragColor = vec4(mix(paper, gl_FragColor.rgb, rev), gl_FragColor.a*rev);' :
            kind === 'decal' ? 'gl_FragColor.a *= rev;' :
            'float fw = max(fwidth(rev), 1e-4); float edge = (1.0 - smoothstep(0.0, fw*1.6, abs(rev-0.5))) * step(0.02, rev) * step(rev, 0.98);\n gl_FragColor.rgb = mix(mix(paper, gl_FragColor.rgb, rev), uInk, edge*0.75); gl_FragColor.a = mix(1.0, gl_FragColor.a, rev);'}
        }`);
  };
  mat.customProgramCacheKey = () => 'ink-' + kind;
  return mat;
}

// ---------------------------------------------------------------- lines (ink)
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';

export function makeInkLineMaterial({ width = 1.1, dashed = false, opacity = 1, color } = {}) {
  const m = new LineMaterial({ color: color || INK.ink, linewidth: width, dashed, transparent: true, depthWrite: false });
  if (dashed) { m.dashSize = 0.08; m.gapSize = 0.06; m.dashScale = 1; }
  m.uniforms = Object.assign(m.uniforms, U, { uLineOpacity: { value: opacity } });
  m.vertexShader = m.vertexShader
    .replace('uniform float linewidth;', `uniform float linewidth;\n${COMMON}\nvarying float vInkVis;`)
    .replace(/vec4 start = modelViewMatrix \* vec4\( instanceStart, 1\.0 \);\s*vec4 end = modelViewMatrix \* vec4\( instanceEnd, 1\.0 \);/, /* glsl */`
      vec4 ws = modelMatrix * vec4( instanceStart, 1.0 );
      vec4 we = modelMatrix * vec4( instanceEnd, 1.0 );
      vInkVis = (min(ws.y, we.y) > uCut + 0.001) ? 0.0 : 1.0;
      ws.y = min(ws.y, uCut); we.y = min(we.y, uCut);
      vec2 mid = vec2((ws.x+we.x)*0.5, -(ws.z+we.z)*0.5);
      float rv = max(max(inkRevealAt(mid+vec2(0.045,0.0)), inkRevealAt(mid-vec2(0.045,0.0))),
                     max(inkRevealAt(mid+vec2(0.0,0.045)), inkRevealAt(mid-vec2(0.0,0.045))));
      vInkVis *= 1.0 - rv;
      vec4 start = viewMatrix * ws;
      vec4 end = viewMatrix * we;`);
  m.fragmentShader = m.fragmentShader
    .replace('uniform float opacity;', 'uniform float opacity;\nuniform float uLineOpacity;\nvarying float vInkVis;')
    .replace('gl_FragColor = vec4( diffuseColor.rgb, alpha );', 'if (vInkVis*uLineOpacity < 0.01) discard;\ngl_FragColor = vec4( diffuseColor.rgb, alpha*vInkVis*uLineOpacity );');
  return m;
}

export const lineMaterials = new Set();
export function trackLineMaterial(m) { lineMaterials.add(m); return m; }
export function setLineResolution(w, h) { for (const m of lineMaterials) m.resolution.set(w, h); }
