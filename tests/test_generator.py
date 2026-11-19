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
