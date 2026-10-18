"""Regression tests for the offline observation exporter."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "export_observations.py"
SPEC = importlib.util.spec_from_file_location("export_observations", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


def row(**overrides):
    result = {
        "patient_id": "source-patient-17",
        "vital_type": "heart_rate",
        "value": "88",
        "unit": "bpm",
        "device_ts": "2024-01-01T12:00:00Z",
        "value_diastolic": "",
    }
    result.update(overrides)
    return result


def test_converts_to_api_payload_and_hashes_patient_id():
    payload = exporter.convert_row(row(), 2, "offline", "test-import")

    assert payload == {
        "patient_id": exporter.patient_key("source-patient-17", "offline"),
        "vital_type": "heart_rate",
        "value": 88.0,
        "unit": "bpm",
        "device_timestamp": "2024-01-01T12:00:00Z",
        "source_id": "test-import",
    }
    assert "source-patient-17" not in payload["patient_id"]


def test_rejects_missing_csv_cell_instead_of_stringifying_none():
    with pytest.raises(ValueError, match="patient_id"):
        exporter.convert_row(row(patient_id=None), 3, "offline", "test-import")


def test_rejects_timezone_naive_timestamp():
    with pytest.raises(ValueError, match="include a timezone"):
        exporter.convert_row(row(device_ts="2024-01-01T12:00:00"), 4, "offline", "test-import")


def test_blood_pressure_requires_diastolic():
    with pytest.raises(ValueError, match="requires value_diastolic"):
        exporter.convert_row(
            row(vital_type="blood_pressure", unit="mmHg", value="120"),
            5, "offline", "test-import"
        )


def test_rejects_non_finite_values():
    with pytest.raises(ValueError, match="finite"):
        exporter.convert_row(row(value="nan"), 6, "offline", "test-import")
