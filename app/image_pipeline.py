from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps


def process_image(
    source: Path | BytesIO | Image.Image,
    *,
    width: int,
    height: int,
    contrast: float = 1.15,
) -> Image.Image:
    """Convert an image to Kindle e-ink size: cover crop, grayscale, contrast."""
    if isinstance(source, Image.Image):
        image = source
    else:
        image = Image.open(source)

    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")
    image = ImageOps.fit(
        image,
        (width, height),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    image = image.convert("L")
    if contrast and contrast != 1.0:
        image = ImageEnhance.Contrast(image).enhance(contrast)
    return image


def save_kindle_png(image: Image.Image, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)
    return destination


def save_preview_png(image: Image.Image, destination: Path, max_edge: int = 540) -> Path:
    """Smaller preview for the browser; still grayscale."""
    preview = image.copy()
    preview.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    preview.save(destination, format="PNG", optimize=True)
    return destination
