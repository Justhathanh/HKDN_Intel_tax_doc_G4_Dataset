import hashlib
import io
import json
import mimetypes
import os
import random
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from .model import CanonicalInvoice

def money(v: Decimal | int) -> str:
    return f"{int(v):,}".replace(",", ".")

def format_vn_date(iso_date: str) -> str:
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return f"Ngày {dt.day:02d} tháng {dt.month:02d} năm {dt.year}"
    except ValueError:
        return iso_date

def number_to_vietnamese_words(n: int) -> str:
    """Chuyển số tiền nguyên sang chữ tiếng Việt chuẩn kế toán hóa đơn."""
    if n == 0:
        return "Không đồng"
    if n < 0:
        return "Âm " + number_to_vietnamese_words(abs(n)).lower()
    units = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ"]
    digits = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]

    def read_triple(num: int, full: bool) -> str:
        h = num // 100
        t = (num % 100) // 10
        u = num % 10
        res = []
        if h > 0 or full:
            res.append(digits[h] + " trăm")
        if t > 1:
            res.append(digits[t] + " mươi")
            if u == 1:
                res.append("mốt")
            elif u == 5:
                res.append("lăm")
            elif u > 0:
                res.append(digits[u])
        elif t == 1:
            res.append("mười")
            if u == 5:
                res.append("lăm")
            elif u > 0:
                res.append(digits[u])
        elif t == 0 and u > 0:
            if h > 0 or full:
                res.append("lẻ")
            res.append(digits[u])
        return " ".join(res)

    groups = []
    temp = n
    while temp > 0:
        groups.append(temp % 1000)
        temp //= 1000

    parts = []
    for idx in range(len(groups) - 1, -1, -1):
        g = groups[idx]
        if g > 0:
            part = read_triple(g, full=(idx < len(groups) - 1))
            if units[idx]:
                part += " " + units[idx]
            parts.append(part)
    sentence = " ".join(parts).strip()
    return sentence[0].upper() + sentence[1:] + " đồng./."

