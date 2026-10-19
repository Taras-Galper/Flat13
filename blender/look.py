# Time of day + lighting scene. Usage inside Blender:  apply_look(moment, scene_id)
#   moment: "1720" (low sun, bay lit gold) or "1825" (blue hour, city lights on)
#   scene_id: a scene from design/lighting.json, or "late" (sensor-driven 20% glow before sunset)
import bpy, json, math, os
from mathutils import Vector
PROJECT = r"C:\Users\grafica\source\repos\dira-landing"
LJ = json.load(open(os.path.join(PROJECT, "design", "lighting.json"), encoding="utf-8"))
SCENES = {s["id"]: s["levels"] for s in LJ["scenes"]}
SCENES["late"] = dict(LIV_COL=38, ENT_NICHE=40, KIT_PLINTH=30, KIT_SHELF=40, LIV_CONSOLE=30, ENT_SCREEN=25, WALL_MEDIA=22, WALL_E=18)
SCENES["rooms"] = dict(SCENES.get("evening", {}), COR_D=30, PASS_GRAZE=45, MST_CURT=55, MST_LAMPS=70, MST_ART=35, MST_NIGHT=0, MST_READ=0,
                       B3_DESK=70, B3_GRAZE=45, B3_TV=35, B3_CURT=45, MAM_TRACK=45, MAM_LAMP=65, MAM_COLOR=55, MAM_MIRROR=50,
                       B4_DISC=40, B4_BOOK=60, B4_CURT=45, B4_NIGHT=40)
GAMMA = 1.6

def level_frac(lvl): return 0.0 if lvl <= 0 else (lvl / 100.0) ** GAMMA

def apply_levels(levels):
    for o in bpy.data.objects:
        c = o.get("circuit")
        if c is None: continue
        f = level_frac(levels.get(c, 0))
        if o.type == "LIGHT": o.data.energy = o["full"] * f
        elif "emit_full" in o.keys() and o.data.materials:
            for n in o.data.materials[0].node_tree.nodes:
                if n.type == "EMISSION": n.inputs[1].default_value = o["emit_full"] * f

def sky_nishita(wn, el_deg, az_deg):
    wn.nodes.clear()
    wo = wn.nodes.new("ShaderNodeOutputWorld"); sky = wn.nodes.new("ShaderNodeTexSky"); bg = wn.nodes.new("ShaderNodeBackground")
    for t in ("NISHITA", "MULTIPLE_SCATTERING"):
        try: sky.sky_type = t; break
        except Exception: pass
    AZ, EL = math.radians(az_deg), math.radians(el_deg)
    d = Vector((math.sin(AZ) * math.cos(EL), math.cos(AZ) * math.cos(EL), math.sin(EL)))
    try:
        sky.sun_disc = False; sky.sun_elevation = EL; sky.sun_rotation = math.atan2(d.x, d.y) * -1 + math.pi / 2
    except Exception as e: print("sky", e)
    for k, v in (("altitude", 60.0), ("air_density", 1.1), ("aerosol_density", 0.9), ("ozone_density", 1.0)):
        try: setattr(sky, k, v)
        except Exception: pass
    bg.inputs[1].default_value = 1.0
    wn.links.new(sky.outputs[0], bg.inputs[0]); wn.links.new(bg.outputs[0], wo.inputs[0])
    return d

def sky_blue_hour(wn, strength=1.0):
    """Analytic twilight: deep blue zenith, pale horizon, a warm band low over the sea where the sun went down (bearing ~260°)."""
    wn.nodes.clear(); N = wn.nodes.new; L = wn.links.new
    wo = N("ShaderNodeOutputWorld"); bg = N("ShaderNodeBackground"); bg.inputs[1].default_value = strength
    tc = N("ShaderNodeTexCoord"); sp = N("ShaderNodeSeparateXYZ"); L(tc.outputs["Generated"], sp.inputs[0])
    mr = N("ShaderNodeMapRange"); mr.interpolation_type = "SMOOTHSTEP"; mr.inputs[1].default_value = -0.02; mr.inputs[2].default_value = 0.55
    L(sp.outputs[2], mr.inputs[0])
    mix = N("ShaderNodeMix"); mix.data_type = "RGBA"; L(mr.outputs[0], mix.inputs[0])
    mix.inputs[6].default_value = (0.105, 0.125, 0.19, 1)       # horizon
    mix.inputs[7].default_value = (0.012, 0.026, 0.075, 1)      # zenith
    # warm afterglow towards the west-south-west
    w = Vector((math.sin(math.radians(260)), math.cos(math.radians(260)), 0)).normalized()
    dp = N("ShaderNodeVectorMath"); dp.operation = "DOT_PRODUCT"; L(tc.outputs["Generated"], dp.inputs[0]); dp.inputs[1].default_value = (w.x, w.y, 0)
    cl = N("ShaderNodeMath"); cl.operation = "MAXIMUM"; L(dp.outputs["Value"], cl.inputs[0]); cl.inputs[1].default_value = 0
    pw = N("ShaderNodeMath"); pw.operation = "POWER"; L(cl.outputs[0], pw.inputs[0]); pw.inputs[1].default_value = 3.0
    lowz = N("ShaderNodeMapRange"); lowz.inputs[1].default_value = 0.0; lowz.inputs[2].default_value = 0.22; lowz.inputs[3].default_value = 1.0; lowz.inputs[4].default_value = 0.0
    L(sp.outputs[2], lowz.inputs[0])
    gm = N("ShaderNodeMath"); gm.operation = "MULTIPLY"; L(pw.outputs[0], gm.inputs[0]); L(lowz.outputs[0], gm.inputs[1])
    add = N("ShaderNodeMix"); add.data_type = "RGBA"; add.blend_type = "ADD"; L(gm.outputs[0], add.inputs[0])
    L(mix.outputs[2], add.inputs[6]); add.inputs[7].default_value = (0.42, 0.17, 0.08, 1)
    L(add.outputs[2], bg.inputs[0]); L(bg.outputs[0], wo.inputs[0])

def set_node_value(mat_name, node_name, v):
    m = bpy.data.materials.get(mat_name)
    if m and node_name in m.node_tree.nodes: m.node_tree.nodes[node_name].outputs[0].default_value = v

def apply_look(moment="1825", scene_id="evening", exposure=None):
    sc = bpy.context.scene; wn = sc.world.node_tree
    sun = bpy.data.objects.get("Sun")
    street = bpy.data.materials.get("Street lights")
    if moment == "1720":
        d = sky_nishita(wn, 8.8, 253.7)
        if sun: sun.data.energy = 4.2; sun.data.color = (1.0, 0.72, 0.48); sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler(); sun.hide_render = False
        set_node_value("City stone", "CITY_EMIT", 0.0)
        if street: street.node_tree.nodes["Emission"].inputs[1].default_value = 0.0
        if bpy.data.objects.get("Street lights"): bpy.data.objects["Street lights"].hide_render = True
        sc.view_settings.exposure = 0.85 if exposure is None else exposure
        sc.view_settings.white_balance_temperature = 5050.0
    else:
        sky_blue_hour(wn, 1.0)
        if sun: sun.hide_render = True
        set_node_value("City stone", "CITY_EMIT", 1.6)
        if street: street.node_tree.nodes["Emission"].inputs[1].default_value = 40.0
        sc.view_settings.exposure = 2.5 if exposure is None else exposure
        sc.view_settings.white_balance_temperature = 3600.0
    apply_levels(SCENES.get(scene_id, {}))
    print("LOOK", moment, scene_id, "exposure", sc.view_settings.exposure)
