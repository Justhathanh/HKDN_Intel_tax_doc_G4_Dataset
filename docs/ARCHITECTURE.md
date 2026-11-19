# Architecture

## Product outcome

The primary output is a visually complete synthetic Vietnamese VAT invoice PDF, not merely random JSON. XML, image variants and Ground Truth are generated from the same canonical invoice.

## Pipeline

```
CLI / config
  -> Invoice Type Registry
  -> Synthetic Party + Line Item Factory
  -> Canonical Invoice Model
  -> Legal/business validation
  -> PDF renderer (+ HTML template)
  -> XML exporter (blocked until schema profile is verified)
  -> PNG/JPG renderer + degradation profiles
  -> Ground Truth JSON + dataset manifest
  -> consistency QA
```

## Modules

- `models/`: canonical invoice and party/item/tax structures.
- `factories/`: deterministic synthetic data, seedable.
- `invoice_types/`: per-document-type field rules.
- `validation/`: business arithmetic, required-field and schema validation.
- `templates/`: visual document layout; separate from XML schema.
- `exporters/`: PDF, HTML, XML and image output.
- `ground_truth/`: exact expected field values from canonical data.
- `manifests/`: IDs, artifact paths, checksums and version lineage.

## Non-negotiable design rules

1. One canonical invoice instance is the source of every artifact.
2. Never infer official XML structure from a PDF screenshot or a legacy XSD.
3. Keep external legal invoice fields separate from THTAX internal metadata.
4. Keep legal schema version and THTAX Core contract version as separate version fields.
5. Do not fabricate tax authority codes, digital signatures, verification QR codes or official approval marks.
6. Every generated document is visibly marked as synthetic.
7. A rule is `verified` only when the source document and version are recorded; otherwise it is `needs_review`.

## Output bundle

```
datasets/samples/<dataset_id>/<document_id>/
  invoice.pdf
  invoice.html
  canonical.json
  ground_truth.json
  manifest.json
  invoice.xml          # only if a verified XML profile is enabled
  images/              # optional PNG/JPG and degradation variants
```

## Integration boundary

The generator owns document content and dataset labels. THTAX Core owns ingestion identifiers, upload metadata, processing state and API contract. Mapping is explicit in `schemas/thtax_core/field_mapping.yaml`; Core-only fields must not be printed on the invoice.
