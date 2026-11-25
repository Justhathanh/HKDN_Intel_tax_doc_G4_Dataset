"""Tesseract adapter. The Python wrapper is optional; the Tesseract binary is external."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


@dataclass
class OCRResult:
    text: str
    mean_confidence: float | None = None


class TesseractOCREngine:
    def __init__(
        self,
        *,
        language: str = "vie+eng",
        config: str = "--oem 1 --psm 6",
        executable: str | None = None,
    ) -> None:
        try:
            import pytesseract
            from pytesseract import Output
        except ImportError as exc:
            raise RuntimeError(
                "OCR Python dependency is missing. Install with: pip install -e .[ocr]"
            ) from exc

        self._pytesseract = pytesseract
        self._output = Output
        self.language = language
        self.config = config

        executable = executable or os.getenv("TESSERACT_CMD")
        if not executable and os.name == "nt":
            windows_default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
            if windows_default.is_file():
                executable = str(windows_default)
        if executable:
            self._pytesseract.pytesseract.tesseract_cmd = executable

        try:
            available = set(self._pytesseract.get_languages(config=""))
        except Exception as exc:
            raise RuntimeError(
                "Cannot start Tesseract. Install Tesseract OCR and add it to PATH, "
                "or set TESSERACT_CMD to the full path of tesseract.exe."
            ) from exc

        requested = set(language.split("+"))
        missing = requested - available
        if missing:
            raise RuntimeError(
                f"Missing Tesseract language data: {', '.join(sorted(missing))}. "
                "Install the Vietnamese 'vie' and English 'eng' traineddata files."
            )

    def recognize(self, image: Image.Image) -> OCRResult:
        data: dict[str, Any] = self._pytesseract.image_to_data(
            image,
            lang=self.language,
            config=self.config,
            output_type=self._output.DICT,
        )
        confidences: list[float] = []
        for raw in data.get("conf", []):
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value >= 0:
                confidences.append(value)

        text = self._pytesseract.image_to_string(
            image,
            lang=self.language,
            config=self.config,
        )
        mean = sum(confidences) / len(confidences) if confidences else None
        return OCRResult(text=text.strip(), mean_confidence=mean)
