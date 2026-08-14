from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import trimesh
from trimesh.smoothing import filter_taubin


class MeshError(RuntimeError):
    """Raised when a mesh cannot be prepared safely enough to export."""


SMOOTHING_ITERATIONS = {
    "off": 0,
    "light": 4,
    "medium": 8,
    "strong": 12,
}

SMOOTHING_ALIASES = {
    "desligado": "off",
    "leve": "light",
    "média": "medium",
    "media": "medium",
    "forte": "strong",
}

DEFAULT_BASE_EMBED_MM = 0.8


@dataclass
class MeshReport:
    target_height_mm: float
    dimensions_mm: list[float]
    vertices: int
    faces: int
    source_shells: int
    cleaned_shells: int
    removed_shells: int
    final_shells: int
    source_watertight: bool
    final_watertight: bool
    winding_consistent: bool
    volume_mm3: float | None
    base_added: bool
    up_axis_detected: str
    smoothing_level: str
    cleanup_min_shell_percent: float
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


def _normalise_smoothing_level(level: str) -> str:
    key = str(level).strip().lower()
    key = SMOOTHING_ALIASES.get(key, key)
    if key not in SMOOTHING_ITERATIONS:
        valid = ", ".join(SMOOTHING_ITERATIONS)
        raise MeshError(f"Unknown smoothing level '{level}'. Valid values: {valid}.")
    return key


def repair_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    mesh = mesh.copy()

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


def _shell_score(shell: trimesh.Trimesh) -> float:
    """Prefer volume for closed bodies and fall back to surface area."""

    try:
        if shell.is_volume:
            volume = float(abs(shell.volume))
            if np.isfinite(volume) and volume > 0:
                return volume
    except Exception:
        pass

    try:
        area = float(shell.area)
        if np.isfinite(area) and area > 0:
            return area
    except Exception:
        pass

    return 0.0


def _aabb_gap(a: trimesh.Trimesh, b: trimesh.Trimesh) -> float:
    """Return Euclidean separation between two axis-aligned bounding boxes."""

    a_min, a_max = np.asarray(a.bounds, dtype=float)
    b_min, b_max = np.asarray(b.bounds, dtype=float)
    gap = np.maximum(0.0, np.maximum(a_min - b_max, b_min - a_max))
    return float(np.linalg.norm(gap))


def cleanup_small_shells(
    mesh: trimesh.Trimesh,
    *,
    min_shell_percent: float = 0.5,
    proximity_ratio: float = 0.015,
) -> tuple[trimesh.Trimesh, int]:
    """Remove tiny, spatially isolated shells while preserving nearby detail."""

    if min_shell_percent <= 0:
        return mesh.copy(), 0

    try:
        shells = list(mesh.split(only_watertight=False))
    except Exception:
        return mesh.copy(), 0

    if len(shells) <= 1:
        return mesh.copy(), 0

    scores = np.asarray([_shell_score(shell) for shell in shells], dtype=float)
    largest = float(scores.max(initial=0.0))
    if largest <= 0:
        return mesh.copy(), 0

    threshold = largest * (float(min_shell_percent) / 100.0)
    kept = {int(i) for i, score in enumerate(scores) if score >= threshold}
    if not kept:
        kept.add(int(np.argmax(scores)))

    model_scale = max(float(np.max(mesh.extents)), 1e-6)
    proximity = max(model_scale * float(proximity_ratio), 1e-6)

    changed = True
    while changed:
        changed = False
        for index, shell in enumerate(shells):
            if index in kept:
                continue
            if any(_aabb_gap(shell, shells[other]) <= proximity for other in kept):
                kept.add(index)
                changed = True

    kept_shells = [shell for index, shell in enumerate(shells) if index in kept]
    removed = len(shells) - len(kept_shells)
    if removed <= 0:
        return mesh.copy(), 0

    cleaned = trimesh.util.concatenate(kept_shells)
    return repair_mesh(cleaned), removed


def smooth_mesh(mesh: trimesh.Trimesh, level: str = "off") -> trimesh.Trimesh:
    """Apply conservative Taubin smoothing without changing mesh topology."""

    key = _normalise_smoothing_level(level)
    iterations = SMOOTHING_ITERATIONS[key]
    if iterations <= 0:
        return mesh.copy()

    smoothed = mesh.copy()
    try:
        filter_taubin(smoothed, lamb=0.45, nu=0.47, iterations=iterations)
    except Exception as exc:
        raise MeshError(f"Mesh smoothing failed: {exc}") from exc

    vertices = np.asarray(smoothed.vertices, dtype=float)
    if not np.isfinite(vertices).all():
        raise MeshError("Mesh smoothing produced invalid vertex coordinates.")

    return repair_mesh(smoothed)


def _export_stage(
    mesh: trimesh.Trimesh,
    artifacts_dir: str | Path | None,
    filename: str,
) -> Path | None:
    if artifacts_dir is None:
        return None

    directory = Path(artifacts_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    mesh.export(str(path), file_type="obj")
    return path


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


def _base_visible_height(height_mm: float, embed_mm: float) -> float:
    sink = min(max(float(embed_mm), 0.0), float(height_mm) * 0.9)
    return float(height_mm) - sink


def add_round_base(
    mesh: trimesh.Trimesh,
    *,
    height_mm: float = 3.0,
    margin_mm: float = 3.0,
    embed_mm: float = DEFAULT_BASE_EMBED_MM,
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
    smoothing_level: str = "off",
    cleanup_min_shell_percent: float = 0.0,
    artifacts_dir: str | Path | None = None,
) -> tuple[Path, MeshReport]:
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    mesh = load_mesh(source)
    source_shells = _shell_count(mesh)
    source_watertight = bool(mesh.is_watertight)

    mesh = repair_mesh(mesh)
    mesh, removed_shells = cleanup_small_shells(
        mesh,
        min_shell_percent=float(cleanup_min_shell_percent),
    )
    cleaned_shells = _shell_count(mesh)
    _export_stage(mesh, artifacts_dir, "cleaned-source.obj")

    smoothing_key = _normalise_smoothing_level(smoothing_level)
    mesh = smooth_mesh(mesh, smoothing_key)
    _export_stage(mesh, artifacts_dir, "smoothed-source.obj")

    mesh, detected_axis = orient_longest_axis_to_z(mesh)

    figure_height = float(target_height_mm)
    if add_base:
        visible_base = _base_visible_height(base_height_mm, DEFAULT_BASE_EMBED_MM)
        figure_height -= visible_base
        if figure_height <= 0:
            raise MeshError("Target height is too small for the selected base height.")

    mesh = scale_to_height(mesh, figure_height)
    mesh = floor_mesh(mesh)

    warnings: list[str] = []
    if not source_watertight:
        warnings.append(
            "The generated source mesh is not watertight. Automatic repair was attempted; "
            "inspect the STL before printing."
        )
    if cleaned_shells > 1:
        warnings.append(
            f"The prepared source contains {cleaned_shells} disconnected shells after "
            "conservative cleanup. Inspect for floating geometry."
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
            "Final mesh is not watertight. Do not treat this export as print-ready without "
            "slicer/mesh validation."
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
        cleaned_shells=cleaned_shells,
        removed_shells=removed_shells,
        final_shells=final_shells,
        source_watertight=source_watertight,
        final_watertight=final_watertight,
        winding_consistent=winding_consistent,
        volume_mm3=round(volume, 3) if volume is not None else None,
        base_added=bool(add_base),
        up_axis_detected=detected_axis,
        smoothing_level=smoothing_key,
        cleanup_min_shell_percent=float(cleanup_min_shell_percent),
        warnings=warnings,
    )
    return destination, report
