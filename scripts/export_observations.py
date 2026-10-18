#!/usr/bin/env python3
"""Convert a normalized long-format CSV into MediQueue observation NDJSON.

This is an offline adapter only: it does not call the API, register patients,
or write to the database. Input data must already be de-identified and mapped
to MediQueue's supported vital names/units. Keep source datasets out of Git.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = {"patient_id", "vital_type", "value", "unit", "device_ts"}
VITAL_UNITS = {
    "heart_rate": {"bpm", "beats/min", "beats_per_minute", "beats per minute", "/min"},
    "spo2": {"%", "percent", "percentage", "pct"},
    "blood_pressure": {
        "mmhg", "mm hg", "mm_hg", "millimeterhg", "millimeters of mercury"
    },
    "temperature": {
        "°c", "c", "celsius", "degc", "deg c", "°f", "f", "fahrenheit", "degf", "deg f"
    },
}


def parse_timestamp(raw: str, row_number: int) -> str:
    try:
        value = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"row {row_number}: device_ts must be an ISO-8601 timestamp") from exc
    if value.tzinfo is None:
        raise ValueError(f"row {row_number}: device_ts must include a timezone (for example Z)")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def patient_key(raw: str, prefix: str) -> str:
    """Create a stable pseudonymous ID so raw IDs are not copied into output."""
    digest = hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def convert_row(row: dict[str, Any], row_number: int, prefix: str, source_id: str) -> dict[str, Any]:
    missing = [name for name in REQUIRED_COLUMNS if not str(row.get(name, "")).strip()]
    if missing:
        raise ValueError(f"row {row_number}: missing value(s) for {', '.join(sorted(missing))}")

    vital = str(row["vital_type"]).strip().lower()
    if vital not in VITAL_UNITS:
        raise ValueError(f"row {row_number}: unsupported vital_type {vital!r}")

    unit = str(row["unit"]).strip()
    if unit.lower() not in VITAL_UNITS[vital]:
        raise ValueError(f"row {row_number}: unsupported unit {unit!r} for {vital}")

    try:
        value = float(row["value"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_number}: value must be numeric") from exc
    if not math.isfinite(value):
        raise ValueError(f"row {row_number}: value must be finite")

    payload = {
        "patient_id": patient_key(str(row["patient_id"]), prefix),
        "vital_type": vital,
        "value": value,
        "unit": unit,
        "device_timestamp": parse_timestamp(str(row["device_ts"]), row_number),
        "source_id": source_id,
    }

    raw_diastolic = row.get("value_diastolic")
    if vital == "blood_pressure":
        if raw_diastolic is None or not str(raw_diastolic).strip():
            raise ValueError(f"row {row_number}: blood_pressure requires value_diastolic")
        try:
            diastolic = float(raw_diastolic)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"row {row_number}: value_diastolic must be numeric") from exc
        if not math.isfinite(diastolic):
            raise ValueError(f"row {row_number}: value_diastolic must be finite")
        payload["value_diastolic"] = diastolic
    elif raw_diastolic is not None and str(raw_diastolic).strip():
        raise ValueError(f"row {row_number}: value_diastolic is only valid for blood_pressure")

    return payload


def convert_file(
    input_path: Path, output: Any, prefix: str, source_id: str, limit: int | None = None
) -> int:
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

        count = 0
        for row_number, row in enumerate(reader, start=2):
            if limit is not None and count >= limit:
                break
            payload = convert_row(row, row_number, prefix, source_id)
            output.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", type=Path, help="de-identified normalized long-format CSV")
    parser.add_argument("-o", "--output", type=Path, default=None, help="output NDJSON path (default: stdout)")
    parser.add_argument("--id-prefix", default="offline", help="prefix for hashed patient IDs (max 43 chars)")
    parser.add_argument("--source-id", default="offline-import", help="MediQueue source_id (max 64 chars)")
    parser.add_argument("--limit", type=int, default=None, help="convert at most N rows for a small test")
    args = parser.parse_args()

    if not args.id_prefix or len(args.id_prefix) > 43:
        parser.error("--id-prefix must contain 1..43 characters")
    if not args.source_id or len(args.source_id) > 64:
        parser.error("--source-id must contain 1..64 characters")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be >= 1")

    try:
        if args.output:
            with args.output.open("w", encoding="utf-8", newline="") as handle:
                count = convert_file(args.input_csv, handle, args.id_prefix, args.source_id, args.limit)
        else:
            count = convert_file(args.input_csv, sys.stdout, args.id_prefix, args.source_id, args.limit)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Converted {count} rows. Output contains observation payloads only; no API calls were made.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
