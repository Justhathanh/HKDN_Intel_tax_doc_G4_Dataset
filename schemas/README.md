# Schema Registry

Store versioned schemas and mapping documentation here.

    schemas/
    ├── core/
    │   └── <core-contract-version>/
    ├── vietnam_tax/
    │   ├── <document-type>/
    │   │   └── <schema-version>/
    │   └── README.md
    └── mappings/
        └── <core-version>__<external-schema-version>/

Do not add a schema as authoritative until its source, effective date, document-type coverage and validation procedure have been reviewed. Never treat the historical QĐ 1450 schema as automatically current for every document type.
