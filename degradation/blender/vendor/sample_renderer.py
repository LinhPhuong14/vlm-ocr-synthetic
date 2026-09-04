# Adapted from tanguymagne/SyntheticDoc (generation/rendering/single_sample_renderer.py),
# MIT License. See ../LICENSE.
#
# Trimmed from the upstream 10-step pipeline to the two outputs ../render.py actually reads:
# the main render and the UV inverse map (used to remap the page's label quads -- see
# NoValidCameraAngleError's callers there). Dropped: the shadow/albedo/3D/normal ground-truth
# passes, `--save-blend-file`, `--compress-pngs`. Everything kept is otherwise unchanged.

import sys
from pathlib import Path

# Blender runs this file by path rather than importing it as part of a package, so its own
# directory is not on sys.path and the sibling modules below would not resolve without this.
sys.path.append(str(Path(__file__).resolve().parent))
import argparse
import json
import random
import traceback
from datetime import datetime

import camera_angle_sampler
import camera_setup
import config
import environment_setup
import ground_truth_module
import lighting_setup
import material_handler
import mesh_loader
import plane_paper_contact
import render_utils
import scene_setup
import uv_unwrap


class NoValidCameraAngleError(Exception):
    """Raised when no valid camera angles exist for a mesh."""


def generateSample(
    sample_id: int,
    mesh_path: str,
    document_path: str,
    background_path: str,
    flip_mesh: bool,
    output_base_dir: str,
    camera_distance: float,
):
    """Build a scene from one mesh, document and background, render it with its UV inverse map.

    Everything lands in <output_base_dir>/<7-digit sample id>/, and the returned metadata is
    the same dict written there as metadata.json. sample_id doubles as the random seed, so the
    same id and assets reproduce the sample exactly.
    """
    sample_id_str = str(sample_id).zfill(7)

    sample_output_dir = Path(output_base_dir) / sample_id_str
    sample_output_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "sample_id": sample_id_str,
        "sample_index": sample_id,
        "seed": sample_id,
        "timestamp": datetime.now().isoformat(),
        "files": {"mesh": mesh_path, "document": document_path, "surface_texture": background_path},
        "outputs": {},
    }

    try:
        # Only place a seed is set, so every random operation below derives from it
        random.seed(sample_id)

        scene_setup.prepareScene()

        paper_obj = mesh_loader.loadPaperMesh(mesh_path)

        uv_unwrap.unwrapUVMap(paper_obj.name)
        uv_unwrap.ensureCorrectUVOrientation(paper_obj.name)
        if flip_mesh:
            mesh_loader.flipPaperToBackSide(paper_obj)

        # Narrowed to a named exception, so a caller generating a dataset can tell a mesh that
        # simply cannot be framed from a genuine failure and skip it.
        try:
            valid_angles = camera_angle_sampler.getValidCameraAngles(
                mesh_obj=paper_obj,
                target_location=config.PAPER_LOCATION,
                distance=camera_distance,
                debug=False,  # set True to have each rejected angle explain itself
            )
        except ValueError as e:
            # Chained, so the visibility check's own message survives in the traceback.
            raise NoValidCameraAngleError(str(e)) from e

        selected_angle = valid_angles[random.randint(0, len(valid_angles) - 1)]
        inclination_deg, azimuth_deg = camera_angle_sampler.viewDirectionToSpherical(selected_angle)

        camera_roll_deg = random.uniform(*config.CAMERA_ROLL_RANGE_DEG)

        metadata["camera"] = {
            "view_direction": selected_angle.tolist(),
            "inclination_deg": float(inclination_deg),
            "azimuth_deg": float(azimuth_deg),
            "roll_deg": float(camera_roll_deg),
            "num_valid_angles": len(valid_angles),
            "distance": camera_distance,
        }

        material_handler.setupPaperTexture(paper_obj.name, document_path)

        table_obj = environment_setup.createTableSurface(table_texture_path=background_path)

        _ = lighting_setup.setupRandomLighting()
        lighting_setup.adjustWorldLighting(
            strength=config.WORLD_LIGHT_STRENGTH, color=config.WORLD_LIGHT_COLOR
        )

        _ = camera_setup.setupCamera(
            camera_name=config.CAMERA_OBJECT_NAME,
            target_location=config.PAPER_LOCATION,
            view_direction=selected_angle,
            distance=camera_distance,
            roll_deg=camera_roll_deg,
        )

        plane_paper_contact.applyRigidBodySimulation(
            objectNames=[paper_obj.name, table_obj.name],
            rigidBodyTypes=["PASSIVE", "ACTIVE"],
            useMargins=[True, True],
            margins=[0.001, 0.001],
        )

        main_render_path = str(sample_output_dir / "render.png")
        render_utils.renderImage(main_render_path)
        metadata["outputs"]["render"] = main_render_path

        uv_path = str(sample_output_dir / "uv_inverse.exr")
        ground_truth_module.renderUVInverseMap(output_path=uv_path)
        metadata["outputs"]["uv_inverse_map"] = uv_path

        metadata["status"] = "success"

    except Exception as e:
        # Recorded rather than re-raised: `main()` always prints `metadata` as its last
        # line of stdout, success or failure, which is what `../render.py::
        # _run_sample_renderer` parses to tell a retryable NoValidCameraAngleError from
        # everything else. A caller that wants the traceback still has it on stderr.
        metadata["status"] = "failed"
        metadata["error"] = str(e)
        metadata["error_type"] = type(e).__name__
        print(f"Sample {sample_id_str} failed ({metadata['error_type']}): {e}", file=sys.stderr)
        traceback.print_exc()

    finally:
        # Written on success and failure alike, so a failed sample still leaves a record
        # on disk explaining why.
        metadata_path = sample_output_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        metadata["outputs"]["metadata"] = str(metadata_path)

    return metadata


def main():
    # Blender consumes the arguments before "--" itself and passes the rest through untouched,
    # so this script only ever parses what follows that separator.
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Render one warped page sample")
    parser.add_argument("--mesh-path", type=str, required=True, help="Path to the .obj mesh")
    parser.add_argument(
        "--document-path", type=str, required=True, help="Path to the document .png"
    )
    parser.add_argument(
        "--background-path",
        type=str,
        required=True,
        help="Path to the background material directory",
    )
    parser.add_argument(
        "--output-dir", type=str, default="./renders", help="Directory the sample is written to"
    )
    parser.add_argument(
        "--sample-id", type=int, default=0, help="ID of the sample, also used as the random seed"
    )
    parser.add_argument(
        "--camera-distance", type=float, default=0.6, help="Distance from the page to the camera"
    )
    parser.add_argument(
        "--flip-mesh", action="store_true", help="Render the back side of the page"
    )

    args = parser.parse_args(argv)

    sample_metadata = generateSample(
        sample_id=args.sample_id,
        mesh_path=args.mesh_path,
        document_path=args.document_path,
        background_path=args.background_path,
        flip_mesh=args.flip_mesh,
        output_base_dir=args.output_dir,
        camera_distance=args.camera_distance,
    )

    print(json.dumps(sample_metadata))


if __name__ == "__main__":
    main()
