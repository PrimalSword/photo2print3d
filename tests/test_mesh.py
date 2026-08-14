from __future__ import annotations

import math

import trimesh

from photo2print3d.mesh import prepare_mesh


def test_prepare_mesh_scales_longest_axis_and_floors(tmp_path):
    source = tmp_path / "source.obj"
    output = tmp_path / "prepared.stl"

    # Intentionally make Y the longest axis so the auto-orientation path is tested.
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


def test_prepare_mesh_can_add_round_base(tmp_path):
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

    assert stl_path.exists()
    assert report.base_added is True
    assert report.dimensions_mm[2] > 100.0
    assert report.final_shells >= 1
