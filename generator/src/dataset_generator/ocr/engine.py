
"""PaddleOCR 3.x adapter with line-level diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image


@dataclass
class OCRResult:
    text: str
    mean_confidence: float | None = None
    lines: list[dict[str, Any]] = field(default_factory=list)
    detection_count: int = 0


def _to_list(value: Any) -> list:
    """Convert NumPy arrays and tuples into JSON-compatible lists."""
    if value is None:
        return []

    if hasattr(value, "tolist"):
        return value.tolist()

    return list(value)


class PaddleOCREngine:
    def __init__(self, *, language: str = "vi") -> None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError(
                "PaddleOCR is missing. Install it with: "
                "python -m pip install paddleocr"
            ) from exc

        self.ocr = PaddleOCR(
            lang=language,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def recognize(self, image: Image.Image) -> OCRResult:
        rgb = np.asarray(image.convert("RGB"))
        bgr = rgb[:, :, ::-1].copy()

        results = self.ocr.predict(bgr)

        if not results:
            return OCRResult(text="")

        all_texts: list[str] = []
        all_scores: list[float] = []
        all_lines: list[dict[str, Any]] = []
        total_detections = 0

        for result in results:
            payload = result.json

            if isinstance(payload, dict) and "res" in payload:
                payload = payload["res"]

            if not isinstance(payload, dict):
                continue

            page_texts = _to_list(payload.get("rec_texts"))
            page_scores = _to_list(payload.get("rec_scores"))
            page_boxes = _to_list(payload.get("rec_boxes"))
            detection_polys = _to_list(payload.get("dt_polys"))

            total_detections += len(
                detection_polys if detection_polys else page_boxes
            )

            lines = []

            for index, text in enumerate(page_texts):
                score = (
                    page_scores[index]
                    if index < len(page_scores)
                    else None
                )

                box = (
                    page_boxes[index]
                    if index < len(page_boxes)
                    else None
                )

                lines.append({
                    "text": str(text) if text is not None else "",
                    "confidence": (
                        float(score)
                        if score is not None
                        else None
                    ),
                    "box": _to_list(box),
                })

            # Sort by vertical position, then horizontal position.
            # Preserve original order if boxes are unavailable.
            if lines and all(
                len(line["box"]) >= 4
                for line in lines
            ):
                lines.sort(
                    key=lambda line: (
                        (float(line["box"][1]) +
                         float(line["box"][3])) / 2,
                        float(line["box"][0]),
                    )
                )

            for line in lines:
                text = line["text"]

                if text:
                    all_texts.append(text)

                score = line["confidence"]
                if score is not None:
                    all_scores.append(score)

            all_lines.extend(lines)

        mean = (
            sum(all_scores) / len(all_scores)
            if all_scores else None
        )

        return OCRResult(
            text="\n".join(all_texts).strip(),
            mean_confidence=mean,
            lines=all_lines,
            detection_count=total_detections,
        )
