import argparse
import shutil
import sys
from pathlib import Path
from .exporters import write_bundle, write_corrupted_bundle
from .extended_docs import create_extended_document, write_extended_bundle
from .factory import create_sample_invoice
from .registry import DOCUMENT_TYPE_REGISTRY, get_document_type
from .validation import validate_invoice


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic Vietnamese tax document dataset")
    parser.add_argument(
        "--document-type",
        type=str,
        default="vat_invoice",
        help="Loại chứng từ cần tạo (mặc định: vat_invoice, hoặc 'all' để tạo đủ 9 loại)",
    )
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("datasets/samples"))
    parser.add_argument("--include-negative", action="store_true", help="Sinh thêm mẫu lỗi nghiệp vụ và lỗi định dạng")
    parser.add_argument("--allow-unverified", action="store_true", help="Cho phép sinh chứng từ mở rộng chưa xác minh schema")
    parser.add_argument("--zip", action="store_true", help="Đóng gói thư mục kết quả thành file .zip sau khi sinh xong")
    parser.add_argument("--name", type=str, default=None, help="Tên thư mục và file zip xuất ra")
    args = parser.parse_args()

    if len(sys.argv) == 1:
        print("=== THTAX - TRÌNH SINH DỮ LIỆU CHỨNG TỪ GIẢ LẬP ===")
        raw_type = input("1. Loại chứng từ ('vat_invoice' hoặc 'all' cho đủ 9 loại) [mặc định: vat_invoice]: ").strip()
        if raw_type:
            args.document_type = raw_type

        raw_count = input("2. Số lượng chứng từ hợp lệ mỗi loại [mặc định: 5]: ").strip()
        args.count = int(raw_count) if raw_count.isdigit() and int(raw_count) > 0 else 5

        raw_neg = input("3. Có tạo kèm hóa đơn lỗi & file hỏng không? (y/n) [mặc định: y]: ").strip().lower()
        args.include_negative = raw_neg != "n"

        raw_zip = input("4. Có đóng gói thành file .zip luôn không? (y/n) [mặc định: y]: ").strip().lower()
        args.zip = raw_zip != "n"

        raw_name = input("5. Đặt tên cho thư mục & file zip [Enter để dùng mặc định]: ").strip()
        if raw_name:
            args.name = raw_name
        print("-" * 50)

    if args.count < 1:
        parser.error("--count must be >= 1")

    if args.document_type != "all":
        try:
            doc_spec = get_document_type(args.document_type)
        except KeyError:
            valid_keys = ", ".join(list(DOCUMENT_TYPE_REGISTRY.keys()) + ["all"])
            parser.error(f"Invalid --document-type '{args.document_type}'. Available: {valid_keys}")

        if doc_spec.status != "supported" and not args.allow_unverified:
            parser.error(
                f"Document type '{args.document_type}' is '{doc_spec.status}' (schema unverified). "
                f"Pass --allow-unverified to generate reference samples."
            )

    dataset_id = args.name if args.name else f"thtax-dataset-seed{args.seed}"
    batch_dir = args.output / dataset_id
    seen_references: set[tuple[str, str]] = set()

    # Sinh Hóa đơn GTGT chuẩn MVP (vat_invoice)
    if args.document_type in ("vat_invoice", "all"):
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

    # Sinh 8 loại chứng từ mở rộng (khi truyền --document-type all hoặc --allow-unverified)
    ext_types = []
    if args.document_type == "all":
        ext_types = [k for k in DOCUMENT_TYPE_REGISTRY.keys() if k != "vat_invoice"]
    elif args.document_type != "vat_invoice" and args.allow_unverified:
        ext_types = [args.document_type]

    for idx, ext_type in enumerate(ext_types):
        for i in range(args.count):
            ext_seed = args.seed + (idx + 1) * 100 + i
            ext_doc = create_extended_document(ext_type, seed=ext_seed)
            write_extended_bundle(ext_doc, batch_dir / ext_doc.document_id, seed=ext_seed)
            print(f"Generated EXTENDED ({ext_type}) {ext_doc.document_id} -> {batch_dir}")

    if args.zip:
        zip_path = shutil.make_archive(str(batch_dir), "zip", root_dir=str(batch_dir))
        print(f"Packaged ZIP archive -> {zip_path}")


if __name__ == "__main__":
    main()