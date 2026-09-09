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

## The simulated-mesh engine, and what it does NOT change

`degradation/simulated_warp.py` (added later) projects a page onto a mesh some cloth
simulator produced. It still vendors nothing: it is a READER for `.obj` frames carrying
material-space coordinates, it ships pointing at no directory, and with no directory it is
a no-op. No simulator is imported, shelled out to, or needed to run this repository, and
`rulebase/rules/augmentation.yaml`'s `simulated_crumple` ships `enabled: false` with an
empty `meshes` path for exactly that reason. The paragraph above still holds as written:
ARCSim is not vendored and nothing here runs it.

What that engine was built and measured against WAS ARCSim output, and the licence position
is unchanged by that. ARCSim is licensed for "educational, research, and not-for-profit
purposes" only; its conditions include carrying its licence text in copies, displaying that
licence from programs built on it, and citing Narain et al. 2012/2013 in any publication
based on work using it. Producing meshes is a step an operator takes outside this
repository, under whatever licence covers what they ran. **A commercial dataset must not be
built on ARCSim output without a commercial licence from UC Berkeley's Office of Technology
Licensing.** Any simulator whose frames carry material-space coordinates fits the same
reader.
