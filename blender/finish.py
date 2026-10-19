# Photographic finishing in Blender 5.x's compositor: soft bloom on bright lamps + a gentle vignette.
import bpy
def setup_finish(sc, bloom=0.30, vignette=0.28):
    nt = bpy.data.node_groups.get("Finish") or bpy.data.node_groups.new("Finish", "CompositorNodeTree")
    nt.nodes.clear()
    if not any(s.in_out == "OUTPUT" for s in nt.interface.items_tree if hasattr(s, "in_out")):
        nt.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    N = nt.nodes.new; L = nt.links.new
    rl = N("CompositorNodeRLayers"); out = N("NodeGroupOutput")
    gl = N("CompositorNodeGlare")
    gl.inputs["Type"].default_value = "Bloom"; gl.inputs["Quality"].default_value = "High"
    gl.inputs["Threshold"].default_value = 0.85; gl.inputs["Strength"].default_value = bloom; gl.inputs["Size"].default_value = 0.65
    gl.inputs["Saturation"].default_value = 0.8
    L(rl.outputs["Image"], gl.inputs["Image"])
    el = N("CompositorNodeEllipseMask"); el.inputs["Size"].default_value[0] = 1.05; el.inputs["Size"].default_value[1] = 0.95
    bl = N("CompositorNodeBlur"); bl.inputs["Size"].default_value[0] = 260; bl.inputs["Size"].default_value[1] = 260
    try: bl.inputs["Extend Bounds"].default_value = False
    except Exception: pass
    L(el.outputs["Mask"], bl.inputs["Image"])
    ma = N("ShaderNodeMath"); ma.operation = "MULTIPLY_ADD"; ma.inputs[1].default_value = vignette; ma.inputs[2].default_value = 1.0 - vignette
    L(bl.outputs[0], ma.inputs[0])
    mx = N("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs[0].default_value = 1.0
    L(gl.outputs[0], mx.inputs[6]); L(ma.outputs[0], mx.inputs[7])
    L(mx.outputs[2], out.inputs[0])
    sc.compositing_node_group = nt
    try: sc.render.use_compositing = True
    except Exception: pass
    print("FINISH on: bloom", bloom, "vignette", vignette)
