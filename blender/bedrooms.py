# Bedrooms, the wardrobe walk and the girls' toys — IKEA's own models where they exist.
# Exec'd from build_scene.py after the public rooms (shares its globals and the helpers in ikea_models.py).
import re
G = ikea_glb
if "mirror" not in M:
    _m = bpy.data.materials.new("Mirror"); _m.use_nodes = True; _b = _m.node_tree.nodes["Principled BSDF"]
    _b.inputs["Base Color"].default_value = (0.92, 0.93, 0.92, 1); _b.inputs["Metallic"].default_value = 1.0; _b.inputs["Roughness"].default_value = 0.02
    M["mirror"] = _m
if "kelvin_rgb" not in globals():
    def kelvin_rgb(k):
        t = k / 100.0
        r = 1.0 if t <= 66 else min(1, max(0, 1.2929 * (t - 60) ** -0.1332))
        g = min(1, max(0, (0.3900815 * math.log(t) - 0.6318414) if t <= 66 else 1.1298909 * (t - 60) ** -0.0755148))
        b = 1.0 if t >= 66 else (0.0 if t <= 19 else min(1, max(0, 0.5432068 * math.log(t - 10) - 1.1962541)))
        return (r, g, b)

def curtain(name, axis, a0, a1, c, zb=0.02, zt=H - 0.02):
    """Sheer linen curtain gathered beside a window. axis 'x' runs along x at y=c, 'y' along y at x=c."""
    bm = bmesh.new(); n = max(40, int((a1 - a0) / 0.012))
    for i in range(n + 1):
        u = a0 + (a1 - a0) * i / n; w = 0.028 * math.sin(i / n * math.pi * 2 * max(3, (a1 - a0) / 0.10))
        p0 = (u, c + w, zb) if axis == "x" else (c + w, u, zb); p1 = (u, c + w, zt) if axis == "x" else (c + w, u, zt)
        bm.verts.new(p0); bm.verts.new(p1)
    bm.verts.ensure_lookup_table()
    for i in range(n): bm.faces.new((bm.verts[2 * i], bm.verts[2 * i + 2], bm.verts[2 * i + 3], bm.verts[2 * i + 1]))
    o = obj_from_bm(name, bm, M["curtain"]); o.data.shade_smooth(); o.modifiers.new("Solid", "SOLIDIFY").thickness = 0.002
    return o

def curtains_open(name, axis, w0, w1, c):
    """Two gathered sheer panels parked either side of a window."""
    return [curtain(name + " L", axis, w0 - 0.14, w0 + 0.24, c), curtain(name + " R", axis, w1 - 0.24, w1 + 0.14, c)]

def ray_top(x, y, ignore=()):
    sc = bpy.context.scene; dg = bpy.context.evaluated_depsgraph_get(); o = Vector((x, y, 2.4))
    for _ in range(12):
        hit, loc, nor, idx, ob, _m = sc.ray_cast(dg, o, Vector((0, 0, -1)))
        if not hit: return 0.0
        if ob in ignore or ob.type == "LIGHT" or ob.name.startswith(("Ceiling", "Slab above")): o = loc - Vector((0, 0, 0.001)); continue
        return loc.z
    return 0.0

if "cotton" not in M:
    M["cotton"] = textured("Cotton sheet", os.path.join(TEX, "rough_linen"), 0.35, no_diffuse=True, base=srgb("#EEEAE2"), nor_strength=0.5, sheen=0.25)