def _register_fonts() -> tuple[str, str]:
    font_path = os.getenv("DATASET_FONT_PATH")
    regular_candidates = [font_path, "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    bold_candidates = ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]

    reg = next((p for p in regular_candidates if p and Path(p).exists()), None)
    if not reg:
        raise RuntimeError("Vietnamese TTF font not found. Set DATASET_FONT_PATH.")
    bold = next((p for p in bold_candidates if p and Path(p).exists()), reg)

    pdfmetrics.registerFont(TTFont("VNRegular", reg))
    pdfmetrics.registerFont(TTFont("VNBold", bold))
    return "VNRegular", "VNBold"

def export_pdf(inv: CanonicalInvoice, path: Path):
    reg_font, bold_font = _register_fonts()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("InvTitle", parent=styles["Title"], fontName=bold_font, fontSize=14, leading=18, alignment=1, textColor=colors.HexColor("#1a365d"))
    subtitle_style = ParagraphStyle("InvSub", parent=styles["BodyText"], fontName=reg_font, fontSize=8.5, leading=11, alignment=1)
    wm_style = ParagraphStyle("Watermark", parent=styles["BodyText"], fontName=bold_font, fontSize=8.5, leading=11, alignment=1, textColor=colors.red)
    normal = ParagraphStyle("VNNormal", parent=styles["BodyText"], fontName=reg_font, fontSize=8, leading=11.5)
    small = ParagraphStyle("VNSmall", parent=styles["BodyText"], fontName=reg_font, fontSize=7.5, leading=10)

    story = []

    # 1. Header chuẩn Hóa đơn GTGT Việt Nam (3 cột: Logo/Tên | Tiêu đề + Ngày | Mẫu số - Ký hiệu - Số)
    header_data = [
        [
            Paragraph("<b>THTAX DEMO</b><br/><font size=7>Mẫu hóa đơn điện tử<br/>NĐ 254/2026/NĐ-CP</font>", small),
            Paragraph(
                f"<b>HÓA ĐƠN GIÁ TRỊ GIA TĂNG</b><br/>"
                f"<font size=7.5><i>(Bản thể hiện của hóa đơn điện tử)</i></font><br/>"
                f"<font size=8>{format_vn_date(inv.issue_date)}</font>",
                title_style,
            ),
            Paragraph(
                f"<b>Mẫu số:</b> {inv.form_number}<br/>"
                f"<b>Ký hiệu:</b> {inv.series}<br/>"
                f"<b>Số:</b> <font color='#c53030'><b>{inv.invoice_number}</b></font>",
                normal,
            ),
        ]
    ]
    header_table = Table(header_data, colWidths=[35 * mm, 105 * mm, 40 * mm])
    header_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), reg_font),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#2b6cb0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7fafc")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("DỮ LIỆU GIẢ LẬP - KHÔNG CÓ GIÁ TRỊ PHÁP LÝ", wm_style))
    story.append(Spacer(1, 2 * mm))

    # 2. Khối thông tin Người bán & Người mua (2 cột: Người bán | Người mua)
    bank_info = inv.extra.get("seller_bank_account", "")
    pay_method = inv.extra.get("payment_method", "TM/CK")
    party_data = [
        [
            Paragraph(
                f"<b>Đơn vị bán hàng:</b> {inv.seller.name}<br/>"
                f"<b>Mã số thuế:</b> {inv.seller.tax_code}<br/>"
                f"<b>Địa chỉ:</b> {inv.seller.address}<br/>"
                f"<b>Số tài khoản:</b> {bank_info}",
                normal,
            )
        ],
        [
            Paragraph(
                f"<b>Tên đơn vị mua hàng:</b> {inv.buyer.name}<br/>"
                f"<b>Mã số thuế:</b> {inv.buyer.tax_code}<br/>"
                f"<b>Địa chỉ:</b> {inv.buyer.address}<br/>"
                f"<b>Hình thức thanh toán:</b> {pay_method} &nbsp;&nbsp;&nbsp;&nbsp; <b>Đơn vị tiền tệ:</b> {inv.currency}",
                normal,
            )
        ],
    ]
    party_table = Table(party_data, colWidths=[180 * mm])
    party_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), reg_font),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#718096")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(party_table)
    story.append(Spacer(1, 3 * mm))

    # 3. Bảng chi tiết hàng hóa, dịch vụ (9 cột: STT | Tên hàng | ĐVT | SL | Đơn giá | Thành tiền chưa thuế | Thuế suất | Tiền thuế GTGT | Tổng tiền thanh toán)
    
    cell_left = ParagraphStyle("CellLeft", parent=normal, fontSize=7, leading=9.5, alignment=0)
    cell_center = ParagraphStyle("CellCenter", parent=normal, fontSize=7, leading=9.5, alignment=1)
    cell_right = ParagraphStyle("CellRight", parent=normal, fontSize=7, leading=9.5, alignment=2)

    rows = [[
        "STT", "Tên hàng hóa, dịch vụ", "ĐVT", "SL", "Đơn giá",
        "Thành tiền\nchưa thuế", "Thuế\nsuất", "Tiền thuế\nGTGT", "Tổng tiền\nthanh toán"
    ]]
    for i, line in enumerate(inv.lines, 1):
        line_total = line.amount + line.vat_amount
        rows.append([
            Paragraph(str(i), cell_center),
            Paragraph(line.name, cell_left),
            Paragraph(line.unit, cell_center),
            Paragraph(str(line.quantity), cell_right),
            Paragraph(money(line.unit_price), cell_right),
            Paragraph(money(line.amount), cell_right),
            Paragraph(f"{int(line.vat_rate)}%", cell_center),
            Paragraph(money(line.vat_amount), cell_right),
            Paragraph(money(line_total), cell_right),
        ])
    rows.append([
        "", "Tổng cộng tiền thanh toán:", "", "", "",
        Paragraph(f"<b>{money(inv.subtotal)}</b>", cell_right),
        "",
        Paragraph(f"<b>{money(inv.vat_total)}</b>", cell_right),
        Paragraph(f"<b>{money(inv.grand_total)}</b>", cell_right),
    ])

    col_widths = [9 * mm, 47 * mm, 12 * mm, 10 * mm, 21 * mm, 23 * mm, 12 * mm, 21 * mm, 25 * mm]
    items_table = Table(rows, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), reg_font),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("FONTNAME", (0, -1), (-1, -1), bold_font),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ebf4ff")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f7fafc")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#718096")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("SPAN", (0, -1), (4, -1)),
                ("ALIGN", (0, -1), (4, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 3 * mm))

    # 4. Số tiền viết bằng chữ & Khối chữ ký điện tử giả lập
    amount_words = number_to_vietnamese_words(int(inv.grand_total))
    story.append(Paragraph(f"<b>Số tiền viết bằng chữ:</b> <i>{amount_words}</i>", normal))
    story.append(Spacer(1, 6 * mm))

    sign_data = [
        [
            Paragraph("<b>Người mua hàng</b><br/><i>(Ký, ghi rõ họ tên)</i>", subtitle_style),
            Paragraph(
                "<b>Người bán hàng</b><br/><i>(Ký, đóng dấu, ghi rõ họ tên)</i><br/><br/>"
                "<font color='#c53030' size=7>[MẪU CHỮ KÝ SỐ GIẢ LẬP - KHÔNG CÓ GIÁ TRỊ PHÁP LÝ]<br/>"
                f"Ký bởi: {inv.seller.name}</font>",
                subtitle_style,
            ),
        ]
    ]
    sign_table = Table(sign_data, colWidths=[85 * mm, 95 * mm])
    sign_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sign_table)

    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    doc.build(story)

