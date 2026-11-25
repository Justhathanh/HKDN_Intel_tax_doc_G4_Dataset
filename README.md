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

**Yêu cầu:**
- Python 3.11 trở lên.
- Git.
- Windows, macOS hoặc Linux.

**Bước 1: Clone repository**

\`\`\`bash
git clone https://github.com/Justhathanh/HKDN_Intel_tax_doc_G4_Dataset.git
cd HKDN_Intel_tax_doc_G4_Dataset
\`\`\`

**Bước 2: Tạo và kích hoạt virtual environment**

Windows PowerShell:

\`\`\`powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
\`\`\`

macOS/Linux:

\`\`\`bash
python3 -m venv .venv
source .venv/bin/activate
\`\`\`

**Bước 3: Cài đặt dependencies**

Chỉ cài đặt generator và các công cụ development:

\`\`\`bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
\`\`\`

Nếu cần sử dụng OCR bằng PaddleOCR:

\`\`\`bash
python -m pip install -e ".[ocr,dev]"
\`\`\`

Lệnh trên cài đặt thêm:
- PaddleOCR 3.x: nhận diện văn bản.
- PaddlePaddle 3.x: backend chạy mô hình OCR.
- OpenCV Headless: xử lý ảnh và tiền xử lý trước OCR.
- Pytest: chạy kiểm thử tự động.

**Bước 4: Kiểm tra môi trường**

\`\`\`bash
python -m pip check
python -m pytest -v
\`\`\`

Nếu cài OCR, kiểm tra thêm:

\`\`\`bash
thtax-ocr --help
\`\`\`

**Lưu ý:**
- OCR là dependency tùy chọn. Không cần cài nếu chỉ sử dụng chức năng generate dataset.
- Việc cài PaddlePaddle có thể phụ thuộc hệ điều hành, phiên bản Python và cấu hình CPU/GPU.
- Không cần cài Tesseract OCR cho pipeline OCR hiện tại.
- Kích hoạt \`.venv\` trước khi chạy các lệnh của dự án.

Set \`DATASET_FONT_PATH\` to a Vietnamese-capable TTF font if the default system font is unavailable. For example, on Windows:

\`\`\`powershell
$env:DATASET_FONT_PATH = "C:\Windows\Fonts\arial.ttf"
\`\`\`

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
- `images/page-001_blur.jpg`: Ảnh giả lập xoay nghiêng, làm mờ và nhiễu hạt phục vụ kiểm thử tiền xử lý ảnh và OCR.
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


## Web UI — THTAX Dataset Studio

Giao diện local để chọn công ty, loại chứng từ và quản lý các đợt generate.

```powershell
# Kích hoạt venv trước
python -m pip install -e .
streamlit run generator/src/dataset_generator/web_app.py
```

Mở URL local mà Streamlit hiển thị (thường là `http://localhost:8501`).

### Cách sử dụng

1. Mở tab **Tạo dữ liệu**, chọn một trong ba công ty mẫu.
2. Chọn loại chứng từ (hiện chỉ `vat_invoice` được bật) và chiều hóa đơn: đầu vào hoặc đầu ra.
3. Chọn số lượng, seed và có/không tạo negative cases.
4. Bấm **Tạo dataset**, tải ZIP ngay tại giao diện.
5. Tab **Quản lý công ty** cho phép thêm, lưu trữ/kích hoạt hoặc xóa vĩnh viễn một công ty cùng toàn bộ batch/ZIP thuộc công ty đó.
6. Tab **Kho dữ liệu** liệt kê các batch; chọn một hoặc nhiều batch bằng checkbox rồi xác nhận **Xóa batch đã chọn** để xóa hàng loạt.

Ba công ty mặc định là hồ sơ giả lập để kiểm thử UI, không đại diện cho ba khách hàng Pilot thực tế. Cấu hình công ty được lưu tại `configs/companies.json`.

### Cấu trúc output

```text
datasets/
└── companies/
    └── <company_id>/
        └── <document_type>/
            └── <direction>/  # incoming hoặc outgoing
                └── <batch_id>/
                ├── batch_manifest.json
                ├── <document_id>/
                │   ├── invoice.pdf
                │   ├── invoice_scan.pdf
                │   ├── canonical.json
                │   ├── ground_truth.json
                │   ├── manifest.json
                │   └── images/
                └── ...
```

Mỗi batch có ZIP cùng tên ở cạnh thư mục batch. Không đưa dữ liệu Pilot thật vào thư mục synthetic này. Dữ liệu thật cần một kho riêng, phân quyền theo client/engagement, giữ nguyên file nguồn và có quy trình phê duyệt xử lý.

**Giới hạn hiện tại:** Web UI chỉ bật loại chứng từ `supported` trong registry (hiện là `vat_invoice`). Các loại `needs_review`/`planned` không được mở cho đến khi schema và quy tắc nghiệp vụ được xác minh. PDF layout và biến thể OCR hiện tại vẫn là phiên bản MVP; giao diện quản lý không đồng nghĩa đã có nhiều layout thực tế.


