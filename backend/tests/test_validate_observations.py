"""Tests for the offline NDJSON validator."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from io import StringIO

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_observations.py"
SPEC = importlib.util.spec_from_file_location("validate_observations", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)

NOW = datetime(2026, 10, 18, tzinfo=UTC)


def test_accepts_valid_observation_and_reports_summary(tmp_path):
    source = tmp_path / "observations.ndjson"
    source.write_text(
        '{"patient_id":"offline-demo","vital_type":"heart_rate","value":80,'
        '"unit":"bpm","device_timestamp":"2024-01-01T00:00:00Z"}\n',
        encoding="utf-8",
    )
    output = StringIO()
    assert validator.validate_file(source, output, now=NOW) == (1, 0)
    assert "1 valid, 0 invalid" in output.getvalue()


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
