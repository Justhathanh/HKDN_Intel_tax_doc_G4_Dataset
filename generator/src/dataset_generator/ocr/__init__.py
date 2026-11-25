"""OCR extraction and Ground Truth evaluation for synthetic tax documents."""

from .evaluator import evaluate_fields
from .extractor import extract_document

__all__ = ["evaluate_fields", "extract_document"]
