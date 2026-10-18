"""Module 2: Validation & Normalization.

Rejects malformed or ambiguous input rather than silently correcting it.
Out-of-range measurements are rejected (never clamped). Supported units are
normalized to the canonical unit for each vital type.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

CANONICAL_UNITS = {
    "heart_rate": "bpm",
    "spo2": "%",
    "blood_pressure": "mmHg",
    "temperature": "°C",
}

# Accepted (unit alias -> canonical). Anything else, including ambiguous
# aliases such as "deg" or unitless spo2, is rejected.
UNIT_ALIASES: dict[str, dict[str, str]] = {
    "heart_rate": {
        "bpm": "bpm",
        "beats/min": "bpm",
        "beats_per_minute": "bpm",
        "beats per minute": "bpm",
        "/min": "bpm",
    },
    "spo2": {
        "%": "%",
        "percent": "%",
        "percentage": "%",
        "pct": "%",
    },
    "blood_pressure": {
        "mmhg": "mmHg",
        "mm hg": "mmHg",
        "mm_hg": "mmHg",
        "millimeterhg": "mmHg",
        "millimeters of mercury": "mmHg",
    },
    "temperature": {
        "°c": "°C",
        "c": "°C",
        "celsius": "°C",
        "degc": "°C",
        "deg c": "°C",
        "°f": "°F",
        "f": "°F",
        "fahrenheit": "°F",
        "degf": "°F",
        "deg f": "°F",
    },
}

# Plausibility limits (configurable in a production design; fixed here).
# (min, max) in the canonical unit.
PLAUSIBILITY: dict[str, tuple[float, float]] = {
    "heart_rate": (20.0, 300.0),
    "spo2": (50.0, 100.0),
    "blood_pressure_systolic": (40.0, 300.0),
    "blood_pressure_diastolic": (20.0, 200.0),
    "temperature": (25.0, 45.0),
}

# Tolerance for device timestamps slightly ahead of the server clock.
FUTURE_TOLERANCE = timedelta(minutes=5)


class ValidationError(Exception):
    """Raised when an observation fails validation. Carries an HTTP-ready code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class NormalizedObservation:
    patient_id: str
    vital_type: str
    value: float
    value_diastolic: float | None
    unit: str
    device_ts: datetime
    ingest_ts: datetime
    source_id: str
    idempotency_key: str


def _parse_timestamp(raw: Any, field_name: str) -> datetime:
    if raw is None:
        raise ValidationError("missing_field", f"{field_name} is required")
    if isinstance(raw, datetime):
        ts = raw
    elif isinstance(raw, str):
        text = raw.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            ts = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValidationError(
                "invalid_timestamp", f"{field_name} is not a valid ISO-8601 timestamp"
            ) from exc
    else:
        raise ValidationError("invalid_timestamp", f"{field_name} has unsupported type")
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def compute_idempotency_key(
    patient_id: str, vital_type: str, device_ts: datetime, source_id: str
) -> str:
    ts = device_ts.astimezone(timezone.utc).isoformat()
    return f"{patient_id}|{vital_type}|{ts}|{source_id}"


def _normalize_unit(vital_type: str, raw_unit: str) -> str:
    key = raw_unit.strip().lower()
    aliases = UNIT_ALIASES.get(vital_type, {})
    canonical = aliases.get(key)
    if canonical is None:
        raise ValidationError(
            "ambiguous_or_unknown_unit",
            f"Unit {raw_unit!r} is unknown or ambiguous for {vital_type}; "
            "supported units: " + ", ".join(sorted(aliases)),
        )
    return canonical


def _check_range(name: str, value: float) -> None:
    lo, hi = PLAUSIBILITY[name]
    if not (lo <= value <= hi):
        raise ValidationError(
            "out_of_range",
            f"{name} value {value} outside plausible range [{lo}, {hi}]; not clamped",
        )


def validate_and_normalize(payload: dict[str, Any], now: datetime | None = None) -> NormalizedObservation:
    """Validate schema, ranges, units, and timestamps; return a normalized row.

    Raises ValidationError on any failure. Never silently corrects ambiguous
    units or out-of-range measurements.
    """
    now = now or datetime.now(timezone.utc)

    for required in ("patient_id", "vital_type", "value", "unit", "device_timestamp"):
        if payload.get(required) is None:
            raise ValidationError("missing_field", f"{required} is required")

    patient_id = str(payload["patient_id"]).strip()
    if not patient_id or len(patient_id) > 64:
        raise ValidationError("invalid_field", "patient_id must be 1..64 characters")

    vital_type = str(payload["vital_type"]).strip().lower()
    if vital_type not in CANONICAL_UNITS:
        raise ValidationError(
            "invalid_vital_type",
            f"vital_type must be one of {sorted(CANONICAL_UNITS)}",
        )

    try:
        value = float(payload["value"])
    except (TypeError, ValueError) as exc:
        raise ValidationError("invalid_field", "value must be numeric") from exc
    if value != value or value in (float("inf"), float("-inf")):
        raise ValidationError("invalid_field", "value must be finite")

    value_diastolic: float | None = None
    raw_dia = payload.get("value_diastolic")
    if vital_type == "blood_pressure":
        if raw_dia is None:
            raise ValidationError(
                "missing_field", "value_diastolic is required for blood_pressure"
            )
        try:
            value_diastolic = float(raw_dia)
        except (TypeError, ValueError) as exc:
            raise ValidationError("invalid_field", "value_diastolic must be numeric") from exc
        if value_diastolic != value_diastolic:
            raise ValidationError("invalid_field", "value_diastolic must be finite")
    elif raw_dia is not None:
        raise ValidationError(
            "invalid_field",
            "value_diastolic is only valid for blood_pressure observations",
        )

    unit = _normalize_unit(vital_type, str(payload["unit"]))

    # Temperature conversion to Celsius.
    if vital_type == "temperature" and unit == "°F":
        value = (value - 32.0) * 5.0 / 9.0
        unit = "°C"

    device_ts = _parse_timestamp(payload["device_timestamp"], "device_timestamp")
    ingest_raw = payload.get("ingest_timestamp")
    ingest_ts = _parse_timestamp(ingest_raw, "ingest_timestamp") if ingest_raw else now
    if ingest_ts > now + FUTURE_TOLERANCE or device_ts > now + FUTURE_TOLERANCE:
        raise ValidationError(
            "timestamp_in_future",
            "device_timestamp/ingest_timestamp more than 5 minutes in the future",
        )

    source_id = str(payload.get("source_id") or "device").strip() or "device"
    if len(source_id) > 64:
        raise ValidationError("invalid_field", "source_id must be <= 64 characters")

    # Plausibility checks (canonical units).
    if vital_type == "heart_rate":
        _check_range("heart_rate", value)
    elif vital_type == "spo2":
        _check_range("spo2", value)
    elif vital_type == "temperature":
        _check_range("temperature", value)
    elif vital_type == "blood_pressure":
        _check_range("blood_pressure_systolic", value)
        _check_range("blood_pressure_diastolic", value_diastolic)
        if value <= value_diastolic:
            raise ValidationError(
                "invalid_field",
                "systolic must be greater than diastolic for blood_pressure",
            )

    key = compute_idempotency_key(patient_id, vital_type, device_ts, source_id)
    return NormalizedObservation(
        patient_id=patient_id,
        vital_type=vital_type,
        value=round(value, 6),
        value_diastolic=round(value_diastolic, 6) if value_diastolic is not None else None,
        unit=unit,
        device_ts=device_ts,
        ingest_ts=ingest_ts,
        source_id=source_id,
        idempotency_key=key,
    )
