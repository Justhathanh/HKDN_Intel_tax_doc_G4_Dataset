"""Image preprocessing helpers used before OCR."""

from PIL import Image, ImageFilter, ImageOps


def preprocess_image(image: Image.Image, *, min_width: int = 1800) -> Image.Image:
    """Prepare a document image without destructive binarization.

    Grayscale + autocontrast + modest upscaling/sharpening is a safe baseline
    for the project's clean and mildly degraded synthetic invoices.
    """
    prepared = ImageOps.grayscale(image)
    prepared = ImageOps.autocontrast(prepared, cutoff=1)

    if prepared.width < min_width:
        scale = min_width / prepared.width
        prepared = prepared.resize(
            (min_width, max(1, round(prepared.height * scale))),
            Image.Resampling.LANCZOS,
        )

    return prepared.filter(
        ImageFilter.UnsharpMask(radius=1.2, percent=130, threshold=3)
    )
