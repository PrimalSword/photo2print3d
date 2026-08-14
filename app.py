from __future__ import annotations

from pathlib import Path

import gradio as gr

from photo2print3d.config import Settings
from photo2print3d.mesh import MeshReport, prepare_mesh
from photo2print3d.pipeline import finish_reconstruction, generate_printable_model

TITLE = "Photo2Print3D V4"


def _finish_status(report: MeshReport, *, prefix: str) -> str:
    removed = report.removed_shells
    cleanup_note = f" Limpeza removeu {removed} ilha(s) isolada(s)." if removed else ""
    refinement_note = ""
    if report.refinement_passes:
        refinement_note = (
            f" Refino {report.refinement_passes}x: "
            f"{report.pre_refine_faces:,} → {report.refined_faces:,} faces."
        )
    if report.warnings:
        return (
            f"⚠️ {prefix}.{cleanup_note}{refinement_note} "
            "Leia o relatório e confira no slicer."
        )
    return (
        f"✅ {prefix}.{cleanup_note}{refinement_note} "
        "Abra no slicer e confira a prévia antes de imprimir."
    )


def _generate_from_image(
    image_path: str | None,
    height_mm: float,
    add_base: bool,
    base_height_mm: float,
    base_margin_mm: float,
    mc_resolution: int,
    foreground_ratio: float,
    refinement_passes: int,
    smoothing_level: str,
    cleanup_min_shell_percent: float,
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
            refinement_passes=int(refinement_passes),
            smoothing_level=str(smoothing_level),
            cleanup_min_shell_percent=float(cleanup_min_shell_percent),
        )
    except Exception as exc:
        raise gr.Error(str(exc)) from exc

    if result.cache_hit:
        cache_note = "♻️ **Cache:** a reconstrução 3D já existia; o TripoSR não rodou novamente. "
    else:
        cache_note = "🧠 **Cache:** reconstrução nova salva para reutilização. "

    status = cache_note + _finish_status(result.report, prefix="STL gerado")
    return (
        str(result.stl_path),
        str(result.stl_path),
        result.report.to_dict(),
        status,
        str(result.raw_mesh_path),
        str(result.raw_mesh_path),
        str(result.cleaned_mesh_path),
        str(result.refined_mesh_path),
        str(result.smoothed_mesh_path),
    )


def _reprocess_cached(
    raw_mesh_path: str | None,
    height_mm: float,
    add_base: bool,
    base_height_mm: float,
    base_margin_mm: float,
    refinement_passes: int,
    smoothing_level: str,
    cleanup_min_shell_percent: float,
):
    if not raw_mesh_path:
        raise gr.Error("Gere uma reconstrução 3D primeiro.")

    try:
        result = finish_reconstruction(
            raw_mesh_path,
            target_height_mm=float(height_mm),
            add_base=bool(add_base),
            base_height_mm=float(base_height_mm),
            base_margin_mm=float(base_margin_mm),
            refinement_passes=int(refinement_passes),
            smoothing_level=str(smoothing_level),
            cleanup_min_shell_percent=float(cleanup_min_shell_percent),
        )
    except Exception as exc:
        raise gr.Error(str(exc)) from exc

    status = (
        "⚡ **Reprocessamento rápido:** TripoSR não foi executado. "
        + _finish_status(result.report, prefix="Acabamento atualizado")
    )
    return (
        str(result.stl_path),
        str(result.stl_path),
        result.report.to_dict(),
        status,
        str(result.cleaned_mesh_path),
        str(result.refined_mesh_path),
        str(result.smoothed_mesh_path),
    )


def _prepare_existing_mesh(
    mesh_path: str | None,
    height_mm: float,
    add_base: bool,
    base_height_mm: float,
    base_margin_mm: float,
    refinement_passes: int,
    smoothing_level: str,
    cleanup_min_shell_percent: float,
):
    if not mesh_path:
        raise gr.Error("Envie uma malha 3D primeiro.")

    settings = Settings.from_env()
    settings.ensure_runtime_dirs()
    output_dir = settings.work_dir / "manual-prepare"
    artifacts_dir = output_dir / "artifacts"
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
            refinement_passes=int(refinement_passes),
            smoothing_level=str(smoothing_level),
            cleanup_min_shell_percent=float(cleanup_min_shell_percent),
            artifacts_dir=artifacts_dir,
        )
    except Exception as exc:
        raise gr.Error(str(exc)) from exc

    status = _finish_status(report, prefix="Malha preparada")
    return str(stl_path), str(stl_path), report.to_dict(), status


