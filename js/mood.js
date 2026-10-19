// "Make it yours": the whole flat as a live 3D model with Cycles-baked light.
// Light is baked once per group (three times of day and the lighting plan's lamp groups) and re-mixed
// here, so any time of day and any lighting scene can be shown live. The flat comes in three parts —
// the shell, the living room and the bedrooms — loaded one after another. Walk around at eye level,
// style every room with samples or a ready-made mood, and share the result as a link.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { buildWorld, setWorldMix } from './world.js';
import { DATA } from './data.js';

const Q = new URLSearchParams(location.search);
const BASE = Q.get('base') || 'mood/';
const NOENV = Q.has('noenv');          // tests on software GL skip the reflection probe
const FLAT = Q.has('flat') ? 0.35 : 0;  // debug: flat light when a part has no lightmaps yet
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const P = (px, py, h) => V(px, h, -py);                     // plan metres → world
const EYE = 1.6;

// ------------------------------------------------------------------ rooms and the areas you style
const ROOMS = Object.fromEntries(DATA.rooms.map((r) => [r.id, r.rects]));
const AREAS = {
  living: { he: 'סלון, מבואה ומטבח', en: 'Living room, entry & kitchen', rooms: ['living', 'entry', 'kitchen', 'corridor', 'terrace'], floor: 'tile' },
  master: { he: 'חדר ההורים', en: 'Main bedroom', rooms: ['master', 'passage'], floor: 'oak' },
  teen: { he: 'חדר הנערה · ממ״ד', en: 'Teen room · safe room', rooms: ['mamad'], floor: 'oak' },
  office: { he: 'חדר עבודה ומשחק', en: 'Office & games', rooms: ['bed3'], floor: 'oak' },
  toddler: { he: 'חדר הקטנה', en: 'Toddler room', rooms: ['bed4'], floor: 'oak' },
  baths: { he: 'חדרי רחצה', en: 'Bathrooms & laundry', rooms: ['wc', 'bath', 'laundry', 'ensuite', 'service'], floor: 'tile' },
};
const AREA_KEYS = Object.keys(AREAS);
const ROOM_AREA = {}; for (const [a, d] of Object.entries(AREAS)) for (const r of d.rooms) ROOM_AREA[r] = a;
const inRect = ([x0, x1, y0, y1], x, y, m = 0) => x >= x0 - m && x <= x1 + m && y >= y0 - m && y <= y1 + m;
function roomAt(px, py, m = 0) { for (const r of DATA.rooms) if (r.id && r.id !== 'landing' && r.rects.some((q) => inRect(q, px, py, m))) return r.id; return ''; }
// every room rectangle with its area index, for the wall-paint lookup in the shader
const RECTS = []; for (const r of DATA.rooms) if (ROOM_AREA[r.id]) for (const q of r.rects) RECTS.push({ q, a: AREA_KEYS.indexOf(ROOM_AREA[r.id]) });

// ------------------------------------------------------------------ the lighting plan (design/lighting.json)
let SCENES = { off: { he: 'כבוי', en: 'Off', levels: {} } };
let CCT = {};
const frac = (lvl) => (lvl > 0 ? Math.pow(lvl / 100, 1.6) : 0);

// ------------------------------------------------------------------ time of day: weights of the baked daylight maps
const TIMES = [
  { key: 'morning', he: 'בוקר', en: 'Morning', clock: '07:36', day: [1, 0, 0], ev: 0.9, sky: [[0.62, 0.74, 0.88], [0.92, 0.86, 0.78]], lamps: 'off' },
  { key: 'midday', he: 'צהריים', en: 'Midday', clock: '12:48', day: [0, 1, 0], ev: 0.7, sky: [[0.42, 0.62, 0.90], [0.86, 0.90, 0.95]], lamps: 'off' },
  { key: 'evening', he: 'ערב', en: 'Evening', clock: '18:25', day: [0, 0, 1], ev: 2.6, sky: [[0.10, 0.17, 0.36], [0.50, 0.58, 0.74]], lamps: 'evening' },
  { key: 'night', he: 'לילה', en: 'Night', clock: '22:12', day: [0, 0, 0.07], ev: 3.0, sky: [[0.02, 0.03, 0.07], [0.10, 0.12, 0.18]], lamps: 'evening' },
];

// ------------------------------------------------------------------ samples
const T = (name) => ({ map: `assets/tex/${name}/diff.jpg`, nor: `assets/tex/${name}/nor.jpg`, rough: `assets/tex/${name}/rough.jpg` });
const SAMPLES = {
  floor: { he: 'רצפה', en: 'Floor', items: [
    { id: 'asbuilt', he: 'כמו בתכנון', en: 'As designed', swatch: '#E9E1D2', original: true },
    { id: 'oak', he: 'פרקט אלון', en: 'White oak planks', tex: T('laminate_floor_02'), size: 1.7, swatch: 'assets/tex/laminate_floor_02/diff.jpg' },
    { id: 'concrete', he: 'מיקרוטופינג', en: 'Microcement', tex: T('smooth_concrete_floor'), size: 2.0, swatch: 'assets/tex/smooth_concrete_floor/diff.jpg' },
    { id: 'marble', he: 'שיש', en: 'Marble', tex: T('marble_01'), size: 1.5, swatch: 'assets/tex/marble_01/diff.jpg' },
  ] },
  walls: { he: 'קירות', en: 'Walls', items: [
    { id: 'limewash', he: 'סיד', en: 'Limewash', swatch: '#ECE6DC', original: true },
    { id: 'clay', he: 'טיח חימר', en: 'Clay', color: '#C9B8A3', swatch: '#C9B8A3' },
    { id: 'sage', he: 'מרווה', en: 'Sage', color: '#B9BDA8', swatch: '#B9BDA8' },
    { id: 'rose', he: 'ורוד עתיק', en: 'Dusty rose', color: '#D8BCB1', swatch: '#D8BCB1' },
    { id: 'butter', he: 'חמאה', en: 'Butter', color: '#E8DBB4', swatch: '#E8DBB4' },
    { id: 'ink', he: 'דיו', en: 'Ink blue', color: '#4C5664', swatch: '#4C5664' },
  ] },
  fabric: { he: 'בדים', en: 'Fabric', items: [
    { id: 'asbuilt', he: 'כמו בתכנון', en: 'As designed', swatch: '#CDBFA9', original: true },
    { id: 'oat', he: 'שיבולת שועל', en: 'Oat', tint: '#E3D7C2', swatch: '#E3D7C2' },
    { id: 'terracotta', he: 'טרקוטה', en: 'Terracotta', tint: '#B86F52', swatch: '#B86F52' },
    { id: 'moss', he: 'אזוב', en: 'Moss', tint: '#7C8466', swatch: '#7C8466' },
    { id: 'denim', he: 'כחול פשתן', en: 'Linen blue', tint: '#7F8FA3', swatch: '#7F8FA3' },
    { id: 'charcoal', he: 'פחם', en: 'Charcoal', tint: '#4A4846', swatch: '#4A4846' },
  ] },
  wood: { he: 'עץ', en: 'Wood', items: [
    { id: 'oak', he: 'אלון', en: 'Rift oak (as designed)', swatch: 'assets/tex/white_oak_veneer/diff.jpg', original: true },
    { id: 'walnut', he: 'אגוז', en: 'Walnut', tint: '#7A5238', swatch: 'assets/tex/walnut_veneer/diff.jpg' },
    { id: 'ash', he: 'אפר בהיר', en: 'Pale ash', tint: '#E2D2B8', swatch: '#E2D2B8' },
    { id: 'black', he: 'שחור', en: 'Black stain', tint: '#3A3430', swatch: '#3A3430' },
  ] },
};
const CATS = Object.keys(SAMPLES);
const ORIGINAL = Object.fromEntries(CATS.map((c) => [c, SAMPLES[c].items.find((i) => i.original).id]));
// which meshes belong to which sample category (by the Blender object name)
const CATEGORY = [
  ['floor', /^Floor (?!terrace|service|landing)/],
  ['walls', /^(Wall |Lintel |Head |Jamb )/],
  ['fabric', /^(HYLTARP|STOCKHOLM|Cushion|Bench pad|LYCKSELE|Office cushion)|duvet|throw|pillow|headboard/i],
  ['wood', /^(BESTA|LISTERBY|Base run|Tall column|Peninsula|Floating shelf|Wall run|Fluted|Bench seat|Shoe cabinet|Niche|Screen|Seam|Waterfall|Wardrobe walk|TONSTAD|Teen bed platform|Teen shelf|BILLY|FLISAT|KURA)/],
];
const categoryOf = (name) => { for (const [c, re] of CATEGORY) if (re.test(name)) return c; return null; };

