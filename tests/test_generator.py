import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
import pymupdf
import pytest

from dataset_generator.exporters import write_bundle, write_corrupted_bundle
from dataset_generator.factory import create_sample_invoice, mutate_invoice
from dataset_generator.model import InvoiceLine
from dataset_generator.registry import DOCUMENT_TYPE_REGISTRY, get_document_type
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


def test_g4t80_registry_9_types_and_statuses():
    expected_keys = {
        "vat_invoice",
        "sales_invoice",
        "adjustment_invoice",
        "replacement_invoice",
        "state_budget_payment",
        "tax_notice",
        "fee_receipt",
        "pit_withholding",
        "non_tax_document",
    }
    assert expected_keys.issubset(set(DOCUMENT_TYPE_REGISTRY.keys()))
    assert get_document_type("vat_invoice").status == "supported"
    assert get_document_type("vat_invoice").in_mvp is True

    for key in expected_keys - {"vat_invoice"}:
        spec = get_document_type(key)
        assert spec.status != "supported"
        assert spec.in_mvp is False

    with pytest.raises(KeyError):
        get_document_type("unknown_doc_type")


def test_g4t81_decimal_rounding_and_metadata_separation():
    line = InvoiceLine(
        name="Dịch vụ test làm tròn",
        unit="Gói",
        quantity=Decimal("1.5"),
        unit_price=Decimal("333333"),
        vat_rate=Decimal("8"),
    )
    assert line.amount == Decimal("500000")
    assert line.vat_amount == Decimal("40000")

    inv = create_sample_invoice(seed=42, scenario="valid")
    legal_dict = inv.to_legal_dict()
    assert "document_id" not in legal_dict
    assert "thtax_core_contract_version" not in legal_dict


@pytest.mark.parametrize(
    "error_kind",
    [
        "missing_buyer_name",
        "invalid_tax_code",
        "negative_qty",
        "duplicate_reference",
        "non_tax_document",
    ],
)
def test_g4t82_all_5_mutation_cases(error_kind):
    base_inv = create_sample_invoice(seed=42, scenario="valid")
    seen_refs = {(base_inv.series, base_inv.invoice_number)}

    mutated = mutate_invoice(base_inv, seed=1042, error_kind=error_kind)
    assert base_inv.buyer.name != ""  

    if error_kind == "duplicate_reference":
        mutated.series = base_inv.series
        mutated.invoice_number = base_inv.invoice_number

    errors = validate_invoice(mutated, seen_references=seen_refs)
    assert len(errors) > 0


def test_g4t83_cli_validation_and_zip_output(tmp_path: Path):
    res_bad = subprocess.run(
        [sys.executable, "-m", "dataset_generator.cli", "--document-type", "sales_invoice"],
        capture_output=True,
        text=True,
    )
    assert res_bad.returncode != 0

    res_ok = subprocess.run(
        [
            sys.executable,
            "-m",
            "dataset_generator.cli",
            "--document-type",
            "vat_invoice",
            "--count",
            "1",
            "--seed",
            "77",
            "--name",
            "test-batch-77",
            "--output",
            str(tmp_path),
            "--zip",
        ],
        capture_output=True,
        text=True,
    )
    assert res_ok.returncode == 0
    assert (tmp_path / "test-batch-77").is_dir()
    assert (tmp_path / "test-batch-77.zip").is_file()


def test_g4t84_pdf_watermark_and_text_layer(tmp_path: Path):
    inv = create_sample_invoice(seed=42, scenario="valid")
    out_dir = tmp_path / inv.document_id
    write_bundle(inv, out_dir)

    with pymupdf.open(out_dir / "invoice.pdf") as doc:
        full_text = "\n".join(page.get_text() for page in doc)

    assert "DỮ LIỆU GIẢ LẬP - KHÔNG CÓ GIÁ TRỊ PHÁP LÝ" in full_text
    assert inv.invoice_number in full_text
    assert inv.document_id not in full_text