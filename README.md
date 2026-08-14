# Photo2Print3D

Photo2Print3D is an experimental local-first pipeline that turns a single reference image into a 3D mesh, then prepares that mesh for FDM printing.

The project is intentionally split into two layers:

1. **3D reconstruction engine** — replaceable. The first adapter targets the official TripoSR project.
2. **Printability pipeline** — our code. It scales in millimetres, repairs simple mesh defects, adds a printable base, validates the result and exports STL.

The immediate MVP is deliberately narrow: **image in → printable STL out**.

## Status

Early MVP. The geometry generator and post-processing pipeline are usable from a local Gradio interface, but generated meshes still need visual inspection before printing.

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

This reports the active Python executable, NVIDIA GPU/VRAM when available, PyTorch/CUDA status and whether TripoSR is installed in the expected location.

### 4. Install TripoSR

The easiest supported integration is to clone the official TripoSR repository into `vendor/TripoSR`.

Windows PowerShell:

```powershell
.\scripts\setup_triposr.ps1
```

Linux/macOS:

```bash
bash scripts/setup_triposr.sh
```

> TripoSR's official README currently states that the default single-image run needs about 6 GB of VRAM. CPU fallback exists, but it will be much slower.

### 5. Launch the app

```bash
python app.py
```

Open the local Gradio URL shown in the terminal.

## How the MVP works

```text
reference image
      ↓
image preparation
      ↓
TripoSR adapter
      ↓
raw OBJ mesh
      ↓
mesh repair + cleanup
      ↓
scale to target height (mm)
      ↓
optional circular base
      ↓
printability report
      ↓
STL
```

## CLI

If you already have a mesh and only want to prepare it for printing:

```bash
photo2print3d prepare input.obj --height-mm 120 --base --output output.stl
```

To run the full image pipeline:

```bash
photo2print3d generate reference.png --height-mm 120 --base --output output.stl
```

## Current printability checks

The MVP reports:

- mesh bounds and final dimensions in millimetres;
- number of connected bodies;
- watertight status;
- winding consistency;
- volume when available;
- whether a base was added.

It also attempts conservative hole filling and normal repair. A `watertight: false` report is a hard warning: inspect or repair the mesh before sending it to the slicer.

## Roadmap

- Blender headless repair backend for robust voxel remeshing;
- automatic support-risk analysis;
- minimum-thickness analysis;
- selectable base styles and engraved names;
- head/ear caricature controls;
- Stable Fast 3D / newer reconstruction adapters;
- multi-view reconstruction adapters;
- 3MF export with print metadata;
- GPU worker/service mode.

## Third-party components

Photo2Print3D does not vendor TripoSR. The setup scripts clone the official project separately so its code, model weights and licensing remain clearly isolated. Review third-party licences before commercial deployment.

## Safety note for printing

Generated geometry is probabilistic. Always inspect the model in a slicer before printing. Do not use this pipeline for safety-critical, load-bearing, medical, food-contact or other regulated parts without an appropriate engineering validation process.
