# Which furniture can be moved in the live page, and what moves together.
# Run in the background on the baking copy:  blender -b dira_mood2.blend -P piece_tag.py
# Every web copy in MOOD2 gets a custom property "piece" (exported to glTF as extras) and the page reads
# mood/pieces.json. A piece is a group of objects standing on the floor (one IKEA product, one bed with its
# frame) plus everything that rests on it (bedding, cushions, toys, books, a bedside lamp).
import bpy, json, os, re, math
import numpy as np

PROJECT = r"C:\Users\grafica\source\repos\dira-landing"
col = bpy.data.collections["MOOD2"]

# built in, part of the architecture, or a light fitting: stays where it is
STATIC = re.compile(r"^(Base run|Worktop|Splash|Tall column|Peninsula|Waterfall|Toe kick|Floating shelf|Niche|Shoe cabinet|Clay media|Curtain pocket|Screen|Seam|"
                    r"Wardrobe walk|Wall run|Fluted|Hob|Sink|Tap|Bench seat|Bench pad|Coir mat|Office TV|TV|Teen wall mirror|Teen shelf|SKALA|Pendant|"
                    r"Planter|Upstand|Balustrade|Rail|[A-Z]\d+ )|curtain|Curtain", re.I)
CURTAIN = re.compile(r"curtain", re.I)
FLOOR_LAMP = re.compile(r"HOLMO|VIDJA|OKENSAND|floor lamp", re.I)   # their light is baked where they stand
RUG = re.compile(r"rug|LOHALS|runner|LINDKNUD|STAPPSPARV|ARENDE", re.I)
FLOOR_Z = 0.05

def base(name): return re.sub(r"\.\d{3}$", "", name)
def root(o):
    while o.parent: o = o.parent
    return o

items = []
for o in col.objects:
    if o.get("atlas") not in ("L", "R") or o.type != "MESH" or not o.data.vertices: continue
    src = bpy.data.objects.get(o.get("src", ""))
    fam = base(root(src).name) if src else base(o.name)
    v = np.empty(len(o.data.vertices) * 3, np.float32); o.data.vertices.foreach_get("co", v); v = v.reshape(-1, 3)
    mn, mx = v.min(0), v.max(0)
    static = bool(STATIC.match(fam) or STATIC.match(base(o.get("src", o.name))) or CURTAIN.search(fam))
    items.append(dict(o=o, fam=fam, mn=mn, mx=mx, circuit=o.get("circuit"), static=static, room=o.get("room", ""), atlas=o["atlas"]))

# pieces: objects joined when they are parts of one product (same name, touching) or when one rests on
# or sits inside the other (a table top on its legs, bedding on a bed, books in a bookcase, a lamp on a
# bedside table). Rugs stay pieces of their own, or the whole room would join through them.
def is_rug(it): return bool(RUG.search(it["fam"])) or (it["mx"][2] - it["mn"][2] < 0.03 and it["mn"][2] < FLOOR_Z)
def xy_overlap(a, b):
    w = min(a["mx"][0], b["mx"][0]) - max(a["mn"][0], b["mn"][0]); d = min(a["mx"][1], b["mx"][1]) - max(a["mn"][1], b["mn"][1])
    return max(0.0, w) * max(0.0, d)
def area(a): return max(1e-6, float((a["mx"][0] - a["mn"][0]) * (a["mx"][1] - a["mn"][1])))
def touch(a, b, g=0.02):
    return all(a["mn"][k] - g < b["mx"][k] and b["mn"][k] - g < a["mx"][k] for k in range(3))
def rests(a, b):   # a rests on b, or sits inside it
    if xy_overlap(a, b) < 0.3 * min(area(a), area(b)): return False
    return abs(a["mn"][2] - b["mx"][2]) < 0.04 or (b["mn"][2] + 0.01 < a["mn"][2] < b["mx"][2])
live = [it for it in items if not it["static"]]
par = list(range(len(live)))
def find(i):
    while par[i] != i: par[i] = par[par[i]]; i = par[i]
    return i
for i in range(len(live)):
    for j in range(i + 1, len(live)):
        a, b = live[i], live[j]
        if is_rug(a) != is_rug(b): continue
        if (a["fam"] == b["fam"] and touch(a, b)) or (not is_rug(a) and (rests(a, b) or rests(b, a))):
            par[find(i)] = find(j)
groups = {}
for i, it in enumerate(live): groups.setdefault(find(i), []).append(it)
pieces = []
for g in groups.values():
    mn = np.min([s["mn"] for s in g], 0); mx = np.max([s["mx"] for s in g], 0)
    if mn[2] > FLOOR_Z: continue                      # nothing of it stands on the floor: a wall shelf, a picture
    big = max(g, key=lambda s: float(np.prod(np.maximum(s["mx"] - s["mn"], 0.01))))
    pieces.append(dict(members=list(g), mn=mn, mx=mx, name=big["fam"], room=big["room"], atlas=big["atlas"]))

out = []
pieces.sort(key=lambda p: (p["room"], p["name"], round(float(p["mn"][0]), 2), round(float(p["mn"][1]), 2)))
for k, p in enumerate(pieces):
    pid = f"p{k}"
    floor_lamp = any(m["circuit"] and m["mn"][2] < FLOOR_Z for m in p["members"]) or bool(FLOOR_LAMP.search(p["name"]))
    size = p["mx"] - p["mn"]
    rug = bool(RUG.search(p["name"]) or size[2] < 0.03)
    movable = bool(not floor_lamp and size[0] < 3.2 and size[1] < 3.2)
    for m in p["members"]:
        m["o"]["piece"] = pid
        m["o"]["pmov"] = 1 if movable else 0
        m["o"]["plamp"] = 1 if m["circuit"] else 0
    out.append(dict(id=pid, name=p["name"], room=p["room"], atlas=p["atlas"], rug=rug, movable=movable,
                    cx=round(float(p["mn"][0] + p["mx"][0]) / 2, 3), cy=round(float(p["mn"][1] + p["mx"][1]) / 2, 3),
                    w=round(float(size[0]), 3), d=round(float(size[1]), 3), h=round(float(p["mx"][2]), 3), z0=round(float(p["mn"][2]), 3),
                    n=len(p["members"]), lamp=bool(any(m["circuit"] for m in p["members"]))))
json.dump(out, open(os.path.join(PROJECT, "mood", "pieces.json"), "w", encoding="utf-8"), indent=0, ensure_ascii=False)
bpy.ops.wm.save_mainfile()
print("PIECES", len(out), "movable", sum(p["movable"] for p in out), "rugs", sum(p["rug"] for p in out))
for p in out: print(p["id"], p["room"], p["name"], p["movable"], p["rug"], p["w"], p["d"], p["h"], p["n"])
