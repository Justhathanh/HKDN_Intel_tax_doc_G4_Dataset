"""Synthetic XML serialization for Dataset Generator.

This is an internal test-data interchange format, NOT a legally verified
Vietnamese e-invoice XML schema.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _add(parent: ET.Element, name: str, value: Any) -> ET.Element:
    node = ET.SubElement(parent, name)
    node.text = "" if value is None else str(value)
    return node


def canonical_to_xml(document: dict[str, Any]) -> bytes:
    root = ET.Element("SyntheticTaxDocument", {
        "formatVersion": "1.0",
        "schemaStatus": "unverified",
        "synthetic": "true",
    })
    _add(root, "DocumentId", document.get("document_id"))
    _add(root, "DocumentType", document.get("document_type"))
    _add(root, "IssueDate", document.get("issue_date"))

    if "seller" in document:
        parties = ET.SubElement(root, "Parties")
        for role in ("seller", "buyer"):
            party = document.get(role) or {}
            node = ET.SubElement(parties, role.capitalize())
            for key in ("name", "tax_code", "address", "email"):
                if key in party:
                    _add(node, key, party.get(key))
    elif "issuer_name" in document:
        parties = ET.SubElement(root, "Parties")
        for role, prefix in (("Issuer", "issuer"), ("Recipient", "recipient")):
            node = ET.SubElement(parties, role)
            for key in ("name", "tax_code", "address"):
                source_key = f"{prefix}_{key}"
                if source_key in document:
                    _add(node, key, document.get(source_key))

    identity = ET.SubElement(root, "DocumentIdentity")
    for key in ("form_number", "series", "invoice_number", "reference_code"):
        value = document.get(key)
        if value is None:
            value = (document.get("metadata") or {}).get(key)
        if value is not None:
            _add(identity, key, value)

    metadata = document.get("metadata") or {}
    if metadata:
        meta_node = ET.SubElement(root, "Metadata")
        for key in sorted(metadata):
            _add(meta_node, key, metadata[key])

    items = document.get("lines", document.get("items", [])) or []
    items_node = ET.SubElement(root, "LineItems")
    for index, item in enumerate(items, 1):
        line = ET.SubElement(items_node, "Line", {"index": str(index)})
        for key, value in item.items():
            if isinstance(value, (dict, list)):
                value = str(value)
            _add(line, key, value)

    totals = document.get("totals")
    if totals is None:
        totals = {"total_amount": document.get("total_amount")}
        for key in ("subtotal", "vat_amount"):
            if key in metadata:
                totals[key] = metadata[key]
    totals_node = ET.SubElement(root, "Totals")
    for key, value in (totals or {}).items():
        _add(totals_node, key, value)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_canonical_xml(document: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_to_xml(document))
