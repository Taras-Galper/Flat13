# Bake the light of the whole flat for the live page, one light group at a time.
# usage:  blender -b dira_mood2.blend -P mood_bake2.py -- <day samples> <lamp samples> [groups,comma,separated | export]
# Light is linear, so the page re-mixes these maps live (any time of day, any lighting scene).
#   day groups (full colour, every atlas):  morning, midday, dusk
#   lamp groups (one channel each, tinted in the page): only the objects near those lamps are baked;
#   texels further away keep zero (that light does not reach them).
# Writes mood/lm/<atlas>_<group>.npy (float16); tools/mood_pack.py turns them into WebP lightmaps.
import bpy, os, sys, json, math, time
import numpy as np

PROJECT = r"C:\Users\grafica\source\repos\dira-landing"
OUT = os.path.join(PROJECT, "mood")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
S_DAY = int(argv[0]) if argv else 128
S_LAMP = int(argv[1]) if len(argv) > 1 else 160
ONLY = set(argv[2].split(",")) if len(argv) > 2 else None
# "empty": the shell (and the rugs) baked with the movable furniture taken out, for rooms whose furniture the
# visitor rearranges in the page. Saved as E<atlas>_<group>.npy next to the normal bakes.
EMPTY = bool(ONLY and "empty" in ONLY)
if EMPTY: ONLY.discard("empty"); ONLY = ONLY or None
# "at:S" (or "at:SL"…) bakes only those atlases
ATLASES = "SLR"
for t in list(ONLY or []):
    if t.startswith("at:"): ATLASES = t[3:]; ONLY.discard(t)
if ONLY is not None and not ONLY: ONLY = None
SIZE = {"S": 2048, "L": 1536, "R": 1536}
FILES = {"S": "shell_raw.glb", "L": "living_raw.glb", "R": "rooms_raw.glb"}

exec(open(os.path.join(PROJECT, "blender", "look.py"), encoding="utf-8").read(), globals())
def log(*a):
    msg = " ".join(str(x) for x in a); print(msg)
    with open(os.path.join(OUT, "bake2.log"), "a", encoding="utf-8") as fh: fh.write(msg + "\n")

src = open(os.path.join(PROJECT, "js", "data.js"), encoding="utf-8").read()
ROOMS = {r["id"]: r["rects"] for r in json.loads(src[src.index("{"): src.rindex("}") + 1])["rooms"]}
ALL = [r for r in ROOMS if r != "landing"]
DAY = ["morning", "midday", "dusk"]
LAMPS = [   # (group, circuits, rooms the light reaches)
    ("entry", ["ENT_D", "ENT_NICHE", "ENT_SCREEN"], ["entry", "living", "kitchen", "corridor"]),
    ("walls", ["WALL_E", "LIV_CURT"], ["living", "entry", "kitchen", "terrace"]),
    ("media", ["WALL_MEDIA", "LIV_ART"], ["living", "entry", "kitchen"]),
    ("paper", ["LIV_PEND", "LIV_COL", "LIV_LANT"], ["living", "entry", "kitchen", "terrace"]),
    ("screen", ["LIV_TV", "LIV_CONSOLE"], ["living", "entry", "kitchen"]),
    ("kitchen", ["KIT_D", "KIT_SHELF", "KIT_PEND", "KIT_PLINTH"], ["kitchen", "living", "entry", "corridor"]),
    ("corridor", ["COR_D", "NIGHT", "PASS_GRAZE"], ALL),
    ("master", ["MST_CURT", "MST_READ", "MST_LAMPS", "MST_ART", "MST_NIGHT"], ["master", "ensuite", "passage", "terrace"]),
    ("bed3", ["B3_DESK", "B3_GRAZE", "B3_TV", "B3_CURT"], ["bed3", "corridor", "terrace"]),
    ("mamad", ["MAM_TRACK", "MAM_MIRROR", "MAM_LAMP", "MAM_COLOR"], ["mamad", "corridor", "terrace"]),
    ("bed4", ["B4_DISC", "B4_CURT", "B4_BOOK", "B4_NIGHT"], ["bed4", "corridor", "passage"]),
    ("terrace", ["BAL_TREE", "BAL_GLOW", "BAL_WALL", "BAL_TABLE"], ["terrace", "living", "bed3", "mamad", "master"]),
]
REACH = 0.8   # metres around the rooms a group lights (baked)
ISOLATE = 2.5  # metres around them that stay in the scene while it bakes (shadows, bounce)

