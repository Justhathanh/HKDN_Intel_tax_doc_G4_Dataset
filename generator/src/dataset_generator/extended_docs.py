import hashlib
import json
import mimetypes
import random
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .exporters import _register_fonts, export_images_and_scan_pdf, format_vn_date, money, number_to_vietnamese_words
from .factory import BUYERS, CATALOG, SELLERS
from .model import round_amount


@dataclass
class ExtendedDocument:
    document_id: str
    document_type: str
    title: str
    issue_date: str
    reference_code: str
    issuer_name: str
    issuer_tax_code: str
    issuer_address: str
    recipient_name: str
    recipient_tax_code: str
    recipient_address: str
    total_amount: Decimal
    currency: str = "VND"
    schema_verified: bool = False
    synthetic: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    items: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def conv(v):
            if isinstance(v, Decimal):
                return str(v)
            if isinstance(v, dict):
                return {k: conv(x) for k, x in v.items()}
            if isinstance(v, list):
                return [conv(x) for x in v]
            return v

        return conv(asdict(self))


def create_extended_document(doc_type: str, seed: int = 42) -> ExtendedDocument:
    rng = random.Random(seed)
    seller_name, seller_addr, seller_tax, _ = rng.choice(SELLERS)
    buyer_name, buyer_addr, buyer_tax = rng.choice(BUYERS)
    issue_dt = (date(2026, 7, 1) + timedelta(days=rng.randint(0, 140))).isoformat()
    doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"thtax-ext-{doc_type}-{seed}"))

    chosen = rng.sample(CATALOG, k=2)
    items = []
    subtotal = Decimal("0")
    for name, unit, min_p, max_p in chosen:
        qty = Decimal(str(rng.randint(1, 4)))
        price = Decimal(str(rng.randrange(min_p, max_p, 100_000)))
        amt = round_amount(qty * price)
        subtotal += amt
        items.append({"name": name, "unit": unit, "quantity": qty, "unit_price": price, "amount": amt})

    if doc_type == "sales_invoice":
        return ExtendedDocument(
            document_id=doc_id,
            document_type="sales_invoice",
            title="HÓA ĐƠN BÁN HÀNG",
            issue_date=issue_dt,
            reference_code=f"2C26TAA - {seed:08d}",
            issuer_name=seller_name,
            issuer_tax_code=seller_tax,
            issuer_address=seller_addr,
            recipient_name=buyer_name,
            recipient_tax_code=buyer_tax,
            recipient_address=buyer_addr,
            total_amount=subtotal,
            metadata={"form_number": "2", "series": "2C26TAA", "invoice_number": f"{seed:08d}", "tax_regime": "Trực tiếp trên doanh thu"},
            items=items,
        )

    if doc_type in ("adjustment_invoice", "replacement_invoice"):
        is_adj = doc_type == "adjustment_invoice"
        vat = round_amount(subtotal * Decimal("0.08"))
        total = subtotal + vat
        orig_num = f"{max(1, seed - 1):08d}"
        reason = (
            f"Điều chỉnh giảm đơn giá dịch vụ theo Biên bản thỏa thuận số BB-{seed}/2026"
            if is_adj
            else f"Thay thế cho hóa đơn điện tử Mẫu số 1, Ký hiệu C26TAA, Số {orig_num} lập sai thông tin địa chỉ"
        )
        return ExtendedDocument(
            document_id=doc_id,
            document_type=doc_type,
            title="HÓA ĐƠN GTGT ĐIỀU CHỈNH" if is_adj else "HÓA ĐƠN GTGT THAY THẾ",
            issue_date=issue_dt,
            reference_code=f"C26TAA - {seed:08d}",
            issuer_name=seller_name,
            issuer_tax_code=seller_tax,
            issuer_address=seller_addr,
            recipient_name=buyer_name,
            recipient_tax_code=buyer_tax,
            recipient_address=buyer_addr,
            total_amount=total,
            metadata={
                "form_number": "1",
                "series": "C26TAA",
                "invoice_number": f"{seed:08d}",
                "reference_invoice_number": orig_num,
                "reference_series": "C26TAA",
                "reason": reason,
                "subtotal": subtotal,
                "vat_amount": vat,
            },
            items=items,
        )

    if doc_type == "state_budget_payment":
        tax_amt = Decimal(str(rng.randrange(5_000_000, 30_000_000, 500_000)))
        return ExtendedDocument(
            document_id=doc_id,
            document_type="state_budget_payment",
            title="GIẤY NỘP TIỀN VÀO NGÂN SÁCH NHÀ NƯỚC",
            issue_date=issue_dt,
            reference_code=f"GNT-{seed:06d}",
            issuer_name="KHO BẠC NHÀ NƯỚC TP. HỒ CHÍ MINH (MẪU GIẢ LẬP)",
            issuer_tax_code="9900000001",
            issuer_address="Số 37 Nguyễn Huệ, Quận 1, TP. Hồ Chí Minh",
            recipient_name=buyer_name,
            recipient_tax_code=buyer_tax,
            recipient_address=buyer_addr,
            total_amount=tax_amt,
            metadata={"chapter_code": "754", "sub_item_code": "1701", "tax_period": "Q3/2026", "bank_name": "Vietcombank CN TP.HCM"},
            items=[{"name": "Thuế Giá trị gia tăng hàng sản xuất kinh doanh trong nước", "unit": "Kỳ", "quantity": Decimal("1"), "unit_price": tax_amt, "amount": tax_amt}],
        )

    if doc_type == "tax_notice":
        due_amt = Decimal(str(rng.randrange(2_000_000, 15_000_000, 200_000)))
        return ExtendedDocument(
            document_id=doc_id,
            document_type="tax_notice",
            title="THÔNG BÁO VỀ VIỆC NỘP TIỀN THUẾ VÀ TIỀN CHẬM NỘP",
            issue_date=issue_dt,
            reference_code=f"TB-{seed}/CCT-QLN",
            issuer_name="CHI CỤC THUẾ KHU VỰC MẪU (DỮ LIỆU GIẢ LẬP)",
            issuer_tax_code="9900000002",
            issuer_address="Quận 1, TP. Hồ Chí Minh",
            recipient_name=buyer_name,
            recipient_tax_code=buyer_tax,
            recipient_address=buyer_addr,
            total_amount=due_amt,
            metadata={"deadline_date": "2026-12-31", "notice_type": "Thông báo tiền thuế nợ"},
            items=[{"name": "Tiền thuế TNDN tạm nộp theo tờ khai mẫu", "unit": "Khoản", "quantity": Decimal("1"), "unit_price": due_amt, "amount": due_amt}],
        )

    if doc_type == "fee_receipt":
        fee_amt = Decimal("500000")
        return ExtendedDocument(
            document_id=doc_id,
            document_type="fee_receipt",
            title="BIÊN LAI THU TIỀN PHÍ, LỆ PHÍ",
            issue_date=issue_dt,
            reference_code=f"BL26P - {seed:07d}",
            issuer_name="TRUNG TÂM PHỤC VỤ HÀNH CHÍNH CÔNG MẪU",
            issuer_tax_code="9900000003",
            issuer_address="TP. Hồ Chí Minh",
            recipient_name=buyer_name,
            recipient_tax_code=buyer_tax,
            recipient_address=buyer_addr,
            total_amount=fee_amt,
            metadata={"serial": "BL26P", "receipt_number": f"{seed:07d}"},
            items=[{"name": "Lệ phí cấp giấy chứng nhận đăng ký kinh doanh (Mẫu)", "unit": "Lần", "quantity": Decimal("1"), "unit_price": fee_amt, "amount": fee_amt}],
        )

    if doc_type == "pit_withholding":
        income = Decimal("35000000")
        tax_withheld = Decimal("3500000")
        return ExtendedDocument(
            document_id=doc_id,
            document_type="pit_withholding",
            title="CHỨNG TỪ KHẤU TRỪ THUẾ THU NHẬP CÁ NHÂN",
            issue_date=issue_dt,
            reference_code=f"CT26T - {seed:07d}",
            issuer_name=seller_name,
            issuer_tax_code=seller_tax,
            issuer_address=seller_addr,
            recipient_name="NGUYỄN VĂN MẪU (CÁ NHÂN GIẢ LẬP)",
            recipient_tax_code="9988776655",
            recipient_address="Quận Bình Thạnh, TP. Hồ Chí Minh",
            total_amount=tax_withheld,
            metadata={"serial": "CT26T", "certificate_number": f"{seed:07d}", "taxable_income": income, "withheld_tax": tax_withheld, "income_period": "Tháng 10/2026"},
            items=[{"name": "Thu nhập từ tiền lương, tiền công (Khấu trừ 10%)", "unit": "Tháng", "quantity": Decimal("1"), "unit_price": income, "amount": tax_withheld}],
        )

    # Mặc định: non_tax_document (Phiếu thu / Biên nhận nội bộ không liên quan thuế)
    return ExtendedDocument(
        document_id=doc_id,
        document_type="non_tax_document",
        title="PHIẾU GIAO NHẬN & BIÊN NHẬN THANH TOÁN NỘI BỘ",
        issue_date=issue_dt,
        reference_code=f"NB-{seed:05d}",
        issuer_name="CỬA HÀNG VĂN PHÒNG PHẨM NỘI BỘ DEMO",
        issuer_tax_code="",
        issuer_address="Số 10 Đường Nội Bộ, TP. Hồ Chí Minh",
        recipient_name="Phòng Hành chính - Nhân sự (Mẫu)",
        recipient_tax_code="",
        recipient_address="Tầng 2, Tòa nhà Văn phòng Mẫu",
        total_amount=subtotal,
        metadata={"note": "Chứng từ nội bộ không có giá trị kê khai thuế"},
        items=items,
    )


