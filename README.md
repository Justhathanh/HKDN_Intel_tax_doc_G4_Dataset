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

- Verified current framework includes Nghị định 254/2026/NĐ-CP and Thông tư 91/2026/TT-BTC, both effective 01/07/2026.
- Quyết định 1233/QĐ-CT dated 27/08/2026 replaces Quyết định 1306/QĐ-CT and defines business-data components and transmission. It specifies a transition period for message versions 2.1.0 and 2.1.1.
- Earlier instruments (including TT78/2021 and QĐ1450/QĐ-TCT) must not be assumed to be the current technical schema. Record the exact applicable instrument, annex, version and effective date before implementing any legal field rule.
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

### 1. Cài đặt môi trường

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

### 2. Tạo bộ dữ liệu kiểm thử & tự động xuất file nén `.zip`

**Cách 1: Chế độ tương tác nhanh (Khuyên dùng)**
Chỉ cần gõ đúng 1 lệnh sau và nhấn **Enter** 3 lần để nhận cấu hình mặc định:

```bash
python -m dataset_generator.cli
```

Hệ thống sẽ hiển thị 3 câu hỏi tùy chọn (bấm **Enter** liên tiếp để dùng mặc định):

1. Số lượng hóa đơn hợp lệ muốn tạo _(mặc định: 5)_
2. Có tạo kèm hóa đơn lỗi & file hỏng không? _(mặc định: y)_
3. Có đóng gói thành file `.zip` luôn không? _(mặc định: y)_

Kết quả xuất ra tại:

- Thư mục chi tiết: `datasets/samples/sample-42/`
- File nén sẵn sàng sử dụng: `datasets/samples/sample-42.zip`

**Cách 2: Sinh bộ dữ liệu kiểm thử đầy đủ bằng tham số**

```bash
# Sinh 5 hóa đơn hợp lệ + 3 hóa đơn lỗi nghiệp vụ + 3 mẫu file lỗi định dạng + xuất file .zip
python -m dataset_generator.cli --count 5 --seed 100 --include-negative --zip --output datasets/samples
```

**Cấu trúc mỗi thư mục chứng từ sinh ra (`datasets/samples/sample-<seed>/<document_id>/`):**

- `invoice.pdf`: Bản thể hiện hóa đơn GTGT chuẩn NĐ 254/2026/NĐ-CP & TT 91/2026/TT-BTC (có text layer).
- `invoice_scan.pdf`: Bản PDF dạng ảnh scan (không có text layer) phục vụ kiểm thử luồng OCR.
- `images/page-001.png`: Ảnh hóa đơn gốc sắc nét (200 DPI).
- `images/page-001_blur.jpg`: Ảnh giả lập xoay nghiêng, làm mờ và nhiễu hạt phục vụ kiểm thử tiền xử lý ảnh (ST09) và OCR.
- `canonical.json`: Dữ liệu gốc chuẩn hóa sinh ra chứng từ.
- `ground_truth.json`: Nhãn kiểm thử (`valid_synthetic`, `invalid_format`, `missing_required_field`, `inconsistent_totals`), giá trị hiển thị (`displayed`), giá trị chuẩn hóa (`normalized`) và danh sách lỗi kỳ vọng.
- `manifest.json`: Thông tin phiên bản pháp lý (`ND254_2026_TT91_2026`), `seed`, `MIME type` và mã băm `SHA-256` của toàn bộ file trong bundle.

### Kiểm tra nhanh trạng thái hóa đơn hợp lệ / lỗi (PowerShell)

```powershell
Get-ChildItem .\datasets\samples\sample-100\*\manifest.json | ForEach-Object { $m = Get-Content $_ -Raw \vert{} ConvertFrom-Json; [PSCustomObject]@{ Folder =$_.Directory.Name; Status = $m.validation_status; Errors = ($m.validation_errors -join " | ") } } | Format-Table -AutoSize
```

### Chạy kiểm thử tự động (Unit Tests)

```bash
python -m pytest -v
```

## Ownership

- **Vy:** primary owner — implement generator, invoice templates, exporters, Ground Truth and tests.
- **Thành:** support — confirm THTAX Core contract/mapping, prioritize document types, review legal/schema decisions and PRs.

## Scope boundary

This repository generates synthetic source documents and labels. It does not issue real invoices, sign documents, connect to tax authority systems, or replace THTAX ingestion/backend.
