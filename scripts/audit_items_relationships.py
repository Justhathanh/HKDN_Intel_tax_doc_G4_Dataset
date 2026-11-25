
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(
    "datasets/companies/company-a/"
    "BATCH-20261125-060347-c1007f/documents"
)

ITEM_FIELDS = (
    "name",
    "unit",
    "quantity",
    "unit_price",
    "amount",
    "vat_rate",
)


checks = 0
passed = 0
errors = []


def check(condition, message):
    global checks, passed

    checks += 1

    if condition:
        passed += 1
    else:
        errors.append(message)
        print("[FAIL]", message)


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(path)

    return json.loads(path.read_text(encoding="utf-8"))


def normalize(value):
    if value is None:
        return None

    text = str(value).strip()

    try:
        number = Decimal(text)
        return ("number", number.normalize())
    except InvalidOperation:
        return ("text", text)


def to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def get_total(canonical):
    if canonical.get("document_type") == "vat_invoice":
        totals = canonical.get("totals") or {}
        return to_decimal(totals.get("grand_total"))

    return to_decimal(canonical.get("total_amount"))


def get_invoice_number(canonical):
    metadata = canonical.get("metadata") or {}

    return (
        metadata.get("invoice_number")
        or canonical.get("invoice_number")
    )


def get_series(canonical):
    metadata = canonical.get("metadata") or {}

    return metadata.get("series") or canonical.get("series")