sc = bpy.context.scene
sc.render.engine = "CYCLES"
cp = bpy.context.preferences.addons["cycles"].preferences; cp.compute_device_type = "OPTIX"; cp.get_devices()
for d in cp.devices: d.use = (d.type == "OPTIX")
sc.cycles.device = "GPU"; sc.cycles.use_denoising = False
sc.cycles.max_bounces = 6; sc.cycles.diffuse_bounces = 4
bk = sc.render.bake; bk.use_pass_direct = True; bk.use_pass_indirect = True; bk.use_pass_color = False
bk.target = "IMAGE_TEXTURES"

col = bpy.data.collections["MOOD2"]
KEEP = {"MOOD2", "Shell", "Openings", "Floors", "Ceilings", "Lights"}
for o in bpy.data.objects:
    if o.type in ("MESH", "CURVE") and not ({c.name for c in o.users_collection} & KEEP): o.hide_render = True
for o in col.objects: o.hide_render = False
ATL = {a: [o for o in col.objects if o.get("atlas") == a] for a in "SLR"}
sun = bpy.data.objects.get("Sun"); wn = sc.world.node_tree
street = bpy.data.materials.get("Street lights")
if street: street.node_tree.nodes["Emission"].inputs[1].default_value = 0.0

def lights_off():
    apply_levels({})
    for o in bpy.data.objects:
        if o.type == "LIGHT" and o.name != "Sun" and "circuit" not in o.keys(): o.data.energy = 0.0

def world_black():
    wn.nodes.clear(); wo = wn.nodes.new("ShaderNodeOutputWorld"); bg = wn.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (0, 0, 0, 1); bg.inputs[1].default_value = 0.0; wn.links.new(bg.outputs[0], wo.inputs[0])

def set_group(g):
    lights_off()
    if g in DAY:
        sc.cycles.samples = S_DAY
        if g == "dusk":
            sky_blue_hour(wn, 1.0)
            if sun: sun.hide_render = True
        else:
            el, az, e, c = (18.0, 110.0, 4.0, (1.0, 0.86, 0.72)) if g == "morning" else (47.0, 190.0, 5.0, (1.0, 0.97, 0.93))
            d = sky_nishita(wn, el, az)
            if sun: sun.hide_render = False; sun.data.energy = e; sun.data.color = c; sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    else:
        sc.cycles.samples = S_LAMP
        world_black()
        if sun: sun.hide_render = True
        apply_levels({c: 100 for c in next(cs for n, cs, _ in LAMPS if n == g)})

def near(o, rooms, reach=REACH):
    rs = [(x0 - reach, x1 + reach, y0 - reach, y1 + reach) for k in rooms for (x0, x1, y0, y1) in ROOMS[k]]
    from mathutils import Vector
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    mnx, mxx = min(p.x for p in pts), max(p.x for p in pts); mny, mxy = min(p.y for p in pts), max(p.y for p in pts)
    return any(mnx < x1 and mxx > x0 and mny < y1 and mxy > y0 for x0, x1, y0, y1 in rs)

