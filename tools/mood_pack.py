"""Pack the baked light of the live page: mood/lm/<atlas>_<group>.npy (float, from blender/mood_bake2.py)
-> denoised, 8-bit WebP lightmaps + mood/lightmaps.json.
  daylight groups: one RGB map each;  lamp groups: one channel each, three per map (tinted in the page)
  atlases: S shell (shell.glb), L living room, entry, kitchen, balcony (living.glb), R bedrooms, corridor, baths (rooms.glb)
Run from the project folder:  python3 tools/mood_pack.py"""
import json, os, sys
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, median_filter, distance_transform_edt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOOD = os.path.join(ROOT, "mood"); NPY = os.path.join(MOOD, "lm2")          # bakes in, from blender/mood_bake2.py
OUT = os.path.join(MOOD, os.environ.get("MOOD_OUT", "v2")); LM = os.path.join(OUT, "lm")   # page data out
DAY = ["morning", "midday", "dusk"]
LAMPS = {"entry": ["ENT_D", "ENT_NICHE", "ENT_SCREEN"], "walls": ["WALL_E", "LIV_CURT"], "media": ["WALL_MEDIA", "LIV_ART"],
         "paper": ["LIV_PEND", "LIV_COL", "LIV_LANT"], "screen": ["LIV_TV", "LIV_CONSOLE"], "kitchen": ["KIT_D", "KIT_SHELF", "KIT_PEND", "KIT_PLINTH"],
         "corridor": ["COR_D", "NIGHT", "PASS_GRAZE"], "master": ["MST_CURT", "MST_READ", "MST_LAMPS", "MST_ART", "MST_NIGHT"],
         "bed3": ["B3_DESK", "B3_GRAZE", "B3_TV", "B3_CURT"], "mamad": ["MAM_TRACK", "MAM_MIRROR", "MAM_LAMP", "MAM_COLOR"],
         "bed4": ["B4_DISC", "B4_CURT", "B4_BOOK", "B4_NIGHT"], "terrace": ["BAL_TREE", "BAL_GLOW", "BAL_WALL", "BAL_TABLE"]}
GLB = {"S": "shell.gltf", "L": "living.gltf", "R": "rooms.gltf"}
ORDER = ["S", "L", "R"]           # the page loads the parts in this order
DILATE = 6                        # px: islands grow into the empty atlas so filtering and mipmaps never pull in black

# Intel Open Image Denoise has a filter made for baked lightmaps (pip install --user oidn tbb)
try:
    import ctypes, glob, site
    for p in glob.glob(os.path.join(site.getusersitepackages(), "oidn", "lib.*", "libtbb.so.12*")) + glob.glob(os.path.join(site.getusersitepackages(), "oidn", "lib.*", "tbb12.dll")):
        ctypes.CDLL(p, mode=getattr(ctypes, "RTLD_GLOBAL", 0)); break
    import oidn
    _dev = oidn.NewDevice(); oidn.CommitDevice(_dev)
except Exception as e:
    oidn = None; print("OIDN not available, using a Gaussian:", str(e)[:80])
if os.environ.get("MOOD_NOOIDN"): oidn = None

def oidn_lightmap(v):
    h, w, _ = v.shape; v = np.ascontiguousarray(v, np.float32); out = np.zeros_like(v)
    f = oidn.NewFilter(_dev, "RTLightmap")
    oidn.SetSharedFilterImage(f, "color", v, oidn.FORMAT_FLOAT3, w, h); oidn.SetSharedFilterImage(f, "output", out, oidn.FORMAT_FLOAT3, w, h)
    oidn.CommitFilter(f); oidn.ExecuteFilter(f); oidn.ReleaseFilter(f)
    return np.maximum(out, 0)

def gauss(v, m, sigma=3.0):
    """Fallback: fireflies clamped to their 5x5 neighbourhood, then a Gaussian over the island texels only."""
    nz = v[m > 0]; floor = 0.04 * float(np.percentile(nz, 99)) if nz.size else 0.0
    for c in range(3): v[..., c] = np.minimum(v[..., c], 3.0 * median_filter(v[..., c], size=5) + floor)
    w = gaussian_filter(m, sigma, mode="constant"); out = np.empty_like(v)
    for c in range(3): out[..., c] = gaussian_filter(v[..., c] * m, sigma, mode="constant") / np.maximum(w, 1e-6)
    return out