def drape(name, cx, cy, foot, w, l, top, head, side_out, foot_out, drop_side, drop_foot, mat, thick=0.03, fold=0.0, tuck_neg=False):
    """A duvet that lies on the mattress and falls over the sides and the foot: a parametric sheet with a
    rounded edge, a slight flare, soft wrinkles, then solidified. head '+y'/'-y'/'+x'/'-x'; w across, l along (foot -> fold)."""
    bm = bmesh.new(); nu, nv = 56, 64
    def edge(s, half, out, drop):
        # s: distance past the mattress edge along the cloth. Returns (horizontal offset, vertical drop)
        r = max(0.02, out)
        if s <= 0: return s, 0.0
        if s <= math.pi * r / 2: return r * math.sin(s / r), r * (1 - math.cos(s / r))
        t = min(s - math.pi * r / 2, max(0.0, drop - r)); return r + t * 0.10, r + t
    side_len = math.pi * max(0.02, side_out) / 2 + max(0.0, drop_side - side_out)
    foot_len = math.pi * max(0.02, foot_out) / 2 + max(0.0, drop_foot - foot_out)
    seed = random.Random(hash(name) & 0xffff).random() * 40
    rows = []
    for j in range(nv + 1):
        vv = -foot_len + (l + foot_len) * j / nv          # along: <0 hangs over the foot, l is the fold line
        row = []
        for i in range(nu + 1):
            u_lo = -w / 2 if tuck_neg else -(w / 2 + side_len)
            uu = u_lo + (w / 2 + side_len - u_lo) * i / nu
            su = abs(uu) - w / 2
            hx, dx = edge(su, w / 2, side_out, drop_side)
            X = math.copysign(w / 2 + hx, uu) if su > 0 else uu
            hy, dy = edge(-vv, 0, foot_out, drop_foot)
            Y = -hy if vv < 0 else vv
            Z = top - dx - dy
            n = noise.noise(Vector((X * 4 + seed, Y * 3, 0.3)))
            Z += 0.006 * n + 0.004 * math.sin(Y * 23 + X * 5) * (1 if su > 0 or vv < 0 else 0.4)
            X += 0.008 * n * (1 if su > 0 else 0)
            # into world: local X across, Y along from the foot toward the head
            sgn = 1 if head[0] == "+" else -1
            P = (cx + X, foot + sgn * Y, Z) if head[1] == "y" else (foot + sgn * Y, cy + X, Z)
            row.append(bm.verts.new(P))
        rows.append(row)
    for j in range(nv):
        for i in range(nu):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    o = obj_from_bm(name, bm, mat)
    so = o.modifiers.new("Thick", "SOLIDIFY"); so.thickness = thick; so.offset = 1.0
    ss = o.modifiers.new("Sub", "SUBSURF"); ss.levels = 1; ss.render_levels = 2
    o.data.shade_smooth()
    if o.data.polygons and o.data.polygons[len(o.data.polygons) // 2].normal.z < 0: so.offset = -1.0
    return o

def bedding(prefix, bed_objs, head, w, l, pillows=2, duvet=M["linen_oat"], pillow_mat=None, drop_side=0.22, drop_foot=0.20, tuck=False, wall_side=False):
    """Mattress (if the frame has none), a draped duvet with a turned-down fold, and pillows. head: '+x','-x','+y','-y'."""
    if not bed_objs: return []
    mn, mx = _bbox(bed_objs); cx, cy = (mn.x + mx.x) / 2, (mn.y + mx.y) / 2
    along_y = head[1] == "y"; s = 1 if head[0] == "+" else -1
    z = ray_top(cx, cy)
    made = []
    hw, hl = w / 2, l / 2
    if z < 0.40:
        made.append(soft(prefix + " mattress", cx - (hw if along_y else hl), cx + (hw if along_y else hl),
                         cy - (hl if along_y else hw), cy + (hl if along_y else hw), z + 0.02, z + 0.21, M["cotton"], r=0.04, crown=0.006, wobble=0.0))
        z += 0.21
    top = z + 0.018
    outer_half = ((mx.x - mn.x) if along_y else (mx.y - mn.y)) / 2
    outer_len = (mx.y - mn.y) if along_y else (mx.x - mn.x)
    c_along = cy if along_y else cx
    foot = c_along - s * (hl - (0.05 if tuck else 0.0))
    if tuck: side_out = foot_out = 0.02; ds = df = 0.0
    else:
        side_out = max(0.03, outer_half - hw + 0.02); ds = drop_side
        foot_out = max(0.03, (outer_len - l) / 2 + 0.02) if (outer_len - l) < 0.25 else 0.03; df = drop_foot if (outer_len - l) < 0.25 else 0.03
    fold_at = l - 0.52 - (0.05 if tuck else 0.0)
    made.append(drape(prefix + " duvet", cx, cy, foot, w - (0.08 if tuck else 0.0), fold_at, top, head, side_out, foot_out, ds, df, duvet, tuck_neg=wall_side))
    # the turned-down top of the duvet, a soft roll across the bed
    f0, f1 = sorted([foot + s * (fold_at - 0.26), foot + s * (fold_at + 0.02)])
    ext = side_out if not tuck else 0.0
    if along_y: fr = soft(prefix + " duvet fold", cx - hw - (0.0 if wall_side else ext), cx + hw + ext, f0, f1, top + 0.045, top + 0.095, duvet, r=0.025, crown=0.018, wobble=0.005)
    else: fr = soft(prefix + " duvet fold", f0, f1, cy - hw - ext, cy + hw + ext, top + 0.045, top + 0.095, duvet, r=0.025, crown=0.018, wobble=0.005)
    made.append(fr)
    head_c = c_along + s * hl
    for k in range(pillows):
        o_ = (k - (pillows - 1) / 2) * (w / pillows)
        a0, a1 = sorted([head_c - s * 0.05, head_c - s * 0.44])
        b0, b1 = o_ - w / pillows / 2 + 0.05, o_ + w / pillows / 2 - 0.05
        if along_y: pp = soft(prefix + " pillow", cx + b0, cx + b1, a0, a1, top, top + 0.14, pillow_mat or M["cotton"], r=0.05, crown=0.05, wobble=0.005)
        else: pp = soft(prefix + " pillow", a0, a1, cy + b0, cy + b1, top, top + 0.14, pillow_mat or M["cotton"], r=0.05, crown=0.05, wobble=0.005)
        recenter(pp)
        if along_y: pp.rotation_euler.x = math.radians(-14 * s)
        else: pp.rotation_euler.y = math.radians(14 * s)
        made.append(pp)
    bpy.context.view_layer.update()
    for o in made:
        if o.name.startswith((prefix + " pillow")):
            mn2, _ = _bbox([o]); move([o], (0, 0, top - 0.004 - mn2.z))
    return made

BOOK_MATS = [flat("Book " + c, srgb(c), 0.75) for c in ("#CFC5B4", "#9A8A78", "#6E7B6A", "#B9785E", "#3F4A55", "#E3DCCD", "#C9A86A", "#8C5A4A", "#596B78", "#D8C3B0")]
if "linen_rose" not in M:
    M["linen_rose"] = textured("Linen dusty rose", os.path.join(TEX, "rough_linen"), 0.27, no_diffuse=True, base=srgb("#C59A8E"), nor_strength=0.8, sheen=0.3)
    M["linen_ochre"] = textured("Linen ochre", os.path.join(TEX, "rough_linen"), 0.27, no_diffuse=True, base=srgb("#C49A5A"), nor_strength=0.8, sheen=0.3)

def book_row(name, axis, a0, a1, c0, c1, z, hmax=0.30, seed=1, lean_end=True):
    """Upright books on a shelf from a0 to a1 along axis ('x' or 'y'); c0..c1 is the shelf depth range."""
    rnd = random.Random(seed); a = a0; out = []
    while a < a1 - 0.02:
        t = rnd.uniform(0.016, 0.042); h = rnd.uniform(0.62, 1.0) * hmax; d = rnd.uniform(0.70, 0.95) * (c1 - c0)
        if a + t > a1: break
        m = BOOK_MATS[rnd.randrange(len(BOOK_MATS))]
        if axis == "x": out.append(box(name, a, a + t - 0.001, c1 - d, c1, z, z + h, m, bevel=0.002, seg=1))
        else: out.append(box(name, c1 - d, c1, a, a + t - 0.001, z, z + h, m, bevel=0.002, seg=1))
        a += t
        if rnd.random() < 0.07: a += rnd.uniform(0.04, 0.10)
    return out

def shelf_tops(x, y, objs, zmax=2.3):
    """Heights of the horizontal surfaces of `objs` under (x, y), top to bottom."""
    sc = bpy.context.scene; dg = bpy.context.evaluated_depsgraph_get(); o = Vector((x, y, zmax)); tops = []
    own = set(objs)
    for _ in range(30):
        hit, loc, nor, idx, ob, _m = sc.ray_cast(dg, o, Vector((0, 0, -1)))
        if not hit or loc.z < 0.02: break
        if ob in own and nor.z > 0.9: tops.append(loc.z)
        o = loc - Vector((0, 0, 0.004))
    return tops

def fill_bookcase(objs, face, seed=3):
    """Books (and the odd gap) on every shelf of an imported bookcase. face: the open side, '-y','+y','-x','+x'."""
    mn, mx = _bbox(objs); cx, cy = (mn.x + mx.x) / 2, (mn.y + mx.y) / 2
    tops = shelf_tops(cx, cy, objs)
    for k, z in enumerate(tops):
        nxt = [t for t in tops if t > z + 0.05]; clear = (min(nxt) - z - 0.03) if nxt else 0.30
        if clear < 0.12 or z > 2.0: continue
        hmax = min(0.32, clear - 0.01)
        if face[1] == "y":
            c0, c1 = (mn.y + 0.03, mx.y - 0.03)
            book_row("Shelf book", "x", mn.x + 0.03, mn.x + 0.03 + (mx.x - mn.x - 0.06) * (0.55 + 0.4 * ((k * 7 + seed) % 3) / 2), c0, c1, z + 0.001, hmax, seed * 31 + k)
        else:
            c0, c1 = (mn.x + 0.03, mx.x - 0.03)
            book_row("Shelf book", "y", mn.y + 0.03, mn.y + 0.03 + (mx.y - mn.y - 0.06) * 0.7, c0, c1, z + 0.001, hmax, seed * 31 + k)

def cushion_on(name, x, y, lean_axis, lean_deg, mat, sofa, push):
    """A throw cushion standing on a seat, leaning back, nudged clear of the sofa."""
    o = soft(name, x - 0.035, x + 0.035, y - 0.22, y + 0.22, 1.0, 1.44, mat, r=0.03, crown=0.0, wobble=0.004) if lean_axis == "y" else \
        soft(name, x - 0.22, x + 0.22, y - 0.035, y + 0.035, 1.0, 1.44, mat, r=0.03, crown=0.0, wobble=0.004)
    # puff it: thick in the middle, thin at the seams, corners pulled in
    mw = o.matrix_world; c = Vector((x, y, 1.22))
    for v in o.data.vertices:
        p = v.co.copy(); lx, ly, lz = (p.y - y, p.x - x, p.z - 1.22) if lean_axis == "y" else (p.x - x, p.y - y, p.z - 1.22)
        u, w_ = min(1, abs(lx) / 0.22), min(1, abs(lz) / 0.22)
        bulge = 0.055 * (1 - u * u) * (1 - w_ * w_)
        pinch = 0.03 * (u * w_) ** 2
        if lean_axis == "y": v.co.x += math.copysign(bulge, p.x - x); v.co.y -= math.copysign(pinch, ly * 1 + 1e-9) * 0; v.co.z -= math.copysign(pinch, lz)
        else: v.co.y += math.copysign(bulge, p.y - y); v.co.z -= math.copysign(pinch, lz)
    recenter(o)
    if lean_axis == "y": o.rotation_euler.y = math.radians(lean_deg)
    else: o.rotation_euler.x = math.radians(lean_deg)
    drop([o]); clear_of([o], sofa, push, 0.004, 40); drop([o])
    return o

def fit(objs, size):
    """Scale a (soft-toy) group about its floor centre so its largest side is `size` metres."""
    if not objs: return objs
    bpy.context.view_layer.update(); mn, mx = _bbox(objs); d = max(mx - mn)
    if d <= size: return objs
    k = size / d; c = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    S = Matrix.Translation(c) @ Matrix.Scale(k, 4) @ Matrix.Translation(-c)
    for r in _roots(objs): r.matrix_world = S @ r.matrix_world
    bpy.context.view_layer.update(); return objs

def toy(item, x, y, rz, name, size, z=1.4):
    return drop(fit(G(item, (x, y, z), rz, name), size))

def lamp_on(item, x, y, circuit, full=4.0, name="Table lamp"):
    objs = drop(G(item, (x, y, 1.2), 0, name))
    if objs:
        mn, mx = _bbox(objs)
        L = bpy.data.lights.new(name + " bulb", "POINT"); L.shadow_soft_size = 0.04
        lo = bpy.data.objects.new(name + " bulb", L); lo.location = (x, y, mn.z + (mx.z - mn.z) * 0.72); col("Lights").objects.link(lo)
        lo["circuit"] = circuit; lo["full"] = full; lo["cct"] = 2200; L.color = kelvin_rgb(2200); L.energy = 0
    return objs

# ================================================================ wardrobe walk (built-in, fluted oak)
fluted("Wardrobe walk", -3.44, -2.85, 6.05, 9.53, 0.0, H, "-x", M["oak"])
box("Walk runner", -4.30, -3.55, 6.30, 9.20, 0.0, 0.006, M["jute"], bevel=0.002, seg=1)

# ================================================================ main bedroom (head under the north window: the lit sheer is the headboard light)
bed = G("49496674", (-5.75, 11.16 - 1.05, 0.0), 0, "TONSTAD bed")      # clear of the sheer in front of the window
main_bedding = bedding("Main bed", bed, "+y", 1.55, 1.96, pillows=2, duvet=M["linen_oat"])
throw = soft("Main bed throw", -6.55, -4.95, 9.50, 9.90, 0.0, 0.04, M["linen"], r=0.015, crown=0.01)
drop([throw])
for x in (-6.85, -4.62):
    G("80489322", (x, 11.16 - 0.20, 0.0), 0, "TONSTAD bedside")
lamp_on("90601200", -6.85, 10.96, "MST_LAMPS", 4.0, "KUDDLAVA lamp W")
lamp_on("90601200", -4.62, 10.96, "MST_LAMPS", 4.0, "KUDDLAVA lamp E")
G("90415689", (-5.75, 8.92, 0.0), 90, "LINDKNUD rug")
G("00541531", (-7.05, 8.45, 0.0), 0, "OKENSAND floor lamp")
curtain("Main curtain N", "x", -6.55, -4.85, 11.22)
curtains_open("Main curtain W", "y", 9.11, 10.52, -7.25)

# ================================================================ teen room (the safe room): a 1.40 bed, desk + dressing mirror, wardrobe
tb_x0, tb_x1, tb_y0, tb_y1 = -2.58, -1.18, 7.14, 9.18
box("Teen bed platform", tb_x0, tb_x1, tb_y0, tb_y1 - 0.08, 0.06, 0.26, M["oak_ikea"], bevel=0.008, seg=2)
box("Teen bed plinth", tb_x0 + 0.06, tb_x1 - 0.06, tb_y0 + 0.06, tb_y1 - 0.14, 0.0, 0.06, M["frame"])
soft("Teen bed mattress", tb_x0 + 0.02, tb_x1 - 0.02, tb_y0 + 0.02, tb_y1 - 0.10, 0.26, 0.46, M["ceramic"], r=0.04, crown=0.006, wobble=0.0)
soft("Teen headboard", tb_x0, tb_x1, tb_y1 - 0.09, tb_y1, 0.26, 0.86, M["linen"], r=0.04, crown=0.02)
tbed = [o for o in bpy.data.objects if o.name.startswith("Teen bed")]
bedding("Teen bed", tbed, "+y", 1.36, 1.96, pillows=2, duvet=M["linen_rose"], pillow_mat=M["linen_oat"], drop_side=0.18, wall_side=True)
G("80489322", (-0.97, 8.96, 0.0), 0, "TONSTAD bedside teen")
lamp_on("90601200", -0.97, 8.96, "MAM_LAMP", 3.5, "KUDDLAVA lamp teen")
G("69521620", (0.32 - 0.30, 8.20, 0.0), -90, "LAGKAPTEN ALEX desk")
drop(G("90404921", (0.10, 8.75, 0.9), -90, "NAVLINGE lamp"))
chair = G("30492204", (-0.55, 8.15, 0.0), 90, "FLINTAN chair")
G("70530609", (-2.60 + 0.49, 6.16 + 0.31, 0.0), 180, "VILHATTEN wardrobe")
G("00396242", (-1.35, 6.45, 0.0), 180, "KNAPPER mirror")
box("Teen wall mirror frame", 0.300, 0.318, 7.80, 8.60, 0.98, 1.78, M["oak_ikea"], bevel=0.004)     # between the MAM_MIRROR bars, over the desk
box("Teen wall mirror", 0.296, 0.300, 7.82, 8.58, 1.00, 1.76, M["mirror"], bevel=0.0, seg=1)
G("20576435", (-1.40, 7.78, 0.0), 90, "ARENDE rug")
for k, (item, x, y, rz) in enumerate((("80602083", -2.20, 8.80, 20), ("50522101", -1.55, 8.84, -15))):   # her plush toys live on the bed
    toy(item, x, y, rz, "Teen plush", 0.34)
box("Teen shelf", -2.60, -2.38, 7.55, 8.98, 1.42, 1.445, M["oak_ikea"], bevel=0.004)
book_row("Teen book", "y", 7.60, 8.18, -2.60, -2.40, 1.446, 0.26, 11)
for k, y in enumerate((8.38, 8.76)):
    drop(G("00566395", (-2.48, y, 1.6), 90 + (-6 + 12 * k), "RODALM frame teen", stand_up=True))
curtains_open("Teen curtain", "x", -1.31, -0.27, 9.25)

# ================================================================ office + game room
G("69521620", (1.95, 9.14 - 0.30, 0.0), 0, "LAGKAPTEN ALEX desk office")
drop(G("80106012", (2.45, 8.97, 0.9), 200, "FORSA lamp"))
G("90320224", (1.90, 8.22, 0.0), 180, "ALEFJALL chair")
G("09387021", (3.39 - 0.555, 7.62, 0.0), -90, "LYCKSELE sofa bed")
G("99188343", (0.56 + 0.207, 7.62, 0.0), 90, "BESTA office")
frame_tv(0.56, 7.62, 1.22, w=1.23, h=0.71, name="Office TV")
_sofa = [o for o in bpy.data.objects if o.name.startswith("LYCKSELE")]
if _sofa:
    smn, smx = _bbox(_sofa)
    for k, (yy, m) in enumerate(((smx.y - 0.32, M["linen_ochre"]), (smn.y + 0.32, M["linen"]))):
        cushion_on("Office cushion", smx.x - 0.66, yy, "y", 14, m, _sofa, (-1, 0, 0))
for k, x in enumerate((2.19, 2.99)):
    fill_bookcase(G("10508932", (x, 6.01 + 0.14, 0.0), 180, "BILLY bookcase"), "+y", seed=5 + k)
G("20576435", (1.62, 7.55, 0.0), 0, "ARENDE rug office")
curtains_open("Office curtain", "x", 1.29, 2.50, 9.20)

# ================================================================ toddler room: everything at her height, toys put away
kura = G("80253809", (-7.34 + 1.045 + 0.02, 8.02 - 0.495 - 0.02, 0.0), 0, "KURA bed") or []
if kura:   # KURA turned upside down is the low floor bed — the right height for a three-year-old
    mn, mx = _bbox(kura); c = (mn + mx) / 2
    Rx = Matrix.Translation(c) @ Matrix.Rotation(math.pi, 4, "X") @ Matrix.Translation(-c)
    for r in _roots(kura): r.matrix_world = Rx @ r.matrix_world
    bpy.context.view_layer.update(); mn, _ = _bbox(kura); move(kura, (0, 0, -mn.z))
bedding("Toddler bed", kura, "-x", 0.86, 1.96, pillows=1, duvet=M["linen"], tuck=True)
toy("30373588", -6.45, 7.60, 15, "BLAHAJ", 0.55, z=0.45)                 # BLÅHAJ sleeps in her bed
toy("00402813", -7.00, 7.40, -60, "DJUNGELSKOG bear", 0.34, z=0.45)
G("39574865", (-4.53 - 0.22 - 0.01, 6.60, 0.0), 90, "TROFAST")
G("60322173", (-4.80, 7.55, 0.0), 0, "FLADIS toy basket")
toy("80602083", -4.80, 7.55, 0, "Basket bear", 0.26)
toy("50522101", -4.76, 6.95, 90, "TROFAST plush", 0.24)
G("50298418", (-5.75, 6.25, 0.0), 0, "FLISAT table")
for y in (5.72, 6.78):      # FLISAT stools (the IKEA file is only the seat insert, so model the stool)
    box("FLISAT stool", -5.90, -5.60, y - 0.13, y + 0.13, 0.275, 0.30, M["oak_ikea"], bevel=0.006, seg=2)
    for dx in (-0.12, 0.12):
        for dy in (-0.10, 0.10):
            box("FLISAT stool", -5.75 + dx - 0.016, -5.75 + dx + 0.016, y + dy - 0.016, y + dy + 0.016, 0.0, 0.275, M["oak_ikea"], bevel=0.004, seg=2)
    box("FLISAT stool", -5.88, -5.62, y - 0.012, y + 0.012, 0.10, 0.125, M["oak_ikea"], bevel=0.003, seg=1)
drop(G("50589361", (-5.85, 6.25, 0.9), 30, "LILLABO cars"))
G("10460888", (-7.34 + 0.42, 4.76 + 0.28, 0.0), 180, "SMAGORA wardrobe")
G("60603026", (-6.05, 6.20, 0.0), 90, "STAPPSPARV rug toddler")
fd = G("80614566", (-4.53 - 0.14, 6.60, 0.85), -90, "FLISAT book display")
if fd:     # her picture books, covers out
    fmn, fmx = _bbox(fd); rnd = random.Random(7)
    for k, z in enumerate(shelf_tops((fmn.x + fmx.x) / 2, (fmn.y + fmx.y) / 2, fd)[:3]):
        for j, (y0, w_, h_) in enumerate(((fmn.y + 0.03, 0.20, 0.21), (fmn.y + 0.25, 0.19, 0.17))):
            if y0 + w_ > fmx.y - 0.02: continue
            b = box("Picture book", fmx.x - 0.105, fmx.x - 0.093, y0, y0 + w_, z + 0.001, z + 0.001 + h_, BOOK_MATS[rnd.randrange(len(BOOK_MATS))], bevel=0.002, seg=1)
            recenter(b); b.rotation_euler.y = math.radians(-8); bpy.context.view_layer.update()
            bmn, _ = _bbox([b]); move([b], (0, 0, z + 0.001 - bmn.z))
            clear_of([b], fd, (1, 0, 0), 0.003, 30)
curtains_open("Toddler curtain", "y", 5.56, 6.76, -7.25)

# rugs: whatever stands on one is lifted by its thickness, together with everything resting on it
def settle_on_rugs(prefixes=("LINDKNUD", "ARENDE", "STAPPSPARV")):
    bpy.context.view_layer.update()
    pool = [o for o in bpy.data.objects if o.type == "MESH" and any(c.name in ("Interior", "IKEA", "Props") for c in o.users_collection)
            and not o.name.startswith(prefixes + ("Curtain", "Main curtain", "Teen curtain", "Office curtain", "Toddler curtain", "Walk runner", "Wall", "Floor", "Ceiling"))]
    bb = {o: _bbox([o]) for o in pool}
    def xy(a, b, m=0.0): return a[0].x < b[1].x - m and b[0].x < a[1].x - m and a[0].y < b[1].y - m and b[0].y < a[1].y - m
    rugs = {}
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith(prefixes): rugs.setdefault(re.sub(r"\.\d+$", "", o.name), []).append(o)
    for rname, robjs in rugs.items():
        rb = _bbox(robjs); top = rb[1].z; rug = robjs[0]
        if top <= 0.0005: continue
        moved = {o for o in pool if xy(bb[o], rb, 0.005) and bb[o][0].z < top - 1e-4 and bb[o][0].z > -0.01}
        grow = True
        while grow:
            grow = False
            for o in pool:
                if o in moved or bb[o][0].z < 0.02: continue
                if any(xy(bb[o], bb[m]) and bb[o][0].z >= bb[m][0].z for m in moved): moved.add(o); grow = True
        roots = set(_roots(list(moved)))
        for r in roots: r.location.z += top
        bpy.context.view_layer.update(); bb = {o: _bbox([o]) for o in pool}
        print("rug", rug.name, round(top, 4), "lifted", len(roots))
settle_on_rugs()
print("BEDROOMS OK")