// ready-made moods: one click styles the room you are in (or every room)
const MOODS = [
  { id: 'asbuilt', he: 'כמו בתכנון', en: 'As designed', picks: { floor: 'asbuilt', walls: 'limewash', fabric: 'asbuilt', wood: 'oak' } },
  { id: 'nordic', he: 'נורדי בהיר', en: 'Pale Nordic', picks: { floor: 'oak', walls: 'limewash', fabric: 'oat', wood: 'ash' } },
  { id: 'clay', he: 'חימר חם', en: 'Warm clay', picks: { floor: 'asbuilt', walls: 'clay', fabric: 'terracotta', wood: 'walnut' } },
  { id: 'sage', he: 'גן מרווה', en: 'Sage garden', picks: { floor: 'asbuilt', walls: 'sage', fabric: 'moss', wood: 'oak' } },
  { id: 'ink', he: 'דיו ואגוז', en: 'Ink & walnut', picks: { floor: 'concrete', walls: 'ink', fabric: 'oat', wood: 'walnut' } },
  { id: 'soft', he: 'ורוד רך', en: 'Soft rose', picks: { floor: 'oak', walls: 'rose', fabric: 'oat', wood: 'ash' } },
];

// the IKEA pieces in each area (article numbers as in the Blender scene)
const IKEA = {
  living: [['HYLTARP', '2-seat sofa', '09489637'], ['STOCKHOLM 2025', 'armchair', '10594755'], ['BESTÅ', 'TV bench', '99188343'], ['LOHALS', 'rug, flatwoven', '00277395'],
    ['ROSENTORP', 'bar stool', '10619930'], ['NÄMMARÖ', 'easy chair, outdoor', '79584363'], ['NÄMMARÖ', 'table, outdoor', '20510307'], ['NÄMMARÖ', 'armchair, outdoor', '90511105']],
  master: [['TONSTAD', 'bed frame', '49496674'], ['TONSTAD', 'bedside table', '80489322'], ['KUDDLAVA', 'table lamp', '90601200'], ['LINDKNUD', 'rug', '90415689'], ['OKENSAND', 'floor lamp', '00541531']],
  teen: [['TONSTAD', 'bedside table', '80489322'], ['KUDDLAVA', 'table lamp', '90601200'], ['LAGKAPTEN / ALEX', 'desk', '69521620'], ['NAVLINGE', 'work lamp', '90404921'],
    ['FLINTAN', 'office chair', '30492204'], ['VILHATTEN', 'wardrobe', '70530609'], ['KNAPPER', 'standing mirror', '00396242'], ['ARENDE', 'rug', '20576435'], ['RÖDALM', 'frame', '00566395']],
  office: [['LAGKAPTEN / ALEX', 'desk', '69521620'], ['FORSÅ', 'work lamp', '80106012'], ['ÄLEFJÄLL', 'office chair', '90320224'], ['LYCKSELE', 'sofa bed', '09387021'],
    ['BESTÅ', 'TV bench', '99188343'], ['BILLY', 'bookcase', '10508932'], ['ARENDE', 'rug', '20576435']],
  toddler: [['KURA', 'reversible bed', '80253809'], ['SMÅGÖRA', 'wardrobe', '10460888'], ['TROFAST', 'storage', '39574865'], ['FLISAT', 'children’s table', '50298418'],
    ['FLISAT', 'book display', '80614566'], ['FLADIS', 'basket', '60322173'], ['STAPPSPARV', 'rug', '60603026'], ['BLÅHAJ', 'soft toy', '30373588'], ['DJUNGELSKOG', 'soft toy', '00402813'], ['LILLABO', 'toy cars', '50589361']],
  baths: [],
};
// one place to change how a sample looks in the tray (all floors are the ivory porcelain as designed)
const swatchOf = (cat, it) => it.swatch;
const bgOf = (sw) => (sw.startsWith('#') ? `background:${sw}` : `background-image:url(${sw})`);
const artNo = (n) => `${n.slice(0, 3)}.${n.slice(3, 6)}.${n.slice(6)}`;

// ------------------------------------------------------------------ renderer
const canvas = document.getElementById('mood');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.AgXToneMapping;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(42, 1, 0.03, 60000);
camera.rotation.order = 'YXZ';
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true; controls.dampingFactor = 0.08; controls.screenSpacePanning = true;
controls.maxPolarAngle = THREE.MathUtils.degToRad(86);

// ------------------------------------------------------------------ the lightmap mixer
const U = {
  dayW: { value: new THREE.Vector3(0, 0, 1) },
  gain: { value: 1.0 },
  grade: { value: new THREE.Vector3(1, 1, 1) },   // a white balance per time of day, like the renders' 3600 K
  flat: { value: FLAT },
};
let MANIFEST = null, TEXMAP = {};
const texLoader = new THREE.TextureLoader();
const lmTex = {};
function loadLM(file) {
  if (!lmTex[file]) {
    const t = texLoader.load(BASE + file); t.colorSpace = THREE.NoColorSpace; t.flipY = false; t.channel = 1;
    t.minFilter = THREE.LinearMipmapLinearFilter; t.anisotropy = 4; lmTex[file] = t;
  }
  return lmTex[file];
}
const BLACK = new THREE.DataTexture(new Uint8Array([0, 0, 0, 255]), 1, 1); BLACK.needsUpdate = true; BLACK.channel = 1;
const lampFiles = (A) => [...new Set(Object.values(A.channels).map((c) => c.file))].sort();
const NA = AREA_KEYS.length, NR = RECTS.length;
const RECT_U = RECTS.map(({ q }) => new THREE.Vector4(q[0], q[1], q[2], q[3]));
const RECT_A = RECTS.map(({ a }) => a);

