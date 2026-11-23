import copy
import copy
import random
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal
from .model import CanonicalInvoice, InvoiceLine, Party

SELLERS = [
    (
        "CĂ”NG TY TNHH GIáº¢I PHĂP CĂ”NG NGHá»† MINH Há»ŒA (Dá»® LIá»†U GIáº¢ Láº¬P)",
        "Sá»‘ 123 ÄÆ°á»ng Nguyá»…n Huá»‡, PhÆ°á»ng Báº¿n NghĂ©, Quáº­n 1, TP. Há»“ ChĂ­ Minh",
        "9901234567",
        "19039988776601 - NgĂ¢n hĂ ng TMCP Ká»¹ ThÆ°Æ¡ng Viá»‡t Nam (Techcombank)",
    ),
    (
        "CĂ”NG TY Cá»” PHáº¦N THÆ¯Æ NG Máº I Dá»CH Vá»¤ DEMO VIá»†T",
        "Táº§ng 8, TĂ²a nhĂ  Thá»­ Nghiá»‡m, Phá»‘ Duy TĂ¢n, Quáº­n Cáº§u Giáº¥y, HĂ  Ná»™i",
        "9902345678-001",
        "0011009988776 - NgĂ¢n hĂ ng TMCP Ngoáº¡i ThÆ°Æ¡ng Viá»‡t Nam (Vietcombank)",
    ),
    (
        "CĂ”NG TY TNHH PHáº¦N Má»€M MáºªU THTAX",
        "Sá»‘ 88 ÄÆ°á»ng Báº¡ch Äáº±ng, Quáº­n Háº£i ChĂ¢u, TP. ÄĂ  Náºµng",
        "9903456789",
        "112233445566 - NgĂ¢n hĂ ng TMCP CĂ´ng ThÆ°Æ¡ng Viá»‡t Nam (VietinBank)",
    ),
]

BUYERS = [
    (
        "CĂ”NG TY TNHH KHĂCH HĂ€NG DOANH NGHIá»†P MáºªU A",
        "Sá»‘ 456 ÄÆ°á»ng VĂµ VÄƒn Táº§n, PhÆ°á»ng 5, Quáº­n 3, TP. Há»“ ChĂ­ Minh",
        "9911112222",
    ),
    (
        "CĂ”NG TY Cá»” PHáº¦N Äá»I TĂC Káº¾ TOĂN DEMO B",
        "Sá»‘ 79 ÄÆ°á»ng Äiá»‡n BiĂªn Phá»§, Quáº­n BĂ¬nh Tháº¡nh, TP. Há»“ ChĂ­ Minh",
        "9922223333",
    ),
    (
        "DOANH NGHIá»†P TÆ¯ NHĂ‚N THá»¬ NGHIá»†M C",
        "Sá»‘ 12 ÄÆ°á»ng Xa Lá»™ HĂ  Ná»™i, TP. Thá»§ Äá»©c, TP. Há»“ ChĂ­ Minh",
        "9933334444-002",
    ),
]

CATALOG = [
    ("Dá»‹ch vá»¥ tÆ° váº¥n giáº£i phĂ¡p chuyá»ƒn Ä‘á»•i sá»‘ doanh nghiá»‡p", "GĂ³i", 5_000_000, 15_000_000),
    ("Báº£n quyá»n pháº§n má»m quáº£n lĂ½ hĂ³a Ä‘Æ¡n Ä‘iá»‡n tá»­ (12 thĂ¡ng)", "NÄƒm", 2_500_000, 6_000_000),
    ("Dá»‹ch vá»¥ lÆ°u trá»¯ vĂ  sao lÆ°u dá»¯ liá»‡u Ä‘Ă¡m mĂ¢y", "ThĂ¡ng", 1_500_000, 4_500_000),
    ("Thiáº¿t bá»‹ mĂ¡y chá»§ lÆ°u trá»¯ chuyĂªn dá»¥ng NAS", "Bá»™", 12_000_000, 28_000_000),
    ("Dá»‹ch vá»¥ báº£o trĂ¬ há»‡ thá»‘ng háº¡ táº§ng máº¡ng ná»™i bá»™", "Láº§n", 2_000_000, 5_000_000),
]

