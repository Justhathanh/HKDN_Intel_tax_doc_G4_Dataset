from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

from dataset_generator.exporters import write_bundle, write_corrupted_bundle
from dataset_generator.factory import create_sample_invoice
from dataset_generator.model import Party
from dataset_generator.registry import DOCUMENT_TYPE_REGISTRY
from dataset_generator.validation import validate_invoice

ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "configs"
COMPANY_FILE = CONFIG_DIR / "companies.json"
OUTPUT_ROOT = ROOT / "datasets" / "companies"

DEFAULT_COMPANIES = [
    {
        "id": "company-a",
        "name": "Công ty mẫu A",
        "legal_name": "CÔNG TY TNHH THƯƠNG MẠI MẪU A (DỮ LIỆU GIẢ LẬP)",
        "tax_code": "9901111222",
        "address": "Địa chỉ giả lập, TP. Hồ Chí Minh",
        "industry": "Thương mại",
        "active": True,
    },
    {
        "id": "company-b",
        "name": "Công ty mẫu B",
        "legal_name": "CÔNG TY CỔ PHẦN DỊCH VỤ MẪU B (DỮ LIỆU GIẢ LẬP)",
        "tax_code": "9902222333",
        "address": "Địa chỉ giả lập, TP. Hà Nội",
        "industry": "Dịch vụ",
        "active": True,
    },
    {
        "id": "company-c",
        "name": "Công ty mẫu C",
        "legal_name": "CÔNG TY TNHH SẢN XUẤT MẪU C (DỮ LIỆU GIẢ LẬP)",
        "tax_code": "9903333444",
        "address": "Địa chỉ giả lập, TP. Đà Nẵng",
        "industry": "Sản xuất",
        "active": True,
    },
]


