import random
import uuid
from decimal import Decimal
from .model import CanonicalInvoice, InvoiceLine, Party

def create_sample_invoice(seed: int = 42) -> CanonicalInvoice:
    rng = random.Random(seed)
    lines = [
        InvoiceLine("Dịch vụ tư vấn quản lý", "Lần", Decimal("1"), Decimal(rng.randrange(2_000_000, 8_000_000)), Decimal("10")),
        InvoiceLine("Phí triển khai phần mềm", "Gói", Decimal("2"), Decimal(rng.randrange(1_000_000, 3_000_000)), Decimal("10")),
    ]
    return CanonicalInvoice(
        document_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"thtax-synthetic-{seed}")),
        document_type="vat_invoice",
        issue_date="2026-11-20",
        form_number="1",
        series="C26TAA",
        invoice_number=f"{seed:08d}",
        seller=Party("CÔNG TY TNHH MINH HỌA (DỮ LIỆU GIẢ LẬP)", "123 Đường Mẫu, Phường Thử Nghiệm, TP. Hồ Chí Minh", "0000000000"),
        buyer=Party("CÔNG TY CỔ PHẦN KHÁCH HÀNG MẪU", "456 Đường Dữ Liệu, TP. Hồ Chí Minh", "1111111111"),
        lines=lines,
        extra={"seed": seed, "dataset_label": "valid_synthetic"}
    )
