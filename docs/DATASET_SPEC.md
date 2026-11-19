# Dataset Specification

## MVP document

Start with one Vietnamese VAT invoice (hóa đơn giá trị gia tăng) and generate a complete, printable PDF. Add sales invoice and adjustment/replacement invoices only after their field rules are reviewed.

## Bundle structure

```
datasets/samples/<dataset_id>/<document_id>/
  invoice.pdf
  invoice.html
  canonical.json
  ground_truth.json
  manifest.json
  invoice.xml          # optional, gated by verified schema
  images/
    page-001.png
    page-001_blur.jpg
```

## Identifiers and versioning

- `dataset_id`: stable batch identifier.
- `document_id`: UUID for one logical invoice.
- `document_type`: registry key, e.g. `vat_invoice`.
- `generator_version`: code release.
- `legal_profile_id` / `legal_profile_version`: applicable verified legal profile.
- `xml_schema_version`: exact XML message/schema version or null.
- `thtax_core_contract_version`: Core contract version or null until supplied.
- `seed`: deterministic generation seed.

## Ground Truth

Store field path, displayed/raw value, normalized value, presence, and field-level label. Store document-level label separately. Ground Truth must be generated from canonical data, never extracted back from PDF/image.

## Labels

`valid_synthetic`, `missing_required_field`, `invalid_format`, `inconsistent_totals`, `non_tax_document`, `low_quality_image`, `needs_review`. These are dataset QA labels, not tax authority statuses.

## Integrity

Manifest links every artifact to the same document_id and stores MIME type, SHA-256, generator version, seed and validation results.
