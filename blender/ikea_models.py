# IKEA pieces for the living room, modelled at catalogue sizes (ikea.com product pages, Oct 2026).
# Exec'd from build_scene.py: uses its globals (bpy, bmesh, M, box, cyl, col, obj_from_bm, recenter, textured, flat, srgb, TEX, H).
from mathutils import noise

# ---------------------------------------------------------------- materials
M["samsala"] = textured("Samsala grey-beige", os.path.join(TEX, "rough_linen"), 0.22, no_diffuse=True, base=srgb("#BDB2A3"), nor_strength=0.9, sheen=0.45)
M["djurmo"] = textured("Djurmo boucle", os.path.join(TEX, "curly_teddy_natural"), 0.30, nor_strength=1.3, sheen=0.5, value=1.12, sat=0.45)
M["jute"] = textured("LOHALS jute", os.path.join(TEX, "hessian_230"), 0.18, nor_strength=1.4, value=1.0, sat=1.25, tint=(0.95, 0.80, 0.52))
M["oak_ikea"] = textured("Oak veneer", os.path.join(TEX, "white_oak_veneer"), 0.6, value=1.1, sat=0.8, nor_strength=0.35)
M["oak_dark"] = textured("Oak dark brown stain", os.path.join(TEX, "white_oak_veneer"), 0.6, value=0.42, sat=0.95, nor_strength=0.4)
M["vidja"] = translucent("VIDJA shade", srgb("#F4EFE6"), 0.72)
M["ricepaper"] = translucent("Rice paper", srgb("#F2EADB"), 0.75, os.path.join(TEX, "rough_linen"), nor_size=0.35)
M["abs_white"] = flat("ABS white", srgb("#ECE9E3"), 0.45)

# ---------------------------------------------------------------- helpers
def soft(name, x0, x1, y0, y1, z0, z1, mat, r=0.04, crown=0.0, sag=0.0, wobble=0.004, level=2, coll="Interior"):
    """Upholstered block: bevelled box -> subdivision -> crowned top, slight sag and fabric wobble."""
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=7, use_grid_fill=True)
    bmesh.ops.scale(bm, vec=(x1 - x0, y1 - y0, z1 - z0), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), verts=bm.verts)
    cx, cy, hx, hy = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    seed = random.Random(hash(name) & 0xffff).random() * 50
    for v in bm.verts:
        u = 1 - min(1, abs(v.co.x - cx) / hx) ** 2; w = 1 - min(1, abs(v.co.y - cy) / hy) ** 2
        if v.co.z > z1 - 1e-4: v.co.z += crown * u * w
        if crown and v.co.z < z1 - 1e-4 and v.co.z > z0 + 1e-4:          # sides bulge a touch
            t = (v.co.z - z0) / (z1 - z0); b = crown * 0.35 * math.sin(t * math.pi)
            if abs(v.co.x - cx) > hx - 1e-4: v.co.x += math.copysign(b, v.co.x - cx) * w
            if abs(v.co.y - cy) > hy - 1e-4: v.co.y += math.copysign(b, v.co.y - cy) * u
        if sag and v.co.z > z1 - 1e-4: v.co.z -= sag * u * w
        n = noise.noise(Vector((v.co.x * 7 + seed, v.co.y * 7, v.co.z * 7)))
        v.co += Vector((0, 0, 0)) + Vector((n, noise.noise(Vector((v.co.y * 6, v.co.z * 6 + seed, v.co.x))), n * 0.5)) * wobble
    o = obj_from_bm(name, bm, mat, coll)
    bv = o.modifiers.new("Bevel", "BEVEL"); bv.width = r; bv.segments = 3; bv.limit_method = "ANGLE"
    ss = o.modifiers.new("Sub", "SUBSURF"); ss.levels = level; ss.render_levels = level
    o.data.shade_smooth()
    return o

def piping(name, x0, x1, y0, y1, z, r, mat, inset=0.0):
    """Welt seam around a cushion at height z (rounded rectangle curve with a round profile)."""
    x0 += inset; x1 -= inset; y0 += inset; y1 -= inset
    rr = min(r, (x1 - x0) / 2 - 0.001, (y1 - y0) / 2 - 0.001); pts = []
    for (cx, cy, a0) in ((x1 - rr, y1 - rr, 0), (x0 + rr, y1 - rr, 90), (x0 + rr, y0 + rr, 180), (x1 - rr, y0 + rr, 270)):
        for k in range(7):
            a = math.radians(a0 + k * 15); pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a), z))
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.0045; cu.bevel_resolution = 2
    sp = cu.splines.new("POLY"); sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts): sp.points[i].co = (*p, 1)
    sp.use_cyclic_u = True
    o = bpy.data.objects.new(name, cu); o.data.materials.append(mat); col("Interior").objects.link(o); return o

