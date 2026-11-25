"""PDF/image OCR extraction with preservation of original input files."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pymupdf
from PIL import Image

from .engine import TesseractOCREngine
from .preprocessing import preprocess_image


def _recognize_page(
    image: Image.Image,
    engine: TesseractOCREngine,
    *,
    preprocess: bool,
) -> dict[str, Any]:
    working = preprocess_image(image) if preprocess else image
    result = engine.recognize(working)
    return {
        "text": result.text,
        "mean_confidence": result.mean_confidence,
    }


def extract_document(
    source: Path,
    engine: TesseractOCREngine,
    *,
    dpi: int = 220,
    preprocess: bool = True,
    force_ocr: bool = False,
) -> dict[str, Any]:
    """Extract text from a PDF or image. Text-layer PDF pages use native extraction."""
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
                    })
                    continue

                scale = dpi / 72
                pixmap = page.get_pixmap(
                    matrix=pymupdf.Matrix(scale, scale),
                    alpha=False,
                )
                image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
                recognized = _recognize_page(
                    image, engine, preprocess=preprocess
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
            "text": "\n\n".join(page["text"] for page in pages),
        }

    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        with Image.open(source) as image:
            recognized = _recognize_page(
                image.convert("RGB"), engine, preprocess=preprocess
            )
        return {
            "source": str(source),
            "source_type": "image",
            "page_count": 1,
            "pages": [{"page": 1, "method": "ocr", **recognized}],
            "text": recognized["text"],
        }

    raise ValueError(f"Unsupported input format: {source.suffix}")