function lightmapped(mat, atlas) {
  const A = MANIFEST.atlases[atlas];
  const files = lampFiles(A), NL = Math.max(1, files.length);
  A.lampW = A.lampW || Array.from({ length: NL * 3 }, () => new THREE.Vector3());
  const day = MANIFEST.day.map((g) => (A.maps[g] ? loadLM(A.maps[g].file) : BLACK));
  const dayS = new THREE.Vector3(...MANIFEST.day.map((g) => (A.maps[g] ? A.maps[g].scale : 0)));
  const lamps = Array.from({ length: NL }, (_, i) => (files[i] ? loadLM(files[i]) : BLACK));
  mat.lightMap = day[0]; mat.lightMapIntensity = 0;            // turns on the uv1 lightmap path; the sum below replaces it
  mat.userData.atlas = atlas;
  const wall = !!mat.userData.uWallCol, planar = !!mat.userData.uTri;
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, {
      lmD0: { value: day[0] }, lmD1: { value: day[1] }, lmD2: { value: day[2] }, lmDS: { value: dayS },
      uDayW: U.dayW, uLampW: { value: A.lampW }, uGain: U.gain, uGrade: U.grade, uFlat: { value: Object.keys(A.maps).length ? 0 : FLAT },
      uTint: mat.userData.uTint || { value: new THREE.Color(1, 1, 1) }, uTintAmt: mat.userData.uTintAmt || { value: 0 },
    });
    lamps.forEach((t, i) => { sh.uniforms['lmL' + i] = { value: t }; });
    if (wall) Object.assign(sh.uniforms, { uRects: { value: RECT_U }, uRectA: { value: RECT_A }, uWallCol: mat.userData.uWallCol, uWallBase: mat.userData.uWallBase });
    if (planar) Object.assign(sh.uniforms, { uTri: mat.userData.uTri, uTriRot: mat.userData.uTriRot, uTexAdj: mat.userData.uTexAdj, uTexTint: mat.userData.uTexTint });
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vWP; varying vec3 vWN;')
      .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvWP = (modelMatrix * vec4(transformed, 1.0)).xyz; vWN = normalize(mat3(modelMatrix) * objectNormal);');
    const lampSum = lamps.map((_, i) => `{ vec3 t = lmDecode(texture2D(lmL${i}, q).rgb); E += t.r * uLampW[${3 * i}] + t.g * uLampW[${3 * i + 1}] + t.b * uLampW[${3 * i + 2}]; }`).join('\n');
    let fs = sh.fragmentShader
      .replace('#include <common>', `#include <common>
        varying vec3 vWP; varying vec3 vWN;
        uniform sampler2D lmD0, lmD1, lmD2, ${lamps.map((_, i) => 'lmL' + i).join(', ')}; uniform vec3 lmDS, uDayW; uniform vec3 uLampW[${NL * 3}]; uniform float uGain, uFlat; uniform vec3 uGrade;
        uniform vec3 uTint; uniform float uTintAmt;
        ${wall ? `uniform vec4 uRects[${NR}]; uniform int uRectA[${NR}]; uniform vec3 uWallCol[${NA}]; uniform vec3 uWallBase;` : ''}
        ${planar ? `uniform vec4 uTri; uniform float uTriRot; uniform vec2 uTexAdj; uniform vec3 uTexTint;
        // Blender's object-space texture mapping, which glTF cannot carry: flat (floors) or box (wood, fabric)
        vec4 triTex(sampler2D t, vec2 uv) {
          if (uTri.x < 0.5) return texture2D(t, uv);
          vec3 bp = vec3(vWP.x, -vWP.z, vWP.y);
          if (uTri.x < 1.5) {
            float c = cos(uTriRot), s = sin(uTriRot);
            vec2 p = vec2(c * bp.x - s * bp.y, s * bp.x + c * bp.y) * uTri.y + uTri.zw;
            return texture2D(t, vec2(p.x, 1.0 - p.y));
          }
          vec3 bn = abs(normalize(vec3(vWN.x, -vWN.z, vWN.y))); bn = pow(bn, vec3(6.0)); bn /= dot(bn, vec3(1.0));
          vec3 sp = bp * uTri.y;
          return texture2D(t, vec2(sp.y, 1.0 - sp.z)) * bn.x + texture2D(t, vec2(sp.x, 1.0 - sp.z)) * bn.y + texture2D(t, vec2(sp.x, 1.0 - sp.y)) * bn.z;
        }` : ''}
        vec3 lmDecode(vec3 t) { return pow(t, vec3(2.2)); }`)
      .replace('#include <color_fragment>', `#include <color_fragment>
        { float l = dot(diffuseColor.rgb, vec3(0.299, 0.587, 0.114));
          diffuseColor.rgb = mix(diffuseColor.rgb, uTint * (0.35 + 1.3 * l), uTintAmt); }
        ${wall ? `{ // wall paint per area: which room is this side of the wall in (a step along the normal, into the room)
          vec3 qp = vWP + normalize(vWN) * 0.08; vec2 pl = vec2(qp.x, -qp.z); int a = -1;
          for (int i = 0; i < ${NR}; i++) { vec4 r = uRects[i]; if (pl.x >= r.x && pl.x <= r.y && pl.y >= r.z && pl.y <= r.w) a = uRectA[i]; }
          vec3 c = uWallBase;
          for (int k = 0; k < ${NA}; k++) if (k == a) c = uWallCol[k];
          diffuseColor.rgb *= c; }` : ''}`)
      .replace('#include <lights_fragment_maps>', `#include <lights_fragment_maps>
        { vec2 q = vLightMapUv;
          // all interior light is baked: drop the live lights (they only light the world outside)
          irradiance = vec3(0.0); reflectedLight.directDiffuse = vec3(0.0); reflectedLight.directSpecular = vec3(0.0);
          vec3 E = uDayW.x * lmDS.x * lmDecode(texture2D(lmD0, q).rgb) + uDayW.y * lmDS.y * lmDecode(texture2D(lmD1, q).rgb) + uDayW.z * lmDS.z * lmDecode(texture2D(lmD2, q).rgb);
          ${lampSum}
          E += vec3(uFlat);
          irradiance += E * uGrade * uGain * PI; }`);
    if (planar) fs = fs
      .replace(/#include <map_fragment>/, `
        #ifdef USE_MAP
          diffuseColor *= triTex(map, vMapUv);
          // the colour adjustments of the Blender material (value, saturation, tint)
          diffuseColor.rgb = mix(vec3(dot(diffuseColor.rgb, vec3(0.2126, 0.7152, 0.0722))), diffuseColor.rgb, uTexAdj.y) * uTexAdj.x * uTexTint;
        #endif`)
      .replace(/#include <roughnessmap_fragment>/, `float roughnessFactor = roughness;
        #ifdef USE_ROUGHNESSMAP
          roughnessFactor *= triTex(roughnessMap, vRoughnessMapUv).g;
        #endif`);
    sh.fragmentShader = fs;
  };
  mat.customProgramCacheKey = () => 'lm' + atlas + NL + (wall ? 'W' : '') + (planar ? 'P' : '');
  mat.needsUpdate = true;
}

function kelvin(k) {   // approximate blackbody colour, normalised to luminance 1
  const t = k / 100; let r, g, b;
  r = t <= 66 ? 1 : Math.min(1, 1.2929 * Math.pow(t - 60, -0.1332));
  g = t <= 66 ? Math.min(1, Math.max(0, 0.3901 * Math.log(t) - 0.6318)) : Math.min(1, 1.1299 * Math.pow(t - 60, -0.0755));
  b = t >= 66 ? 1 : t <= 19 ? 0 : Math.min(1, Math.max(0, 0.5432 * Math.log(t - 10) - 1.1963));
  const L = 0.2126 * r + 0.7152 * g + 0.0722 * b; return new THREE.Vector3(r / L, g / L, b / L);
}

// ------------------------------------------------------------------ state
const defaultPicks = () => Object.fromEntries(AREA_KEYS.map((a) => [a, { ...ORIGINAL }]));
const state = { time: 2, scene: 'evening', userPickedScene: false, area: 'living', areaLocked: false, everywhere: false, picks: defaultPicks() };
const byCatArea = {};               // `${cat}:${area}` → materials
const wallMats = [];                // wall paint lives in the shader: one colour per area
const emissive = [];                // { mat, circuit, base, paper }
let ceilings = [], world = null, sky = null;
const parts = {};                   // atlas → loaded group
const meshes = [];                  // every interior mesh (for picking)
const outside = { hemi: null, sun: null };
let envCam = null, pmrem = null, envRT = null, envDirty = 0;
function refreshEnv() {
  if (!envCam) return;
  const hidden = []; for (const c of ceilings) { hidden.push([c, c.visible]); c.visible = true; }
  scene.environment = null; envCam.update(renderer, scene);
  for (const [c, v] of hidden) c.visible = v;
  if (envRT) envRT.dispose(); envRT = pmrem.fromCubemap(envCam.renderTarget.texture); scene.environment = envRT.texture;
}
const SUNS = [[110, 18, 2.6, 0xffe2c4], [190, 47, 3.0, 0xfff6ea], [262, -3, 0.0, 0xff9a70], [262, -20, 0.0, 0x000000]];
const HEMI = [[0x9fbbe0, 0x8a7a64, 1.1], [0xbcd2ee, 0x9a8a72, 1.3], [0x5a6c96, 0x2e2b2c, 0.55], [0x0e1424, 0x0a0a0c, 0.25]];

function applyLight() {
  const t = state.time, i0 = Math.floor(Math.min(t, 2.999)), f = t - i0, a = TIMES[i0], b = TIMES[Math.min(3, i0 + 1)];
  const mix = (x, y) => x + (y - x) * f;
  U.dayW.value.set(mix(a.day[0], b.day[0]), mix(a.day[1], b.day[1]), mix(a.day[2], b.day[2]));
  // the eye adapts: dim scenes (the 5% night path, the film glow) get a little more exposure, as they would in the room
  const ADAPT = { night: 2.2, film: 0.7, view: 0.6, bedtime: 0.4 };
  const adapt = t >= 1.6 ? ADAPT[state.scene] || 0 : 0;
  renderer.toneMappingExposure = Math.pow(2, mix(a.ev, b.ev) + adapt);
  if (sky) sky.material.uniforms.uK.value = Math.pow(2, -adapt);   // …but the night sky stays dark
  const warm = THREE.MathUtils.smoothstep(t, 1.4, 2.0); U.grade.value.set(1 + 0.16 * warm, 1, 1 - 0.22 * warm);
  const levels = (SCENES[state.scene] || SCENES.off).levels;
  // lamp channels: mean level of the circuits baked together, tinted by their colour temperature
  for (const A of Object.values(MANIFEST.atlases)) {
    const files = lampFiles(A); if (!A.lampW) continue;
    for (const c of Object.values(A.channels)) {
      const slot = files.indexOf(c.file) * 3 + c.channel;
      const circ = c.circuits; const w = circ.reduce((s, k) => s + frac(levels[k] || 0), 0) / circ.length;
      const cct = circ.reduce((s, k) => s + (CCT[k] || 2700), 0) / circ.length;
      A.lampW[slot].copy(kelvin(cct)).multiplyScalar(w * c.scale);
    }
  }
  // paper shades are emitters in Blender, so the diffuse bake left them black: when a shade is off it still
  // has to read as white paper in daylight, so it gets a small fill that follows the time of day
  const PAPER_FILL = [0.16, 0.2, 0.025, 0.004], fill = mix(PAPER_FILL[i0], PAPER_FILL[Math.min(3, i0 + 1)]);
  for (const e of emissive) e.mat.emissiveIntensity = e.base * frac(levels[e.circuit] || 0) + (e.paper ? fill / 0.6 : 0);
  if (sky) {
    sky.material.uniforms.uZen.value.setRGB(...a.sky[0].map((v, k) => mix(v, b.sky[0][k])));
    sky.material.uniforms.uHor.value.setRGB(...a.sky[1].map((v, k) => mix(v, b.sky[1][k])));
  }
  if (outside.sun) {
    const k0 = SUNS[i0], k1 = SUNS[Math.min(3, i0 + 1)];
    const az = THREE.MathUtils.degToRad(mix(k0[0], k1[0])), el = THREE.MathUtils.degToRad(mix(k0[1], k1[1]));
    outside.sun.position.set(Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el)).multiplyScalar(200).add(V(5, 0, -6));
    outside.sun.target.position.set(5, 0, -6); outside.sun.intensity = Math.max(0, mix(k0[2], k1[2]));
    outside.sun.color.set(k0[3]).lerp(new THREE.Color(k1[3]), f);
    const h0 = HEMI[i0], h1 = HEMI[Math.min(3, i0 + 1)];
    outside.hemi.color.set(h0[0]).lerp(new THREE.Color(h1[0]), f); outside.hemi.groundColor.set(h0[1]).lerp(new THREE.Color(h1[1]), f); outside.hemi.intensity = mix(h0[2], h1[2]) * Math.pow(2, -adapt); outside.sun.intensity *= Math.pow(2, -adapt);
  }
  if (world) world.group.traverse((o) => { if (o.isInstancedMesh && o.material.userData.nightGlow) o.material.userData.nightGlow.value = THREE.MathUtils.smoothstep(t, 1.6, 2.2); });
  envDirty = performance.now() + 180;
  saveHash(); updateUI();
}