def tapered_leg(name, x, y, z0, z1, r0, r1, mat):
    return cyl(name, x, y, r0, z0, z1, mat, seg=24, r2=r1, bevel=0.002)

def lathe(name, profile, mat, cx, cy, seg=72, coll="Interior", noise_amp=0.0):
    """Revolve a (radius, z) profile around a vertical axis; open ends."""
    bm = bmesh.new(); rings = []
    for (r, z) in profile:
        ring = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            rr = r * (1 + noise_amp * (0.6 * noise.noise(Vector((math.cos(a) * 3, math.sin(a) * 3, z * 9))) + 0.4 * noise.noise(Vector((math.cos(a) * 14, math.sin(a) * 14, z * 30)))))
            ring.append(bm.verts.new((cx + rr * math.cos(a), cy + rr * math.sin(a), z)))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(seg): bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i]))
    o = obj_from_bm(name, bm, mat, coll); o.data.shade_smooth(); return o

# ---------------------------------------------------------------- JÄTTEBO 3-seat modular sofa, 240 × 95 × 71, seat h 46
def ikea_jattebo(f):
    x0, x1, y0, y1 = f["rect"]            # faces west: back on the east side (x1)
    arm = 0.25; seat_d = 0.69
    for k, (a, b) in enumerate(((y0, y0 + arm), (y1 - arm, y1))):
        soft(f"JATTEBO arm {k}", x0 + 0.01, x1, a, b, 0.03, 0.60, M["samsala"], r=0.05, crown=0.012)
    soft("JATTEBO base", x0 + 0.02, x1 - 0.02, y0 + arm, y1 - arm, 0.03, 0.30, M["samsala"], r=0.03)
    n = 3; w = (y1 - y0 - 2 * arm) / n
    for k in range(n):
        a = y0 + arm + k * w
        soft(f"JATTEBO seat {k}", x0, x0 + seat_d, a + 0.004, a + w - 0.004, 0.30, 0.46, M["samsala"], r=0.045, crown=0.022, sag=0.012)
        piping(f"JATTEBO seat seam {k}", x0 + 0.01, x0 + seat_d - 0.01, a + 0.012, a + w - 0.012, 0.381, 0.05, M["samsala"])
        o = soft(f"JATTEBO back {k}", x0 + seat_d - 0.02, x1 - 0.03, a + 0.006, a + w - 0.006, 0.40, 0.73, M["samsala"], r=0.06, crown=0.03)
        o.data.transform(Matrix.Translation(-Vector((x1 - 0.1, a + w / 2, 0.40))))
        o.rotation_euler.y = math.radians(7); o.location = (x1 - 0.1, a + w / 2, 0.40)
    soft("JATTEBO back frame", x1 - 0.12, x1, y0 + arm, y1 - arm, 0.30, 0.66, M["samsala"], r=0.03)
    for (yy, m, rot) in ((y1 - arm - 0.30, M["linen"], 12), (y0 + arm + 0.32, M["linen_oat"], -9)):
        o = soft("Cushion", x1 - 0.48, x1 - 0.32, yy - 0.23, yy + 0.23, 0.46, 0.92, m, r=0.06, crown=0.05, level=2)
        recenter(o); o.rotation_euler = (math.radians(rot), math.radians(14), 0)
    soft("Throw folded", x0 + 0.08, x0 + 0.52, y0 + arm + 0.06, y0 + arm + 0.70, 0.46, 0.485, M["wool"], r=0.008, crown=0.004, level=1)

