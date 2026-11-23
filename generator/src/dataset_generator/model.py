from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

CURRENCY_QUANTIZE = Decimal("1")
ROUNDING_POLICY = ROUND_HALF_UP


def round_amount(value: Decimal) -> Decimal:
    return value.quantize(CURRENCY_QUANTIZE, rounding=ROUNDING_POLICY)
    
@dataclass
class InvoiceLine:
    name: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    vat_rate: Decimal

    @property
    def amount(self) -> Decimal:
        return round_amount(self.quantity * self.unit_price)

    @property
    def vat_amount(self) -> Decimal:
        return round_amount(self.amount * self.vat_rate / Decimal("100"))

@dataclass
class Party:
    name: str
    address: str
    tax_code: str
    email: str | None = None
    bank_account: str | None = None

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
    payment_method: str = "TM/CK"
    synthetic: bool = True
    legal_profile_version: str = "ND254_2026_TT91_2026"
    xml_schema_version: str = "unverified"
    thtax_core_contract_version: str = "v1.0-draft"
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

    def to_legal_dict(self) -> dict[str, Any]:
        data = self.to_dict()
        data.pop("document_id", None)
        data.pop("thtax_core_contract_version", None)
        return data

    def to_dict(self) -> dict[str, Any]:
        def conv(v):
            if isinstance(v, Decimal): 
                return str(v)
            if hasattr(v, "__dataclass_fields__"): 
                return {k: conv(x) for k, x in asdict(v).items()}
            if isinstance(v, dict): 
                return {k: conv(x) for k, x in v.items()}
            if isinstance(v, list): 
                return [conv(x) for x in v]
            return v
        data = conv(asdict(self))
        data["totals"] = {"subtotal": str(self.subtotal), 
                          "vat_total": str(self.vat_total), 
                          "grand_total": str(self.grand_total)}
        return data
