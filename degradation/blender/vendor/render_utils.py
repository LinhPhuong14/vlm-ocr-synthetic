# Adapted from tanguymagne/SyntheticDoc (generation/rendering/render_utils.py), MIT License.
# See ../LICENSE. `renderImage` retries without denoising on a build that lacks
# OpenImageDenoise -- not in the original, which assumes a full Blender install.

import os

import bpy
import config
from blender_utils import suppressOutput


def renderImage(output_path):
    """Render the scene from its active camera to an image file.

    Retries once without denoising if the Blender build has no OpenImageDenoise: a full
    install from blender.org has it, but a stripped distro package (Ubuntu's `apt install
    blender`, notably) does not, and raises instead of silently ignoring the setting.
    """
    if config.VERBOSE:
        print(f"\nRendering to: {output_path}")

    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    scene = bpy.context.scene
    scene.render.filepath = output_path

    try:
        with suppressOutput():
            bpy.ops.render.render(write_still=True)
    except RuntimeError as error:
        if "OpenImageDenoiser" not in str(error) or not scene.cycles.use_denoising:
            raise
        scene.cycles.use_denoising = False
        with suppressOutput():
            bpy.ops.render.render(write_still=True)

    if config.VERBOSE:
        print(f"Render complete: {output_path}\n")
