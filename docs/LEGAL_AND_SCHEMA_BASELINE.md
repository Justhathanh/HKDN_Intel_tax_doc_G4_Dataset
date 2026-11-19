# Legal and schema baseline (review required)

Last checked: 2026-11-20. This file is a research register, not a legal opinion.

## Confirmed references

| Instrument | Verified facts | Engineering implication |
|---|---|---|
| Nghị định 254/2026/NĐ-CP | Issued 30/06/2026; effective 01/07/2026; governs e-invoices/e-documents under the 2025 Tax Administration Law. | Use it as part of the current legal baseline. Article 10 fields must be reviewed against the full signed text before coding. |
| Thông tư 91/2026/TT-BTC | Issued 30/06/2026; effective 01/07/2026. | Review relevant provisions and annexes with Decree 254. |
| Quyết định 1233/QĐ-CT | Issued 27/08/2026; replaces QĐ1306/QĐ-CT; defines business data and transmission; transition accepts message versions 2.1.0 and 2.1.1, with 2.1.0 through 31/12/2026. | XML export must be version-profiled; do not hardcode one version as timeless. |

## Important invoice content to model

The published text of Decree 254 Article 10 identifies core invoice content including invoice name/form/series/number; seller and buyer identification; item name/unit/quantity/unit price/amount; VAT rate and tax totals; total payable; issue/signing timestamps; and tax authority code where applicable. Conditional fields must remain conditional, not universally required.

## Official references

- [Decree 254/2026/NĐ-CP — Government legal portal](https://vanban.chinhphu.vn/?classid=1&docid=218689&pageid=27160&typegroupid=4)
- [Circular 91/2026/TT-BTC — Government legal portal](https://vanban.chinhphu.vn/?classid=1&docid=219006&orggroupid=4&pageid=27160)
- [Decision 1233/QĐ-CT — text and annex reference](https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Quyet-dinh-1233-QD-CT-2026-thanh-phan-chua-du-lieu-nghiep-vu-hoa-don-chung-tu-dien-tu-722644.aspx)

## Not yet approved

- Exact XSD/message files and complete XML element mapping for each supported invoice type.
- Exact THTAX Core mandatory fields and API contract version.
- Applicability of legacy standards to each specific invoice profile.
- Tax-rate rules and exceptions for the generated business scenarios.

Do not mark XML as legally/schema valid until the actual schema file, source, version and validation tests are checked into the repository. Do not generate tax authority codes or signatures.
