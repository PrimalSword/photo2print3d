from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import trimesh


class MeshError(RuntimeError):
    """Raised when a mesh cannot be prepared safely enough to export."""


@dataclass
class MeshReport:
    target_height_mm: float
    dimensions_mm: list[float]
    vertices: int
    faces: int
    source_shells: int
    final_shells: int
    source_watertight: bool
    final_watertight: bool
    winding_consistent: bool
    volume_mm3: float | None
    base_added: bool
    up_axis_detected: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def load_mesh(path: str | Path) -> trimesh.Trimesh:
    loaded = trimesh.load(str(Path(path)), force="mesh", process=False)
    if not isinstance(loaded, trimesh.Trimesh):
        raise MeshError(f"Could not load a triangle mesh from {path}")
    if loaded.vertices.size == 0 or loaded.faces.size == 0:
        raise MeshError("The mesh is empty.")
    return loaded


def _shell_count(mesh: trimesh.Trimesh) -> int:
    try:
        return len(mesh.split(only_watertight=False))
    except Exception:
        return 1


def repair_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    mesh = mesh.copy()

    # Trimesh's validation process removes common duplicate/degenerate data.
    try:
        mesh.process(validate=True)
    except Exception:
        pass

    try:
        mesh.merge_vertices()
    except Exception:
        pass

    try:
        mesh.remove_unreferenced_vertices()
    except Exception:
        pass

    try:
        trimesh.repair.fix_normals(mesh, multibody=True)
    except TypeError:
        trimesh.repair.fix_normals(mesh)

    try:
        trimesh.repair.fill_holes(mesh)
    except Exception:
        pass

    try:
        trimesh.repair.fix_inversion(mesh, multibody=True)
    except Exception:
        pass

    return mesh


def orient_longest_axis_to_z(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, str]:
    """Treat the longest bounding-box dimension as figure height and map it to Z."""

    mesh = mesh.copy()
    extents = np.asarray(mesh.extents, dtype=float)
    up_index = int(np.argmax(extents))
    labels = ("X", "Y", "Z")

    if up_index == 0:
        mesh.vertices = mesh.vertices[:, [1, 2, 0]]
    elif up_index == 1:
        mesh.vertices = mesh.vertices[:, [0, 2, 1]]

    if up_index != 2:
        try:
            trimesh.repair.fix_normals(mesh, multibody=True)
        except TypeError:
            trimesh.repair.fix_normals(mesh)

    return mesh, labels[up_index]


def scale_to_height(mesh: trimesh.Trimesh, target_height_mm: float) -> trimesh.Trimesh:
    if target_height_mm <= 0:
        raise MeshError("Target height must be greater than zero.")

    current_height = float(mesh.extents[2])
    if current_height <= 0:
        raise MeshError("Mesh height is zero; it cannot be scaled.")

    mesh = mesh.copy()
    mesh.apply_scale(float(target_height_mm) / current_height)
    return mesh


def floor_mesh(mesh: trimesh.Trimesh, z: float = 0.0) -> trimesh.Trimesh:
    mesh = mesh.copy()
    mesh.apply_translation([0.0, 0.0, float(z) - float(mesh.bounds[0, 2])])
    return mesh


def add_round_base(
    mesh: trimesh.Trimesh,
    *,
    height_mm: float = 3.0,
    margin_mm: float = 3.0,
    embed_mm: float = 0.8,
) -> trimesh.Trimesh:
    if height_mm <= 0:
        raise MeshError("Base height must be greater than zero.")
    if margin_mm < 0:
        raise MeshError("Base margin cannot be negative.")

    mesh = floor_mesh(mesh)
    footprint = np.asarray(mesh.extents[:2], dtype=float)
    radius = max(float(footprint.max()) / 2.0 + margin_mm, 5.0)

    base = trimesh.creation.cylinder(radius=radius, height=height_mm, sections=96)
    base.apply_translation([0.0, 0.0, height_mm / 2.0])

    # Sink the feet slightly into the closed base. We deliberately keep the base
    # as an overlapping closed shell in the MVP; slicers generally resolve this,
    # while a future Blender backend will perform a true remeshed union.
    sink = min(max(float(embed_mm), 0.0), height_mm * 0.9)
    mesh.apply_translation([0.0, 0.0, height_mm - sink])

    return trimesh.util.concatenate([mesh, base])


def prepare_mesh(
    source: str | Path,
    destination: str | Path,
    *,
    target_height_mm: float = 120.0,
    add_base: bool = True,
    base_height_mm: float = 3.0,
    base_margin_mm: float = 3.0,
) -> tuple[Path, MeshReport]:
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    mesh = load_mesh(source)
    source_shells = _shell_count(mesh)
    source_watertight = bool(mesh.is_watertight)

    mesh = repair_mesh(mesh)
    mesh, detected_axis = orient_longest_axis_to_z(mesh)
    mesh = scale_to_height(mesh, target_height_mm)
    mesh = floor_mesh(mesh)

    warnings: list[str] = []
    if not source_watertight:
        warnings.append(
            "The generated source mesh is not watertight. Automatic repair was attempted; inspect the STL before printing."
        )
    if source_shells > 1:
        warnings.append(
            f"The generated source contains {source_shells} disconnected shells. Inspect for floating geometry."
        )

    if add_base:
        mesh = add_round_base(
            mesh,
            height_mm=base_height_mm,
            margin_mm=base_margin_mm,
        )

    mesh = repair_mesh(mesh)
    final_shells = _shell_count(mesh)
    final_watertight = bool(mesh.is_watertight)

    if not final_watertight:
        warnings.append(
            "Final mesh is not watertight. Do not treat this export as print-ready without slicer/mesh validation."
        )

    winding_consistent = bool(mesh.is_winding_consistent)
    if not winding_consistent:
        warnings.append("Final mesh has inconsistent winding/normals.")

    volume: float | None
    try:
        volume = float(abs(mesh.volume)) if mesh.is_volume else None
    except Exception:
        volume = None

    mesh.export(str(destination), file_type="stl")

    report = MeshReport(
        target_height_mm=float(target_height_mm),
        dimensions_mm=[round(float(v), 3) for v in mesh.extents],
        vertices=int(len(mesh.vertices)),
        faces=int(len(mesh.faces)),
        source_shells=source_shells,
        final_shells=final_shells,
        source_watertight=source_watertight,
        final_watertight=final_watertight,
        winding_consistent=winding_consistent,
        volume_mm3=round(volume, 3) if volume is not None else None,
        base_added=bool(add_base),
        up_axis_detected=detected_axis,
        warnings=warnings,
    )
    return destination, report
