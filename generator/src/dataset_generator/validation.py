import re
from decimal import Decimal
from .model import CanonicalInvoice

VALID_VAT_RATES = {Decimal("0"), Decimal("5"), Decimal("8"), Decimal("10")}
TAX_CODE_PATTERN = re.compile(r"^\d{10}(-\d{3})?$")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_invoice(
    invoice: CanonicalInvoice,
    seen_references: set[tuple[str, str]] | None = None,
) -> list[str]:
    errors = []
    if not invoice.document_id:
        errors.append("document_id is required")
    if invoice.document_type != "vat_invoice":
        errors.append("MVP supports vat_invoice only")
    if not (invoice.form_number or "").strip():
        errors.append("form_number is required")
    if not (invoice.series or "").strip():
        errors.append("series is required")
    if not (invoice.invoice_number or "").strip():
        errors.append("invoice_number is required")
    if not ISO_DATE_PATTERN.match(invoice.issue_date or ""):
        errors.append("issue_date invalid format (expected YYYY-MM-DD)")

    ref_key = (invoice.series, invoice.invoice_number)
    if seen_references is not None and all(ref_key) and ref_key in seen_references:
        errors.append(f"duplicate_reference: {invoice.series}-{invoice.invoice_number} already exists")

    if not invoice.seller.name.strip():
        errors.append("seller.name is required")
    if not invoice.buyer.name.strip():
        errors.append("buyer.name is required")
    if not TAX_CODE_PATTERN.match(invoice.seller.tax_code or ""):
        errors.append("seller.tax_code invalid format")
    if invoice.buyer.tax_code and not TAX_CODE_PATTERN.match(invoice.buyer.tax_code):
        errors.append("buyer.tax_code invalid format")

    if not invoice.lines:
        errors.append("invoice must contain at least one line")
    for i, line in enumerate(invoice.lines):
        if line.quantity <= 0:
            errors.append(f"lines[{i}].quantity must be positive")
        if line.unit_price < 0:
            errors.append(f"lines[{i}].unit_price cannot be negative")
        if line.vat_rate not in VALID_VAT_RATES:
            errors.append(f"lines[{i}].vat_rate out of allowed list (0, 5, 8, 10)")
    if invoice.grand_total != invoice.subtotal + invoice.vat_total:
        errors.append("grand_total arithmetic mismatch")
    return errors