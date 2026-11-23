from dataclasses import dataclass, field
from typing import Dict, List, Literal

SupportStatus = Literal["planned", "in_progress", "supported", "unsupported", "needs_review"]


@dataclass(frozen=True)
class DocumentTypeSpec:
    type_key: str
    display_name: str
    category: str
    description: str
    status: SupportStatus
    in_mvp: bool
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    conditional_fields: List[str] = field(default_factory=list)


DOCUMENT_TYPE_REGISTRY: Dict[str, DocumentTypeSpec] = {
    "vat_invoice": DocumentTypeSpec(
        type_key="vat_invoice",
        display_name="Hóa đơn Giá trị gia tăng",
        category="tax_invoice",
        description="Hóa đơn GTGT điện tử theo NĐ 254/2026/NĐ-CP và TT 91/2026/TT-BTC.",
        status="supported",
        in_mvp=True,
        required_fields=["template_code", "serial", "invoice_number", "issue_date", "seller", "buyer", "items", "subtotal", "vat_amount", "grand_total", "currency"],
        optional_fields=["payment_method", "buyer_email", "note"],
        conditional_fields=["buyer_tax_code", "vat_breakdown_by_rate"],
    ),
    "sales_invoice": DocumentTypeSpec(
        type_key="sales_invoice",
        display_name="Hóa đơn Bán hàng",
        category="tax_invoice",
        description="Hóa đơn bán hàng dành cho đối tượng tính thuế trực tiếp (không tách dòng thuế GTGT).",
        status="needs_review",
        in_mvp=False,
        required_fields=["template_code", "serial", "invoice_number", "issue_date", "seller", "items", "grand_total"],
        optional_fields=["buyer", "payment_method"],
        conditional_fields=["buyer_tax_code"],
    ),
    "adjustment_invoice": DocumentTypeSpec(
        type_key="adjustment_invoice",
        display_name="Hóa đơn Điều chỉnh",
        category="tax_invoice",
        description="Hóa đơn điều chỉnh tăng/giảm thông tin hoặc số tiền của hóa đơn gốc.",
        status="needs_review",
        in_mvp=False,
        required_fields=["reference_invoice", "adjustment_reason", "issue_date", "seller", "buyer", "items", "grand_total"],
        optional_fields=["note"],
        conditional_fields=["vat_amount"],
    ),
    "replacement_invoice": DocumentTypeSpec(
        type_key="replacement_invoice",
        display_name="Hóa đơn Thay thế",
        category="tax_invoice",
        description="Hóa đơn phát hành thay thế toàn bộ cho hóa đơn gốc đã lập sai.",
        status="needs_review",
        in_mvp=False,
        required_fields=["reference_invoice", "replacement_reason", "issue_date", "seller", "buyer", "items", "grand_total"],
        optional_fields=["note"],
        conditional_fields=["vat_amount"],
    ),
    "state_budget_payment": DocumentTypeSpec(
        type_key="state_budget_payment",
        display_name="Giấy nộp tiền vào Ngân sách Nhà nước",
        category="tax_payment",
        description="Chứng từ xác nhận nộp thuế/phí vào NSNN qua ngân hàng hoặc Kho bạc.",
        status="needs_review",
        in_mvp=False,
        required_fields=["taxpayer_name", "taxpayer_tax_code", "payment_date", "treasury_account", "amount"],
        optional_fields=["collecting_agency", "chapter_code", "sub_item_code"],
        conditional_fields=["decision_number"],
    ),
    "tax_notice": DocumentTypeSpec(
        type_key="tax_notice",
        display_name="Thông báo thuế",
        category="tax_administration",
        description="Thông báo của cơ quan thuế gửi người nộp thuế (tiền thuế, tiền chậm nộp, nghĩa vụ kê khai).",
        status="needs_review",
        in_mvp=False,
        required_fields=["notice_number", "notice_date", "issuing_tax_authority", "taxpayer_tax_code", "content"],
        optional_fields=["deadline_date"],
        conditional_fields=["payable_amount"],
    ),
    "fee_receipt": DocumentTypeSpec(
        type_key="fee_receipt",
        display_name="Biên lai thu phí, lệ phí",
        category="receipt",
        description="Biên lai thu các khoản phí, lệ phí thuộc ngân sách nhà nước.",
        status="needs_review",
        in_mvp=False,
        required_fields=["template_code", "serial", "receipt_number", "issue_date", "collector_name", "payer_name", "amount"],
        optional_fields=["payer_address"],
        conditional_fields=["payer_tax_code"],
    ),
    "pit_withholding": DocumentTypeSpec(
        type_key="pit_withholding",
        display_name="Chứng từ khấu trừ thuế TNCN",
        category="withholding_certificate",
        description="Chứng từ xác nhận số thuế thu nhập cá nhân đã khấu trừ của tổ chức trả thu nhập.",
        status="needs_review",
        in_mvp=False,
        required_fields=["serial", "certificate_number", "issue_date", "withholding_org", "individual_name", "taxable_income", "withheld_tax"],
        optional_fields=["individual_address"],
        conditional_fields=["individual_tax_code", "citizen_id"],
    ),
    "non_tax_document": DocumentTypeSpec(
        type_key="non_tax_document",
        display_name="Tài liệu không liên quan đến thuế",
        category="non_tax",
        description="Phiếu thu nội bộ, biên nhận bán lẻ hoặc tài liệu hành chính dùng làm mẫu đối chứng negative.",
        status="planned",
        in_mvp=False,
        required_fields=["document_title", "content"],
        optional_fields=["issue_date", "amount"],
        conditional_fields=[],
    ),
}


def get_document_type(type_key: str) -> DocumentTypeSpec:
    if type_key not in DOCUMENT_TYPE_REGISTRY:
        raise KeyError(f"Unsupported or unknown document type_key: '{type_key}'")
    return DOCUMENT_TYPE_REGISTRY[type_key]