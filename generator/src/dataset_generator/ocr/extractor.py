
"""PDF/image OCR extraction with preservation of original input files."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pymupdf
from PIL import Image

from .engine import PaddleOCREngine
from .preprocessing import deskew_image, preprocess_image


def _recognize_page(
    image: Image.Image,
    engine: PaddleOCREngine,
    *,
    preprocess: bool,
    deskew: bool,
) -> dict[str, Any]:
    """Deskew and preprocess an image before OCR."""

    skew_angle = None

    # Step 1: Correct image rotation.
    if deskew:
        image, skew_angle = deskew_image(image)

    # Step 2: Apply image enhancement.
    working = preprocess_image(image) if preprocess else image

    # Step 3: Run OCR.
    result = engine.recognize(working)

    return {
        "text": result.text,
        "mean_confidence": result.mean_confidence,
        "detection_count": result.detection_count,
        "lines": result.lines,
        "skew_angle": skew_angle,
        "deskew_applied": (
            skew_angle is not None and skew_angle != 0.0
        ),
    }


def extract_document(
    source: Path,
    engine: PaddleOCREngine,
    *,
    dpi: int = 220,
    preprocess: bool = True,
    deskew: bool = True,
    force_ocr: bool = False,
) -> dict[str, Any]:
    """Extract text from a PDF or image.

    Text-layer PDF pages use native extraction unless force_ocr is enabled.
    Original input files are never modified.
    """

    source = Path(source)
    suffix = source.suffix.lower()

    if suffix == ".pdf":
        pages: list[dict[str, Any]] = []

        with pymupdf.open(source) as document:
            for page_index, page in enumerate(document):
                native_text = page.get_text("text").strip()

                if native_text and not force_ocr:
                    pages.append({
                         "page": page_index + 1,
                         "method": "text_layer",
                         "text": native_text,
                         "mean_confidence": None,
                         "detection_count": 0,
                         "lines": [],
                         "skew_angle": None,
                        "deskew_applied": False,
                        })
                    continue

                scale = dpi / 72

                pixmap = page.get_pixmap(
                    matrix=pymupdf.Matrix(scale, scale),
                    alpha=False,
                )

                image = Image.open(
                    io.BytesIO(pixmap.tobytes("png"))
                ).convert("RGB")

                recognized = _recognize_page(
                    image,
                    engine,
                    preprocess=preprocess,
                    deskew=deskew,
                )

                pages.append({
                    "page": page_index + 1,
                    "method": "ocr",
                    **recognized,
                })

        return {
            "source": str(source),
            "source_type": "pdf",
            "page_count": len(pages),
            "pages": pages,
            "text": "\n\n".join(
                page["text"] for page in pages
            ),
        }

    if suffix in {
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
        ".bmp",
    }:
        with Image.open(source) as image:
            recognized = _recognize_page(
                image.convert("RGB"),
                engine,
                preprocess=preprocess,
                deskew=deskew,
            )

        return {
            "source": str(source),
            "source_type": "image",
            "page_count": 1,
            "pages": [
                {
                    "page": 1,
                    "method": "ocr",
                    **recognized,
                }
            ],
            "text": recognized["text"],
        }

    raise ValueError(
        f"Unsupported input format: {source.suffix}"
    )