// ------------------------------------------------------------------ materials from samples
const texCache = {};
function tex(url, srgb) {
  const k = url + srgb;
  if (!texCache[k]) { const t = texLoader.load(url); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace; t.anisotropy = 8; texCache[k] = t; }
  return texCache[k];
}
function applySample(area, cat, id, quiet = false) {
  const item = SAMPLES[cat].items.find((x) => x.id === id); if (!item) return;
  state.picks[area][cat] = id;
  const ai = AREA_KEYS.indexOf(area);
  if (cat === 'walls') {
    for (const m of wallMats) m.userData.uWallCol.value[ai].copy(item.color ? new THREE.Color(item.color) : m.userData.uWallBase.value);
  }
  for (const m of byCatArea[`${cat}:${area}`] || []) {
    const o = m.userData.orig;
    if (cat === 'floor') {
      if (item.tex) {
        m.map = tex(item.tex.map, true); m.normalMap = null; m.roughnessMap = tex(item.tex.rough, false);
        m.userData.uTri.value.set(1, 1 / item.size, 0, 0); m.userData.uTriRot.value = 0; m.color.set(0xffffff);
        m.userData.uTexAdj.value.set(1, 1); m.userData.uTexTint.value.set(1, 1, 1);
      } else {
        m.map = o.map; m.normalMap = o.normalMap; m.roughnessMap = o.roughnessMap; m.color.copy(o.color);
        m.userData.uTri.value.copy(o.tri); m.userData.uTriRot.value = o.triRot; m.userData.uTexAdj.value.copy(o.adj); m.userData.uTexTint.value.copy(o.tint);
      }
      m.needsUpdate = true;
    } else if (cat !== 'walls') {
      if (item.tint) { m.userData.uTint.value.set(item.tint).convertSRGBToLinear(); m.userData.uTintAmt.value = 1; }
      else m.userData.uTintAmt.value = 0;
    }
  }
  if (!quiet) { envDirty = performance.now() + 180; saveHash(); updateUI(); }
}
function applyMood(id) {
  const mood = MOODS.find((m) => m.id === id); if (!mood) return;
  const areas = state.everywhere ? AREA_KEYS : [state.area];
  for (const a of areas) for (const c of CATS) applySample(a, c, mood.picks[c], true);
  envDirty = performance.now() + 180; saveHash(); updateUI();
}
const moodOf = (area) => (MOODS.find((m) => CATS.every((c) => m.picks[c] === state.picks[area][c])) || {}).id;

// ------------------------------------------------------------------ load
function prepare(root, atlas) {
  const matCopies = new Map();
  root.traverse((o) => {
    if (!o.isMesh) return;
    const ud = { ...(o.parent?.userData || {}), ...o.userData };
    const src = ud.src || o.name, room = ud.room || '', area = ROOM_AREA[room] || '';
    const cat = categoryOf(src);
    let m = o.material;
    const paper = /^(Washi|Rice paper|VIDJA shade)/.test(m.name);
    const fam = paper ? (src.match(/^(Pendant kitchen|Pendant living|VIDJA|HOLMO|KUDDLAVA)/) || [''])[0] : '';
    // meshes in a swappable category get their own material per area (so a sample changes only that room)
    const key = m.uuid + (cat && cat !== 'walls' ? cat + area : cat || '') + fam;
    if (!matCopies.has(key)) {
      const mm = m.clone(); mm.userData.orig = { map: m.map, normalMap: m.normalMap, roughnessMap: m.roughnessMap, color: m.color.clone() };
      mm.userData.uTint = { value: new THREE.Color(1, 1, 1) }; mm.userData.uTintAmt = { value: 0 };
      // textures Blender mapped by object coordinates: reproduce that mapping and the colour adjustments
      const tm = TEXMAP[m.name.replace(/@[A-Z]$/, '').replace(/\.\d{3}$/, '')];
      if (tm || cat === 'floor') {
        const tri = new THREE.Vector4(tm ? (tm.mode === 'flat' ? 1 : 2) : 0, tm ? tm.k : 1, tm?.off?.[0] || 0, tm?.off?.[1] || 0);
        const adj = new THREE.Vector2(tm?.value ?? 1, tm?.sat ?? 1), tint = new THREE.Vector3(...(tm?.tint || [1, 1, 1]));
        Object.assign(mm.userData, { uTri: { value: tri.clone() }, uTriRot: { value: tm?.rot || 0 }, uTexAdj: { value: adj.clone() }, uTexTint: { value: tint.clone() } });
        Object.assign(mm.userData.orig, { tri, triRot: tm?.rot || 0, adj, tint });
        if (tm) { mm.normalMap = null; mm.userData.orig.normalMap = null; }   // their normal maps were object-mapped too
      }
      if (cat === 'walls') {
        mm.userData.uWallBase = { value: m.color.clone() };
        mm.userData.uWallCol = { value: AREA_KEYS.map(() => m.color.clone()) };
        mm.color.set(0xffffff); wallMats.push(mm);
      }
      lightmapped(mm, atlas);
      if (paper) {
        // paper shades glow from the lamp inside them: which circuit depends on the fitting
        const circuit = /^Pendant kitchen/.test(src) ? 'KIT_PEND' : /^Pendant living/.test(src) ? 'LIV_PEND' : /^VIDJA/.test(src) ? 'LIV_COL' : /^HOLMO/.test(src) ? 'LIV_LANT' : ud.circuit || null;
        mm.emissive = new THREE.Color(1.0, 0.72, 0.45); mm.emissiveMap = null; mm.side = THREE.DoubleSide;
        if (circuit) emissive.push({ mat: mm, circuit, base: 2.2, paper: true });
      } else if (mm.emissive && (mm.emissive.r + mm.emissive.g + mm.emissive.b) > 0.01) {
        mm.emissiveIntensity = mm.emissiveIntensity || 1;
        if (ud.circuit) emissive.push({ mat: mm, circuit: ud.circuit, base: mm.emissiveIntensity || 1 });
      }
      if (/^(Glass|Balustrade glass)/.test(m.name)) { mm.transparent = true; mm.opacity = /^Bal/.test(m.name) ? 0.2 : 0.12; mm.depthWrite = false; mm.metalness = 0; mm.roughness = 0.05; }
      if (/^Mirror/.test(m.name)) { mm.metalness = 1; mm.roughness = 0.04; mm.color.set(0xd8d8d8); }
      if (/^Linen sheer/.test(m.name)) { mm.transparent = true; mm.opacity = 0.82; mm.side = THREE.DoubleSide; }
      matCopies.set(key, mm);
      if (cat && cat !== 'walls' && area) (byCatArea[`${cat}:${area}`] ||= []).push(mm);
    }
    o.material = matCopies.get(key);
    o.userData.category = cat; o.userData.area = area; o.userData.src = src;
    meshes.push(o);
    if (/^Ceiling/.test(src)) { ceilings.push(o); o.visible = viewKey !== 'overview'; }
  });
}
function loadPart(atlas, onProgress) {
  const A = MANIFEST.atlases[atlas];
  return new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).loadAsync(BASE + A.glb, (e) => onProgress && e.total && onProgress(e.loaded / e.total))
    .then((gltf) => { prepare(gltf.scene, atlas); scene.add(gltf.scene); parts[atlas] = gltf.scene; return gltf.scene; });
}

