from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
from uuid import uuid4

from .config import Settings
from .generator import TripoSRGenerator
from .mesh import MeshReport, prepare_mesh
from .preprocess import prepare_reference_image


CACHE_SCHEMA_VERSION = "triposr-v3-1"


@dataclass(frozen=True)
class ReconstructionResult:
    raw_mesh_path: Path
    prepared_image_path: Path
    cache_key: str
    cache_hit: bool


@dataclass(frozen=True)
class FinishResult:
    stl_path: Path
    cleaned_mesh_path: Path
    refined_mesh_path: Path
    smoothed_mesh_path: Path
    report: MeshReport


@dataclass(frozen=True)
class PipelineResult:
    stl_path: Path
    raw_mesh_path: Path
    cleaned_mesh_path: Path
    refined_mesh_path: Path
    smoothed_mesh_path: Path
    prepared_image_path: Path
    report: MeshReport
    cache_key: str
    cache_hit: bool


def _hash_file(path: Path, digest: hashlib._Hash) -> None:
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)


def _reconstruction_cache_key(
    prepared_image: Path,
    *,
    mc_resolution: int,
    foreground_ratio: float,
) -> str:
    digest = hashlib.sha256()
    digest.update(CACHE_SCHEMA_VERSION.encode("utf-8"))
    digest.update(f"|mc={int(mc_resolution)}".encode("utf-8"))
    digest.update(f"|fg={float(foreground_ratio):.6f}".encode("utf-8"))
    _hash_file(prepared_image, digest)
    return digest.hexdigest()


def reconstruct_image(
    image_path: str | Path,
    *,
    mc_resolution: int = 192,
    foreground_ratio: float = 0.85,
    settings: Settings | None = None,
) -> ReconstructionResult:
    """Run TripoSR once and persist the raw geometry in a content-addressed cache."""

    settings = settings or Settings.from_env()
    settings.ensure_runtime_dirs()

    staging_dir = settings.work_dir / "staging" / f"reconstruct-{uuid4().hex[:12]}"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged_image = staging_dir / "reference.png"

    try:
        prepare_reference_image(image_path, staged_image)
        cache_key = _reconstruction_cache_key(
            staged_image,
            mc_resolution=mc_resolution,
            foreground_ratio=foreground_ratio,
        )

        cache_dir = settings.work_dir / "cache" / "reconstructions" / cache_key
        cached_image = cache_dir / "reference.png"
        cached_mesh = cache_dir / "raw" / "mesh.obj"
        metadata_path = cache_dir / "cache.json"

        if cached_mesh.exists() and cached_mesh.stat().st_size > 0:
            if not cached_image.exists():
                cache_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staged_image, cached_image)
            return ReconstructionResult(
                raw_mesh_path=cached_mesh,
                prepared_image_path=cached_image,
                cache_key=cache_key,
                cache_hit=True,
            )

        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_mesh.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged_image, cached_image)

        generator = TripoSRGenerator(
            settings.triposr_dir,
            device=settings.triposr_device,
        )
        generation = generator.generate(
            cached_image,
            cache_dir / "engine-output",
            mc_resolution=mc_resolution,
            foreground_ratio=foreground_ratio,
        )
        shutil.copy2(generation.mesh_path, cached_mesh)

        metadata_path.write_text(
            json.dumps(
                {
                    "schema": CACHE_SCHEMA_VERSION,
                    "cache_key": cache_key,
                    "mc_resolution": int(mc_resolution),
                    "foreground_ratio": float(foreground_ratio),
                    "device": settings.triposr_device,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        return ReconstructionResult(
            raw_mesh_path=cached_mesh,
            prepared_image_path=cached_image,
            cache_key=cache_key,
            cache_hit=False,
        )
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def finish_reconstruction(
    raw_mesh_path: str | Path,
    *,
    target_height_mm: float = 140.0,
    add_base: bool = True,
    base_height_mm: float = 4.0,
    base_margin_mm: float = 5.0,
    refinement_passes: int = 1,
    smoothing_level: str = "medium",
    cleanup_min_shell_percent: float = 0.5,
    settings: Settings | None = None,
) -> FinishResult:
    """Re-run only mesh finishing steps; never invoke the 3D reconstruction model."""

    settings = settings or Settings.from_env()
    settings.ensure_runtime_dirs()

    raw_mesh = Path(raw_mesh_path).expanduser().resolve()
    if not raw_mesh.exists():
        raise FileNotFoundError(
            "A malha bruta em cache não existe mais. Gere a reconstrução novamente."
        )

    job_dir = settings.work_dir / "jobs" / f"finish-{uuid4().hex[:12]}"
    artifacts_dir = job_dir / "artifacts"
    output_dir = job_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    stl_path, report = prepare_mesh(
        raw_mesh,
        output_dir / "photo2print3d.stl",
        target_height_mm=target_height_mm,
        add_base=add_base,
        base_height_mm=base_height_mm,
        base_margin_mm=base_margin_mm,
        refinement_passes=refinement_passes,
        smoothing_level=smoothing_level,
        cleanup_min_shell_percent=cleanup_min_shell_percent,
        artifacts_dir=artifacts_dir,
    )

    return FinishResult(
        stl_path=stl_path,
        cleaned_mesh_path=artifacts_dir / "cleaned-source.obj",
        refined_mesh_path=artifacts_dir / "refined-source.obj",
        smoothed_mesh_path=artifacts_dir / "smoothed-source.obj",
        report=report,
    )


def generate_printable_model(
    image_path: str | Path,
    *,
    target_height_mm: float = 140.0,
    add_base: bool = True,
    base_height_mm: float = 4.0,
    base_margin_mm: float = 5.0,
    mc_resolution: int = 192,
    foreground_ratio: float = 0.85,
    refinement_passes: int = 1,
    smoothing_level: str = "medium",
    cleanup_min_shell_percent: float = 0.5,
    settings: Settings | None = None,
) -> PipelineResult:
    settings = settings or Settings.from_env()

    reconstruction = reconstruct_image(
        image_path,
        mc_resolution=mc_resolution,
        foreground_ratio=foreground_ratio,
        settings=settings,
    )
    finishing = finish_reconstruction(
        reconstruction.raw_mesh_path,
        target_height_mm=target_height_mm,
        add_base=add_base,
        base_height_mm=base_height_mm,
        base_margin_mm=base_margin_mm,
        refinement_passes=refinement_passes,
        smoothing_level=smoothing_level,
        cleanup_min_shell_percent=cleanup_min_shell_percent,
        settings=settings,
    )

    return PipelineResult(
        stl_path=finishing.stl_path,
        raw_mesh_path=reconstruction.raw_mesh_path,
        cleaned_mesh_path=finishing.cleaned_mesh_path,
        refined_mesh_path=finishing.refined_mesh_path,
        smoothed_mesh_path=finishing.smoothed_mesh_path,
        prepared_image_path=reconstruction.prepared_image_path,
        report=finishing.report,
        cache_key=reconstruction.cache_key,
        cache_hit=reconstruction.cache_hit,
    )
