# Dataset Generator — XML, Scenario and Export Contract

## 1. Canonical source

PDF, XML and Ground Truth must be generated from the same per-document `canonical.json`.
The XML currently uses `thtax-synthetic-internal-v1`: it is well-formed XML for parser/integration testing, **not** a verified Vietnamese tax XML schema. Keep `xml_schema_verified=false` and `xml_schema_version=null` until an authoritative schema/version has been reviewed.

## 2. Per-document artifacts

Each valid document bundle contains:
- PDF source representation (`invoice.pdf` for Core VAT; `document.pdf` for Extended).
- `document.xml`, serialized from canonical data.
- `canonical.json`, `ground_truth.json`, `manifest.json`.
- OCR derivatives such as `invoice_scan.pdf` and `images/`.

The manifest records artifact path, MIME type, byte size and SHA-256. It also records the XML format, well-formedness, schema-verification state and canonical-source relationship.

## 3. Adjustment and replacement scenarios

Adjustment and replacement documents are generated with an original VAT invoice in the same Batch:
- `scenario_id` groups the pair.
- Original invoice has role `original`.
- Related document has role `adjustment` or `replacement` and points to the original using `references_document_id`.
- Adjustment stores an absolute adjustment amount plus a signed business delta. Expected final total is original total plus signed delta.
- Replacement stores the replacement total. Expected final total equals the replacement total; the original is superseded and is not added to it.

These are synthetic scenario semantics for testing relationships and calculations, not a claim of legal compliance.

## 4. Batch exports

### Full Dataset
Contains generated source files, OCR derivatives, canonical data, Ground Truth, per-document manifests, batch manifest, validation report and dataset index. Use this for internal QA and evaluation.

### Upload Dataset
Contains only original PDF/XML inputs for valid generated document bundles. It excludes Ground Truth, canonical JSON, scan derivatives and corrupted-format fixtures to prevent label leakage into the ingestion pipeline. Keep Full Dataset as the evaluation reference.

## 5. Scope labels

Registry status remains independent from generator availability. A generated Extended sample is still marked unverified until its schema and business rules have been reviewed. Core/Pilot and Extended must not be conflated in reports.


## Short filenames and adjustment scenario pair

Generated source filenames use a document-type prefix and a reproducible three-digit code derived from the batch seed, for example `tax_invoice387.pdf` and `tax_invoice387.xml`. The same code is reused for both members of a linked adjustment/replacement scenario:
- `adjustment_invoice387_root.pdf`: original invoice PDF.
- `adjustment_invoice387_adjusted.pdf`: adjusted invoice PDF.
- `adjustment_invoice387_root.xml`: standalone original XML.
- `adjustment_invoice387.xml`: one scenario XML containing both `Root` and `Adjusted` document nodes.

The combined scenario XML is stored with the adjusted document and its artifact entry is recorded in that document's manifest. The Windows Explorer "Type" label can show the default associated application (for example Microsoft Edge); verify the actual file extension is `.xml` and inspect the XML declaration/content rather than relying on that label.
