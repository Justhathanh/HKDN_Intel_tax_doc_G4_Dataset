"""Structural validation for extended synthetic documents.

These checks validate internal data consistency only. They do not establish
legal or tax-schema compliance.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

EXTENDED_GENERATOR_TYPES = frozenset(
    {
        "sales_invoice",
        "adjustment_invoice",
        "replacement_invoice",
        "state_budget_payment",
        "tax_notice",
        "fee_receipt",
        "pit_withholding",
    }
)


def _decimal(value: Any) -> Decimal | None:
    """Return a finite Decimal, or None for invalid/non-finite input."""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _required_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_extended_document(doc: Any) -> list[str]:
    """Check structural and arithmetic integrity, not legal compliance."""
    errors: list[str] = []

    if not _required_text(getattr(doc, "document_id", None)):
        errors.append("document_id is required")

    document_type = getattr(doc, "document_type", None)
    if document_type not in EXTENDED_GENERATOR_TYPES:
        errors.append(f"unsupported extended document type: {document_type}")

    for field_name in ("title", "reference_code", "issuer_name", "recipient_name"):
        if not _required_text(getattr(doc, field_name, None)):
            errors.append(f"{field_name} is required")

    issue_date = getattr(doc, "issue_date", None)
    try:
        if not isinstance(issue_date, str):
            raise ValueError
        date.fromisoformat(issue_date)
        if len(issue_date) != 10:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("issue_date must use YYYY-MM-DD")

    total_amount = _decimal(getattr(doc, "total_amount", None))
    if total_amount is None:
        errors.append("total_amount must be a finite valid number")
        return errors
    if total_amount < 0:
        errors.append("total_amount cannot be negative")

    metadata = getattr(doc, "metadata", None)
    if metadata is None:
        metadata = {}
    elif not isinstance(metadata, dict):
        errors.append("metadata must be an object")
        metadata = {}

    items = getattr(doc, "items", None)
    if not isinstance(items, list) or not items:
        errors.append("at least one line item is required")
        return errors

    item_total = Decimal("0")
    all_amounts_present = True

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"items[{index}] must be an object")
            all_amounts_present = False
            continue

        for field_name in ("name", "unit"):
            if not _required_text(item.get(field_name)):
                errors.append(f"items[{index}].{field_name} is required")

        values: dict[str, Decimal] = {}
        for field_name in ("quantity", "unit_price", "amount"):
            if field_name not in item:
                errors.append(f"items[{index}].{field_name} is required")
                if field_name == "amount":
                    all_amounts_present = False
                continue

            number = _decimal(item[field_name])
            if number is None:
                errors.append(f"items[{index}].{field_name} must be a finite valid number")
                if field_name == "amount":
                    all_amounts_present = False
                continue
            values[field_name] = number

        quantity = values.get("quantity")
        if quantity is not None and quantity <= 0:
            errors.append(f"items[{index}].quantity must be positive")

        unit_price = values.get("unit_price")
        if unit_price is not None and unit_price < 0:
            errors.append(f"items[{index}].unit_price cannot be negative")

        amount = values.get("amount")
        if amount is not None:
            if amount < 0:
                errors.append(f"items[{index}].amount cannot be negative")
            item_total += amount
        else:
            all_amounts_present = False

    if all_amounts_present:
        has_vat_breakdown = "subtotal" in metadata or "vat_amount" in metadata
        if has_vat_breakdown:
            subtotal = _decimal(metadata.get("subtotal"))
            vat_amount = _decimal(metadata.get("vat_amount"))
            if subtotal is None or vat_amount is None:
                errors.append("subtotal and vat_amount must be finite valid numbers")
            else:
                if subtotal < 0 or vat_amount < 0:
                    errors.append("subtotal and vat_amount cannot be negative")
                if item_total != subtotal:
                    errors.append("line_items total does not match subtotal")
                if subtotal + vat_amount != total_amount:
                    errors.append("subtotal + vat_amount does not match total_amount")
        elif item_total != total_amount:
            errors.append("line_items total does not match total_amount")

    return errors
