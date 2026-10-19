# Lighting design → Blender. Exec'd from build_scene.py (shares its globals: bpy, bmesh, M, H, HC, box, cyl, col, ...).
# Every fitting becomes a real light tagged with its circuit; look.py sets levels per scene and the time of day.
LJ = json.load(open(os.path.join(PROJECT, "design", "lighting.json"), encoding="utf-8"))
ROOMS_BUILT = {"entry", "living", "kitchen", "terrace", "corridor", "master", "passage", "mamad", "bed3", "bed4"}
FULL = dict(L1=6.0, L2=3.5, L3=2.2, L4=6.0, L5=5.0, E1=3.0, E3=2.0, B1=1.2, D1=3.0, D2=2.2, E2=3.0, E4=1.2, P2=6.0, R1=1.6, K1=9.0, T1=2.0, O1=14.0, N1=0.3)   # W per m for lines, W per fitting
CUT = []          # ceiling cutters (slots and holes)

def kelvin_rgb(k):
    t = k / 100.0
    r = 255 if t <= 66 else 329.698727446 * ((t - 60) ** -0.1332047592)
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * ((t - 60) ** -0.0755148492)
    b = 255 if t >= 66 else (0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307)
    c = [min(255, max(0, v)) / 255 for v in (r, g, b)]
    lin = [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c]
    m = max(lin); return tuple(x / m for x in lin)

M["baffle"] = flat("Downlight baffle", srgb("#151413"), 0.35)
def tag(o, circuit, full, cct):
    o["circuit"] = circuit; o["full"] = float(full); o["cct"] = int(cct)
    o.data.color = kelvin_rgb(cct); o.data.energy = 0.0

def cct_of(f):
    c = LJ["circuits"][f["c"]]["cct"]
    return min(c, 2200) if f["t"] in ("E2", "E3", "E4", "L3", "N1") else c

def strip_light(name, f, z, down=True, tilt=0.0, spread=80, width=0.025):
    x0, y0, x1, y1 = f["l"]; L = math.dist((x0, y0), (x1, y1))
    ld = bpy.data.lights.new(name, "AREA"); ld.shape = "RECTANGLE"; ld.size = L; ld.size_y = width
    try: ld.spread = math.radians(spread)
    except Exception: pass
    o = bpy.data.objects.new(name, ld); col("Lights").objects.link(o)
    o.location = ((x0 + x1) / 2, (y0 + y1) / 2, z)
    ang = math.atan2(y1 - y0, x1 - x0)
    o.rotation_euler = (tilt if down else math.pi, 0.0, ang)     # area lights emit along local -Z; tilt leans the beam towards local +Y
    try: o.visible_camera = False
    except Exception: pass
    tag(o, f["c"], FULL[f["t"]] * L, cct_of(f)); return o

def spot(name, f, z, size_deg, target=None, radius=0.012, full=3.0):
    x, y = f["p"]
    ld = bpy.data.lights.new(name, "SPOT"); ld.spot_size = math.radians(size_deg); ld.spot_blend = 0.35; ld.shadow_soft_size = radius
    try: ld.show_cone = False
    except Exception: pass
    o = bpy.data.objects.new(name, ld); col("Lights").objects.link(o); o.location = (x, y, z)
    d = (Vector(target) - Vector((x, y, z))) if target else Vector((0, 0, -1))
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    tag(o, f["c"], full, cct_of(f)); return o

def recessed(f, r_hole, depth, size_deg, target=None, full=3.0):
    x, y = f["p"]
    CUT.append(("cyl", x, y, r_hole))
    cyl(f"{f['t']} barrel", x, y, r_hole - 0.001, H - depth - 0.002, H, M["baffle"], seg=24, bevel=0, coll="Fixtures")
    e = emissive(f"{f['t']} source {x:.2f}", kelvin_rgb(cct_of(f)), 0.0)
    src = cyl(f"{f['t']} source", x, y, r_hole * 0.42, H - depth - 0.004, H - depth - 0.0025, e, seg=16, bevel=0, coll="Fixtures")
    src["circuit"] = f["c"]; src["emit_full"] = 60.0
    return spot(f"{f['t']} {f['c']} {x:.2f},{y:.2f}", f, H - depth - 0.006, size_deg, target, radius=r_hole * 0.4, full=full)

