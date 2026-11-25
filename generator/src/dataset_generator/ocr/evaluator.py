"""Field-level OCR evaluation against this repository's Ground Truth format."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _edit_distance(left: list[str] | str, right: list[str] | str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (a != b),
                )
            )
        previous = current
    return previous[-1]


def _field_candidates(value: Any) -> list[str]:
    if isinstance(value, dict):
        candidates = [value.get("displayed"), value.get("normalized")]
    else:
        candidates = [value]
    result: list[str] = []
    for candidate in candidates:
        normalized = normalize_text(candidate)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _best_field_distance(expected: str, actual_words: list[str]) -> tuple[float, float]:
    """Approximate field CER/WER by aligning each expected field to nearby OCR words."""
    expected_words = expected.split()
    if not expected_words:
        return 0.0, 0.0
    if not actual_words:
        return 1.0, 1.0

    min_words = max(1, len(expected_words) - 2)
    max_words = min(len(actual_words), len(expected_words) + 2)
    best_cer = 1.0
    best_wer = 1.0

    for size in range(min_words, max_words + 1):
        for start in range(0, len(actual_words) - size + 1):
            window_words = actual_words[start : start + size]
            window_text = " ".join(window_words)
            char_rate = _edit_distance(expected, window_text) / max(1, len(expected))
            word_rate = _edit_distance(expected_words, window_words) / len(expected_words)
            if (char_rate + word_rate) < (best_cer + best_wer):
                best_cer, best_wer = char_rate, word_rate

    return best_cer, best_wer


def evaluate_fields(ocr_text: str, ground_truth: dict[str, Any]) -> dict[str, Any]:
    """Evaluate GT scalar fields; does not mutate OCR output or Ground Truth."""
    fields = ground_truth.get("fields", {})
    if not isinstance(fields, dict):
        raise ValueError("Ground Truth 'fields' must be a JSON object")

    actual = normalize_text(ocr_text)
    actual_words = actual.split()
    details: dict[str, Any] = {}
    cer_total = wer_total = 0.0

    for field_name, expected_value in fields.items():
        candidates = _field_candidates(expected_value)
        if not candidates:
            continue

        matched = any(
            f" {candidate} " in f" {actual} "
            for candidate in candidates
        )
        distances = [_best_field_distance(candidate, actual_words) for candidate in candidates]
        field_cer, field_wer = min(distances, key=lambda pair: pair[0] + pair[1])
        cer_total += field_cer
        wer_total += field_wer

        details[field_name] = {
            "expected": expected_value,
            "matched": matched,
            "status": "PASS" if matched else "FAIL",
            "field_cer": field_cer,
            "field_wer": field_wer,
        }

    evaluated = len(details)
    passed = sum(1 for item in details.values() if item["matched"])
    field_accuracy = passed / evaluated if evaluated else None
    document_accuracy = (
        1.0 if evaluated and passed == evaluated else
        0.0 if evaluated else None
    )

    return {
        "evaluated_fields": evaluated,
        "passed_fields": passed,
        "failed_fields": evaluated - passed,
        "field_accuracy": field_accuracy,
        "document_accuracy": document_accuracy,
        "field_cer": cer_total / evaluated if evaluated else None,
        "field_wer": wer_total / evaluated if evaluated else None,
        "fields": details,
        "metric_note": (
            "Field CER/WER are approximate per-field edit rates aligned to nearby OCR "
            "tokens. They are not full-page CER/WER. Full-document CER/WER requires "
            "a verbatim page-level transcription in Ground Truth."
        ),
    }


def load_ground_truth(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Ground Truth must be a JSON object: {path}")
    return data
