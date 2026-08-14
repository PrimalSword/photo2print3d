# Photo2Print3D

Photo2Print3D is an experimental local-first pipeline that turns a single reference image into a 3D mesh, then prepares that mesh for FDM printing.

The project is intentionally split into two layers:

1. **3D reconstruction engine** — replaceable. The first adapter targets the official TripoSR project.
2. **Printability pipeline** — our code. It repairs simple defects, removes conservative floating geometry, optionally smooths the mesh, scales it in millimetres, adds a printable base, validates the result and exports STL.

The immediate MVP is deliberately narrow: **image in → printable STL out**.

## Status

V2 MVP. The geometry generator and post-processing pipeline are usable from a local Gradio interface. Generated meshes still need visual inspection before printing, but the post-processing layer now includes conservative shell cleanup, Taubin smoothing and exact total-height sizing.

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

#### Windows with NVIDIA/CUDA configured

```powershell
.\scripts\setup_triposr.ps1
```

#### Windows CPU / unsupported or low-memory GPU

```powershell
.\scripts\setup_cpu_windows.ps1
```

The Windows setup installs a known-compatible Gradio/Transformers/Hugging Face stack, ONNX Runtime for `rembg`, the CPU marching-cubes compatibility layer and then validates the environment with `pip check`.

Linux/macOS:

```bash
bash scripts/setup_triposr.sh
```

> TripoSR's official README states that the default single-image GPU run takes about 6 GB of VRAM. On a 16 GB CPU-only workstation, resolution `192` is the recommended quality preset after a successful first run. Resolution `256` is experimental and can force heavy paging; `128` remains the fast/low-memory option.

### 5. Launch the app

```bash
python app.py
```

Open the local Gradio URL shown in the terminal.

## V2 quality controls

The image workflow exposes three reconstruction presets through marching-cubes resolution:

- `128` — fast / low memory;
- `192` — recommended quality balance;
- `256` — experimental / high memory.

Post-processing adds:

- **Taubin smoothing** — Off, Light, Medium or Strong. Light is the default for generated meshes and reduces the faceted look without changing topology.
- **Conservative island cleanup** — tiny components are only removed when they are both small relative to the largest shell and spatially isolated. Nearby details such as hair, eyes, shoes or accessories are deliberately preserved.
- **Exact total height** — the requested final height includes the visible base instead of adding the base on top of the requested figure height.

For imported meshes, smoothing and shell cleanup default to Off so existing geometry is not modified unexpectedly.

## How the V2 pipeline works

```text
reference image
      ↓
image preparation
      ↓
TripoSR adapter
      ↓
raw OBJ mesh
      ↓
repair
      ↓
conservative floating-shell cleanup
      ↓
optional Taubin smoothing
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

If you already have a mesh and only want to prepare it for printing:

```bash
photo2print3d prepare input.obj --height-mm 120 --base --output output.stl
```

To run the full image pipeline:

```bash
photo2print3d generate reference.png --height-mm 120 --base --output output.stl
```

## Current printability checks

The report includes:

- mesh bounds and final dimensions in millimetres;
- source shell count;
- shell count after conservative cleanup;
- number of removed isolated shells;
- final connected-body count;
- source and final watertight status;
- winding consistency;
- volume when available;
- selected smoothing level and cleanup threshold;
- whether a base was added.

It also attempts conservative hole filling and normal repair. A `final_watertight: false` report is a hard warning: inspect or repair the mesh before sending it to the slicer.

## Roadmap

- Blender headless repair backend for robust voxel remeshing / true boolean base union;
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
