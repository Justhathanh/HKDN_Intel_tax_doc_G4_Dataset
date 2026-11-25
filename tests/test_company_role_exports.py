
import json
import xml.etree.ElementTree as ET

import pytest

from dataset_generator import batch_generator


COMPANY = {
    "id": "company-integration-test",
    "name": "Công ty kiểm thử tích hợp",
    "legal_name": "CÔNG TY KIỂM THỬ TÍCH HỢP",
    "tax_code": "9905555666",
    "address": "Địa chỉ kiểm thử tích hợp",
    "industry": "Công nghệ",
}


DOCUMENT_ROLES = {
    "sales_invoice": {
        "incoming": "recipient",
        "outgoing": "issuer",
    },
    "adjustment_invoice": {
        "incoming": "recipient",
        "outgoing": "issuer",
    },
    "replacement_invoice": {
        "incoming": "recipient",
        "outgoing": "issuer",
    },
    "state_budget_payment": {
        "incoming": "recipient",
        "outgoing": "recipient",
    },
    "tax_notice": {
        "incoming": "recipient",
        "outgoing": "recipient",
    },
    "fee_receipt": {
        "incoming": "recipient",
        "outgoing": "recipient",
    },
    "pit_withholding": {
        "incoming": "issuer",
        "outgoing": "issuer",
    },
}


@pytest.mark.parametrize("document_type", DOCUMENT_ROLES.keys())
@pytest.mark.parametrize("direction", ["incoming", "outgoing"])
def test_company_role_is_preserved_in_all_exports(
    tmp_path, monkeypatch, document_type, direction
):
    # 1. Tạo batch thực tế
    monkeypatch.setattr(batch_generator, "OUTPUT_ROOT", tmp_path)

    archive = batch_generator.create_batch(
        company=COMPANY,
        document_types=[document_type],
        direction=direction,
        count_per_type=1,
        seed=42,
        include_negative=False,
        allow_unverified=True,
    )

    batch_dir = tmp_path / COMPANY["id"] / archive.stem

    # 2. Đọc batch manifest
    batch_manifest = json.loads(
        (batch_dir / "batch_manifest.json").read_text(encoding="utf-8")
    )

    # Chọn đúng chứng từ cần kiểm tra.
    # Không chọn nhầm chứng từ gốc của Adjustment/Replacement.
    records = [
        item
        for item in batch_manifest["documents"]
        if item["document_type"] == document_type
    ]

    assert len(records) == 1, (
        f"Expected exactly one {document_type}, found {len(records)}"
    )

    record = records[0]
    doc_dir = batch_dir / record["relative_path"]

    # 3. Đọc Canonical
    canonical = json.loads(
        (doc_dir / "canonical.json").read_text(encoding="utf-8")
    )

    # 4. Đọc Ground Truth
    ground_truth = json.loads(
        (doc_dir / "ground_truth.json").read_text(encoding="utf-8")
    )

    # 5. Đọc XML
    doc_manifest = json.loads(
        (doc_dir / "manifest.json").read_text(encoding="utf-8")
    )

    xml_root = ET.parse(
        doc_dir / doc_manifest["xml_artifact"]
    ).getroot()

    # 6. Xác định vai trò doanh nghiệp
    expected_role = DOCUMENT_ROLES[document_type][direction]
    opposite_role = (
        "issuer" if expected_role == "recipient" else "recipient"
    )

    # 7. Kiểm tra Canonical
    assert canonical[f"{expected_role}_name"] == COMPANY["legal_name"]
    assert canonical[f"{expected_role}_tax_code"] == COMPANY["tax_code"]
    assert canonical[f"{expected_role}_address"] == COMPANY["address"]

    # Đối tác không được bị ghi đè.
    assert canonical[f"{opposite_role}_name"] != COMPANY["legal_name"]

    # 8. Kiểm tra Ground Truth khớp Canonical
    for role in ("issuer", "recipient"):
        for field in ("name", "tax_code", "address"):
            canonical_value = canonical[f"{role}_{field}"]
            gt_value = ground_truth["fields"][f"{role}.{field}"]

            assert gt_value["normalized"] == canonical_value

   
    # 9. Kiểm tra XML khớp Canonical
    # Adjustment/Replacement lưu chứng từ đích trong Adjusted.
    if xml_root.tag == "SyntheticAdjustmentScenario":
        xml_document = xml_root.find(
            "Adjusted/SyntheticTaxDocument"
        )
        assert xml_document is not None, (
            "Không tìm thấy Adjusted/SyntheticTaxDocument"
        )
    else:
        xml_document = xml_root

    for role in ("issuer", "recipient"):
        for field in ("name", "tax_code", "address"):
            xml_value = xml_document.findtext(
                f"Parties/{role.capitalize()}/{field}"
            )

            assert xml_value == canonical[f"{role}_{field}"], (
                f"XML mismatch: {document_type}, "
                f"{direction}, {role}.{field}: "
                f"expected={canonical[f'{role}_{field}']!r}, "
                f"actual={xml_value!r}"
            )


    # 10. Kiểm tra PDF
    pdf_files = [
        path
        for path in doc_dir.glob("*.pdf")
        if not path.stem.endswith("_scan")
    ]

    assert pdf_files, "Không tìm thấy PDF chứng từ"

    for pdf_path in pdf_files:
        assert pdf_path.read_bytes().startswith(b"%PDF-")

    # 11. Kiểm tra metadata
    pilot_company = canonical["metadata"]["pilot_company"]

    assert pilot_company["company_id"] == COMPANY["id"]
    assert pilot_company["display_name"] == COMPANY["name"]
    assert pilot_company["selected_direction"] == direction
