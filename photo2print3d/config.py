from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve_path(value: str | None, default: Path) -> Path:
    return Path(value).expanduser().resolve() if value else default.resolve()


@dataclass(frozen=True)
class Settings:
    """Runtime paths and generator defaults."""

    work_dir: Path
    triposr_dir: Path
    triposr_device: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            work_dir=_resolve_path(
                os.getenv("PHOTO2PRINT3D_WORKDIR"), PROJECT_ROOT / "work"
            ),
            triposr_dir=_resolve_path(
                os.getenv("TRIPOSR_DIR"), PROJECT_ROOT / "vendor" / "TripoSR"
            ),
            triposr_device=os.getenv("TRIPOSR_DEVICE", "cuda:0"),
        )

    def ensure_runtime_dirs(self) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