# ---------------------------------------------------------------- STOCKHOLM 2025 armchair, 76 × 72 × 68, seat h 40, solid oak legs
def ikea_stockholm(f, idx):
    x0, x1, y0, y1 = f["rect"]            # faces north: back on the south side (y0)
    cx = (x0 + x1) / 2; W, D = x1 - x0, y1 - y0
    for (lx, ly) in ((x0 + 0.09, y0 + 0.09), (x1 - 0.09, y0 + 0.09), (x0 + 0.09, y1 - 0.09), (x1 - 0.09, y1 - 0.09)):
        tapered_leg(f"STOCKHOLM {idx} leg", lx, ly, 0.0, 0.152, 0.016, 0.024, M["oak_ikea"])
    soft(f"STOCKHOLM {idx} base", x0 + 0.02, x1 - 0.02, y0 + 0.02, y1 - 0.01, 0.15, 0.30, M["djurmo"], r=0.06, crown=0.01)
    soft(f"STOCKHOLM {idx} seat", x0 + 0.10, x1 - 0.10, y0 + 0.14, y1 - 0.005, 0.29, 0.40, M["djurmo"], r=0.05, crown=0.025, sag=0.008)
    # one curved shell for back and arms: a U-shaped sweep, lower at the front ends
    bm = bmesh.new(); t = 0.13; rings = []
    hw, hd = W / 2 - t / 2, D - t / 2 - 0.02
    N = 56
    for i in range(N + 1):
        s = i / N                          # 0 = front-left, 0.5 = back centre, 1 = front-right
        a = math.pi * s
        px = cx - math.cos(a) * hw
        py = y0 + t / 2 + 0.01 + hd * (1 - math.sin(a))
        # tangent and outward normal in plan
        a2 = math.pi * min(1, s + 1e-3); a1 = math.pi * max(0, s - 1e-3)
        dx = (-math.cos(a2) + math.cos(a1)) * hw; dy = -(math.sin(a2) - math.sin(a1)) * hd
        L = math.hypot(dx, dy) or 1; nx, ny = dy / L, -dx / L
        if (px - cx) * nx + (py - (y0 + D / 2)) * ny < 0: nx, ny = -nx, -ny
        top = 0.54 + 0.14 * math.sin(a) ** 1.5
        sec = [(-t / 2, 0.28), (t / 2, 0.28), (t / 2, top - 0.02), (t * 0.25, top), (-t * 0.25, top), (-t / 2, top - 0.02)]
        rings.append([bm.verts.new((px + nx * u, py + ny * u, z)) for (u, z) in sec])
    for ra, rb in zip(rings, rings[1:]):
        for j in range(len(ra)): bm.faces.new((ra[j], ra[(j + 1) % len(ra)], rb[(j + 1) % len(rb)], rb[j]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])
    o = obj_from_bm(f"STOCKHOLM {idx} shell", bm, M["djurmo"])
    ss = o.modifiers.new("Sub", "SUBSURF"); ss.levels = 2; ss.render_levels = 3; o.data.shade_smooth()
    o2 = soft(f"STOCKHOLM {idx} back cushion", cx - 0.25, cx + 0.25, y0 + 0.12, y0 + 0.26, 0.38, 0.64, M["djurmo"], r=0.05, crown=0.03)
    recenter(o2); o2.rotation_euler.x = math.radians(10)

# ---------------------------------------------------------------- LISTERBY coffee table Ø90 h45, oak veneer top, solid oak legs and shelf
def ikea_listerby_round(cx, cy, r=0.45, h=0.45, mat=None, shelf=True, name="LISTERBY"):
    mat = mat or M["oak_ikea"]
    cyl(name + " top", cx, cy, r, h - 0.028, h, mat, seg=96, bevel=0.004)
    for k in range(4):
        a = math.radians(45 + 90 * k); lx, ly = cx + math.cos(a) * r * 0.62, cy + math.sin(a) * r * 0.62
        o = box(name + " leg", lx - 0.022, lx + 0.022, ly - 0.022, ly + 0.022, 0.0, h - 0.028, mat, bevel=0.006, seg=3)
    if shelf:
        cyl(name + " shelf", cx, cy, r * 0.70, 0.10, 0.118, mat, seg=72, bevel=0.003)

# ---------------------------------------------------------------- BESTÅ TV bench 240 × 42 × 38, wall-mounted, oak-effect fronts, push-open
def ikea_besta(f):
    x0, x1, y0, y1 = f["rect"]; z0, z1 = 0.15, 0.53
    box("BESTA carcass", x0, x1 - 0.018, y0, y1, z0, z1, M["oak_ikea"], bevel=0.002, seg=1)
    n = 4; w = (y1 - y0) / n
    for k in range(n):
        a = y0 + k * w
        box("BESTA front", x1 - 0.018, x1, a + 0.0015, a + w - 0.0015, z0 + 0.002, z1 - 0.002, M["oak_ikea"], bevel=0.0015, seg=1)

# ---------------------------------------------------------------- LOHALS jute rug 200 × 300, flatwoven
def ikea_lohals(f):
    x0, x1, y0, y1 = f["rect"]
    box("LOHALS rug", x0, x1, y0, y1, 0.0, 0.008, M["jute"], bevel=0.003, seg=2)

# ---------------------------------------------------------------- VIDJA floor lamp Ø18 h137 / HÖLMÖ Ø22 h117 (rice paper)
def ikea_vidja(f):
    cx, cy, r = f["circle"]; r = 0.09
    cyl("VIDJA base", cx, cy, 0.09, 0.0, 0.03, M["abs_white"], seg=48)
    lathe("VIDJA shade", [(r, 0.03), (r, 1.37)], M["vidja"], cx, cy)
    for k2, z in enumerate((0.45, 1.0)):
        L = bpy.data.lights.new(f"Column lamp {k2}", "POINT"); L.shadow_soft_size = 0.06
        lo = bpy.data.objects.new(f"Column lamp {k2}", L); lo.location = (cx, cy, z); col("Lights").objects.link(lo)
        lo["circuit"] = "LIV_COL"; lo["full"] = 5.0; lo["cct"] = 2200

