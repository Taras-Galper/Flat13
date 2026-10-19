# Builds the Japandi proof scene (entry + living, with kitchen and balcony around it) in Blender 5.x.
# Plan metres map straight to Blender: x east, y north, z up.
# Run inside Blender:  exec(open(r"<project>\blender\build_scene.py").read())
import bpy, bmesh, json, math, os, random, urllib.request
from mathutils import Vector, Matrix

PROJECT = r"C:\Users\grafica\source\repos\dira-landing"
TEX = os.path.join(PROJECT, "assets", "tex")
BTEX = os.path.join(PROJECT, "blender", "tex")
MODELS = os.path.join(PROJECT, "blender", "models")
H = 2.70
HC = 2.62          # dropped gypsum ceiling in the public rooms (lighting design)
DROP = ("entry", "living", "kitchen", "corridor")
UA = {"User-Agent": "dira-landing/1.0"}
random.seed(7)

def load_js(path):
    s = open(path, encoding="utf-8").read()
    return json.loads(s[s.index("{"): s.rindex(";")])
DATA = load_js(os.path.join(PROJECT, "js", "data.js"))
SPEC = json.load(open(os.path.join(PROJECT, "design", "japandi.json"), encoding="utf-8"))

# ------------------------------------------------------------------ reset
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
for c in list(bpy.data.collections): bpy.data.collections.remove(c)
for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.curves, bpy.data.images, bpy.data.node_groups):
    for b in list(blk):
        try: blk.remove(b)
        except Exception: pass
scene = bpy.context.scene
COLS = {}
def col(name):
    if name not in COLS:
        c = bpy.data.collections.new(name); scene.collection.children.link(c); COLS[name] = c
    return COLS[name]

# ------------------------------------------------------------------ downloads (Poly Haven, CC0)
def ph_texture(asset, res="1k"):
    d = os.path.join(TEX, asset)
    if all(os.path.exists(os.path.join(d, f)) for f in ("diff.jpg", "nor.jpg", "rough.jpg")): return d
    os.makedirs(d, exist_ok=True)
    files = json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.polyhaven.com/files/{asset}", headers=UA), timeout=30))
    for key, name in (("Diffuse", "diff"), ("nor_gl", "nor"), ("Rough", "rough")):
        url = files[key][res]["jpg"]["url"]
        open(os.path.join(d, name + ".jpg"), "wb").write(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
    return d

def ph_model(asset, res="1k"):
    d = os.path.join(MODELS, asset); main = os.path.join(d, asset + ".gltf")
    if os.path.exists(main): return main
    os.makedirs(d, exist_ok=True)
    files = json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.polyhaven.com/files/{asset}", headers=UA), timeout=30))
    g = files["gltf"][res]["gltf"]
    open(main, "wb").write(urllib.request.urlopen(urllib.request.Request(g["url"], headers=UA), timeout=60).read())
    for rel, info in g.get("include", {}).items():
        p = os.path.join(d, rel.replace("/", os.sep)); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(urllib.request.urlopen(urllib.request.Request(info["url"], headers=UA), timeout=60).read())
    return main

# ------------------------------------------------------------------ materials
def img(path, color=True):
    im = bpy.data.images.load(path, check_existing=True)
    im.colorspace_settings.name = "sRGB" if color else "Non-Color"
    return im

def new_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (300, 0)
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m, nt, bsdf

def coords(nt, size, rot=0.0, offset=(0, 0, 0), space="Object"):
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-900, 0)
    mp = nt.nodes.new("ShaderNodeMapping"); mp.location = (-700, 0)
    mp.inputs["Scale"].default_value = (1 / size, 1 / size, 1 / size)
    mp.inputs["Rotation"].default_value = (0, 0, rot)
    mp.inputs["Location"].default_value = offset
    nt.links.new(tc.outputs[space], mp.inputs[0])
    return mp.outputs[0]

def textured(name, folder, size, *, rot=0.0, offset=(0, 0, 0), tint=None, rough_mul=1.0, nor_strength=1.0,
             nor_file="nor.jpg", proj="BOX", no_diffuse=False, base=None, sheen=0.0, value=1.0, sat=1.0, rough_add=0.0):
    m, nt, b = new_mat(name)
    uv = coords(nt, size, rot, offset)
    def teximg(f, color):
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = img(os.path.join(folder, f), color)
        t.projection = proj; t.projection_blend = 0.25 if proj == "BOX" else 0
        nt.links.new(uv, t.inputs[0]); return t
    if not no_diffuse:
        d = teximg("diff.jpg", True); src = d.outputs[0]
        if value != 1.0 or sat != 1.0:
            hs = nt.nodes.new("ShaderNodeHueSaturation"); hs.inputs["Value"].default_value = value; hs.inputs["Saturation"].default_value = sat
            nt.links.new(src, hs.inputs["Color"]); src = hs.outputs[0]
        if tint:
            mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs[0].default_value = 1.0
            nt.links.new(src, mx.inputs[6]); mx.inputs[7].default_value = (*tint, 1); src = mx.outputs[2]
        nt.links.new(src, b.inputs["Base Color"])
    elif base:
        b.inputs["Base Color"].default_value = (*base, 1)
    r = teximg("rough.jpg", False)
    mr = nt.nodes.new("ShaderNodeMath"); mr.operation = "MULTIPLY_ADD"; mr.inputs[1].default_value = rough_mul; mr.inputs[2].default_value = rough_add
    nt.links.new(r.outputs[0], mr.inputs[0]); nt.links.new(mr.outputs[0], b.inputs["Roughness"])
    nf = nor_file if os.path.exists(os.path.join(folder, nor_file)) else ("nor.png" if os.path.exists(os.path.join(folder, "nor.png")) else "nor.jpg")
    n = teximg(nf, False)
    nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs[0].default_value = nor_strength
    nt.links.new(n.outputs[0], nm.inputs[1]); nt.links.new(nm.outputs[0], b.inputs["Normal"])
    if sheen:
        b.inputs["Sheen Weight"].default_value = sheen; b.inputs["Sheen Roughness"].default_value = 0.5
    return m

def flat(name, rgb, rough=0.5, metal=0.0, spec=0.5, sheen=0.0):
    m, nt, b = new_mat(name)
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if sheen: b.inputs["Sheen Weight"].default_value = sheen
    return m

def srgb(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)

