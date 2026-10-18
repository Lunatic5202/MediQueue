#!/usr/bin/env python3
"""Validate offline MediQueue observation NDJSON without calling the API."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

# Allow running this script directly from a source checkout.
BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from mediqueue.modules.validation import ValidationError, validate_and_normalize  # noqa: E402


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _record_stats(stats: dict[str, dict[str, Any]], observation: Any) -> None:
    item = stats.setdefault(
        observation.vital_type,
        {
            "count": 0,
            "unit": observation.unit,
            "min": observation.value,
            "max": observation.value,
            "first": observation.device_ts,
            "last": observation.device_ts,
            "diastolic_min": observation.value_diastolic,
            "diastolic_max": observation.value_diastolic,
        },
    )
    item["count"] += 1
    item["min"] = min(item["min"], observation.value)
    item["max"] = max(item["max"], observation.value)
    item["first"] = min(item["first"], observation.device_ts)
    item["last"] = max(item["last"], observation.device_ts)
    if observation.value_diastolic is not None:
        current_min = item["diastolic_min"]
        current_max = item["diastolic_max"]
        item["diastolic_min"] = (
            observation.value_diastolic
            if current_min is None
            else min(current_min, observation.value_diastolic)
        )
        item["diastolic_max"] = (
            observation.value_diastolic
            if current_max is None
            else max(current_max, observation.value_diastolic)
        )


def validate_file(path: Path, output: TextIO, now: datetime | None = None) -> tuple[int, int]:
    """Return (valid, invalid) counts; report aggregate stats, never patient IDs."""
    valid = 0
    invalid = 0
    stats: dict[str, dict[str, Any]] = {}
    now = now or datetime.now(UTC)
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
                if not isinstance(payload, dict):
                    raise ValueError("each line must be a JSON object")
                observation = validate_and_normalize(payload, now=now)
            except json.JSONDecodeError as exc:
                invalid += 1
                print(f"line {line_number}: invalid JSON ({exc.msg})", file=output)
            except (ValidationError, ValueError, TypeError) as exc:
                invalid += 1
                message = exc.message if isinstance(exc, ValidationError) else str(exc)
                print(f"line {line_number}: {message}", file=output)
            else:
                valid += 1
                _record_stats(stats, observation)

    print(f"Validation summary: {valid} valid, {invalid} invalid observation(s).", file=output)
    for vital_type in sorted(stats):
        item = stats[vital_type]
        line = (
            f"  {vital_type}: {item['count']} valid; "
            f"value range {item['min']:.2f}–{item['max']:.2f} {item['unit']}; "
            f"timestamps {_timestamp(item['first'])} to {_timestamp(item['last'])}"
        )
        if vital_type == "blood_pressure":
            line += (
                f"; diastolic range {item['diastolic_min']:.2f}"
                f"–{item['diastolic_max']:.2f} {item['unit']}"
            )
        print(line, file=output)
    return valid, invalid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="NDJSON file created by an offline exporter")
    args = parser.parse_args()
    try:
        valid, invalid = validate_file(args.input, sys.stderr)
    except OSError as exc:
        print(f"error: cannot read input file: {exc}", file=sys.stderr)
        return 2
    if valid == 0:
        print("error: no valid observations found", file=sys.stderr)
        return 1
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