## XML, linked scenarios and export profiles

The Dataset Studio now writes a well-formed internal XML representation from each canonical document. This is an integration-test format only; it is **not** a legally verified e-invoice XML schema. Manifest fields explicitly retain `xml_schema_verified: false` and `xml_schema_version: null`.

Adjustment samples can use either a VAT invoice or a Sales Invoice as the original document; the selected type is preserved in the linked adjusted snapshot. Replacement samples currently retain a VAT invoice as the original. Adjustment scenarios carry a signed delta; replacement scenarios supersede the original and are not additive.

Each Batch produces two archives:
- `<batch_id>.zip`: Full Dataset, including source files, OCR derivatives, Canonical JSON, Ground Truth, manifests and reports.
- `<batch_id>-upload.zip`: Upload Dataset, containing only original PDF/XML inputs and excluding Ground Truth, canonical labels, scan derivatives and corrupted fixtures.

See [Dataset Export Contract](docs/DATASET_EXPORT_CONTRACT.md) for the artifact and scenario contract.


Generated batches can be selected and deleted in bulk from the **Kho dữ liệu** tab. Deletion removes only selected batch directories and their adjacent Full/Upload ZIP archives. The **Quản lý công ty** tab also supports permanent company deletion, which removes that company profile from `configs/companies.json` and its entire local dataset directory. Both operations require explicit confirmation and validate paths under the configured data root. Generated datasets are excluded from Git by `.gitignore`.


## OCR extraction and field-level evaluation

The project provides an optional OCR pipeline implemented in \`generator/src/dataset_generator/ocr/\`, using **PaddleOCR 3.x**.

OCR processing runs locally. Original documents and Ground Truth files are not modified.

### 1. Install dependencies

Activate the project's virtual environment, then install the OCR dependencies:

\`\`\`powershell
python -m pip install -e ".[ocr,dev]"
\`\`\`

Verify the installation:

\`\`\`powershell
python -m pip check
thtax-ocr --help
\`\`\`

No separate Tesseract installation is required.

### 2. Run OCR on a batch

Process a directory recursively:

\`\`\`powershell
thtax-ocr --input "datasets/companies/company-a/BATCH-..." --output "ocr_results"
\`\`\`

Or run a single PDF/image file:

\`\`\`powershell
thtax-ocr --input "path/to/invoice.pdf" --output "ocr_results"
\`\`\`

The module can also be executed directly:

\`\`\`powershell
python -m dataset_generator.ocr.cli --input "path/to/input" --output "ocr_results"
\`\`\`

**Supported input formats:**
- PDF
- PNG
- JPG/JPEG
- TIFF
- BMP

**Available options:**

| Option | Description |
|---|---|
| \`--input\` | Input PDF/image file or directory (required) |
| \`--output\` | Output directory (default: \`ocr_results\`) |
| \`--dpi\` | PDF rendering resolution (default: 220) |
| \`--lang\` | PaddleOCR language (default: \`vi\`) |
| \`--force-ocr\` | Force OCR even when a PDF has a text layer |
| \`--no-preprocess\` | Disable image preprocessing |
| \`--no-deskew\` | Disable automatic image deskew |

### 3. Extraction workflow

1. Discover supported PDF and image files.
2. Extract the native text layer from PDFs when available.
3. Render scanned PDF pages at the configured DPI.
4. Apply optional deskew and image preprocessing.
5. Run PaddleOCR recognition.
6. Compare extracted fields against the corresponding \`ground_truth.json\`.
7. Export individual results and an aggregate evaluation report.

PDFs containing a text layer use PyMuPDF native extraction by default. Use \`--force-ocr\` to process these pages through PaddleOCR.

### 4. Outputs and metrics

The output directory contains:

- \`<document>.txt\`: extracted text.
- \`<document>.json\`: extraction results, page-level diagnostics and evaluation details.
- \`ocr_evaluation_report.json\`: aggregate evaluation across processed documents.

When a sibling \`ground_truth.json\` exists, the evaluator compares extracted scalar fields against Ground Truth using normalized, accent-insensitive matching.

The report includes:
- Field Accuracy.
- Document Accuracy.
- Field-level CER/WER.
- Per-field PASS/FAIL results.
- Mean OCR confidence.

**Metric boundary:** CER/WER currently measure concatenated expected scalar fields, not a verbatim full-page transcription. Full-document CER/WER requires page-level transcription in Ground Truth and must not be inferred from field labels.

Mean OCR confidence represents the OCR engine's recognition confidence. It is not a measure of field correctness.

### 5. Data preservation

- Original PDFs and images are read-only.
- \`canonical.json\`, \`ground_truth.json\` and manifests are not modified.
- OCR outputs are written to the separate output directory.
- Errors in individual documents are recorded without stopping the remaining batch.

Do not commit generated OCR reports or large experimental datasets unless explicitly required.