def ikea_holmo(f):
    cx, cy, r = f["circle"]; r = 0.11
    cyl("HOLMO base", cx, cy, 0.10, 0.0, 0.025, M["abs_white"], seg=48)
    prof = [(r, 0.025 + 1.145 * i / 40) for i in range(41)]
    lathe("HOLMO shade", prof, M["ricepaper"], cx, cy, noise_amp=0.012)
    z = 0.10
    while z < 1.17:
        bpy.ops.mesh.primitive_torus_add(major_radius=r + 0.0008, minor_radius=0.0012, location=(cx, cy, z), major_segments=64, minor_segments=5)
        t = bpy.context.active_object; t.name = "HOLMO rib"; t.data.materials.append(M["ricepaper"])
        for c in t.users_collection: c.objects.unlink(t)
        col("Interior").objects.link(t); z += 0.075
    L = bpy.data.lights.new("Lantern light", "POINT"); L.energy = 6; L.shadow_soft_size = 0.06
    lo = bpy.data.objects.new("Lantern light", L); lo.location = (cx, cy, 0.7); col("Lights").objects.link(lo)

# ---------------------------------------------------------------- IKEA PS 2026 pendant shade Ø90 h33, handmade rice paper, half-moon dome
def ikea_ps2026(cx, cy, zb, name):
    R, Hh = 0.45, 0.33; prof = []
    for i in range(65):
        t = i / 64                          # 0 = bottom rim, 1 = crown
        prof.append((R * math.cos(t * math.pi / 2) ** 0.85 + 0.03 * (1 - t) * 0, zb + Hh * math.sin(t * math.pi / 2)))
    prof[-1] = (0.035, zb + Hh)
    lathe(name, prof, M["ricepaper"], cx, cy, seg=160, noise_amp=0.065)
    for i in range(1, 9):                   # galvanised wire hoops inside the paper
        t = i / 9; rr = R * math.cos(t * math.pi / 2) ** 0.85; z = zb + Hh * math.sin(t * math.pi / 2)
        bpy.ops.mesh.primitive_torus_add(major_radius=rr - 0.002, minor_radius=0.0013, location=(cx, cy, z), major_segments=96, minor_segments=5)
        o = bpy.context.active_object; o.name = name + " hoop"; o.data.materials.append(M["ricepaper"])
        for c in o.users_collection: c.objects.unlink(o)
        col("Interior").objects.link(o)
    cyl(name + " cord", cx, cy, 0.003, zb + Hh, H, M["steel"], seg=8, bevel=0)
    L = bpy.data.lights.new(name + " bulb", "POINT"); L.energy = 3; L.shadow_soft_size = 0.06
    lo = bpy.data.objects.new(name + " bulb", L); lo.location = (cx, cy, zb + 0.14); col("Lights").objects.link(lo)
print("IKEA models ready")

# ---------------------------------------------------------------- round 2: kitchen stools and the balcony
M["black_paint"] = flat("ROSENTORP black", srgb("#1E1D1C"), 0.42)
M["acacia"] = textured("Acacia light brown stain", os.path.join(TEX, "white_oak_veneer"), 0.6, value=0.78, sat=1.2, tint=(0.95, 0.78, 0.58), nor_strength=0.5, rough_add=0.1)
M["outdoor_cushion"] = textured("Frosön Duvholmen beige", os.path.join(TEX, "rough_linen"), 0.25, no_diffuse=True, base=srgb("#D3C8B6"), nor_strength=0.8, sheen=0.3)
M["jute"] = textured("LOHALS jute natural", os.path.join(TEX, "hessian_230"), 0.18, no_diffuse=True, base=srgb("#9E8F68"), nor_strength=1.5, sheen=0.0)

def _turn(objs, cx, cy, deg):
    """Rotate freshly built objects about a vertical axis through (cx, cy)."""
    R = Matrix.Translation((cx, cy, 0)) @ Matrix.Rotation(math.radians(deg), 4, "Z") @ Matrix.Translation((-cx, -cy, 0))
    for o in objs: o.matrix_world = R @ o.matrix_world

def _new_since(before): return [o for o in bpy.data.objects if o.name not in before]