def plaster(name, c1, c2, nor_folder, scale=1.6, nor_strength=0.25):
    m, nt, b = new_mat(name)
    uv = coords(nt, 1.0)
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = scale; nz.inputs["Detail"].default_value = 6
    nt.links.new(uv, nz.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].position = 0.7; ramp.color_ramp.elements[1].color = (*c2, 1)
    nt.links.new(nz.outputs[0], ramp.inputs[0]); nt.links.new(ramp.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.92
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img(os.path.join(nor_folder, "nor.jpg"), False); t.projection = "BOX"; t.projection_blend = 0.3
    nt.links.new(coords(nt, 2.0), t.inputs[0])
    nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs[0].default_value = nor_strength
    nt.links.new(t.outputs[0], nm.inputs[1]); nt.links.new(nm.outputs[0], b.inputs["Normal"])
    return m

def stone(name, c1, c2, pits=True, rough=0.55):
    m, nt, b = new_mat(name)
    uv = coords(nt, 1.0)
    w = nt.nodes.new("ShaderNodeTexWave"); w.wave_type = "BANDS"; w.inputs["Scale"].default_value = 3.0
    w.inputs["Distortion"].default_value = 6; w.inputs["Detail"].default_value = 4
    nt.links.new(uv, w.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1); ramp.color_ramp.elements[1].color = (*c2, 1)
    nt.links.new(w.outputs[1], ramp.inputs[0]); src = ramp.outputs[0]
    if pits:
        v = nt.nodes.new("ShaderNodeTexVoronoi"); v.inputs["Scale"].default_value = 60
        nt.links.new(uv, v.inputs[0])
        th = nt.nodes.new("ShaderNodeMath"); th.operation = "LESS_THAN"; th.inputs[1].default_value = 0.08
        nt.links.new(v.outputs[0], th.inputs[0])
        mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"
        nt.links.new(th.outputs[0], mx.inputs[0]); nt.links.new(src, mx.inputs[6]); mx.inputs[7].default_value = (0.75, 0.7, 0.62, 1)
        src = mx.outputs[2]
        bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.2
        nt.links.new(th.outputs[0], bump.inputs["Height"]); nt.links.new(bump.outputs[0], b.inputs["Normal"])
    nt.links.new(src, b.inputs["Base Color"]); b.inputs["Roughness"].default_value = rough
    return m

def glass_mat(name, tint=(0.95, 0.97, 0.97)):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    gl = nt.nodes.new("ShaderNodeBsdfGlass"); gl.inputs["Roughness"].default_value = 0.0; gl.inputs["Color"].default_value = (*tint, 1)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent"); tr.inputs[0].default_value = (*tint, 1)
    lp = nt.nodes.new("ShaderNodeLightPath"); mx = nt.nodes.new("ShaderNodeMixShader")
    mx2 = nt.nodes.new("ShaderNodeMixShader"); mx2.inputs[0].default_value = 0.85
    nt.links.new(gl.outputs[0], mx2.inputs[1]); nt.links.new(tr.outputs[0], mx2.inputs[2])     # thin pane: mostly transparent, some reflection
    nt.links.new(lp.outputs["Is Shadow Ray"], mx.inputs[0])
    nt.links.new(mx2.outputs[0], mx.inputs[1]); nt.links.new(tr.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs[0])
    return m

def translucent(name, rgb, trans=0.55, nor_folder=None, nor_size=0.27, alpha=1.0, emit=None):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    df = nt.nodes.new("ShaderNodeBsdfDiffuse"); df.inputs[0].default_value = (*rgb, 1)
    tl = nt.nodes.new("ShaderNodeBsdfTranslucent"); tl.inputs[0].default_value = (*rgb, 1)
    mx = nt.nodes.new("ShaderNodeMixShader"); mx.inputs[0].default_value = trans
    nt.links.new(df.outputs[0], mx.inputs[1]); nt.links.new(tl.outputs[0], mx.inputs[2]); sh = mx.outputs[0]
    if nor_folder:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = img(os.path.join(nor_folder, "nor.jpg"), False); t.projection = "BOX"
        nt.links.new(coords(nt, nor_size), t.inputs[0])
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs[0].default_value = 0.6
        nt.links.new(t.outputs[0], nm.inputs[1]); nt.links.new(nm.outputs[0], df.inputs["Normal"]); nt.links.new(nm.outputs[0], tl.inputs["Normal"])
    if alpha < 1.0:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent"); m2 = nt.nodes.new("ShaderNodeMixShader"); m2.inputs[0].default_value = alpha
        nt.links.new(tr.outputs[0], m2.inputs[1]); nt.links.new(sh, m2.inputs[2]); sh = m2.outputs[0]
    nt.links.new(sh, out.inputs[0])
    return m

def emissive(name, rgb, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*rgb, 1); e.inputs[1].default_value = strength; nt.links.new(e.outputs[0], out.inputs[0])
    return m

def image_mat(name, path, rough=0.9):
    m, nt, b = new_mat(name)
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img(path, True)
    tc = nt.nodes.new("ShaderNodeTexCoord"); nt.links.new(tc.outputs["UV"], t.inputs[0])
    nt.links.new(t.outputs[0], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = rough
    return m

for a in ("hessian_230", "plastered_wall_04", "beige_wall_001"):
    try: ph_texture(a)
    except Exception as e: print("texture download failed", a, e)

M = {}
M["ivory"] = textured("Tile ivory 60x60", os.path.join(BTEX, "tile_ivory"), 1.2, offset=(-4.41 / 1.2, -9.25 / 1.2, 0), nor_file="nor.png", proj="FLAT", nor_strength=0.6)
M["wood_ew"] = textured("Tile wood 50x15 E-W", os.path.join(BTEX, "tile_wood"), 1.5, nor_file="nor.png", proj="FLAT", nor_strength=0.8)
M["wood_ns"] = textured("Tile wood 50x15 N-S", os.path.join(BTEX, "tile_wood"), 1.5, rot=math.pi / 2, nor_file="nor.png", proj="FLAT", nor_strength=0.8)
M["wall"] = plaster("Limewash", srgb("#E7E0D4"), srgb("#EEE8DE"), os.path.join(TEX, "painted_plaster_wall"), scale=1.4)
M["ceiling"] = plaster("Ceiling", srgb("#EDE8E0"), srgb("#F1EDE6"), os.path.join(TEX, "painted_plaster_wall"), scale=0.8, nor_strength=0.1)
M["clay"] = plaster("Clay plaster", srgb("#9A8A76"), srgb("#A89884"), os.path.join(TEX, "plastered_wall_04"), scale=2.2, nor_strength=0.5)
M["oak"] = textured("Rift oak", os.path.join(TEX, "white_oak_veneer"), 0.6, value=1.05, sat=0.85, nor_strength=0.4)
M["oak_light"] = textured("Oak light", os.path.join(TEX, "white_oak_veneer"), 0.6, value=1.15, sat=0.7, nor_strength=0.3)
M["smoked"] = textured("Smoked oak", os.path.join(TEX, "white_oak_veneer"), 0.6, value=0.38, sat=0.9, nor_strength=0.4)
M["teak"] = textured("Teak", os.path.join(TEX, "white_oak_veneer"), 0.6, value=0.8, sat=1.15, tint=(0.95, 0.82, 0.68), nor_strength=0.5)
M["boucle"] = textured("Boucle oatmeal", os.path.join(TEX, "curly_teddy_natural"), 0.34, nor_strength=1.0, sheen=0.4, value=1.08, sat=0.75)
M["wool"] = textured("Charcoal wool", os.path.join(TEX, "poly_wool_herringbone"), 0.27, nor_strength=0.9, sheen=0.3, value=0.62, sat=0.35, tint=(1.0, 0.96, 0.9))
M["linen"] = textured("Linen sage", os.path.join(TEX, "rough_linen"), 0.27, no_diffuse=True, base=srgb("#9AA08A"), nor_strength=0.8, sheen=0.3)
M["linen_oat"] = textured("Linen oat", os.path.join(TEX, "rough_linen"), 0.27, no_diffuse=True, base=srgb("#DCD2C2"), nor_strength=0.8, sheen=0.3)
M["outdoor"] = textured("Outdoor fabric", os.path.join(TEX, "rough_linen"), 0.27, no_diffuse=True, base=srgb("#E2D9CA"), nor_strength=0.7)
M["rug"] = textured("Wool jute rug", os.path.join(TEX, "hessian_230"), 0.25, nor_strength=1.2, value=1.35, sat=0.55, sheen=0.5)
M["coir"] = textured("Coir mat", os.path.join(TEX, "hessian_230"), 0.12, nor_strength=1.5, value=0.9, sat=1.1, tint=(0.85, 0.68, 0.45))
M["travertine"] = stone("Travertine", srgb("#D8CBB6"), srgb("#E6DCCB"))
M["limestone"] = stone("Limestone", srgb("#DCD3C3"), srgb("#E4DCCF"), pits=False, rough=0.45)
M["steel"] = flat("Blackened steel", srgb("#1F1E1D"), 0.45, 0.6)
M["frame"] = flat("Window frame", srgb("#2A2826"), 0.4, 0.5)
M["screen"] = flat("TV glass", (0.004, 0.004, 0.005), 0.08, 0.0)
M["glass"] = glass_mat("Glass", tint=(0.74, 0.77, 0.77))
M["balustrade"] = glass_mat("Balustrade glass", tint=(0.8, 0.84, 0.84))
M["curtain"] = translucent("Linen sheer", srgb("#F2EDE4"), 0.65, os.path.join(TEX, "rough_linen"), alpha=0.92)
M["washi"] = translucent("Washi", srgb("#F3EBDC"), 0.7)
M["ceramic"] = flat("Ceramic white", srgb("#F2EFE9"), 0.25)
M["clay_pot"] = flat("Clay pot", srgb("#9C7A62"), 0.85)
M["leaf"] = flat("Olive leaf", srgb("#5F6A48"), 0.5)
M["leaf"].node_tree.nodes["Principled BSDF"].inputs["Subsurface Weight"].default_value = 0.15
M["trunk"] = flat("Olive bark", srgb("#6A5D50"), 0.9)
M["soil"] = flat("Soil", srgb("#3B3129"), 1.0)
M["paper"] = flat("Book linen", srgb("#CFC5B4"), 0.8)
M["paper2"] = flat("Book clay", srgb("#9A8A78"), 0.8)
M["art"] = image_mat("Sumi canvas", os.path.join(BTEX, "art", "sumi.jpg"))
M["lobby"] = flat("Lobby stone", srgb("#D7D1C6"), 0.4)
M["slab"] = flat("Exterior render", srgb("#E6E0D5"), 0.85)
M["sea"] = flat("Sea", srgb("#2F5266"), 0.08)
M["land"] = flat("Land", srgb("#B9AE9A"), 1.0)
M["city"] = flat("City stone", srgb("#E6DECF"), 0.8)
M["hills"] = flat("Far hills", srgb("#9DA6AE"), 1.0)
M["warm_light"] = emissive("Warm glow", (1.0, 0.72, 0.42), 8.0)

# ------------------------------------------------------------------ geometry helpers
def obj_from_bm(name, bm, mat, coll="Interior"):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); col(coll).objects.link(o)
    if mat: me.materials.append(mat)
    return o

def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.0, seg=3, coll="Interior", rot_z=0.0, pivot=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    if bevel >= 0.02:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=6, use_grid_fill=True)
    bmesh.ops.scale(bm, vec=(x1 - x0, y1 - y0, z1 - z0), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), verts=bm.verts)
    o = obj_from_bm(name, bm, mat, coll)
    if bevel > 0:
        mod = o.modifiers.new("Bevel", "BEVEL"); mod.width = bevel; mod.segments = seg; mod.limit_method = "ANGLE"; mod.harden_normals = False
        o.data.shade_smooth() if seg > 2 else None
        if seg > 2:
            wn = o.modifiers.new("WN", "WEIGHTED_NORMAL"); wn.keep_sharp = True
    return o

