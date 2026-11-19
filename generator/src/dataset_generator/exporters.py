import hashlib, json, os
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from .model import CanonicalInvoice

def money(v):
    return f"{int(v):,}".replace(",", ".")

def export_pdf(inv: CanonicalInvoice, path: Path):
    font_path = os.getenv("DATASET_FONT_PATH")
    candidates = [font_path, "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    chosen = next((p for p in candidates if p and Path(p).exists()), None)
    if not chosen:
        raise RuntimeError("Vietnamese TTF font not found. Set DATASET_FONT_PATH.")
    pdfmetrics.registerFont(TTFont("Vietnamese", chosen))
    styles = getSampleStyleSheet()
    title = ParagraphStyle("InvoiceTitle", parent=styles["Title"], fontName="Vietnamese", fontSize=16, leading=20, alignment=1)
    normal = ParagraphStyle("VN", parent=styles["BodyText"], fontName="Vietnamese", fontSize=8, leading=11)
    story = [Paragraph("HÓA ĐƠN GIÁ TRỊ GIA TĂNG", title),
             Paragraph("DỮ LIỆU GIẢ LẬP - KHÔNG CÓ GIÁ TRỊ PHÁP LÝ", ParagraphStyle("watermark", parent=normal, alignment=1, textColor=colors.red)),
             Spacer(1, 5*mm)]
    story += [Paragraph(f"<b>Mẫu số:</b> {inv.form_number} &nbsp;&nbsp; <b>Ký hiệu:</b> {inv.series} &nbsp;&nbsp; <b>Số:</b> {inv.invoice_number}", normal),
              Paragraph(f"<b>Ngày lập:</b> {inv.issue_date}", normal), Spacer(1, 3*mm),
              Paragraph(f"<b>Người bán:</b> {inv.seller.name}<br/><b>MST:</b> {inv.seller.tax_code}<br/><b>Địa chỉ:</b> {inv.seller.address}", normal),
              Spacer(1, 2*mm),
              Paragraph(f"<b>Người mua:</b> {inv.buyer.name}<br/><b>MST:</b> {inv.buyer.tax_code}<br/><b>Địa chỉ:</b> {inv.buyer.address}", normal),
              Spacer(1, 4*mm)]
    rows = [["STT", "Tên hàng hóa, dịch vụ", "ĐVT", "SL", "Đơn giá", "Thành tiền", "Thuế suất"]]
    for i, line in enumerate(inv.lines, 1):
        rows.append([str(i), line.name, line.unit, str(line.quantity), money(line.unit_price), money(line.amount), f"{line.vat_rate}%"])
    table = Table(rows, colWidths=[10*mm, 57*mm, 14*mm, 12*mm, 25*mm, 27*mm, 18*mm], repeatRows=1)
    table.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),"Vietnamese"),("FONTSIZE",(0,0),(-1,-1),7),
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e8edf3")),("GRID",(0,0),(-1,-1),0.4,colors.grey),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(0,0),(0,-1),"CENTER"),("ALIGN",(3,1),(-1,-1),"RIGHT"),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story += [table, Spacer(1, 4*mm),
        Paragraph(f"<b>Cộng tiền hàng:</b> {money(inv.subtotal)} VND", normal),
        Paragraph(f"<b>Tiền thuế GTGT:</b> {money(inv.vat_total)} VND", normal),
        Paragraph(f"<b>Tổng thanh toán:</b> {money(inv.grand_total)} VND", normal),
        Spacer(1, 12*mm), Paragraph("Người mua hàng                         Người bán hàng", normal)]
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    doc.build(story)

def write_bundle(inv: CanonicalInvoice, out_dir: Path, generator_version="0.1.0"):
    out_dir.mkdir(parents=True, exist_ok=True)
    canonical = out_dir / "canonical.json"
    canonical.write_text(json.dumps(inv.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    export_pdf(inv, out_dir / "invoice.pdf")
    gt = {"document_id": inv.document_id, "document_label": "valid_synthetic",
          "fields": {k: v for k, v in inv.to_dict().items() if k not in ("lines", "extra")},
          "line_items": inv.to_dict()["lines"]}
    (out_dir / "ground_truth.json").write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts = {}
    for p in out_dir.iterdir():
        if p.is_file() and p.name != "manifest.json":
            artifacts[p.name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
    manifest = {"dataset_id": out_dir.parent.name, "document_id": inv.document_id,
      "document_type": inv.document_type, "generator_version": generator_version,
      "xml_schema_version": None, "thtax_core_contract_version": None,
      "synthetic": True, "seed": inv.extra.get("seed"), "artifacts": artifacts,
      "validation_status": "valid_synthetic"}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
