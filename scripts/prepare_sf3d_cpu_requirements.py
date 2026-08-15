from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: prepare_sf3d_cpu_requirements.py <stable-fast-3d-dir>")
        return 2

    root = Path(sys.argv[1]).expanduser().resolve()
    source = root / "requirements.txt"
    destination = root / "requirements-photo2print3d-cpu.txt"

    if not source.exists():
        print(f"SF3D requirements.txt not found: {source}")
        return 2

    lines: list[str] = []
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("rembg[gpu]=="):
            # The official requirements select rembg[gpu] on Windows. Our V5 test
            # intentionally forces SF3D to CPU, so installing onnxruntime-gpu is
            # unnecessary and creates avoidable driver/runtime friction.
            version_and_marker = line[len("rembg[gpu]==") :]
            lines.append(f"rembg=={version_and_marker}")
        else:
            lines.append(raw_line)

    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
