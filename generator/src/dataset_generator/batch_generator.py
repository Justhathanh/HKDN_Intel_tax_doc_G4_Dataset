
from __future__ import annotations

import json
import secrets
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from decimal import Decimal, InvalidOperation
from .exporters import export_pdf, write_bundle, write_corrupted_bundle
from .extended_docs import create_extended_document, write_extended_bundle
from .factory import create_sample_invoice, mutate_invoice
from .model import CanonicalInvoice, InvoiceLine, Party
from .registry import DOCUMENT_TYPE_REGISTRY
from .validation import validate_invoice
from .bundle_tools import add_xml_and_refresh_manifest, add_adjustment_scenario_xml, build_dataset_index, create_upload_archive


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = ROOT / "datasets" / "companies"

# Chỉ các loại này có cấu trúc bên phát hành/bên nhận tương ứng
# với quan hệ người bán/người mua của hóa đơn.
INVOICE_LIKE_TYPES = {
    "vat_invoice",
    "sales_invoice",
    "adjustment_invoice",
    "replacement_invoice",
}

# Các loại này đã có hàm sinh trong extended_docs.py.
EXTENDED_GENERATOR_TYPES = {
    "sales_invoice",
    "adjustment_invoice",
    "replacement_invoice",
    "state_budget_payment",
    "tax_notice",
    "fee_receipt",
    "pit_withholding",
}


def validate_extended_document(doc: Any) -> list[str]:
    """Kiểm tra tính toàn vẹn cơ bản, không xác nhận tuân thủ pháp lý."""
    errors: list[str] = []

    if not doc.document_id:
        errors.append("document_id is required")

    if doc.document_type not in EXTENDED_GENERATOR_TYPES:
        errors.append(
            f"unsupported extended document type: {doc.document_type}"
        )

    if not doc.title.strip():
        errors.append("title is required")

    if not doc.reference_code.strip():
        errors.append("reference_code is required")

    try:
        datetime.strptime(str(doc.issue_date), "%Y-%m-%d")
    except (TypeError, ValueError):
        errors.append("issue_date must use YYYY-MM-DD")

    if not doc.issuer_name.strip():
        errors.append("issuer_name is required")

    if not doc.recipient_name.strip():
        errors.append("recipient_name is required")

    try:
        total_amount = Decimal(str(doc.total_amount))

        if total_amount < 0:
            errors.append("total_amount cannot be negative")
    except (InvalidOperation, TypeError, ValueError):
        errors.append("total_amount must be a valid number")
        return errors

    if not doc.items:
        errors.append("at least one line item is required")
        return errors

    item_total = Decimal("0")
    all_amounts_present = True

    for index, item in enumerate(doc.items):
        for field in ("name", "unit", "quantity", "unit_price", "amount"):
            if field not in item:
                errors.append(f"items[{index}].{field} is required")

        try:
            if "quantity" in item and Decimal(str(item["quantity"])) <= 0:
                errors.append(f"items[{index}].quantity must be positive")

            if "unit_price" in item and Decimal(str(item["unit_price"])) < 0:
                errors.append(
                    f"items[{index}].unit_price cannot be negative"
                )

            if "amount" in item:
                amount = Decimal(str(item["amount"]))

                if amount < 0:
                    errors.append(
                        f"items[{index}].amount cannot be negative"
                    )

                item_total += amount
            else:
                all_amounts_present = False

        except (InvalidOperation, TypeError, ValueError):
            errors.append(f"items[{index}] contains an invalid numeric value")
            all_amounts_present = False

    if all_amounts_present:
        metadata = doc.metadata or {}

        # Chứng từ có VAT: dòng hàng đối chiếu với subtotal,
        # tổng thanh toán đối chiếu với subtotal + VAT.
        if "subtotal" in metadata and "vat_amount" in metadata:
            try:
                subtotal = Decimal(str(metadata["subtotal"]))
                vat_amount = Decimal(str(metadata["vat_amount"]))

                if item_total != subtotal:
                    errors.append(
                        "line_items total does not match subtotal"
                    )

                if subtotal + vat_amount != total_amount:
                    errors.append(
                        "subtotal + vat_amount does not match total_amount"
                    )

            except (InvalidOperation, TypeError, ValueError):
                errors.append("Invalid subtotal or vat_amount")

        else:
            # Chứng từ không có VAT riêng.
            if item_total != total_amount:
                errors.append(
                    "line_items total does not match total_amount"
                )

    return errors



