"""Module 4: Feature Engineering.

Rolling, trailing, patient-local temporal features over the configured history
window. Missing vitals remain missing (null) and are flagged; nothing is
imputed as normal. TRAINING AND INFERENCE MUST USE THE FUNCTIONS IN THIS
MODULE to avoid train/serve skew.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from ..config import get_settings

VITALS = ("heart_rate", "spo2", "blood_pressure", "temperature")

# Per-vital abrupt-change thresholds (canonical units) used to flag
# abrupt_change. An abrupt change may be real deterioration; it is passed
# through and flagged, never suppressed.
ABRUPT_CHANGE = {
    "heart_rate": 30.0,       # bpm within <= 10 minutes
    "spo2": 4.0,              # percentage points within <= 10 minutes
    "blood_pressure_systolic": 25.0,  # mmHg within <= 10 minutes
    "temperature": 1.0,       # °C within <= 10 minutes
}
ABRUPT_WINDOW_MINUTES = 10.0


def feature_names() -> list[str]:
    """Canonical, ordered feature schema shared by training and inference."""
    names: list[str] = []
    for vital in VITALS:
        prefix = vital
        names.extend(
            [
                f"{prefix}__latest",
                f"{prefix}__latest_diastolic",
                f"{prefix}__minutes_since_last",
                f"{prefix}__mean",
                f"{prefix}__std",
                f"{prefix}__min",
                f"{prefix}__max",
                f"{prefix}__slope_per_min",
                f"{prefix}__delta_short_horizon",
                f"{prefix}__count",
                f"{prefix}__missing",
            ]
        )
    names.extend(
        [
            "shock_index",
            "cross_vital__hr_temp_ratio",
            "global__reading_count",
            "global__minutes_since_last_any",
            "global__low_history",
        ]
    )
    return names


def feature_schema_hash() -> str:
    payload = "\n".join(feature_names())
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class FeatureResult:
    features: dict[str, float | None]
    low_confidence: bool
    missing_vitals: list[str]
    window_start: datetime
    window_end: datetime
    abrupt_changes: list[dict[str, Any]] = field(default_factory=list)
    per_vital_latest: dict[str, dict[str, Any]] = field(default_factory=dict)
    reading_count: int = 0
    span_minutes: float = 0.0


def _safe_mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _safe_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    m = sum(values) / len(values)
    var = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)


def _slope_per_min(points: list[tuple[float, float]]) -> float | None:
    """Least-squares slope over (minutes_since_epoch, value) points."""
    if len(points) < 2:
        return None
    n = len(points)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return None
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    return num / denom


def _short_horizon_delta(
    points_desc: list[tuple[float, float]], short_horizon_minutes: float
) -> float | None:
    """Latest value minus the most recent value at least `short_horizon_minutes`
    old. None when no older reference exists (not imputed)."""
    if not points_desc:
        return None
    latest_t, latest_v = points_desc[0]
    for t, v in points_desc[1:]:
        if (latest_t - t) >= short_horizon_minutes:
            return latest_v - v
    return None


def _detect_abrupt_changes(
    vital_key: str, points_asc: list[tuple[float, float]]
) -> list[dict[str, Any]]:
    threshold_key = "blood_pressure_systolic" if vital_key == "blood_pressure" else vital_key
    threshold = ABRUPT_CHANGE.get(threshold_key)
    if threshold is None or len(points_asc) < 2:
        return []
    flags: list[dict[str, Any]] = []
    j = 0
    for i in range(len(points_asc)):
        t_i, v_i = points_asc[i]
        while j < i and (t_i - points_asc[j][0]) > ABRUPT_WINDOW_MINUTES:
            j += 1
        for k in range(j, i):
            t_k, v_k = points_asc[k]
            if (t_i - t_k) > ABRUPT_WINDOW_MINUTES:
                continue
            delta = v_i - v_k
            if abs(delta) >= threshold:
                flags.append(
                    {
                        "vital": vital_key,
                        "from_value": v_k,
                        "to_value": v_i,
                        "delta": round(delta, 4),
                        "from_minutes_ago": round(t_i - t_k, 2),
                    }
                )
                return flags  # one flag per vital per computation is sufficient
    return flags


def _vital_points(
    rows: list[dict[str, Any]], vital: str, epoch: datetime, value_key: str = "value"
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for r in rows:
        if r["vital_type"] != vital:
            continue
        val = r.get(value_key)
        if val is None:
            continue
        minutes = (r["device_ts"] - epoch).total_seconds() / 60.0
        points.append((minutes, float(val)))
    return points


def compute_features(rows: list[dict[str, Any]], as_of: datetime) -> FeatureResult:
    """Compute rolling features from an ascending, window-bounded history.

    `rows` must be sorted by device_ts ascending and bounded to the trailing
    window (see history.load_window).
    """
    settings = get_settings()
    short_h = settings.short_horizon_minutes
    span_minutes = 0.0
    reading_count = len(rows)
    if rows:
        span_minutes = (rows[-1]["device_ts"] - rows[0]["device_ts"]).total_seconds() / 60.0

    features: dict[str, float | None] = {name: None for name in feature_names()}
    abrupt: list[dict[str, Any]] = []
    missing: list[str] = []
    latest_map: dict[str, dict[str, Any]] = {}

    for r in rows:
        latest_map[r["vital_type"]] = r

    epoch = as_of
    hr_points = _vital_points(rows, "heart_rate", epoch)
    temp_points = _vital_points(rows, "temperature", epoch)
    spo2_points = _vital_points(rows, "spo2", epoch)
    sbp_points = _vital_points(rows, "blood_pressure", epoch)
    dbp_points = _vital_points(rows, "blood_pressure", epoch, value_key="value_diastolic")

    vital_point_map = {
        "heart_rate": hr_points,
        "spo2": spo2_points,
        "blood_pressure": sbp_points,
        "temperature": temp_points,
    }

    for vital in VITALS:
        points = vital_point_map[vital]
        if not points:
            missing.append(vital)
            features[f"{vital}__missing"] = 1.0
            continue
        features[f"{vital}__missing"] = 0.0
        desc = sorted(points, key=lambda p: p[0], reverse=True)
        asc = sorted(points, key=lambda p: p[0])
        values = [p[1] for p in asc]
        latest_t, latest_v = desc[0]
        features[f"{vital}__latest"] = latest_v
        # points are minutes relative to as_of (<= 0), so age is simply -latest_t
        features[f"{vital}__minutes_since_last"] = round(max(0.0, -latest_t), 4)
        features[f"{vital}__mean"] = _safe_mean(values)
        features[f"{vital}__std"] = _safe_std(values)
        features[f"{vital}__min"] = min(values)
        features[f"{vital}__max"] = max(values)
        features[f"{vital}__slope_per_min"] = _slope_per_min(asc)
        features[f"{vital}__delta_short_horizon"] = _short_horizon_delta(desc, short_h)
        features[f"{vital}__count"] = float(len(values))

        abrupt.extend(_detect_abrupt_changes(vital, asc))

        if vital == "blood_pressure":
            dbp_desc = sorted(dbp_points, key=lambda p: p[0], reverse=True)
            if dbp_desc:
                features["blood_pressure__latest_diastolic"] = dbp_desc[0][1]

    # Cross-vital features (only when the available data supports them).
    hr_latest = features.get("heart_rate__latest")
    sbp_latest = features.get("blood_pressure__latest")
    temp_latest = features.get("temperature__latest")
    if hr_latest is not None and sbp_latest not in (None, 0):
        features["shock_index"] = round(hr_latest / sbp_latest, 4)
    if hr_latest is not None and temp_latest not in (None, 0):
        features["cross_vital__hr_temp_ratio"] = round(hr_latest / temp_latest, 4)

    features["global__reading_count"] = float(reading_count)
    any_latest_min = None
    for vital in VITALS:
        t = features.get(f"{vital}__minutes_since_last")
        if t is not None:
            any_latest_min = t if any_latest_min is None else min(any_latest_min, t)
    features["global__minutes_since_last_any"] = any_latest_min

    low_confidence = (
        reading_count < settings.min_readings_for_confidence
        or span_minutes < settings.min_span_minutes_for_confidence
    )
    features["global__low_history"] = 1.0 if low_confidence else 0.0

    window_start = rows[0]["device_ts"] if rows else as_of - timedelta(
        hours=settings.history_window_hours
    )

    return FeatureResult(
        features=features,
        low_confidence=low_confidence,
        missing_vitals=missing,
        window_start=window_start,
        window_end=as_of,
        abrupt_changes=abrupt,
        per_vital_latest=latest_map,
        reading_count=reading_count,
        span_minutes=span_minutes,
    )


def to_model_vector(features: dict[str, float | None]) -> list[float]:
    """Ordered vector aligned with feature_names(); None -> NaN."""
    out: list[float] = []
    for name in feature_names():
        val = features.get(name)
        out.append(float("nan") if val is None else float(val))
    return out
