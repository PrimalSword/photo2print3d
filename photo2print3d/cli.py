from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
import typer

from .doctor import system_report
from .mesh import prepare_mesh
from .pipeline import generate_printable_model


app = typer.Typer(no_args_is_help=True, help="Photo2Print3D command-line tools.")
console = Console()


@app.command()
def doctor() -> None:
    """Show the local Python, GPU, PyTorch and TripoSR setup status."""

    console.print_json(json.dumps(system_report()))


@app.command()
def generate(
    image: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output: Path = typer.Option(Path("output.stl"), "--output", "-o"),
    height_mm: float = typer.Option(120.0, "--height-mm", min=10.0, max=1000.0),
    base: bool = typer.Option(True, "--base/--no-base"),
    base_height_mm: float = typer.Option(3.0, "--base-height-mm", min=0.5, max=30.0),
    base_margin_mm: float = typer.Option(3.0, "--base-margin-mm", min=0.0, max=50.0),
    mc_resolution: int = typer.Option(256, "--mc-resolution", min=64, max=512),
) -> None:
    """Generate a 3D mesh from IMAGE and prepare it for printing."""

    result = generate_printable_model(
        image,
        target_height_mm=height_mm,
        add_base=base,
        base_height_mm=base_height_mm,
        base_margin_mm=base_margin_mm,
        mc_resolution=mc_resolution,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result.stl_path.read_bytes())

    console.print(f"[bold green]STL created:[/] {output.resolve()}")
    console.print_json(json.dumps(result.report.to_dict()))


@app.command()
def prepare(
    mesh: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output: Path = typer.Option(Path("output.stl"), "--output", "-o"),
    height_mm: float = typer.Option(120.0, "--height-mm", min=10.0, max=1000.0),
    base: bool = typer.Option(True, "--base/--no-base"),
    base_height_mm: float = typer.Option(3.0, "--base-height-mm", min=0.5, max=30.0),
    base_margin_mm: float = typer.Option(3.0, "--base-margin-mm", min=0.0, max=50.0),
) -> None:
    """Prepare an existing 3D MESH and export a scaled STL."""

    output, report = prepare_mesh(
        mesh,
        output,
        target_height_mm=height_mm,
        add_base=base,
        base_height_mm=base_height_mm,
        base_margin_mm=base_margin_mm,
    )
    console.print(f"[bold green]STL created:[/] {output.resolve()}")
    console.print_json(json.dumps(report.to_dict()))


if __name__ == "__main__":
    app()