async function init() {
  MANIFEST = await (await fetch(BASE + 'lightmaps.json')).json();
  if (!MANIFEST.day) MANIFEST.day = ['morning', 'midday', 'dusk'];
  try { TEXMAP = await (await fetch(BASE + 'texmap.json')).json(); } catch (e) { console.warn('texture mapping table not found'); }
  try {
    const L = await (await fetch('design/lighting.json')).json();
    for (const s of L.scenes) SCENES[s.id] = { he: s.he, en: s.name, levels: s.levels, text: s.text };
    for (const [k, c] of Object.entries(L.circuits)) CCT[k] = c.cct;
  } catch (e) { console.warn('lighting plan not found', e); }
  const order = MANIFEST.order || Object.keys(MANIFEST.atlases);
  const first = order.filter((a) => a !== 'R'), later = order.filter((a) => a === 'R');
  const prog = Object.fromEntries(first.map((a) => [a, 0]));
  const veilP = $('#veil .veil__p');
  await Promise.all(first.map((a) => loadPart(a, (p) => { prog[a] = p; if (veilP) veilP.style.setProperty('--p', Object.values(prog).reduce((s, x) => s + x, 0) / first.length); })));
  // the world outside: Haifa Bay, the city, our tower below
  world = buildWorld(scene); setWorldMix(world, scene, 1); world.sky.visible = false; scene.fog.density = 0.00004;
  sky = makeSky(); scene.add(sky);
  // reflections: a cube map of the lit room itself, refreshed when the light changes
  envCam = new THREE.CubeCamera(0.05, 60000, new THREE.WebGLCubeRenderTarget(256, { type: THREE.HalfFloatType }));
  envCam.position.copy(P(5.6, 7.2, 1.3)); scene.add(envCam);
  pmrem = new THREE.PMREMGenerator(renderer);
  scene.environmentIntensity = 0.6;
  // live light for the world outside only (the interior shader ignores it)
  outside.hemi = new THREE.HemisphereLight(0xbcd2ee, 0x8a7a64, 1.2); outside.sun = new THREE.DirectionalLight(0xfff1dc, 2.5);
  scene.add(outside.hemi, outside.sun, outside.sun.target);
  marker = makeMarker(); scene.add(marker);
  buildUI();
  const h = readHash();
  setView(h.view && VIEWS[h.view] ? h.view : 'overview', true);
  if (h.eye) { enterEye(h.eye.pos, h.eye.look, true); }
  applyPicks(); applyLight();
  document.getElementById('veil').classList.add('is-gone');
  // the bedrooms follow in the background
  for (const a of later) {
    setBusy(true);
    await loadPart(a, (p) => setBusy(true, p));
    applyPicks(); applyLight(); setBusy(false);
  }
}
function applyPicks() { for (const a of AREA_KEYS) for (const c of CATS) applySample(a, c, state.picks[a][c], true); updateUI(); }

function makeSky() {
  const m = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, toneMapped: true,
    uniforms: { uZen: { value: new THREE.Color() }, uHor: { value: new THREE.Color() }, uK: { value: 1 } },
    vertexShader: 'varying vec3 vD; void main(){ vD = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); gl_Position.z = gl_Position.w * 0.99999; }',
    fragmentShader: 'uniform vec3 uZen, uHor; uniform float uK; varying vec3 vD;\nvoid main(){ float h = clamp(vD.y, 0.0, 1.0); gl_FragColor = vec4(mix(uHor, uZen, pow(h, 0.5)) * 0.7 * uK, 1.0);\n#include <tonemapping_fragment>\n#include <colorspace_fragment>\n}',
  });
  const s = new THREE.Mesh(new THREE.SphereGeometry(30000, 32, 16), m); s.frustumCulled = false; s.renderOrder = -10; return s;
}

// ------------------------------------------------------------------ views: the overview, and one eye-level spot per room
const VIEWS = {
  overview: { he: 'מבט על', en: 'Overview', pos: P(5.2, -5.4, 19.5), look: P(0.1, 6.5, 0), fov: 36 },
  // eye-level spots in each room
  entry: { he: 'מבואה', en: 'Entry', pos: P(7.14, 4.28, EYE), look: P(7.0, 6.6, 1.42), fov: 58 },
  living: { he: 'סלון', en: 'Living', pos: P(7.02, 6.15, EYE), look: P(5.4, 10.6, 1.12), fov: 58 },
  media: { he: 'קיר המדיה', en: 'Media wall', pos: P(6.62, 8.95, EYE), look: P(3.55, 7.1, 1.05), fov: 58 },
  kitchen: { he: 'מטבח', en: 'Kitchen', pos: P(4.35, 5.55, EYE), look: P(3.2, 2.2, 0.92), fov: 58 },
  terrace: { he: 'מרפסת', en: 'Balcony', pos: P(6.9, 10.35, EYE), look: P(0.5, 12.2, 1.1), fov: 62 },
  corridor: { he: 'מסדרון', en: 'Corridor', pos: P(3.1, 5.35, EYE), look: P(-4.0, 5.35, 1.3), fov: 62 },
  office: { he: 'חדר עבודה', en: 'Office', pos: P(0.95, 6.35, EYE), look: P(2.9, 9.0, 1.0), fov: 66 },
  teen: { he: 'חדר הנערה', en: 'Teen room', pos: P(-0.2, 6.55, EYE), look: P(-2.1, 9.0, 1.0), fov: 66 },
  toddler: { he: 'חדר הקטנה', en: 'Toddler room', pos: P(-4.85, 5.25, EYE), look: P(-6.9, 7.6, 0.8), fov: 66 },
  master: { he: 'חדר ההורים', en: 'Main bedroom', pos: P(-4.35, 8.65, EYE), look: P(-6.8, 10.8, 1.0), fov: 66 },
};
// a click on a room in the plan goes to its spot
const ROOM_VIEW = { entry: 'entry', living: 'living', kitchen: 'kitchen', terrace: 'terrace', corridor: 'corridor', bed3: 'office', mamad: 'teen', bed4: 'toddler', master: 'master', passage: 'master', ensuite: 'master' };   // the bathrooms have no fittings in the model yet
let viewKey = 'overview', tween = null;
const eye = { on: false, yaw: 0, pitch: 0, pos: new THREE.Vector3(), keys: new Set() };
const dirOf = (yaw, pitch) => V(-Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), -Math.cos(yaw) * Math.cos(pitch));
function lookAngles(pos, look) { const d = look.clone().sub(pos).normalize(); return { yaw: Math.atan2(-d.x, -d.z), pitch: Math.asin(THREE.MathUtils.clamp(d.y, -1, 1)) }; }

function setView(key, instant = false) {
  const v = VIEWS[key]; viewKey = key;
  if (key === 'overview') {
    eye.on = false; controls.enabled = true;
    controls.minDistance = 2.5; controls.maxDistance = 34; controls.enablePan = true; controls.rotateSpeed = 0.8;
    for (const c of ceilings) c.visible = false;
    flyTo(v.pos, v.look, v.fov, instant, false);
  } else enterEye(v.pos, v.look, instant, eyeFov(v.fov));
  updateUI();
}
function enterEye(pos, look, instant = false, fov = 64) {
  controls.enabled = false;
  for (const c of ceilings) c.visible = true;
  flyTo(pos, look, fov, instant, true);
}
function flyTo(pos, look, fov, instant, toEye) {
  const from = { pos: camera.position.clone(), look: eye.on ? camera.position.clone().add(dirOf(eye.yaw, eye.pitch)) : controls.target.clone(), fov: camera.fov };
  const to = { pos: pos.clone(), look: look.clone(), fov, eye: toEye };
  eye.on = false;
  if (instant) { tween = null; finishFly(to); return; }
  tween = { from, to, t0: performance.now(), dur: Math.min(1600, 700 + from.pos.distanceTo(to.pos) * 60) };
}
function finishFly(to) {
  camera.position.copy(to.pos); camera.fov = to.fov; camera.updateProjectionMatrix();
  if (to.eye) {
    const a = lookAngles(to.pos, to.look); eye.yaw = a.yaw; eye.pitch = a.pitch; eye.pos.copy(to.pos); eye.on = true;
    applyEye();
  } else { controls.target.copy(to.look); camera.lookAt(to.look); }
  saveHash(); updateUI();
}
function applyEye() { camera.position.copy(eye.pos); camera.rotation.set(eye.pitch, eye.yaw, 0, 'YXZ'); }

// walking: glide to a point on the floor, keep looking the same way
function walkTo(px, pz) {
  const to = V(px, EYE, pz);
  const dist = to.distanceTo(eye.pos);
  if (dist < 0.15) return;
  tween = { walk: true, from: eye.pos.clone(), to, t0: performance.now(), dur: THREE.MathUtils.clamp(dist / 1.5, 0.45, 2.2) * 1000 };
}
const inFlat = (x, z) => !!roomAt(x, -z, 0.05);
function blocked(from, dir, dist) {
  ray.set(V(from.x, 0.9, from.z), dir); ray.far = dist + 0.3;
  return ray.intersectObjects(meshes, false).some((h) => h.object.visible && !h.object.material.transparent);
}

