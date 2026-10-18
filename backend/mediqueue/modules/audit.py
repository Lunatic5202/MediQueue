"""Module 9: Audit Logging & Monitoring.

Audit events are append-only. A failure to persist an audit event must prevent
the associated action from being reported as success — the pipeline wraps
processing in a single transaction so an audit failure rolls back the action.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ..db import audit_events, events, to_json, utcnow


class AuditWriteError(Exception):
    """Raised when an audit event cannot be persisted."""


def record_audit(
    conn: Any,
    *,
    actor: str,
    event_type: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> int:
    """Append an audit event inside the caller's transaction.

    Any DB error propagates so the caller's transaction fails and nothing is
    reported as successfully completed.
    """
    try:
        result = conn.execute(
            audit_events.insert().values(
                ts=utcnow(),
                actor=actor,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id is not None else None,
                payload_json=to_json(payload or {}),
            )
        )
        return int(result.inserted_primary_key[0])
    except Exception as exc:  # noqa: BLE001
        raise AuditWriteError(f"failed to persist audit event {event_type!r}: {exc}") from exc


def record_event(
    conn: Any,
    *,
    topic: str,
    payload: dict[str, Any],
    patient_id: str | None = None,
) -> int:
    """Append a realtime-feed event (durable; powers polling fallback)."""
    result = conn.execute(
        events.insert().values(
            ts=utcnow(),
            topic=topic,
            patient_id=patient_id,
            payload_json=to_json(payload),
        )
    )
    return int(result.inserted_primary_key[0])


def query_audit(
    conn: Any,
    *,
    event_type: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor: str | None = None,
    since_id: int | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    import json

    stmt = select(audit_events).order_by(audit_events.c.id.desc()).limit(min(limit, 1000))
    if event_type:
        stmt = stmt.where(audit_events.c.event_type == event_type)
    if entity_type:
        stmt = stmt.where(audit_events.c.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(audit_events.c.entity_id == str(entity_id))
    if actor:
        stmt = stmt.where(audit_events.c.actor == actor)
    if since_id is not None:
        stmt = select(audit_events).where(audit_events.c.id > since_id).order_by(
            audit_events.c.id.asc()
        ).limit(min(limit, 1000))
    rows = conn.execute(stmt).mappings().all()
    out = []
    for r in rows:
        item = dict(r)
        item["payload"] = json.loads(item.pop("payload_json") or "{}")
        out.append(item)
    return out
