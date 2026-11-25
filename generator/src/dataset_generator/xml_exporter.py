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


def _append_value(parent: ET.Element, name: str, value: Any) -> ET.Element:
    if isinstance(value, dict):
        node = ET.SubElement(parent, name)
        for child_name, child_value in value.items():
            _append_value(node, str(child_name), child_value)
        return node
    if isinstance(value, list):
        node = ET.SubElement(parent, name)
        for item in value:
            _append_value(node, "Item", item)
        return node
    return _add(parent, name, value)


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
            for key in ("name", "tax_code", "address", "email"):
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

    metadata = document.get("metadata") or document.get("extra") or {}
    if metadata:
        meta_node = ET.SubElement(root, "Metadata")
        for key in sorted(metadata):
            _append_value(meta_node, key, metadata[key])

    items = document.get("lines", document.get("items", [])) or []
    items_node = ET.SubElement(root, "LineItems")
    for index, item in enumerate(items, 1):
        line = ET.SubElement(items_node, "Line", {"index": str(index)})
        for key, value in item.items():
            _append_value(line, key, value)

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




def adjustment_scenario_to_xml(
    root_document: dict[str, Any],
    adjusted_document: dict[str, Any],
    scenario_id: str,
    scenario_type: str = "adjustment_invoice",
) -> bytes:
    """Serialize root + adjusted documents into one scenario XML file."""

    def normalize_scenario_parties(document: dict[str, Any]) -> dict[str, Any]:
        """Normalize legacy seller/buyer parties to issuer/recipient."""
        normalized = dict(document)

        if "seller" in normalized or "buyer" in normalized:
            seller = normalized.pop("seller", None) or {}
            buyer = normalized.pop("buyer", None) or {}

            for role, party in (
                ("issuer", seller),
                ("recipient", buyer),
            ):
                for field in ("name", "tax_code", "address", "email"):
                    if field in party:
                        normalized[f"{role}_{field}"] = party[field]

        return normalized

    root = ET.Element("SyntheticAdjustmentScenario", {
        "formatVersion": "1.0",
        "schemaStatus": "unverified",
        "synthetic": "true",
    })

    _add(root, "ScenarioId", scenario_id)
    _add(root, "ScenarioType", scenario_type)

    root_node = ET.SubElement(root, "Root")
    root_normalized = normalize_scenario_parties(root_document)
    root_node.append(
        ET.fromstring(canonical_to_xml(root_normalized))
    )

    adjusted_node = ET.SubElement(root, "Adjusted")
    adjusted_normalized = normalize_scenario_parties(adjusted_document)
    adjusted_node.append(
        ET.fromstring(canonical_to_xml(adjusted_normalized))
    )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)



def write_adjustment_scenario_xml(
    root_document: dict[str, Any],
    adjusted_document: dict[str, Any],
    scenario_id: str,
    path: Path,
    scenario_type: str = "adjustment_invoice",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        adjustment_scenario_to_xml(
            root_document,
            adjusted_document,
            scenario_id,
            scenario_type,
        )
    )
