"""Database engine, schema, and helpers (SQLAlchemy Core).

Works with SQLite (default) and PostgreSQL via MEDIQUEUE_DATABASE_URL.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    TypeDecorator,
    create_engine,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from .config import get_settings


class UTCDateTime(TypeDecorator):
    """Timezone-aware datetime column that stays consistent on SQLite and
    PostgreSQL. SQLite stores/returns naive UTC; we re-attach UTC on read."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, datetime) and value.tzinfo is not None:
            value = value.astimezone(UTC)
            if dialect.name == "sqlite":
                value = value.replace(tzinfo=None)
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)

patients = Table(
    "patients",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("display_name", String(128), nullable=True),
    Column("age", Integer, nullable=True),
    Column("sex", String(16), nullable=True),
    Column("arrival_time", UTCDateTime(), nullable=False),
    # Triage category uses ESI-style numbering: 1 = most urgent, 5 = least urgent.
    Column("triage_category", Integer, nullable=False, default=3),
    Column("status", String(16), nullable=False, default="active"),
    Column("created_at", UTCDateTime(), nullable=False),
)

observations = Table(
    "observations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("patient_id", String(64), ForeignKey("patients.id"), nullable=False),
    Column("vital_type", String(32), nullable=False),
    Column("value", Float, nullable=False),
    Column("value_diastolic", Float, nullable=True),
    Column("unit", String(32), nullable=False),
    Column("device_ts", UTCDateTime(), nullable=False),
    Column("ingest_ts", UTCDateTime(), nullable=False),
    Column("source_id", String(64), nullable=False, default="device"),
    Column("idempotency_key", String(256), nullable=False, unique=True),
)

feature_sets = Table(
    "feature_sets",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("patient_id", String(64), ForeignKey("patients.id"), nullable=False),
    Column("computed_at", UTCDateTime(), nullable=False),
    Column("window_start", UTCDateTime(), nullable=False),
    Column("window_end", UTCDateTime(), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("low_confidence", Boolean, nullable=False, default=False),
    Column("missing_vitals_json", Text, nullable=False, default="[]"),
)

risk_assessments = Table(
    "risk_assessments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("patient_id", String(64), ForeignKey("patients.id"), nullable=False),
    # NULL score means abstained (e.g., insufficient history). Never treat as "safe".
    Column("risk_score", Float, nullable=True),
    Column("risk_band", String(16), nullable=True),
    Column("model_version_id", String(64), nullable=True),
    Column("latency_ms", Float, nullable=True),
    Column("status", String(16), nullable=False, default="ok"),  # ok | abstained
    Column("low_confidence", Boolean, nullable=False, default=False),
    Column("stale", Boolean, nullable=False, default=False),
    Column("reason", String(128), nullable=True),
    Column("created_at", UTCDateTime(), nullable=False),
)

alerts = Table(
    "alerts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("patient_id", String(64), ForeignKey("patients.id"), nullable=False),
    Column("trigger_type", String(32), nullable=False),  # absolute_threshold | adverse_trend
    Column("triggering_vital", String(32), nullable=False),  # risk_score or a vital type
    Column("severity", String(16), nullable=False),  # watch | elevated | high
    Column("status", String(16), nullable=False, default="open"),  # open | resolved | suppressed
    Column("dedup_key", String(256), nullable=False),
    Column("explanation_json", Text, nullable=False),
    Column("first_seen", UTCDateTime(), nullable=False),
    Column("last_seen", UTCDateTime(), nullable=False),
    Column("cooldown_until", UTCDateTime(), nullable=True),
    Column("resolved_at", UTCDateTime(), nullable=True),
)

recommendations = Table(
    "recommendations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("patient_id", String(64), ForeignKey("patients.id"), nullable=False),
    Column("alert_id", Integer, ForeignKey("alerts.id"), nullable=True),
    Column("current_priority", Integer, nullable=False),
    Column("proposed_priority", Integer, nullable=False),
    Column("direction", String(16), nullable=False),  # escalate | de_escalate
    Column("status", String(16), nullable=False, default="pending"),
    # pending | confirmed | rejected | overridden | superseded
    Column("rationale", Text, nullable=True),
    Column("created_at", UTCDateTime(), nullable=False),
    Column("decided_at", UTCDateTime(), nullable=True),
    Column("decided_by", String(64), nullable=True),
    Column("applied_priority", Integer, nullable=True),
)

clinician_actions = Table(
    "clinician_actions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("patient_id", String(64), ForeignKey("patients.id"), nullable=False),
    Column("recommendation_id", Integer, ForeignKey("recommendations.id"), nullable=True),
    Column("action", String(32), nullable=False),  # confirm | reject | override | manual_adjust
    Column("previous_priority", Integer, nullable=True),
    Column("new_priority", Integer, nullable=True),
    Column("rationale", Text, nullable=True),
    Column("actor", String(64), nullable=False),
    Column("created_at", UTCDateTime(), nullable=False),
)

clinicians = Table(
    "clinicians",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String(64), nullable=False, unique=True),
    Column("role", String(32), nullable=False),  # clinician | administrator | auditor | system
    Column("password_hash", String(128), nullable=False),
    Column("salt", String(64), nullable=False),
    Column("created_at", UTCDateTime(), nullable=False),
)