def render_extended_pdf(doc: ExtendedDocument, path: Path):
    reg_font, bold_font = _register_fonts()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ExtTitle", parent=styles["Title"], fontName=bold_font, fontSize=13, leading=17, alignment=1, textColor=colors.HexColor("#1a365d"))
    wm_style = ParagraphStyle("ExtWM", parent=styles["BodyText"], fontName=bold_font, fontSize=8, leading=11, alignment=1, textColor=colors.red)
    normal = ParagraphStyle("ExtNorm", parent=styles["BodyText"], fontName=reg_font, fontSize=8.5, leading=12)
    cell_l = ParagraphStyle("ExtCellL", parent=normal, fontSize=8, leading=10, alignment=0)
    cell_c = ParagraphStyle("ExtCellC", parent=normal, fontSize=8, leading=10, alignment=1)
    cell_r = ParagraphStyle("ExtCellR", parent=normal, fontSize=8, leading=10, alignment=2)

    story = [
        Paragraph(f"<b>{doc.title}</b>", title_style),
        Paragraph(f"<i>{format_vn_date(doc.issue_date)} &nbsp;|&nbsp; Số tham chiếu: {doc.reference_code}</i>", cell_c),
        Spacer(1, 2 * mm),
        Paragraph("DỮ LIỆU GIẢ LẬP - MẪU THAM CHIẾU CHƯA XÁC MINH SCHEMA PHÁP LÝ", wm_style),
        Spacer(1, 3 * mm),
    ]

    # Khối tham chiếu riêng cho Hóa đơn điều chỉnh / thay thế
    if doc.document_type in ("adjustment_invoice", "replacement_invoice"):
        ref_box = Table(
            [[Paragraph(f"<b>Thông tin tham chiếu hóa đơn gốc:</b> {doc.metadata.get('reason', '')}", normal)]],
            colWidths=[180 * mm],
        )
        ref_box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#dd6b20")), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffaf0")), ("PADDING", (0, 0), (-1, -1), 5)]))
        story.extend([ref_box, Spacer(1, 3 * mm)])

    # Thông tin các bên
    tax_issuer = f"<b>Mã số thuế:</b> {doc.issuer_tax_code}<br/>" if doc.issuer_tax_code else ""
    tax_recip = f"<b>Mã số thuế:</b> {doc.recipient_tax_code}<br/>" if doc.recipient_tax_code else ""
    meta_line = ""
    if doc.document_type == "state_budget_payment":
        meta_line = f"<br/><b>Chương:</b> {doc.metadata['chapter_code']} &nbsp;|&nbsp; <b>Tiểu mục:</b> {doc.metadata['sub_item_code']} &nbsp;|&nbsp; <b>Kỳ thuế:</b> {doc.metadata['tax_period']}"
    elif doc.document_type == "pit_withholding":
        meta_line = f"<br/><b>Tổng thu nhập chịu thuế:</b> {money(doc.metadata['taxable_income'])} VND &nbsp;|&nbsp; <b>Kỳ trả thu nhập:</b> {doc.metadata['income_period']}"

    party_tbl = Table(
        [
            [Paragraph(f"<b>Đơn vị phát hành / Người bán:</b> {doc.issuer_name}<br/>{tax_issuer}<b>Địa chỉ:</b> {doc.issuer_address}", normal)],
            [Paragraph(f"<b>Đơn vị nhận / Người nộp / Người mua:</b> {doc.recipient_name}<br/>{tax_recip}<b>Địa chỉ:</b> {doc.recipient_address}{meta_line}", normal)],
        ],
        colWidths=[180 * mm],
    )
    party_tbl.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#718096")), ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e0")), ("PADDING", (0, 0), (-1, -1), 5)]))
    story.extend([party_tbl, Spacer(1, 3 * mm)])

    # Bảng nội dung chi tiết (6 cột, không tách VAT như hóa đơn GTGT)
    rows = [["STT", "Nội dung hàng hóa, dịch vụ / khoản nộp", "ĐVT", "SL", "Đơn giá / Mức thu", "Thành tiền"]]
    for idx, it in enumerate(doc.items, 1):
        rows.append([
            Paragraph(str(idx), cell_c),
            Paragraph(it["name"], cell_l),
            Paragraph(it["unit"], cell_c),
            Paragraph(str(it["quantity"]), cell_r),
            Paragraph(money(it["unit_price"]), cell_r),
            Paragraph(money(it["amount"]), cell_r),
        ])
    rows.append(["", "Tổng cộng:", "", "", "", Paragraph(f"<b>{money(doc.total_amount)}</b>", cell_r)])

    tbl = Table(rows, colWidths=[12 * mm, 76 * mm, 16 * mm, 14 * mm, 30 * mm, 32 * mm], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), reg_font),
        ("FONTNAME", (0, 0), (-1, 0), bold_font),
        ("FONTNAME", (0, -1), (-1, -1), bold_font),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf2f7")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#718096")),
        ("SPAN", (0, -1), (4, -1)),
        ("ALIGN", (0, -1), (4, -1), "RIGHT"),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([tbl, Spacer(1, 3 * mm)])

    words = number_to_vietnamese_words(int(doc.total_amount))
    story.append(Paragraph(f"<b>Số tiền viết bằng chữ:</b> <i>{words}</i>", normal))

    pdf_doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    pdf_doc.build(story)


