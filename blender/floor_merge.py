# One floor for the whole flat, instead of a box per room: the room boxes overlapped and each had its own
# lightmap island, so the baked light broke at every joint (dark seams across doorways and room edges).
# The new floor is one flat mesh (the rooms grown under the walls and through the doorways) with ONE
# lightmap island, so the light runs continuously from room to room. Its faces keep a material per
# styling area ("Tile ivory 60x60~living@S"), so a floor sample can still change one room's floor.
# Then the shell atlas is packed again. Run in the background:  blender -b dira_mood2.blend -P floor_merge.py
import bpy, bmesh, json, math, os
from mathutils import Vector

PROJECT = r"C:\Users\grafica\source\repos\dira-landing"
col = bpy.data.collections["MOOD2"]
AREAS = {"living": ["living", "entry", "kitchen", "corridor", "terrace"], "master": ["master", "passage"], "teen": ["mamad"], "office": ["bed3"],
         "toddler": ["bed4"], "baths": ["wc", "bath", "laundry", "ensuite", "service"]}
AREA_OF = {r: a for a, rs in AREAS.items() for r in rs}
GROW = 0.14      # under the walls and through the doorways
SIZE = 2048

def log(*a):
    msg = " ".join(str(x) for x in a); print(msg)
    with open(os.path.join(PROJECT, "mood", "floor_merge.log"), "a", encoding="utf-8") as fh: fh.write(msg + "\n")

old = [o for o in col.objects if o.name.startswith("Floor ") and o.get("room") not in ("terrace", "") ]
rects = []
for o in old:
    xs = [v.co.x for v in o.data.vertices]; ys = [v.co.y for v in o.data.vertices]; zs = [v.co.z for v in o.data.vertices]
    rects.append(dict(x0=min(xs), x1=max(xs), y0=min(ys), y1=max(ys), z=max(zs), room=o["room"], mat=o.data.materials[0]))
log("floors", len(old), [r["room"] for r in rects])
Z = max(r["z"] for r in rects)

# the grid of all the grown rectangles' edges; keep the cells inside any of them
xs = sorted({round(v, 4) for r in rects for v in (r["x0"] - GROW, r["x1"] + GROW)})
ys = sorted({round(v, 4) for r in rects for v in (r["y0"] - GROW, r["y1"] + GROW)})
def owner(cx, cy):
    best, bd = None, 1e9
    for r in rects:
        dx = max(r["x0"] - cx, 0, cx - r["x1"]); dy = max(r["y0"] - cy, 0, cy - r["y1"]); d = math.hypot(dx, dy)
        if d < bd - 1e-6: best, bd = r, d
    return best if bd <= GROW + 1e-4 else None

mats, slots = {}, []
def slot(r):
    name = f"{r['mat'].name.replace('@S', '')}~{AREA_OF.get(r['room'], 'living')}@S"
    if name not in mats:
        m = r["mat"].copy(); m.name = name; mats[name] = len(slots); slots.append(m)
    return mats[name]

bm = bmesh.new(); vid = {}
def vert(i, j):
    if (i, j) not in vid: vid[(i, j)] = bm.verts.new((xs[i], ys[j], Z))
    return vid[(i, j)]
for i in range(len(xs) - 1):
    for j in range(len(ys) - 1):
        cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
        r = owner(cx, cy)
        if r is None: continue
        f = bm.faces.new((vert(i, j), vert(i + 1, j), vert(i + 1, j + 1), vert(i, j + 1)))
        f.material_index = slot(r)
bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1), use_dissolve_boundaries=False, verts=bm.verts[:], edges=bm.edges[:], delimit={"MATERIAL"})
me = bpy.data.meshes.new("Floor flat")
bm.to_mesh(me); bm.free()
for m in slots: me.materials.append(m)
# texture UVs (the page maps the tiles in world space anyway) and ONE lightmap island: the plan itself
minx, maxx, miny, maxy = xs[0], xs[-1], ys[0], ys[-1]; S = max(maxx - minx, maxy - miny)
uv = me.uv_layers.new(name="UVMap"); lm = me.uv_layers.new(name="LM")
for p in me.polygons:
    for li in p.loop_indices:
        co = me.vertices[me.loops[li].vertex_index].co
        uv.data[li].uv = (co.x / 1.2, co.y / 1.2)
        lm.data[li].uv = ((co.x - minx) / S, (co.y - miny) / S)
me.uv_layers.active = uv; uv.active_render = True
fo = bpy.data.objects.new("Floor flat", me); col.objects.link(fo)
fo["atlas"] = "S"; fo["src"] = "Floor flat"; fo["room"] = ""
for o in old: bpy.data.objects.remove(o, do_unlink=True)
log("floor faces", len(me.polygons), "materials", list(mats))

# pack the shell atlas again: every object's lightmap islands back to 0..1, then square tiles by size
S_objs = [o for o in col.objects if o.get("atlas") == "S" and o.type == "MESH"]
for o in S_objs:
    if o is fo: continue
    lay = o.data.uv_layers["LM"].data
    us = [d.uv.x for d in lay]; vs = [d.uv.y for d in lay]
    if not us: continue
    u0, v0 = min(us), min(vs); e = max(max(us) - u0, max(vs) - v0, 1e-6)
    for d in lay: d.uv = ((d.uv.x - u0) / e, (d.uv.y - v0) / e)
def area(o):
    if o is fo: return S * S            # the floor keeps the same texel density as the walls
    return max(1e-4, sum(p.area for p in o.data.polygons))
def pack_tiles(objs, px, pad=3):
    areas = [area(o) for o in objs]
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
        x0, y0, s_ = place[i]
        for d in o.data.uv_layers["LM"].data:
            u, v = d.uv
            d.uv = (x0 + m + u * (s_ - 2 * m), y0 + m + v * (s_ - 2 * m))
    log("packed", len(objs), "texels/m", round(lo * px, 1))
pack_tiles(S_objs, SIZE)
bpy.ops.wm.save_mainfile()
log("FLOOR MERGE OK")
