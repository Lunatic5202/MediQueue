"""Aggregate quality audit for generic offline training CSVs.

The report intentionally excludes patient identifiers and raw observation values.
It is a data hygiene check, not clinical validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {"patient_id", "vital_type", "value", "unit", "device_ts"}
EXPECTED_UNITS = {
    "heart_rate": "bpm",
    "spo2": "%",
    "blood_pressure": "mmHg",
    "temperature": "°C",
}


def audit_generic_csv(path: str | Path) -> dict[str, Any]:
    """Return a privacy-conscious, aggregate audit report for a generic CSV."""
    df = pd.read_csv(path)
    columns = [str(column) for column in df.columns]
    missing_columns = sorted(REQUIRED_COLUMNS - set(columns))
    report: dict[str, Any] = {
        "status": "ok",
        "schema_valid": not missing_columns,
        "columns": columns,
        "row_count": int(len(df)),
        "missing_columns": missing_columns,
        "missing_values": {},
        "invalid_numeric_value_rows": 0,
        "non_finite_value_rows": 0,
        "invalid_timestamp_rows": 0,
        "invalid_vital_type_rows": 0,
        "unit_mismatch_rows": 0,
        "invalid_label_rows": 0,
        "positive_label_rows": 0,
        "negative_label_rows": 0,
        "unlabeled_rows": int(len(df)) if "label" not in df.columns else 0,
        "duplicate_observation_rows": 0,
        "errors": [],
        "warnings": [],
    }

    if missing_columns:
        report["status"] = "error"
        report["errors"].append("missing required columns")
        return report
    if df.empty:
        report["status"] = "error"
        report["errors"].append("dataset contains no rows")
        return report

    checked_columns = sorted(REQUIRED_COLUMNS | ({"label"} if "label" in df.columns else set()))
    for column in checked_columns:
        missing_count = int(df[column].isna().sum())
        if missing_count:
            report["missing_values"][column] = missing_count

    missing_core = sum(
        int(df[column].isna().sum())
        for column in ("patient_id", "vital_type", "value", "unit", "device_ts")
    )
    if missing_core:
        report["errors"].append("required observation fields contain missing values")

    patient_ids = df["patient_id"].astype("string").str.strip()
    vital_types = df["vital_type"].astype("string").str.strip()
    units = df["unit"].astype("string").str.strip()
    blank_identity = int((patient_ids.isna() | patient_ids.eq("")).sum())
    blank_vital = int((vital_types.isna() | vital_types.eq("")).sum())
    report["blank_patient_id_rows"] = blank_identity
    if blank_identity:
        report["errors"].append("patient_id contains blank values")
    if blank_vital:
        report["errors"].append("vital_type contains blank values")

    numeric = pd.to_numeric(df["value"], errors="coerce")
    report["invalid_numeric_value_rows"] = int((df["value"].notna() & numeric.isna()).sum())
    report["non_finite_value_rows"] = int(
        (numeric.notna() & ~np.isfinite(numeric.astype(float))).sum()
    )
    if report["invalid_numeric_value_rows"] or report["non_finite_value_rows"]:
        report["errors"].append("value contains non-numeric or non-finite values")

    timestamps = pd.to_datetime(df["device_ts"], errors="coerce", utc=True)
    report["invalid_timestamp_rows"] = int(timestamps.isna().sum())
    if report["invalid_timestamp_rows"]:
        report["errors"].append("device_ts contains invalid timestamps")

    known_vitals = vital_types.isin(EXPECTED_UNITS)
    report["invalid_vital_type_rows"] = int((vital_types.notna() & ~known_vitals).sum())
    if report["invalid_vital_type_rows"]:
        report["errors"].append("vital_type contains unsupported values")

    expected_units = vital_types.map(EXPECTED_UNITS)
    comparable_units = expected_units.notna() & units.notna()
    report["unit_mismatch_rows"] = int((comparable_units & units.ne(expected_units)).sum())
    if report["unit_mismatch_rows"]:
        report["errors"].append("unit does not match the supported vital type")

    duplicate_mask = df.duplicated(
        subset=["patient_id", "vital_type", "device_ts"], keep="first"
    )
    report["duplicate_observation_rows"] = int(duplicate_mask.sum())
    if report["duplicate_observation_rows"]:
        report["warnings"].append(
            "duplicate patient_id/vital_type/device_ts keys found; review before training"
        )

    if "label" not in df.columns:
        report["warnings"].append("label column is missing; supervised training requires labels")
    else:
        labels = pd.to_numeric(df["label"], errors="coerce")
        present = df["label"].notna()
        valid_binary = labels.isin([0, 1])
        report["invalid_label_rows"] = int((present & ~valid_binary).sum())
        report["positive_label_rows"] = int((present & valid_binary & labels.eq(1)).sum())
        report["negative_label_rows"] = int((present & valid_binary & labels.eq(0)).sum())
        report["unlabeled_rows"] = int((~present).sum())
        if report["invalid_label_rows"]:
            report["errors"].append("label contains values other than 0 or 1")
        if report["unlabeled_rows"]:
            report["warnings"].append("some rows have no label; verify this is intentional")

    report["status"] = "error" if report["errors"] else "warning" if report["warnings"] else "ok"
    return report