def write_extended_bundle(doc: ExtendedDocument, out_dir: Path, seed: int = 42, generator_version: str = "0.2.0"):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "canonical.json").write_text(json.dumps(doc.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    pdf_path = out_dir / "document.pdf"
    render_extended_pdf(doc, pdf_path)
    export_images_and_scan_pdf(pdf_path, out_dir, seed=seed)

    gt = {
        "document_id": doc.document_id,
        "document_type": doc.document_type,
        "document_label": "reference_unverified_synthetic",
        "schema_verified": False,
        "fields": {
            "reference_code": {"displayed": doc.reference_code, "normalized": doc.reference_code, "present": True},
            "issue_date": {"displayed": format_vn_date(doc.issue_date), "normalized": doc.issue_date, "present": True},
            "issuer.name": {"displayed": doc.issuer_name, "normalized": doc.issuer_name, "present": bool(doc.issuer_name)},
            "issuer.tax_code": {"displayed": doc.issuer_tax_code, "normalized": doc.issuer_tax_code, "present": bool(doc.issuer_tax_code)},
            "recipient.name": {"displayed": doc.recipient_name, "normalized": doc.recipient_name, "present": bool(doc.recipient_name)},
            "totals.total_amount": {"displayed": money(doc.total_amount), "normalized": str(doc.total_amount), "present": True},
        },
        "line_items": doc.to_dict()["items"],
        "relationships": {
            key: doc.to_dict()["metadata"][key]
            for key in ("scenario_id", "role", "references_document_id", "reference_invoice_number", "reference_series", "scenario_expected", "adjustment_direction", "adjustment_delta_signed")
            if key in doc.metadata
        },
    }
    (out_dir / "ground_truth.json").write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")

    artifacts = {}
    for p in sorted(out_dir.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rel_path = p.relative_to(out_dir).as_posix()
            mime, _ = mimetypes.guess_type(p.name)
            artifacts[rel_path] = {
                "mime_type": mime or "application/octet-stream",
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "bytes": p.stat().st_size,
            }

    manifest = {
        "dataset_id": out_dir.parent.parent.name if out_dir.parent.name == "documents" else out_dir.parent.name,
        "document_id": doc.document_id,
        "document_type": doc.document_type,
        "generator_version": generator_version,
        "schema_verified": False,
        "xml_schema_version": None,
        "thtax_core_contract_version": "1.0.0",
        "synthetic": True,
        "seed": seed,
        "artifacts": artifacts,
        "validation_status": "reference_unverified_synthetic",
        "validation_errors": [],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")