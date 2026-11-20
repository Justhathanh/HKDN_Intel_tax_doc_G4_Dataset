import json
from pathlib import Path
from dataset_generator.exporters import write_bundle, write_corrupted_bundle
from dataset_generator.factory import create_sample_invoice
from dataset_generator.validation import validate_invoice

def test_seed_is_deterministic():
    a = create_sample_invoice(7)
    b = create_sample_invoice(7)
    assert a.to_dict() == b.to_dict()

def test_totals_are_consistent():
    invoice = create_sample_invoice(10)
    assert invoice.grand_total == invoice.subtotal + invoice.vat_total
    assert validate_invoice(invoice) == []

def test_export_multiformat_bundle(tmp_path: Path):
    invoice = create_sample_invoice(15, scenario="valid")
    out_dir = tmp_path / invoice.document_id
    write_bundle(invoice, out_dir)

    expected_files = [
        "canonical.json",
        "invoice.pdf",
        "invoice_scan.pdf",
        "images/page-001.png",
        "images/page-001_blur.jpg",
        "ground_truth.json",
        "manifest.json",
    ]
    for fname in expected_files:
        assert (out_dir / fname).exists(), f"Missing {fname}"

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["validation_status"] == "valid_synthetic"
    assert "invoice_scan.pdf" in manifest["artifacts"]

def test_negative_and_corrupted_cases(tmp_path: Path):
    bad_inv = create_sample_invoice(1001, scenario="invalid_business")
    errors = validate_invoice(bad_inv)
    assert len(errors) > 0

    corrupt_dir = tmp_path / "corrupted"
    write_corrupted_bundle(corrupt_dir, "empty_pdf")
    assert (corrupt_dir / "corrupted_empty.pdf").stat().st_size == 0