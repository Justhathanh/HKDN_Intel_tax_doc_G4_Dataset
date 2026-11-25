
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET

from pathlib import Path
from typing import Any


VALID_STATUSES = {"passed", "passed_basic_checks"}

CORRUPTED_CASES = {
    "empty_pdf": {
        "extension": ".pdf",
        "error_code": "EMPTY_FILE",
    },
    "fake_pdf_text": {
        "extension": ".pdf",
        "error_code": "INVALID_MIME_OR_HEADER",
    },
    "malformed_xml": {
        "extension": ".xml",
        "error_code": "XML_SYNTAX_ERROR",
    },
}


class _Audit:
    def __init__(self) -> None:
        self.checks = 0
        self.errors: list[str] = []

    def check(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            self.errors.append(message)

    def load_json(self, path: Path) -> Any | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.check(False, f"{path}: cannot read valid JSON ({exc})")
            return None

    def result(self) -> dict[str, Any]:
        return {
            "is_valid": not self.errors,
            "checks": self.checks,
            "passed": self.checks - len(self.errors),
            "failed": len(self.errors),
            "errors": self.errors,
        }


def _safe_child(root: Path, relative_path: str) -> Path | None:
    """Resolve a relative path without allowing traversal outside root."""
    try:
        candidate = (root / relative_path).resolve()
        candidate.relative_to(root.resolve())
        return candidate
    except (ValueError, OSError):
        return None


def _verify_artifacts(
    audit: _Audit,
    document_dir: Path,
    artifacts: Any,
    *,
    allow_malformed_xml: bool = False,
) -> None:
    audit.check(
        isinstance(artifacts, dict),
        f"{document_dir}: manifest artifacts must be an object",
    )
    if not isinstance(artifacts, dict):
        return

    for relative_path, metadata in artifacts.items():
        if not isinstance(relative_path, str):
            audit.check(
                False,
                f"{document_dir}: artifact path must be a string",
            )
            continue

        artifact_path = _safe_child(document_dir, relative_path)

        audit.check(
            artifact_path is not None,
            f"{document_dir}: unsafe artifact path '{relative_path}'",
        )
        if artifact_path is None:
            continue

        audit.check(
            artifact_path.is_file(),
            f"{document_dir}: missing artifact '{relative_path}'",
        )
        if not artifact_path.is_file():
            continue

        if not isinstance(metadata, dict):
            audit.check(
                False,
                f"{document_dir}: invalid artifact metadata '{relative_path}'",
            )
            continue

        try:
            content = artifact_path.read_bytes()
        except OSError as exc:
            audit.check(
                False,
                f"{document_dir}: cannot read artifact '{relative_path}': {exc}",
            )
            continue

        audit.check(
            metadata.get("bytes") == len(content),
            f"{document_dir}: artifact size mismatch '{relative_path}'",
        )
        audit.check(
            metadata.get("sha256") == hashlib.sha256(content).hexdigest(),
            f"{document_dir}: SHA-256 mismatch '{relative_path}'",
        )

        if artifact_path.suffix.lower() == ".xml":
            try:
                ET.fromstring(content)
                xml_valid = True
            except ET.ParseError:
                xml_valid = False

            if allow_malformed_xml:
                # Corrupted XML is checked separately against its expected case.
                continue

            audit.check(
                xml_valid,
                f"{document_dir}: malformed XML '{relative_path}'",
            )


def _compare_ground_truth(
    audit: _Audit,
    canonical: dict[str, Any],
    ground_truth: dict[str, Any],
    document_dir: Path,
) -> None:
    fields = ground_truth.get("fields")

    audit.check(
        isinstance(fields, dict),
        f"{document_dir}: Ground Truth fields must be an object",
    )
    if not isinstance(fields, dict):
        return

    is_legacy = isinstance(canonical.get("seller"), dict)

    if is_legacy:
        seller = canonical.get("seller", {})
        buyer = canonical.get("buyer", {})
        totals = canonical.get("totals", {})

        mappings = {
            "form_number": canonical.get("form_number"),
            "series": canonical.get("series"),
            "invoice_number": canonical.get("invoice_number"),
            "issue_date": canonical.get("issue_date"),
            "seller.name": seller.get("name"),
            "seller.tax_code": seller.get("tax_code"),
            "seller.address": seller.get("address"),
            "buyer.name": buyer.get("name"),
            "buyer.tax_code": buyer.get("tax_code"),
            "buyer.address": buyer.get("address"),
            "totals.subtotal": totals.get("subtotal"),
            "totals.vat_total": totals.get("vat_total"),
            "totals.grand_total": totals.get("grand_total"),
        }

        canonical_items = canonical.get("lines", [])
        relationships = canonical.get("extra", {}).get("scenario", {})

    else:
        mappings = {
            "reference_code": canonical.get("reference_code"),
            "issue_date": canonical.get("issue_date"),
            "issuer.name": canonical.get("issuer_name"),
            "issuer.tax_code": canonical.get("issuer_tax_code"),
            "issuer.address": canonical.get("issuer_address"),
            "recipient.name": canonical.get("recipient_name"),
            "recipient.tax_code": canonical.get("recipient_tax_code"),
            "recipient.address": canonical.get("recipient_address"),
            "totals.total_amount": canonical.get("total_amount"),
        }

        canonical_items = canonical.get("items", [])
        metadata = canonical.get("metadata", {})

        relationship_keys = (
            "scenario_id",
            "role",
            "references_document_id",
            "reference_invoice_number",
            "reference_series",
            "scenario_expected",
            "adjustment_direction",
            "adjustment_delta_signed",
        )

        relationships = {
            key: metadata[key]
            for key in relationship_keys
            if key in metadata
        }

    for field_name, expected_value in mappings.items():
        field = fields.get(field_name)

        audit.check(
            isinstance(field, dict),
            f"{document_dir}: Ground Truth missing field '{field_name}'",
        )
        if not isinstance(field, dict):
            continue

        expected_normalized = (
            "" if expected_value is None else str(expected_value)
        )

        audit.check(
            field.get("normalized") == expected_normalized,
            f"{document_dir}: Ground Truth normalized mismatch: {field_name}",
        )

        expected_present = expected_value is not None and expected_value != ""

        audit.check(
            field.get("present") is expected_present,
            f"{document_dir}: Ground Truth present mismatch: {field_name}",
        )

    audit.check(
        ground_truth.get("line_items") == canonical_items,
        f"{document_dir}: Ground Truth line_items do not match Canonical",
    )

    gt_relationships = ground_truth.get("relationships", {})

    if is_legacy:
        audit.check(
            gt_relationships == relationships,
            f"{document_dir}: Ground Truth relationships do not match Canonical",
        )
    else:
        audit.check(
            isinstance(gt_relationships, dict),
            f"{document_dir}: Extended Ground Truth relationships must be an object",
        )

        if isinstance(gt_relationships, dict):
            for key, expected_value in relationships.items():
                audit.check(
                    gt_relationships.get(key) == expected_value,
                    f"{document_dir}: Ground Truth relationship mismatch: {key}",
                )


def validate_document_bundle(
    document_dir: Path | str,
) -> dict[str, Any]:
    """Audit a normal or negative document with Canonical data."""
    document_dir = Path(document_dir)
    audit = _Audit()

    canonical = audit.load_json(document_dir / "canonical.json")
    ground_truth = audit.load_json(document_dir / "ground_truth.json")
    manifest = audit.load_json(document_dir / "manifest.json")

    if not all(
        isinstance(item, dict)
        for item in (canonical, ground_truth, manifest)
    ):
        return audit.result()

    audit.check(
        canonical.get("document_id") == manifest.get("document_id"),
        f"{document_dir}: Canonical/manifest document_id mismatch",
    )
    audit.check(
        canonical.get("document_type") == manifest.get("document_type"),
        f"{document_dir}: Canonical/manifest document_type mismatch",
    )
    audit.check(
        ground_truth.get("document_id") == canonical.get("document_id"),
        f"{document_dir}: Ground Truth/Canonical document_id mismatch",
    )

    gt_type = ground_truth.get("document_type")
    if gt_type is not None:
        audit.check(
            gt_type == canonical.get("document_type"),
            f"{document_dir}: Ground Truth/Canonical document_type mismatch",
        )

    _compare_ground_truth(audit, canonical, ground_truth, document_dir)

    artifacts = manifest.get("artifacts")
    _verify_artifacts(audit, document_dir, artifacts)

    if isinstance(artifacts, dict):
        for required in ("canonical.json", "ground_truth.json"):
            audit.check(
                required in artifacts,
                f"{document_dir}: manifest does not register '{required}'",
            )

        xml_artifact = manifest.get("xml_artifact")
        if xml_artifact is not None:
            audit.check(
                xml_artifact in artifacts,
                f"{document_dir}: xml_artifact is not registered in manifest",
            )

    return audit.result()


def validate_corrupted_bundle(
    document_dir: Path | str,
    report_record: dict[str, Any],
) -> dict[str, Any]:
    """Audit an intentionally corrupted artifact against its declared case."""
    document_dir = Path(document_dir)
    audit = _Audit()

    manifest = audit.load_json(document_dir / "manifest.json")
    ground_truth = audit.load_json(document_dir / "ground_truth.json")

    if not isinstance(manifest, dict) or not isinstance(ground_truth, dict):
        return audit.result()

    document_id = report_record.get("document_id")
    case = report_record.get("case")
    case_spec = CORRUPTED_CASES.get(case)

    audit.check(
        manifest.get("document_id") == document_id,
        f"{document_dir}: corrupted manifest document_id mismatch",
    )
    audit.check(
        ground_truth.get("document_id") == document_id,
        f"{document_dir}: corrupted Ground Truth document_id mismatch",
    )
    audit.check(
        manifest.get("document_type") == "corrupted_document",
        f"{document_dir}: unexpected corrupted document_type",
    )
    audit.check(
        report_record.get("status") == "corrupted_sample",
        f"{document_dir}: report status is not corrupted_sample",
    )
    audit.check(
        case_spec is not None,
        f"{document_dir}: unknown corrupted case '{case}'",
    )

    if case_spec is None:
        return audit.result()

    expected_error = case_spec["error_code"]

    audit.check(
        ground_truth.get("document_label") == "invalid_format",
        f"{document_dir}: corrupted Ground Truth label mismatch",
    )
    audit.check(
        ground_truth.get("expected_error_code") == expected_error,
        f"{document_dir}: Ground Truth expected_error_code mismatch",
    )
    audit.check(
        expected_error in manifest.get("validation_errors", []),
        f"{document_dir}: manifest does not declare expected error",
    )
    audit.check(
        case in report_record.get("errors", []),
        f"{document_dir}: Validation Report does not declare corrupted case",
    )

    artifacts = manifest.get("artifacts")
    _verify_artifacts(
        audit,
        document_dir,
        artifacts,
        allow_malformed_xml=True,
    )

    if not isinstance(artifacts, dict):
        return audit.result()

    artifact_names = [
        name
        for name in artifacts
        if name != "ground_truth.json"
    ]

    audit.check(
        len(artifact_names) == 1,
        f"{document_dir}: corrupted bundle must have exactly one corrupted artifact",
    )

    if len(artifact_names) != 1:
        return audit.result()

    artifact_name = artifact_names[0]
    artifact_path = _safe_child(document_dir, artifact_name)

    if artifact_path is None or not artifact_path.is_file():
        audit.check(
            False,
            f"{document_dir}: corrupted artifact is missing or unsafe",
        )
        return audit.result()

    audit.check(
        Path(artifact_name).suffix.lower() == case_spec["extension"],
        f"{document_dir}: corrupted artifact extension mismatch",
    )

    try:
        content = artifact_path.read_bytes()
    except OSError as exc:
        audit.check(
            False,
            f"{document_dir}: cannot read corrupted artifact: {exc}",
        )
        return audit.result()

    if case == "empty_pdf":
        audit.check(
            len(content) == 0,
            f"{document_dir}: empty_pdf artifact is not empty",
        )

    elif case == "fake_pdf_text":
        audit.check(
            len(content) > 0,
            f"{document_dir}: fake_pdf_text artifact is empty",
        )
        audit.check(
            not content.startswith(b"%PDF-"),
            f"{document_dir}: fake_pdf_text unexpectedly has a PDF header",
        )

    elif case == "malformed_xml":
        try:
            ET.fromstring(content)
            xml_is_malformed = False
        except ET.ParseError:
            xml_is_malformed = True

        audit.check(
            xml_is_malformed,
            f"{document_dir}: malformed_xml artifact is valid XML",
        )

    return audit.result()


def validate_batch_integrity(
    batch_dir: Path | str,
) -> dict[str, Any]:
    """Audit a complete batch, including valid, negative and corrupted samples."""
    batch_dir = Path(batch_dir)
    audit = _Audit()

    batch_manifest = audit.load_json(batch_dir / "batch_manifest.json")
    dataset_index = audit.load_json(batch_dir / "dataset_index.json")
    validation_report = audit.load_json(batch_dir / "validation_report.json")

    if not all(
        isinstance(item, dict)
        for item in (batch_manifest, dataset_index, validation_report)
    ):
        return audit.result()

    batch_id = batch_manifest.get("batch_id")

    audit.check(
        batch_id == batch_dir.name,
        f"{batch_dir}: batch_manifest batch_id does not match directory name",
    )
    audit.check(
        dataset_index.get("batch_id") == batch_id,
        f"{batch_dir}: dataset_index batch_id mismatch",
    )
    audit.check(
        validation_report.get("batch_id") == batch_id,
        f"{batch_dir}: validation_report batch_id mismatch",
    )

    records = batch_manifest.get("documents")
    index_records = dataset_index.get("documents")
    report_records = validation_report.get("results")

    audit.check(
        isinstance(records, list),
        f"{batch_dir}: batch_manifest documents must be a list",
    )
    audit.check(
        isinstance(index_records, list),
        f"{batch_dir}: dataset_index documents must be a list",
    )
    audit.check(
        isinstance(report_records, list),
        f"{batch_dir}: validation_report results must be a list",
    )

    if not all(
        isinstance(value, list)
        for value in (records, index_records, report_records)
    ):
        return audit.result()

    audit.check(
        dataset_index.get("document_count") == len(index_records),
        f"{batch_dir}: dataset_index document_count mismatch",
    )
    audit.check(
        validation_report.get("total_documents") == len(report_records),
        f"{batch_dir}: validation_report total_documents mismatch",
    )

    batch_by_id: dict[str, dict[str, Any]] = {}
    index_by_id: dict[str, dict[str, Any]] = {}
    report_by_id: dict[str, dict[str, Any]] = {}

    def build_map(
        source: list[Any],
        target: dict[str, dict[str, Any]],
        label: str,
    ) -> None:
        for record in source:
            if not isinstance(record, dict):
                audit.check(
                    False,
                    f"{batch_dir}: invalid {label} record",
                )
                continue

            document_id = record.get("document_id")

            audit.check(
                isinstance(document_id, str) and bool(document_id),
                f"{batch_dir}: {label} record has missing document_id",
            )

            if not isinstance(document_id, str) or not document_id:
                continue

            audit.check(
                document_id not in target,
                f"{batch_dir}: duplicate document_id in {label}: {document_id}",
            )
            target[document_id] = record

    build_map(records, batch_by_id, "batch_manifest")
    build_map(index_records, index_by_id, "dataset_index")
    build_map(report_records, report_by_id, "validation_report")

    valid_ids = {
        document_id
        for document_id, record in report_by_id.items()
        if record.get("status") in VALID_STATUSES
    }

    negative_ids = {
        document_id
        for document_id, record in report_by_id.items()
        if record.get("status") == "negative_sample"
    }

    corrupted_ids = {
        document_id
        for document_id, record in report_by_id.items()
        if record.get("status") == "corrupted_sample"
    }

    expected_index_ids = valid_ids | negative_ids

    audit.check(
        set(batch_by_id) == valid_ids,
        f"{batch_dir}: batch_manifest must contain exactly the valid document IDs",
    )
    audit.check(
        set(index_by_id) == expected_index_ids,
        f"{batch_dir}: dataset_index must contain valid and negative document IDs only",
    )
    audit.check(
        not (corrupted_ids & set(index_by_id)),
        f"{batch_dir}: corrupted samples must not appear in dataset_index",
    )

    valid_count = len(valid_ids)
    negative_count = len(negative_ids) + len(corrupted_ids)

    audit.check(
        batch_manifest.get("valid_count") == valid_count,
        f"{batch_dir}: batch_manifest valid_count mismatch",
    )

    expected_valid_count_by_type = {
        key: 0
        for key in batch_manifest.get("document_types", [])
        if isinstance(key, str)
    }

    for document_id in valid_ids:
        record = report_by_id[document_id]
        document_type = record.get("document_type")

        if isinstance(document_type, str):
            expected_valid_count_by_type[document_type] = (
                expected_valid_count_by_type.get(document_type, 0) + 1
            )

    audit.check(
        batch_manifest.get("valid_count_by_type")
        == expected_valid_count_by_type,
        f"{batch_dir}: batch_manifest valid_count_by_type mismatch",
    )

    audit.check(
        validation_report.get("valid_documents") == valid_count,
        f"{batch_dir}: validation_report valid_documents mismatch",
    )
    audit.check(
        validation_report.get("negative_documents") == negative_count,
        f"{batch_dir}: validation_report negative_documents mismatch",
    )

    # Audit all valid and negative bundles listed in Dataset Index.
    for document_id, index_record in index_by_id.items():
        relative_path = index_record.get("relative_path")

        document_dir = (
            _safe_child(batch_dir, relative_path)
            if isinstance(relative_path, str)
            else None
        )

        audit.check(
            document_dir is not None and document_dir.is_dir(),
            f"{batch_dir}: missing or unsafe indexed document path for {document_id}",
        )

        if document_dir is None or not document_dir.is_dir():
            continue

        document_result = validate_document_bundle(document_dir)

        for error in document_result["errors"]:
            audit.check(False, error)

        canonical = audit.load_json(document_dir / "canonical.json")
        manifest = audit.load_json(document_dir / "manifest.json")

        if not isinstance(canonical, dict) or not isinstance(manifest, dict):
            continue

        audit.check(
            canonical.get("document_id") == document_id,
            f"{document_dir}: index/Canonical document_id mismatch",
        )
        audit.check(
            manifest.get("document_id") == document_id,
            f"{document_dir}: index/manifest document_id mismatch",
        )
        audit.check(
            manifest.get("dataset_id") == batch_id,
            f"{document_dir}: document manifest dataset_id mismatch",
        )

        report_record = report_by_id.get(document_id)

        if report_record is not None:
            audit.check(
                canonical.get("document_type") == report_record.get("document_type"),
                f"{document_dir}: Validation Report document_type mismatch",
            )

        audit.check(
            index_record.get("document_type") == canonical.get("document_type"),
            f"{document_dir}: dataset_index document_type mismatch",
        )

        expected_artifacts = sorted(manifest.get("artifacts", {}).keys())

        audit.check(
            index_record.get("relative_path") == relative_path,
            f"{document_dir}: dataset_index relative_path mismatch",
        )
        audit.check(
            index_record.get("artifacts") == expected_artifacts,
            f"{document_dir}: dataset_index artifacts mismatch",
        )
        audit.check(
            index_record.get("validation_status")
            == manifest.get("validation_status"),
            f"{document_dir}: dataset_index validation_status mismatch",
        )
        audit.check(
            index_record.get("schema_verified")
            == manifest.get("schema_verified", False),
            f"{document_dir}: dataset_index schema_verified mismatch",
        )
        audit.check(
            index_record.get("xml_schema_verified")
            == manifest.get("xml_schema_verified", False),
            f"{document_dir}: dataset_index xml_schema_verified mismatch",
        )

    # Batch Manifest contains valid documents only.
    for document_id, record in batch_by_id.items():
        report_record = report_by_id.get(document_id)

        audit.check(
            report_record is not None
            and report_record.get("status") in VALID_STATUSES,
            f"{batch_dir}: batch document is not valid in Validation Report: {document_id}",
        )

        index_record = index_by_id.get(document_id)

        audit.check(
            index_record is not None,
            f"{batch_dir}: valid document missing from Dataset Index: {document_id}",
        )

        if index_record is not None:
            audit.check(
                record.get("relative_path") == index_record.get("relative_path"),
                f"{batch_dir}: Batch Manifest/Dataset Index path mismatch: {document_id}",
            )

        if report_record is not None:
            audit.check(
                record.get("document_type") == report_record.get("document_type"),
                f"{batch_dir}: Batch Manifest/Validation Report type mismatch: {document_id}",
            )

    # Negative samples must be represented in Dataset Index.
    for document_id in negative_ids:
        audit.check(
            document_id in index_by_id,
            f"{batch_dir}: negative sample missing from Dataset Index: {document_id}",
        )

        report_record = report_by_id[document_id]

        audit.check(
            bool(report_record.get("case")),
            f"{batch_dir}: negative sample missing case: {document_id}",
        )
        audit.check(
            bool(report_record.get("errors")),
            f"{batch_dir}: negative sample missing expected errors: {document_id}",
        )

    # Corrupted samples have no Canonical and are audited separately.
    negative_root = _safe_child(batch_dir, "documents/negative")

    audit.check(
        negative_root is not None and negative_root.is_dir(),
        f"{batch_dir}: missing documents/negative directory",
    )

    if negative_root is not None and negative_root.is_dir():
        for document_id in corrupted_ids:
            report_record = report_by_id[document_id]
            corrupted_dir = _safe_child(negative_root, document_id)

            audit.check(
                corrupted_dir is not None and corrupted_dir.is_dir(),
                f"{batch_dir}: missing corrupted sample directory: {document_id}",
            )

            if corrupted_dir is None or not corrupted_dir.is_dir():
                continue

            corrupted_result = validate_corrupted_bundle(
                corrupted_dir,
                report_record,
            )

            for error in corrupted_result["errors"]:
                audit.check(False, error)

            audit.check(
                not (corrupted_dir / "canonical.json").exists(),
                f"{corrupted_dir}: corrupted sample must not contain canonical.json",
            )

    # Verify scenario references between valid documents.
    for document_id, record in batch_by_id.items():
        related_id = record.get("related_document_id")

        if not related_id:
            continue

        related = batch_by_id.get(related_id)

        audit.check(
            related is not None,
            f"{batch_dir}: {document_id} references missing document {related_id}",
        )

        if related is None:
            continue

        scenario_id = record.get("scenario_id")
        related_scenario_id = related.get("scenario_id")

        if scenario_id is not None and related_scenario_id is not None:
            audit.check(
                scenario_id == related_scenario_id,
                f"{batch_dir}: scenario_id mismatch between {document_id} and {related_id}",
            )

    return audit.result()