def _apply_company_to_vat(invoice: Any, company: dict, direction: str) -> None:
    party = Party(
        name=company["legal_name"],
        address=company.get("address", ""),
        tax_code=company["tax_code"],
    )

    if direction == "incoming":
        invoice.buyer = party
    else:
        invoice.seller = party

    invoice.extra["pilot_company"] = {
        "company_id": company["id"],
        "display_name": company["name"],
        "industry": company.get("industry", ""),
        "invoice_direction": direction,
    }


def _apply_company_to_extended(doc: Any, company: dict, direction: str) -> None:
    doc.metadata["pilot_company"] = {
        "company_id": company["id"],
        "display_name": company["name"],
        "industry": company.get("industry", ""),
        "selected_direction": direction,
    }

    if doc.document_type not in INVOICE_LIKE_TYPES:
        return

    if direction == "incoming":
        doc.recipient_name = company["legal_name"]
        doc.recipient_tax_code = company["tax_code"]
        doc.recipient_address = company.get("address", "")
    else:
        doc.issuer_name = company["legal_name"]
        doc.issuer_tax_code = company["tax_code"]
        doc.issuer_address = company.get("address", "")


def _short_document_base(document_type: str, code: str | int, role: str | None = None) -> str:
    prefixes = {
        "vat_invoice": "tax_invoice",
        "sales_invoice": "sales_invoice",
        "adjustment_invoice": "adjustment_invoice",
        "replacement_invoice": "replacement_invoice",
        "state_budget_payment": "state_budget_payment",
        "tax_notice": "tax_notice",
        "fee_receipt": "fee_receipt",
        "pit_withholding": "pit_withholding",
    }
    prefix = prefixes.get(document_type, document_type)
    formatted_code = f"{int(code):03d}"
    suffix = f"_{role}" if role else ""
    return f"{prefix}{formatted_code}{suffix}"


def _rename_pdf_artifacts(document_dir: Path, base_name: str, primary_pdf: str) -> None:
    source = document_dir / primary_pdf
    target = document_dir / f"{base_name}.pdf"
    if source.exists() and source != target:
        source.rename(target)
    scan = document_dir / "invoice_scan.pdf"
    scan_target = document_dir / f"{base_name}_scan.pdf"
    if scan.exists() and scan != scan_target:
        scan.rename(scan_target)


def _build_adjusted_invoice_snapshot(original: CanonicalInvoice, adjustment: Any) -> CanonicalInvoice:
    """Build the complete invoice state after applying an adjustment delta."""
    metadata = adjustment.metadata
    subtotal_delta = Decimal(str(metadata["subtotal"]))
    signed_subtotal_delta = (
        -subtotal_delta
        if metadata["adjustment_direction"] == "decrease"
        else subtotal_delta
    )
    adjustment_line = InvoiceLine(
        name=f"Điều chỉnh {metadata['adjustment_direction']} theo {adjustment.reference_code}",
        unit="Khoản",
        quantity=Decimal("1"),
        unit_price=signed_subtotal_delta,
        vat_rate=Decimal("8"),
    )
    extra = dict(original.extra)
    extra["scenario"] = {
        "scenario_id": metadata["scenario_id"],
        "role": "adjusted",
        "root_document_id": original.document_id,
        "adjustment_document_id": adjustment.document_id,
        "adjustment_reason": metadata["reason"],
        "adjustment_direction": metadata["adjustment_direction"],
        "adjustment_delta_signed": str(metadata["adjustment_delta_signed"]),
        "expected_final_total": str(metadata["scenario_expected"]["final_total"]),
    }
    return CanonicalInvoice(
        document_id=f"{original.document_id}-adjusted",
        document_type="vat_invoice",
        issue_date=adjustment.issue_date,
        form_number=original.form_number,
        series=original.series,
        invoice_number=original.invoice_number,
        seller=original.seller,
        buyer=original.buyer,
        lines=[*original.lines, adjustment_line],
        currency=original.currency,
        payment_method=original.payment_method,
        synthetic=True,
        legal_profile_version=original.legal_profile_version,
        xml_schema_version=original.xml_schema_version,
        thtax_core_contract_version=original.thtax_core_contract_version,
        extra=extra,
    )


