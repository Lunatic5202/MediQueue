"""Module 3: Patient State & Time-Series History.

Maintains a bounded, time-ordered per-patient vital-sign history. Late events
are inserted by device timestamp; duplicates are acknowledged idempotently
(enforced via the unique idempotency key at insert time).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, select

from ..config import get_settings
from ..db import observations, utcnow


def insert_observation(conn: Any, obs: Any) -> int | None:
    """Insert a normalized observation.

    Returns the new row id, or None if the idempotency key already exists
    (duplicate — caller must acknowledge without re-triggering downstream work).
    """
    result = conn.execute(
        observations.insert().values(
            patient_id=obs.patient_id,
            vital_type=obs.vital_type,
            value=obs.value,
            value_diastolic=obs.value_diastolic,
            unit=obs.unit,
            device_ts=obs.device_ts,
            ingest_ts=obs.ingest_ts,
            source_id=obs.source_id,
            idempotency_key=obs.idempotency_key,
        )
    )
    return int(result.inserted_primary_key[0])


def insert_observation_idempotent(conn: Any, obs: Any) -> tuple[int | None, bool]:
    """Insert observation; returns (row_id, is_duplicate)."""
    from sqlalchemy.exc import IntegrityError

    existing = conn.execute(
        select(observations.c.id).where(observations.c.idempotency_key == obs.idempotency_key)
    ).scalar_one_or_none()
    if existing is not None:
        return int(existing), True
    try:
        row_id = insert_observation(conn, obs)
        return row_id, False
    except IntegrityError:
        # Race with a concurrent insert of the same key.
        conn.rollback()
        existing = conn.execute(
            select(observations.c.id).where(observations.c.idempotency_key == obs.idempotency_key)
        ).scalar_one_or_none()
        return (int(existing) if existing is not None else None), True


def prune_history(conn: Any, patient_id: str, now: datetime | None = None) -> int:
    """Bound stored history: keep at most max_history_per_patient rows and
    never older than the configured rolling window times a retention factor.

    Returns the number of rows deleted.
    """
    settings = get_settings()
    now = now or utcnow()
    cutoff = now - timedelta(hours=settings.history_window_hours * 2)
    ids = [
        r[0]
        for r in conn.execute(
            select(observations.c.id)
            .where(observations.c.patient_id == patient_id, observations.c.device_ts < cutoff)
            .order_by(observations.c.device_ts.desc())
        ).all()
    ]
    # Keep within row cap (newest N).
    cap = settings.max_history_per_patient
    all_ids = [
        r[0]
        for r in conn.execute(
            select(observations.c.id)
            .where(observations.c.patient_id == patient_id)
            .order_by(observations.c.device_ts.desc())
        ).all()
    ]
    to_delete = set(ids)
    if len(all_ids) > cap:
        to_delete.update(all_ids[cap:])
    if not to_delete:
        return 0
    result = conn.execute(delete(observations).where(observations.c.id.in_(to_delete)))
    return int(result.rowcount or 0)


def load_window(
    conn: Any,
    patient_id: str,
    as_of: datetime,
    window_hours: float | None = None,
) -> list[dict[str, Any]]:
    """Load observations in the trailing window ending at as_of, ordered by
    device timestamp ascending (ties broken by ingest order / id).
    """
    settings = get_settings()
    hours = window_hours if window_hours is not None else settings.history_window_hours
    start = as_of - timedelta(hours=hours)
    rows = conn.execute(
        select(observations)
        .where(
            observations.c.patient_id == patient_id,
            observations.c.device_ts <= as_of,
            observations.c.device_ts >= start,
        )
        .order_by(observations.c.device_ts.asc(), observations.c.id.asc())
    ).mappings().all()
    return [dict(r) for r in rows]


def is_late(obs_device_ts: datetime, ingest_ts: datetime, threshold_minutes: float = 2.0) -> bool:
    """An observation is 'late' when it arrives noticeably after its device time."""
    return (ingest_ts - obs_device_ts) > timedelta(minutes=threshold_minutes)


def latest_per_vital(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Most recent reading per vital type from an ascending list."""
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        out[row["vital_type"]] = row
    return out