def recenter(o):
    me = o.data; c = sum((v.co for v in me.vertices), Vector()) / len(me.vertices)
    me.transform(Matrix.Translation(-c)); o.location = c; return o

def cushion(name, x0, x1, y0, y1, z0, z1, mat, r=0.05, puff=0.012, coll="Interior"):
    r = min(r, 0.035)
    o = box(name, x0, x1, y0, y1, z0, z1, mat, bevel=r, seg=6, coll=coll)
    if puff > 0:
        # a slight crown on the top face only: tailored, not pebble-like
        me = o.data; zt = max(v.co.z for v in me.vertices)
        cx = sum(v.co.x for v in me.vertices) / len(me.vertices); cy = sum(v.co.y for v in me.vertices) / len(me.vertices)
        hx = (x1 - x0) / 2; hy = (y1 - y0) / 2
        for v in me.vertices:
            if v.co.z > zt - 1e-4:
                u = 1 - min(1, abs(v.co.x - cx) / hx) ** 2; w = 1 - min(1, abs(v.co.y - cy) / hy) ** 2
                v.co.z += puff * u * w
    o.data.shade_smooth()
    return o

def cyl(name, cx, cy, r, z0, z1, mat, seg=48, r2=None, bevel=0.004, coll="Interior"):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=(r if r2 is None else r2), depth=z1 - z0)
    bmesh.ops.translate(bm, vec=(cx, cy, (z0 + z1) / 2), verts=bm.verts)
    o = obj_from_bm(name, bm, mat, coll)
    if bevel:
        mod = o.modifiers.new("Bevel", "BEVEL"); mod.width = bevel; mod.segments = 2; mod.limit_method = "ANGLE"
    o.data.shade_smooth()
    o.modifiers.new("WN", "WEIGHTED_NORMAL").keep_sharp = True
    return o

def prism(name, poly, holes, z0, z1, mat, coll="Shell"):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "2D"; cu.fill_mode = "BOTH"
    for ring in [poly] + holes:
        sp = cu.splines.new("POLY"); sp.points.add(len(ring) - 1)
        for i, (x, y) in enumerate(ring): sp.points[i].co = (x, y, 0, 1)
        sp.use_cyclic_u = True
    cu.extrude = (z1 - z0) / 2
    o = bpy.data.objects.new(name, cu); col(coll).objects.link(o); o.location.z = (z0 + z1) / 2
    o.data.materials.append(mat)
    return o

# ------------------------------------------------------------------ shell
for i, w in enumerate(DATA["walls"]):
    prism(f"Wall {i:02d}", w["outer"], w["holes"], 0.0, H, M["wall"])
for i, o in enumerate(DATA["openings"]):
    x0, x1, y0, y1 = o["rect"]; along_x = (x1 - x0) >= (y1 - y0)
    if o["sill"] > 0.001: box(f"Sill {i}", x0, x1, y0, y1, 0, o["sill"], M["wall"], coll="Shell")
    if o["head"] < H: box(f"Lintel {i}", x0, x1, y0, y1, o["head"], H, M["wall"], coll="Shell")
    z0, z1, f = o["sill"], o["head"], 0.05
    c = (y0 + y1) / 2 if along_x else (x0 + x1) / 2
    a0, a1 = (x0, x1) if along_x else (y0, y1)
    def B(p0, p1, q0, q1, h0, h1, mat, nm):
        return box(nm, p0, p1, q0, q1, h0, h1, mat, coll="Openings") if along_x else box(nm, q0, q1, p0, p1, h0, h1, mat, coll="Openings")
    if o["kind"] in ("window", "slider", "glassdoor"):
        if o["kind"] == "slider":
            mid = (a0 + a1) / 2
            for k, (p0, p1, off) in enumerate([(a0, mid + 0.05, -0.035), (mid - 0.05, a1, 0.035)]):
                B(p0, p1, c + off - .03, c + off + .03, z0, z0 + f, M["frame"], f"Slider frame {i}{k}a")
                B(p0, p1, c + off - .03, c + off + .03, z1 - f, z1, M["frame"], f"Slider frame {i}{k}b")
                B(p0, p0 + f, c + off - .03, c + off + .03, z0, z1, M["frame"], f"Slider frame {i}{k}c")
                B(p1 - f, p1, c + off - .03, c + off + .03, z0, z1, M["frame"], f"Slider frame {i}{k}d")
                B(p0 + f, p1 - f, c + off - .004, c + off + .004, z0 + f, z1 - f, M["glass"], f"Slider glass {i}{k}")
        else:
            B(a0, a1, c - .03, c + .03, z0, z0 + f, M["frame"], f"Frame {i}a"); B(a0, a1, c - .03, c + .03, z1 - f, z1, M["frame"], f"Frame {i}b")
            B(a0, a0 + f, c - .03, c + .03, z0, z1, M["frame"], f"Frame {i}c"); B(a1 - f, a1, c - .03, c + .03, z0, z1, M["frame"], f"Frame {i}d")
            if a1 - a0 > 1.25: B((a0 + a1) / 2 - .025, (a0 + a1) / 2 + .025, c - .03, c + .03, z0, z1, M["frame"], f"Mullion {i}")
            B(a0 + f, a1 - f, c - .004, c + .004, z0 + f, z1 - f, M["glass"], f"Glass {i}")
            if o["sill"] > 0.3:
                q0, q1 = (y0, y1) if along_x else (x0, x1)
                B(a0, a1, q0 - 0.03, q1 + 0.03, z0 - 0.03, z0, M["limestone"], f"Window sill {i}")
    else:
        T = (y1 - y0) if along_x else (x1 - x0)
        jw = 0.04; fm = M["oak"]
        B(a0, a0 + jw, c - T / 2 - .01, c + T / 2 + .01, 0, o["head"], fm, f"Jamb {i}a"); B(a1 - jw, a1, c - T / 2 - .01, c + T / 2 + .01, 0, o["head"], fm, f"Jamb {i}b")
        B(a0, a1, c - T / 2 - .01, c + T / 2 + .01, o["head"] - jw, o["head"], fm, f"Head {i}")
        hx, hy = o["hinge"]; hA = hx if along_x else hy
        sign = 1 if abs(hA - a0) < abs(hA - a1) else -1
        hA = a0 + jw if sign > 0 else a1 - jw
        L = (a1 - a0) - 2 * jw - 0.01; t = 0.045
        sx, sy = o["swing"]
        hp = (hA, c) if along_x else (c, hA)
        # leaf open at ~90° along the swing direction (entry door drawn open too: the camera walks in)
        lx0, lx1 = sorted([hp[0], hp[0] + sx * L]) if sx else (hp[0] - t / 2, hp[0] + t / 2)
        ly0, ly1 = sorted([hp[1], hp[1] + sy * L]) if sy else (hp[1] - t / 2, hp[1] + t / 2)
        if sx: ly0, ly1 = hp[1] - t / 2, hp[1] + t / 2
        if sy: lx0, lx1 = hp[0] - t / 2, hp[0] + t / 2
        leaf = box(f"Door leaf {o['room']}", lx0, lx1, ly0, ly1, 0.01, o["head"] - jw - 0.005, M["oak_light"] if o["kind"] == "entry" else M["wall"], bevel=0.003, seg=2, coll="Openings")