def load_companies() -> list[dict]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not COMPANY_FILE.exists():
        save_companies(DEFAULT_COMPANIES)
    try:
        data = json.loads(COMPANY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else DEFAULT_COMPANIES
    except (OSError, json.JSONDecodeError):
        return DEFAULT_COMPANIES


def save_companies(companies: list[dict]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    COMPANY_FILE.write_text(json.dumps(companies, ensure_ascii=False, indent=2), encoding="utf-8")


def slug(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "company"


def create_batch(company: dict, document_type: str, direction: str, count: int, seed: int, include_negative: bool) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    batch_id = f"{document_type}-{timestamp}-{uuid.uuid4().hex[:6]}"
    batch_dir = OUTPUT_ROOT / company["id"] / document_type / direction / batch_id
    batch_dir.mkdir(parents=True, exist_ok=False)

    generated = []
    seen: set[tuple[str, str]] = set()
    for i in range(count):
        current_seed = seed + i
        invoice = create_sample_invoice(current_seed, scenario="valid")
        selected_party = Party(
            name=company["legal_name"],
            address=company["address"],
            tax_code=company["tax_code"],
        )
        if direction == "incoming":
            invoice.buyer = selected_party
        else:
            invoice.seller = selected_party
        invoice.extra["pilot_company"] = {
            "company_id": company["id"],
            "display_name": company["name"],
            "industry": company.get("industry", ""),
            "invoice_direction": direction,
        }
        errors = validate_invoice(invoice, seen_references=seen)
        if errors:
            raise ValueError("; ".join(errors))
        seen.add((invoice.series, invoice.invoice_number))
        write_bundle(invoice, batch_dir / invoice.document_id)
        generated.append(invoice.document_id)

    negative_count = 0
    if include_negative:
        cases = ["missing_buyer_name", "invalid_tax_code", "negative_qty", "duplicate_reference"]
        for j, case in enumerate(cases):
            invoice = create_sample_invoice(seed + 1000 + j, scenario="valid")
            selected_party = Party(company["legal_name"], company["address"], company["tax_code"])
            if direction == "incoming":
                invoice.buyer = selected_party
            else:
                invoice.seller = selected_party
            # Apply the negative mutation after assigning the selected company.
            from dataset_generator.factory import mutate_invoice
            invoice = mutate_invoice(invoice, seed=seed + 1000 + j, error_kind=case)
            if case == "duplicate_reference" and seen:
                invoice.series, invoice.invoice_number = next(iter(seen))
            invoice.extra["pilot_company"] = {
                "company_id": company["id"],
                "display_name": company["name"],
                "industry": company.get("industry", ""),
            }
            errors = validate_invoice(invoice, seen_references=seen)
            write_bundle(invoice, batch_dir / invoice.document_id, validation_errors=errors)
            negative_count += 1

        for case in ("empty_pdf", "fake_pdf_text", "malformed_xml"):
            write_corrupted_bundle(batch_dir / f"corrupted-{case}", case_name=case)
            negative_count += 1

    metadata = {
        "batch_id": batch_id,
        "company": {k: company.get(k) for k in ("id", "name", "legal_name", "tax_code", "industry")},
        "document_type": document_type,
        "invoice_direction": direction,
        "synthetic": True,
        "seed": seed,
        "valid_count": count,
        "negative_count": negative_count,
        "created_at": datetime.now().astimezone().isoformat(),
        "documents": generated,
        "notice": "Synthetic data only. Not real invoices and not valid for tax/legal use.",
    }
    (batch_dir / "batch_manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    zip_path = shutil.make_archive(str(batch_dir), "zip", root_dir=str(batch_dir))
    return Path(zip_path)


def main() -> None:
    st.set_page_config(page_title="THTAX Dataset Studio", page_icon="🧾", layout="wide")
    st.title("THTAX Dataset Studio")
    st.caption("Quản lý công ty mẫu · Sinh chứng từ giả lập · Chuẩn bị dữ liệu kiểm thử OCR")
    st.warning("Dữ liệu tạo bởi ứng dụng là dữ liệu giả lập, không phải chứng từ thật và không có giá trị pháp lý.")

    companies = load_companies()
    active = [c for c in companies if c.get("active", True)]
    tab_generate, tab_companies, tab_output = st.tabs(["Tạo dữ liệu", "Quản lý công ty", "Kho dữ liệu"])

    with tab_generate:
        left, right = st.columns([1.1, 1])
        with left:
            st.subheader("1. Chọn công ty")
            if not active:
                st.info("Chưa có công ty đang hoạt động. Hãy tạo công ty trong tab Quản lý công ty.")
                selected = None
            else:
                labels = {f'{c["name"]} · {c["industry"]}': c for c in active}
                selected_label = st.selectbox("Đơn vị dữ liệu", list(labels))
                selected = labels[selected_label]
                st.write(f'**Mã số thuế mẫu:** `{selected["tax_code"]}`')
                st.write(f'**Tên pháp lý:** {selected["legal_name"]}')
        with right:
            st.subheader("2. Chọn loại chứng từ")
            supported = [k for k, spec in DOCUMENT_TYPE_REGISTRY.items() if spec.status == "supported"]
            selected_type = st.selectbox(
                "Loại chứng từ",
                supported,
                format_func=lambda key: DOCUMENT_TYPE_REGISTRY[key].display_name,
            )
            st.caption(DOCUMENT_TYPE_REGISTRY[selected_type].description)
            direction = st.selectbox(
                "Chiều hóa đơn",
                ["incoming", "outgoing"],
                format_func=lambda x: "Đầu vào · Công ty được chọn là bên mua" if x == "incoming" else "Đầu ra · Công ty được chọn là bên bán",
            )
            st.caption("Các loại đang needs_review/planned sẽ chỉ mở khi schema và quy tắc được xác minh.")

        st.divider()
        st.subheader("3. Cấu hình đợt generate")
        c1, c2, c3 = st.columns(3)
        with c1:
            count = st.number_input("Số chứng từ hợp lệ", min_value=1, max_value=500, value=10, step=1)
        with c2:
            seed = st.number_input("Seed", min_value=1, max_value=2_000_000_000, value=42, step=1)
        with c3:
            include_negative = st.checkbox("Tạo thêm bộ dữ liệu lỗi", value=True)
        st.caption("Bộ lỗi hiện gồm lỗi nghiệp vụ và file hỏng. Không trộn các mẫu lỗi vào tập đánh giá OCR sạch.")
        if st.button("Tạo dataset", type="primary", disabled=selected is None, use_container_width=True):
            with st.spinner("Đang tạo tài liệu, Ground Truth và Manifest..."):
                try:
                    archive = create_batch(selected, selected_type, direction, int(count), int(seed), include_negative)
                    st.success("Đã tạo dataset.")
                    st.code(str(archive.relative_to(ROOT)))
                    st.download_button(
                        "Tải dataset ZIP",
                        data=archive.read_bytes(),
                        file_name=archive.name,
                        mime="application/zip",
                        use_container_width=True,
                    )
                except Exception as exc:
                    st.error(f"Không thể tạo dataset: {exc}")

    with tab_companies:
        st.subheader("Danh sách công ty")
        st.caption("Ba công ty ban đầu chỉ là hồ sơ giả lập để thử giao diện. Thay bằng thông tin đã được phê duyệt khi cần.")
        for company in companies:
            with st.expander(f'{company["name"]} · {company["tax_code"]}'):
                st.write(f'**Tên pháp lý:** {company["legal_name"]}')
                st.write(f'**Ngành:** {company.get("industry", "")}')
                st.write(f'**Trạng thái:** {"Đang hoạt động" if company.get("active", True) else "Đã lưu trữ"}')
                if st.button("Lưu trữ / kích hoạt", key=f'toggle-{company["id"]}'):
                    company["active"] = not company.get("active", True)
                    save_companies(companies)
                    st.rerun()

        st.divider()
        st.subheader("Thêm công ty")
        with st.form("new-company", clear_on_submit=True):
            name = st.text_input("Tên hiển thị *")
            legal_name = st.text_input("Tên pháp lý *")
            tax_code = st.text_input("Mã số thuế *")
            address = st.text_area("Địa chỉ")
            industry = st.selectbox("Ngành nghề", ["Thương mại", "Dịch vụ", "Sản xuất", "Vận tải", "Công nghệ", "Khác"])
            submitted = st.form_submit_button("Thêm công ty")
            if submitted:
                if not name.strip() or not legal_name.strip() or not tax_code.strip():
                    st.error("Tên hiển thị, tên pháp lý và mã số thuế là bắt buộc.")
                elif any(c["tax_code"] == tax_code.strip() for c in companies):
                    st.error("Mã số thuế đã tồn tại trong danh sách.")
                else:
                    companies.append({
                        "id": f'{slug(name)}-{uuid.uuid4().hex[:6]}',
                        "name": name.strip(), "legal_name": legal_name.strip(),
                        "tax_code": tax_code.strip(), "address": address.strip(),
                        "industry": industry, "active": True,
                    })
                    save_companies(companies)
                    st.success("Đã thêm công ty.")
                    st.rerun()

    with tab_output:
        st.subheader("Kho dữ liệu đã tạo")
        if not OUTPUT_ROOT.exists():
            st.info("Chưa có dataset nào.")
        else:
            for manifest in sorted(OUTPUT_ROOT.glob("*/*/*/batch_manifest.json"), reverse=True):
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                    with st.expander(f'{data["company"]["name"]} · {data["document_type"]} · {data["batch_id"]}'):
                        st.write(f'Ngày tạo: {data["created_at"]}')
                        st.write(f'Số hợp lệ: {data["valid_count"]} · Số negative: {data["negative_count"]}')
                        archive = manifest.parent.with_suffix(".zip")
                        if archive.exists():
                            st.download_button("Tải ZIP", archive.read_bytes(), file_name=archive.name, key=f'dl-{data["batch_id"]}')
                except (OSError, json.JSONDecodeError, KeyError):
                    st.warning(f"Manifest không đọc được: {manifest}")


if __name__ == "__main__":
    main()
