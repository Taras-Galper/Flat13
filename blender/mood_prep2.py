# The whole flat for the live three.js page ("mood.html"), in three parts the page loads one after another:
#   S  shell    walls, floors, ceilings, openings of every room          -> mood/shell.glb   (lightmap 2048)
#   L  living   furniture + built-ins of the living room, entry, kitchen, balcony  -> mood/living.glb  (1536)
#   R  rooms    furniture + built-ins of the bedrooms, corridor, bathrooms         -> mood/rooms.glb   (1536)
# Each part has its own lightmap atlas (second UV set "LM"). Run inside Blender after build_scene.py and
# bedrooms.py; saves blender/dira_mood2.blend for mood_bake2.py and leaves the open scene as it was.
import bpy, bmesh, math, os, json, time
from mathutils import Vector

PROJECT = r"C:\Users\grafica\source\repos\dira-landing"
LOG = os.path.join(PROJECT, "mood", "prep2.log")
def log(*a):
    msg = " ".join(str(x) for x in a); print(msg)
    with open(LOG, "a", encoding="utf-8") as fh: fh.write(msg + "\n")

def load_rooms():
    src = open(os.path.join(PROJECT, "js", "data.js"), encoding="utf-8").read()
    data = json.loads(src[src.index("{"): src.rindex("}") + 1])
    return {r["id"]: [tuple(x) for x in r["rects"]] for r in data["rooms"]}
ROOMS = load_rooms()
LIVING = ["living", "entry", "kitchen", "terrace"]
FLAT = [r for r in ROOMS if r != "landing"]
M = 0.32
def grow(rs, m): return [(x0 - m, x1 + m, y0 - m, y1 + m) for (x0, x1, y0, y1) in rs]
RECTS = grow([r for k in FLAT for r in ROOMS[k]], M)
LRECTS = [r for k in LIVING for r in ROOMS[k]]
ARCH_COLS = {"Shell", "Openings", "Floors", "Ceilings"}
SKIP_COLS = {"World", "Cameras", "Lights", "MOOD", "Cutters"}
BUILTIN = ("Base run", "Worktop", "Splash", "Tall column", "Peninsula", "Waterfall", "Toe kick", "Floating shelf", "Niche",
           "Shoe cabinet", "Clay media", "Curtain pocket", "Screen", "Seam")
SIZE = {"S": 2048, "L": 1536, "R": 1536}
# triangle budgets per object, by size. The first version cut everything to 1200 / 4000 / 9000 triangles (down to 4 %),
# with Blender's collapse decimation: cushions cracked open at their seams, small triangles flipped (dark specks), the
# vase broke into shards. Now flat areas are dissolved first (lossless), collapse comes after only above a far higher
# budget, never below 30 % of the original, and the model's own normals are copied back afterwards.
CAPS = ((0.35, 6000), (1.0, 16000), (99.0, 36000))
MIN_RATIO = 0.30

def inside(rects, x, y): return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, x1, y0, y1 in rects)
def bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))), Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
def overlaps(o, rects):
    mn, mx = bbox(o)
    return any(mn.x < x1 and mx.x > x0 and mn.y < y1 and mx.y > y0 for x0, x1, y0, y1 in rects)
def room_of(x, y):
    for k in FLAT:
        if inside(ROOMS[k], x, y): return k
    return ""

def pick():
    out = []
    for o in bpy.data.objects:
        if o.type not in ("MESH", "CURVE") or o.hide_render: continue
        cols = {c.name for c in o.users_collection}
        if cols & SKIP_COLS: continue
        mn, mx = bbox(o)
        if mx.z < -0.5 or mn.z > 3.2: continue
        c = (mn + mx) / 2
        if cols & ARCH_COLS:
            if not overlaps(o, RECTS) or o.name.startswith(("Balcony above", "Slab above")): continue
            out.append((o, "S", room_of(c.x, c.y)))
        else:
            if not inside(RECTS, c.x, c.y): continue
            out.append((o, "L" if inside(grow(LRECTS, 0.05), c.x, c.y) else "R", room_of(c.x, c.y)))
    return out