# floors
for room, r, fin in SPEC["zones"]:
    x0, x1, y0, y1 = r
    if fin == "woodtile": mat = M["wood_ns"] if room == "wc" else M["wood_ew"]; top = -0.02 if room == "terrace" else 0.0
    elif fin in ("ivory",): mat, top = M["ivory"], 0.0
    else: mat, top = M["lobby"], 0.0
    box(f"Floor {room}", x0, x1, y0, y1, top - 0.03, top, mat, coll="Floors")
for s in DATA["slabs"]:
    prism("Slab", s, [], -0.33, -0.031, M["slab"], coll="Shell")
# ceilings (interior) + the balcony above ours
for room, r, fin in SPEC["zones"]:
    if room in ("terrace", "service"): continue
    x0, x1, y0, y1 = r
    box(f"Ceiling {room}", x0, x1, y0, y1, HC if room in DROP else H, H + 0.2, M["ceiling"], coll="Ceilings")
box("Balcony above", -1.98, 8.07, 9.55, 13.25, H, H + 0.30, M["slab"], coll="Shell")      # next floor's balcony: sits on our walls
for s_ in DATA["slabs"]:
    prism("Slab above", s_, [], H + 0.004, H + 0.30, M["slab"], coll="Shell")                   # floor slab of the apartment above
box("Curtain pocket", 4.15, 7.77, 9.0, 9.25, H - 0.12, H, M["ceiling"], coll="Ceilings")
# balcony edge: upstand, glass balustrade, rail
box("Balcony nose", -1.98, 8.07, 12.98, 13.25, -0.33, 0.0, M["slab"], coll="Shell")
box("Upstand", -1.73, 7.8, 12.98, 13.18, -0.02, 0.10, M["slab"], coll="Shell")
box("Balustrade", -1.73, 7.8, 13.06, 13.08, 0.10, 1.08, M["balustrade"], coll="Shell")
box("Rail", -1.73, 7.8, 13.04, 13.10, 1.08, 1.12, M["frame"], coll="Shell")

# ------------------------------------------------------------------ furniture (entry, living, kitchen, balcony)
F = [f for f in SPEC["furniture"] if f["room"] in ("entry", "living", "kitchen", "terrace")]   # bedrooms: bedrooms.py
def R(f): return f["rect"]
def plant_fit(asset, loc, height, rot_z=0.0):
    """Import a Poly Haven model and scale it so its height is `height`, standing on loc."""
    try: p = ph_model(asset)
    except Exception as e: print("model download failed", asset, e); return
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=p)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        for c in list(o.users_collection): c.objects.unlink(o)
        col("Props").objects.link(o)
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
    zmin = min(p.z for p in pts); zmax = max(p.z for p in pts)
    cx = (min(p.x for p in pts) + max(p.x for p in pts)) / 2; cy = (min(p.y for p in pts) + max(p.y for p in pts)) / 2
    k = height / max(1e-6, zmax - zmin)
    for r in [o for o in new if o.parent is None]:
        r.location = Vector((loc[0] + (r.location.x - cx) * k, loc[1] + (r.location.y - cy) * k, loc[2] + (r.location.z - zmin) * k))
        r.scale = r.scale * k; r.rotation_euler.z += rot_z
exec(open(os.path.join(PROJECT, "blender", "ikea_models.py"), encoding="utf-8").read())

def fluted(name, x0, x1, y0, y1, z0, z1, face, mat, pitch=0.026):
    """Body plus half-round flutes on one face ('-y','+y','-x','+x')."""
    box(name + " body", x0, x1, y0, y1, z0, z1, mat, bevel=0.002, seg=1)
    r = pitch / 2
    if face in ("-y", "+y"):
        n = int((x1 - x0) / pitch); y = y0 if face == "-y" else y1
        for i in range(n):
            cx = x0 + (i + 0.5) * pitch
            c = cyl(f"{name} flute", cx, y, r * 0.95, z0 + 0.01, z1 - 0.01, mat, seg=12, bevel=0)
    else:
        n = int((y1 - y0) / pitch); x = x0 if face == "-x" else x1
        for i in range(n):
            c = cyl(f"{name} flute", x, y0 + (i + 0.5) * pitch, r * 0.95, z0 + 0.01, z1 - 0.01, mat, seg=12, bevel=0)

def sofa(f):
    x0, x1, y0, y1 = R(f)          # faces west: back on the east side
    box("Sofa plinth", x0 + .05, x1 - .05, y0 + .05, y1 - .05, 0.0, 0.07, M["oak"], bevel=0.004)
    cushion("Sofa base", x0, x1, y0, y1, 0.07, 0.24, M["boucle"], r=0.04, puff=0)
    arm = 0.16
    cushion("Sofa arm S", x0 + .02, x1, y0, y0 + arm, 0.24, 0.52, M["boucle"], r=0.07)
    cushion("Sofa arm N", x0 + .02, x1, y1 - arm, y1, 0.24, 0.52, M["boucle"], r=0.07)
    cushion("Sofa back", x1 - .22, x1, y0 + arm, y1 - arm, 0.24, 0.58, M["boucle"], r=0.08)
    seat_w = (y1 - y0 - 2 * arm) / 3
    for k in range(3):
        cy0 = y0 + arm + k * seat_w
        cushion(f"Sofa seat {k}", x0 + .03, x1 - .2, cy0 + .005, cy0 + seat_w - .005, 0.24, 0.38, M["boucle"], r=0.06)
        o = recenter(cushion(f"Sofa back cushion {k}", x1 - .40, x1 - .20, cy0 + .02, cy0 + seat_w - .02, 0.38, 0.72, M["boucle"], r=0.08))
        o.rotation_euler.y = math.radians(9)
    # two cushions + a folded throw
    for k, (cy, m) in enumerate([(y1 - arm - 0.28, M["linen"]), (y0 + arm + 0.30, M["linen_oat"])]):
        p = recenter(cushion(f"Throw cushion {k}", x1 - .52, x1 - .38, cy - .22, cy + .22, 0.40, 0.82, m, r=0.07))
        p.rotation_euler.y = math.radians(14)
    cushion("Throw", x0 + .1, x0 + .55, y0 + arm + .05, y0 + arm + .72, 0.38, 0.415, M["wool"], r=0.012, puff=0)

