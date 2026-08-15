# Photo2Print3D

Photo2Print3D is an experimental local-first pipeline that turns a single reference image into a 3D mesh and prepares that mesh for FDM printing.

## Status

V5 changes the reconstruction strategy instead of continuing to polish TripoSR output. The app now supports two engines:

- **Stable Fast 3D (SF3D)** — new default quality experiment;
- **TripoSR** — legacy/fallback engine.

Stable Fast 3D is executed from its own isolated virtual environment because its official dependency pins conflict with the Gradio/Hugging Face stack used by the main Photo2Print3D app.

The finishing pipeline remains separate and cacheable: cleanup, optional subdivision, Taubin smoothing, millimetre scaling and STL export can be re-run without executing the reconstruction engine again.

Generated meshes always require slicer inspection.

## Main app setup

Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

## Install Stable Fast 3D on Windows CPU

Stable Fast 3D's official Windows support is experimental and requires Visual Studio 2022 / Build Tools with the **Desktop development with C++** workload.

After Visual Studio/Build Tools is installed, run the CMD wrapper below. It avoids local PowerShell execution-policy restrictions:

```cmd
scripts\setup_sf3d_cpu_windows.cmd
```

The installer:

1. clones the official `Stability-AI/stable-fast-3d` repository;
2. checks out official commit `ff21fc491b4dc5314bf6734c7c0dabd86b5f5bb2`;
3. creates `vendor/stable-fast-3d/.venv`;
4. installs a CPU PyTorch stack in that isolated environment;
5. converts the official Windows `rembg[gpu]` dependency to CPU `rembg` for this CPU-only workflow;
6. installs the remaining official SF3D requirements, including its native extensions.

### Hugging Face access

The official SF3D model `stabilityai/stable-fast-3d` is gated. Request model access on Hugging Face, create a read token, then authenticate the isolated engine environment:

```cmd
vendor\stable-fast-3d\.venv\Scripts\huggingface-cli.exe login
```

The model weights are downloaded by SF3D on first use after authentication.

## Run V5

```powershell
.\.venv\Scripts\python.exe app.py
```

For the first SF3D comparison use:

- motor: **Stable Fast 3D**;
- foreground occupancy: `0.85`;
- SF3D bake/texture resolution: `256` for the CPU test;
- base: **off**;
- surface refinement: **off**;
- Taubin smoothing: **off**;
- cleanup: `0.0%` for the cleanest raw A/B test;
- target height: `140 mm`.

The point of this first run is to judge the geometry produced by SF3D itself. If the raw reconstruction is not materially better than TripoSR, subdivision and smoothing are not treated as a substitute for a better reconstruction engine.

## Engine cache

The cache key includes the selected engine and engine-specific reconstruction parameters. SF3D raw meshes are cached as GLB; TripoSR raw meshes are cached as OBJ:

```text
work/cache/reconstructions/<sha256>/raw/mesh.glb
work/cache/reconstructions/<sha256>/raw/mesh.obj
```

Changing only finishing parameters reuses the cached raw mesh.

## Current finishing pipeline

```text
raw engine mesh
      ↓
repair
      ↓
conservative floating-shell cleanup
      ↓
optional uniform subdivision (0x / 1x / 2x)
      ↓
optional Taubin smoothing
      ↓
orientation + exact scaling in mm
      ↓
optional circular base
      ↓
printability report
      ↓
STL
```

The current circular base is still concatenated as a separate shell rather than true boolean-unioned. V5 therefore keeps the base disabled by default while evaluating SF3D geometry. Robust shell union / true base boolean is a separate next step.

## TripoSR fallback

The existing TripoSR setup remains available. On the tested 16 GB CPU-only workstation, `192` remains the sensible TripoSR reconstruction profile; `256` can cause heavy paging.

## Third-party components

Photo2Print3D does not vendor TripoSR or Stable Fast 3D. Setup scripts clone the official projects into `vendor/`, preserving their separate code, model weights and licensing. Review the upstream licenses and model terms before commercial use.

## Safety note

Generated geometry is probabilistic. Always inspect the model in a slicer before printing. Do not use this pipeline for safety-critical, load-bearing, medical, food-contact or regulated parts without appropriate engineering validation.
