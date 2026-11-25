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


def evaluate_fields(ocr_text: str, ground_truth: dict[str, Any]) -> dict[str, Any]:
    """Evaluate GT scalar fields; does not mutate OCR output or Ground Truth."""
    fields = ground_truth.get("fields", {})
    if not isinstance(fields, dict):
        raise ValueError("Ground Truth 'fields' must be a JSON object")

    actual = normalize_text(ocr_text)
    details: dict[str, Any] = {}
    char_errors = char_count = word_errors = word_count = 0

    for field_name, expected_value in fields.items():
        candidates = _field_candidates(expected_value)
        if not candidates:
            continue

        matched = any(
            f" {candidate} " in f" {actual} "
            for candidate in candidates
        )
        best_candidate = min(
            candidates,
            key=lambda candidate: _edit_distance(
                candidate, actual
            ),
        )
        char_errors += _edit_distance(best_candidate, actual)
        char_count += len(best_candidate)
        expected_words = best_candidate.split()
        actual_words = actual.split()
        word_errors += _edit_distance(expected_words, actual_words)
        word_count += len(expected_words)

        details[field_name] = {
            "expected": expected_value,
            "matched": matched,
            "status": "PASS" if matched else "FAIL",
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
        "field_cer": char_errors / char_count if char_count else None,
        "field_wer": word_errors / word_count if word_count else None,
        "fields": details,
        "metric_note": (
            "CER/WER are computed over the concatenated expected scalar fields, "
            "not over a full-page transcript. Full-document CER/WER requires "
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
