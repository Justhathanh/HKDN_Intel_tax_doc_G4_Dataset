import json

import pytest

from dataset_generator import web_app


def test_delete_batch_removes_only_selected_batch_and_archives(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "OUTPUT_ROOT", tmp_path / "datasets")
    batch_dir = web_app.OUTPUT_ROOT / "company-a" / "BATCH-20261125-abc123"
    batch_dir.mkdir(parents=True)
    manifest = batch_dir / "batch_manifest.json"
    manifest.write_text("{}", encoding="utf-8")

    full_zip = batch_dir.with_name(batch_dir.name + ".zip")
    upload_zip = batch_dir.with_name(batch_dir.name + "-upload.zip")
    full_zip.write_bytes(b"full")
    upload_zip.write_bytes(b"upload")

    other_batch = web_app.OUTPUT_ROOT / "company-a" / "BATCH-20261125-other"
    other_batch.mkdir(parents=True)
    (other_batch / "batch_manifest.json").write_text("{}", encoding="utf-8")

    web_app.delete_batch_files(manifest)

    assert not batch_dir.exists()
    assert not full_zip.exists()
    assert not upload_zip.exists()
    assert other_batch.exists()


def test_delete_batch_rejects_path_outside_dataset_root(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "OUTPUT_ROOT", tmp_path / "datasets")
    outside_batch = tmp_path / "outside" / "BATCH-20261125-abc123"
    outside_batch.mkdir(parents=True)
    manifest = outside_batch / "batch_manifest.json"
    manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="outside"):
        web_app.delete_batch_files(manifest)

    assert outside_batch.exists()


def test_delete_selected_batches_removes_all_selected_and_preserves_others(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "OUTPUT_ROOT", tmp_path / "datasets")
    manifests = []
    for batch_id in ("BATCH-20261125-one", "BATCH-20261125-two"):
        batch_dir = web_app.OUTPUT_ROOT / "company-a" / batch_id
        batch_dir.mkdir(parents=True)
        manifest = batch_dir / "batch_manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        batch_dir.with_name(batch_id + ".zip").write_bytes(b"full")
        batch_dir.with_name(batch_id + "-upload.zip").write_bytes(b"upload")
        manifests.append(manifest)

    untouched = web_app.OUTPUT_ROOT / "company-b" / "BATCH-20261125-keep"
    untouched.mkdir(parents=True)
    (untouched / "batch_manifest.json").write_text("{}", encoding="utf-8")

    assert web_app.delete_selected_batches(manifests) == 2
    assert all(not manifest.parent.exists() for manifest in manifests)
    assert untouched.exists()


def test_delete_selected_batches_validates_all_before_deleting(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "OUTPUT_ROOT", tmp_path / "datasets")
    valid = web_app.OUTPUT_ROOT / "company-a" / "BATCH-20261125-valid"
    valid.mkdir(parents=True)
    valid_manifest = valid / "batch_manifest.json"
    valid_manifest.write_text("{}", encoding="utf-8")

    invalid = tmp_path / "outside" / "BATCH-20261125-invalid"
    invalid.mkdir(parents=True)
    invalid_manifest = invalid / "batch_manifest.json"
    invalid_manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="outside"):
        web_app.delete_selected_batches([valid_manifest, invalid_manifest])
    assert valid.exists()


def test_delete_company_removes_profile_and_all_company_datasets(tmp_path, monkeypatch):
    output_root = tmp_path / "datasets"
    monkeypatch.setattr(web_app, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(web_app, "CONFIG_DIR", tmp_path / "configs")
    monkeypatch.setattr(web_app, "COMPANY_FILE", tmp_path / "configs" / "companies.json")

    companies = [
        {"id": "company-a", "name": "Company A"},
        {"id": "company-b", "name": "Company B"},
    ]
    web_app.save_companies(companies)

    company_dir = output_root / "company-a"
    batch_dir = company_dir / "BATCH-20261125-abc123"
    batch_dir.mkdir(parents=True)
    (batch_dir / "batch_manifest.json").write_text("{}", encoding="utf-8")
    (company_dir / "BATCH-20261125-abc123.zip").write_bytes(b"full")

    other_company_dir = output_root / "company-b"
    other_company_dir.mkdir(parents=True)
    (other_company_dir / "keep.txt").write_text("keep", encoding="utf-8")

    remaining = web_app.delete_company("company-a", companies)

    assert remaining == [{"id": "company-b", "name": "Company B"}]
    assert not company_dir.exists()
    assert other_company_dir.exists()
    assert json.loads(web_app.COMPANY_FILE.read_text(encoding="utf-8")) == remaining


def test_delete_company_rejects_unknown_or_unsafe_company_id(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "OUTPUT_ROOT", tmp_path / "datasets")
    companies = [{"id": "company-a"}]

    with pytest.raises(ValueError, match="does not exist"):
        web_app.delete_company("company-missing", companies)
    with pytest.raises(ValueError, match="Invalid company ID"):
        web_app.delete_company("../outside", companies)
