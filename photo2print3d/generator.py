from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class GenerationError(RuntimeError):
    """Raised when the external reconstruction engine fails."""


@dataclass(frozen=True)
class GenerationResult:
    mesh_path: Path
    stdout: str
    stderr: str


class TripoSRGenerator:
    """Thin adapter around the official TripoSR `run.py` CLI.

    Keeping the model in a separate checkout avoids coupling our application to
    TripoSR internals and makes the reconstruction engine replaceable later.
    """

    def __init__(self, triposr_dir: str | Path, *, device: str = "cuda:0") -> None:
        self.triposr_dir = Path(triposr_dir).expanduser().resolve()
        self.device = device

    @property
    def run_script(self) -> Path:
        return self.triposr_dir / "run.py"

    def validate_installation(self) -> None:
        if not self.run_script.exists():
            raise GenerationError(
                "TripoSR was not found. Expected run.py at "
                f"{self.run_script}. Run the setup script or set TRIPOSR_DIR."
            )

    def generate(
        self,
        image_path: str | Path,
        output_dir: str | Path,
        *,
        mc_resolution: int = 256,
        foreground_ratio: float = 0.85,
    ) -> GenerationResult:
        self.validate_installation()

        image_path = Path(image_path).expanduser().resolve()
        output_dir = Path(output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        command = [
            sys.executable,
            str(self.run_script),
            str(image_path),
            "--output-dir",
            str(output_dir),
            "--device",
            self.device,
            "--mc-resolution",
            str(int(mc_resolution)),
            "--foreground-ratio",
            str(float(foreground_ratio)),
            "--model-save-format",
            "obj",
        ]

        completed = subprocess.run(
            command,
            cwd=self.triposr_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        if completed.returncode != 0:
            raise GenerationError(
                "TripoSR failed with exit code "
                f"{completed.returncode}.\n\nSTDOUT:\n{completed.stdout}\n\nSTDERR:\n{completed.stderr}"
            )

        mesh_path = output_dir / "0" / "mesh.obj"
        if not mesh_path.exists():
            candidates = sorted(output_dir.rglob("mesh.obj"))
            if not candidates:
                raise GenerationError(
                    "TripoSR finished without an OBJ mesh in the expected output directory."
                )
            mesh_path = candidates[0]

        return GenerationResult(
            mesh_path=mesh_path,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
