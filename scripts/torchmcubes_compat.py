"""CPU-only torchmcubes compatibility layer for TripoSR on Windows.

TripoSR only needs ``marching_cubes`` from torchmcubes during mesh extraction.
On Windows, building torchmcubes requires a native C++ toolchain. For the
Photo2Print3D CPU profile we avoid that compiler dependency and use
scikit-image's marching-cubes implementation instead.
"""

from __future__ import annotations

import numpy as np
import torch
from skimage.measure import marching_cubes as _sk_marching_cubes


def marching_cubes(vol: torch.Tensor, thresh: float):
    """Return vertices/faces with the coordinate convention TripoSR expects."""

    volume = np.ascontiguousarray(vol.detach().cpu().numpy(), dtype=np.float32)
    verts, faces, _, _ = _sk_marching_cubes(
        volume,
        level=float(thresh),
        allow_degenerate=False,
    )

    # scikit-image returns coordinates in input-array axis order. torchmcubes
    # returns the reverse order for the volume convention used by TripoSR;
    # TripoSR then reverses it again in isosurface.py. Reverse here so the
    # existing TripoSR code keeps producing the same final XYZ convention.
    verts = np.ascontiguousarray(verts[:, [2, 1, 0]], dtype=np.float32)
    faces = np.ascontiguousarray(faces, dtype=np.int64)

    return torch.from_numpy(verts), torch.from_numpy(faces)
