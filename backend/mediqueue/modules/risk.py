"""Module 6: Risk Interpretation & Alert Generation.

Applies configurable threshold and trend rules to a risk assessment plus the
patient's recent feature history. Alerts are deduplicated on
(patient_id, trigger_type, triggering_vital), carry structured evidence, and
use hysteresis (cooldown) without indefinitely suppressing sustained adverse
trends. Explanations are generated from verified structured observations with
templates — no generative/LLM text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from ..config import get_settings
from ..db import alerts, to_json

NORMAL_RANGES: dict[str, tuple[float, float]] = {
    "heart_rate": (60.0, 100.0),
    "spo2": (95.0, 100.0),
    "blood_pressure": (90.0, 129.0),  # systolic
    "temperature": (36.0, 37.5),
}

# Minimum net worsening over the confirmation span for a trend trigger.
MIN_TREND_DELTA: dict[str, float] = {
    "heart_rate": 8.0,
    "spo2": 2.0,
    "blood_pressure": 8.0,
    "temperature": 0.5,
}

SEVERITY_ORDER = {"watch": 1, "elevated": 2, "high": 3}


@dataclass
class AlertCandidate:
    trigger_type: str
    triggering_vital: str
    severity: str
    explanation: dict[str, Any]


@dataclass
class AlertOutcome:
    created: list[dict[str, Any]] = field(default_factory=list)
    updated: list[dict[str, Any]] = field(default_factory=list)
    suppressed: list[dict[str, Any]] = field(default_factory=list)
    resolved: list[dict[str, Any]] = field(default_factory=list)


def risk_band(score: float | None) -> str | None:
    if score is None:
        return None
    s = get_settings()
    if score >= s.band_high:
        return "high"
    if score >= s.band_elevated:
        return "elevated"
    if score >= s.band_watch:
        return "watch"
    return "low"


def band_thresholds() -> dict[str, float]:
    s = get_settings()
    return {"watch": s.band_watch, "elevated": s.band_elevated, "high": s.band_high}


def _adverse_direction(vital: str, latest: float, net_delta: float) -> str:
    """Choose the deterioration direction for a vital at its latest value."""
    lo, hi = NORMAL_RANGES[vital]
    if latest > hi:
        return "up"
    if latest < lo:
        return "down"
    # Within normal range: follow the larger observed movement.
    return "up" if net_delta >= 0 else "down"


def detect_adverse_trend(
    conn: Any,
    patient_id: str,
    vital: str,
    as_of: datetime,
    feature_result: Any,
) -> dict[str, Any] | None:
    """Return trend evidence when a sustained adverse trend is present.

    Confirmation span: the longer of the last `trend_min_readings` readings or
    `trend_min_span_minutes`. An abrupt change (from feature engineering) may
    shorten the confirmation span. Requires `trend_min_readings` consecutive
    worsening readings within the span.
    """
    from ..db import observations

    settings = get_settings()
    n = settings.trend_min_readings

    rows = conn.execute(
        select(observations)
        .where(
            observations.c.patient_id == patient_id,
            observations.c.vital_type == vital,
            observations.c.device_ts <= as_of,
        )
        .order_by(observations.c.device_ts.desc(), observations.c.id.desc())
        .limit(50)
    ).mappings().all()
    rows = [dict(r) for r in rows]
    if len(rows) < n:
        return None

    nth_ts = rows[n - 1]["device_ts"]
    span_needed = max(
        settings.trend_min_span_minutes,
        (as_of - nth_ts).total_seconds() / 60.0,
    )
    window_start = as_of - timedelta(minutes=span_needed)

    abrupt = None
    for flag in feature_result.abrupt_changes:
        if flag.get("vital") in (vital, f"{vital}_systolic"):
            abrupt = flag
            break

    window_rows = [r for r in rows if r["device_ts"] >= window_start]
    window_rows.reverse()  # ascending
    if len(window_rows) < n:
        if abrupt is None:
            return None
        # Abrupt change shortens the confirmation span: use the abrupt pair.
        window_rows = [
            r for r in rows if r["device_ts"] >= as_of - timedelta(minutes=settings.short_horizon_minutes)
        ]
        window_rows.reverse()
        if len(window_rows) < 2:
            return None

    values = [float(r["value"]) for r in window_rows]
    net_delta = values[-1] - values[0]
    direction = _adverse_direction(vital, values[-1], net_delta)
    sign = 1.0 if direction == "up" else -1.0

    # Consecutive worsening check on the trailing readings inside the span.
    tail = values[-max(n, 2):]
    pairwise = [tail[i + 1] - tail[i] for i in range(len(tail) - 1)]
    consecutive = all(sign * d >= 0 for d in pairwise) and any(sign * d > 0 for d in pairwise)
    min_delta = MIN_TREND_DELTA.get(vital, 1.0)
    net_worsening = sign * net_delta

    abrupt_shortcut = abrupt is not None and sign * float(abrupt["delta"]) > 0
    if not abrupt_shortcut and not (consecutive and net_worsening >= min_delta):
        return None
    if abrupt_shortcut and net_worsening <= 0:
        return None

    unit = window_rows[-1]["unit"]
    return {
        "vital": vital,
        "direction": direction,
        "first_value": values[0],
        "last_value": values[-1],
        "net_delta": round(net_delta, 4),
        "span_minutes": round(span_needed, 2),
        "reading_count": len(window_rows),
        "consecutive_worsening": bool(consecutive or abrupt_shortcut),
        "abrupt_change": bool(abrupt_shortcut),
        "unit": unit,
        "evidence_rows": window_rows[-n:],
    }


def _absolute_candidate(
    score: float, band: str, model_version_id: str | None, feature_result: Any
) -> AlertCandidate | None:
    settings = get_settings()
    if score < settings.alert_absolute_threshold:
        return None
    evidence: list[dict[str, Any]] = []
    for vital, row in feature_result.per_vital_latest.items():
        evidence.append(
            {
                "type": "reading",
                "vital_type": vital,
                "value": row["value"],
                "value_diastolic": row.get("value_diastolic"),
                "unit": row["unit"],
                "device_ts": row["device_ts"].isoformat(),
            }
        )
    explanation = {
        "summary": (
            f"Deterioration risk score {score:.2f} ({band}) is at or above the "
            f"configured alert threshold {settings.alert_absolute_threshold:.2f}. "
            "Score is a decision-support signal, not a validated clinical priority."
        ),
        "trigger": "absolute_threshold",
        "risk": {
            "score": round(score, 4),
            "band": band,
            "threshold": settings.alert_absolute_threshold,
            "thresholds": band_thresholds(),
            "model_version_id": model_version_id,
        },
        "evidence": evidence,
        "missing_vitals": feature_result.missing_vitals,
        "low_confidence": feature_result.low_confidence,
        "generator": "structured_template_v1",
    }
    return AlertCandidate(
        trigger_type="absolute_threshold",
        triggering_vital="risk_score",
        severity=band,
        explanation=explanation,
    )


def _trend_candidate(
    trend: dict[str, Any],
    score: float | None,
    band: str | None,
    model_version_id: str | None,
) -> AlertCandidate:
    vital = trend["vital"]
    evidence = [
        {
            "type": "reading",
            "vital_type": r["vital_type"],
            "value": r["value"],
            "value_diastolic": r.get("value_diastolic"),
            "unit": r["unit"],
            "device_ts": r["device_ts"].isoformat(),
        }
        for r in trend["evidence_rows"]
    ]
    direction_word = "increase" if trend["direction"] == "up" else "decrease"
    explanation = {
        "summary": (
            f"Sustained adverse trend in {vital}: {direction_word} of "
            f"{abs(trend['net_delta']):.2f} {trend['unit']} over ~{trend['span_minutes']:.0f} minutes "
            f"across {trend['reading_count']} readings"
            + (" (abrupt change)" if trend["abrupt_change"] else "")
            + "."
        ),
        "trigger": "adverse_trend",
        "risk": {
            "score": None if score is None else round(score, 4),
            "band": band,
            "thresholds": band_thresholds(),
            "model_version_id": model_version_id,
        },
        "trend": {k: v for k, v in trend.items() if k != "evidence_rows"},
        "evidence": evidence,
        "generator": "structured_template_v1",
    }
    # Display severity floors at "watch" so trend alerts remain visible even
    # when the absolute score band is still "low".
    sev = band if band in SEVERITY_ORDER else "watch"
    if SEVERITY_ORDER[sev] < SEVERITY_ORDER["watch"]:
        sev = "watch"
    return AlertCandidate(
        trigger_type="adverse_trend",
        triggering_vital=vital,
        severity=sev,
        explanation=explanation,
    )


def _resolve_stale_alerts(
    conn: Any, patient_id: str, as_of: datetime, adverse_vitals: set[str], score: float | None
) -> list[int]:
    """Resolve open alerts whose trigger no longer holds. Returns resolved ids."""
    settings = get_settings()
    resolved: list[int] = []
    rows = conn.execute(
        select(alerts).where(alerts.c.patient_id == patient_id, alerts.c.status == "open")
    ).mappings().all()
    for row in rows:
        row = dict(row)
        should_resolve = False
        if row["trigger_type"] == "absolute_threshold":
            if score is not None and score < settings.band_watch:
                should_resolve = True
        elif row["trigger_type"] == "adverse_trend":
            if row["triggering_vital"] not in adverse_vitals:
                should_resolve = True
        if should_resolve:
            conn.execute(
                alerts.update()
                .where(alerts.c.id == row["id"])
                .values(status="resolved", resolved_at=as_of)
            )
            resolved.append(row["id"])
    return resolved


def process_risk_interpretation(
    conn: Any,
    *,
    patient_id: str,
    score: float | None,
    model_version_id: str | None,
    feature_result: Any,
    as_of: datetime,
) -> AlertOutcome:
    """Create/update/resolve alerts for the latest assessment. Idempotent-ish:
    reprocessing the same state updates open alerts rather than duplicating."""
    settings = get_settings()
    outcome = AlertOutcome()

    band = risk_band(score)
    adverse_vitals: set[str] = set()

    # Trend evaluation for each vital with enough data.
    trend_candidates: list[AlertCandidate] = []
    for vital in ("heart_rate", "spo2", "blood_pressure", "temperature"):
        if vital in feature_result.missing_vitals:
            continue
        trend = detect_adverse_trend(conn, patient_id, vital, as_of, feature_result)
        if trend is not None:
            adverse_vitals.add(vital)
            trend_candidates.append(_trend_candidate(trend, score, band, model_version_id))

    resolved_ids = _resolve_stale_alerts(conn, patient_id, as_of, adverse_vitals, score)
    outcome.resolved = [{"alert_id": aid} for aid in resolved_ids]

    candidates: list[AlertCandidate] = []
    absolute = _absolute_candidate(score, band or "low", model_version_id, feature_result) if score is not None else None
    if absolute is not None:
        candidates.append(absolute)
    candidates.extend(trend_candidates)

    # Latest band of each vital's trend for material-worsening comparisons.
    for cand in candidates:
        dedup_key = f"{patient_id}|{cand.trigger_type}|{cand.triggering_vital}"
        open_row = conn.execute(
            select(alerts)
            .where(alerts.c.dedup_key == dedup_key, alerts.c.status == "open")
            .order_by(alerts.c.id.desc())
        ).mappings().first()

        if open_row is not None:
            open_row = dict(open_row)
            prev_sev = open_row["severity"]
            new_sev = (
                cand.severity
                if SEVERITY_ORDER.get(cand.severity, 0) > SEVERITY_ORDER.get(prev_sev, 0)
                else prev_sev
            )
            upgraded = new_sev != prev_sev
            conn.execute(
                alerts.update()
                .where(alerts.c.id == open_row["id"])
                .values(
                    severity=new_sev,
                    explanation_json=to_json(cand.explanation),
                    last_seen=as_of,
                    cooldown_until=as_of + timedelta(minutes=settings.alert_cooldown_minutes),
                )
            )
            outcome.updated.append(
                {"alert_id": open_row["id"], "severity": new_sev, "upgraded": upgraded}
            )
            continue

        # No open alert: apply cooldown hysteresis on recently closed alerts.
        cooldown_floor = as_of - timedelta(minutes=settings.alert_cooldown_minutes)
        recent = conn.execute(
            select(alerts)
            .where(alerts.c.dedup_key == dedup_key, alerts.c.last_seen >= cooldown_floor)
            .order_by(alerts.c.id.desc())
        ).mappings().first()

        if recent is not None:
            recent = dict(recent)
            material = False
            if score is not None:
                try:
                    import json as _json

                    prev_expl = _json.loads(recent.get("explanation_json") or "{}")
                    prev_score = (prev_expl.get("risk") or {}).get("score")
                except (ValueError, TypeError):
                    prev_score = None
                if prev_score is not None and score - float(prev_score) >= settings.material_worsening_delta:
                    material = True
                prev_band = risk_band(prev_score)
                if prev_band is not None and band is not None:
                    if SEVERITY_ORDER.get(band, 0) > SEVERITY_ORDER.get(prev_band, 0):
                        material = True
            if not material:
                outcome.suppressed.append(
                    {"dedup_key": dedup_key, "reason": "cooldown", "last_seen": recent["last_seen"].isoformat()}
                )
                continue
            # Material worsening: reopen as a new alert (prior is closed).
            conn.execute(
                alerts.update()
                .where(alerts.c.id == recent["id"])
                .values(status="suppressed")  # keep audit trail of the closed one
            )

        inserted = conn.execute(
            alerts.insert().values(
                patient_id=patient_id,
                trigger_type=cand.trigger_type,
                triggering_vital=cand.triggering_vital,
                severity=cand.severity,
                status="open",
                dedup_key=dedup_key,
                explanation_json=to_json(cand.explanation),
                first_seen=as_of,
                last_seen=as_of,
                cooldown_until=as_of + timedelta(minutes=settings.alert_cooldown_minutes),
            )
        )
        alert_id = int(inserted.inserted_primary_key[0])
        outcome.created.append({"alert_id": alert_id, "severity": cand.severity, "trigger_type": cand.trigger_type})

    return outcome
