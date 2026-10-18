"""Tests for the offline NDJSON validator."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_observations.py"
SPEC = importlib.util.spec_from_file_location("validate_observations", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)

NOW = datetime(2026, 10, 18, tzinfo=UTC)


def test_accepts_valid_observation_and_reports_quality_summary(tmp_path):
    source = tmp_path / "observations.ndjson"
    source.write_text(
        '{"patient_id":"offline-demo","vital_type":"heart_rate","value":80,'
        '"unit":"bpm","device_timestamp":"2024-01-01T00:00:00Z"}\n'
        '{"patient_id":"offline-demo","vital_type":"heart_rate","value":95,'
        '"unit":"bpm","device_timestamp":"2024-01-01T00:01:00Z"}\n'
        '{"patient_id":"offline-demo","vital_type":"blood_pressure","value":120,'
        '"value_diastolic":80,"unit":"mmHg","device_timestamp":"2024-01-01T00:02:00Z"}\n',
        encoding="utf-8",
    )
    output = StringIO()
    assert validator.validate_file(source, output, now=NOW) == (3, 0)
    report = output.getvalue()
    assert "3 valid, 0 invalid" in report
    assert "heart_rate: 2 valid" in report
    assert "value range 80.00–95.00 bpm" in report
    assert "blood_pressure: 1 valid" in report
    assert "diastolic range 80.00–80.00 mmHg" in report
    assert "timestamps 2024-01-01T00:00:00Z to 2024-01-01T00:01:00Z" in report


def test_reports_invalid_range_and_malformed_json_without_patient_ids(tmp_path):
    source = tmp_path / "observations.ndjson"
    source.write_text(
        '{"patient_id":"private-demo","vital_type":"spo2","value":120,'
        '"unit":"%","device_timestamp":"2024-01-01T00:00:00Z"}\n'
        '{not-json}\n',
        encoding="utf-8",
    )
    output = StringIO()
    assert validator.validate_file(source, output, now=NOW) == (0, 2)
    report = output.getvalue()
    assert "line 1: " in report and "outside plausible range" in report
    assert "line 2: invalid JSON" in report
    assert "private-demo" not in report


def test_ignores_blank_lines(tmp_path):
    source = tmp_path / "observations.ndjson"
    source.write_text("\n  \n", encoding="utf-8")
    assert validator.validate_file(source, StringIO(), now=NOW) == (0, 0)
