from __future__ import annotations

import math

import trimesh

from photo2print3d.mesh import prepare_mesh


def test_prepare_mesh_scales_longest_axis_and_floors(tmp_path):
    source = tmp_path / "source.obj"
    output = tmp_path / "prepared.stl"

    mesh = trimesh.creation.box(extents=[2.0, 10.0, 3.0])
    mesh.export(source)

    stl_path, report = prepare_mesh(
        source,
        output,
        target_height_mm=100.0,
        add_base=False,
    )

    prepared = trimesh.load(stl_path, force="mesh")

    assert stl_path.exists()
    assert report.up_axis_detected == "Y"
    assert math.isclose(float(prepared.extents[2]), 100.0, rel_tol=1e-4)
    assert math.isclose(float(prepared.bounds[0, 2]), 0.0, abs_tol=1e-4)
    assert report.final_watertight is True


def test_prepare_mesh_keeps_requested_total_height_with_round_base(tmp_path):
    source = tmp_path / "source.obj"
    output = tmp_path / "with-base.stl"

    mesh = trimesh.creation.box(extents=[4.0, 4.0, 10.0])
    mesh.export(source)

    stl_path, report = prepare_mesh(
        source,
        output,
        target_height_mm=100.0,
        add_base=True,
        base_height_mm=3.0,
        base_margin_mm=2.0,
    )

    prepared = trimesh.load(stl_path, force="mesh")

    assert stl_path.exists()
    assert report.base_added is True
    assert math.isclose(float(prepared.extents[2]), 100.0, rel_tol=1e-4)
    assert math.isclose(report.dimensions_mm[2], 100.0, rel_tol=1e-4)
    assert report.final_shells >= 1


def test_cleanup_removes_tiny_far_shell(tmp_path):
    source = tmp_path / "floating.obj"
    output = tmp_path / "cleaned.stl"

    main = trimesh.creation.box(extents=[10.0, 10.0, 10.0])
    speck = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
    speck.apply_translation([30.0, 0.0, 0.0])
    combined = trimesh.util.concatenate([main, speck])
    combined.export(source)

    _, report = prepare_mesh(
        source,
        output,
        target_height_mm=100.0,
        add_base=False,
        cleanup_min_shell_percent=0.5,
    )

    assert report.source_shells == 2
    assert report.cleaned_shells == 1
    assert report.removed_shells == 1
    assert report.final_shells == 1
    assert report.final_watertight is True


def test_smoothing_level_is_reported(tmp_path):
    source = tmp_path / "sphere.obj"
    output = tmp_path / "smoothed.stl"

    mesh = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    mesh.export(source)

    _, report = prepare_mesh(
        source,
        output,
        target_height_mm=100.0,
        add_base=False,
        smoothing_level="Leve",
    )

    assert report.smoothing_level == "light"
    assert report.final_watertight is True


def test_prepare_mesh_exports_cleaned_and_smoothed_sources(tmp_path):
    source = tmp_path / "sphere.obj"
    output = tmp_path / "prepared.stl"
    artifacts = tmp_path / "artifacts"

    trimesh.creation.icosphere(subdivisions=2, radius=1.0).export(source)

    prepare_mesh(
        source,
        output,
        target_height_mm=100.0,
        add_base=False,
        smoothing_level="Média",
        artifacts_dir=artifacts,
    )

    assert (artifacts / "cleaned-source.obj").exists()
    assert (artifacts / "smoothed-source.obj").exists()
    assert (artifacts / "cleaned-source.obj").stat().st_size > 0
    assert (artifacts / "smoothed-source.obj").stat().st_size > 0
