import random
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal
from .model import CanonicalInvoice, InvoiceLine, Party

SELLERS = [
    (
        "CÔNG TY TNHH GIẢI PHÁP CÔNG NGHỆ MINH HỌA (DỮ LIỆU GIẢ LẬP)",
        "Số 123 Đường Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh",
        "9901234567",
        "19039988776601 - Ngân hàng TMCP Kỹ Thương Việt Nam (Techcombank)",
    ),
    (
        "CÔNG TY CỔ PHẦN THƯƠNG MẠI DỊCH VỤ DEMO VIỆT",
        "Tầng 8, Tòa nhà Thử Nghiệm, Phố Duy Tân, Quận Cầu Giấy, Hà Nội",
        "9902345678-001",
        "0011009988776 - Ngân hàng TMCP Ngoại Thương Việt Nam (Vietcombank)",
    ),
    (
        "CÔNG TY TNHH PHẦN MỀM MẪU THTAX",
        "Số 88 Đường Bạch Đằng, Quận Hải Châu, TP. Đà Nẵng",
        "9903456789",
        "112233445566 - Ngân hàng TMCP Công Thương Việt Nam (VietinBank)",
    ),
]

BUYERS = [
    (
        "CÔNG TY TNHH KHÁCH HÀNG DOANH NGHIỆP MẪU A",
        "Số 456 Đường Võ Văn Tần, Phường 5, Quận 3, TP. Hồ Chí Minh",
        "9911112222",
    ),
    (
        "CÔNG TY CỔ PHẦN ĐỐI TÁC KẾ TOÁN DEMO B",
        "Số 79 Đường Điện Biên Phủ, Quận Bình Thạnh, TP. Hồ Chí Minh",
        "9922223333",
    ),
    (
        "DOANH NGHIỆP TƯ NHÂN THỬ NGHIỆM C",
        "Số 12 Đường Xa Lộ Hà Nội, TP. Thủ Đức, TP. Hồ Chí Minh",
        "9933334444-002",
    ),
]

CATALOG = [
    ("Dịch vụ tư vấn giải pháp chuyển đổi số doanh nghiệp", "Gói", 5_000_000, 15_000_000),
    ("Bản quyền phần mềm quản lý hóa đơn điện tử (12 tháng)", "Năm", 2_500_000, 6_000_000),
    ("Dịch vụ lưu trữ và sao lưu dữ liệu đám mây", "Tháng", 1_500_000, 4_500_000),
    ("Thiết bị máy chủ lưu trữ chuyên dụng NAS", "Bộ", 12_000_000, 28_000_000),
    ("Dịch vụ bảo trì hệ thống hạ tầng mạng nội bộ", "Lần", 2_000_000, 5_000_000),
]

def create_sample_invoice(
    seed: int = 42,
    scenario: Literal["valid", "invalid_business"] = "valid",
) -> CanonicalInvoice:
    rng = random.Random(seed)
    seller_name, seller_addr, seller_tax, seller_bank = rng.choice(SELLERS)
    buyer_name, buyer_addr, buyer_tax = rng.choice(BUYERS)

    vat_rate = rng.choice([Decimal("0"), Decimal("5"), Decimal("8"), Decimal("10")])
    base_date = date(2026, 7, 1) + timedelta(days=rng.randint(0, 140))
    qa_label = "valid_synthetic"
    error_reason = None

    if scenario == "invalid_business":
        error_kind = rng.choice(["invalid_tax_code", "invalid_vat_rate", "missing_buyer_name", "negative_qty"])
        error_reason = error_kind
        if error_kind == "invalid_tax_code":
            seller_tax = "12345"
            qa_label = "invalid_format"
        elif error_kind == "invalid_vat_rate":
            vat_rate = Decimal("15")
            qa_label = "invalid_format"
        elif error_kind == "missing_buyer_name":
            buyer_name = ""
            qa_label = "missing_required_field"
        elif error_kind == "negative_qty":
            qa_label = "inconsistent_totals"

    chosen_items = rng.sample(CATALOG, k=rng.randint(2, 4))
    lines = []
    for idx, (name, unit, min_p, max_p) in enumerate(chosen_items):
        qty = Decimal(str(rng.randint(1, 5)))
        if scenario == "invalid_business" and error_reason == "negative_qty" and idx == 0:
            qty = Decimal("-2")
        unit_price = Decimal(str(rng.randrange(min_p, max_p, 100_000)))
        lines.append(InvoiceLine(name, unit, qty, unit_price, vat_rate))

    return CanonicalInvoice(
        document_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"thtax-synthetic-{scenario}-{seed}")),
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
            "scenario": scenario,
            "qa_label": qa_label,
            "error_reason": error_reason,
            "seller_bank_account": seller_bank,
            "payment_method": rng.choice(["TM/CK", "CK", "TM"]),
            "watermark": "DỮ LIỆU GIẢ LẬP - KHÔNG CÓ GIÁ TRỊ PHÁP LÝ",
            "legal_profile_id": "ND254_2026_TT91_2026",
            "legal_profile_version": "2026.07.01",
        },
    )