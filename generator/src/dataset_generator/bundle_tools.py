"""Post-process generated document bundles with XML and integrity metadata."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .xml_exporter import write_canonical_xml


def add_xml_and_refresh_manifest(document_dir: Path) -> Path:
    canonical_path = document_dir / "canonical.json"
    if not canonical_path.is_file():
        raise FileNotFoundError(f"Missing canonical.json in {document_dir}")

    canonical: dict[str, Any] = json.loads(canonical_path.read_text(encoding="utf-8"))
    xml_path = document_dir / "document.xml"
    write_canonical_xml(canonical, xml_path)

    # Parse back to ensure the generated XML is well-formed.
    ET.parse(xml_path)

    manifest_path = document_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = {}
    for path in sorted(document_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            relative = path.relative_to(document_dir).as_posix()
            mime, _ = mimetypes.guess_type(path.name)
            artifacts[relative] = {
                "mime_type": mime or "application/octet-stream",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }

    manifest["artifacts"] = artifacts
    manifest["xml_artifact"] = "document.xml"
    manifest["xml_format"] = "thtax-synthetic-internal-v1"
    manifest["xml_schema_version"] = None
    manifest["xml_schema_verified"] = False
    manifest["xml_well_formed"] = True
    manifest["artifact_consistency"] = "generated_from_canonical_json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
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
