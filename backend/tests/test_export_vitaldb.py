"""Regression tests for the optional VitalDB adapter without the vitaldb package."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "export_vitaldb.py"
SPEC = importlib.util.spec_from_file_location("export_vitaldb", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def test_exports_available_measurements_and_skips_missing_values():
    samples = [[80, 98, 120, 80, 36.7], [float("nan"), 97, 120, float("nan"), 36.8]]
    output = StringIO()
    count = adapter.write_payloads(samples, output, 12, datetime(2024, 1, 1, tzinfo=UTC), 60)
    lines = [json.loads(line) for line in output.getvalue().splitlines()]
    assert count == 6
    assert [item["vital_type"] for item in lines] == ["heart_rate", "spo2", "temperature", "blood_pressure", "spo2", "temperature"]
    assert lines[0]["device_timestamp"] == "2024-01-01T00:00:00Z"
    assert lines[4]["device_timestamp"] == "2024-01-01T00:01:00Z"
    assert lines[3]["value_diastolic"] == 80.0
    assert all("vitaldb-case-12" not in item["patient_id"] for item in lines)


def test_rejects_samples_with_missing_track_columns():
    import pytest
    with pytest.raises(ValueError, match="five requested track columns"):
        adapter.write_payloads([[80, 98]], StringIO(), 1, datetime(2024, 1, 1, tzinfo=UTC), 60)


def test_start_time_requires_timezone():
    import pytest
    with pytest.raises(ValueError, match="include a timezone"):
        adapter.parse_start_time("2024-01-01T00:00:00")
