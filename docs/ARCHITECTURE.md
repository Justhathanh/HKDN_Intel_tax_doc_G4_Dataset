# Architecture

## Responsibilities
- generator/core: generation orchestration and canonical document model.
- generator/document_types: per-document-type definitions and rules.
- generator/templates: visual layouts for PDF/image rendering.
- generator/exporters: XML, PDF and image serialization.
- schemas: versioned schemas and mapping references.
- ground_truth: expected field values and document-level labels.
- manifests: dataset inventory, lineage and checksums.

## Data flow
Input Config -> Document Type Definition -> Canonical Model -> Exporters -> Ground Truth + Manifest -> QA

All output formats for one document must derive from the same canonical instance. Do not independently generate values in each exporter.

## Boundaries
- The generator creates synthetic source documents; it does not implement THTAX ingestion.
- The THTAX backend remains the authority for its Core API contract.
- Legal schema validation is separate from visual template similarity.
- Unsupported document types must be explicitly labelled, not silently mapped to another type.