def denoise(v, m, near):
    v = oidn_lightmap(v) if oidn is not None else gauss(v, m)
    v = np.where(m[..., None] > 0, v, 0)
    return v[near[0], near[1]] * (DIST[..., None] <= DILATE)   # dilate: empty texels take their nearest island texel

def enc(v, s): return (np.clip(v / s, 0, 1) ** (1 / 2.2) * 255 + 0.5).astype(np.uint8)
def save(arr8, name):
    # PNG rows run top-down, Blender pixels bottom-up; glTF UVs (flipY=false) expect the PNG orientation
    Image.fromarray(arr8[::-1]).save(os.path.join(LM, name), "WEBP", quality=88, method=5)
    return "lm/" + name

os.makedirs(LM, exist_ok=True)
have = sorted({f.split("_")[0] for f in os.listdir(NPY) if f.endswith(".npy")})
atlases = [a for a in ORDER if a in have] + [a for a in have if a not in ORDER]
man = {"atlases": {}, "order": atlases, "day": DAY, "lamps": LAMPS}
# MOOD_ATLASES=S,L packs only those atlases and keeps the others from the existing manifest (the full pack is slow)
only = [a for a in os.environ.get("MOOD_ATLASES", "").split(",") if a]
if only and os.path.exists(os.path.join(OUT, "lightmaps.json")):
    old = json.load(open(os.path.join(OUT, "lightmaps.json")))
    man["atlases"] = {a: v for a, v in old.get("atlases", {}).items() if a in atlases}
for atlas in (only or atlases):
    ent = man["atlases"][atlas] = {"glb": GLB.get(atlas, ""), "maps": {}, "channels": {}}
    man["atlases"] = {a: man["atlases"][a] for a in atlases if a in man["atlases"]}   # keep the load order
    files = [f for f in os.listdir(NPY) if f.startswith(atlas + "_") and f.endswith(".npy")]
    m = None   # island texels: anything any group lit (a lamp bake leaves many island texels at exactly 0)
    for f in files:
        k = np.load(os.path.join(NPY, f)).astype(np.float32).max(axis=2) > 0
        m = k if m is None else (m | k)
    m = m.astype(np.float32)
    DIST, near = distance_transform_edt(m == 0, return_indices=True)
    print(atlas, m.shape[0], "island texels", round(float(m.mean()), 3))
    for g in DAY:
        p = os.path.join(NPY, f"{atlas}_{g}.npy")
        if not os.path.exists(p): continue
        v = denoise(np.load(p).astype(np.float32), m, near); nz = v[v > 1e-6]
        s = float(np.percentile(nz, 99.5)) if nz.size else 1.0
        ent["maps"][g] = {"file": save(enc(v, s), f"{atlas}_{g}.webp"), "scale": s}
    lamps = [g for g in LAMPS if os.path.exists(os.path.join(NPY, f"{atlas}_{g}.npy"))]
    for k in range(0, len(lamps), 3):
        trio = lamps[k:k + 3]; out = None
        for ch, g in enumerate(trio):
            v = denoise(np.load(os.path.join(NPY, f"{atlas}_{g}.npy")).astype(np.float32), m, near)
            L = v @ np.array([0.2126, 0.7152, 0.0722], np.float32); nz = L[L > 1e-6]
            s = float(np.percentile(nz, 99.7)) if nz.size else 1.0
            if out is None: out = np.zeros(L.shape + (3,), np.uint8)
            out[..., ch] = enc(L, s)
            ent["channels"][g] = {"file": f"lm/{atlas}_lamps{k // 3}.webp", "channel": ch, "scale": s, "circuits": LAMPS[g]}
        save(out, f"{atlas}_lamps{k // 3}.webp")
    print(atlas, "maps", list(ent["maps"]), "lamp channels", list(ent["channels"]))
json.dump(man, open(os.path.join(OUT, "lightmaps.json"), "w"), indent=1)
sz = sum(os.path.getsize(os.path.join(LM, f)) for f in os.listdir(LM) if f.endswith(".webp"))
print(f"lightmaps {sz / 1e6:.1f} MB")