with gr.Blocks(title=TITLE) as demo:
    raw_mesh_state = gr.State(value=None)

    gr.Markdown(
        "# Photo2Print3D V4\n"
        "**Imagem → reconstrução 3D cacheada → limpeza → refino de superfície → suavização → "
        "escala em mm → base → validação → STL.**\n\n"
        "A V4 cria geometria intermediária antes da suavização. Assim o acabamento deixa de "
        "apenas empurrar os mesmos vértices grossos e passa a ter mais pontos para formar curvas."
    )

    with gr.Tab("Foto → STL"):
        with gr.Row():
            with gr.Column(scale=1):
                image = gr.Image(type="filepath", label="Imagem de referência")
                height = gr.Slider(
                    50,
                    300,
                    value=140,
                    step=1,
                    label="Altura total final (mm)",
                )
                add_base = gr.Checkbox(value=True, label="Adicionar base redonda")
                with gr.Row():
                    base_height = gr.Slider(
                        1,
                        10,
                        value=4,
                        step=0.5,
                        label="Altura da base (mm)",
                    )
                    base_margin = gr.Slider(
                        0,
                        15,
                        value=5,
                        step=0.5,
                        label="Margem da base (mm)",
                    )

                with gr.Accordion("Reconstrução 3D", open=True):
                    resolution = gr.Dropdown(
                        choices=[
                            ("Rápido — 128", 128),
                            ("Recomendado — 192", 192),
                            ("Experimental — 256", 256),
                        ],
                        value=192,
                        label="Perfil de reconstrução",
                    )
                    foreground_ratio = gr.Slider(
                        0.55,
                        0.95,
                        value=0.85,
                        step=0.01,
                        label="Ocupação do personagem na imagem",
                    )
                    gr.Markdown(
                        "Alterar **perfil de reconstrução** ou **ocupação** exige reconstruir. "
                        "A mesma imagem + esses parâmetros reaproveita o cache."
                    )

                with gr.Accordion("Acabamento V4", open=True):
                    refinement = gr.Dropdown(
                        choices=[
                            ("Desligado — malha original", 0),
                            ("1x — recomendado (≈ 4× faces)", 1),
                            ("2x — experimental (≈ 16× faces)", 2),
                        ],
                        value=1,
                        label="Refino da superfície",
                    )
                    smoothing = gr.Dropdown(
                        choices=["Desligado", "Leve", "Média", "Forte"],
                        value="Média",
                        label="Suavização Taubin",
                    )
                    cleanup_percent = gr.Slider(
                        0.0,
                        5.0,
                        value=0.5,
                        step=0.1,
                        label="Limpeza conservadora de ilhas (% do maior shell)",
                    )
                    gr.Markdown(
                        "**1x** subdivide cada triângulo em quatro antes do Taubin e é o teste "
                        "recomendado. **2x** pode chegar perto de 650 mil faces numa malha 192 e "
                        "é experimental. Refino, suavização, limpeza, altura e base usam o botão "
                        "de reprocessamento e não rodam o TripoSR."
                    )

                generate_button = gr.Button("Reconstruir + gerar STL", variant="primary")
                reprocess_button = gr.Button("⚡ Reprocessar acabamento sem reconstruir")

            with gr.Column(scale=1):
                model = gr.Model3D(label="Prévia 3D", height=480)
                download = gr.File(label="Baixar STL")
                status = gr.Markdown()
                report = gr.JSON(label="Relatório de imprimibilidade")

                with gr.Accordion("Arquivos técnicos V4", open=False):
                    gr.Markdown(
                        "Arquivos intermediários para comparação, diagnóstico ou edição externa."
                    )
                    raw_download = gr.File(label="Malha bruta do TripoSR (OBJ)")
                    cleaned_download = gr.File(label="Após limpeza conservadora (OBJ)")
                    refined_download = gr.File(label="Após refino da superfície (OBJ)")
                    smoothed_download = gr.File(label="Após suavização (OBJ)")

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
                refinement,
                smoothing,
                cleanup_percent,
            ],
            outputs=[
                model,
                download,
                report,
                status,
                raw_mesh_state,
                raw_download,
                cleaned_download,
                refined_download,
                smoothed_download,
            ],
        )

        reprocess_button.click(
            fn=_reprocess_cached,
            inputs=[
                raw_mesh_state,
                height,
                add_base,
                base_height,
                base_margin,
                refinement,
                smoothing,
                cleanup_percent,
            ],
            outputs=[
                model,
                download,
                report,
                status,
                cleaned_download,
                refined_download,
                smoothed_download,
            ],
        )

    with gr.Tab("Malha pronta → STL"):
        gr.Markdown(
            "Use esta aba quando você já tiver um `.obj`, `.glb`, `.gltf`, `.ply` ou `.stl`. "
            "O refino fica desligado por padrão para não alterar uma malha externa sem intenção."
        )
        with gr.Row():
            with gr.Column():
                mesh_input = gr.Model3D(label="Malha de entrada")
                mesh_height = gr.Slider(
                    50,
                    300,
                    value=120,
                    step=1,
                    label="Altura total final (mm)",
                )
                mesh_base = gr.Checkbox(value=True, label="Adicionar base redonda")
                mesh_base_height = gr.Slider(
                    1,
                    10,
                    value=3,
                    step=0.5,
                    label="Altura da base (mm)",
                )
                mesh_base_margin = gr.Slider(
                    0,
                    15,
                    value=3,
                    step=0.5,
                    label="Margem da base (mm)",
                )
                mesh_refinement = gr.Dropdown(
                    choices=[
                        ("Desligado", 0),
                        ("1x", 1),
                        ("2x — experimental", 2),
                    ],
                    value=0,
                    label="Refino da superfície",
                )
                mesh_smoothing = gr.Dropdown(
                    choices=["Desligado", "Leve", "Média", "Forte"],
                    value="Desligado",
                    label="Suavização Taubin",
                )
                mesh_cleanup = gr.Slider(
                    0.0,
                    5.0,
                    value=0.0,
                    step=0.1,
                    label="Limpeza conservadora de ilhas (% do maior shell)",
                )
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
                mesh_refinement,
                mesh_smoothing,
                mesh_cleanup,
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
        "Refino deixa a superfície mais densa, mas não cria detalhes que a reconstrução original "
        "não capturou. Se `final_watertight: false`, trate como pendência de reparo."
    )


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=1).launch()