def ikea_rosentorp(cx, cy, face_deg=-90, name="ROSENTORP"):
    """ROSENTORP counter stool with backrest, 40 × 45 × 92, seat h 63 (built facing -y, then turned)."""
    before = set(o.name for o in bpy.data.objects)
    sw, sd = 0.40, 0.36
    soft(name + " seat", cx - sw / 2, cx + sw / 2, cy - sd / 2, cy + sd / 2, 0.605, 0.63, M["black_paint"], r=0.012, crown=0.004, wobble=0.0, level=2)
    for (dx, dy) in ((-0.17, -0.15), (0.17, -0.15), (-0.17, 0.17), (0.17, 0.17)):
        top = 0.92 if dy > 0 else 0.605
        bx, by = cx + dx * 1.12, cy + dy * 1.12
        tx, ty = cx + dx * 0.92, cy + dy * 0.92
        cu = bpy.data.curves.new(name + " leg", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.016; cu.bevel_resolution = 3
        sp = cu.splines.new("POLY"); pts = [(bx, by, 0.0), (tx, ty, 0.605)] + ([(tx, ty + 0.01, top)] if dy > 0 else [])
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts): sp.points[i].co = (*p, 1)
        o = bpy.data.objects.new(name + " leg", cu); o.data.materials.append(M["black_paint"]); col("Interior").objects.link(o)
    for z in (0.25,):
        box(name + " footrest", cx - 0.19, cx + 0.19, cy - 0.185, cy - 0.165, z, z + 0.02, M["black_paint"], bevel=0.006, seg=2)
        box(name + " rail", cx - 0.20, cx + 0.20, cy + 0.17, cy + 0.19, z + 0.05, z + 0.07, M["black_paint"], bevel=0.006, seg=2)
    # curved back rail
    bm = bmesh.new(); N = 24; ring_prev = None
    for i in range(N + 1):
        t = i / N; x = cx - 0.19 + 0.38 * t; y = cy + 0.165 + 0.035 * math.sin(t * math.pi)
        r = [bm.verts.new((x, y, 0.80)), bm.verts.new((x, y + 0.02, 0.80)), bm.verts.new((x, y + 0.02, 0.90)), bm.verts.new((x, y, 0.90))]
        if ring_prev:
            for j in range(4): bm.faces.new((ring_prev[j], ring_prev[(j + 1) % 4], r[(j + 1) % 4], r[j]))
        ring_prev = r
    o = obj_from_bm(name + " back", bm, M["black_paint"]); b = o.modifiers.new("Bevel", "BEVEL"); b.width = 0.006; b.segments = 2
    _turn(_new_since(before), cx, cy, face_deg + 90)

def ikea_nammaro_sofa(x0, x1, y0, y1, name="NAMMARO sofa"):
    """NÄMMARÖ 3-seat modular sofa, 189 × 74 × 70, seat frame h 30, with Frösön/Duvholmen cushions; back on the south side (y0)."""
    n = 3; w = (x1 - x0) / n
    for k in range(n):
        a = x0 + k * w
        for (lx, ly) in ((a + 0.03, y0 + 0.03), (a + w - 0.03, y0 + 0.03), (a + 0.03, y1 - 0.03), (a + w - 0.03, y1 - 0.03)):
            box(name + " leg", lx - 0.025, lx + 0.025, ly - 0.025, ly + 0.025, 0.0, 0.30, M["acacia"], bevel=0.004, seg=2)
        box(name + " rail", a + 0.005, a + w - 0.005, y1 - 0.05, y1 - 0.005, 0.20, 0.27, M["acacia"], bevel=0.004, seg=2)
        s = y0 + 0.06
        while s < y1 - 0.06:
            box(name + " slat", a + 0.01, a + w - 0.01, s, s + 0.06, 0.27, 0.295, M["acacia"], bevel=0.004, seg=2); s += 0.08
        for z in (0.36, 0.46, 0.56, 0.66):
            box(name + " back slat", a + 0.01, a + w - 0.01, y0 + 0.01, y0 + 0.035, z, z + 0.06, M["acacia"], bevel=0.004, seg=2)
        box(name + " back post", a + 0.005, a + 0.045, y0, y0 + 0.045, 0.30, 0.70, M["acacia"], bevel=0.004, seg=2)
        box(name + " back post", a + w - 0.045, a + w - 0.005, y0, y0 + 0.045, 0.30, 0.70, M["acacia"], bevel=0.004, seg=2)
        soft(name + " seat cushion", a + 0.012, a + w - 0.012, y0 + 0.05, y1 - 0.01, 0.30, 0.40, M["outdoor_cushion"], r=0.04, crown=0.015)
        o = soft(name + " back cushion", a + 0.02, a + w - 0.02, y0 + 0.04, y0 + 0.17, 0.40, 0.78, M["outdoor_cushion"], r=0.05, crown=0.03)
        recenter(o); o.rotation_euler.x = math.radians(9)

def ikea_nammaro_table(x0, x1, y0, y1, h=0.75, name="NAMMARO table"):
    for (lx, ly) in ((x0 + 0.06, y0 + 0.06), (x1 - 0.06, y0 + 0.06), (x0 + 0.06, y1 - 0.06), (x1 - 0.06, y1 - 0.06)):
        box(name + " leg", lx - 0.03, lx + 0.03, ly - 0.03, ly + 0.03, 0.0, h - 0.03, M["acacia"], bevel=0.004, seg=2)
    box(name + " apron", x0 + 0.04, x1 - 0.04, y0 + 0.04, y1 - 0.04, h - 0.09, h - 0.03, M["acacia"], bevel=0.003, seg=1)
    s = x0
    while s < x1 - 0.01:
        box(name + " slat", s + 0.004, min(x1, s + 0.085) - 0.004, y0, y1, h - 0.03, h, M["acacia"], bevel=0.003, seg=2); s += 0.09