// portrait screens see more height: widen the eye-level view so a room still reads
const eyeFov = (f) => (camera.aspect >= 1 ? f : Math.min(95, (2 * Math.atan(Math.tan((f * Math.PI) / 360) / Math.pow(camera.aspect, 0.6)) * 180) / Math.PI));

// ------------------------------------------------------------------ the shareable link: #v=…&t=…&s=…&p=…
const SHORT = { floor: 'f', walls: 'w', fabric: 'c', wood: 'o' };
let hashTimer = 0, hashReady = false;
function saveHash() {
  if (!hashReady) return;
  clearTimeout(hashTimer);
  hashTimer = setTimeout(() => {
    const h = new URLSearchParams();
    if (eye.on && viewKey !== 'overview') {
      const d = dirOf(eye.yaw, eye.pitch);
      h.set('e', [eye.pos.x, -eye.pos.z, d.x, -d.z, d.y].map((n) => n.toFixed(2)).join(','));
    } else h.set('v', 'overview');
    h.set('t', state.time.toFixed(2)); h.set('s', state.scene);
    const p = [];
    for (const a of AREA_KEYS) {
      const diff = CATS.filter((c) => state.picks[a][c] !== ORIGINAL[c]).map((c) => SHORT[c] + '.' + state.picks[a][c]);
      if (diff.length) p.push(a + ':' + diff.join(','));
    }
    if (p.length) h.set('p', p.join(';'));
    history.replaceState(null, '', '#' + h.toString());
  }, 250);
}
function readHash() {
  const h = new URLSearchParams(location.hash.slice(1)), out = {};
  if (h.get('t')) state.time = THREE.MathUtils.clamp(+h.get('t') || 2, 0, 3);
  if (h.get('s') && SCENES[h.get('s')]) { state.scene = h.get('s'); state.userPickedScene = true; }
  const LONG = Object.fromEntries(Object.entries(SHORT).map(([k, v]) => [v, k]));
  for (const part of (h.get('p') || '').split(';')) {
    const [a, list] = part.split(':'); if (!AREAS[a] || !list) continue;
    for (const kv of list.split(',')) { const [s, id] = kv.split('.'); const c = LONG[s]; if (c && SAMPLES[c].items.some((i) => i.id === id)) state.picks[a][c] = id; }
  }
  const e = (h.get('e') || '').split(',').map(Number);
  if (e.length === 5 && e.every(Number.isFinite)) {
    out.view = 'living';
    out.eye = { pos: P(e[0], e[1], EYE), look: P(e[0] + e[2], e[1] + e[3], EYE + e[4]) };
  } else out.view = h.get('v') || 'overview';
  hashReady = true;
  return out;
}

// ------------------------------------------------------------------ the plan: where you are, click a room to go there
const NS = 'http://www.w3.org/2000/svg';
const svgEl = (tag, attrs = {}, parent) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (parent) parent.appendChild(n); return n; };
let mapCam = null, mapRooms = {}, mapHere = '';
function buildMap() {
  const host = $('#plan'); const VB = { x0: -8.1, x1: 8.4, y0: -0.1, y1: 13.4 };
  const svg = svgEl('svg', { viewBox: `${VB.x0} ${-VB.y1} ${VB.x1 - VB.x0} ${VB.y1 - VB.y0}`, role: 'img', 'aria-label': 'Floor plan: click a room to go there' }, host);
  const gR = svgEl('g', { class: 'mm-rooms' }, svg), gW = svgEl('g', { class: 'mm-walls' }, svg), gL = svgEl('g', { class: 'mm-labels' }, svg);
  mapCam = svgEl('g', { class: 'mm-cam' }, svg);
  for (const r of DATA.rooms) {
    if (!r.id || r.id === 'landing' || r.id === 'service') continue;
    const g = svgEl('g', { class: 'mm-room', 'data-room': r.id }, gR);
    for (const [x0, x1, y0, y1] of r.rects) svgEl('rect', { x: x0, y: -y1, width: x1 - x0, height: y1 - y0 }, g);
    const v = ROOM_VIEW[r.id];
    if (v) {
      g.classList.add('is-stop'); g.setAttribute('tabindex', '0'); g.setAttribute('role', 'button');
      const name = VIEWS[v].en; g.setAttribute('aria-label', 'Go to ' + name);
      const t = svgEl('title', {}, g); t.textContent = name;
      const go = () => setView(v);
      g.addEventListener('click', go);
      g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
    }
    mapRooms[r.id] = g;
  }
  for (const w of DATA.walls) {
    const ring = (pts) => 'M' + pts.map(([x, y]) => `${x},${-y}`).join('L') + 'Z';
    svgEl('path', { d: [ring(w.outer), ...(w.holes || []).map(ring)].join(' '), 'fill-rule': 'evenodd' }, gW);
  }
  const SHORT_HE = { living: 'סלון', kitchen: 'מטבח', terrace: 'מרפסת', master: 'הורים', mamad: 'נערה', bed3: 'עבודה', bed4: 'קטנה' };
  for (const r of DATA.rooms) {
    if (!r.label || !SHORT_HE[r.id]) continue;
    const t = svgEl('text', { x: r.label[0], y: -r.label[1], 'text-anchor': 'middle', 'dominant-baseline': 'middle' }, gL);
    t.textContent = SHORT_HE[r.id];
  }
  const L = 2.0, a = 0.55;
  svgEl('path', { class: 'mm-cone', d: `M0,0 L${(L * Math.cos(-a)).toFixed(3)},${(L * Math.sin(-a)).toFixed(3)} A${L},${L} 0 0 1 ${(L * Math.cos(a)).toFixed(3)},${(L * Math.sin(a)).toFixed(3)} Z` }, mapCam);
  svgEl('circle', { class: 'mm-dot', r: 0.2 }, mapCam);
}
function updateMap() {
  if (!mapCam) return;
  const show = eye.on || (tween && tween.walk);
  mapCam.style.display = show ? '' : 'none';
  const px = camera.position.x, py = -camera.position.z;
  if (show) {
    const ang = Math.atan2(-Math.cos(eye.yaw), -Math.sin(eye.yaw)) * 180 / Math.PI;   // heading in svg space (y down)
    mapCam.setAttribute('transform', `translate(${px.toFixed(2)} ${(-py).toFixed(2)}) rotate(${ang.toFixed(1)})`);
  }
  const here = show ? roomAt(px, py) : '';
  if (here !== mapHere) {
    mapRooms[mapHere]?.classList.remove('is-here'); mapRooms[here]?.classList.add('is-here'); mapHere = here;
    // the samples follow you from room to room
    const a = ROOM_AREA[here];
    if (a && a !== state.area && !state.areaLocked) { state.area = a; updateUI(); }
    if (here && envCam) {   // reflections from the room you are in
      const q = ROOMS[here][0]; envCam.position.copy(P((q[0] + q[1]) / 2, (q[2] + q[3]) / 2, 1.3)); envDirty = performance.now() + 400;
    }
  }
}
function setBusy(on, p = 0) {
  const b = $('#busy'); if (!b) return;
  b.classList.toggle('is-on', on); b.style.setProperty('--p', p);
}

// ------------------------------------------------------------------ the moodboard sheet
function renderBoard() {
  const sw = (cat, id, a) => {
    const it = SAMPLES[cat].items.find((i) => i.id === id);
    const bg = bgOf(swatchOf(cat, it, a));
    return `<figure><i style="${bg}"></i><figcaption><b dir="rtl">${it.he}</b><span>${SAMPLES[cat].en} · ${it.en}</span></figcaption></figure>`;
  };
  const rows = AREA_KEYS.map((a) => {
    const d = AREAS[a], m = MOODS.find((x) => x.id === moodOf(a));
    return `<section class="board__row${a === state.area ? ' is-here' : ''}">
      <header><b dir="rtl">${d.he}</b><span>${d.en}${m ? ' · ' + m.en : ''}</span></header>
      <div class="board__sw">${CATS.map((c) => sw(c, state.picks[a][c], a)).join('')}</div></section>`;
  }).join('');
  const ik = IKEA[state.area] || [];
  $('#boardBody').innerHTML = `<div class="board__rooms">${rows}</div>
    <aside class="board__ikea"><div class="panel__title"><span dir="rtl">רהיטי איקאה</span> IKEA in ${AREAS[state.area].en}</div>
      ${ik.length ? `<ul>${ik.map(([n, d, no]) => `<li><b>${n}</b> <span>${d}</span><code>${artNo(no)}</code></li>`).join('')}</ul>` : '<p class="panel__note">Built-ins only in these rooms.</p>'}
      <p class="panel__note">Article numbers as modelled; search them on ikea.com.</p></aside>`;
}
function openBoard(on) { $('#board').classList.toggle('is-on', on); if (on) renderBoard(); }

