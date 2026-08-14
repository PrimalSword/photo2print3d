from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


def prepare_reference_image(
    source: str | Path,
    destination: str | Path,
    *,
    max_side: int = 2048,
) -> Path:
    """Normalize a reference image without inventing or altering visual content.

    TripoSR performs its own background removal, so this stage intentionally keeps
    preprocessing conservative: EXIF orientation is applied, the image is converted
    to RGB, and very large inputs are downscaled.
    """

    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA")

        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

        if image.mode == "RGBA":
            # Preserve a clean neutral background for downstream segmentation.
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.getchannel("A"))
            image = background
        else:
            image = image.convert("RGB")

        image.save(destination, format="PNG", optimize=True)

    return destination