def ikea_nammaro_armchair(cx, cy, face_deg, name="NAMMARO chair"):
    """Dining armchair, seat h 42, straight slatted back, armrests; built facing +y then turned."""
    before = set(o.name for o in bpy.data.objects)
    W, D = 0.56, 0.56
    for (dx, dy, top) in ((-W / 2 + 0.03, D / 2 - 0.03, 0.66), (W / 2 - 0.03, D / 2 - 0.03, 0.66), (-W / 2 + 0.03, -D / 2 + 0.03, 0.86), (W / 2 - 0.03, -D / 2 + 0.03, 0.86)):
        box(name + " leg", cx + dx - 0.025, cx + dx + 0.025, cy + dy - 0.025, cy + dy + 0.025, 0.0, top, M["acacia"], bevel=0.004, seg=2)
    s = cy - D / 2 + 0.05
    while s < cy + D / 2 - 0.04:
        box(name + " slat", cx - W / 2 + 0.05, cx + W / 2 - 0.05, s, s + 0.05, 0.40, 0.42, M["acacia"], bevel=0.003, seg=2); s += 0.07
    for k in range(4):
        z = 0.50 + k * 0.09
        box(name + " back slat", cx - W / 2 + 0.05, cx + W / 2 - 0.05, cy - D / 2 + 0.01, cy - D / 2 + 0.03, z, z + 0.06, M["acacia"], bevel=0.003, seg=2)
    for sx in (-1, 1):
        box(name + " arm", cx + sx * (W / 2 - 0.03) - 0.03, cx + sx * (W / 2 - 0.03) + 0.03, cy - D / 2, cy + D / 2 + 0.02, 0.66, 0.69, M["acacia"], bevel=0.005, seg=2)
    soft(name + " cushion", cx - W / 2 + 0.06, cx + W / 2 - 0.06, cy - D / 2 + 0.05, cy + D / 2 - 0.02, 0.42, 0.47, M["outdoor_cushion"], r=0.025, crown=0.01)
    _turn(_new_since(before), cx, cy, face_deg - 90)
print("IKEA round 2 ready")

# ---------------------------------------------------------------- real IKEA models via the IKEA Browser add-on (extensions.blender.org/add-ons/ikea-browser)
import sys as _sys, pathlib as _pl
def ikea_glb(item_no, loc, rot_deg=0.0, name=None, stand_up=False):
    """Import IKEA's own 3D model for an article number and stand it at loc (bbox centre, floor at loc.z), turned rot_deg about Z.
    Returns the new objects, or None when the add-on or the model isn't available (callers then fall back to the modelled piece)."""
    lib = _sys.modules.get("bl_ext.user_default.ikea_browser.ikea_lib")
    try:
        if lib:
            W = lib.IkeaApiWrapper("gb", "en"); W.cache_dir = _pl.Path(bpy.utils.extension_path_user("bl_ext.user_default.ikea_browser")) / "cache"
            path = W.get_model(item_no)
        else:
            path = os.path.join(os.environ.get("APPDATA", ""), "Blender Foundation", "Blender", "5.2", "extensions", ".user", "user_default", "ikea_browser", "cache", item_no, "model.glb")
            if not os.path.exists(path): return None
    except Exception as e:
        print("IKEA model unavailable", item_no, str(e)[:80]); return None
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        for c in list(o.users_collection): c.objects.unlink(o)
        col("IKEA").objects.link(o); o["ikeaItemNo"] = item_no
        if name: o.name = name
    bpy.context.view_layer.update()
    if stand_up:      # frames ship lying flat: stand them up, leaning back 10 degrees
        Rx = Matrix.Rotation(math.radians(80), 4, "X")
        for r in [o for o in new if o.parent is None]: r.matrix_world = Rx @ r.matrix_world
        bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
    c = Vector(((min(p.x for p in pts) + max(p.x for p in pts)) / 2, (min(p.y for p in pts) + max(p.y for p in pts)) / 2, min(p.z for p in pts)))
    T = Matrix.Translation(Vector(loc)) @ Matrix.Rotation(math.radians(rot_deg), 4, "Z") @ Matrix.Translation(-c)
    for r in [o for o in new if o.parent is None]: r.matrix_world = T @ r.matrix_world
    for o in new:
        if o.type == "MESH": o.data.shade_smooth() if False else None
    return new
print("IKEA glb import ready")

