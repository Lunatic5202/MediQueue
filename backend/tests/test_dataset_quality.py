"""Tests for the aggregate offline generic-CSV quality audit."""

from __future__ import annotations

import pandas as pd

from mediqueue.training.dataset_quality import audit_generic_csv


def _csv(tmp_path, rows, columns=None):
    path = tmp_path / "training.csv"
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
    return path


def _row(**overrides):
    row = {
        "patient_id": "synthetic-1",
        "vital_type": "heart_rate",
        "value": 80,
        "unit": "bpm",
        "device_ts": "2026-01-01T00:00:00Z",
        "label": 0,
    }
    row.update(overrides)
    return row


def test_quality_audit_reports_clean_dataset(tmp_path):
    report = audit_generic_csv(_csv(tmp_path, [_row(), _row(patient_id="synthetic-2")]))

    assert report["status"] == "ok"
    assert report["row_count"] == 2
    assert report["positive_label_rows"] == 0
    assert report["negative_label_rows"] == 2
    assert report["duplicate_observation_rows"] == 0


def test_quality_audit_detects_invalid_values_labels_units_and_timestamps(tmp_path):
    report = audit_generic_csv(
        _csv(
            tmp_path,
            [
                _row(value="not-a-number"),
                _row(patient_id="synthetic-2", label=0.5),
                _row(patient_id="synthetic-3", unit="seconds"),
                _row(patient_id="synthetic-4", device_ts="not-a-time"),
            ],
        )
    )

    assert report["status"] == "error"
    assert report["invalid_numeric_value_rows"] == 1
    assert report["invalid_label_rows"] == 1
    assert report["unit_mismatch_rows"] == 1
    assert report["invalid_timestamp_rows"] == 1


def test_quality_audit_flags_duplicate_observation_keys(tmp_path):
    report = audit_generic_csv(_csv(tmp_path, [_row(), _row(value=90)]))

    assert report["status"] == "warning"
    assert report["duplicate_observation_rows"] == 1
    assert report["warnings"]


def test_quality_audit_rejects_missing_required_columns(tmp_path):
    report = audit_generic_csv(_csv(tmp_path, [{"patient_id": "synthetic-1"}]))

    assert report["status"] == "error"
    assert "value" in report["missing_columns"]
    assert "missing required columns" in report["errors"]


def test_quality_audit_does_not_include_patient_identifiers(tmp_path):
    secret_id = "synthetic-private-identifier"
    report = audit_generic_csv(_csv(tmp_path, [_row(patient_id=secret_id, value="bad")]))

    assert secret_id not in str(report)
