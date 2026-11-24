
from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

import streamlit as st

from dataset_generator.batch_generator import create_batch
from dataset_generator.registry import DOCUMENT_TYPE_REGISTRY


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

    COMPANY_FILE.write_text(
        json.dumps(companies, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def slug(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "company"


def get_batch_manifests() -> list[Path]:
    """Tìm Manifest của cả Batch mới và cấu trúc dữ liệu cũ."""
    if not OUTPUT_ROOT.exists():
        return []

    manifests = set(OUTPUT_ROOT.glob("*/BATCH-*/batch_manifest.json"))
    manifests.update(OUTPUT_ROOT.glob("*/*/*/*/batch_manifest.json"))

    return sorted(
        manifests,
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def delete_batch_files(manifest_path: Path) -> None:
    """Delete one generated batch and its ZIPs, restricted to OUTPUT_ROOT."""
    manifest_path = manifest_path.resolve()
    output_root = OUTPUT_ROOT.resolve()
    batch_dir = manifest_path.parent
    try:
        batch_dir.relative_to(output_root)
    except ValueError as exc:
        raise ValueError("Batch path is outside the dataset storage directory") from exc

    if manifest_path.name != "batch_manifest.json" or not batch_dir.name.startswith("BATCH-"):
        raise ValueError("Invalid batch manifest path")
    if not manifest_path.is_file():
        raise FileNotFoundError("Batch manifest no longer exists")

    shutil.rmtree(batch_dir)
    for suffix in (".zip", "-upload.zip"):
        archive = batch_dir.with_name(batch_dir.name + suffix)
        if archive.is_file():
            archive.unlink()


def render_generate_tab(active: list[dict]) -> None:
    left, right = st.columns([1.1, 1])

    with left:
        st.subheader("1. Chọn công ty")

        if not active:
            st.info(
                "Chưa có công ty đang hoạt động. "
                "Hãy tạo công ty trong tab Quản lý công ty."
            )
            selected = None
        else:
            labels = {
                f'{company["name"]} · {company["industry"]}': company
                for company in active
            }

            selected_label = st.selectbox(
                "Đơn vị dữ liệu",
                list(labels),
            )
            selected = labels[selected_label]

            st.write(f'**Mã số thuế mẫu:** `{selected["tax_code"]}`')
            st.write(f'**Tên pháp lý:** {selected["legal_name"]}')

    with right:
        st.subheader("2. Chọn loại chứng từ")

        allow_unverified = st.checkbox(
            "Cho phép sinh chứng từ chưa xác minh schema",
            value=False,
            help=(
                "Cho phép tạo dữ liệu tham khảo cho các loại needs_review. "
                "Các mẫu này không được xem là đã xác minh pháp lý."
            ),
        )

        available_types = [
            key
            for key, spec in DOCUMENT_TYPE_REGISTRY.items()
            if spec.status == "supported"
            or (
                allow_unverified
                and spec.status == "needs_review"
            )
        ]

        selected_types = st.multiselect(
            "Các loại chứng từ trong Batch",
            options=available_types,
            default=(
                ["vat_invoice"]
                if "vat_invoice" in available_types
                else []
            ),
            format_func=lambda key: (
                f"{DOCUMENT_TYPE_REGISTRY[key].display_name}"
                f" · {DOCUMENT_TYPE_REGISTRY[key].status}"
            ),
        )

        for type_key in selected_types:
            spec = DOCUMENT_TYPE_REGISTRY[type_key]

            with st.expander(spec.display_name):
                st.write(spec.description)
                st.caption(
                    f"Trạng thái: {spec.status} · "
                    f"{'Core/MVP' if spec.in_mvp else 'Extended'}"
                )

        adjustment_original_type = "vat_invoice"
        if "adjustment_invoice" in selected_types:
            adjustment_original_type = st.selectbox(
                "Loại hóa đơn gốc cho kịch bản điều chỉnh",
                options=["vat_invoice", "sales_invoice"],
                format_func=lambda value: (
                    "Hóa đơn GTGT" if value == "vat_invoice" else "Hóa đơn bán hàng"
                ),
                help="Hóa đơn gốc và trạng thái sau điều chỉnh sẽ giữ cùng loại. Sales Invoice là dữ liệu Extended chưa xác minh schema pháp lý.",
            )

        direction = st.selectbox(
            "Vai trò công ty mẫu trong hóa đơn",
            ["incoming", "outgoing"],
            format_func=lambda value: (
                "Đầu vào · Công ty là bên mua/nhận"
                if value == "incoming"
                else "Đầu ra · Công ty là bên bán/phát hành"
            ),
        )

        st.caption(
            "Vai trò công ty chỉ được áp dụng cho các loại hóa đơn "
            "phù hợp. Các chứng từ hành chính giữ nguyên vai trò "
            "bên phát hành và bên nhận."
        )

    st.divider()
    st.subheader("3. Cấu hình Batch")

    col1, col2, col3 = st.columns(3)

    with col1:
        count = st.number_input(
            "Số chứng từ hợp lệ cho mỗi loại",
            min_value=1,
            max_value=500,
            value=10,
            step=1,
        )

    with col2:
        seed = st.number_input(
            "Seed",
            min_value=1,
            max_value=2_000_000_000,
            value=42,
            step=1,
        )

    with col3:
        include_negative = st.checkbox(
            "Tạo thêm bộ dữ liệu lỗi",
            value=True,
            disabled="vat_invoice" not in selected_types,
            help=(
                "Negative samples hiện chỉ hỗ trợ VAT Invoice."
            ),
        )

    if "vat_invoice" not in selected_types:
        st.caption(
            "Chưa chọn VAT Invoice: không tạo negative samples."
        )

    st.caption(
        "Bộ dữ liệu lỗi gồm lỗi nghiệp vụ và file hỏng. "
        "Không trộn các mẫu lỗi vào tập đánh giá OCR sạch."
    )

    if selected_types:
        requested_total = len(selected_types) * int(count)
        scenario_originals = sum(
            1 for key in selected_types
            if key in {"adjustment_invoice", "replacement_invoice"}
        ) * int(count)
        total = requested_total + scenario_originals
        st.info(
            f"Dự kiến tạo {total} chứng từ gốc/liên kết "
            f"({requested_total} chứng từ được chọn + "
            f"{scenario_originals} hóa đơn gốc cho scenario)."
        )
    else:
        st.info("Hãy chọn ít nhất một loại chứng từ.")

    if st.button(
        "Tạo dataset",
        type="primary",
        disabled=selected is None or not selected_types,
        use_container_width=True,
    ):
        with st.spinner(
            "Đang tạo chứng từ, Ground Truth, Manifest và ZIP..."
        ):
            try:
                archive = create_batch(
                    company=selected,
                    document_types=selected_types,
                    direction=direction,
                    count_per_type=int(count),
                    seed=int(seed),
                    include_negative=include_negative,
                    allow_unverified=allow_unverified,
                    adjustment_original_type=adjustment_original_type,
                )

                st.success("Đã tạo dataset.")

                try:
                    st.code(str(archive.relative_to(ROOT)))
                except ValueError:
                    st.code(str(archive))

                st.download_button(
                    "Tải Full Dataset (kèm Ground Truth)",
                    data=archive.read_bytes(),
                    file_name=archive.name,
                    mime="application/zip",
                    use_container_width=True,
                )

                upload_archive = archive.with_name(
                    archive.stem + "-upload.zip"
                )
                if upload_archive.exists():
                    st.download_button(
                        "Tải Upload Dataset (chỉ PDF/XML đầu vào)",
                        data=upload_archive.read_bytes(),
                        file_name=upload_archive.name,
                        mime="application/zip",
                        use_container_width=True,
                        help="Không chứa Ground Truth, canonical data hoặc file scan/negative.",
                    )

            except Exception as exc:
                st.error(f"Không thể tạo dataset: {exc}")


def render_companies_tab(companies: list[dict]) -> None:
    st.subheader("Danh sách công ty")

    st.caption(
        "Các công ty ban đầu là hồ sơ giả lập để thử giao diện. "
        "Không sử dụng dữ liệu này như thông tin doanh nghiệp thật."
    )

    for company in companies:
        with st.expander(
            f'{company["name"]} · {company["tax_code"]}'
        ):
            st.write(f'**Tên pháp lý:** {company["legal_name"]}')
            st.write(f'**Ngành:** {company.get("industry", "")}')

            st.write(
                "**Trạng thái:** "
                + (
                    "Đang hoạt động"
                    if company.get("active", True)
                    else "Đã lưu trữ"
                )
            )

            if st.button(
                "Lưu trữ / kích hoạt",
                key=f'toggle-{company["id"]}',
            ):
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

        industry = st.selectbox(
            "Ngành nghề",
            [
                "Thương mại",
                "Dịch vụ",
                "Sản xuất",
                "Vận tải",
                "Công nghệ",
                "Khác",
            ],
        )

        submitted = st.form_submit_button("Thêm công ty")

        if submitted:
            if (
                not name.strip()
                or not legal_name.strip()
                or not tax_code.strip()
            ):
                st.error(
                    "Tên hiển thị, tên pháp lý và mã số thuế là bắt buộc."
                )

            elif any(
                company["tax_code"] == tax_code.strip()
                for company in companies
            ):
                st.error(
                    "Mã số thuế đã tồn tại trong danh sách."
                )

            else:
                companies.append(
                    {
                        "id": f"{slug(name)}-{uuid.uuid4().hex[:6]}",
                        "name": name.strip(),
                        "legal_name": legal_name.strip(),
                        "tax_code": tax_code.strip(),
                        "address": address.strip(),
                        "industry": industry,
                        "active": True,
                    }
                )

                save_companies(companies)
                st.success("Đã thêm công ty.")
                st.rerun()


def render_output_tab() -> None:
    st.subheader("Kho dữ liệu đã tạo")

    manifests = get_batch_manifests()

    if not manifests:
        st.info("Chưa có dataset nào.")
        return

    for manifest in manifests:
        try:
            data = json.loads(
                manifest.read_text(encoding="utf-8")
            )

            company = data.get("company", {})
            company_name = company.get("name", "Unknown")
            batch_id = data.get("batch_id", manifest.parent.name)

            document_types = data.get(
                "document_types",
                [data.get("document_type", "Unknown")],
            )

            type_label = ", ".join(document_types)

            with st.expander(
                f"{company_name} · {type_label} · {batch_id}"
            ):
                st.write(
                    f'Ngày tạo: {data.get("created_at", "Unknown")}'
                )

                st.write(
                    f'Số hợp lệ: {data.get("valid_count", 0)}'
                    f' · Số negative: {data.get("negative_count", 0)}'
                )

                valid_by_type = data.get("valid_count_by_type")

                if valid_by_type:
                    st.write("Số lượng theo loại:")
                    st.json(valid_by_type)

                status_by_type = data.get("document_type_status")

                if status_by_type:
                    st.write("Trạng thái Registry:")
                    st.json(status_by_type)

                archive = manifest.parent.with_suffix(".zip")

                if archive.exists():
                    st.download_button(
                        "Tải Full Dataset",
                        data=archive.read_bytes(),
                        file_name=archive.name,
                        mime="application/zip",
                        key=f"dl-full-{batch_id}",
                    )

                upload_archive = archive.with_name(
                    archive.stem + "-upload.zip"
                )
                if upload_archive.exists():
                    st.download_button(
                        "Tải Upload Dataset",
                        data=upload_archive.read_bytes(),
                        file_name=upload_archive.name,
                        mime="application/zip",
                        key=f"dl-upload-{batch_id}",
                        help="Chỉ chứa PDF/XML đầu vào; không kèm Ground Truth.",
                    )

                st.divider()
                confirm_delete = st.checkbox(
                    "Tôi xác nhận xóa vĩnh viễn batch này khỏi máy",
                    key=f"confirm-delete-{batch_id}",
                )
                if st.button(
                    "Xóa batch",
                    key=f"delete-batch-{batch_id}",
                    type="secondary",
                    disabled=not confirm_delete,
                ):
                    try:
                        delete_batch_files(manifest)
                        st.success(f"Đã xóa batch {batch_id} và các file ZIP.")
                        st.rerun()
                    except (OSError, ValueError) as exc:
                        st.error(f"Không thể xóa batch: {exc}")

                validation_report = (
                    manifest.parent / "validation_report.json"
                )

                if validation_report.exists():
                    with st.expander("Xem Validation Report"):
                        report_data = json.loads(
                            validation_report.read_text(
                                encoding="utf-8"
                            )
                        )
                        st.json(report_data)

        except (OSError, json.JSONDecodeError, KeyError) as exc:
            st.warning(
                f"Không đọc được Manifest {manifest}: {exc}"
            )


def main() -> None:
    st.set_page_config(
        page_title="THTAX Dataset Studio",
        page_icon="🧾",
        layout="wide",
    )

    st.title("THTAX Dataset Studio")

    st.caption(
        "Quản lý công ty mẫu · Sinh nhiều loại chứng từ giả lập "
        "· Chuẩn bị dữ liệu kiểm thử OCR"
    )

    st.warning(
        "Dữ liệu tạo bởi ứng dụng là dữ liệu giả lập, "
        "không phải chứng từ thật và không có giá trị pháp lý."
    )

    companies = load_companies()
    active = [
        company
        for company in companies
        if company.get("active", True)
    ]

    tab_generate, tab_companies, tab_output = st.tabs(
        [
            "Tạo dữ liệu",
            "Quản lý công ty",
            "Kho dữ liệu",
        ]
    )

    with tab_generate:
        render_generate_tab(active)

    with tab_companies:
        render_companies_tab(companies)

    with tab_output:
        render_output_tab()


if __name__ == "__main__":
    main()