# ---------------------------------------------------------------- dressing the home: a family of four lives here
def _bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))), Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))

def snap(objs, axis, value, side="max"):
    """Move a freshly imported group so its bbox min/max on axis ('x' or 'y') sits at value (e.g. flat against a wall)."""
    if not objs: return objs
    mn, mx = _bbox(objs); i = "xyz".index(axis); cur = (mx if side == "max" else mn)[i]
    d = Vector((0, 0, 0)); d[i] = value - cur
    for r in [o for o in objs if o.parent is None]: r.location += d
    return objs

def frame_tv(x_wall, yc, zc, w=1.45, h=0.83, depth=0.026, name="TV"):
    """A real 65-inch set flat on the wall, in art mode: thin black bezel, matte screen showing a painting."""
    box(name + " body", x_wall, x_wall + depth, yc - w / 2, yc + w / 2, zc - h / 2, zc + h / 2, M["frame"], bevel=0.003, seg=2)
    m, nt, b = new_mat("TV art mode")
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img(os.path.join(PROJECT, "blender", "tv_art.jpg"), True)
    tc = nt.nodes.new("ShaderNodeTexCoord"); nt.links.new(tc.outputs["UV"], t.inputs[0])
    nt.links.new(t.outputs[0], b.inputs["Base Color"]); nt.links.new(t.outputs[0], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 0.16; b.inputs["Roughness"].default_value = 0.7
    bm = bmesh.new(); bz = 0.012; x = x_wall + depth + 0.0005
    vs = [bm.verts.new(v) for v in ((x, yc + w / 2 - bz, zc - h / 2 + bz), (x, yc - w / 2 + bz, zc - h / 2 + bz), (x, yc - w / 2 + bz, zc + h / 2 - bz), (x, yc + w / 2 - bz, zc + h / 2 - bz))]
    f = bm.faces.new(vs); uv = bm.loops.layers.uv.new()
    for l, c in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))): l[uv].uv = c
    obj_from_bm(name + " screen", bm, m)


# ---------------------------------------------------------------- contact helpers: things rest on surfaces and never interpenetrate
from mathutils.bvhtree import BVHTree as _BVH
def _bvh(objs):
    dg = bpy.context.evaluated_depsgraph_get(); bm = bmesh.new()
    for o in objs:
        if o.type not in ("MESH", "CURVE"): continue
        ev = o.evaluated_get(dg)
        try: me = ev.to_mesh()
        except Exception: continue
        if me is None: continue
        b2 = bmesh.new(); b2.from_mesh(me); b2.transform(o.matrix_world); ev.to_mesh_clear()
        me2 = bpy.data.meshes.new("tmp"); b2.to_mesh(me2); b2.free(); bm.from_mesh(me2); bpy.data.meshes.remove(me2)
    t = _BVH.FromBMesh(bm); bm.free(); return t

def _roots(objs): return [o for o in objs if o.parent is None or o.parent not in objs]

def move(objs, d):
    for r in _roots(objs): r.location += Vector(d)
    bpy.context.view_layer.update()

def drop(objs, clearance=0.0005):
    """Lower/raise a group so it rests on the highest surface under its footprint (ignores itself)."""
    if not objs: return objs
    bpy.context.view_layer.update(); mn, mx = _bbox(objs); own = set(objs); dg = bpy.context.evaluated_depsgraph_get(); sc = bpy.context.scene
    top = 0.0; any_hit = False
    for i in range(5):
        for j in range(5):
            x = mn.x + (mx.x - mn.x) * (0.15 + 0.7 * i / 4); y = mn.y + (mx.y - mn.y) * (0.15 + 0.7 * j / 4)
            o = Vector((x, y, mx.z + 0.01))
            for _ in range(12):
                hit, loc, nor, idx, ob, _m = sc.ray_cast(dg, o, Vector((0, 0, -1)))
                if not hit: break
                if ob in own or ob.name.startswith(("Floor", "Slab")) is False and False: pass
                if ob in own or (ob.type == "LIGHT"): o = loc - Vector((0, 0, 0.0005)); continue
                if loc.z > top or not any_hit: top = loc.z if not any_hit else max(top, loc.z)
                any_hit = True; break
    if any_hit: move(objs, (0, 0, top + clearance - mn.z))
    return objs

def clear_of(objs, others, direction, step=0.004, n=60):
    """Nudge a group along direction until it no longer intersects the given objects."""
    if not objs: return objs
    tb = _bvh(others)
    for k in range(n):
        if not tb.overlap(_bvh(objs)): return objs
        move(objs, Vector(direction) * step)
    print("clear_of gave up for", objs[0].name)
    return objs

def by_prefix(*prefixes): return [o for o in bpy.data.objects if o.name.startswith(prefixes) and o.type in ("MESH", "CURVE")]

