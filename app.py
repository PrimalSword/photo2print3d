from __future__ import annotations

from pathlib import Path

import gradio as gr

from photo2print3d.config import Settings
from photo2print3d.mesh import prepare_mesh
from photo2print3d.pipeline import generate_printable_model

TITLE = "Photo2Print3D"


def _generate_from_image(
    image_path: str | None,
    height_mm: float,
    add_base: bool,
    base_height_mm: float,
    base_margin_mm: float,
    mc_resolution: int,
    foreground_ratio: float,
):
    if not image_path:
        raise gr.Error("Envie uma imagem de referência primeiro.")

    try:
        result = generate_printable_model(
            image_path,
            target_height_mm=float(height_mm),
            add_base=bool(add_base),
            base_height_mm=float(base_height_mm),
            base_margin_mm=float(base_margin_mm),
            mc_resolution=int(mc_resolution),
            foreground_ratio=float(foreground_ratio),
        )
    except Exception as exc:
        raise gr.Error(str(exc)) from exc

    warnings = result.report.warnings
    status = (
        "✅ STL gerado. Abra no slicer e confira a prévia antes de imprimir."
        if not warnings
        else "⚠️ STL gerado com alertas. Leia o relatório antes de imprimir."
    )
    return (
        str(result.stl_path),
        str(result.stl_path),
        result.report.to_dict(),
        status,
    )


def _prepare_existing_mesh(
    mesh_path: str | None,
    height_mm: float,
    add_base: bool,
    base_height_mm: float,
    base_margin_mm: float,
):
    if not mesh_path:
        raise gr.Error("Envie uma malha 3D primeiro.")

    settings = Settings.from_env()
    settings.ensure_runtime_dirs()
    output_dir = settings.work_dir / "manual-prepare"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{Path(mesh_path).stem}-print.stl"

    try:
        stl_path, report = prepare_mesh(
            mesh_path,
            output_path,
            target_height_mm=float(height_mm),
            add_base=bool(add_base),
            base_height_mm=float(base_height_mm),
            base_margin_mm=float(base_margin_mm),
        )
    except Exception as exc:
        raise gr.Error(str(exc)) from exc

    status = (
        "✅ Malha preparada. Confira no slicer antes de imprimir."
        if not report.warnings
        else "⚠️ Malha preparada com alertas. Confira o relatório e o slicer."
    )
    return str(stl_path), str(stl_path), report.to_dict(), status


with gr.Blocks(title=TITLE) as demo:
    gr.Markdown(
        "# Photo2Print3D\n"
        "**Imagem → reconstrução 3D → escala em mm → base → validação → STL.**\n\n"
        "MVP local. O objetivo não é só gerar uma malha bonita: é chegar a um arquivo que possa ser inspecionado e fatiado para FDM."
    )

    with gr.Tab("Foto → STL"):
        with gr.Row():
            with gr.Column(scale=1):
                image = gr.Image(
                    type="filepath",
                    label="Imagem de referência",
                )
                height = gr.Slider(
                    50,
                    300,
                    value=120,
                    step=1,
                    label="Altura final (mm)",
                )
                add_base = gr.Checkbox(value=True, label="Adicionar base redonda")
                with gr.Row():
                    base_height = gr.Slider(
                        1,
                        10,
                        value=3,
                        step=0.5,
                        label="Altura da base (mm)",
                    )
                    base_margin = gr.Slider(
                        0,
                        15,
                        value=3,
                        step=0.5,
                        label="Margem da base (mm)",
                    )
                with gr.Accordion("Motor 3D", open=False):
                    gr.Markdown(
                        "**CPU/baixa memória:** comece em `128`. "
                        "Suba para `192` ou `256` só depois de validar o primeiro modelo."
                    )
                    resolution = gr.Dropdown(
                        choices=[96, 128, 192, 256, 320, 384],
                        value=128,
                        label="Marching cubes resolution",
                    )
                    foreground_ratio = gr.Slider(
                        0.55,
                        0.95,
                        value=0.85,
                        step=0.01,
                        label="Ocupação do personagem na imagem",
                    )
                generate_button = gr.Button("Gerar STL", variant="primary")

            with gr.Column(scale=1):
                model = gr.Model3D(label="Prévia 3D", height=480)
                download = gr.File(label="Baixar STL")
                status = gr.Markdown()
                report = gr.JSON(label="Relatório de imprimibilidade")

        generate_button.click(
            fn=_generate_from_image,
            inputs=[
                image,
                height,
                add_base,
                base_height,
                base_margin,
                resolution,
                foreground_ratio,
            ],
            outputs=[model, download, report, status],
        )

    with gr.Tab("Malha pronta → STL"):
        gr.Markdown(
            "Use esta aba quando você já tiver um `.obj`, `.glb`, `.gltf`, `.ply` ou `.stl` e quiser apenas escalar, reparar e adicionar base."
        )
        with gr.Row():
            with gr.Column():
                mesh_input = gr.Model3D(label="Malha de entrada")
                mesh_height = gr.Slider(50, 300, value=120, step=1, label="Altura final (mm)")
                mesh_base = gr.Checkbox(value=True, label="Adicionar base redonda")
                mesh_base_height = gr.Slider(1, 10, value=3, step=0.5, label="Altura da base (mm)")
                mesh_base_margin = gr.Slider(0, 15, value=3, step=0.5, label="Margem da base (mm)")
                prepare_button = gr.Button("Preparar para impressão", variant="primary")
            with gr.Column():
                prepared_model = gr.Model3D(label="Prévia preparada", height=480)
                prepared_download = gr.File(label="Baixar STL")
                prepared_status = gr.Markdown()
                prepared_report = gr.JSON(label="Relatório de imprimibilidade")

        prepare_button.click(
            fn=_prepare_existing_mesh,
            inputs=[
                mesh_input,
                mesh_height,
                mesh_base,
                mesh_base_height,
                mesh_base_margin,
            ],
            outputs=[
                prepared_model,
                prepared_download,
                prepared_report,
                prepared_status,
            ],
        )

    gr.Markdown(
        "---\n"
        "**Regra do MVP:** arquivo gerado por IA nunca pula a inspeção no slicer. "
        "Se o relatório disser `final_watertight: false`, trate como pendência de reparo."
    )


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=1).launch()
