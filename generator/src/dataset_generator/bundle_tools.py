"""Post-process generated document bundles with XML and integrity metadata."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .xml_exporter import write_canonical_xml, write_adjustment_scenario_xml


def _refresh_manifest(document_dir: Path) -> None:
    manifest_path = document_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = {}
    for path in sorted(document_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            relative = path.relative_to(document_dir).as_posix()
            mime, _ = mimetypes.guess_type(path.name)
            if path.suffix.lower() == ".xml":
                mime = "application/xml"
            artifacts[relative] = {
                "mime_type": mime or "application/octet-stream",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
    manifest["artifacts"] = artifacts
    manifest["xml_format"] = "thtax-synthetic-internal-v1"
    manifest["xml_schema_version"] = None
    manifest["xml_schema_verified"] = False
    manifest["xml_well_formed"] = True
    manifest["artifact_consistency"] = "generated_from_canonical_json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def add_xml_and_refresh_manifest(document_dir: Path, filename: str = "document.xml") -> Path:
    canonical_path = document_dir / "canonical.json"
    if not canonical_path.is_file():
        raise FileNotFoundError(f"Missing canonical.json in {document_dir}")
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    xml_path = document_dir / filename
    write_canonical_xml(canonical, xml_path)
    ET.parse(xml_path)
    _refresh_manifest(document_dir)
    manifest_path = document_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["xml_artifact"] = filename
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return xml_path


def add_adjustment_scenario_xml(
    batch_dir: Path,
    root_document_id: str,
    adjusted_document_id: str,
    scenario_id: str,
    filename: str,
    scenario_type: str = "adjustment_invoice",
    adjusted_snapshot: dict[str, Any] | None = None,
) -> Path:
    documents_dir = batch_dir / "documents"

    def find_document_dir(document_id: str) -> Path:
        for manifest_path in documents_dir.rglob("manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if manifest.get("document_id") == document_id:
                return manifest_path.parent
        raise FileNotFoundError(f"Document bundle not found: {document_id}")

    root_dir = find_document_dir(root_document_id)
    adjusted_dir = find_document_dir(adjusted_document_id)
    root_doc = json.loads((root_dir / "canonical.json").read_text(encoding="utf-8"))
    adjusted_doc = adjusted_snapshot or json.loads((adjusted_dir / "canonical.json").read_text(encoding="utf-8"))
    xml_path = adjusted_dir / filename
    write_adjustment_scenario_xml(root_doc, adjusted_doc, scenario_id, xml_path, scenario_type)
    ET.parse(xml_path)
    _refresh_manifest(adjusted_dir)
    manifest_path = adjusted_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["xml_artifact"] = filename
    manifest["scenario_xml_structure"] = {
        "root": root_document_id,
        "adjusted": adjusted_document_id,
    }
    if (adjusted_dir / "adjusted_state.json").is_file():
        manifest["scenario_snapshot_artifact"] = "adjusted_state.json"
        manifest["artifact_consistency"] = "generated_from_scenario_canonical_snapshot"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return xml_path


def build_dataset_index(batch_dir: Path) -> Path:
    documents_dir = batch_dir / "documents"
    entries = []
    if documents_dir.exists():
        for canonical_path in sorted(documents_dir.rglob("canonical.json")):
            document_dir = canonical_path.parent
            try:
                canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
                manifest_path = document_dir / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            entries.append({
                "document_id": canonical.get("document_id"),
                "document_type": canonical.get("document_type"),
                "relative_path": document_dir.relative_to(batch_dir).as_posix(),
                "folder_name": document_dir.name,
                "filename_code": manifest.get("filename_code"),
                "artifacts": sorted(manifest.get("artifacts", {}).keys()),
                "validation_status": manifest.get("validation_status"),
                "schema_verified": manifest.get("schema_verified", False),
                "xml_schema_verified": manifest.get("xml_schema_verified", False),
            })

    index = {
        "batch_id": batch_dir.name,
        "document_count": len(entries),
        "documents": entries,
    }
    path = batch_dir / "dataset_index.json"
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return path



def create_upload_archive(batch_dir: Path, document_ids: set[str] | None = None) -> Path:
    """Package only original PDF/XML inputs; never leak Ground Truth labels."""
    import zipfile

    archive = batch_dir.with_name(batch_dir.name + "-upload.zip")
    documents_dir = batch_dir / "documents"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for manifest_path in sorted(documents_dir.rglob("manifest.json")):
            document_dir = manifest_path.parent
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            document_id = manifest.get("document_id")
            if not document_id or (document_ids is not None and document_id not in document_ids):
                continue
            for relative in manifest.get("artifacts", {}):
                source = document_dir / relative
                if source.suffix.lower() not in {".pdf", ".xml"}:
                    continue
                if source.name == "invoice_scan.pdf" or source.name.endswith("_scan.pdf") or "corrupted" in source.name:
                    continue
                if source.is_file():
                    archive_name = (
                        document_dir.relative_to(batch_dir) / relative
                    ).as_posix()
                    output.write(source, archive_name)
    return archive
