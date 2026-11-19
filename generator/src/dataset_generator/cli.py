import argparse
from pathlib import Path
from .factory import create_sample_invoice
from .validation import validate_invoice
from .exporters import write_bundle

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic Vietnamese VAT invoice dataset")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("datasets/samples"))
    args = parser.parse_args()
    if args.count < 1: parser.error("--count must be >= 1")
    for i in range(args.count):
        seed = args.seed + i
        invoice = create_sample_invoice(seed)
        errors = validate_invoice(invoice)
        if errors: raise SystemExit("; ".join(errors))
        dataset_id = f"sample-{args.seed}"
        write_bundle(invoice, args.output / dataset_id / invoice.document_id)
        print(f"Generated {invoice.document_id} -> {args.output / dataset_id}")
if __name__ == "__main__": main()