def prep_targets(atlas):
    img = bpy.data.images.get(f"LM_{atlas}") or bpy.data.images.new(f"LM_{atlas}", SIZE[atlas], SIZE[atlas], alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    for m in {m for o in ATL[atlas] for m in o.data.materials if m}:
        nt = m.node_tree
        n = nt.nodes.get("LM_BAKE") or nt.nodes.new("ShaderNodeTexImage"); n.name = "LM_BAKE"; n.image = img
        nt.nodes.active = n
    for o in ATL[atlas]: o.data.uv_layers.active = o.data.uv_layers["LM"]
    return img

def bake(atlas, objs, img):
    # clear by hand and bake only these objects, with a tiny margin so neighbouring islands are never
    # overwritten (the packer dilates the islands afterwards)
    z = np.zeros(img.size[0] * img.size[1] * 4, np.float32); z[3::4] = 1.0; img.pixels.foreach_set(z)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, margin=2, use_clear=False)

def pixels(img):
    a = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32); img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)[..., :3].copy()

def export():
    for m in bpy.data.materials:
        if m.node_tree and "LM_BAKE" in m.node_tree.nodes: m.node_tree.nodes.remove(m.node_tree.nodes["LM_BAKE"])
    apply_levels({c: 100 for _, cs, _ in LAMPS for c in cs})
    for atlas in "SLR":
        for o in ATL[atlas]: o.data.uv_layers.active = o.data.uv_layers[0]
        bpy.ops.object.select_all(action="DESELECT")
        for o in ATL[atlas]: o.hide_set(False); o.select_set(True)
        bpy.context.view_layer.objects.active = ATL[atlas][0]
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "v2", FILES[atlas]), export_format="GLB", use_selection=True,
                                  export_extras=True, export_apply=False, export_texcoords=True, export_normals=True,
                                  export_materials="EXPORT", export_yup=True, export_lights=False, export_cameras=False)
        log("EXPORTED", FILES[atlas], len(ATL[atlas]))

os.makedirs(os.path.join(OUT, "lm2"), exist_ok=True); os.makedirs(os.path.join(OUT, "v2", "lm"), exist_ok=True)
t0 = time.time()
if ONLY == {"export"}:
    export()
else:
    groups = DAY + [g for g, _, _ in LAMPS]
    if ONLY: groups = [g for g in groups if g in ONLY]
    rugs = set()
    if EMPTY:
        P = json.load(open(os.path.join(OUT, "pieces.json"), encoding="utf-8"))
        rugs = {p["id"] for p in P if p["rug"] and p["movable"]}
    def gone(o, atlas):   # hidden in the empty bake: movable furniture (lamp bodies stay: they carry the light)
        if not EMPTY or not o.get("pmov") or o.get("plamp"): return False
        return atlas == "S" or o.get("piece") not in rugs
    for atlas in ATLASES:
        targets = ATL[atlas] if not EMPTY or atlas == "S" else [o for o in ATL[atlas] if o.get("piece") in rugs]
        if not targets: continue
        img = prep_targets(atlas)
        for g in groups:
            objs = targets if g in DAY else [o for o in targets if near(o, next(r for n, _, r in LAMPS if n == g))]
            if not objs: log(f"SKIP {atlas} {g} (nothing near)"); continue
            # a lamp group only needs the rooms its light reaches: the rest of the flat stays out of the GPU
            rooms = None if g in DAY else next(r for n, _, r in LAMPS if n == g)
            for o in col.objects: o.hide_render = gone(o, atlas) or (False if rooms is None else not near(o, rooms, ISOLATE))
            t = time.time(); set_group(g); bake(atlas, objs, img)
            v = pixels(img); name = ("E" if EMPTY else "") + f"{atlas}_{g}.npy"
            np.save(os.path.join(OUT, "lm2", name), v.astype(np.float16))
            log(f"BAKED {name} {len(objs)} objs {time.time() - t:.0f}s  max {v.max():.3f}")
        log(f"ATLAS {atlas} done {time.time() - t0:.0f}s")
        for o in ATL[atlas]: o.data.uv_layers.active = o.data.uv_layers[0]
log("MOOD BAKE2 DONE", ("empty " if EMPTY else "") + (",".join(sorted(ONLY)) if ONLY else "all"), f"{time.time() - t0:.0f}s")