def lounge(f, idx):
    x0, x1, y0, y1 = R(f)          # faces north: back on the south side
    for side, (a, b) in enumerate([(x0, x0 + 0.05), (x1 - 0.05, x1)]):
        box(f"Lounge {idx} side {side}", a, b, y0 + .02, y1 - .04, 0.0, 0.56, M["oak"], bevel=0.01, seg=3)
    box(f"Lounge {idx} rail", x0 + .05, x1 - .05, y0 + .02, y0 + .06, 0.06, 0.18, M["oak"], bevel=0.006)
    cushion(f"Lounge {idx} seat", x0 + .05, x1 - .05, y0 + .1, y1 - .02, 0.18, 0.36, M["wool"], r=0.05)
    b = recenter(cushion(f"Lounge {idx} back", x0 + .06, x1 - .06, y0 + .04, y0 + .22, 0.34, 0.74, M["wool"], r=0.07))
    b.rotation_euler.x = math.radians(12)

def washi_pendant(cx, cy, r, z, name):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=r)
    bmesh.ops.scale(bm, vec=(1, 1, 0.62), verts=bm.verts); bmesh.ops.translate(bm, vec=(cx, cy, z), verts=bm.verts)
    o = obj_from_bm(name, bm, M["washi"]); o.data.shade_smooth()
    for k in range(9):          # bamboo ribs
        zz = z - r * 0.55 + k * (r * 1.1 / 8)
        rr = r * math.sqrt(max(0.0, 1 - ((zz - z) / (r * 0.62)) ** 2)) + 0.002
        bpy.ops.mesh.primitive_torus_add(major_radius=rr, minor_radius=0.0015, location=(cx, cy, zz), major_segments=64, minor_segments=6)
        t = bpy.context.active_object; t.name = name + " rib"; t.data.materials.append(M["washi"])
        for c in t.users_collection: c.objects.unlink(t)
        col("Interior").objects.link(t)
    cyl(name + " cord", cx, cy, 0.003, z + r * 0.6, H, M["steel"], seg=8, bevel=0)
    L = bpy.data.lights.new(name + " bulb", "POINT"); L.energy = 3; L.color = (1.0, 0.78, 0.55); L.shadow_soft_size = 0.05
    lo = bpy.data.objects.new(name + " bulb", L); lo.location = (cx, cy, z); col("Lights").objects.link(lo)

def olive(cx, cy, scale=1.0, name="Olive"):
    cyl(name + " pot", cx, cy, 0.30 * scale, 0.0, 0.55 * scale, M["clay_pot"], r2=0.26 * scale, seg=48)
    cyl(name + " soil", cx, cy, 0.27 * scale, 0.5 * scale, 0.52 * scale, M["soil"], seg=32, bevel=0)
    rnd = random.Random(int(cx * 100 + cy))
    # trunk: two twisting stems
    leaf_bm = bmesh.new()
    def leaf_at(p, d):
        # thin lanceolate leaf: 6 x 1.2 cm
        v = [Vector((0, 0, 0)), Vector((0.02, 0.008, 0.0)), Vector((0.075, 0, 0.004)), Vector((0.02, -0.008, 0.0))]
        q = d.to_track_quat("X", "Z")
        rot = Matrix.Rotation(rnd.uniform(-1.2, 1.2), 4, "X")
        vs = [leaf_bm.verts.new(p + (q.to_matrix().to_4x4() @ rot @ vv.to_4d()).to_3d()) for vv in v]
        leaf_bm.faces.new(vs)
    stems = []
    for s in range(3):
        pts = []; p = Vector((cx + rnd.uniform(-.03, .03), cy + rnd.uniform(-.03, .03), 0.5 * scale)); d = Vector((rnd.uniform(-.2, .2), rnd.uniform(-.2, .2), 1)).normalized()
        for k in range(8):
            pts.append(p.copy()); p += d * 0.14 * scale; d = (d + Vector((rnd.uniform(-.35, .35), rnd.uniform(-.35, .35), 0.15))).normalized()
        stems.append(pts)
    cu = bpy.data.curves.new(name + " trunk", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.025 * scale; cu.bevel_resolution = 3
    for pts in stems:
        sp = cu.splines.new("POLY"); sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts): sp.points[i].co = (*p, 1); sp.points[i].radius = 1.2 - i * 0.12
    to = bpy.data.objects.new(name + " trunk", cu); to.data.materials.append(M["trunk"]); col("Interior").objects.link(to)
    # canopy: leaf clusters around branch tips
    for pts in stems:
        for tip in pts[3:]:
            for k in range(int(260 * scale)):
                off = Vector((rnd.gauss(0, .2), rnd.gauss(0, .2), rnd.gauss(0.08, .13))) * scale
                p = tip + off
                d = (off.normalized() + Vector((rnd.uniform(-.4, .4), rnd.uniform(-.4, .4), rnd.uniform(0.0, 0.5)))).normalized()
                leaf_at(p, d)
    lo = obj_from_bm(name + " leaves", leaf_bm, M["leaf"])
    so = lo.modifiers.new("Solid", "SOLIDIFY"); so.thickness = 0.0008

def stool(cx, cy, name):
    cyl(name + " seat", cx, cy, 0.19, 0.62, 0.66, M["oak"], seg=40)
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        bpy.ops.mesh.primitive_cylinder_add(radius=0.014, depth=0.64, location=(cx + math.cos(a) * 0.13, cy + math.sin(a) * 0.13, 0.31))
        l = bpy.context.active_object; l.rotation_euler = (math.sin(a) * -0.09, math.cos(a) * 0.09, 0); l.data.materials.append(M["oak"]); l.name = name + " leg"
        for c in l.users_collection: c.objects.unlink(l)
        col("Interior").objects.link(l)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.15, minor_radius=0.008, location=(cx, cy, 0.24)); t = bpy.context.active_object
    t.data.materials.append(M["oak"]); t.name = name + " ring"
    for c in t.users_collection: c.objects.unlink(t)
    col("Interior").objects.link(t)

def chair_teak(cx, cy, face_deg, name):
    o = box(name + " seat", cx - .22, cx + .22, cy - .22, cy + .22, 0.42, 0.46, M["teak"], bevel=0.008)
    for dx in (-.19, .19):
        for dy in (-.19, .19):
            box(name + " leg", cx + dx - .02, cx + dx + .02, cy + dy - .02, cy + dy + .02, 0, 0.42, M["teak"], bevel=0.004)
    a = math.radians(face_deg + 180); bx, by = cx + math.cos(a) * 0.2, cy + math.sin(a) * 0.2
    if abs(math.cos(a)) > 0.5: box(name + " back", bx - .02, bx + .02, cy - .2, cy + .2, 0.46, 0.8, M["teak"], bevel=0.006)
    else: box(name + " back", cx - .2, cx + .2, by - .02, by + .02, 0.46, 0.8, M["teak"], bevel=0.006)

