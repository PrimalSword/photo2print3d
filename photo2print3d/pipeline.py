from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .config import Settings
from .generator import TripoSRGenerator
from .mesh import MeshReport, prepare_mesh
from .preprocess import prepare_reference_image


@dataclass(frozen=True)
class PipelineResult:
    stl_path: Path
    raw_mesh_path: Path
    prepared_image_path: Path
    report: MeshReport


def generate_printable_model(
    image_path: str | Path,
    *,
    target_height_mm: float = 120.0,
    add_base: bool = True,
    base_height_mm: float = 3.0,
    base_margin_mm: float = 3.0,
    mc_resolution: int = 192,
    foreground_ratio: float = 0.85,
    smoothing_level: str = "light",
    cleanup_min_shell_percent: float = 0.5,
    settings: Settings | None = None,
) -> PipelineResult:
    settings = settings or Settings.from_env()
    settings.ensure_runtime_dirs()

    job_dir = settings.work_dir / f"job-{uuid4().hex[:12]}"
    input_dir = job_dir / "input"
    raw_dir = job_dir / "raw"
    output_dir = job_dir / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    prepared = prepare_reference_image(image_path, input_dir / "reference.png")

    generator = TripoSRGenerator(
        settings.triposr_dir,
        device=settings.triposr_device,
    )
    generation = generator.generate(
        prepared,
        raw_dir,
        mc_resolution=mc_resolution,
        foreground_ratio=foreground_ratio,
    )

    stl_path, report = prepare_mesh(
        generation.mesh_path,
        output_dir / "photo2print3d.stl",
        target_height_mm=target_height_mm,
        add_base=add_base,
        base_height_mm=base_height_mm,
        base_margin_mm=base_margin_mm,
        smoothing_level=smoothing_level,
        cleanup_min_shell_percent=cleanup_min_shell_percent,
    )

    return PipelineResult(
        stl_path=stl_path,
        raw_mesh_path=generation.mesh_path,
        prepared_image_path=prepared,
        report=report,
    )
