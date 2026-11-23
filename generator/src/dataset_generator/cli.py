import argparse
import shutil
import sys
from pathlib import Path
from .exporters import write_bundle, write_corrupted_bundle
from .factory import create_sample_invoice
from .registry import DOCUMENT_TYPE_REGISTRY, get_document_type
from .validation import validate_invoice


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic Vietnamese VAT invoice dataset")
    parser.add_argument(
        "--document-type",
        type=str,
        default="vat_invoice",
        help="Loại chứng từ cần tạo (mặc định: vat_invoice)",
    )
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("datasets/samples"))
    parser.add_argument("--include-negative", action="store_true", help="Sinh thêm mẫu lỗi nghiệp vụ và lỗi định dạng")
    parser.add_argument("--zip", action="store_true", help="Đóng gói thư mục kết quả thành file .zip sau khi sinh xong")
    parser.add_argument("--name", type=str, default=None, help="Tên thư mục và file zip xuất ra")
    args = parser.parse_args()

    if len(sys.argv) == 1:
        print("=== THTAX - TRÌNH SINH DỮ LIỆU HÓA ĐƠN GIẢ LẬP ===")
        raw_count = input("1. Số lượng hóa đơn hợp lệ muốn tạo [mặc định: 5]: ").strip()
        args.count = int(raw_count) if raw_count.isdigit() and int(raw_count) > 0 else 5

        raw_neg = input("2. Có tạo kèm hóa đơn lỗi & file hỏng không? (y/n) [mặc định: y]: ").strip().lower()
        args.include_negative = raw_neg != "n"

        raw_zip = input("3. Có đóng gói thành file .zip luôn không? (y/n) [mặc định: y]: ").strip().lower()
        args.zip = raw_zip != "n"

        raw_name = input("4. Đặt tên cho thư mục & file zip [Enter để dùng mặc định]: ").strip()
        if raw_name:
            args.name = raw_name
        print("-" * 50)

    if args.count < 1:
        parser.error("--count must be >= 1")

    try:
        doc_spec = get_document_type(args.document_type)
    except KeyError:
        valid_keys = ", ".join(DOCUMENT_TYPE_REGISTRY.keys())
        parser.error(f"Invalid --document-type '{args.document_type}'. Available: {valid_keys}")

    if doc_spec.status != "supported":
        parser.error(
            f"Document type '{args.document_type}' is currently '{doc_spec.status}' "
            f"(not supported in MVP; only 'vat_invoice' is supported)."
        )

    dataset_id = args.name if args.name else f"thtax-dataset-seed{args.seed}"
    batch_dir = args.output / dataset_id
    seen_references: set[tuple[str, str]] = set()

    for i in range(args.count):
        seed = args.seed + i
        invoice = create_sample_invoice(seed, scenario="valid")
        errors = validate_invoice(invoice, seen_references=seen_references)
        if errors:
            raise SystemExit("; ".join(errors))
        seen_references.add((invoice.series, invoice.invoice_number))
        write_bundle(invoice, batch_dir / invoice.document_id)
        print(f"Generated VALID {invoice.document_id} -> {batch_dir}")

    if args.include_negative:
        negative_cases = [
            "missing_buyer_name",
            "invalid_tax_code",
            "negative_qty",
            "duplicate_reference",
            "non_tax_document",
        ]
        for j, error_kind in enumerate(negative_cases):
            bad_seed = args.seed + 1000 + j
            bad_inv = create_sample_invoice(bad_seed, scenario="invalid_business", error_kind=error_kind)
            if error_kind == "duplicate_reference" and seen_references:
                first_series, first_num = next(iter(seen_references))
                bad_inv.series = first_series
                bad_inv.invoice_number = first_num
            bad_errors = validate_invoice(bad_inv, seen_references=seen_references)
            write_bundle(bad_inv, batch_dir / bad_inv.document_id, validation_errors=bad_errors)
            print(f"Generated INVALID ({error_kind}) {bad_inv.document_id} -> {batch_dir}")

        for case in ("empty_pdf", "fake_pdf_text", "malformed_xml"):
            write_corrupted_bundle(batch_dir / f"corrupted-{case}", case_name=case)
            print(f"Generated CORRUPTED {case} -> {batch_dir}")

    if args.zip:
        zip_path = shutil.make_archive(str(batch_dir), "zip", root_dir=str(batch_dir))
        print(f"Packaged ZIP archive -> {zip_path}")


if __name__ == "__main__":
    main()
