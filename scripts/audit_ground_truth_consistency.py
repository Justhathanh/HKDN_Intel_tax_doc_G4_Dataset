
import json
import sys
from pathlib import Path
from collections import Counter


BATCH = Path(
    "datasets/companies/company-a/"
    "BATCH-20261125-060347-c1007f"
)

DOCS = BATCH / "documents"


LEGACY_FIELDS = [
    "seller.name",
    "seller.tax_code",
    "seller.address",
    "buyer.name",
    "buyer.tax_code",
    "buyer.address",
    "form_number",
    "invoice_number",
    "series",
    "issue_date",
    "totals.subtotal",
    "totals.vat_total",
    "totals.grand_total",
]

EXTENDED_MAPPING = {
    "issuer.name": "issuer_name",
    "issuer.tax_code": "issuer_tax_code",
    "issuer.address": "issuer_address",
    "recipient.name": "recipient_name",
    "recipient.tax_code": "recipient_tax_code",
    "recipient.address": "recipient_address",
    "issue_date": "issue_date",
    "reference_code": "reference_code",
    "totals.total_amount": "total_amount",
}


def get_nested(data, dotted_key):
    current = data

    for part in dotted_key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)

    return current


def normalize(value):
    if value is None:
        return None

    if isinstance(value, str):
        return value.strip()

    return value


def is_present(value):
    if value is None:
        return False

    if isinstance(value, str):
        return value.strip() != ""

    return True


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(path)

    return json.loads(path.read_text(encoding="utf-8"))


def get_doc_type(gt, manifest, canonical):
    return (
        gt.get("document_type")
        or manifest.get("document_type")
        or canonical.get("document_type")
        or "unknown"
    )


def compare_field(gt_fields, canonical, gt_key, canonical_key):
    gt_item = gt_fields.get(gt_key)

    if isinstance(gt_item, dict):
        gt_value = gt_item.get("normalized")
        gt_present = gt_item.get("present", False)
    else:
        gt_value = gt_item
        gt_present = is_present(gt_item)

    canonical_value = get_nested(canonical, canonical_key)
    canonical_present = is_present(canonical_value)

    errors = []

    if bool(gt_present) != canonical_present:
        errors.append(
            f"{gt_key}: present mismatch "
            f"(GT={gt_present}, Canonical={canonical_present})"
        )
    elif normalize(gt_value) != normalize(canonical_value):
        errors.append(
            f"{gt_key}: value mismatch "
            f"(GT={gt_value!r}, Canonical={canonical_value!r})"
        )

    return errors


def compare_document(folder):
    errors = []
    warnings = []
    checks = 0

    try:
        gt = load_json(folder / "ground_truth.json")
        canonical = load_json(folder / "canonical.json")
        manifest = load_json(folder / "manifest.json")
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return {
            "folder": folder.name,
            "status": "ERROR",
            "checks": 0,
            "errors": [str(exc)],
            "warnings": [],
        }

    doc_type = get_doc_type(gt, manifest, canonical)
    gt_fields = gt.get("fields", {})

    if doc_type == "vat_invoice":
        mapping = {
            field: field
            for field in LEGACY_FIELDS
        }

    elif doc_type in {
        "sales_invoice",
        "adjustment_invoice",
        "replacement_invoice",
    }:
        mapping = EXTENDED_MAPPING

    else:
        mapping = {}
        warnings.append(
            f"Unsupported document_type: {doc_type}"
        )

    for gt_key, canonical_key in mapping.items():
        checks += 1
        errors.extend(
            compare_field(
                gt_fields,
                canonical,
                gt_key,
                canonical_key,
            )
        )

    # Verify document_type consistency
    for source_name, source in [
        ("manifest", manifest),
        ("canonical", canonical),
    ]:
        source_type = source.get("document_type")

        if source_type:
            checks += 1

            if source_type != doc_type:
                errors.append(
                    f"document_type mismatch: "
                    f"resolved={doc_type}, "
                    f"{source_name}={source_type}"
                )

    return {
        "folder": folder.name,
        "document_type": doc_type,
        "status": "FAIL" if errors else "PASS",
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def main():
    if not DOCS.exists():
        print(f"ERROR: Documents directory not found: {DOCS}")
        sys.exit(1)

    results = []

    for gt_path in sorted(DOCS.rglob("ground_truth.json")):
        relative_parts = gt_path.relative_to(DOCS).parts

        # Corrupted samples are handled by integrity validator.
        if "negative" in relative_parts:
            continue

        results.append(compare_document(gt_path.parent))

    print("\n========== CANONICAL ↔ GROUND TRUTH AUDIT ==========")

    total_checks = 0
    total_errors = 0
    status_counts = Counter()

    for result in results:
        status_counts[result["status"]] += 1
        total_checks += result["checks"]
        total_errors += len(result["errors"])

        print(
            f"\n[{result['status']}] "
            f"{result['folder']} "
            f"({result.get('document_type', 'unknown')})"
        )

        for error in result["errors"]:
            print("  ERROR:", error)

        for warning in result["warnings"]:
            print("  WARNING:", warning)

    print("\n========== SUMMARY ==========")
    print("Documents:", len(results))
    print("Passed:", status_counts["PASS"])
    print("Failed:", status_counts["FAIL"])
    print("Errors:", total_errors)
    print("Checks:", total_checks)

    if total_errors:
        print("\nRESULT: FAILED")
        sys.exit(1)

    print("\nRESULT: PASSED")


if __name__ == "__main__":
    main()
