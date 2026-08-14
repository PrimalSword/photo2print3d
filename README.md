# Photo2Print3D

Photo2Print3D is an experimental local-first pipeline that turns a single reference image into a 3D mesh, then prepares that mesh for FDM printing.

The project is intentionally split into two layers:

1. **3D reconstruction engine** — replaceable. The first adapter targets the official TripoSR project.
2. **Printability pipeline** — our code. It repairs defects, cleans conservative floating geometry, optionally refines and smooths the surface, scales in millimetres, adds a base, validates the result and exports STL.

The immediate MVP remains deliberately narrow: **image in → printable STL out**.

## Status

V4 MVP. Heavy TripoSR reconstruction remains content-addressed and cached locally. V4 adds a true geometry-density stage before Taubin smoothing: every refinement pass subdivides each triangle into four while preserving shared edge midpoints.

This does **not** invent detail that TripoSR failed to reconstruct. Its purpose is to give smoothing more vertices to work with so coarse faceting can become gentler curvature.

Generated meshes still require slicer inspection before printing.

## Quick start

### 1. Clone this repository

```bash
git clone https://github.com/PrimalSword/photo2print3d.git
cd photo2print3d
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

Linux/macOS:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

### 3. Run the hardware/runtime doctor

```bash
photo2print3d doctor
```

### 4. Install TripoSR

Windows CPU / unsupported or low-memory GPU:

```powershell
.\scripts\setup_cpu_windows.ps1
```

Windows with NVIDIA/CUDA configured:

```powershell
.\scripts\setup_triposr.ps1
```

Linux/macOS:

```bash
bash scripts/setup_triposr.sh
```

> On a 16 GB CPU-only workstation, reconstruction resolution `192` is the recommended balance. `256` remains experimental. Surface refinement is a finishing operation and therefore reuses the cached raw mesh.

### 5. Launch the app

```bash
python app.py
```

Open the local Gradio URL shown in the terminal.

## V4 workflow

The image tab separates **reconstruction** from **finishing**.

### Reconstruction controls

- **Rápido — 128** — lower memory / faster iteration;
- **Recomendado — 192** — default quality balance;
- **Experimental — 256** — high memory use;
- **foreground occupancy** — subject occupancy in the TripoSR input frame.

The raw reconstruction is cached by prepared image + reconstruction resolution + occupancy. Repeating those inputs reuses:

```text
work/cache/reconstructions/<sha256>/raw/mesh.obj
```

### V4 finishing controls

- **Surface refinement 0x** — keep original topology;
- **Surface refinement 1x** — recommended; approximately 4× the source face count;
- **Surface refinement 2x** — experimental; approximately 16× the source face count and guarded by a 750,000-face safety limit;
- **Taubin smoothing** — Off, Light, Medium or Strong; Medium remains the generated-mesh default;
- **Conservative island cleanup** — removes only tiny, spatially isolated components;
- **Exact total height** — includes the visible base;
- **Base height / margin** — can be changed without reconstructing.

For the current 192 test model with about 41,000 source faces, one refinement pass should produce about 164,000 faces. Two passes would approach 657,000 faces and are therefore experimental.

After the first reconstruction, use **Reprocessar acabamento sem reconstruir** to change refinement, smoothing, cleanup, height or base without invoking TripoSR.

### Technical artifacts

Every generated result exposes:

- raw TripoSR OBJ;
- OBJ after conservative shell cleanup;
- OBJ after surface refinement;
- OBJ after Taubin smoothing;
- final STL.

## How the V4 pipeline works

```text
reference image
      ↓
image preparation
      ↓
content-addressed reconstruction cache
      ↓ (cache miss only)
TripoSR
      ↓
raw OBJ
      ↓
repair + conservative floating-shell cleanup
      ↓
cleaned-source.obj
      ↓
uniform surface subdivision (0x / 1x / 2x)
      ↓
refined-source.obj
      ↓
Taubin smoothing
      ↓
smoothed-source.obj
      ↓
orientation + exact total-height scaling
      ↓
optional circular base
      ↓
printability report
      ↓
STL
```

## CLI

Recommended image workflow:

```bash
photo2print3d generate reference.png --height-mm 140 --mc-resolution 192 --refinement 1 --smoothing medium --cleanup-percent 0.5 --output output.stl
```

Prepare an existing mesh without changing topology by default:

```bash
photo2print3d prepare input.obj --height-mm 120 --base --output output.stl
```

## Current printability checks

The report includes:

- final dimensions in millimetres;
- source shell count and shell count after cleanup;
- removed isolated shell count;
- refinement passes;
- vertex/face counts before and after refinement;
- final connected-body count;
- source and final watertight status;
- winding consistency;
- volume when available;
- smoothing level and cleanup threshold;
- whether a base was added.

A high-density warning is added above 400,000 refined faces. A `final_watertight: false` report remains a hard warning requiring slicer/mesh inspection.

## Roadmap

- voxel/remesh or Blender backend for robust shell union and true base boolean;
- automatic support-risk analysis;
- minimum-thickness analysis;
- selectable base styles and engraved names;
- bust / full-figure workflow presets;
- Stable Fast 3D / newer reconstruction adapters;
- multi-view reconstruction adapters;
- 3MF export with print metadata;
- GPU worker/service mode.

## Third-party components

Photo2Print3D does not vendor TripoSR. The setup scripts clone the official project separately so its code, model weights and licensing remain clearly isolated. Review third-party licences before commercial deployment.

## Safety note for printing

Generated geometry is probabilistic. Always inspect the model in a slicer before printing. Do not use this pipeline for safety-critical, load-bearing, medical, food-contact or other regulated parts without appropriate engineering validation.
