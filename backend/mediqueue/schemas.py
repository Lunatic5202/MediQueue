"""Pydantic request/response contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

VitalType = Literal["heart_rate", "spo2", "blood_pressure", "temperature"]
Role = Literal["clinician", "administrator", "auditor", "system"]
PriorityCategory = int  # ESI-style: 1 most urgent .. 5 least urgent


class PatientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(min_length=1, max_length=64)
    display_name: str | None = Field(default=None, max_length=128)
    age: int | None = Field(default=None, ge=0, le=130)
    sex: str | None = Field(default=None, max_length=16)
    arrival_time: datetime | None = None
    triage_category: PriorityCategory = Field(default=3, ge=1, le=5)


class ObservationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(min_length=1, max_length=64)
    vital_type: VitalType
    value: float
    # Diastolic value for blood_pressure observations (systolic is `value`).
    value_diastolic: float | None = None
    unit: str = Field(min_length=1, max_length=32)
    device_timestamp: datetime
    ingest_timestamp: datetime | None = None
    source_id: str = Field(default="device", max_length=64)


class ObservationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    patient_id: str
    vital_type: str
    value: float
    value_diastolic: float | None = None
    unit: str
    device_ts: datetime
    ingest_ts: datetime
    source_id: str


class IngestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["accepted", "duplicate"]
    observation_id: int | None = None
    processing_ms: float
    risk_assessment_id: int | None = None
    risk_score: float | None = None
    risk_band: str | None = None
    low_confidence: bool = False
    stale: bool = False
    alert_ids: list[int] = Field(default_factory=list)
    recommendation_ids: list[int] = Field(default_factory=list)
    stages_ms: dict[str, float] = Field(default_factory=dict)
    detail: str | None = None


class RiskAssessmentOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    patient_id: str
    risk_score: float | None
    risk_band: str | None
    model_version_id: str | None
    latency_ms: float | None
    status: str
    low_confidence: bool
    stale: bool
    reason: str | None
    created_at: datetime


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    vital_type: str | None = None
    value: float | None = None
    value_diastolic: float | None = None
    unit: str | None = None
    device_ts: datetime | None = None
    note: str | None = None


class AlertOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    patient_id: str
    trigger_type: str
    triggering_vital: str
    severity: str
    status: str
    explanation: dict[str, Any]
    first_seen: datetime
    last_seen: datetime
    cooldown_until: datetime | None
    resolved_at: datetime | None


class RecommendationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    patient_id: str
    alert_id: int | None
    current_priority: int
    proposed_priority: int
    direction: str
    status: str
    rationale: str | None
    created_at: datetime
    decided_at: datetime | None
    decided_by: str | None
    applied_priority: int | None


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rationale: str | None = Field(default=None, max_length=2000)
    # For override: clinician-directed priority (1..5). Required for override.
    override_priority: PriorityCategory | None = Field(default=None, ge=1, le=5)


class QueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str
    display_name: str | None
    arrival_time: datetime
    triage_category: int
    status: str
    latest_risk_score: float | None
    latest_risk_band: str | None
    latest_assessment_stale: bool
    latest_assessment_low_confidence: bool
    latest_assessment_status: str | None
    latest_assessment_at: datetime | None
    model_version_id: str | None
    pending_recommendation: RecommendationOut | None = None
    open_alert_count: int = 0


class QueueOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    items: list[QueueItem]


class AuditEventOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    ts: datetime
    actor: str
    event_type: str
    entity_type: str | None
    entity_id: str | None
    payload: dict[str, Any]


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class LoginOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    role: str
    username: str
    expires_at: datetime


class ReplayStartIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n_patients: int = Field(default=20, ge=1, le=500)
    rate_per_min: float = Field(default=30.0, gt=0, le=1000)
    scenario: Literal["mixed", "stable", "sepsis_like", "respiratory_decline"] = "mixed"
    duration_seconds: float | None = Field(default=None, gt=0, le=3600)


class ReplayStatusOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    running: bool
    n_patients: int
    rate_per_min: float
    scenario: str
    events_emitted: int
    started_at: datetime | None
    finished_at: datetime | None
    last_error: str | None


class EventOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    ts: datetime
    topic: str
    patient_id: str | None
    payload: dict[str, Any]


class ModelInfoOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_version_id: str | None
    kind: str | None
    task: str | None
    dataset_hash: str | None
    feature_schema_hash: str | None
    metrics: dict[str, Any]
    created_at: datetime | None
    loaded: bool
    detail: str | None


class HealthOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    version: str
    model_loaded: bool
    database: str
    time: datetime