def dress():
    G = ikea_glb
    # living: sofa and armchairs are IKEA's own models where available (fallbacks were built in the furniture loop)
    # toys live in the girls' rooms (bedrooms pass), not on the living-room floor
    drop(G("50504734", (5.78, 7.40, 0.47), 15, "OMBONAD tray"))
    for i, y in enumerate((7.40, 7.74)):
        o = drop(G("00566395", (3.72, y, 0.50), 90 - 6 + 12 * i, "RODALM frame", stand_up=True))
    box("Books BESTA a", 3.56, 3.84, 8.05, 8.28, 0.487, 0.512, M["paper"], bevel=0.003); box("Books BESTA b", 3.58, 3.82, 8.07, 8.26, 0.512, 0.532, M["paper2"], bevel=0.003)
    drop([box("Book side", 6.45, 6.66, 8.86, 9.02, 0.60, 0.625, M["paper2"], bevel=0.003)])
    # cushions and a throw on the HYLTARP
    sofa = by_prefix("HYLTARP")
    if sofa:
        sc = bpy.context.scene; dg = bpy.context.evaluated_depsgraph_get()
        def first_hit(o, d):
            own = set()
            for _ in range(10):
                hit, loc, nor, idx, ob, _m = sc.ray_cast(dg, o, d)
                if not hit: return None
                if ob.name.startswith("HYLTARP"): return loc
                o = loc + d * 0.001
            return None
        for (yy, m, rz) in ((8.20, M["linen"], 8), (7.05, M["linen_oat"], -6)):
            seat = first_hit(Vector((7.10, yy, 1.6)), Vector((0, 0, -1)))          # seat top (measured ~0.44)
            sz = (seat.z if seat else 0.44) + 0.004
            back = first_hit(Vector((6.90, yy, sz + 0.06)), Vector((1, 0, 0)))     # where the back cushion starts (~7.42)
            bx = (back.x if back else 7.42) - 0.012
            o = soft("Cushion", bx - 0.15, bx, yy - 0.22, yy + 0.22, sz, sz + 0.44, m, r=0.06, crown=0.045)
            piv = Vector((bx - 0.15, yy, sz)); o.data.transform(Matrix.Translation(-piv)); o.location = piv      # pivot on the front-bottom edge, resting on the seat
            o.rotation_euler = (0.0, math.radians(9), math.radians(rz))           # leans back into the cushion behind it
            bpy.context.view_layer.update()
            mn, mx = _bbox([o]); move([o], (0, 0, sz + 0.002 - mn.z))             # sits on the seat, not in it
            clear_of([o], sofa, (-1, 0, 0), step=0.003, n=40)

    # kitchen: a working family kitchen
    G("20557168", (3.95, 0.70, 0.92), 8, "SMAAETA board")
    G("20532724", (2.50, 0.60, 0.92), 0, "IKEA 365 coffee maker")
    for i, x in enumerate((2.80, 2.95, 3.10)): G("50213546", (x, 0.52, 1.57), 0, "KORKEN jar")
    G("90596171", (2.95, 0.62, 0.92), 0, "BRUGDHAJ utensils")
    G("60484250", (3.27, 0.85, 0.926), 0, "IKEA 365 pot")
    G("70565948", (5.15, 0.66, 0.92), 0, "STAMLING drainer")
    drop(G("00581800", (5.78, 1.35, 0.95), 0, "KANELMOTT fruit stand"))
    bowl = drop(G("60214343", (3.30, 2.82, 0.95), 0, "BLANDA bamboo bowl"))
    placed = []
    for k, (a, dx, dy) in enumerate((("food_apple_01", -0.055, 0.0), ("food_pomegranate_01", 0.05, 0.03), ("food_lime_01", 0.01, -0.06))):
        before = set(bpy.data.objects); place_model(a, (3.30 + dx, 2.82 + dy, 1.10), k * 0.9, 1.0)
        new = [o for o in bpy.data.objects if o not in before]
        drop(new)
        if placed: clear_of(new, placed, (dx, dy, 0) if (dx or dy) else (0, 0, 1), step=0.003)
        placed += new
    # entry: keys on the bench
    t = drop(G("20056642", (6.25, 4.60, 0.60), 0, "SKALA tray")); clear_of(t, by_prefix("Niche", "Shoe cabinet"), (0, 1, 0)); drop(t)
    # balcony
    drop(G("80326537", (2.45, 11.22, 0.40), 0, "POMP lantern"))
    e = G("80600885", (7.30, 10.15, 0.0), 0, "FEJKA eucalyptus")
    if e:
        mn, mx = _bbox(e); move(e, (min(0, 7.77 - mx.x), max(0, 9.73 - mn.y), 0))
    # the coffee-table bowl sits on the tray
    for o in by_prefix("wooden_bowl_01"): pass

print("dressing ready")