def clean(me, planar=False):
    """Shell and built-ins: weld split vertices (one lightmap island per surface) and merge coplanar faces.
    Furniture is not welded: that joined the separate shells of cushions and lost the model's hard and soft edges."""
    bm = bmesh.new(); bm.from_mesh(me)
    if planar:
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0006)
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1.0), use_dissolve_boundaries=False, verts=bm.verts[:], edges=bm.edges[:], delimit={"MATERIAL"})
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me); bm.free()

def pack_tiles(objs, px, pad=3):
    """Per-object square tiles (sized by surface area), shelf-packed into the atlas."""
    areas = [max(1e-4, sum(p.area for p in o.data.polygons)) * (1.8 if o.get("furn") else 1.0) for o in objs]
    order = sorted(range(len(objs)), key=lambda i: -areas[i])
    def fits(k):
        side = [max(10 / px, k * math.sqrt(a)) for a in areas]
        x = y = row = 0.0; place = {}
        for i in order:
            s_ = side[i]
            if x + s_ > 1.0: x = 0.0; y += row; row = 0.0
            if y + s_ > 1.0: return None
            place[i] = (x, y, s_); x += s_; row = max(row, s_)
        return place
    lo, hi = 0.0, 1.0
    while fits(hi): hi *= 2
    for _ in range(40):
        mid = (lo + hi) / 2
        if fits(mid): lo = mid
        else: hi = mid
    place = fits(lo); m = pad / px
    for i, o in enumerate(objs):
        x0, y0, s_ = place[i]; lay = o.data.uv_layers["LM"].data
        for d in lay:
            u, v = d.uv
            d.uv = (x0 + m + u * (s_ - 2 * m), y0 + m + v * (s_ - 2 * m))
    log("packed", len(objs), "texels/m", round(lo * px, 1))

def apply_mods(ob):
    bpy.context.view_layer.update()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()), preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get())
    old = ob.data; ob.modifiers.clear(); ob.data = me2; bpy.data.meshes.remove(old)

STATE = {}
def step_copy():
    dg = bpy.context.evaluated_depsgraph_get()
    col = bpy.data.collections.get("MOOD2") or bpy.data.collections.new("MOOD2")
    if col.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(col)
    for o in list(col.objects): bpy.data.objects.remove(o, do_unlink=True)
    matcopy = {}; made = {"S": [], "L": [], "R": []}; tb = ta = 0
    for o, atlas, room in pick():
        ev = o.evaluated_get(dg)
        try: me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=False, depsgraph=dg)
        except Exception as e: log("skip", o.name, e); continue
        if not me.polygons: bpy.data.meshes.remove(me); continue
        me.transform(o.matrix_world)
        n = sum(len(p.vertices) - 2 for p in me.polygons); tb += n
        no = bpy.data.objects.new(o.name, me); col.objects.link(no)
        no["atlas"] = atlas; no["src"] = o.name; no["room"] = room
        if atlas != "S" and not o.name.startswith(BUILTIN): no["furn"] = 1   # furniture: a larger share of the lightmap
        for k in ("circuit", "emit_full", "full"):
            if k in o.keys(): no[k] = o[k]
        mn_, mx_ = bbox(no); diag = (mx_ - mn_).length
        cap = next(c for lim, c in CAPS if diag < lim)
        if n > cap and not o.name.startswith(("Wall", "Floor", "Ceiling")):
            ref = no.copy(); ref.data = me.copy(); col.objects.link(ref)      # the full mesh, to copy the normals back from
            # 1. flat areas: dissolve, lossless (keeps UV seams, sharp edges and materials apart)
            d = no.modifiers.new("Flat", "DECIMATE"); d.decimate_type = "DISSOLVE"; d.angle_limit = math.radians(0.5)
            d.delimit = {"UV", "SHARP", "MATERIAL", "SEAM"}
            apply_mods(no)
            m2 = sum(len(p.vertices) - 2 for p in no.data.polygons)
            # 2. only if still over budget: collapse, but never below 30 % of the original
            if m2 > cap:
                d = no.modifiers.new("Simplify", "DECIMATE"); d.ratio = min(1.0, max(MIN_RATIO * n / m2, cap / m2)); d.use_collapse_triangulate = True
                apply_mods(no)
            # 3. the model's own normals back (soft cushions, crisp edges, reflections that follow the surface)
            t = no.modifiers.new("Normals", "DATA_TRANSFER"); t.object = ref; t.use_loop_data = True
            t.data_types_loops = {"CUSTOM_NORMAL"}; t.loop_mapping = "POLYINTERP_NEAREST"
            apply_mods(no)
            ref_me = ref.data; bpy.data.objects.remove(ref, do_unlink=True); bpy.data.meshes.remove(ref_me)
        ta += sum(len(p.vertices) - 2 for p in no.data.polygons)
        for i, m in enumerate(no.data.materials):
            if m is None: continue
            key = (m.name, atlas)
            if key not in matcopy:
                mc = m.copy(); mc.name = f"{m.name}@{atlas}"; matcopy[key] = mc
            no.data.materials[i] = matcopy[key]
        clean(no.data, planar=(atlas == "S" or o.name.startswith(BUILTIN)))
        if not no.data.uv_layers: no.data.uv_layers.new(name="UVMap")
        no.data.uv_layers.new(name="LM")
        made[atlas].append(no)
    STATE["made"] = made; STATE["queue"] = [o for a in made for o in made[a]]; STATE["n"] = len(STATE["queue"])
    log("MOOD2 objects", {k: len(v) for k, v in made.items()}, "tris", tb, "->", ta)

