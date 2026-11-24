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

Adjustment documents can be generated with either an original VAT invoice or an original Sales Invoice in the same Batch. The Streamlit UI exposes this choice when `adjustment_invoice` is selected. The chosen original type is preserved in the root document, adjusted snapshot and scenario XML. Replacement scenarios currently continue to use an original VAT invoice:
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


## Document folders and short filenames

Both Full Dataset and Upload Dataset ZIPs expose one top-level folder per document directly under `documents/`. The folder name is based on the document type and its random three-digit human-lookup code, for example `tax_invoice387/` or `sales_invoice142/`. Related artifacts in that document bundle use the same prefix and code, including PDF, XML, scan PDF and page images.

The stable identity remains `document_id`, not the filename code. Each per-document `manifest.json`, the batch manifest and `dataset_index.json` retain the document ID and map it to `folder_name` and `relative_path`. The three-digit code is randomly selected from 001–999, is not derived from the batch seed, and collisions across documents or batches are allowed.

If two documents in the same batch have the same type and random code, the folder name receives a collision suffix such as `tax_invoice027__2/`. The code itself remains unchanged and collisions remain allowed; the suffix only prevents files from overwriting each other.

For adjustment/replacement scenarios, each document ID has its own folder. The original VAT invoice is stored in a `tax_invoiceNNN/` folder with `tax_invoiceNNN_root.pdf` and `tax_invoiceNNN_root.xml`. The related adjustment/replacement document is stored in its own type folder, such as `adjustment_invoiceNNN/`, with its role-specific PDF (for example `adjustment_invoiceNNN_adjustment.pdf` and `adjustment_invoiceNNN_adjusted.pdf`, or `replacement_invoiceNNN_replacement.pdf`) and scenario XML. Both folders share the scenario's three-digit lookup code. The batch manifest links them using `scenario_id`, `document_id` and `related_document_id`.

The combined scenario XML is stored with the adjustment/replacement document and its artifact entry is recorded in that document's manifest. The Windows Explorer "Type" label can show the default associated application (for example Microsoft Edge); verify the actual file extension and inspect the XML declaration/content rather than relying on that label.


## 6. Local dataset cleanup

The **Kho dữ liệu** tab provides a per-batch delete action. The user must explicitly confirm before deletion. The operation removes only the selected batch directory and its adjacent Full Dataset and Upload Dataset ZIP files, and validates that the target is inside `datasets/companies/`. It does not delete source code, other batches or GitHub history. Generated company datasets and ZIP archives are ignored by `.gitignore`.
