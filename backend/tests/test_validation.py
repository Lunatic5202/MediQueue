"""Module 2 tests: schema/range/unit/timestamp validation and normalization."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from mediqueue.modules.validation import (
    ValidationError,
    compute_idempotency_key,
    validate_and_normalize,
)

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def test_valid_hr_observation_normalizes():
    obs = validate_and_normalize(
        {
            "patient_id": "p1",
            "vital_type": "heart_rate",
            "value": 88,
            "unit": "beats/min",
            "device_timestamp": (NOW - timedelta(minutes=1)).isoformat(),
        },
        now=NOW,
    )
    assert obs.unit == "bpm"
    assert obs.value == 88.0
    assert obs.device_ts == NOW - timedelta(minutes=1)
    assert obs.ingest_ts == NOW
    assert obs.idempotency_key == compute_idempotency_key(
        "p1", "heart_rate", NOW - timedelta(minutes=1), "device"
    )


def test_temperature_fahrenheit_converts_to_celsius():
    obs = validate_and_normalize(
        {
            "patient_id": "p1",
            "vital_type": "temperature",
            "value": 98.6,
            "unit": "°F",
            "device_timestamp": NOW.isoformat(),
        },
        now=NOW,
    )
    assert obs.unit == "°C"
    assert abs(obs.value - 37.0) < 0.01


def test_ambiguous_unit_rejected():
    with pytest.raises(ValidationError) as exc:
        validate_and_normalize(
            {
                "patient_id": "p1",
                "vital_type": "heart_rate",
                "value": 80,
                "unit": "beats",  # ambiguous
                "device_timestamp": NOW.isoformat(),
            },
            now=NOW,
        )
    assert exc.value.code == "ambiguous_or_unknown_unit"


def test_unitless_spo2_rejected():
    with pytest.raises(ValidationError) as exc:
        validate_and_normalize(
            {
                "patient_id": "p1",
                "vital_type": "spo2",
                "value": 98,
                "unit": "unitless",
                "device_timestamp": NOW.isoformat(),
            },
            now=NOW,
        )
    assert exc.value.code == "ambiguous_or_unknown_unit"


def test_out_of_range_rejected_not_clamped():
    with pytest.raises(ValidationError) as exc:
        validate_and_normalize(
            {
                "patient_id": "p1",
                "vital_type": "heart_rate",
                "value": 350,
                "unit": "bpm",
                "device_timestamp": NOW.isoformat(),
            },
            now=NOW,
        )
    assert exc.value.code == "out_of_range"


def test_spo2_above_100_rejected():
    with pytest.raises(ValidationError):
        validate_and_normalize(
            {
                "patient_id": "p1",
                "vital_type": "spo2",
                "value": 101,
                "unit": "%",
                "device_timestamp": NOW.isoformat(),
            },
            now=NOW,
        )


def test_bp_requires_diastolic_and_sys_greater_than_dia():
    with pytest.raises(ValidationError) as exc:
        validate_and_normalize(
            {
                "patient_id": "p1",
                "vital_type": "blood_pressure",
                "value": 120,
                "unit": "mmHg",
                "device_timestamp": NOW.isoformat(),
            },
            now=NOW,
        )
    assert exc.value.code == "missing_field"

    with pytest.raises(ValidationError):
        validate_and_normalize(
            {
                "patient_id": "p1",
                "vital_type": "blood_pressure",
                "value": 80,
                "value_diastolic": 120,
                "unit": "mmHg",
                "device_timestamp": NOW.isoformat(),
            },
            now=NOW,
        )


def test_diastolic_only_on_bp():
    with pytest.raises(ValidationError):
        validate_and_normalize(
            {
                "patient_id": "p1",
                "vital_type": "heart_rate",
                "value": 80,
                "value_diastolic": 60,
                "unit": "bpm",
                "device_timestamp": NOW.isoformat(),
            },
            now=NOW,
        )


def test_future_timestamp_rejected():
    with pytest.raises(ValidationError) as exc:
        validate_and_normalize(
            {
                "patient_id": "p1",
                "vital_type": "heart_rate",
                "value": 80,
                "unit": "bpm",
                "device_timestamp": (NOW + timedelta(hours=1)).isoformat(),
            },
            now=NOW,
        )
    assert exc.value.code == "timestamp_in_future"


def test_missing_required_field_rejected():
    with pytest.raises(ValidationError) as exc:
        validate_and_normalize(
            {"patient_id": "p1", "vital_type": "heart_rate", "value": 80, "unit": "bpm"},
            now=NOW,
        )
    assert exc.value.code == "missing_field"


def test_invalid_vital_type_rejected():
    with pytest.raises(ValidationError) as exc:
        validate_and_normalize(
            {
                "patient_id": "p1",
                "vital_type": "respiratory_rate",
                "value": 16,
                "unit": "bpm",
                "device_timestamp": NOW.isoformat(),
            },
            now=NOW,
        )
    assert exc.value.code == "invalid_vital_type"


def test_non_finite_value_rejected():
    with pytest.raises(ValidationError):
        validate_and_normalize(
            {
                "patient_id": "p1",
                "vital_type": "heart_rate",
                "value": float("nan"),
                "unit": "bpm",
                "device_timestamp": NOW.isoformat(),
            },
            now=NOW,
        )


def test_idempotency_key_is_deterministic():
    ts = NOW - timedelta(minutes=3)
    k1 = compute_idempotency_key("p", "spo2", ts, "device")
    k2 = compute_idempotency_key("p", "spo2", ts, "device")
    k3 = compute_idempotency_key("p", "spo2", ts, "other")
    assert k1 == k2
    assert k1 != k3
