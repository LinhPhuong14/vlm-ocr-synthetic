# Adapted from tanguymagne/SyntheticDoc (generation/rendering/ground_truth_module.py),
# MIT License. See ../LICENSE. Trimmed to the one pass this repo uses -- the UV inverse map,
# which sample_renderer.py inverts into a source-to-render pixel map for the page's label
# quads (see ../render.py). The shadow/albedo/3D/normal passes upstream also renders are
# dropped: nothing here reads them.

import os
from contextlib import contextmanager

import bpy
import config
from blender_utils import suppressOutput


@contextmanager
def groundTruthRenderSettings(output_path, file_format, color_depth, samples, use_denoising):
    """Switch the scene over to one ground truth pass, and put every setting back afterwards.

    Restoring happens even when the render raises, since a failed pass must not leave the
    scene's paper material swapped out from under whatever runs next.
    """
    scene = bpy.context.scene
    image_settings = scene.render.image_settings

    saved = {
        "engine": scene.render.engine,
        "samples": scene.cycles.samples,
        "use_denoising": scene.cycles.use_denoising,
        "filepath": scene.render.filepath,
        "film_transparent": scene.render.film_transparent,
        "file_format": image_settings.file_format,
        "color_mode": image_settings.color_mode,
        "color_depth": image_settings.color_depth,
    }

    # The world lights the background, which has to come out pure black for the paper to be
    # separable from the table, so the background nodes are blacked out and saved along with it.
    background_nodes = []
    if scene.world and scene.world.use_nodes:
        background_nodes = [n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND"]
    saved_world = [
        (n, tuple(n.inputs["Color"].default_value), n.inputs["Strength"].default_value)
        for n in background_nodes
    ]

    try:
        scene.render.engine = "CYCLES"
        scene.cycles.samples = samples
        scene.cycles.use_denoising = use_denoising
        scene.render.film_transparent = False
        image_settings.color_mode = "RGB"
        image_settings.file_format = file_format
        image_settings.color_depth = color_depth
        if file_format == "OPEN_EXR":
            image_settings.exr_codec = "ZIP"

        for node in background_nodes:
            node.inputs["Color"].default_value = (0, 0, 0, 1)
            node.inputs["Strength"].default_value = 0.0

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        scene.render.filepath = output_path

        if config.VERBOSE:
            print(f"Format: {file_format}, samples: {samples}, denoising: {use_denoising}")
            print(f"Output: {output_path}")
            print(f"Resolution: {scene.render.resolution_x}x{scene.render.resolution_y}")
            print("Rendering...")

        yield scene

    finally:
        scene.render.engine = saved["engine"]
        scene.cycles.samples = saved["samples"]
        scene.cycles.use_denoising = saved["use_denoising"]
        scene.render.filepath = saved["filepath"]
        scene.render.film_transparent = saved["film_transparent"]
        image_settings.file_format = saved["file_format"]
        image_settings.color_mode = saved["color_mode"]
        image_settings.color_depth = saved["color_depth"]

        for node, color, strength in saved_world:
            node.inputs["Color"].default_value = color
            node.inputs["Strength"].default_value = strength


def createUVGradientMaterial(objectName):
    """Paint a mesh with its own UV coordinates: U in red, V in green, a constant 1.0 in blue."""
    if config.VERBOSE:
        print(f"Creating UV gradient material for '{objectName}'...")

    mat_name = "UV_Gradient_Material"

    # Rebuilt from scratch on every call, so a stale version from an earlier sample cannot
    # survive into this one.
    if mat_name in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[mat_name])

    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()

    node_uv = nodes.new(type="ShaderNodeUVMap")
    node_uv.location = (-400, 0)

    node_separate = nodes.new(type="ShaderNodeSeparateXYZ")
    node_separate.location = (-200, 0)

    node_combine = nodes.new(type="ShaderNodeCombineRGB")
    node_combine.location = (0, 0)
    node_combine.inputs["B"].default_value = 1.0

    # Emission rather than a shaded surface: the pixel value has to be the coordinate itself,
    # unaffected by the lights that are still in the scene.
    node_emission = nodes.new(type="ShaderNodeEmission")
    node_emission.location = (200, 0)
    node_emission.inputs["Strength"].default_value = 1.0

    node_output = nodes.new(type="ShaderNodeOutputMaterial")
    node_output.location = (400, 0)

    links.new(node_uv.outputs["UV"], node_separate.inputs["Vector"])
    links.new(node_separate.outputs["X"], node_combine.inputs["R"])
    links.new(node_separate.outputs["Y"], node_combine.inputs["G"])
    links.new(node_combine.outputs["Image"], node_emission.inputs["Color"])
    links.new(node_emission.outputs["Emission"], node_output.inputs["Surface"])

    obj = bpy.data.objects.get(objectName)
    if obj:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        if config.VERBOSE:
            print(f"Applied UV gradient material to '{objectName}'")

    return mat


def setupBlackMaterial(objectName):
    """Paint an object pure black, so it reads as background and can be masked out."""
    mat_name = "Black_Background_Material"

    if mat_name in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[mat_name])

    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()

    # Black emission, not a black surface: a surface would still catch a highlight from the
    # lights and leave the background short of a clean zero.
    node_emission = nodes.new(type="ShaderNodeEmission")
    node_emission.inputs["Color"].default_value = (0, 0, 0, 1)
    node_emission.inputs["Strength"].default_value = 1.0

    node_output = nodes.new(type="ShaderNodeOutputMaterial")
    node_output.location = (200, 0)

    links.new(node_emission.outputs["Emission"], node_output.inputs["Surface"])

    obj = bpy.data.objects.get(objectName)
    if obj:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        if config.VERBOSE:
            print(f"Applied black material to '{objectName}'")

    return mat


def renderUVInverseMap(output_path):
    """Render each visible point of the paper as its UV coordinate, black elsewhere.

    This is the map that says where every pixel of the photograph came from on the flat page
    -- what `../render.py` inverts into a source-to-render pixel map for the page's label
    quads. EXR keeps the coordinates at full float precision.
    """
    if config.VERBOSE:
        print("\n" + "=" * 50)
        print("Rendering UV Inverse Map")
        print("=" * 50)

    createUVGradientMaterial(config.PAPER_OBJECT_NAME)
    setupBlackMaterial(config.TABLE_OBJECT_NAME)

    # A single sample, because there is nothing to converge: the emission shader already outputs
    # the exact value, and more samples would only average neighbours in and blur the edges.
    # Denoising is off for the same reason: it would invent coordinates that lie off the surface.
    with (
        groundTruthRenderSettings(
            output_path, file_format="OPEN_EXR", color_depth="32", samples=1, use_denoising=False
        ),
        suppressOutput(),
    ):
        bpy.ops.render.render(write_still=True)

    if config.VERBOSE:
        print(f"UV inverse map rendered to: {output_path}\n")

    return output_path
