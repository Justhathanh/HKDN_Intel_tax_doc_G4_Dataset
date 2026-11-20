import argparse
from pathlib import Path
from .exporters import write_bundle, write_corrupted_bundle
from .factory import create_sample_invoice
from .validation import validate_invoice

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic Vietnamese VAT invoice dataset")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("datasets/samples"))
    parser.add_argument("--include-negative", action="store_true", help="Sinh thêm mẫu lỗi nghiệp vụ và lỗi định dạng")
    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count must be >= 1")

    dataset_id = f"sample-{args.seed}"
    for i in range(args.count):
        seed = args.seed + i
        invoice = create_sample_invoice(seed, scenario="valid")
        errors = validate_invoice(invoice)
        if errors:
            raise SystemExit("; ".join(errors))
        write_bundle(invoice, args.output / dataset_id / invoice.document_id)
        print(f"Generated VALID {invoice.document_id} -> {args.output / dataset_id}")

    if args.include_negative:
        for j in range(3):
            bad_seed = args.seed + 1000 + j
            bad_inv = create_sample_invoice(bad_seed, scenario="invalid_business")
            bad_errors = validate_invoice(bad_inv)
            write_bundle(bad_inv, args.output / dataset_id / bad_inv.document_id, validation_errors=bad_errors)
            print(f"Generated INVALID_BUSINESS {bad_inv.document_id} -> {args.output / dataset_id}")

        for case in ("empty_pdf", "fake_pdf_text", "malformed_xml"):
            write_corrupted_bundle(args.output / dataset_id / f"corrupted-{case}", case_name=case)
            print(f"Generated CORRUPTED {case} -> {args.output / dataset_id}")

if __name__ == "__main__":
    main()