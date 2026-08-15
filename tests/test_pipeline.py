from __future__ import annotations

import math
from pathlib import Path

from PIL import Image
import trimesh

from photo2print3d.config import Settings
from photo2print3d.generator import GenerationResult, StableFast3DGenerator, TripoSRGenerator
from photo2print3d.pipeline import finish_reconstruction, reconstruct_image


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        work_dir=tmp_path / "work",
        triposr_dir=tmp_path / "vendor" / "TripoSR",
        triposr_device="cpu",
        sf3d_dir=tmp_path / "vendor" / "stable-fast-3d",
        sf3d_python=tmp_path / "vendor" / "stable-fast-3d" / ".venv" / "python",
        sf3d_device="cpu",
    )


def _reference_image(path: Path) -> None:
    Image.new("RGB", (128, 192), (220, 180, 140)).save(path)


def test_reconstruction_cache_skips_second_triposr_run(tmp_path, monkeypatch):
    image_path = tmp_path / "reference.png"
    _reference_image(image_path)
    settings = _settings(tmp_path)
    calls: list[tuple[int, float]] = []

    def fake_generate(
        self,
        image_path,
        output_dir,
        *,
        mc_resolution=256,
        foreground_ratio=0.85,
    ):
        calls.append((int(mc_resolution), float(foreground_ratio)))
        mesh_path = Path(output_dir) / "0" / "mesh.obj"
        mesh_path.parent.mkdir(parents=True, exist_ok=True)
        trimesh.creation.icosphere(subdivisions=1, radius=1.0).export(mesh_path)
        return GenerationResult(mesh_path=mesh_path, stdout="ok", stderr="")

    monkeypatch.setattr(TripoSRGenerator, "generate", fake_generate)

    first = reconstruct_image(
        image_path,
        engine="triposr",
        mc_resolution=192,
        foreground_ratio=0.85,
        settings=settings,
    )
    second = reconstruct_image(
        image_path,
        engine="triposr",
        mc_resolution=192,
        foreground_ratio=0.85,
        settings=settings,
    )

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert first.engine == "triposr"
    assert first.cache_key == second.cache_key
    assert first.raw_mesh_path == second.raw_mesh_path
    assert first.raw_mesh_path.exists()
    assert len(calls) == 1


def test_triposr_cache_key_changes_with_engine_parameters(tmp_path, monkeypatch):
    image_path = tmp_path / "reference.png"
    _reference_image(image_path)
    settings = _settings(tmp_path)
    calls = 0

    def fake_generate(
        self,
        image_path,
        output_dir,
        *,
        mc_resolution=256,
        foreground_ratio=0.85,
    ):
        nonlocal calls
        calls += 1
        mesh_path = Path(output_dir) / "0" / "mesh.obj"
        mesh_path.parent.mkdir(parents=True, exist_ok=True)
        trimesh.creation.box(extents=[1.0, 1.0, 2.0]).export(mesh_path)
        return GenerationResult(mesh_path=mesh_path, stdout="ok", stderr="")

    monkeypatch.setattr(TripoSRGenerator, "generate", fake_generate)

    fast = reconstruct_image(
        image_path, engine="triposr", mc_resolution=128, settings=settings
    )
    quality = reconstruct_image(
        image_path, engine="triposr", mc_resolution=192, settings=settings
    )

    assert fast.cache_key != quality.cache_key
    assert calls == 2


def test_sf3d_cache_uses_glb_and_skips_second_engine_run(tmp_path, monkeypatch):
    image_path = tmp_path / "reference.png"
    _reference_image(image_path)
    settings = _settings(tmp_path)
    calls: list[tuple[float, int]] = []

    def fake_generate(
        self,
        image_path,
        output_dir,
        *,
        foreground_ratio=0.85,
        texture_resolution=256,
        remesh_option="none",
        target_vertex_count=-1,
    ):
        calls.append((float(foreground_ratio), int(texture_resolution)))
        mesh_path = Path(output_dir) / "0" / "mesh.glb"
        mesh_path.parent.mkdir(parents=True, exist_ok=True)
        mesh_path.write_bytes(
            trimesh.creation.icosphere(subdivisions=1, radius=1.0).export(file_type="glb")
        )
        return GenerationResult(mesh_path=mesh_path, stdout="ok", stderr="")

    monkeypatch.setattr(StableFast3DGenerator, "generate", fake_generate)

    first = reconstruct_image(
        image_path,
        engine="sf3d",
        foreground_ratio=0.85,
        sf3d_texture_resolution=256,
        settings=settings,
    )
    second = reconstruct_image(
        image_path,
        engine="sf3d",
        foreground_ratio=0.85,
        sf3d_texture_resolution=256,
        settings=settings,
    )

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert first.engine == "sf3d"
    assert first.raw_mesh_path.suffix == ".glb"
    assert first.raw_mesh_path.exists()
    assert len(calls) == 1


def test_engine_name_changes_cache_key(tmp_path, monkeypatch):
    image_path = tmp_path / "reference.png"
    _reference_image(image_path)
    settings = _settings(tmp_path)

    def fake_tripo(self, image_path, output_dir, **kwargs):
        mesh_path = Path(output_dir) / "0" / "mesh.obj"
        mesh_path.parent.mkdir(parents=True, exist_ok=True)
        trimesh.creation.box().export(mesh_path)
        return GenerationResult(mesh_path=mesh_path, stdout="ok", stderr="")

    def fake_sf3d(self, image_path, output_dir, **kwargs):
        mesh_path = Path(output_dir) / "0" / "mesh.glb"
        mesh_path.parent.mkdir(parents=True, exist_ok=True)
        mesh_path.write_bytes(trimesh.creation.box().export(file_type="glb"))
        return GenerationResult(mesh_path=mesh_path, stdout="ok", stderr="")

    monkeypatch.setattr(TripoSRGenerator, "generate", fake_tripo)
    monkeypatch.setattr(StableFast3DGenerator, "generate", fake_sf3d)

    tripo = reconstruct_image(image_path, engine="triposr", settings=settings)
    sf3d = reconstruct_image(image_path, engine="sf3d", settings=settings)

    assert tripo.cache_key != sf3d.cache_key


def test_finish_reconstruction_reuses_raw_mesh_and_exports_stages(tmp_path):
    settings = _settings(tmp_path)
    raw_mesh = tmp_path / "raw.obj"
    trimesh.creation.icosphere(subdivisions=2, radius=1.0).export(raw_mesh)

    result = finish_reconstruction(
        raw_mesh,
        target_height_mm=140.0,
        add_base=True,
        base_height_mm=4.0,
        base_margin_mm=5.0,
        refinement_passes=1,
        smoothing_level="Média",
        cleanup_min_shell_percent=0.5,
        settings=settings,
    )

    prepared = trimesh.load(result.stl_path, force="mesh")

    assert result.stl_path.exists()
    assert result.cleaned_mesh_path.exists()
    assert result.refined_mesh_path.exists()
    assert result.smoothed_mesh_path.exists()
    assert result.report.refinement_passes == 1
    assert result.report.refined_faces == result.report.pre_refine_faces * 4
    assert result.report.smoothing_level == "medium"
    assert result.report.final_watertight is True
    assert math.isclose(float(prepared.extents[2]), 140.0, rel_tol=1e-4)