// ------------------------------------------------------------------ UI
const $ = (s) => document.querySelector(s);
function buildUI() {
  // the area you are styling
  $('#area').innerHTML = AREA_KEYS.map((a) => `<option value="${a}">${AREAS[a].en} · ${AREAS[a].he}</option>`).join('');
  $('#area').addEventListener('change', (e) => { state.area = e.target.value; state.areaLocked = true; updateUI(); });
  // moods
  $('#moods').innerHTML = MOODS.map((m) => `<button data-m="${m.id}"><b dir="rtl">${m.he}</b><span>${m.en}</span><i>${CATS.map((c) => { const it = SAMPLES[c].items.find((x) => x.id === m.picks[c]); return `<u style="${it.swatch.startsWith('#') ? 'background:' + it.swatch : `background-image:url(${it.swatch})`}"></u>`; }).join('')}</i></button>`).join('');
  $('#moods').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) applyMood(b.dataset.m); });
  $('#everywhere').addEventListener('change', (e) => { state.everywhere = e.target.checked; });
  // samples
  const tabs = $('#sampleTabs'), tray = $('#tray');
  tabs.innerHTML = Object.entries(SAMPLES).map(([k, c], i) => `<button class="tab${i ? '' : ' is-on'}" data-cat="${k}"><span dir="rtl">${c.he}</span> ${c.en}</button>`).join('');
  const showCat = (k) => {
    tray.dataset.cat = k;
    tabs.querySelectorAll('.tab').forEach((b) => b.classList.toggle('is-on', b.dataset.cat === k));
    tray.innerHTML = SAMPLES[k].items.map((it) => {
      const bg = bgOf(swatchOf(k, it));
      return `<button class="card" draggable="false" data-cat="${k}" data-id="${it.id}"><i style="${bg}"></i><b dir="rtl">${it.he}</b><span>${it.en}</span></button>`;
    }).join('');
    updateUI();
  };
  tabs.addEventListener('click', (e) => { const b = e.target.closest('.tab'); if (b) showCat(b.dataset.cat); });
  showCat('floor');
  tray.addEventListener('pointerdown', startDrag);
  // time of day
  $('#times').innerHTML = TIMES.map((t, i) => `<button data-i="${i}"><b dir="rtl">${t.he}</b><span>${t.en} · ${t.clock}</span></button>`).join('');
  $('#times').addEventListener('click', (e) => { const b = e.target.closest('button'); if (!b) return; animateTime(+b.dataset.i); });
  $('#time').addEventListener('input', (e) => { state.time = +e.target.value; autoScene(); applyLight(); });
  // lighting scenes
  const order = ['off', 'welcome', 'evening', 'cook', 'view', 'film', 'bedtime', 'night', 'all'].filter((k) => SCENES[k]);
  $('#scenes').innerHTML = order.map((k) => `<button data-k="${k}" title="${(SCENES[k].text || '').replace(/"/g, '&quot;')}"><b dir="rtl">${SCENES[k].he}</b><span>${SCENES[k].en}</span></button>`).join('');
  $('#scenes').addEventListener('click', (e) => { const b = e.target.closest('button'); if (!b) return; state.scene = b.dataset.k; state.userPickedScene = true; applyLight(); });
  // the plan and the overview button
  buildMap();
  $('#overviewBtn').addEventListener('click', () => setView('overview'));
  // phones: one panel at a time, from the bar at the bottom
  $('#mbar').addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b) return;
    const k = 'sheet-' + b.dataset.sheet, on = !document.body.classList.contains(k);
    document.body.classList.remove('sheet-samples', 'sheet-light', 'sheet-plan');
    if (on) document.body.classList.add(k);
    document.querySelectorAll('#mbar button').forEach((x) => x.classList.toggle('is-on', on && x === b));
  });
  // the moodboard sheet and the link
  $('#boardBtn').addEventListener('click', () => openBoard(!$('#board').classList.contains('is-on')));
  $('#boardClose').addEventListener('click', () => openBoard(false));
  $('#boardAll').addEventListener('click', () => { const src = state.picks[state.area]; for (const a of AREA_KEYS) for (const c of CATS) applySample(a, c, src[c], true); applyPicks(); saveHash(); renderBoard(); });
  $('#boardReset').addEventListener('click', () => { state.picks = defaultPicks(); applyPicks(); saveHash(); renderBoard(); });
  $('#copyLink').addEventListener('click', async () => {
    saveHash(); await new Promise((r) => setTimeout(r, 300));
    const b = $('#copyLink');
    try { await navigator.clipboard.writeText(location.href); b.classList.add('is-done'); b.querySelector('span').textContent = 'Link copied'; }
    catch { prompt('Copy this link:', location.href); }
    setTimeout(() => { b.classList.remove('is-done'); b.querySelector('span').textContent = 'Copy link to this room'; }, 2200);
  });
  // keys: [ ] time · arrows / WASD walk · O overview · M moodboard
  window.addEventListener('keydown', (e) => {
    if (e.target.closest && e.target.closest('input, select, textarea')) return;
    if (e.key === '[' || e.key === ']') { state.time = Math.min(3, Math.max(0, state.time + (e.key === ']' ? 0.25 : -0.25))); autoScene(); applyLight(); }
    if (e.key === 'o' || e.key === 'O') setView('overview');
    if (e.key === 'm' || e.key === 'M') openBoard(!$('#board').classList.contains('is-on'));
    if (e.key === 'Escape') openBoard(false);
    const k = { ArrowUp: 'f', w: 'f', W: 'f', ArrowDown: 'b', s: 'b', S: 'b', ArrowLeft: 'l', ArrowRight: 'r', a: 'sl', A: 'sl', d: 'sr', D: 'sr' }[e.key];
    if (k && eye.on) { eye.keys.add(k); e.preventDefault(); }
  });
  window.addEventListener('keyup', (e) => {
    const k = { ArrowUp: 'f', w: 'f', W: 'f', ArrowDown: 'b', s: 'b', S: 'b', ArrowLeft: 'l', ArrowRight: 'r', a: 'sl', A: 'sl', d: 'sr', D: 'sr' }[e.key];
    if (k) eye.keys.delete(k);
  });
  window.addEventListener('blur', () => eye.keys.clear());
  // the canvas: drag to look (inside) / orbit (overview); click the floor to walk; double-click to step in
  canvas.addEventListener('pointerdown', onCanvasDown);
  canvas.addEventListener('pointermove', onCanvasHover);
  canvas.addEventListener('pointerleave', () => { marker.visible = false; });
  canvas.addEventListener('dblclick', onCanvasDbl);
}
function autoScene() { if (!state.userPickedScene) state.scene = state.time >= 1.6 ? TIMES[Math.round(state.time)].lamps || 'evening' : 'off'; }
let timeAnim = null;
function animateTime(i) { timeAnim = { from: state.time, to: i, t0: performance.now(), dur: 900 }; }
function updateUI() {
  const t = state.time;
  document.querySelectorAll('#times button').forEach((b) => b.classList.toggle('is-on', Math.abs(+b.dataset.i - t) < 0.13));
  const r = $('#time'); if (r && document.activeElement !== r) r.value = t;
  document.querySelectorAll('#scenes button').forEach((b) => b.classList.toggle('is-on', b.dataset.k === state.scene));
  const ob = $('#overviewBtn'); if (ob) ob.classList.toggle('is-on', viewKey === 'overview' && !eye.on && !(tween && tween.to?.eye));
  const sel = $('#area'); if (sel && sel.value !== state.area) sel.value = state.area;
  const fc = document.querySelector('#tray .card[data-cat="floor"][data-id="asbuilt"] i'); if (fc) fc.setAttribute('style', bgOf(swatchOf('floor', SAMPLES.floor.items[0])));
  const picks = state.picks[state.area];
  document.querySelectorAll('#tray .card').forEach((b) => b.classList.toggle('is-on', picks[b.dataset.cat] === b.dataset.id));
  const mid = moodOf(state.area);
  document.querySelectorAll('#moods button').forEach((b) => b.classList.toggle('is-on', b.dataset.m === mid));
  document.body.classList.toggle('is-dark', t >= 1.6);
  document.body.classList.toggle('is-eye', eye.on);
  if ($('#board')?.classList.contains('is-on')) renderBoard();
}

