"""Build the Untangle sewing needle and export it as a GLB.

Run from the landing/ folder:

    blender -b -P blender/needle.py

The needle points down -Z in Blender (-Y in glTF): the tip sits at z = -1 and
the gold-plated eye near z = +0.9. Pass `-- --preview out.png` to also render a
quick look-dev image.
"""

import math
import os
import sys

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "public", "models", "needle.glb"))

argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
PREVIEW = argv[argv.index("--preview") + 1] if "--preview" in argv else None

# Profile of the needle as (radius, z), tip to head.
R = 0.034
PROFILE = [
    (0.0, -1.0),
    (0.0035, -0.985),
    (0.009, -0.94),
    (0.017, -0.86),
    (0.025, -0.76),
    (0.031, -0.64),
    (R, -0.52),
    (R, 0.70),
    (R * 1.04, 0.80),  # the eye region swells slightly, as real needles do
    (R * 1.05, 0.90),
    (R * 0.98, 0.955),
    (R * 0.8, 0.985),
    (R * 0.45, 0.998),
    (0.0, 1.0),
]
SEGMENTS = 64


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_material(name, color, roughness, metallic=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def build_body():
    mesh = bpy.data.meshes.new("NeedleBody")
    bm = bmesh.new()
    rings = []
    for r, z in PROFILE:
        if r == 0.0:
            rings.append([bm.verts.new((0.0, 0.0, z))])
            continue
        ring = []
        for i in range(SEGMENTS):
            a = 2 * math.pi * i / SEGMENTS
            # Flatten the head a little so the eye reads as a slot.
            squash = 1.0 - 0.18 * max(0.0, (z - 0.72) / 0.28)
            ring.append(bm.verts.new((math.cos(a) * r, math.sin(a) * r * squash, z)))
        rings.append(ring)

    for lower, upper in zip(rings, rings[1:]):
        if len(lower) == 1:
            for i in range(SEGMENTS):
                bm.faces.new((lower[0], upper[i], upper[(i + 1) % SEGMENTS]))
        elif len(upper) == 1:
            for i in range(SEGMENTS):
                bm.faces.new((lower[i], upper[0], lower[(i + 1) % SEGMENTS]))
        else:
            for i in range(SEGMENTS):
                j = (i + 1) % SEGMENTS
                bm.faces.new((lower[i], lower[j], upper[j], upper[i]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("Needle", mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build_eye_cutter():
    # A stadium-shaped slot through the head, along the X axis.
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.0115, depth=0.2, location=(0, 0, 0))
    cutter = bpy.context.active_object
    # Point the cylinder along X, then stretch it along Z into a long eye.
    cutter.rotation_euler = (0, math.radians(90), 0)
    cutter.scale = (1.0, 1.0, 5.4)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    cutter.location = (0, 0, 0.86)
    return cutter


def main():
    reset_scene()
    body = build_body()
    cutter = build_eye_cutter()

    sub = body.modifiers.new("Smooth", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 1
    boolean = body.modifiers.new("Eye", "BOOLEAN")
    boolean.operation = "DIFFERENCE"
    boolean.solver = "EXACT"
    boolean.object = cutter

    bpy.context.view_layer.objects.active = body
    for mod in list(body.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)

    steel = make_material("Steel", (0.86, 0.87, 0.9), 0.16)
    gold = make_material("GoldEye", (1.0, 0.77, 0.42), 0.24)
    body.data.materials.append(steel)
    body.data.materials.append(gold)
    for poly in body.data.polygons:
        if poly.center.z > 0.68:
            poly.material_index = 1
        poly.use_smooth = True

    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.ops.object.shade_auto_smooth(angle=math.radians(50))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=OUT,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
    )
    print(f"wrote {OUT}")

    if PREVIEW:
        render_preview(body, PREVIEW)


def render_preview(body, path):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.07, 0.19, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.2

    body.rotation_euler = (math.radians(70), math.radians(20), math.radians(35))
    bpy.ops.object.light_add(type="AREA", location=(1.5, -1.5, 2.0))
    bpy.context.active_object.data.energy = 300
    bpy.context.active_object.data.size = 2.0
    bpy.ops.object.light_add(type="AREA", location=(-2, 1, -1))
    bpy.context.active_object.data.energy = 120
    bpy.ops.object.camera_add(location=(0, -3.2, 0), rotation=(math.radians(90), 0, 0))
    scene.camera = bpy.context.active_object
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"preview {path}")


main()
