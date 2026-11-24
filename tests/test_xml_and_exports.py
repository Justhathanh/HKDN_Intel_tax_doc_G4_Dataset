import hashlib
import json
import zipfile
import xml.etree.ElementTree as ET

from dataset_generator.bundle_tools import (
    add_xml_and_refresh_manifest,
    create_upload_archive,
)
from dataset_generator.xml_exporter import canonical_to_xml


def test_canonical_xml_is_well_formed_and_escapes_text():
    payload = {
        "document_id": "doc-1",
        "document_type": "vat_invoice",
        "issue_date": "2026-11-25",
        "seller": {"name": "A & B", "tax_code": "0123456789"},
        "buyer": {"name": "Buyer", "tax_code": ""},
        "lines": [{"name": "Item <one>", "quantity": "2", "amount": "100"}],
        "totals": {"subtotal": "100", "grand_total": "100"},
        "metadata": {"scenario_expected": {"final_total": "110"}},
    }

    root = ET.fromstring(canonical_to_xml(payload))
    assert root.findtext("DocumentId") == "doc-1"
    assert root.find("Parties/Seller/name").text == "A & B"
    assert root.find("LineItems/Line/name").text == "Item <one>"
    assert root.attrib["schemaStatus"] == "unverified"
    assert root.findtext("Metadata/scenario_expected/final_total") == "110"


def test_add_xml_refreshes_artifact_hashes(tmp_path):
    doc_dir = tmp_path / "doc-1"
    doc_dir.mkdir()
    canonical = {
        "document_id": "doc-1",
        "document_type": "sales_invoice",
        "issue_date": "2026-11-25",
        "issuer_name": "Issuer",
        "recipient_name": "Recipient",
        "items": [],
        "total_amount": "10",
    }
    (doc_dir / "canonical.json").write_text(
        json.dumps(canonical), encoding="utf-8"
    )
    (doc_dir / "document.pdf").write_bytes(b"%PDF-test")
    (doc_dir / "manifest.json").write_text(
        json.dumps({"document_id": "doc-1", "artifacts": {}}),
        encoding="utf-8",
    )

    xml_path = add_xml_and_refresh_manifest(doc_dir)
    manifest = json.loads((doc_dir / "manifest.json").read_text(encoding="utf-8"))

    assert ET.parse(xml_path).getroot().findtext("DocumentId") == "doc-1"
    assert manifest["xml_schema_verified"] is False
    assert manifest["artifacts"]["document.xml"]["sha256"] == hashlib.sha256(
        xml_path.read_bytes()
    ).hexdigest()


def test_upload_archive_excludes_ground_truth_and_scan(tmp_path):
    batch = tmp_path / "batch-1"
    doc_dir = batch / "documents" / "doc-1"
    doc_dir.mkdir(parents=True)
    files = {
        "document.pdf": b"%PDF-input",
        "document.xml": b"<root />",
        "invoice_scan.pdf": b"%PDF-scan",
        "ground_truth.json": b'{"answer": 1}',
        "canonical.json": b'{"source": true}',
    }
    for name, data in files.items():
        (doc_dir / name).write_bytes(data)
    manifest = {
        "document_id": "doc-1",
        "artifacts": {name: {} for name in files},
    }
    (doc_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    archive = create_upload_archive(batch)
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())

    assert "documents/doc-1/document.pdf" in names
    assert "documents/doc-1/document.xml" in names
    assert not any("ground_truth" in name for name in names)
    assert not any("canonical" in name for name in names)
    assert not any("scan" in name for name in names)


def test_adjustment_scenario_links_original_and_signed_delta(tmp_path, monkeypatch):
    from dataset_generator import batch_generator

    monkeypatch.setattr(batch_generator, "OUTPUT_ROOT", tmp_path)
    archive = batch_generator.create_batch(
        company={
            "id": "company-test",
            "name": "Test",
            "legal_name": "TEST COMPANY",
            "tax_code": "9901111222",
            "address": "Synthetic address",
        },
        document_types=["adjustment_invoice"],
        direction="incoming",
        count_per_type=1,
        seed=42,
        include_negative=False,
        allow_unverified=True,
    )
    batch_dir = tmp_path / "company-test" / archive.stem
    manifest = json.loads((batch_dir / "batch_manifest.json").read_text(encoding="utf-8"))
    records = manifest["documents"]
    original = next(item for item in records if item.get("scenario_role") == "original")
    adjustment = next(item for item in records if item["document_type"] == "adjustment_invoice")
    assert adjustment["related_document_id"] == original["document_id"]
    original_gt = json.loads(
        (batch_dir / "documents" / original["document_id"] / "ground_truth.json").read_text(encoding="utf-8")
    )
    assert original_gt["relationships"]["scenario_id"] == adjustment["scenario_id"]

    doc_dir = batch_dir / "documents" / adjustment["document_id"]
    canonical = json.loads((doc_dir / "canonical.json").read_text(encoding="utf-8"))
    expected = canonical["metadata"]["scenario_expected"]
    assert expected["final_total"] == str(
        int(expected["original_total"]) + int(expected["adjustment_delta"])
    )
    assert (doc_dir / "document.xml").is_file()
    assert (batch_dir / "dataset_index.json").is_file()
    assert archive.is_file()
    assert archive.with_name(archive.stem + "-upload.zip").is_file()


def test_replacement_scenario_is_not_additive(tmp_path, monkeypatch):
    from dataset_generator import batch_generator

    monkeypatch.setattr(batch_generator, "OUTPUT_ROOT", tmp_path)
    archive = batch_generator.create_batch(
        company={
            "id": "company-test",
            "name": "Test",
            "legal_name": "TEST COMPANY",
            "tax_code": "9901111222",
            "address": "Synthetic address",
        },
        document_types=["replacement_invoice"],
        direction="outgoing",
        count_per_type=1,
        seed=43,
        include_negative=False,
        allow_unverified=True,
    )
    batch_dir = tmp_path / "company-test" / archive.stem
    manifest = json.loads((batch_dir / "batch_manifest.json").read_text(encoding="utf-8"))
    replacement = next(
        item for item in manifest["documents"]
        if item["document_type"] == "replacement_invoice"
    )
    canonical = json.loads(
        (batch_dir / "documents" / replacement["document_id"] / "canonical.json").read_text(encoding="utf-8")
    )
    expected = canonical["metadata"]["scenario_expected"]
    assert expected["rule"] == "replacement_supersedes_original_not_additive"
    assert expected["final_total"] == expected["replacement_total"]