// ------------------------------------------------------------------ pointer: look, walk, drop samples
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
function pick(x, y, list = meshes) {
  const r = canvas.getBoundingClientRect(); ndc.set(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(ndc, camera); ray.far = Infinity;
  const hits = ray.intersectObjects(list, false).filter((h) => h.object.visible && !h.object.material.transparent);
  return hits[0] || null;
}
// which area a hit belongs to: furniture by its room, walls and floors by the side you see
function hitArea(h) {
  if (!h) return null;
  const n = h.face ? h.face.normal.clone().transformDirection(h.object.matrixWorld) : V(0, 1, 0);
  if (n.dot(ray.ray.direction) > 0) n.negate();
  const p = h.point.clone().addScaledVector(n, 0.08);
  return ROOM_AREA[roomAt(p.x, -p.z)] || h.object.userData.area || null;
}
let marker = null;
function makeMarker() {
  const g = new THREE.Mesh(new THREE.RingGeometry(0.16, 0.22, 40), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.75, depthTest: true, toneMapped: false }));
  g.rotation.x = -Math.PI / 2; g.visible = false; g.renderOrder = 5; return g;
}
let hoverT = 0;
function onCanvasHover(e) {
  if (!eye.on || drag || look) { if (marker) marker.visible = false; return; }
  const now = performance.now(); if (now - hoverT < 90) return; hoverT = now;
  const h = pick(e.clientX, e.clientY);
  const ok = h && h.face && h.face.normal.clone().transformDirection(h.object.matrixWorld).y > 0.7 && h.point.y < 0.6 && inFlat(h.point.x, h.point.z);
  marker.visible = !!ok;
  if (ok) marker.position.set(h.point.x, h.point.y + 0.01, h.point.z);
  canvas.style.cursor = ok ? 'pointer' : '';
}
let look = null;
function onCanvasDown(e) {
  if (!eye.on || e.button !== 0) return;      // the overview is OrbitControls
  canvas.setPointerCapture(e.pointerId);
  look = { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY, moved: false };
  const mv = (ev) => {
    const dx = ev.clientX - look.x, dy = ev.clientY - look.y; look.x = ev.clientX; look.y = ev.clientY;
    if (Math.hypot(ev.clientX - look.x0, ev.clientY - look.y0) > 5) look.moved = true;
    const k = 0.0032 * (camera.fov / 60);
    eye.yaw += dx * k; eye.pitch = THREE.MathUtils.clamp(eye.pitch + dy * k, -1.25, 1.25);
    if (!tween) applyEye();
  };
  const up = (ev) => {
    canvas.removeEventListener('pointermove', mv);
    const l = look; look = null;
    if (!l.moved) clickWalk(ev.clientX, ev.clientY);
  };
  canvas.addEventListener('pointermove', mv);
  canvas.addEventListener('pointerup', up, { once: true });
}
function clickWalk(x, y) {
  const h = pick(x, y); if (!h) return;
  const n = h.face ? h.face.normal.clone().transformDirection(h.object.matrixWorld) : V(0, 1, 0);
  let p = h.point.clone();
  if (!(n.y > 0.7 && p.y < 0.6)) {      // a wall or a piece of furniture: walk up to it
    const d = ray.ray.direction.clone(); d.y = 0; d.normalize();
    p.addScaledVector(d, -0.55);
  }
  if (!inFlat(p.x, p.z)) return;
  walkTo(p.x, p.z);
}
function onCanvasDbl(e) {
  if (eye.on) return;
  const h = pick(e.clientX, e.clientY); if (!h || !inFlat(h.point.x, h.point.z)) return;
  // step into the plan at that point, looking the way the overview camera looks
  const d = controls.target.clone().sub(camera.position); d.y = 0; d.normalize();
  const pos = V(h.point.x, EYE, h.point.z);
  enterEye(pos, pos.clone().add(d), false, eyeFov(64)); viewKey = 'here';
  VIEWS.here = { he: '', en: 'Here', pos, look: pos.clone().add(d), fov: 64 };
}

// drag & drop with a live preview on the surface under the pointer
let drag = null;
function hitTarget(x, y) {
  const h = pick(x, y); if (!h) return null;
  return { cat: h.object.userData.category, area: hitArea(h) };
}
function startDrag(e) {
  const card = e.target.closest('.card'); if (!card) return;
  e.preventDefault();
  const ghost = card.cloneNode(true); ghost.classList.add('ghost'); document.body.appendChild(ghost);
  drag = { card, ghost, cat: card.dataset.cat, id: card.dataset.id, x0: e.clientX, y0: e.clientY, moved: false, area: null, prev: null };
  moveGhost(e);
  window.addEventListener('pointermove', onDrag); window.addEventListener('pointerup', endDrag, { once: true });
}
function moveGhost(e) { drag.ghost.style.transform = `translate(${e.clientX - 46}px, ${e.clientY - 46}px)`; }
let dragT = 0;
function onDrag(e) {
  if (!drag) return; moveGhost(e);
  if (Math.hypot(e.clientX - drag.x0, e.clientY - drag.y0) > 6) drag.moved = true;
  const now = performance.now(); if (now - dragT < 70) return; dragT = now;
  const over = document.elementFromPoint(e.clientX, e.clientY) === canvas;
  const t = over ? hitTarget(e.clientX, e.clientY) : null;
  const ok = !!(t && t.cat === drag.cat && t.area);
  drag.ghost.classList.toggle('is-ok', ok);
  // preview: apply while hovering a matching surface, undo when leaving it
  if (drag.area && (!ok || t.area !== drag.area)) { applySample(drag.area, drag.cat, drag.prev); drag.area = null; }
  if (ok && !drag.area) { drag.area = t.area; drag.prev = state.picks[t.area][drag.cat]; applySample(t.area, drag.cat, drag.id); }
}
function endDrag(e) {
  window.removeEventListener('pointermove', onDrag);
  const d = drag; drag = null; d.ghost.remove();
  if (!d.moved) { applySample(state.area, d.cat, d.id); return; }     // a click styles the room you are in
  const t = document.elementFromPoint(e.clientX, e.clientY) === canvas ? hitTarget(e.clientX, e.clientY) : null;
  if (d.area && !(t && t.cat === d.cat && t.area === d.area)) applySample(d.area, d.cat, d.prev);
  else if (t && t.cat === d.cat && t.area) { if (t.area !== d.area) applySample(t.area, d.cat, d.id); state.area = t.area; state.areaLocked = true; updateUI(); }
}

// ------------------------------------------------------------------ loop
function resize() {
  const w = innerWidth, h = innerHeight; renderer.setSize(w, h, false); camera.aspect = w / h;
  if (eye.on && VIEWS[viewKey]) camera.fov = eyeFov(VIEWS[viewKey].fov);
  camera.updateProjectionMatrix();
}
addEventListener('resize', resize); resize();
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const easeWalk = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
let last = performance.now();
function frame(now) {
  const dt = Math.min(0.05, (now - last) / 1000); last = now;
  if (tween) {
    const k = Math.min(1, (now - tween.t0) / tween.dur);
    if (tween.walk) {
      eye.pos.lerpVectors(tween.from, tween.to, easeWalk(k)); applyEye();
      if (k >= 1) { tween = null; saveHash(); }
    } else {
      const e = ease(k);
      camera.position.lerpVectors(tween.from.pos, tween.to.pos, e);
      const lk = new THREE.Vector3().lerpVectors(tween.from.look, tween.to.look, e); camera.lookAt(lk);
      camera.fov = tween.from.fov + (tween.to.fov - tween.from.fov) * e; camera.updateProjectionMatrix();
      if (k >= 1) { const to = tween.to; tween = null; finishFly(to); }
    }
  } else if (eye.on && eye.keys.size) {
    // keys: turn and walk, stopped by walls and furniture
    if (eye.keys.has('l')) eye.yaw += 1.6 * dt;
    if (eye.keys.has('r')) eye.yaw -= 1.6 * dt;
    const f = V(-Math.sin(eye.yaw), 0, -Math.cos(eye.yaw)), s = V(Math.cos(eye.yaw), 0, -Math.sin(eye.yaw));
    const mv = V(0, 0, 0);
    if (eye.keys.has('f')) mv.add(f); if (eye.keys.has('b')) mv.sub(f);
    if (eye.keys.has('sr')) mv.add(s); if (eye.keys.has('sl')) mv.sub(s);
    if (mv.lengthSq() > 0) {
      mv.normalize(); const step = 1.4 * dt;
      const nx = eye.pos.x + mv.x * step, nz = eye.pos.z + mv.z * step;
      if (inFlat(nx, nz) && !blocked(eye.pos, mv, step + 0.25)) { eye.pos.x = nx; eye.pos.z = nz; }
    }
    applyEye(); saveHash();
  }
  if (timeAnim) {
    const k = Math.min(1, (now - timeAnim.t0) / timeAnim.dur); state.time = timeAnim.from + (timeAnim.to - timeAnim.from) * ease(k);
    autoScene(); applyLight(); if (k >= 1) timeAnim = null;
  }
  if (envDirty && now > envDirty) { envDirty = 0; if (!NOENV) refreshEnv(); }
  if (controls.enabled && !tween) controls.update();
  updateMap();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}
init().then(() => requestAnimationFrame(frame)).catch((e) => { console.error(e); $('#veil .veil__en').textContent = 'Could not load the flat: ' + e.message; });
window.__mood = { state, applyLight, applySample, applyMood, setView, walkTo, enterEye, V, scene, camera, renderer, U, eye, parts, openBoard, get MANIFEST() { return MANIFEST; } };