def main():
    documents = {}

    # --------------------------------------------------
    # 1. LOAD DOCUMENTS
    # --------------------------------------------------

    for gt_path in sorted(ROOT.rglob("ground_truth.json")):
        relative = gt_path.relative_to(ROOT)

        if "negative" in relative.parts:
            continue

        folder = gt_path.parent

        try:
            gt = load_json(gt_path)
            canonical = load_json(folder / "canonical.json")
            manifest = load_json(folder / "manifest.json")
        except Exception as exc:
            check(False, f"{folder.name}: cannot load files: {exc}")
            continue

        document_id = canonical.get("document_id")

        check(
            bool(document_id),
            f"{folder.name}: missing canonical document_id"
        )

        if not document_id:
            continue

        documents[document_id] = {
            "name": folder.name,
            "gt": gt,
            "canonical": canonical,
            "manifest": manifest,
        }

    print("\n========== ITEMS AUDIT ==========")

    # --------------------------------------------------
    # 2. ITEMS: GROUND TRUTH VS CANONICAL
    # --------------------------------------------------

    for document_id, doc in documents.items():
        name = doc["name"]
        gt = doc["gt"]
        canonical = doc["canonical"]

        gt_items = gt.get("line_items")
        if gt_items is None:
            gt_items = []

        if canonical.get("document_type") == "vat_invoice":
            canonical_items = canonical.get("lines")
        else:
            canonical_items = canonical.get("items")

        if canonical_items is None:
            canonical_items = []

        check(
            isinstance(gt_items, list),
            f"{name}: GT line_items is not a list"
        )

        check(
            isinstance(canonical_items, list),
            f"{name}: Canonical items/lines is not a list"
        )

        if not isinstance(gt_items, list):
            continue

        if not isinstance(canonical_items, list):
            continue

        check(
            len(gt_items) == len(canonical_items),
            (
                f"{name}: item count mismatch "
                f"GT={len(gt_items)}, "
                f"Canonical={len(canonical_items)}"
            )
        )

        for index, (gt_item, cp_item) in enumerate(
            zip(gt_items, canonical_items)
        ):
            for field in ITEM_FIELDS:
                gt_value = gt_item.get(field)
                cp_value = cp_item.get(field)

                # Only compare fields represented in either side.
                if field not in gt_item and field not in cp_item:
                    continue

                check(
                    normalize(gt_value) == normalize(cp_value),
                    (
                        f"{name}: item[{index}].{field} mismatch "
                        f"GT={gt_value!r}, Canonical={cp_value!r}"
                    )
                )

    # --------------------------------------------------
    # 3. DOCUMENT RELATIONSHIPS
    # --------------------------------------------------

    print("\n========== RELATIONSHIP AUDIT ==========")

    for document_id, doc in documents.items():
        name = doc["name"]
        gt = doc["gt"]
        canonical = doc["canonical"]

        relationships = gt.get("relationships")

        if not isinstance(relationships, dict):
            continue

        role = relationships.get("role")

        if role not in ("adjustment", "replacement"):
            continue

        metadata = canonical.get("metadata") or {}

        reference_id = relationships.get("references_document_id")
        scenario_id = relationships.get("scenario_id")

        # Child must reference an existing document.
        original = documents.get(reference_id)

        check(
            original is not None,
            f"{name}: referenced document {reference_id} not found"
        )

        if original is None:
            continue

        original_name = original["name"]
        original_gt = original["gt"]
        original_cp = original["canonical"]
        original_rel = original_gt.get("relationships")

        if not isinstance(original_rel, dict):
            original_rel = {}

        original_metadata = original_cp.get("metadata") or {}

        # Expected original document type.
        expected_original_type = metadata.get("root_invoice_type")

        check(
            original_cp.get("document_type") == expected_original_type,
            (
                f"{name}: original document type mismatch "
                f"expected={expected_original_type}, "
                f"actual={original_cp.get('document_type')}"
            )
        )

        # Ground Truth role of original.
        check(
            original_rel.get("role") == "original",
            f"{name}: referenced document is not marked original"
        )

        # Scenario ID must match.
        check(
            original_rel.get("scenario_id") == scenario_id,
            f"{name}: original GT scenario_id mismatch"
        )

        check(
            original_metadata.get("scenario_id", scenario_id)
            == scenario_id,
            f"{name}: original Canonical scenario_id mismatch"
        )

        # Original must point back to child in Canonical metadata.
        original_type = original_cp.get("document_type")

        if original_type == "vat_invoice":
            check(
                original_rel.get("related_document_type") == role + "_invoice",
                f"{name}: original GT related_document_type mismatch"
            )

        else:
            check(
                original_metadata.get("related_document_id") == document_id,
                f"{name}: original Canonical related_document_id mismatch"
            )

        # Child relationship data must match Canonical metadata.
        check(
            metadata.get("role") == role,
            f"{name}: Canonical role mismatch"
        )

        check(
            metadata.get("scenario_id") == scenario_id,
            f"{name}: Canonical scenario_id mismatch"
        )

        check(
            metadata.get("references_document_id") == reference_id,
            f"{name}: Canonical references_document_id mismatch"
        )

        # Original invoice number and series.
        expected_number = relationships.get("reference_invoice_number")
        expected_series = relationships.get("reference_series")

        if expected_number is not None:
            check(
                str(get_invoice_number(original_cp)) == str(expected_number),
                f"{name}: referenced invoice number mismatch"
            )

        if expected_series is not None:
            check(
                str(get_series(original_cp)) == str(expected_series),
                f"{name}: referenced invoice series mismatch"
            )

        # Scenario total validation.
        scenario = relationships.get("scenario_expected") or {}

        original_total = to_decimal(scenario.get("original_total"))
        final_total = to_decimal(scenario.get("final_total"))

        actual_original_total = get_total(original_cp)
        actual_child_total = get_total(canonical)

        check(
            original_total is not None
            and actual_original_total == original_total,
            f"{name}: scenario original_total mismatch"
        )

        if role == "adjustment":
            delta = to_decimal(
                relationships.get("adjustment_delta_signed")
            )

            if delta is None:
                delta = to_decimal(scenario.get("adjustment_delta"))

            check(
                delta is not None,
                f"{name}: missing signed adjustment delta"
            )

            if delta is not None and original_total is not None:
                check(
                    original_total + delta == final_total,
                    f"{name}: adjustment total arithmetic is incorrect"
                )

                check(
                    actual_child_total == abs(delta),
                    f"{name}: adjustment document total does not equal absolute delta"
                )

            expected_direction = (
                "increase" if delta is not None and delta > 0
                else "decrease" if delta is not None and delta < 0
                else None
            )

            if expected_direction:
                check(
                    relationships.get("adjustment_direction")
                    == expected_direction,
                    f"{name}: adjustment direction mismatch"
                )

        elif role == "replacement":
            replacement_total = to_decimal(
                scenario.get("replacement_total")
            )

            check(
                replacement_total is not None
                and actual_child_total == replacement_total,
                f"{name}: replacement_total mismatch"
            )

            check(
                final_total == replacement_total,
                f"{name}: replacement final_total must equal replacement_total"
            )

    # --------------------------------------------------
    # 4. SUMMARY
    # --------------------------------------------------

    print("\n========== SUMMARY ==========")
    print("Documents:", len(documents))
    print("Checks:", checks)
    print("Passed:", passed)
    print("Failed:", checks - passed)
    print("Errors:", len(errors))

    if errors:
        print("\n========== ERROR DETAILS ==========")

        for error in errors:
            print("-", error)

    print("\nRESULT:", "PASSED" if not errors else "FAILED")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