revoked_tokens = Table(
    "revoked_tokens",
    metadata,
    Column("jti", String(64), primary_key=True),
    Column("exp", UTCDateTime(), nullable=False),  # purge after this time
    Column("revoked_at", UTCDateTime(), nullable=False),
)

audit_events = Table(
    "audit_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ts", UTCDateTime(), nullable=False),
    Column("actor", String(64), nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("entity_type", String(64), nullable=True),
    Column("entity_id", String(64), nullable=True),
    Column("payload_json", Text, nullable=False, default="{}"),
)

model_versions = Table(
    "model_versions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("kind", String(32), nullable=False),  # lightgbm | logreg
    Column("task", String(32), nullable=False),  # sepsis | deterioration
    Column("artifact_path", String(512), nullable=False),
    Column("dataset_hash", String(64), nullable=False),
    Column("feature_schema_hash", String(64), nullable=False),
    Column("metrics_json", Text, nullable=False, default="{}"),
    Column("created_at", UTCDateTime(), nullable=False),
)

events = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ts", UTCDateTime(), nullable=False),
    Column("topic", String(64), nullable=False),
    Column("patient_id", String(64), nullable=True),
    Column("payload_json", Text, nullable=False),
)

_indexes = [
    Index("ix_observations_patient_ts", observations.c.patient_id, observations.c.device_ts),
    Index("ix_risk_patient_ts", risk_assessments.c.patient_id, risk_assessments.c.created_at),
    Index("ix_alerts_dedup_status", alerts.c.dedup_key, alerts.c.status),
    Index("ix_audit_ts", audit_events.c.ts),
    Index("ix_events_id", events.c.id),
    Index("ix_recommendations_patient_status", recommendations.c.patient_id, recommendations.c.status),
    Index("ix_feature_sets_patient_ts", feature_sets.c.patient_id, feature_sets.c.computed_at),
]

_engine: Engine | None = None


def _ensure_sqlite_dir(url: str) -> None:
    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "", 1)
        if path not in (":memory:", "") and not path.startswith("file:"):
            Path(path).parent.mkdir(parents=True, exist_ok=True)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = get_settings().database_url
        _ensure_sqlite_dir(url)
        kwargs: dict[str, Any] = {"future": True}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(url, **kwargs)
    return _engine


def _install_sqlite_append_only_triggers(engine: Engine) -> None:
    """Enforce append-only audit log at the database layer (SQLite).

    Triggers are persistent database objects; created once (IF NOT EXISTS)
    after the schema exists. On PostgreSQL, grant/revoke rules or event
    triggers should be configured by the DBA (see docs/ibm-z-deployment.md).
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS audit_events_no_update
                BEFORE UPDATE ON audit_events
                BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
                BEFORE DELETE ON audit_events
                BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END
                """
            )
        )


def init_db(engine: Engine | None = None) -> None:
    eng = engine or get_engine()
    # Production schemas are managed by Alembic (`alembic upgrade head`); create_all is
    # a no-op for tables that already exist and is only for dev/tests/first run.
    metadata.create_all(eng)  # includes the secondary indexes above
    if eng.url.get_backend_name() == "sqlite":
        _install_sqlite_append_only_triggers(eng)


def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_json(obj: Any) -> str:
    return json.dumps(obj, default=str, separators=(",", ":"))


def get_session() -> Session:
    return Session(get_engine(), expire_on_commit=False)


def row_dict(row: Any) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def fetch_one(conn: Any, stmt: Any) -> dict[str, Any] | None:
    row = conn.execute(stmt).mappings().first()
    return dict(row) if row is not None else None


def fetch_all(conn: Any, stmt: Any) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(stmt).mappings().all()]