for f in F:
    k = f["kind"]
    if "rect" in f: x0, x1, y0, y1 = R(f)
    if k == "rug" and f["room"] == "living": ikea_glb("00277395", ((x0 + x1) / 2, (y0 + y1) / 2, 0.0), 90, "LOHALS rug") or ikea_lohals(f)
    elif k == "rug": box("Rug " + f["room"], x0, x1, y0, y1, 0.0, 0.014, M["rug"], bevel=0.006, seg=2)
    elif k == "mat": box("Coir mat", x0, x1, y0, y1, -0.012, 0.001, M["coir"])
    elif k == "sofa" and f["room"] == "living": ikea_glb("09489637", (x1 - 0.465, (y0 + y1) / 2, 0.0), -90, "HYLTARP sofa") or ikea_jattebo(f)
    elif k == "lounge": ikea_glb("10594755", ((x0 + x1) / 2, (y0 + y1) / 2, 0.0), 180, "STOCKHOLM 2025 armchair") or ikea_stockholm(f, int(x0 * 10))
    elif k == "console":
        ym = (y0 + y1) / 2      # two BESTÅ 120 × 42 × 48 benches, white stained oak effect, wall-hung side by side = 240
        if not all([ikea_glb("99188343", (3.555 + 0.2066, ym + d * 0.60, 0.0), 90, "BESTA TV bench") for d in (-1, 1)]): ikea_besta(f)      # back flush on the clay panel
    elif k == "console_old":
        box("Console", x0, x1, y0, y1, 0.13, 0.48, M["oak"], bevel=0.004)
        for i in range(1, 4): box("Console seam", x0 - 0.001, x0 + 0.002, y0 + i * (y1 - y0) / 4 - .001, y0 + i * (y1 - y0) / 4 + .001, 0.14, 0.47, M["smoked"])
    elif k == "panel":
        box("Clay media wall", x0, x1 + 0.02, y0, y1, 0, H, M["clay"])
        frame_tv(x1 + 0.02, 7.70, 1.30)
    elif k == "art":
        a = box("Art canvas", x0 - 0.0, x1, y0, y1, 1.15, 1.95, M["art"], bevel=0.003, seg=1)
        bpy.context.view_layer.objects.active = a
        uvl = a.data.uv_layers.new();
        for poly in a.data.polygons:
            for li in poly.loop_indices:
                v = a.data.vertices[a.data.loops[li].vertex_index].co
                uvl.data[li].uv = ((v.y - y0) / (y1 - y0), (v.z - 1.15) / 0.8) if poly.normal.x < -0.5 else (0, 0)
    elif k == "curtain":
        for (a0, a1) in ((4.22, 4.62), (7.30, 7.74)):
            bm = bmesh.new(); n = 48
            for i in range(n + 1):
                x = a0 + (a1 - a0) * i / n; yy = (y0 + y1) / 2 + 0.035 * math.sin(i / n * math.pi * 10)
                bm.verts.new((x, yy, 0.01)); bm.verts.new((x, yy, H - 0.12))
            bm.verts.ensure_lookup_table()
            for i in range(n): bm.faces.new((bm.verts[2 * i], bm.verts[2 * i + 2], bm.verts[2 * i + 3], bm.verts[2 * i + 1]))
            o = obj_from_bm(f"Curtain {a0}", bm, M["curtain"]); o.data.shade_smooth()
            o.modifiers.new("Solid", "SOLIDIFY").thickness = 0.002
    elif k == "screen":
        x = x0
        while x < x1 - 0.01:
            box("Screen slat", x, min(x1, x + 0.03), y0, y1, 0, 2.1, M["oak"], bevel=0.002, seg=1); x += 0.06
        box("Screen top", x0, x1, y0, y1, 2.1, 2.13, M["oak"])
    elif k == "cabinet":
        box("Shoe cabinet low", x0, x1, y0 + 0.02, y1, 0.15, 0.45, M["oak"], bevel=0.002, seg=1)   # floats on a light line
        box("Bench seat", x0, x1, y0 - .005, y1, 0.45, 0.48, M["oak"], bevel=0.003)
        box("Niche back", x0, x1, y0, y0 + 0.02, 0.48, 0.95, M["smoked"])
        cushion("Bench pad", x0 + 0.1, x0 + 0.9, y0 + 0.03, y1 - 0.03, 0.48, 0.53, M["linen_oat"], r=0.02, puff=0)
        fluted("Shoe cabinet upper", x0, x1, y0, y1 - 0.013, 0.95, 2.4, "+y", M["oak"])
    elif k == "lantern":
        ikea_holmo(f)
    elif k == "lantern_old":
        cx, cy, r = f["circle"]
        cyl("Lantern base", cx, cy, r * 0.8, 0, 0.03, M["oak"])
        cyl("Lantern shade", cx, cy, r, 0.1, 1.4, M["washi"], seg=48, bevel=0)
        L = bpy.data.lights.new("Lantern", "POINT"); L.energy = 6; L.color = (1.0, 0.76, 0.52); L.shadow_soft_size = 0.12
        lo = bpy.data.objects.new("Lantern light", L); lo.location = (cx, cy, 0.85); col("Lights").objects.link(lo)
    elif k == "pendant":
        cx, cy, r = f["circle"]
        if f["room"] == "living": ikea_ps2026(cx, cy, 1.85, f"Pendant living {cx:.1f}")
        else: washi_pendant(cx, cy, r, 1.68, f"Pendant {f['room']} {cx:.1f}")
    elif k == "floorlamp":
        ikea_vidja(f)
    elif k == "floorlamp_old":
        cx, cy, r = f["circle"]; hh = f.get("h", 1.6)
        cyl("Column lamp base", cx, cy, r * 0.8, 0.0, 0.05, M["oak"], seg=48)
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=64, radius1=r, radius2=r, depth=hh - 0.08)
        bmesh.ops.translate(bm, vec=(cx, cy, 0.08 + (hh - 0.08) / 2), verts=bm.verts)
        o = obj_from_bm("Column lamp shade", bm, M["washi"]); o.data.shade_smooth(); o.modifiers.new("Solid", "SOLIDIFY").thickness = 0.0015
        zz = 0.14
        while zz < hh:
            bpy.ops.mesh.primitive_torus_add(major_radius=r + 0.001, minor_radius=0.0022, location=(cx, cy, zz), major_segments=72, minor_segments=6)
            t = bpy.context.active_object; t.name = "Column lamp rib"; t.data.materials.append(M["washi"])
            for c in t.users_collection: c.objects.unlink(t)
            col("Interior").objects.link(t); zz += 0.115
        for k2, z in enumerate((0.55, 1.15)):
            L = bpy.data.lights.new(f"Column lamp {k2}", "POINT"); L.shadow_soft_size = 0.12
            lo = bpy.data.objects.new(f"Column lamp {k2}", L); lo.location = (cx, cy, z); col("Lights").objects.link(lo)
            lo["circuit"] = "LIV_COL"; lo["full"] = 9.0; lo["cct"] = 2200
    elif k == "plant":
        cx, cy, r = f["circle"]; plant_fit("potted_plant_01", (cx, cy, 0.0), f.get("h", 1.3))
    elif k == "table":
        cx, cy, r = f["circle"]
        if f["room"] == "living":
            if f["mat"] == "smoked": ikea_listerby_round(cx, cy, r=r, h=f.get("h", 0.56), mat=M["oak_dark"], shelf=False, name="LISTERBY side")
            else: ikea_listerby_round(cx, cy, r=r, h=f.get("h", 0.45))
        elif f["mat"] == "limestone":
            cyl("Coffee top", cx, cy, r, 0.27, 0.32, M["travertine"], seg=64)
            cyl("Coffee drum", cx, cy, r * 0.62, 0.0, 0.27, M["oak"], seg=64)
        else:
            cyl("Side table", cx, cy, r, 0.0, 0.45, M["smoked"], seg=48)
    elif k == "counter":
        box("Base run", x0, x1, y0, y1, 0.1, 0.89, M["oak"], bevel=0.002, seg=1)
        box("Toe kick", x0 + .05, x1 - .05, y0 + .05, y1 - .05, 0, 0.1, M["steel"])
        box("Worktop", x0, x1 + (0.0), y0, y1 + 0.02, 0.89, 0.92, M["limestone"], bevel=0.002, seg=1)
        if (x1 - x0) > (y1 - y0): box("Splash", x0, x1, y0, y0 + 0.02, 0.92, 1.55, M["limestone"])
        else: box("Splash E", x1 - 0.02, x1, y0, y1, 0.92, 1.55, M["limestone"])
        # door seams
        L = (x1 - x0) if (x1 - x0) > (y1 - y0) else (y1 - y0); n = max(2, int(L / 0.6))
        for i in range(1, n):
            if (x1 - x0) > (y1 - y0): box("Seam", x0 + i * L / n - .0015, x0 + i * L / n + .0015, y1 - .002, y1 + .001, 0.12, 0.87, M["smoked"])
            else: box("Seam", x0 - .001, x0 + .002, y0 + i * L / n - .0015, y0 + i * L / n + .0015, 0.12, 0.87, M["smoked"])
    elif k == "tall":
        fluted("Tall column", x0, x1, y0, y1, 0.0, 2.4, "-x", M["oak"])
    elif k == "shelf":
        box("Floating shelf", x0, x1, y0, y0 + 0.26, 1.53, 1.57, M["oak"], bevel=0.003)
    elif k == "hob": box("Hob", x0, x1, y0, y1, 0.92, 0.926, M["screen"], bevel=0.002, seg=1)
    elif k == "sink":
        box("Sink", x0, x1, y0, y1, 0.80, 0.921, M["steel"])
        cyl("Tap", x0 + 0.3, y0 + 0.04, 0.012, 0.92, 1.18, M["steel"], seg=16)
    elif k == "peninsula":
        box("Peninsula body", x0, x1 - 0.03, y0 + 0.05, y1 - 0.25, 0.0, 0.89, M["oak"], bevel=0.002, seg=1)
        fluted("Peninsula front", x0, x1 - 0.03, y1 - 0.25, y1 - 0.24, 0.0, 0.89, "+y", M["oak"])
        box("Peninsula top", x0, x1, y0, y1, 0.89, 0.93, M["limestone"], bevel=0.003)
        box("Waterfall", x1 - 0.03, x1, y0, y1, 0.0, 0.93, M["limestone"], bevel=0.003)
    elif k == "stool":
        cx, cy, r = f["circle"]; ikea_glb("10619930", (cx, cy, 0.0), 0, "ROSENTORP stool") or ikea_rosentorp(cx, cy)
    elif k == "outdoor_sofa":
        w3 = (x1 - x0) / 3
        if not all([ikea_glb("79584363", (x0 + w3 * (i + 0.5), (y0 + y1) / 2, 0.0), 180, "NAMMARO easy chair") for i in range(3)]): ikea_nammaro_sofa(x0, x1, y0, y1)
    elif k == "outdoor_sofa_old":
        box("Out sofa frame", x0, x1, y0, y1, 0.0, 0.3, M["teak"], bevel=0.01)
        cushion("Out sofa seat", x0 + .05, x1 - .05, y0 + .18, y1 - .03, 0.3, 0.42, M["outdoor"], r=0.05)
        cushion("Out sofa back", x0 + .05, x1 - .05, y0, y0 + .2, 0.3, 0.72, M["outdoor"], r=0.07)
    elif k == "dining_out":
        ikea_glb("20510307", ((x0 + x1) / 2, (y0 + y1) / 2, 0.0), 0, "NAMMARO table") or ikea_nammaro_table(x0, x1, y0, y1, h=0.75)
    elif k == "outdoor_table":
        ikea_nammaro_table(x0, x1, y0, y1, h=f.get("h", 0.35), name="Low table")
    elif k == "table_old":
        h = f.get("h", 0.74)
        box("Teak top", x0, x1, y0, y1, h - 0.04, h, M["teak"], bevel=0.006)
        for dx, dy in ((0.06, 0.06), (x1 - x0 - 0.12, 0.06), (0.06, y1 - y0 - 0.12), (x1 - x0 - 0.12, y1 - y0 - 0.12)):
            box("Teak leg", x0 + dx, x0 + dx + 0.06, y0 + dy, y0 + dy + 0.06, 0, h - 0.04, M["teak"], bevel=0.004)
    elif k == "chair" and f["room"] == "terrace":
        cx, cy, r = f["circle"]; face = f.get("face", 90 if cy < 11 else -90)
        ikea_glb("90511105", (cx, cy, 0.0), face + 90, "NAMMARO armchair") or ikea_nammaro_armchair(cx, cy, face)
    elif k == "planter":
        box("Planter", x0, x1, y0, y1, -0.02, f.get("h", 0.45), M["smoked"], bevel=0.008)
        box("Planter soil", x0 + .03, x1 - .03, y0 + .03, y1 - .03, f.get("h", 0.45) - 0.04, f.get("h", 0.45) - 0.02, M["soil"])