def unwrap(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.hide_set(False); ob.select_set(True); bpy.context.view_layer.objects.active = ob
    ob.data.uv_layers.active = ob.data.uv_layers["LM"]
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.reveal(); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.012, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")

def finish():
    made = STATE["made"]
    for atlas, objs in made.items():
        if objs: pack_tiles(objs, SIZE[atlas])
        for ob in objs: ob.data.uv_layers.active = ob.data.uv_layers[0]; ob.data.uv_layers[0].active_render = True
    # the saved copy: originals hidden from render, the MOOD2 copies in their place
    srcs = [bpy.data.objects.get(o["src"]) for a in made for o in made[a]]
    was = [(s, s.hide_render) for s in srcs if s]
    for s, _ in was: s.hide_render = True
    old = bpy.data.collections.get("MOOD")
    if old: old.hide_render = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(PROJECT, "blender", "dira_mood2.blend"), copy=True)
    for s, v in was: s.hide_render = v
    json.dump({a: [{"name": o.name, "room": o["room"]} for o in made[a]] for a in made}, open(os.path.join(PROJECT, "mood", "objects2.json"), "w"), indent=0)
    log("MOOD PREP2 OK", f"{time.time() - STATE['t0']:.0f}s")

def tick():
    try:
        if "made" not in STATE: step_copy(); return 0.1
        q = STATE["queue"]; t = time.time()
        while q and time.time() - t < 0.5: unwrap(q.pop(0))
        if q:
            if len(q) % 50 < 3: log("unwrap left", len(q))
            return 0.05
        finish(); return None
    except Exception as e:
        import traceback; log("PREP2 ERROR", e, traceback.format_exc()); return None

os.makedirs(os.path.join(PROJECT, "mood"), exist_ok=True)
open(LOG, "w").close()
# the first version's prep hid the living room's originals in this open scene: bring them back
old = bpy.data.collections.get("MOOD")
if old:
    for o in old.objects:
        s = bpy.data.objects.get(o.get("src", ""))
        if s: s.hide_render = False; s.hide_set(False)
    old.hide_render = True; old.hide_viewport = True
STATE["t0"] = time.time()
bpy.app.timers.register(tick, first_interval=0.2)
