"""Module 7: Dynamic Queue Recommendation.

Translates an alert into a pending queue-priority recommendation. The
recommendation is applied only after clinician confirmation. Priority uses
ESI-style numbering (1 = most urgent, 5 = least urgent). Confirmed changes are
bounded by configuration (default: at most one triage-category step).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from ..config import get_settings
from ..db import alerts, patients, recommendations, utcnow
from .audit import record_audit


class RecommendationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


BAND_RANK = {"low": 0, "watch": 1, "elevated": 2, "high": 3}


def _band_rank(name: str | None) -> int:
    return BAND_RANK.get(name or "low", 0)


def create_recommendation(
    conn: Any,
    *,
    patient_id: str,
    alert_id: int | None,
    severity: str,
    as_of: datetime,
) -> dict[str, Any] | None:
    """Create a pending recommendation for an alert of sufficient severity.

    Returns the new recommendation row (dict) or None when severity is below
    the configured minimum band. Any existing pending recommendation for the
    patient is marked superseded first (one active recommendation at a time).
    """
    settings = get_settings()
    if _band_rank(severity) < _band_rank(settings.min_band_for_recommendation):
        return None

    patient = conn.execute(
        select(patients).where(patients.c.id == patient_id)
    ).mappings().first()
    if patient is None:
        return None
    current = int(patient["triage_category"])

    # Escalation: move toward category 1, bounded to one step per action.
    proposed = max(1, current - settings.max_priority_step)
    if proposed == current:
        # Already at the most urgent category; recommendation can only note it.
        proposed = current
        direction = "escalate"
    else:
        direction = "escalate"

    conn.execute(
        recommendations.update()
        .where(
            recommendations.c.patient_id == patient_id,
            recommendations.c.status == "pending",
        )
        .values(status="superseded", decided_at=as_of)
    )

    inserted = conn.execute(
        recommendations.insert().values(
            patient_id=patient_id,
            alert_id=alert_id,
            current_priority=current,
            proposed_priority=proposed,
            direction=direction,
            status="pending",
            created_at=as_of,
        )
    )
    rec_id = int(inserted.inserted_primary_key[0])
    record_audit(
        conn,
        actor="system",
        event_type="recommendation_created",
        entity_type="recommendation",
        entity_id=str(rec_id),
        payload={
            "patient_id": patient_id,
            "alert_id": alert_id,
            "current_priority": current,
            "proposed_priority": proposed,
            "severity": severity,
        },
    )
    row = conn.execute(select(recommendations).where(recommendations.c.id == rec_id)).mappings().first()
    return dict(row)


def _get_pending(conn: Any, rec_id: int) -> dict[str, Any]:
    row = conn.execute(
        select(recommendations).where(recommendations.c.id == rec_id)
    ).mappings().first()
    if row is None:
        raise RecommendationError("not_found", f"recommendation {rec_id} not found")
    return dict(row)


def confirm_recommendation(
    conn: Any, rec_id: int, actor: str, rationale: str | None, as_of: datetime | None = None
) -> dict[str, Any]:
    """Apply the recommended priority change. Audit write is part of the same
    transaction: if audit persistence fails, the whole action rolls back."""
    as_of = as_of or utcnow()
    rec = _get_pending(conn, rec_id)
    if rec["status"] != "pending":
        raise RecommendationError("invalid_state", f"recommendation is {rec['status']}, not pending")

    patient = conn.execute(
        select(patients).where(patients.c.id == rec["patient_id"])
    ).mappings().first()
    if patient is None:
        raise RecommendationError("not_found", "patient not found")
    current = int(patient["triage_category"])
    applied = int(rec["proposed_priority"])

    conn.execute(
        patients.update().where(patients.c.id == rec["patient_id"]).values(triage_category=applied)
    )
    conn.execute(
        recommendations.update()
        .where(recommendations.c.id == rec_id)
        .values(
            status="confirmed",
            rationale=rationale,
            decided_at=as_of,
            decided_by=actor,
            applied_priority=applied,
            current_priority=current,
        )
    )
    record_audit(
        conn,
        actor=actor,
        event_type="recommendation_confirmed",
        entity_type="recommendation",
        entity_id=str(rec_id),
        payload={
            "patient_id": rec["patient_id"],
            "previous_priority": current,
            "applied_priority": applied,
            "rationale": rationale,
        },
    )
    row = conn.execute(select(recommendations).where(recommendations.c.id == rec_id)).mappings().first()
    return dict(row)


def reject_recommendation(
    conn: Any, rec_id: int, actor: str, rationale: str | None, as_of: datetime | None = None
) -> dict[str, Any]:
    as_of = as_of or utcnow()
    rec = _get_pending(conn, rec_id)
    if rec["status"] != "pending":
        raise RecommendationError("invalid_state", f"recommendation is {rec['status']}, not pending")
    if not rationale or not rationale.strip():
        raise RecommendationError("rationale_required", "rejection requires a rationale")
    conn.execute(
        recommendations.update()
        .where(recommendations.c.id == rec_id)
        .values(status="rejected", rationale=rationale, decided_at=as_of, decided_by=actor)
    )
    # Suppress the linked alert so the same (unchanged) signal does not
    # immediately re-recommend. Material worsening still bypasses suppression.
    if rec.get("alert_id") is not None:
        settings = get_settings()
        conn.execute(
            alerts.update()
            .where(alerts.c.id == rec["alert_id"])
            .values(
                status="suppressed",
                cooldown_until=as_of + timedelta(minutes=settings.alert_cooldown_minutes),
            )
        )
    record_audit(
        conn,
        actor=actor,
        event_type="recommendation_rejected",
        entity_type="recommendation",
        entity_id=str(rec_id),
        payload={"patient_id": rec["patient_id"], "rationale": rationale},
    )
    row = conn.execute(select(recommendations).where(recommendations.c.id == rec_id)).mappings().first()
    return dict(row)


def override_recommendation(
    conn: Any,
    rec_id: int,
    actor: str,
    override_priority: int,
    rationale: str | None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Clinician-directed priority change. May exceed the automatic one-step
    bound; rationale is mandatory and the action is fully audited."""
    as_of = as_of or utcnow()
    rec = _get_pending(conn, rec_id)
    if rec["status"] != "pending":
        raise RecommendationError("invalid_state", f"recommendation is {rec['status']}, not pending")
    if not rationale or not rationale.strip():
        raise RecommendationError("rationale_required", "override requires a rationale")
    if not (1 <= override_priority <= 5):
        raise RecommendationError("invalid_priority", "override_priority must be within 1..5")

    patient = conn.execute(
        select(patients).where(patients.c.id == rec["patient_id"])
    ).mappings().first()
    if patient is None:
        raise RecommendationError("not_found", "patient not found")
    current = int(patient["triage_category"])

    conn.execute(
        patients.update()
        .where(patients.c.id == rec["patient_id"])
        .values(triage_category=override_priority)
    )
    conn.execute(
        recommendations.update()
        .where(recommendations.c.id == rec_id)
        .values(
            status="overridden",
            rationale=rationale,
            decided_at=as_of,
            decided_by=actor,
            applied_priority=override_priority,
            current_priority=current,
        )
    )
    record_audit(
        conn,
        actor=actor,
        event_type="recommendation_overridden",
        entity_type="recommendation",
        entity_id=str(rec_id),
        payload={
            "patient_id": rec["patient_id"],
            "previous_priority": current,
            "proposed_priority": rec["proposed_priority"],
            "applied_priority": override_priority,
            "rationale": rationale,
        },
    )
    row = conn.execute(select(recommendations).where(recommendations.c.id == rec_id)).mappings().first()
    return dict(row)


def list_recommendations(
    conn: Any, patient_id: str | None = None, status: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    stmt = select(recommendations).order_by(recommendations.c.id.desc()).limit(limit)
    if patient_id:
        stmt = stmt.where(recommendations.c.patient_id == patient_id)
    if status:
        stmt = stmt.where(recommendations.c.status == status)
    return [dict(r) for r in conn.execute(stmt).mappings().all()]
