from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class GenerationError(RuntimeError):
    """Raised when an external reconstruction engine fails."""


@dataclass(frozen=True)
class GenerationResult:
    mesh_path: Path
    stdout: str
    stderr: str


class TripoSRGenerator:
    """Thin adapter around the official TripoSR `run.py` CLI."""

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


class StableFast3DGenerator:
    """Adapter around Stability AI's official Stable Fast 3D `run.py` CLI.

    SF3D is intentionally executed from its own virtual environment. Its official
    dependency pins differ substantially from Photo2Print3D's UI environment, so
    isolating the engine avoids another round of Gradio/Hugging Face dependency
    collisions.
    """

    def __init__(
        self,
        sf3d_dir: str | Path,
        *,
        python_executable: str | Path | None = None,
        device: str = "cpu",
    ) -> None:
        self.sf3d_dir = Path(sf3d_dir).expanduser().resolve()
        self.device = str(device)
        if python_executable:
            self.python_executable = Path(python_executable).expanduser().resolve()
        else:
            if os.name == "nt":
                self.python_executable = self.sf3d_dir / ".venv" / "Scripts" / "python.exe"
            else:
                self.python_executable = self.sf3d_dir / ".venv" / "bin" / "python"

    @property
    def run_script(self) -> Path:
        return self.sf3d_dir / "run.py"

    def validate_installation(self) -> None:
        if not self.run_script.exists():
            raise GenerationError(
                "Stable Fast 3D was not found. Expected run.py at "
                f"{self.run_script}. Run scripts/setup_sf3d_cpu_windows.cmd first or set SF3D_DIR."
            )
        if not self.python_executable.exists():
            raise GenerationError(
                "Stable Fast 3D's isolated Python environment was not found at "
                f"{self.python_executable}. Run scripts/setup_sf3d_cpu_windows.cmd first or "
                "set SF3D_PYTHON."
            )

    def generate(
        self,
        image_path: str | Path,
        output_dir: str | Path,
        *,
        foreground_ratio: float = 0.85,
        texture_resolution: int = 256,
        remesh_option: str = "none",
        target_vertex_count: int = -1,
    ) -> GenerationResult:
        self.validate_installation()

        image_path = Path(image_path).expanduser().resolve()
        output_dir = Path(output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        command = [
            str(self.python_executable),
            str(self.run_script),
            str(image_path),
            "--output-dir",
            str(output_dir),
            "--device",
            self.device,
            "--foreground-ratio",
            str(float(foreground_ratio)),
            "--texture-resolution",
            str(int(texture_resolution)),
            "--remesh_option",
            str(remesh_option),
            "--target_vertex_count",
            str(int(target_vertex_count)),
            "--batch_size",
            "1",
        ]

        env = os.environ.copy()
        if self.device == "cpu":
            env["SF3D_USE_CPU"] = "1"

        completed = subprocess.run(
            command,
            cwd=self.sf3d_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        if completed.returncode != 0:
            combined = f"{completed.stdout}\n{completed.stderr}".lower()
            auth_hint = ""
            if any(term in combined for term in ("gated", "401", "403", "authorized", "access")):
                auth_hint = (
                    "\n\nThe SF3D model is gated on Hugging Face. Request model access and run "
                    "the engine environment's `huggingface-cli login` before retrying."
                )
            raise GenerationError(
                "Stable Fast 3D failed with exit code "
                f"{completed.returncode}.\n\nSTDOUT:\n{completed.stdout}\n\nSTDERR:\n"
                f"{completed.stderr}{auth_hint}"
            )

        mesh_path = output_dir / "0" / "mesh.glb"
        if not mesh_path.exists():
            candidates = sorted(output_dir.rglob("mesh.glb"))
            if not candidates:
                raise GenerationError(
                    "Stable Fast 3D finished without a GLB mesh in the expected output directory."
                )
            mesh_path = candidates[0]

        return GenerationResult(
            mesh_path=mesh_path,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
