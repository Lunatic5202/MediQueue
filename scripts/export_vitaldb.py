#!/usr/bin/env python3
"""Export selected VitalDB open-dataset numeric tracks as offline MediQueue NDJSON.

This optional adapter never calls MediQueue or writes to its database. VitalDB
timestamps are relative to case start, so --start-time is a user-supplied
synthetic UTC anchor for offline replay, not a recorded patient timestamp.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TextIO

DEFAULT_TRACKS = {
    "heart_rate": "Solar8000/HR",
    "spo2": "Solar8000/PLETH_SPO2",
    "systolic": "Solar8000/NIBP_SBP",
    "diastolic": "Solar8000/NIBP_DBP",
    "temperature": "Solar8000/BT",
}
TRACK_ORDER = tuple(DEFAULT_TRACKS)


def parse_start_time(raw: str) -> datetime:
    try:
        value = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("--start-time must be an ISO-8601 timestamp") from exc
    if value.tzinfo is None:
        raise ValueError("--start-time must include a timezone (for example Z)")
    return value.astimezone(UTC)


def patient_key(case_id: int, prefix: str) -> str:
    digest = hashlib.sha256(f"vitaldb-case-{case_id}".encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def write_payloads(samples: Any, output: TextIO, case_id: int, start_time: datetime, interval: float, id_prefix: str = "vitaldb", source_id: str = "vitaldb-offline") -> int:
    """Write rows from load_case() in TRACK_ORDER as API-shaped NDJSON."""
    patient_id = patient_key(case_id, id_prefix)
    count = 0
    for index, sample in enumerate(samples):
        values = list(sample)
        if len(values) < len(TRACK_ORDER):
            raise ValueError("VitalDB samples must contain all five requested track columns")
        timestamp = (start_time + timedelta(seconds=index * interval)).isoformat().replace("+00:00", "Z")
        measurements = {name: _finite(values[pos]) for pos, name in enumerate(TRACK_ORDER)}
        payloads: list[dict[str, Any]] = []
        for vital_type in ("heart_rate", "spo2", "temperature"):
            value = measurements[vital_type]
            if value is not None:
                unit = {"heart_rate": "bpm", "spo2": "%", "temperature": "°C"}[vital_type]
                payloads.append({"patient_id": patient_id, "vital_type": vital_type, "value": value, "unit": unit, "device_timestamp": timestamp, "source_id": source_id})
        systolic, diastolic = measurements["systolic"], measurements["diastolic"]
        if systolic is not None and diastolic is not None:
            payloads.append({"patient_id": patient_id, "vital_type": "blood_pressure", "value": systolic, "value_diastolic": diastolic, "unit": "mmHg", "device_timestamp": timestamp, "source_id": source_id})
        for payload in payloads:
            output.write(json.dumps(payload, separators=(",", ":")) + "\n")
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", type=int, required=True, help="VitalDB open-dataset case ID")
    parser.add_argument("--start-time", required=True, help="synthetic timezone-aware UTC anchor, e.g. 2024-01-01T00:00:00Z")
    parser.add_argument("--interval", type=float, default=60, help="sampling interval in seconds (default: 60)")
    parser.add_argument("-o", "--output", type=Path, default=None, help="output NDJSON path (default: stdout)")
    parser.add_argument("--id-prefix", default="vitaldb", help="prefix for pseudonymous patient IDs (max 43 chars)")
    parser.add_argument("--source-id", default="vitaldb-offline", help="source_id in emitted payloads (max 64 chars)")
    for key, default in DEFAULT_TRACKS.items():
        option_name = key.replace("_", "-")
        parser.add_argument(f"--{option_name}-track", default=default, help=f"VitalDB track name for {key}")
    args = parser.parse_args()
    if args.interval <= 0 or not math.isfinite(args.interval):
        parser.error("--interval must be a finite number greater than zero")
    if not args.id_prefix or len(args.id_prefix) > 43:
        parser.error("--id-prefix must contain 1..43 characters")
    if not args.source_id or len(args.source_id) > 64:
        parser.error("--source-id must contain 1..64 characters")
    try:
        start_time = parse_start_time(args.start_time)
    except ValueError as exc:
        parser.error(str(exc))
    track_names = [getattr(args, f"{key}_track") for key in TRACK_ORDER]
    try:
        import vitaldb
    except ImportError:
        print("error: install the optional dependency with: python -m pip install vitaldb", file=sys.stderr)
        return 2
    try:
        samples = vitaldb.load_case(args.case_id, track_names, interval=args.interval)
        if samples is None:
            raise ValueError("VitalDB returned no samples for this case/tracks")
        if args.output:
            with args.output.open("w", encoding="utf-8", newline="") as handle:
                count = write_payloads(samples, handle, args.case_id, start_time, args.interval, args.id_prefix, args.source_id)
        else:
            count = write_payloads(samples, sys.stdout, args.case_id, start_time, args.interval, args.id_prefix, args.source_id)
    except (OSError, ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Exported {count} offline observation payloads from VitalDB case {args.case_id}; no API calls were made.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