def _build_valid_invoice(seed: int) -> CanonicalInvoice:
    rng = random.Random(seed)
    seller_name, seller_addr, seller_tax, seller_bank = rng.choice(SELLERS)
    buyer_name, buyer_addr, buyer_tax = rng.choice(BUYERS)

    vat_rate = rng.choice([Decimal("0"), Decimal("5"), Decimal("8"), Decimal("10")])
    base_date = date(2026, 7, 1) + timedelta(days=rng.randint(0, 140))

    chosen_items = rng.sample(CATALOG, k=rng.randint(2, 4))
    lines = []
    for name, unit, min_p, max_p in chosen_items:
        qty = Decimal(str(rng.randint(1, 5)))
        unit_price = Decimal(str(rng.randrange(min_p, max_p, 100_000)))
        lines.append(InvoiceLine(name, unit, qty, unit_price, vat_rate))

    return CanonicalInvoice(
        document_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"thtax-synthetic-valid-{seed}")),
        document_type="vat_invoice",
        issue_date=base_date.isoformat(),
        form_number="1",
        series=f"C26T{rng.choice(['AA', 'AB', 'AC'])}",
        invoice_number=f"{seed:08d}",
        seller=Party(seller_name, seller_addr, seller_tax),
        buyer=Party(buyer_name, buyer_addr, buyer_tax),
        lines=lines,
        currency="VND",
        synthetic=True,
        extra={
            "seed": seed,
            "scenario": "valid",
            "qa_label": "valid_synthetic",
            "error_reason": None,
            "seller_bank_account": seller_bank,
            "payment_method": rng.choice(["TM/CK", "CK", "TM"]),
            "watermark": "Dá»® LIá»†U GIáº¢ Láº¬P - KHĂ”NG CĂ“ GIĂ TRá» PHĂP LĂ",
            "legal_profile_id": "ND254_2026_TT91_2026",
            "legal_profile_version": "2026.07.01",
        },
    )


def mutate_invoice(base_invoice: CanonicalInvoice, seed: int, error_kind: str | None = None) -> CanonicalInvoice:
    """Táº¡o báº£n sao Ä‘á»™t biáº¿n lá»—i tá»« canonical valid gá»‘c mĂ  khĂ´ng lĂ m biáº¿n Ä‘á»•i báº£n gá»‘c (G4T-82)."""
    inv = copy.deepcopy(base_invoice)
    rng = random.Random(seed)
    all_kinds = [
        "invalid_tax_code",
        "invalid_vat_rate",
        "missing_buyer_name",
        "negative_qty",
        "non_tax_document",
    ]
    kind = error_kind or rng.choice(all_kinds)

    inv.document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"thtax-synthetic-invalid-{kind}-{seed}"))
    inv.extra["seed"] = seed
    inv.extra["scenario"] = "invalid_business"
    inv.extra["error_reason"] = kind

    if kind == "invalid_tax_code":
        inv.seller.tax_code = "12345"
        inv.extra["qa_label"] = "invalid_format"
    elif kind == "invalid_vat_rate":
        for line in inv.lines:
            line.vat_rate = Decimal("15")
        inv.extra["qa_label"] = "invalid_format"
    elif kind == "missing_buyer_name":
        inv.buyer.name = ""
        inv.extra["qa_label"] = "missing_required_field"
    elif kind == "negative_qty":
        inv.lines[0].quantity = Decimal("-2")
        inv.extra["qa_label"] = "inconsistent_totals"
    elif kind == "duplicate_reference":
        # TrĂ¹ng kĂ½ hiá»‡u vĂ  sá»‘ hĂ³a Ä‘Æ¡n vá»›i máº«u chuáº©n seed=42
        inv.series = "C26TAA"
        inv.invoice_number = "00000042"
        inv.extra["qa_label"] = "duplicate_reference"
    elif kind == "non_tax_document":
        inv.document_type = "non_tax_document"
        inv.form_number = ""
        inv.series = ""
        inv.seller.tax_code = ""
        inv.buyer.tax_code = ""
        inv.extra["qa_label"] = "non_tax_document"

    return inv


def create_sample_invoice(
    seed: int = 42,
    scenario: Literal["valid", "invalid_business"] = "valid",
    error_kind: str | None = None,
) -> CanonicalInvoice:
    base_inv = _build_valid_invoice(seed)
    if scenario == "valid":
        return base_inv
    return mutate_invoice(base_inv, seed=seed, error_kind=error_kind)