def slot_cut(f, wall_side, depth_into=0.10, room_side=0.035):
    """Slot in the dropped ceiling between the line and the wall it grazes."""
    x0, y0, x1, y1 = f["l"]; sx, sy = wall_side
    if abs(x1 - x0) < 1e-6:     # runs along y
        xa, xb = sorted([x0 - sx * room_side, x0 + sx * depth_into]); CUT.append(("box", xa, xb, min(y0, y1), max(y0, y1)))
    else:
        ya, yb = sorted([y0 - sy * room_side, y0 + sy * depth_into]); CUT.append(("box", min(x0, x1), max(x0, x1), ya, yb))

for f in LJ["fixtures"]:
    room = LJ["circuits"][f["c"]]["room"]
    if room not in ROOMS_BUILT: continue
    t = f["t"]; nm = f"{t} {f['c']}"
    if t == "L1" and room not in DROP:                 # bedrooms keep the 2.70 slab ceiling: hidden line just under it
        sd = f.get("side") or (0, 0); wall = (-sd[0], -sd[1])
        x0, y0, x1, y1 = f["l"]; ang = math.atan2(y1 - y0, x1 - x0); ly = (-math.sin(ang), math.cos(ang))
        sgn = 1 if (wall[0] * ly[0] + wall[1] * ly[1]) > 0 else -1
        o = strip_light(nm, f, H - 0.012, tilt=math.radians(25) * sgn, spread=70)
        o.location.x += wall[0] * 0.02; o.location.y += wall[1] * 0.02
        continue
    if t == "L1":
        sd = f.get("side") or (0, 0)
        if sd == [0, 0] or sd == (0, 0):            # the slatted screen: slot centred over the slats
            x0, y0, x1, y1 = f["l"]; CUT.append(("box", x0, x1, y0 - 0.10, y0))
            o = strip_light(nm, f, H - 0.015, spread=60)
            o.location.y = y0 - 0.05
        else:
            wall = (-sd[0], -sd[1]); slot_cut(f, wall)
            x0, y0, x1, y1 = f["l"]; ang = math.atan2(y1 - y0, x1 - x0); ly = (-math.sin(ang), math.cos(ang))
            sgn = 1 if (wall[0] * ly[0] + wall[1] * ly[1]) > 0 else -1
            o = strip_light(nm, f, H - 0.015, tilt=math.radians(20) * sgn, spread=70)
            o.location.x += wall[0] * 0.02; o.location.y += wall[1] * 0.02
    elif t == "L2":
        strip_light(nm, f, H - 0.125, spread=50)
    elif t == "L3":
        x0, y0, x1, y1 = f["l"]
        z = {"ENT_NICHE": 0.145, "LIV_CONSOLE": 0.125, "KIT_PLINTH": 0.095, "MAM_COLOR": 1.02, "MST_NIGHT": 0.12, "B4_NIGHT": 0.03, "NIGHT": 0.06}.get(f["c"], 0.1)
        if "overhang" in f.get("note", ""): z = 0.885
        strip_light(nm, f, z, spread=110, width=0.012)
    elif t == "L4":
        z = {"KIT_SHELF": 1.525, "ENT_NICHE": 0.94, "B4_BOOK": 1.05}.get(f["c"], 1.5)
        strip_light(nm, f, z, spread=110, width=0.015)
    elif t == "D1":
        recessed(f, 0.0275, 0.035, 36, full=FULL["D1"])
    elif t == "D2":
        ax, ay = f.get("aim") or (0, 0)
        if f["c"] == "LIV_ART": tgt = (7.76, f["p"][1], 1.55)
        else: tgt = (f["p"][0] + ax * 0.6, f["p"][1] + ay * 0.6, 0.9)
        recessed(f, 0.016, 0.03, 12, target=tgt, full=FULL["D2"])
    elif t == "E1":
        o = strip_light(nm, f, H - 0.015, spread=70)   # under the balcony soffit, washing the façade
        o.location.y = 9.74
    elif t == "E3":
        x0, y0, x1, y1 = f["l"]
        if "sofa" in f.get("note", ""): continue        # NÄMMARÖ stands on open legs: no plinth to hide a strip under
        else: o = strip_light(nm, f, 0.40, spread=120, width=0.012); o.location.x = 7.27
    elif t == "E2":
        x, y = f["p"]
        tgt = (-1.25, 12.55, 1.0) if x < 0 else (7.54, y, 1.2)
        ld = bpy.data.lights.new(nm, "SPOT"); ld.spot_size = math.radians(28 if x < 0 else 50); ld.spot_blend = 0.5; ld.shadow_soft_size = 0.02
        o = bpy.data.objects.new(nm, ld); col("Lights").objects.link(o); o.location = (x, y, 0.62 if x < 0 else 0.47)
        o.rotation_euler = (Vector(tgt) - o.location).to_track_quat("-Z", "Y").to_euler(); tag(o, f["c"], FULL["E2"], cct_of(f))
    elif t == "E4":
        x, y = f["p"]
        cyl("Table lamp base", x, y, 0.055, 0.752, 0.772, M["teak"], seg=32)
        cyl("Table lamp shade", x, y, 0.06, 0.772, 0.99, M["washi"], seg=32, bevel=0)
        ld = bpy.data.lights.new(nm, "POINT"); ld.shadow_soft_size = 0.03
        o = bpy.data.objects.new(nm, ld); col("Lights").objects.link(o); o.location = (x, y, 0.88); tag(o, f["c"], FULL["E4"], 2200)
    elif t == "L5":                                     # mirror face lights: vertical bars beside the mirror, facing into the room
        x0, y0, x1, y1 = f["l"]; sd = f.get("side") or (0, 0); L = math.dist((x0, y0), (x1, y1))
        for k, (px_, py_) in enumerate(((x0, y0), (x1, y1))):
            ld = bpy.data.lights.new(f"{nm} {k}", "AREA"); ld.shape = "RECTANGLE"; ld.size = 0.03; ld.size_y = 0.60
            o = bpy.data.objects.new(f"{nm} {k}", ld); col("Lights").objects.link(o); o.location = (px_ + sd[0] * 0.03, py_ + sd[1] * 0.03, 1.50)
            o.rotation_euler = Vector((sd[0], sd[1], 0)).to_track_quat("-Z", "Y").to_euler(); tag(o, f["c"], FULL["L5"] / 2, cct_of(f))
            g = box(f"{nm} bar", px_ + sd[0] * 0.005 - 0.012, px_ + sd[0] * 0.005 + 0.012, py_ + sd[1] * 0.005 - 0.012, py_ + sd[1] * 0.005 + 0.012, 1.20, 1.80, emissive(f"{nm} bar {k}", kelvin_rgb(cct_of(f)), 0.0), coll="Fixtures")
            g["circuit"] = f["c"]; g["emit_full"] = 12.0
    elif t == "R1":                                     # articulated wall reading light: small head, narrow beam onto the pillow
        x, y = f["p"]; ax, ay = f.get("aim") or (0, -1)
        hx, hy, hz = x + ax * 0.32, y + ay * 0.32, 1.10
        cyl(f"{nm} arm", x, y, 0.01, 0.95, 1.12, M["frame"], seg=12, bevel=0, coll="Fixtures")
        cyl(f"{nm} head", hx, hy, 0.035, hz - 0.03, hz + 0.05, M["frame"], seg=24, bevel=0.002, coll="Fixtures")
        box(f"{nm} reach", min(x, hx) - 0.008, max(x, hx) + 0.008, min(y, hy) - 0.008, max(y, hy) + 0.008, 1.105, 1.12, M["frame"], coll="Fixtures")
        ld = bpy.data.lights.new(nm, "SPOT"); ld.spot_size = math.radians(30); ld.spot_blend = 0.4; ld.shadow_soft_size = 0.015
        o = bpy.data.objects.new(nm, ld); col("Lights").objects.link(o); o.location = (hx, hy, hz - 0.035)
        o.rotation_euler = Vector((ax * 0.25, ay * 0.25, -1)).to_track_quat("-Z", "Y").to_euler(); tag(o, f["c"], FULL["R1"], cct_of(f))
    elif t == "K1":                                     # flush opal disc
        x, y = f["p"]
        d = cyl(f"{nm} disc", x, y, 0.30, H - 0.045, H, emissive(f"{nm} opal", kelvin_rgb(2700), 0.0), seg=64, bevel=0.01, coll="Fixtures"); d["circuit"] = f["c"]; d["emit_full"] = 6.0
        ld = bpy.data.lights.new(nm, "AREA"); ld.shape = "DISK"; ld.size = 0.56
        o = bpy.data.objects.new(nm, ld); col("Lights").objects.link(o); o.location = (x, y, H - 0.047); tag(o, f["c"], FULL["K1"], cct_of(f))
    elif t == "T1":                                     # surface track with three mini spots (safe room: nothing recessed)
        x0, y0, x1, y1 = f["l"]
        box(f"{nm} track", min(x0, x1), max(x0, x1), min(y0, y1) - 0.017, max(y0, y1) + 0.017, H - 0.035, H, M["frame"], bevel=0.003, seg=2, coll="Fixtures")
        for k, (u, tgt) in enumerate(((0.15, (-2.40, 8.40, 1.0)), (0.55, (0.15, 8.20, 0.8)), (0.88, (-1.80, 6.40, 1.2)))):
            sx, sy = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
            cyl(f"{nm} spot {k}", sx, sy, 0.028, H - 0.13, H - 0.035, M["frame"], seg=24, bevel=0.002, coll="Fixtures")
            ld = bpy.data.lights.new(f"{nm} {k}", "SPOT"); ld.spot_size = math.radians(34); ld.spot_blend = 0.45; ld.shadow_soft_size = 0.012
            o = bpy.data.objects.new(f"{nm} {k}", ld); col("Lights").objects.link(o); o.location = (sx, sy, H - 0.135)
            o.rotation_euler = (Vector(tgt) - o.location).to_track_quat("-Z", "Y").to_euler(); tag(o, f["c"], FULL["T1"], cct_of(f))
    elif t == "O1":                                     # direct/indirect linear pendant over the desk
        x0, y0, x1, y1 = f["l"]; zc = 1.92
        box(f"{nm} body", min(x0, x1), max(x0, x1), y0 - 0.03, y0 + 0.03, zc - 0.02, zc + 0.02, M["frame"], bevel=0.004, seg=2, coll="Fixtures")
        for xx in (x0 + 0.05, x1 - 0.05): cyl(f"{nm} cable", xx, y0, 0.0012, zc + 0.02, H, M["steel"], seg=6, bevel=0, coll="Fixtures")
        for k, (down, share) in enumerate(((True, 0.3), (False, 0.7))):
            ld = bpy.data.lights.new(f"{nm} {k}", "AREA"); ld.shape = "RECTANGLE"; ld.size = abs(x1 - x0) - 0.06; ld.size_y = 0.04
            o = bpy.data.objects.new(f"{nm} {k}", ld); col("Lights").objects.link(o); o.location = ((x0 + x1) / 2, y0, zc - 0.022 if down else zc + 0.022)
            o.rotation_euler = (0 if down else math.pi, 0, 0); tag(o, f["c"], FULL["O1"] * share, 3000)
            try: o.visible_camera = False
            except Exception: pass
    elif t == "B1" and room == "bed3":                  # bias light behind the game-room screen, washing the slatted panel
        x0, y0, x1, y1 = f["l"]
        ld = bpy.data.lights.new(nm, "AREA"); ld.shape = "RECTANGLE"; ld.size = 0.03; ld.size_y = abs(y1 - y0)
        o = bpy.data.objects.new(nm, ld); col("Lights").objects.link(o); o.location = (x0 + 0.05, (y0 + y1) / 2, 1.20)
        o.rotation_euler = Vector((-1, 0, 0)).to_track_quat("-Z", "Y").to_euler(); tag(o, f["c"], FULL["B1"] * abs(y1 - y0), 2700)
        try: o.visible_camera = False
        except Exception: pass
    elif t == "N1":                                     # step light low in the wall
        x, y = f["p"]; ax, ay = f.get("aim") or (0, 1)
        e = emissive(f"{nm} glow {x:.2f}", kelvin_rgb(2200), 0.0)
        g = box(f"{nm} face", x - 0.04 if ay else x - 0.004, x + 0.04 if ay else x + 0.004, y - 0.004 if ay else y - 0.04, y + 0.004 if ay else y + 0.04, 0.28, 0.31, e, coll="Fixtures"); g["circuit"] = f["c"]; g["emit_full"] = 8.0
        ld = bpy.data.lights.new(nm, "SPOT"); ld.spot_size = math.radians(110); ld.spot_blend = 0.6; ld.shadow_soft_size = 0.02
        o = bpy.data.objects.new(nm, ld); col("Lights").objects.link(o); o.location = (x + ax * 0.01, y + ay * 0.01, 0.29)
        o.rotation_euler = Vector((ax, ay, -1.2)).to_track_quat("-Z", "Y").to_euler(); tag(o, f["c"], FULL["N1"], 2200)
    # P1/P2/P4 are built with the furniture (tagged below); P3 is the column lamp; W1/N1/B1 not needed in these rooms' views

