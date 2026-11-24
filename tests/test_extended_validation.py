from decimal import Decimal
from types import SimpleNamespace

import pytest

from dataset_generator.extended_validation import validate_extended_document


def make_document(**overrides):
    values = {
        "document_id": "doc-001",
        "document_type": "sales_invoice",
        "title": "HÓA ĐƠN BÁN HÀNG",
        "issue_date": "2026-11-25",
        "reference_code": "2C26TAA-00000001",
        "issuer_name": "CÔNG TY BÁN HÀNG",
        "issuer_tax_code": "9901234567",
        "issuer_address": "Đà Nẵng",
        "recipient_name": "CÔNG TY MUA HÀNG",
        "recipient_tax_code": "9912345678",
        "recipient_address": "Hồ Chí Minh",
        "total_amount": Decimal("110"),
        "metadata": {},
        "items": [
            {
                "name": "Dịch vụ mẫu",
                "unit": "Gói",
                "quantity": Decimal("1"),
                "unit_price": Decimal("110"),
                "amount": Decimal("110"),
            }
        ],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_valid_extended_document_has_no_errors():
    assert validate_extended_document(make_document()) == []


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_total_is_rejected(value):
    errors = validate_extended_document(make_document(total_amount=value))
    assert "total_amount must be a finite valid number" in errors


def test_invalid_calendar_date_is_rejected():
    errors = validate_extended_document(make_document(issue_date="2026-02-30"))
    assert "issue_date must use YYYY-MM-DD" in errors


def test_malformed_item_is_reported_without_crashing():
    errors = validate_extended_document(make_document(items=[None]))
    assert "items[0] must be an object" in errors


def test_non_finite_line_amount_is_rejected():
    item = {
        "name": "Dịch vụ mẫu",
        "unit": "Gói",
        "quantity": Decimal("1"),
        "unit_price": Decimal("110"),
        "amount": Decimal("NaN"),
    }
    errors = validate_extended_document(make_document(items=[item]))
    assert "items[0].amount must be a finite valid number" in errors


def test_vat_breakdown_must_match_lines_and_total():
    errors = validate_extended_document(
        make_document(
            document_type="adjustment_invoice",
            total_amount=Decimal("118"),
            metadata={
                "subtotal": Decimal("110"),
                "vat_amount": Decimal("8"),
            },
        )
    )
    assert errors == []


def test_vat_breakdown_rejects_inconsistent_total():
    errors = validate_extended_document(
        make_document(
            document_type="adjustment_invoice",
            total_amount=Decimal("119"),
            metadata={
                "subtotal": Decimal("110"),
                "vat_amount": Decimal("8"),
            },
        )
    )
    assert "subtotal + vat_amount does not match total_amount" in errors
