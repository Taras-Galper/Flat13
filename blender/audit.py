# Overlap audit: real triangle intersections between furniture groups, and between furniture and walls.
import bpy, bmesh, re
from mathutils.bvhtree import BVHTree
from mathutils import Vector
dg = bpy.context.evaluated_depsgraph_get()

def group_of(o):
    n = re.sub(r"\.\d+$", "", o.name)
    p = o
    while p.parent: p = p.parent
    if p is not o: n = re.sub(r"\.\d+$", "", p.name)
    for k in ("JATTEBO", "STOCKHOLM", "LISTERBY side", "LISTERBY", "BESTA", "HOLMO", "VIDJA", "Pendant", "Column lamp", "Shoe cabinet", "Bench", "Niche",
              "Peninsula", "Base run", "Worktop", "Splash", "Tall column", "Floating shelf", "Screen", "Teak", "NAMMARO", "Lantern", "Coffee", "Side table", "Clay media", "TV"):
        if n.startswith(k): return k
    return n

def world_bvh(o):
    ev = o.evaluated_get(dg)
    try: me = ev.to_mesh()
    except Exception: return None, None
    if me is None or len(me.polygons) == 0: return None, None
    bm = bmesh.new(); bm.from_mesh(me); bm.transform(o.matrix_world); ev.to_mesh_clear()
    mn = Vector((min(v.co.x for v in bm.verts), min(v.co.y for v in bm.verts), min(v.co.z for v in bm.verts)))
    mx = Vector((max(v.co.x for v in bm.verts), max(v.co.y for v in bm.verts), max(v.co.z for v in bm.verts)))
    t = BVHTree.FromBMesh(bm); bm.free(); return t, (mn, mx)

FURN = [o for o in bpy.data.objects if o.type in ("MESH", "CURVE") and any(c.name in ("Interior", "IKEA", "Props", "Fixtures") for c in o.users_collection)]
WALLS = [o for o in bpy.data.objects if o.type in ("MESH", "CURVE") and any(c.name in ("Shell",) for c in o.users_collection) and (o.name.startswith("Wall") or o.name.startswith("Sill") or o.name.startswith("Lintel"))]
data = {}
for o in FURN + WALLS:
    t, bb = world_bvh(o)
    if t: data[o.name] = (t, bb, "WALL" if o in WALLS else group_of(o))
def ov(a, b): return all(a[0][i] < b[1][i] - 1e-4 and b[0][i] < a[1][i] - 1e-4 for i in range(3))
hits = {}
names = list(data)
for i, a in enumerate(names):
    ta, ba, ga = data[a]
    for b in names[i + 1:]:
        tb, bb, gb = data[b]
        if ga == gb or (ga == "WALL" and gb == "WALL") or not ov(ba, bb): continue
        n = len(ta.overlap(tb))
        if n: hits[(ga, gb) if ga < gb else (gb, ga)] = hits.get((ga, gb) if ga < gb else (gb, ga), 0) + n
for (a, b), n in sorted(hits.items(), key=lambda kv: -kv[1]):
    print(f"{n:6d}  {a}  <->  {b}")
print("AUDIT DONE", len(hits), "pairs")