# props: Poly Haven models

def place_model(asset, loc, rot_z=0.0, scale=1.0):
    try:
        p = ph_model(asset)
    except Exception as e:
        print("model download failed", asset, e); return
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=p)
    new = [o for o in bpy.data.objects if o not in before]
    roots = [o for o in new if o.parent is None]
    for o in new:
        for c in list(o.users_collection): c.objects.unlink(o)
        col("Props").objects.link(o)
    for r in roots:
        r.location = loc; r.rotation_euler = (0, 0, rot_z); r.scale = (scale, scale, scale)
plant_fit("potted_plant_02", (3.80, 8.55, 0.4875), 0.48, rot_z=0.6)
place_model("ceramic_vase_04", (3.78, 7.05, 0.4875), 1.2, 0.8)
_b4 = set(bpy.data.objects); place_model("wooden_bowl_01", (6.14, 7.30, 0.47), 0.4, 0.8); _bowl = [o for o in bpy.data.objects if o not in _b4]
place_model("ceramic_vase_02", (3.30, 0.52, 1.57), 0.0, 0.7)
place_model("wooden_bowl_02", (3.95, 2.85, 0.93), 0.0, 0.8)
_rug = [o for o in bpy.data.objects if o.name.startswith("LOHALS")]
for r in _roots(_rug): r.scale.z *= 0.3                     # flatwoven jute is ~5 mm thick
bpy.context.view_layer.update()
if _rug:
    for grp in ("LISTERBY", "STOCKHOLM 2025 armchair"): move([o for o in bpy.data.objects if o.name.startswith(grp)], (0, 0, _bbox(_rug)[1].z))
dress()
exec(open(os.path.join(PROJECT, "blender", "bedrooms.py"), encoding="utf-8").read())
drop(_bowl)
# books on the coffee table
box("Book 1", 6.02, 6.30, 7.74, 7.96, 0.4575, 0.4825, M["paper"], bevel=0.003); box("Book 2", 6.04, 6.27, 7.76, 7.94, 0.4825, 0.5025, M["paper2"], bevel=0.003)

# ------------------------------------------------------------------ the world: Haifa Bay, 13 floors down
SEA = -45.5
bpy.ops.mesh.primitive_plane_add(size=60000, location=(0, 0, SEA)); sea = bpy.context.active_object; sea.name = "Sea"; sea.data.materials.append(M["sea"])
def land(x, y):  # y north
    return x > -170 + 70 * math.sin(-y / 700) and -y > (-430 + 90 * math.sin(x / 900) if x < 2600 else -430 - (x - 2600) * 0.95)
# NOTE: world.js uses z = -north; here y = north, so the bay lies at y > 430
def is_land(x, y): return x > -170 and (y < 430 - 90 * math.sin(x / 900) if x < 2600 else y < 430 + (x - 2600) * 0.95)
bm = bmesh.new()
rnd = random.Random(1312); n = 0
while n < 2700:
    a = rnd.random() * 2 * math.pi; r = 60 + (rnd.random() ** 0.75) * 4500
    x, y = math.cos(a) * r, math.sin(a) * r
    if not is_land(x, y): continue
    north_view = y > -40 and abs(x) < 900 + max(0, y) and r < 1200
    if north_view and (rnd.random() < 0.18 or r < 200): continue      # the roofs of downtown fill the slope below the balcony
    port = y > 150 and 150 < x < 2600
    base = -39.5 + max(0.0, x - 380) * 0.17 + max(0.0, -y - 150) * 0.07
    base = min(base, 420)
    if port: h, w, d = 5 + rnd.random() * 7, 30 + rnd.random() * 60, 20 + rnd.random() * 30
    elif north_view: h, w, d = 7 + rnd.random() * 15, 14 + rnd.random() * 20, 12 + rnd.random() * 16
    else:
        tall = rnd.random() < 0.06; h = (55 + rnd.random() * 85) if tall else (10 + rnd.random() * 26); w = 14 + rnd.random() * 22; d = 12 + rnd.random() * 18
    geom = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.scale(bm, vec=(w, d, h), verts=geom); bmesh.ops.rotate(bm, verts=geom, cent=(0, 0, 0), matrix=Matrix.Rotation(0.35 + (rnd.random() - .5) * .25, 3, "Z"))
    bmesh.ops.translate(bm, vec=(x, y, base + h / 2), verts=geom); n += 1