def create_batch(
    company: dict,
    document_types: list[str],
    direction: str,
    count_per_type: int,
    seed: int,
    include_negative: bool,
    allow_unverified: bool = False,
) -> Path:
    if not document_types:
        raise ValueError("Select at least one document type")
    if count_per_type < 1:
        raise ValueError("count_per_type must be >= 1")
    if direction not in {"incoming", "outgoing"}:
        raise ValueError("direction must be incoming or outgoing")

    unknown = set(document_types) - set(DOCUMENT_TYPE_REGISTRY)
    if unknown:
        raise ValueError(f"Unknown document types: {', '.join(sorted(unknown))}")

    for type_key in document_types:
        spec = DOCUMENT_TYPE_REGISTRY[type_key]

        if type_key == "non_tax_document":
            raise ValueError(
                "non_tax_document is planned and does not have an approved generator"
            )
        if type_key not in EXTENDED_GENERATOR_TYPES and type_key != "vat_invoice":
            raise ValueError(f"No generator registered for {type_key}")
        if spec.status != "supported" and not allow_unverified:
            raise ValueError(
                f"{type_key} has status '{spec.status}'. "
                "Enable allow_unverified to generate reference samples."
            )

    timestamp = datetime.now().astimezone()
    batch_id = f"BATCH-{timestamp:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    batch_dir = OUTPUT_ROOT / company["id"] / batch_id
    documents_dir = batch_dir / "documents"
    documents_dir.mkdir(parents=True, exist_ok=False)

    document_records: list[dict[str, Any]] = []
    validation_records: list[dict[str, Any]] = []
    valid_count_by_type: dict[str, int] = {}
    negative_count = 0

    for type_index, type_key in enumerate(document_types):
        spec = DOCUMENT_TYPE_REGISTRY[type_key]
        valid_count_by_type[type_key] = 0

        for index in range(count_per_type):
            current_seed = seed + type_index * 100_000 + index
            # Human-friendly lookup code only; collisions across files/batches are allowed.
            filename_code = secrets.randbelow(999) + 1

            if type_key == "vat_invoice":
                invoice = create_sample_invoice(current_seed, scenario="valid")
                _apply_company_to_vat(invoice, company, direction)

                seen = {
                    (record["series"], record["invoice_number"])
                    for record in document_records
                    if record.get("document_type") == "vat_invoice"
                    and record.get("series")
                    and record.get("invoice_number")
                }
                errors = validate_invoice(invoice, seen_references=seen)
                if errors:
                    raise ValueError(
                        f"VAT validation failed for {invoice.document_id}: "
                        + "; ".join(errors)
                    )

                output_dir = documents_dir / invoice.document_id
                write_bundle(invoice, output_dir)
                short_base = _short_document_base(type_key, filename_code)
                _rename_pdf_artifacts(output_dir, short_base, "invoice.pdf")
                add_xml_and_refresh_manifest(output_dir, f"{short_base}.xml")

                record = {
                    "document_id": invoice.document_id,
                    "document_type": type_key,
                    "document_label": "core_synthetic",
                    "validation_status": "passed",
                    "series": invoice.series,
                    "invoice_number": invoice.invoice_number,
                    "filename_code": f"{filename_code:03d}",
                }

            else:
                scenario_original_record = None
                scenario_id = None
                adjusted_invoice_snapshot = None
                doc = create_extended_document(type_key, seed=current_seed)
                _apply_company_to_extended(doc, company, direction)

                if type_key in {"adjustment_invoice", "replacement_invoice"}:
                    scenario_id = str(uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"thtax-scenario-{type_key}-{current_seed}",
                    ))
                    original_seed = current_seed + 50_000_000
                    original = create_sample_invoice(original_seed, scenario="valid")
                    _apply_company_to_vat(original, company, direction)

                    # Keep the parties identical across the source and related document.
                    doc.issuer_name = original.seller.name
                    doc.issuer_tax_code = original.seller.tax_code
                    doc.issuer_address = original.seller.address
                    doc.recipient_name = original.buyer.name
                    doc.recipient_tax_code = original.buyer.tax_code
                    doc.recipient_address = original.buyer.address

                    original.extra["scenario"] = {
                        "scenario_id": scenario_id,
                        "role": "original",
                        "related_document_type": type_key,
                    }
                    doc.metadata["reason"] = (
                        f"Điều chỉnh giá trị hóa đơn gốc {original.series}-{original.invoice_number}"
                        if type_key == "adjustment_invoice"
                        else f"Thay thế hóa đơn gốc {original.series}-{original.invoice_number}"
                    )
                    doc.metadata.update({
                        "scenario_id": scenario_id,
                        "role": "adjustment" if type_key == "adjustment_invoice" else "replacement",
                        "references_document_id": original.document_id,
                        "reference_invoice_number": original.invoice_number,
                        "reference_series": original.series,
                    })

                    if type_key == "adjustment_invoice":
                        # Store an absolute adjustment amount and its signed business effect.
                        # The original document remains unchanged evidence.
                        adjustment_subtotal = (original.grand_total * Decimal("0.05")).quantize(Decimal("1"))
                        vat_amount = (adjustment_subtotal * Decimal("0.08")).quantize(Decimal("1"))
                        doc.items = [{
                            "name": "Khoản điều chỉnh giá trị hàng hóa/dịch vụ (mẫu giả lập)",
                            "unit": "Khoản",
                            "quantity": Decimal("1"),
                            "unit_price": adjustment_subtotal,
                            "amount": adjustment_subtotal,
                        }]
                        doc.metadata["subtotal"] = adjustment_subtotal
                        doc.metadata["vat_amount"] = vat_amount
                        adjustment_direction = "decrease" if current_seed % 2 == 0 else "increase"
                        signed_delta = -(adjustment_subtotal + vat_amount) if adjustment_direction == "decrease" else adjustment_subtotal + vat_amount
                        doc.metadata["adjustment_direction"] = adjustment_direction
                        doc.metadata["adjustment_delta_signed"] = signed_delta
                        doc.total_amount = adjustment_subtotal + vat_amount
                        doc.metadata["scenario_expected"] = {
                            "original_total": original.grand_total,
                            "adjustment_delta": signed_delta,
                            "final_total": original.grand_total + signed_delta,
                            "rule": "original_total_plus_signed_adjustment",
                        }
                    else:
                        doc.metadata["scenario_expected"] = {
                            "original_total": original.grand_total,
                            "replacement_total": doc.total_amount,
                            "final_total": doc.total_amount,
                            "rule": "replacement_supersedes_original_not_additive",
                        }

                    if type_key == "adjustment_invoice":
                        adjusted_invoice_snapshot = _build_adjusted_invoice_snapshot(original, doc)

                    original_errors = validate_invoice(original)
                    if original_errors:
                        raise ValueError(
                            f"Scenario original validation failed for {original.document_id}: "
                            + "; ".join(original_errors)
                        )
                    original_dir = documents_dir / original.document_id
                    write_bundle(original, original_dir)
                    scenario_base = _short_document_base(type_key, filename_code)
                    root_base = f"{scenario_base}_root"
                    _rename_pdf_artifacts(original_dir, root_base, "invoice.pdf")
                    add_xml_and_refresh_manifest(original_dir, f"{root_base}.xml")
                    scenario_original_record = {
                        "document_id": original.document_id,
                        "document_type": "vat_invoice",
                        "document_label": "core_synthetic",
                        "validation_status": "passed",
                        "scenario_id": scenario_id,
                        "scenario_role": "original",
                        "related_document_id": doc.document_id,
                        "series": original.series,
                        "invoice_number": original.invoice_number,
                        "filename_code": f"{filename_code:03d}",
                    }

                errors = validate_extended_document(doc)
                if errors:
                    raise ValueError(
                        f"Extended validation failed for {doc.document_id}: "
                        + "; ".join(errors)
                    )

                output_dir = documents_dir / doc.document_id
                write_extended_bundle(doc, output_dir, seed=current_seed)
                if scenario_id:
                    scenario_base = _short_document_base(type_key, filename_code)
                    if type_key == "adjustment_invoice":
                        adjustment_base = f"{scenario_base}_adjustment"
                        _rename_pdf_artifacts(output_dir, adjustment_base, "document.pdf")
                        adjusted_base = f"{scenario_base}_adjusted"
                        adjusted_pdf = output_dir / f"{adjusted_base}.pdf"
                        export_pdf(adjusted_invoice_snapshot, adjusted_pdf)
                        adjusted_snapshot_dict = adjusted_invoice_snapshot.to_dict()
                    else:
                        adjusted_base = f"{scenario_base}_adjusted"
                        _rename_pdf_artifacts(output_dir, adjusted_base, "document.pdf")
                        adjusted_snapshot_dict = None

                    if adjusted_snapshot_dict is not None:
                        (output_dir / "adjusted_state.json").write_text(
                            json.dumps(adjusted_snapshot_dict, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                    add_adjustment_scenario_xml(
                        batch_dir,
                        original.document_id,
                        doc.document_id,
                        scenario_id,
                        f"{scenario_base}.xml",
                        type_key,
                        adjusted_snapshot=adjusted_snapshot_dict,
                    )
                else:
                    short_base = _short_document_base(type_key, filename_code)
                    _rename_pdf_artifacts(output_dir, short_base, "document.pdf")
                    add_xml_and_refresh_manifest(output_dir, f"{short_base}.xml")

                record = {
                    "document_id": doc.document_id,
                    "document_type": type_key,
                    "document_label": "reference_unverified_synthetic",
                    "validation_status": "passed_basic_checks",
                    **({
                        "scenario_id": doc.metadata["scenario_id"],
                        "scenario_role": doc.metadata["role"],
                        "related_document_id": doc.metadata["references_document_id"],
                    } if type_key in {"adjustment_invoice", "replacement_invoice"} else {}),
                    "filename_code": f"{filename_code:03d}",
                }

                if scenario_original_record:
                    document_records.append(scenario_original_record)
                    validation_records.append({
                        "document_id": scenario_original_record["document_id"],
                        "document_type": "vat_invoice",
                        "status": "passed",
                        "errors": [],
                        "scenario_id": scenario_original_record["scenario_id"],
                        "scenario_role": "original",
                    })
                    valid_count_by_type["vat_invoice"] = valid_count_by_type.get("vat_invoice", 0) + 1

            document_records.append(record)
            validation_records.append({
                "document_id": record["document_id"],
                "document_type": type_key,
                "status": record["validation_status"],
                "errors": [],
            })
            valid_count_by_type[type_key] += 1

    # Negative samples hiện chỉ hỗ trợ VAT Invoice.
    negative_by_type: dict[str, int] = {}
    if include_negative and "vat_invoice" in document_types:
        vat_negative_cases = [
            "missing_buyer_name",
            "invalid_tax_code",
            "negative_qty",
            "duplicate_reference",
        ]
        vat_dir = documents_dir / "negative"
        vat_dir.mkdir(parents=True, exist_ok=True)

        for index, case in enumerate(vat_negative_cases):
            bad_seed = seed + 900_000 + index
            invoice = create_sample_invoice(bad_seed, scenario="valid")
            _apply_company_to_vat(invoice, company, direction)
            invoice = mutate_invoice(
                invoice,
                seed=bad_seed,
                error_kind=case,
            )

            if case == "duplicate_reference":
                existing = next(
                    (
                        item for item in document_records
                        if item.get("document_type") == "vat_invoice"
                    ),
                    None,
                )
                if existing:
                    invoice.series = existing["series"]
                    invoice.invoice_number = existing["invoice_number"]

            seen_negative_refs = {
                (item["series"], item["invoice_number"])
                for item in document_records
                if item.get("document_type") == "vat_invoice"
                and item.get("series")
                and item.get("invoice_number")
            }
            errors = validate_invoice(invoice, seen_references=seen_negative_refs)
            negative_dir = vat_dir / f"{case}-{invoice.document_id}"
            write_bundle(
                invoice,
                negative_dir,
                validation_errors=errors,
            )
            negative_code = secrets.randbelow(999) + 1
            negative_base = f"tax_invoice{negative_code:03d}_{case}"
            _rename_pdf_artifacts(negative_dir, negative_base, "invoice.pdf")
            add_xml_and_refresh_manifest(negative_dir, f"{negative_base}.xml")
            validation_records.append({
                "document_id": invoice.document_id,
                "document_type": "vat_invoice",
                "status": "negative_sample",
                "case": case,
                "errors": errors,
            })
            negative_by_type[case] = 1
            negative_count += 1

        for case in ("empty_pdf", "fake_pdf_text", "malformed_xml"):
            write_corrupted_bundle(
                vat_dir / f"corrupted-{case}",
                case_name=case,
            )
            validation_records.append({
                "document_id": f"corrupted-{case}",
                "document_type": "vat_invoice",
                "status": "corrupted_sample",
                "case": case,
                "errors": [case],
            })
            negative_count += 1

    status_by_type = {
        key: DOCUMENT_TYPE_REGISTRY[key].status
        for key in document_types
    }
    if any(key in document_types for key in ("adjustment_invoice", "replacement_invoice")):
        status_by_type["vat_invoice"] = DOCUMENT_TYPE_REGISTRY["vat_invoice"].status

    manifest = {
        "batch_id": batch_id,
        "company": {
            key: company.get(key)
            for key in ("id", "name", "legal_name", "tax_code", "industry")
        },
        "document_types": document_types,
        "document_type_status": status_by_type,
        "invoice_direction": direction,
        "synthetic": True,
        "seed": seed,
        "filename_code_policy": "random_001_999_human_lookup_only_collisions_allowed",
        "count_per_type": count_per_type,
        "valid_count": sum(valid_count_by_type.values()),
        "valid_count_by_type": valid_count_by_type,
        "negative_count": negative_count,
        "negative_cases": negative_by_type,
        "created_at": timestamp.isoformat(),
        "documents": [
            {
                key: value
                for key, value in record.items()
                if key not in {"series", "invoice_number"}
            }
            for record in document_records
        ],
        "export_policy": {
            "full_dataset": "includes source files, scans, canonical data, Ground Truth, manifests and reports",
            "upload_dataset": "includes only original PDF/XML input files; excludes Ground Truth and corrupted samples",
        },
        "full_dataset_archive": f"{batch_id}.zip",
        "upload_dataset_archive": f"{batch_id}-upload.zip",
        "xml_format": "thtax-synthetic-internal-v1",
        "xml_schema_verified": False,
        "notice": (
            "Synthetic data only. Not real tax documents and not valid "
            "for tax/legal use. XML is well-formed internal interchange data, "
            "not a legally verified tax XML schema. Extended schemas are unverified."
        ),
    }

    validation_report = {
        "batch_id": batch_id,
        "total_documents": len(document_records) + negative_count,
        "valid_documents": len(document_records),
        "negative_documents": negative_count,
        "results": validation_records,
    }

    (batch_dir / "batch_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (batch_dir / "validation_report.json").write_text(
        json.dumps(validation_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    build_dataset_index(batch_dir)
    create_upload_archive(batch_dir)
    zip_path = shutil.make_archive(
        str(batch_dir),
        "zip",
        root_dir=str(batch_dir),
    )
    return Path(zip_path)