# tag the paper lamps built with the furniture
for o in bpy.data.objects:
    if o.type != "LIGHT": continue
    if o.name.startswith("Pendant living") and o.name.endswith("bulb"): tag(o, "LIV_PEND", 8.0, 2200); o.data.shadow_soft_size = 0.12
    elif o.name.startswith("Pendant kitchen") and o.name.endswith("bulb"): tag(o, "KIT_PEND", 7.0, 2200); o.data.shadow_soft_size = 0.06
    elif o.name == "Lantern light": tag(o, "LIV_LANT", 10.0, 2200)
    elif o.name.startswith("Column lamp"): o.data.color = kelvin_rgb(2200)

# cut slots and holes in the dropped ceilings
cutters = []
for c in CUT:
    if c[0] == "box": _, xa, xb, ya, yb = c; cutters.append(box("cutter", xa, xb, ya, yb, HC - 0.02, H - 0.001, None, coll="Cutters"))
    else: _, x, y, r = c; cutters.append(cyl("cutter", x, y, r, HC - 0.02, H - 0.001, None, seg=24, bevel=0, coll="Cutters"))
dg = bpy.context.evaluated_depsgraph_get()
for o in list(col("Ceilings").objects):
    if not o.name.startswith("Ceiling ") or o.name.split(" ", 1)[1] not in DROP: continue
    for cu in cutters:
        md = o.modifiers.new("cut", "BOOLEAN"); md.operation = "DIFFERENCE"; md.object = cu; md.solver = "EXACT"
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); o.modifiers.clear(); o.data = me
for cu in cutters: bpy.data.objects.remove(cu, do_unlink=True)

