# usage: blender -b dira_proof.blend -P render.py -- <camera> <samples> <percent> <out.png> [moment] [scene] [exposure]
import bpy, sys, os
argv = sys.argv[sys.argv.index("--") + 1:]
cam, samples, pct, out = argv[0], int(argv[1]), int(argv[2]), argv[3]
moment = argv[4] if len(argv) > 4 else None
scene_id = argv[5] if len(argv) > 5 else "evening"
expo = float(argv[6]) if len(argv) > 6 and argv[6] != "-" else None
fstop = float(argv[7]) if len(argv) > 7 else None      # depth of field: f-number, e.g. 1.4
# focus point per camera (plan metres, z up): the one thing each view is about
FOCUS = {"CAM Hero": (5.80, 7.70, 0.36), "CAM Entry": (7.40, 6.07, 1.40), "CAM Living to bay": (4.10, 8.85, 1.00),
         "CAM Living to media wall": (3.70, 7.05, 0.62), "CAM Balcony": (2.45, 10.2, 0.6),
         "CAM Detail table": (5.80, 7.70, 0.38), "CAM Detail screen": (7.30, 6.07, 1.15),
         "CAM Kitchen": (3.40, 3.62, 0.75), "CAM Balcony west": (2.45, 10.2, 0.6),
         "CAM Main bedroom": (-5.75, 10.40, 0.65), "CAM Teen": (-1.85, 8.70, 0.60), "CAM Office": (2.30, 8.40, 0.70), "CAM Toddler": (-5.75, 6.40, 0.45)}
finish = (argv[8] != "nofinish") if len(argv) > 8 else True
sc = bpy.context.scene
if moment:
    exec(open(os.path.join(os.path.dirname(bpy.data.filepath), "look.py"), encoding="utf-8").read())
    apply_look(moment, scene_id, expo)
if finish:
    exec(open(os.path.join(os.path.dirname(bpy.data.filepath), "finish.py"), encoding="utf-8").read())
    setup_finish(sc)
sc.camera = bpy.data.objects[cam]
cd = sc.camera.data
if fstop and cam in FOCUS:
    from mathutils import Vector
    cd.dof.use_dof = True; cd.dof.aperture_fstop = fstop; cd.dof.aperture_blades = 7; cd.dof.aperture_ratio = 1.0
    cd.dof.focus_object = None
    fwd = sc.camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    cd.dof.focus_distance = (Vector(FOCUS[cam]) - sc.camera.matrix_world.translation).dot(fwd)
    print("DOF", cam, "f/", fstop, "focus", round(cd.dof.focus_distance, 2), "m")
else:
    cd.dof.use_dof = False
sc.cycles.samples = samples
sc.render.resolution_percentage = pct
cp = bpy.context.preferences.addons["cycles"].preferences
cp.compute_device_type = "OPTIX"; cp.get_devices()
for d in cp.devices: d.use = (d.type == "OPTIX")
sc.cycles.device = "GPU"
sc.render.filepath = out
sc.render.image_settings.file_format = "PNG"
bpy.ops.render.render(write_still=True)
print("RENDERED", out)
