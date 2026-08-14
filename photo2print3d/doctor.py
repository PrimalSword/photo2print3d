from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from typing import Any

from .config import Settings


def _gpu_info() -> list[str]:
    if not shutil.which("nvidia-smi"):
        return []

    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def system_report(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or Settings.from_env()

    report: dict[str, Any] = {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "triposr_dir": str(settings.triposr_dir),
        "triposr_installed": (settings.triposr_dir / "run.py").exists(),
        "nvidia_gpus": _gpu_info(),
    }

    try:
        import torch

        report.update(
            {
                "torch_installed": True,
                "torch_version": torch.__version__,
                "cuda_available": bool(torch.cuda.is_available()),
                "torch_cuda_version": torch.version.cuda,
                "gpu_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
            }
        )
        if torch.cuda.is_available():
            report["torch_gpu_names"] = [
                torch.cuda.get_device_name(index)
                for index in range(torch.cuda.device_count())
            ]
    except ModuleNotFoundError:
        report.update(
            {
                "torch_installed": False,
                "torch_version": None,
                "cuda_available": False,
                "torch_cuda_version": None,
                "gpu_count": 0,
            }
        )

    return report
