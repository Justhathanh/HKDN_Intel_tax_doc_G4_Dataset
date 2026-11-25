
import pytest

from dataset_generator.batch_generator import _apply_company_to_extended
from dataset_generator.extended_docs import create_extended_document


COMPANIES = [
    {
        "id": "company-a",
        "name": "Công ty mẫu A",
        "legal_name": "CÔNG TY TNHH THƯƠNG MẠI MẪU A",
        "tax_code": "9901111222",
        "address": "Địa chỉ Company A",
        "industry": "Thương mại",
    },
    {
        "id": "company-b",
        "name": "Công ty mẫu B",
        "legal_name": "CÔNG TY CỔ PHẦN DỊCH VỤ MẪU B",
        "tax_code": "9902222333",
        "address": "Địa chỉ Company B",
        "industry": "Dịch vụ",
    },
    {
        "id": "company-c",
        "name": "Công ty mẫu C",
        "legal_name": "CÔNG TY TNHH SẢN XUẤT MẪU C",
        "tax_code": "9903333444",
        "address": "Địa chỉ Company C",
        "industry": "Sản xuất",
    },
    {
        # Kiểm tra khả năng hỗ trợ doanh nghiệp mới.
        "id": "company-new",
        "name": "Công ty thử nghiệm mới",
        "legal_name": "CÔNG TY THỬ NGHIỆM MỚI",
        "tax_code": "9904444555",
        "address": "Địa chỉ doanh nghiệp mới",
        "industry": "Công nghệ",
    },
]


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


@pytest.mark.parametrize("company", COMPANIES)
@pytest.mark.parametrize("direction", ["incoming", "outgoing"])
@pytest.mark.parametrize("document_type", DOCUMENT_ROLES.keys())
def test_company_is_assigned_to_correct_document_role(
    company, direction, document_type
):
    doc = create_extended_document(document_type, seed=42)

    expected_role = DOCUMENT_ROLES[document_type][direction]
    opposite_role = "issuer" if expected_role == "recipient" else "recipient"

    # Lưu thông tin đối tác trước khi áp dụng doanh nghiệp.
    original_counterparty = {
        field: getattr(doc, f"{opposite_role}_{field}")
        for field in ("name", "tax_code", "address")
    }

    _apply_company_to_extended(doc, company, direction)

    # Kiểm tra doanh nghiệp xuất hiện đúng vai trò.
    assert getattr(doc, f"{expected_role}_name") == company["legal_name"]
    assert getattr(doc, f"{expected_role}_tax_code") == company["tax_code"]
    assert getattr(doc, f"{expected_role}_address") == company["address"]

    # Kiểm tra thông tin đối tác không bị ghi đè.
    for field, original_value in original_counterparty.items():
        assert getattr(doc, f"{opposite_role}_{field}") == original_value

    # Kiểm tra metadata.
    assert doc.metadata["pilot_company"]["company_id"] == company["id"]
    assert doc.metadata["pilot_company"]["display_name"] == company["name"]
    assert doc.metadata["pilot_company"]["selected_direction"] == direction
