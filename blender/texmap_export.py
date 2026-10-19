# Writes mood/texmap.json: for every material whose textures Blender maps by object coordinates (floors,
# oak veneer, rugs, fabrics), the mapping (flat/box, scale, offset, rotation) and the colour adjustments
# (value, saturation, tint) that glTF cannot carry. js/mood.js reproduces them in its shader.
# Run inside Blender with the built scene open.
import bpy, json, os
PROJECT = r"C:\Users\grafica\source\repos\dira-landing"
out = {}
for m in bpy.data.materials:
    if "@" in m.name or not m.node_tree: continue
    nt = m.node_tree
    if not any(n.type == "TEX_COORD" for n in nt.nodes): continue
    maps = [n for n in nt.nodes if n.type == "MAPPING"]
    if not maps: continue
    imgs = [n for n in nt.nodes if n.type == "TEX_IMAGE"]
    mp = maps[0]; S = mp.inputs["Scale"].default_value; L = mp.inputs["Location"].default_value; R = mp.inputs["Rotation"].default_value
    r = {"mode": "flat" if imgs and imgs[0].projection == "FLAT" else "box", "k": round(S[0], 5)}
    if L[0] or L[1]: r["off"] = [round(L[0], 4), round(L[1], 4)]
    if R[2]: r["rot"] = round(R[2], 4)
    hs = [n for n in nt.nodes if n.type == "HUE_SAT"]
    if hs:
        v, s = hs[0].inputs["Value"].default_value, hs[0].inputs["Saturation"].default_value
        if v != 1: r["value"] = round(v, 3)
        if s != 1: r["sat"] = round(s, 3)
    mx = [n for n in nt.nodes if n.type == "MIX" and n.blend_type == "MULTIPLY" and n.data_type == "RGBA"]
    if mx: r["tint"] = [round(c, 3) for c in mx[0].inputs[7].default_value[:3]]
    out[m.name] = r
json.dump(out, open(os.path.join(PROJECT, "mood", "texmap.json"), "w", encoding="utf-8"), indent=0, ensure_ascii=False)
print("texmap", len(out))
