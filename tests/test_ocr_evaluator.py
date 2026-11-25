from dataset_generator.ocr.evaluator import evaluate_fields, normalize_text


def test_normalize_text_removes_vietnamese_diacritics():
    assert normalize_text("HÓA ĐƠN GIÁ TRỊ GIA TĂNG") == "hoa don gia tri gia tang"


def test_evaluate_fields_matches_displayed_or_normalized_values():
    ground_truth = {
        "fields": {
            "invoice_number": {
                "displayed": "00001234",
                "normalized": "00001234",
                "present": True,
            },
            "seller.name": {
                "displayed": "Công ty TNHH Ánh Dương",
                "normalized": "Công ty TNHH Ánh Dương",
                "present": True,
            },
            "issue_date": {
                "displayed": "26/07/2026",
                "normalized": "2026-07-26",
                "present": True,
            },
        }
    }
    result = evaluate_fields(
        "Số: 00001234\nCong ty TNHH Anh Duong\nNgay 26/07/2026",
        ground_truth,
    )
    assert result["evaluated_fields"] == 3
    assert result["passed_fields"] == 3
    assert result["field_accuracy"] == 1.0
    assert result["document_accuracy"] == 1.0


def test_evaluate_fields_reports_missing_value():
    result = evaluate_fields(
        "So: 123456",
        {"fields": {"invoice_number": {"displayed": "123456"},
                    "seller.name": {"displayed": "Cong ty ABC"}}},
    )
    assert result["passed_fields"] == 1
    assert result["failed_fields"] == 1
    assert result["document_accuracy"] == 0.0


def test_empty_ground_truth_returns_none_metrics():
    result = evaluate_fields("some text", {"fields": {}})
    assert result["evaluated_fields"] == 0
    assert result["field_accuracy"] is None
    assert result["document_accuracy"] is None
