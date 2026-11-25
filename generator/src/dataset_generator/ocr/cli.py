"""Command line entry point for OCR extraction and field evaluation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .engine import TesseractOCREngine
from .evaluator import evaluate_fields, load_ground_truth
from .extractor import extract_document


SUPPORTED_IMAGES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def _safe_name(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem)


def _collect_inputs(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    if not source.is_dir():
        raise FileNotFoundError(f"Input path does not exist: {source}")
    return sorted(
        path for path in source.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    )


def run(args: argparse.Namespace) -> int:
    source = args.input.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    files = _collect_inputs(source)
    if not files:
        raise SystemExit(f"No PDF/image input found under: {source}")

    engine = TesseractOCREngine(
        language=args.lang,
        config=f"--oem 1 --psm {args.psm}",
        executable=args.tesseract_cmd,
    )

    results: list[dict[str, Any]] = []
    for path in files:
        try:
            extracted = extract_document(
                path,
                engine,
                dpi=args.dpi,
                preprocess=not args.no_preprocess,
                force_ocr=args.force_ocr,
            )
            gt = load_ground_truth(path.parent / "ground_truth.json")
            evaluation = evaluate_fields(extracted["text"], gt) if gt else None
            record = {
                **extracted,
                "ground_truth": str(path.parent / "ground_truth.json") if gt else None,
                "evaluation": evaluation,
                "status": "evaluated" if evaluation else "extracted_no_ground_truth",
            }
            output_name = _safe_name(path)
            (output / f"{output_name}.txt").write_text(
                extracted["text"], encoding="utf-8"
            )
            (output / f"{output_name}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            results.append(record)
            print(
                f"[OK] {path.name}: {extracted['page_count']} page(s), "
                f"{evaluation['passed_fields']}/{evaluation['evaluated_fields']} fields"
                if evaluation else
                f"[OK] {path.name}: extracted; Ground Truth not found"
            )
        except Exception as exc:
            results.append({
                "source": str(path),
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            })
            print(f"[ERROR] {path}: {exc}")

    evaluated = [
        item["evaluation"] for item in results if item.get("evaluation")
    ]
    total_fields = sum(item["evaluated_fields"] for item in evaluated)
    passed_fields = sum(item["passed_fields"] for item in evaluated)
    summary = {
        "input": str(source),
        "documents": len(results),
        "successful": sum(item["status"] != "error" for item in results),
        "errors": sum(item["status"] == "error" for item in results),
        "evaluated_documents": len(evaluated),
        "evaluated_fields": total_fields,
        "passed_fields": passed_fields,
        "failed_fields": total_fields - passed_fields,
        "field_accuracy": passed_fields / total_fields if total_fields else None,
        "documents_detail": results,
        "preservation": (
            "Source PDFs/images, canonical.json and ground_truth.json are read-only. "
            "All OCR outputs are written to the separate output directory."
        ),
    }
    report_path = output / "ocr_evaluation_report.json"
    report_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nReport: {report_path}")
    print(
        f"Field accuracy: {passed_fields}/{total_fields} "
        f"({summary['field_accuracy']:.2%})"
        if total_fields else
        "Field accuracy: N/A (no Ground Truth fields evaluated)"
    )
    return 1 if summary["errors"] else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OCR PDF/image files and evaluate extracted fields against Ground Truth"
    )
    parser.add_argument("--input", type=Path, required=True, help="PDF/image file or directory")
    parser.add_argument("--output", type=Path, default=Path("ocr_results"))
    parser.add_argument("--lang", default="vie+eng", help="Tesseract languages, e.g. vie+eng")
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--psm", type=int, default=6)
    parser.add_argument("--tesseract-cmd", default=None)
    parser.add_argument("--force-ocr", action="store_true", help="OCR even when PDF has a text layer")
    parser.add_argument("--no-preprocess", action="store_true")
    args = parser.parse_args()
    if args.dpi < 72:
        parser.error("--dpi must be >= 72")
    if not 0 <= args.psm <= 13:
        parser.error("--psm must be between 0 and 13")
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
