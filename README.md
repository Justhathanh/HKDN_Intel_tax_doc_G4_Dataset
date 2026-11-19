# THTAX Synthetic Tax Invoice Dataset Generator

Repository tạo **hóa đơn điện tử giả lập có bố cục gần với chứng từ thực tế** để kiểm thử pipeline THTAX: upload, classification, PDF text extraction, OCR, XML parsing và field extraction.

> **Synthetic test data only.** Mọi PDF/ảnh/HTML đầu ra phải có watermark “DỮ LIỆU GIẢ LẬP - KHÔNG CÓ GIÁ TRỊ PHÁP LÝ”. Không tạo chữ ký số hợp lệ, mã xác thực/cấp mã của cơ quan thuế hoặc dữ liệu định danh thật.

## Mục tiêu MVP

1. Sinh dữ liệu hóa đơn GTGT giả lập nhất quán từ một Canonical Invoice Model.
2. Render hóa đơn thành PDF có bố cục chuyên nghiệp: thông tin người bán/người mua, thông tin hóa đơn, bảng hàng hóa, thuế và tổng thanh toán.
3. Sinh Ground Truth JSON và manifest liên kết với đúng hóa đơn.
4. Đối chiếu field với THTAX Core qua mapping riêng; không trộn metadata nội bộ THTAX vào nội dung hóa đơn.
5. Mở rộng XML theo đúng schema/version đã xác minh; tạo PNG/JPG và ảnh degraded cho OCR.

## Legal and schema baseline

- Thông tư 78/2021/TT-BTC là căn cứ lịch sử, **không còn là văn bản hiện hành độc lập từ 01/06/2025**; đã được thay thế bởi Thông tư 32/2025/TT-BTC.
- Từ 01/07/2026, cần đọc cùng Nghị định 254/2026/NĐ-CP và Thông tư 91/2026/TT-BTC.
- Quyết định 1233/QĐ-CT ngày 27/08/2026 thay thế Quyết định 1306/QĐ-CT; quy định dữ liệu nghiệp vụ và truyền nhận. Có giai đoạn chuyển tiếp message version 2.1.0/2.1.1.
- Quyết định 1450/QĐ-TCT là chuẩn cũ, không dùng làm schema hiện hành duy nhất.
- Mọi field/rule/schema phải có nguồn, phiên bản, ngày hiệu lực và trạng thái xác minh trong `docs/LEGAL_AND_SCHEMA_BASELINE.md`.

Official/legal references:
- [Nghị định 254/2026/NĐ-CP - Cổng văn bản Chính phủ](https://vanban.chinhphu.vn/?classid=1&docid=218689&pageid=27160&typegroupid=4)
- [Thông tư 91/2026/TT-BTC - Cổng văn bản Chính phủ](https://vanban.chinhphu.vn/?classid=1&docid=219006&orggroupid=4&pageid=27160)
- [Quyết định 1233/QĐ-CT - nội dung và phụ lục kỹ thuật](https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Quyet-dinh-1233-QD-CT-2026-thanh-phan-chua-du-lieu-nghiep-vu-hoa-don-chung-tu-dien-tu-722644.aspx)
- [Thông tư 78/2021/TT-BTC - tình trạng hiệu lực](https://vanban.org/van-ban/thong-tu-78-2021-tt-btc-luat-quan-ly-thue-hoa-don-chung-123-2020-nd-cp/dieu-1)

## Architecture

`Input/config → Document Type → Canonical Invoice Model → validation → PDF/HTML/XML/image exporters → Ground Truth + Manifest`

All artifacts for one invoice must derive from the same canonical data. PDF visual layout, official XML schema compliance and THTAX Core mapping are three separate validations.

## Repository layout

- `generator/src/dataset_generator/`: Python implementation.
- `schemas/legal/`: versioned external XML/JSON schemas, only from verified sources.
- `schemas/thtax_core/`: THTAX Core mapping and contract snapshots supplied by the project.
- `templates/`: invoice visual templates.
- `datasets/`: generated samples; do not commit large generated batches.
- `docs/`: legal baseline, field dictionary, architecture and acceptance rules.

## Run (MVP)

Python 3.11+.

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
source .venv/bin/activate
pip install -e .
python -m dataset_generator.cli --count 1 --output datasets/samples
```

Set `DATASET_FONT_PATH` to a Vietnamese-capable TTF font if the default system font is unavailable (e.g. Arial on Windows or DejaVuSans on Linux).

## Ownership

- **Vy:** primary owner — implement generator, invoice templates, exporters, Ground Truth and tests.
- **Thành:** support — confirm THTAX Core contract/mapping, prioritize document types, review legal/schema decisions and PRs.

## Scope boundary

This repository generates synthetic source documents and labels. It does not issue real invoices, sign documents, connect to tax authority systems, or replace THTAX ingestion/backend.
