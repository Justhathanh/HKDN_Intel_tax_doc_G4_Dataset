from decimal import Decimal
from .model import CanonicalInvoice

def validate_invoice(invoice: CanonicalInvoice) -> list[str]:
    errors = []
    if not invoice.document_id: errors.append("document_id is required")
    if invoice.document_type != "vat_invoice": errors.append("MVP supports vat_invoice only")
    if not invoice.lines: errors.append("invoice must contain at least one line")
    for i, line in enumerate(invoice.lines):
        if line.quantity <= 0: errors.append(f"lines[{i}].quantity must be positive")
        if line.unit_price < 0: errors.append(f"lines[{i}].unit_price cannot be negative")
        if line.vat_rate < 0 or line.vat_rate > 100: errors.append(f"lines[{i}].vat_rate out of range")
    if invoice.grand_total != invoice.subtotal + invoice.vat_total:
        errors.append("grand_total arithmetic mismatch")
    return errors