# ------------------------------------------------------------------ the city at night: lit windows and street lights
def city_windows(mat):
    nt = mat.node_tree; b = nt.nodes["Principled BSDF"]
    geo = nt.nodes.new("ShaderNodeNewGeometry"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(geo.outputs["Position"], sep.inputs[0])
    def math_node(op, a, b=None, v=None):
        n = nt.nodes.new("ShaderNodeMath"); n.operation = op
        (nt.links.new(a, n.inputs[0]) if not isinstance(a, (int, float)) else n.inputs[0].__setattr__("default_value", a))
        if b is not None: (nt.links.new(b, n.inputs[1]) if not isinstance(b, (int, float)) else n.inputs[1].__setattr__("default_value", b))
        return n.outputs[0]
    hpos = math_node("ADD", sep.outputs[0], sep.outputs[1])
    u = math_node("DIVIDE", hpos, 3.6); v = math_node("DIVIDE", sep.outputs[2], 3.1)
    cu, cv = math_node("FLOOR", u), math_node("FLOOR", v)
    fu, fv = math_node("FRACT", u), math_node("FRACT", v)
    comb = nt.nodes.new("ShaderNodeCombineXYZ"); nt.links.new(cu, comb.inputs[0]); nt.links.new(cv, comb.inputs[1])
    wn = nt.nodes.new("ShaderNodeTexWhiteNoise"); wn.noise_dimensions = "3D"; nt.links.new(comb.outputs[0], wn.inputs["Vector"])
    lit = math_node("GREATER_THAN", wn.outputs["Value"], 0.70)
    inu = math_node("MULTIPLY", math_node("GREATER_THAN", fu, 0.18), math_node("LESS_THAN", fu, 0.82))
    inv = math_node("MULTIPLY", math_node("GREATER_THAN", fv, 0.28), math_node("LESS_THAN", fv, 0.82))
    sepn = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(geo.outputs["Normal"], sepn.inputs[0])
    vert = math_node("LESS_THAN", math_node("ABSOLUTE", sepn.outputs[2]), 0.3)
    mask = math_node("MULTIPLY", math_node("MULTIPLY", lit, inu), math_node("MULTIPLY", inv, vert))
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    sep2 = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(wn.outputs["Color"], sep2.inputs[0]); nt.links.new(sep2.outputs[0], ramp.inputs[0])
    ramp.color_ramp.elements[0].color = (*kelvin_rgb(2600), 1); ramp.color_ramp.elements[1].color = (*kelvin_rgb(4200), 1)
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"; mix.inputs[0].default_value = 1.0
    nt.links.new(ramp.outputs[0], mix.inputs[6]); nt.links.new(mask, mix.inputs[7])
    nt.links.new(mix.outputs[2], b.inputs["Emission Color"])
    val = nt.nodes.new("ShaderNodeValue"); val.name = "CITY_EMIT"; val.outputs[0].default_value = 0.0
    nt.links.new(val.outputs[0], b.inputs["Emission Strength"])
city_windows(M["city"])

M["street"] = emissive("Street lights", kelvin_rgb(2400), 0.0)
bm = bmesh.new(); rs = random.Random(99); n = 0
while n < 2600:
    a = rs.random() * 2 * math.pi; r = 80 + (rs.random() ** 0.6) * 5200
    x, y = math.cos(a) * r, math.sin(a) * r
    if not is_land(x, y): continue
    z = -39.5 + min(420, max(0.0, x - 380) * 0.17 + max(0.0, -y - 150) * 0.07) + 5
    g = bmesh.ops.create_icosphere(bm, subdivisions=0, radius=0.35 + r / 5000)["verts"]
    bmesh.ops.translate(bm, vec=(x, y, z), verts=g); n += 1
# the shore road around the bay towards the Krayot
for k in range(900):
    x = -150 + k * 9.5
    y = (430 - 90 * math.sin(x / 900) if x < 2600 else 430 + (x - 2600) * 0.95) - 18
    z = -39.5 + min(420, max(0.0, x - 380) * 0.17) + 6
    if rs.random() < 0.35: continue
    g = bmesh.ops.create_icosphere(bm, subdivisions=0, radius=0.22 + abs(x) / 6000)["verts"]; bmesh.ops.translate(bm, vec=(x + rs.uniform(-3, 3), y + rs.uniform(-25, 8), z), verts=g)
obj_from_bm("Street lights", bm, M["street"], coll="World")
print("LIGHTING OK", sum(1 for o in bpy.data.objects if "circuit" in o.keys()), "tagged")