def export_images_and_scan_pdf(pdf_path: Path, out_dir: Path, seed: int = 42):
    """Xuất ảnh vào thư mục con images/ theo đúng DATASET_SPEC.md và tạo PDF scan."""
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap(dpi=200)
    clean_img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    doc.close()

    # 1. Ảnh nét chuẩn theo DATASET_SPEC.md
    clean_img.save(images_dir / "page-001.png", format="PNG")

    # 2. Ảnh mờ/xoay nghiêng/nhiễu
    angle = rng.uniform(-3.0, 3.0)
    degraded = clean_img.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=(245, 245, 245))
    degraded = degraded.filter(ImageFilter.GaussianBlur(radius=0.85))
    arr = np.array(degraded, dtype=np.int16)
    noise = np_rng.normal(0, 7, arr.shape).astype(np.int16)
    degraded = Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))

    blur_jpg_path = images_dir / "page-001_blur.jpg"
    degraded.save(blur_jpg_path, format="JPEG", quality=75)

    # 3. Đóng gói ảnh degraded thành PDF scan (không có text layer)
    degraded.save(out_dir / "invoice_scan.pdf", format="PDF", resolution=150.0)

def _build_manifest(
    out_dir: Path,
    document_id: str,
    document_type: str,
    validation_status: str,
    seed: int | None,
    generator_version: str,
    validation_errors: list[str] | None = None,
):
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
        "dataset_id": out_dir.parent.name,
        "document_id": document_id,
        "document_type": document_type,
        "generator_version": generator_version,
        "legal_profile_id": "ND254_2026_TT91_2026",
        "legal_profile_version": "2026.07.01",
        "xml_schema_version": None,
        "thtax_core_contract_version": "1.0.0",
        "synthetic": True,
        "seed": seed,
        "artifacts": artifacts,
        "validation_status": validation_status,
        "validation_errors": validation_errors or [],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