obj_from_bm("City", bm, M["city"], coll="World")
# land mass under the city (low-poly terrain) and far hills across the bay
bm = bmesh.new(); S = 120; X0, X1, Y0, Y1 = -2000, 9000, -9000, 2600
grid = [[None] * (S + 1) for _ in range(S + 1)]
for i in range(S + 1):
    for j in range(S + 1):
        x = X0 + (X1 - X0) * i / S; y = Y0 + (Y1 - Y0) * j / S
        z = (-39.5 + min(420, max(0.0, x - 380) * 0.17 + max(0.0, -y - 150) * 0.07)) if is_land(x, y) else SEA - 6
        grid[i][j] = bm.verts.new((x, y, z))
for i in range(S):
    for j in range(S): bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
obj_from_bm("Land", bm, M["land"], coll="World")
bm = bmesh.new(); rr = random.Random(3)
prev = None
for k in range(0, 61):
    x = -6000 + k * 600; z0 = SEA; z1 = SEA + 250 + 450 * abs(math.sin(k * 0.37)) + rr.random() * 120
    a = bm.verts.new((x, 22000, z0)); b = bm.verts.new((x, 22000, z1))
    if prev: bm.faces.new((prev[0], a, b, prev[1]))
    prev = (a, b)
obj_from_bm("Galilee hills", bm, M["hills"], coll="World")

# ------------------------------------------------------------------ light: 15 October, ~17:00, Haifa
AZ, EL = math.radians(251), math.radians(9)
sun_dir = Vector((math.sin(AZ) * math.cos(EL), math.cos(AZ) * math.cos(EL), math.sin(EL)))
world = scene.world or bpy.data.worlds.new("Haifa sky")
scene.world = world; world.use_nodes = True; wn = world.node_tree; wn.nodes.clear()
wo = wn.nodes.new("ShaderNodeOutputWorld"); sky = wn.nodes.new("ShaderNodeTexSky"); bg = wn.nodes.new("ShaderNodeBackground")
try:
    sky.sky_type = "NISHITA"
except Exception:
    try: sky.sky_type = "MULTIPLE_SCATTERING"
    except Exception: pass
try:
    sky.sun_disc = False; sky.sun_elevation = EL
    sky.sun_rotation = math.atan2(sun_dir.x, sun_dir.y) * -1 + math.pi / 2   # verified by the sun-patch test render
except Exception as e: print("sky", e)
for k, v in (("altitude", 60.0), ("air_density", 1.3), ("dust_density", 2.2), ("aerosol_density", 2.2), ("ozone_density", 1.0)):
    try: setattr(sky, k, v)
    except Exception: pass
bg.inputs[1].default_value = 1.0
wn.links.new(sky.outputs[0], bg.inputs[0]); wn.links.new(bg.outputs[0], wo.inputs[0])
sunL = bpy.data.lights.new("Sun", "SUN"); sunL.energy = 4.2; sunL.angle = math.radians(0.6); sunL.color = (1.0, 0.72, 0.48)
sun = bpy.data.objects.new("Sun", sunL); col("Lights").objects.link(sun)
sun.rotation_euler = (-sun_dir).to_track_quat("-Z", "Y").to_euler()
# a soft line of light hidden in the curtain pocket
exec(open(os.path.join(PROJECT, "blender", "lighting_build.py"), encoding="utf-8").read())

# ------------------------------------------------------------------ cameras
def camera(name, loc, look, lens=20, shift_y=0.0):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.sensor_width = 36; cd.shift_y = shift_y; cd.clip_start = 0.05; cd.clip_end = 80000
    o = bpy.data.objects.new(name, cd); col("Cameras").objects.link(o); o.location = loc
    d = Vector(look) - Vector(loc)          # level camera (verticals stay vertical); frame with lens shift
    o.rotation_euler = (math.radians(90), 0, math.atan2(-d.x, d.y))
    return o
cam_entry = camera("CAM Entry", (7.10, 4.62, 1.55), (5.45, 9.05, 1.3), lens=19, shift_y=-0.03)
cam_living = camera("CAM Living to bay", (6.62, 5.42, 1.35), (4.75, 9.6, 1.25), lens=20, shift_y=-0.02)
cam_media = camera("CAM Living to media wall", (6.55, 9.0, 1.35), (3.5, 6.6, 1.2), lens=20, shift_y=-0.04)
cam_hero = camera("CAM Hero", (3.95, 4.70, 1.22), (6.35, 9.35, 1.2), lens=19, shift_y=0.02)
def look_cam(name, loc, look, lens=50):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.sensor_width = 36; cd.clip_start = 0.05; cd.clip_end = 80000
    o = bpy.data.objects.new(name, cd); col("Cameras").objects.link(o); o.location = loc
    o.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler(); return o
look_cam("CAM Detail table", (6.75, 6.55, 0.80), (5.25, 8.15, 0.55), 50)
look_cam("CAM Detail screen", (6.50, 4.75, 1.35), (7.40, 6.20, 1.10), 40)
look_cam("CAM Kitchen", (5.05, 5.15, 1.40), (3.15, 2.55, 0.85), 22)
look_cam("CAM Balcony west", (7.0, 11.9, 1.45), (0.2, 10.9, 0.55), 24)
look_cam("CAM Main bedroom", (-4.32, 8.24, 1.38), (-6.05, 10.70, 0.75), 16)
look_cam("CAM Teen", (-0.15, 6.40, 1.45), (-1.90, 8.70, 0.75), 18)
look_cam("CAM Office", (0.86, 6.28, 1.45), (2.60, 8.60, 0.75), 18)
look_cam("CAM Toddler", (-6.95, 5.30, 1.25), (-5.10, 7.50, 0.45), 18)
cam_balcony = camera("CAM Balcony", (5.9, 9.95, 1.55), (2.5, 13.2, 1.2), lens=20, shift_y=-0.05)
walk = camera("CAM Walk", (7.12, 4.45, 1.60), (7.0, 9.0, 1.4), lens=20, shift_y=-0.02)
keys = [(1, (7.12, 4.45, 1.60), (7.05, 9.0)), (40, (7.0, 5.0, 1.58), (6.0, 9.3)), (96, (6.62, 5.42, 1.55), (4.75, 9.6))]
for fr, loc, look in keys:
    walk.location = loc; walk.rotation_euler = (math.radians(90), 0, math.atan2(-(look[0] - loc[0]), look[1] - loc[1]))
    walk.keyframe_insert("location", frame=fr); walk.keyframe_insert("rotation_euler", frame=fr)
try:
    for fc in walk.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = "BEZIER"; kp.easing = "AUTO"
except Exception as e: print("fcurves", e)
scene.frame_start, scene.frame_end = 1, 96; scene.render.fps = 24
scene.camera = cam_living

# ------------------------------------------------------------------ render settings
scene.render.engine = "CYCLES"
cp = bpy.context.preferences.addons["cycles"].preferences
try:
    cp.compute_device_type = "OPTIX"; cp.get_devices()
    for d in cp.devices: d.use = d.type in ("OPTIX",)
    scene.cycles.device = "GPU"
except Exception as e: print("gpu", e)
scene.cycles.samples = 384; scene.cycles.use_denoising = True
try: scene.cycles.denoiser = "OPTIX"
except Exception: pass
scene.cycles.max_bounces = 10; scene.cycles.diffuse_bounces = 6; scene.cycles.glossy_bounces = 4; scene.cycles.transparent_max_bounces = 12
scene.cycles.use_light_tree = True
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
try: scene.view_settings.view_transform = "AgX"; scene.view_settings.look = "AgX - Medium High Contrast"
except Exception: pass
scene.view_settings.exposure = 1.6
for k, v in (("use_white_balance", True), ("white_balance_temperature", 5050.0), ("white_balance_tint", 2.0)):
    try: setattr(scene.view_settings, k, v)
    except Exception as e: print("wb", k, e)
os.makedirs(os.path.join(PROJECT, "blender", "renders"), exist_ok=True)
print("BUILD OK", len(bpy.data.objects), "objects")
