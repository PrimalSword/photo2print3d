from __future__ import annotations

from pathlib import Path

import gradio as gr

from photo2print3d.config import Settings
from photo2print3d.mesh import MeshReport, prepare_mesh
from photo2print3d.pipeline import finish_reconstruction, generate_printable_model

TITLE = "Photo2Print3D V5"


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


def _engine_label(engine: str) -> str:
    return "Stable Fast 3D" if str(engine) == "sf3d" else "TripoSR"


def _generate_from_image(
    image_path: str | None,
    engine: str,
    height_mm: float,
    add_base: bool,
    base_height_mm: float,
    base_margin_mm: float,
    mc_resolution: int,
    foreground_ratio: float,
    sf3d_texture_resolution: int,
    refinement_passes: int,
    smoothing_level: str,
    cleanup_min_shell_percent: float,
):
    if not image_path:
        raise gr.Error("Envie uma imagem de referência primeiro.")

    try:
        result = generate_printable_model(
            image_path,
            engine=str(engine),
            target_height_mm=float(height_mm),
            add_base=bool(add_base),
            base_height_mm=float(base_height_mm),
            base_margin_mm=float(base_margin_mm),
            mc_resolution=int(mc_resolution),
            foreground_ratio=float(foreground_ratio),
            sf3d_texture_resolution=int(sf3d_texture_resolution),
            refinement_passes=int(refinement_passes),
            smoothing_level=str(smoothing_level),
            cleanup_min_shell_percent=float(cleanup_min_shell_percent),
        )
    except Exception as exc:
        raise gr.Error(str(exc)) from exc

    engine_name = _engine_label(result.engine)
    if result.cache_hit:
        cache_note = (
            f"♻️ **Cache {engine_name}:** a reconstrução já existia; o motor não rodou novamente. "
        )
    else:
        cache_note = f"🧠 **{engine_name}:** reconstrução nova salva no cache. "

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
        "⚡ **Reprocessamento rápido:** nenhum motor 3D foi executado. "
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
        "# Photo2Print3D V5\n"
        "**Agora com dois motores 3D: Stable Fast 3D para o teste de qualidade e TripoSR como "
        "backend legado.**\n\n"
        "A V5 muda a fonte da geometria em vez de continuar polindo a mesma reconstrução ruim. "
        "Stable Fast 3D roda em um ambiente Python isolado para não quebrar as dependências do app."
    )

    with gr.Tab("Foto → STL"):
        with gr.Row():
            with gr.Column(scale=1):
                image = gr.Image(type="filepath", label="Imagem de referência")

                with gr.Accordion("Motor 3D", open=True):
                    engine = gr.Dropdown(
                        choices=[
                            ("Stable Fast 3D — novo / qualidade", "sf3d"),
                            ("TripoSR — legado", "triposr"),
                        ],
                        value="sf3d",
                        label="Motor de reconstrução",
                    )
                    foreground_ratio = gr.Slider(
                        0.55,
                        0.95,
                        value=0.85,
                        step=0.01,
                        label="Ocupação do personagem na imagem",
                    )
                    resolution = gr.Dropdown(
                        choices=[
                            ("128 — rápido", 128),
                            ("192 — recomendado", 192),
                            ("256 — experimental", 256),
                        ],
                        value=192,
                        label="TripoSR: resolução (ignorada pelo SF3D)",
                    )
                    sf3d_texture = gr.Dropdown(
                        choices=[
                            ("256 — CPU / teste", 256),
                            ("512", 512),
                            ("1024 — padrão oficial / mais pesado", 1024),
                        ],
                        value=256,
                        label="SF3D: resolução de textura/bake",
                    )
                    gr.Markdown(
                        "O **SF3D** usa modelo gated do Hugging Face e, no Windows, suporte "
                        "experimental. Para este PC o backend é forçado para CPU. A resolução "
                        "de textura não aumenta a geometria do STL; 256 reduz trabalho desnecessário "
                        "no primeiro teste."
                    )

                height = gr.Slider(
                    50,
                    300,
                    value=140,
                    step=1,
                    label="Altura total final (mm)",
                )
                add_base = gr.Checkbox(
                    value=False,
                    label="Adicionar base redonda (desligada no teste V5)",
                )
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
                gr.Markdown(
                    "**Nesta rodada deixe a base desligada.** O sistema atual ainda concatena a "
                    "base como outro shell; primeiro vamos decidir se a geometria do novo motor vale a pena."
                )

                with gr.Accordion("Acabamento", open=True):
                    refinement = gr.Dropdown(
                        choices=[
                            ("Desligado — recomendado para avaliar o SF3D", 0),
                            ("1x — ≈ 4× faces", 1),
                            ("2x — experimental", 2),
                        ],
                        value=0,
                        label="Refino da superfície",
                    )
                    smoothing = gr.Dropdown(
                        choices=["Desligado", "Leve", "Média", "Forte"],
                        value="Desligado",
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
                        "Para julgar o novo motor, comece com **refino e suavização desligados**. "
                        "Se a malha bruta for boa, o acabamento pode ser testado depois sem reconstruir."
                    )

                generate_button = gr.Button("Reconstruir com motor selecionado + gerar STL", variant="primary")
                reprocess_button = gr.Button("⚡ Reprocessar acabamento sem reconstruir")

            with gr.Column(scale=1):
                model = gr.Model3D(label="Prévia 3D", height=480)
                download = gr.File(label="Baixar STL")
                status = gr.Markdown()
                report = gr.JSON(label="Relatório de imprimibilidade")

                with gr.Accordion("Arquivos técnicos V5", open=False):
                    raw_download = gr.File(label="Malha bruta do motor (GLB/OBJ)")
                    cleaned_download = gr.File(label="Após limpeza conservadora (OBJ)")
                    refined_download = gr.File(label="Após refino da superfície (OBJ)")
                    smoothed_download = gr.File(label="Após suavização (OBJ)")

        generate_button.click(
            fn=_generate_from_image,
            inputs=[
                image,
                engine,
                height,
                add_base,
                base_height,
                base_margin,
                resolution,
                foreground_ratio,
                sf3d_texture,
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
            "Use esta aba quando você já tiver um `.obj`, `.glb`, `.gltf`, `.ply` ou `.stl`."
        )
        with gr.Row():
            with gr.Column():
                mesh_input = gr.Model3D(label="Malha de entrada")
                mesh_height = gr.Slider(50, 300, value=120, step=1, label="Altura total final (mm)")
                mesh_base = gr.Checkbox(value=False, label="Adicionar base redonda")
                mesh_base_height = gr.Slider(1, 10, value=3, step=0.5, label="Altura da base (mm)")
                mesh_base_margin = gr.Slider(0, 15, value=3, step=0.5, label="Margem da base (mm)")
                mesh_refinement = gr.Dropdown(
                    choices=[("Desligado", 0), ("1x", 1), ("2x — experimental", 2)],
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
            outputs=[prepared_model, prepared_download, prepared_report, prepared_status],
        )

    gr.Markdown(
        "---\n"
        "**Teste V5:** compare primeiro a malha SF3D sem base, sem subdivisão e sem smoothing. "
        "Se a reconstrução bruta continuar ruim, trocar acabamento não vai salvar o modelo."
    )


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=1).launch()
