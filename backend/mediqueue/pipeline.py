"""Pipeline orchestration: steps 1-9 of the MediQueue processing sequence.

Each observation is processed inside a single database transaction that
includes audit writes. If any audit write fails, the transaction rolls back
and the API reports failure — an action is never reported as successfully
completed when its audit record could not be persisted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select

from .config import get_settings
from .db import (
    alerts,
    feature_sets,
    patients,
    recommendations,
    risk_assessments,
    to_json,
    utcnow,
)
from .modules import history, inference, risk as risk_mod
from .modules.audit import record_audit, record_event
from .modules.features import FeatureResult, compute_features
from .modules.inference import InferenceError
from .modules.recommendation import create_recommendation
from .modules.validation import NormalizedObservation, ValidationError


class PipelineError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass
class PipelineResult:
    status: str  # accepted | duplicate
    observation_id: int | None = None
    risk_assessment_id: int | None = None
    risk_score: float | None = None
    risk_band: str | None = None
    low_confidence: bool = False
    stale: bool = False
    alert_ids: list[int] = field(default_factory=list)
    recommendation_ids: list[int] = field(default_factory=list)
    stages_ms: dict[str, float] = field(default_factory=dict)
    detail: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)


BroadcastFn = Callable[[dict[str, Any]], None]


def _stage_timer(stages: dict[str, float], name: str) -> Any:
    class _T:
        def __enter__(self) -> "_T":
            self.start = time.perf_counter()
            return self

        def __exit__(self, *exc: object) -> None:
            stages[name] = (time.perf_counter() - self.start) * 1000.0

    return _T()


def ensure_patient(
    conn: Any, patient_id: str, as_of: datetime | None = None
) -> dict[str, Any]:
    row = conn.execute(select(patients).where(patients.c.id == patient_id)).mappings().first()
    if row is not None:
        return dict(row)
    now = as_of or utcnow()
    conn.execute(
        patients.insert().values(
            id=patient_id,
            display_name=None,
            age=None,
            sex=None,
            arrival_time=now,
            triage_category=3,
            status="active",
            created_at=now,
        )
    )
    record_audit(
        conn,
        actor="system",
        event_type="patient_registered",
        entity_type="patient",
        entity_id=patient_id,
        payload={"auto_registered": True},
    )
    row = conn.execute(select(patients).where(patients.c.id == patient_id)).mappings().first()
    return dict(row)


def mark_prior_scores_stale(conn: Any, patient_id: str, reason: str, as_of: datetime) -> None:
    """Mark the patient's most recent non-stale assessment as stale.

    A missing score, failed inference, or stale assessment must never be
    interpreted as the patient being safe.
    """
    row = conn.execute(
        select(risk_assessments)
        .where(risk_assessments.c.patient_id == patient_id, risk_assessments.c.stale.is_(False))
        .order_by(risk_assessments.c.id.desc())
        .limit(1)
    ).mappings().first()
    if row is not None:
        conn.execute(
            risk_assessments.update()
            .where(risk_assessments.c.id == row["id"])
            .values(stale=True)
        )
        record_audit(
            conn,
            actor="system",
            event_type="score_marked_stale",
            entity_type="risk_assessment",
            entity_id=str(row["id"]),
            payload={"patient_id": patient_id, "reason": reason, "at": as_of.isoformat()},
        )


def process_observation(
    conn: Any,
    payload: dict[str, Any],
    *,
    actor: str = "system",
    now: datetime | None = None,
    broadcast: BroadcastFn | None = None,
) -> PipelineResult:
    """Full ingestion pipeline. The caller owns the transaction boundaries.

    Raises PipelineError for validation failures and AuditWriteError (via
    record_audit) when audit persistence fails — callers must roll back and
    report failure in those cases.
    """
    from .modules.validation import validate_and_normalize

    settings = get_settings()
    now = now or datetime.now(timezone.utc)
    stages: dict[str, float] = {}
    result = PipelineResult(status="accepted")

    with _stage_timer(stages, "validation_ms"):
        try:
            obs: NormalizedObservation = validate_and_normalize(payload, now=now)
        except ValidationError as exc:
            raise PipelineError(exc.code, exc.message, status_code=422) from exc

    with _stage_timer(stages, "persistence_ms"):
        ensure_patient(conn, obs.patient_id, as_of=now)
        row_id, is_duplicate = history.insert_observation_idempotent(conn, obs)

    if is_duplicate:
        result.status = "duplicate"
        result.observation_id = row_id
        result.detail = "duplicate acknowledged idempotently; downstream processing not re-triggered"
        record_audit(
            conn,
            actor=actor,
            event_type="observation_duplicate",
            entity_type="observation",
            entity_id=str(row_id),
            payload={"patient_id": obs.patient_id, "vital_type": obs.vital_type},
        )
        return result

    result.observation_id = row_id

    if history.is_late(obs.device_ts, obs.ingest_ts):
        record_audit(
            conn,
            actor=actor,
            event_type="late_observation",
            entity_type="observation",
            entity_id=str(row_id),
            payload={
                "patient_id": obs.patient_id,
                "vital_type": obs.vital_type,
                "device_ts": obs.device_ts.isoformat(),
                "ingest_ts": obs.ingest_ts.isoformat(),
            },
        )

    # Prune bounded history (keeps storage and future loads bounded).
    history.prune_history(conn, obs.patient_id, now=now)

    with _stage_timer(stages, "features_ms"):
        window_rows = history.load_window(conn, obs.patient_id, as_of=now)
        feature_result: FeatureResult = compute_features(window_rows, now)

        conn.execute(
            feature_sets.insert().values(
                patient_id=obs.patient_id,
                computed_at=now,
                window_start=feature_result.window_start,
                window_end=feature_result.window_end,
                payload_json=to_json(feature_result.features),
                low_confidence=feature_result.low_confidence,
                missing_vitals_json=to_json(feature_result.missing_vitals),
            )
        )

    score: float | None = None
    model_version: str | None = None
    latency_ms: float | None = None
    assessment_id: int | None = None
    inference_failed = False
    abstained = False
    abstain_reason: str | None = None

    engine = inference.get_inference_engine()

    if feature_result.low_confidence:
        # Default: abstain. Record an assessment row with a NULL score so the
        # dashboard can display "insufficient data" without implying safety.
        abstained = True
        abstain_reason = "insufficient_history"
        record_audit(
            conn,
            actor="system",
            event_type="inference_abstained",
            entity_type="patient",
            entity_id=obs.patient_id,
            payload={
                "reason": abstain_reason,
                "reading_count": feature_result.reading_count,
                "span_minutes": feature_result.span_minutes,
            },
        )
    elif not engine.loaded:
        inference_failed = True
        mark_prior_scores_stale(conn, obs.patient_id, "model_not_loaded", now)
        record_audit(
            conn,
            actor="system",
            event_type="inference_failed",
            entity_type="patient",
            entity_id=obs.patient_id,
            payload={"reason": engine.error or "model_not_loaded"},
        )
    else:
        with _stage_timer(stages, "inference_ms"):
            try:
                prediction = engine.predict(feature_result.features)
                score = prediction.risk_score
                model_version = prediction.model_version_id
                latency_ms = prediction.latency_ms
            except InferenceError as exc:
                inference_failed = True
                mark_prior_scores_stale(conn, obs.patient_id, str(exc), now)
                record_audit(
                    conn,
                    actor="system",
                    event_type="inference_failed",
                    entity_type="patient",
                    entity_id=obs.patient_id,
                    payload={"error": str(exc)},
                )

    if abstained or inference_failed:
        inserted = conn.execute(
            risk_assessments.insert().values(
                patient_id=obs.patient_id,
                risk_score=None,
                risk_band=None,
                model_version_id=model_version,
                latency_ms=latency_ms,
                status="abstained",
                low_confidence=abstained,
                stale=False,
                reason=abstain_reason or "inference_failed",
                created_at=now,
            )
        )
        assessment_id = int(inserted.inserted_primary_key[0])
        result.risk_assessment_id = assessment_id
        result.low_confidence = abstained
        result.stale = inference_failed
        result.detail = abstain_reason or "inference_failed"
    else:
        band = risk_mod.risk_band(score)
        inserted = conn.execute(
            risk_assessments.insert().values(
                patient_id=obs.patient_id,
                risk_score=score,
                risk_band=band,
                model_version_id=model_version,
                latency_ms=latency_ms,
                status="ok",
                low_confidence=False,
                stale=False,
                reason=None,
                created_at=now,
            )
        )
        assessment_id = int(inserted.inserted_primary_key[0])
        result.risk_assessment_id = assessment_id
        result.risk_score = score
        result.risk_band = band
        record_audit(
            conn,
            actor="system",
            event_type="risk_score_computed",
            entity_type="risk_assessment",
            entity_id=str(assessment_id),
            payload={
                "patient_id": obs.patient_id,
                "risk_score": round(score, 4),
                "risk_band": band,
                "model_version_id": model_version,
                "latency_ms": round(latency_ms, 3) if latency_ms is not None else None,
                "low_confidence": False,
            },
        )

    with _stage_timer(stages, "interpretation_ms"):
        outcome = risk_mod.process_risk_interpretation(
            conn,
            patient_id=obs.patient_id,
            score=score,
            model_version_id=model_version,
            feature_result=feature_result,
            as_of=now,
        )

    alert_ids: list[int] = []
    for item in outcome.created:
        alert_id = int(item["alert_id"])
        alert_ids.append(alert_id)
        record_audit(
            conn,
            actor="system",
            event_type="alert_created",
            entity_type="alert",
            entity_id=str(alert_id),
            payload={"patient_id": obs.patient_id, **item},
        )
        rec = create_recommendation(
            conn,
            patient_id=obs.patient_id,
            alert_id=alert_id,
            severity=item["severity"],
            as_of=now,
        )
        if rec is not None:
            result.recommendation_ids.append(int(rec["id"]))

    for item in outcome.updated:
        alert_id = int(item["alert_id"])
        alert_ids.append(alert_id)
        record_audit(
            conn,
            actor="system",
            event_type="alert_updated",
            entity_type="alert",
            entity_id=str(alert_id),
            payload={"patient_id": obs.patient_id, **item},
        )
        # A new pending recommendation is created only when the alert severity
        # was upgraded (avoids re-recommending after clinician rejection).
        if item.get("upgraded"):
            rec = create_recommendation(
                conn,
                patient_id=obs.patient_id,
                alert_id=alert_id,
                severity=item["severity"],
                as_of=now,
            )
            if rec is not None:
                result.recommendation_ids.append(int(rec["id"]))

    for item in outcome.suppressed:
        record_audit(
            conn,
            actor="system",
            event_type="alert_suppressed",
            entity_type="alert",
            entity_id=str(item.get("dedup_key")),
            payload={"patient_id": obs.patient_id, **item},
        )

    for item in outcome.resolved:
        record_audit(
            conn,
            actor="system",
            event_type="alert_resolved",
            entity_type="alert",
            entity_id=str(item["alert_id"]),
            payload={"patient_id": obs.patient_id},
        )

    result.alert_ids = alert_ids
    result.stages_ms.update(stages)

    # Durable realtime events (polling fallback) — recorded in-transaction.
    payload_events: list[dict[str, Any]] = []
    obs_event = {
        "topic": "observation",
        "patient_id": obs.patient_id,
        "data": {
            "observation_id": row_id,
            "vital_type": obs.vital_type,
            "value": obs.value,
            "value_diastolic": obs.value_diastolic,
            "unit": obs.unit,
            "device_ts": obs.device_ts.isoformat(),
        },
    }
    payload_events.append(obs_event)
    assessment_event = {
        "topic": "risk_assessment",
        "patient_id": obs.patient_id,
        "data": {
            "assessment_id": assessment_id,
            "risk_score": result.risk_score,
            "risk_band": result.risk_band,
            "status": "abstained" if abstained else ("failed" if inference_failed else "ok"),
            "low_confidence": result.low_confidence,
            "stale": result.stale,
            "model_version_id": model_version,
            "created_at": now.isoformat(),
        },
    }
    payload_events.append(assessment_event)
    for item in outcome.created + outcome.updated:
        payload_events.append(
            {
                "topic": "alert",
                "patient_id": obs.patient_id,
                "data": {"alert_id": int(item["alert_id"]), "severity": item.get("severity")},
            }
        )
    for rec_id in result.recommendation_ids:
        payload_events.append(
            {"topic": "recommendation", "patient_id": obs.patient_id, "data": {"recommendation_id": rec_id}}
        )

    for ev in payload_events:
        record_event(conn, topic=ev["topic"], payload=ev["data"], patient_id=ev["patient_id"])

    result.events = payload_events
    if broadcast is not None:
        # Broadcast happens AFTER commit by the caller using result.events;
        # kept here for interface clarity.
        pass
    return result
