# Photo2Print3D

Photo2Print3D is an experimental local-first pipeline that turns a single reference image into a 3D mesh, then prepares that mesh for FDM printing.

The project is intentionally split into two layers:

1. **3D reconstruction engine** — replaceable. The first adapter targets the official TripoSR project.
2. **Printability pipeline** — our code. It repairs simple defects, removes conservative floating geometry, optionally smooths the mesh, scales it in millimetres, adds a printable base, validates the result and exports STL.

The immediate MVP is deliberately narrow: **image in → printable STL out**.

## Status

V3 MVP. The heavy single-image reconstruction is now content-addressed and cached locally. Once a raw TripoSR mesh exists, height, base, shell cleanup and Taubin smoothing can be reprocessed without invoking TripoSR again.

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

> On a 16 GB CPU-only workstation, resolution `192` is the recommended quality preset. Resolution `256` is experimental and can force heavy paging; `128` remains the fast/low-memory option.

### 5. Launch the app

```bash
python app.py
```

Open the local Gradio URL shown in the terminal.

## V3 workflow

The image tab now separates **reconstruction** from **finishing**.

### Reconstruction controls

- **Rápido — 128** — lower memory / faster iteration;
- **Recomendado — 192** — default quality balance;
- **Experimental — 256** — high memory use;
- **foreground occupancy** — controls how much of the TripoSR input frame is occupied by the subject.

A reconstruction cache key is derived from the prepared image, marching-cubes resolution, foreground ratio and a cache schema version. Repeating the same reconstruction reuses the cached raw OBJ even after restarting the app.

Cached geometry lives under:

```text
work/cache/reconstructions/<sha256>/
```

### Finishing controls

- **Taubin smoothing** — Off, Light, Medium or Strong. Medium is the V3 default for generated meshes based on the current FDM test workflow;
- **Conservative island cleanup** — removes only tiny components that are both small and spatially isolated;
- **Exact total height** — the chosen height includes the visible base;
- **Base height / margin** — can be changed without reconstructing the image.

After the first reconstruction, use **Reprocessar acabamento sem reconstruir** to change smoothing, cleanup, total height or base. This runs only the lightweight mesh pipeline.

### Technical artifacts

Every generated result exposes:

- raw TripoSR OBJ;
- OBJ after conservative shell cleanup;
- OBJ after Taubin smoothing;
- final STL.

These artifacts make A/B comparison and external Blender/mesh-editor inspection easier.

## How the V3 pipeline works

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
repair
      ↓
conservative floating-shell cleanup
      ↓
cleaned-source.obj
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

Changing only finishing parameters starts from the cached raw OBJ and skips every step above it.

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
- bust / full-figure workflow presets;
- Stable Fast 3D / newer reconstruction adapters;
- multi-view reconstruction adapters;
- 3MF export with print metadata;
- GPU worker/service mode.

## Third-party components

Photo2Print3D does not vendor TripoSR. The setup scripts clone the official project separately so its code, model weights and licensing remain clearly isolated. Review third-party licences before commercial deployment.

## Safety note for printing

Generated geometry is probabilistic. Always inspect the model in a slicer before printing. Do not use this pipeline for safety-critical, load-bearing, medical, food-contact or other regulated parts without an appropriate engineering validation process.