def write_bundle(inv: CanonicalInvoice, out_dir: Path, generator_version="0.2.0", validation_errors: list[str] | None = None):
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = inv.extra.get("seed", 42)
    qa_label = inv.extra.get("qa_label", "valid_synthetic") if validation_errors else "valid_synthetic"

    canonical = out_dir / "canonical.json"
    canonical.write_text(json.dumps(inv.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    pdf_path = out_dir / "invoice.pdf"
    export_pdf(inv, pdf_path)
    export_images_and_scan_pdf(pdf_path, out_dir, seed=seed)

    # Ground Truth chuẩn DATASET_SPEC.md: lưu cả giá trị hiển thị lẫn giá trị chuẩn hóa
    gt_fields = {
        "form_number": {"displayed": inv.form_number, "normalized": inv.form_number, "present": True},
        "series": {"displayed": inv.series, "normalized": inv.series, "present": True},
        "invoice_number": {"displayed": inv.invoice_number, "normalized": inv.invoice_number, "present": True},
        "issue_date": {"displayed": format_vn_date(inv.issue_date), "normalized": inv.issue_date, "present": True},
        "seller.name": {"displayed": inv.seller.name, "normalized": inv.seller.name, "present": bool(inv.seller.name)},
        "seller.tax_code": {"displayed": inv.seller.tax_code, "normalized": inv.seller.tax_code, "present": bool(inv.seller.tax_code)},
        "seller.address": {"displayed": inv.seller.address, "normalized": inv.seller.address, "present": bool(inv.seller.address)},
        "buyer.name": {"displayed": inv.buyer.name, "normalized": inv.buyer.name, "present": bool(inv.buyer.name)},
        "buyer.tax_code": {"displayed": inv.buyer.tax_code, "normalized": inv.buyer.tax_code, "present": bool(inv.buyer.tax_code)},
        "buyer.address": {"displayed": inv.buyer.address, "normalized": inv.buyer.address, "present": bool(inv.buyer.address)},
        "totals.subtotal": {"displayed": money(inv.subtotal), "normalized": str(inv.subtotal), "present": True},
        "totals.vat_total": {"displayed": money(inv.vat_total), "normalized": str(inv.vat_total), "present": True},
        "totals.grand_total": {"displayed": money(inv.grand_total), "normalized": str(inv.grand_total), "present": True},
    }

    gt = {
        "document_id": inv.document_id,
        "document_label": qa_label,
        "expected_validation_errors": validation_errors or [],
        "fields": gt_fields,
        "line_items": inv.to_dict()["lines"],
    }
    (out_dir / "ground_truth.json").write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
    _build_manifest(out_dir, inv.document_id, inv.document_type, qa_label, seed, generator_version, validation_errors)

def write_corrupted_bundle(out_dir: Path, case_name: str, generator_version="0.2.0"):
    """Sinh các mẫu lỗi định dạng (0-byte, sai magic bytes, XML hỏng) theo DATASET_SPEC.md."""
    out_dir.mkdir(parents=True, exist_ok=True)
    doc_id = f"corrupted-{case_name}"

    if case_name == "empty_pdf":
        (out_dir / "corrupted_empty.pdf").write_bytes(b"")
        expected_error = "EMPTY_FILE"
    elif case_name == "fake_pdf_text":
        (out_dir / "corrupted_fake.pdf").write_text("DỮ LIỆU GIẢ LẬP - NOT A REAL PDF HEADER", encoding="utf-8")
        expected_error = "INVALID_MIME_OR_HEADER"
    else:
        (out_dir / "corrupted_malformed.xml").write_text("<HDon><DLHDon><TTChung>UNCLOSED_TAG", encoding="utf-8")
        expected_error = "XML_SYNTAX_ERROR"

    gt = {
        "document_id": doc_id,
        "document_label": "invalid_format",
        "expected_error_code": expected_error,
        "fields": {},
        "line_items": [],
    }
    (out_dir / "ground_truth.json").write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
    _build_manifest(out_dir, doc_id, "corrupted_document", "invalid_format", None, generator_version, [expected_error])