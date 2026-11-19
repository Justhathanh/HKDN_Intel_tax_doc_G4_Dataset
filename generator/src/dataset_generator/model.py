from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any

@dataclass
class InvoiceLine:
    name: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    vat_rate: Decimal

    @property
    def amount(self) -> Decimal:
        return self.quantity * self.unit_price

    @property
    def vat_amount(self) -> Decimal:
        return (self.amount * self.vat_rate / Decimal("100")).quantize(Decimal("1"))

@dataclass
class Party:
    name: str
    address: str
    tax_code: str

@dataclass
class CanonicalInvoice:
    document_id: str
    document_type: str
    issue_date: str
    form_number: str
    series: str
    invoice_number: str
    seller: Party
    buyer: Party
    lines: list[InvoiceLine]
    currency: str = "VND"
    synthetic: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def subtotal(self) -> Decimal:
        return sum((x.amount for x in self.lines), Decimal("0"))

    @property
    def vat_total(self) -> Decimal:
        return sum((x.vat_amount for x in self.lines), Decimal("0"))

    @property
    def grand_total(self) -> Decimal:
        return self.subtotal + self.vat_total

    def to_dict(self) -> dict[str, Any]:
        def conv(v):
            if isinstance(v, Decimal): return str(v)
            if hasattr(v, "__dataclass_fields__"): return {k: conv(x) for k, x in asdict(v).items()}
            if isinstance(v, dict): return {k: conv(x) for k, x in v.items()}
            if isinstance(v, list): return [conv(x) for x in v]
            return v
        data = conv(asdict(self))
        data["totals"] = {"subtotal": str(self.subtotal), "vat_total": str(self.vat_total), "grand_total": str(self.grand_total)}
        return data
