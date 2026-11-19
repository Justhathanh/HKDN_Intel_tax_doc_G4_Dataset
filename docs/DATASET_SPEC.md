# Dataset Specification

## Required identifiers
- dataset_id: stable identifier for one generated dataset batch.
- document_id: unique identifier for one logical document.
- document_type: registry key, e.g. invoice_gtgt.
- generator_version: version of generator code/configuration.
- schema_version: exact schema/contract version, or null while unconfirmed.
- split: optional train/validation/test assignment.

## Required artifacts
Each logical document should have:
- canonical input data;
- one Ground Truth JSON;
- zero or more visual artifacts (PDF, PNG, JPG);
- XML only where an applicable XML schema and mapping have been confirmed;
- manifest entry linking every artifact.

## Ground Truth principles
Ground Truth records exact expected values, normalized values where relevant, field presence, confidence-independent labels, and document-level validity. Preserve original displayed text separately from normalized values when normalization is needed.

## Quality labels
Suggested labels: valid, invalid_schema, missing_required_field, inconsistent_values, non_tax_document, low_quality_image, needs_review.

These are dataset QA labels, not official tax authority statuses.
