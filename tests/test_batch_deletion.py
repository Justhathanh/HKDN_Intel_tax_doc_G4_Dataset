from pathlib import Path

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
