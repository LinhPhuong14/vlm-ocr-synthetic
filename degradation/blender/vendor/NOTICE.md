# Provenance

Every `.py` file in this directory (and `materials/paperTexture.blend`) is adapted from
[tanguymagne/SyntheticDoc](https://github.com/tanguymagne/SyntheticDoc), used under the MIT
License reproduced in [`LICENSE`](LICENSE) (Copyright (c) 2026 Tanguy MAGNE). Each file names
its own origin and what, if anything, changed from upstream at the top.

What is here is the *rendering* side only — Blender, the paper material, the camera/lighting
system, the UV-inverse ground truth. SyntheticDoc's *simulation* side (`generation/simulation/`,
physically deforming a sheet with [ARCSim](https://graphics.eecs.berkeley.edu/resources/ARCSim/))
is not vendored and is not used anywhere in this repository: ARCSim's licence is
**non-commercial use only**, which is not a constraint this repository can accept for a
component of its own generation pipeline. The deformed meshes fed to `sample_renderer.py`
here come from `../meshes.py` instead — analytic, developable-surface constructions in plain
numpy, with no simulator and no external licence to track.
