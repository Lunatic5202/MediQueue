"""HTTP API surface (FastAPI routers)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import desc, func, select

from . import __version__
from .config import get_settings
from .db import (
    alerts,
    events,
    feature_sets,
    get_engine,
    get_session,
    patients,
    recommendations,
    risk_assessments,
    utcnow,
)
from .modules.audit import query_audit
from .modules.history import load_window
from .modules.inference import get_inference_engine
from .modules.recommendation import (
    RecommendationError,
    confirm_recommendation,
    list_recommendations,
    override_recommendation,
    reject_recommendation,
)
from .modules.simulator import get_replay_state, start_replay, stop_replay
from .pipeline import PipelineError, process_observation
from .realtime import hub
from .schemas import (
    AuditEventOut,
    DecisionIn,
    EventOut,
    HealthOut,
    IngestResult,
    LoginIn,
    LoginOut,
    ModelInfoOut,
    ObservationIn,
    PatientCreate,
    QueueOut,
    ReplayStartIn,
    ReplayStatusOut,
    RiskAssessmentOut,
)
from .security import (
    AuditorUser,
    ClinicianUser,
    ReplayOperator,
    check_login_allowed,
    clear_login_failures,
    current_user,
    issue_token,
    record_login_failure,
    revoke_token,
    verify_credentials,
)

api = APIRouter(prefix="/api")


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
@api.post("/auth/login", response_model=LoginOut, tags=["auth"])
def login(body: LoginIn, request: Request) -> Any:
    ip = request.client.host if request.client else "unknown"
    wait = check_login_allowed(ip, body.username)
    if wait:
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts; try again later",
            headers={"Retry-After": str(wait)},
        )
    user = verify_credentials(body.username, body.password)
    if user is None:
        record_login_failure(ip, body.username)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    clear_login_failures(ip, body.username)
    token, expires = issue_token(user["username"], user["role"])
    return LoginOut(token=token, role=user["role"], username=user["username"], expires_at=expires)


@api.get("/auth/me", tags=["auth"])
async def me(user: dict = Depends(current_user)) -> Any:
    return {"username": user["username"], "role": user["role"]}


@api.post("/auth/logout", tags=["auth"])
def logout(user: dict = Depends(current_user)) -> Any:
    revoke_token(user["token"])
    return {"status": "logged_out"}


# --------------------------------------------------------------------------
# Health & model info
# --------------------------------------------------------------------------
@api.get("/health", response_model=HealthOut, tags=["system"])
def health() -> Any:
    engine = get_inference_engine()
    db_url = get_settings().database_url.split("://")[0]
    return HealthOut(
        status="ok",
        version=__version__,
        model_loaded=engine.loaded,
        database=db_url,
        time=utcnow(),
    )


@api.get("/model", response_model=ModelInfoOut, tags=["system"])
def model_info() -> Any:
    return ModelInfoOut(**get_inference_engine().info())


# --------------------------------------------------------------------------
# Patients
# --------------------------------------------------------------------------
@api.post("/patients", tags=["patients"])
def create_patient(body: PatientCreate, user: dict = Depends(ClinicianUser)) -> Any:
    now = utcnow()
    with get_engine().begin() as conn:
        existing = conn.execute(
            select(patients.c.id).where(patients.c.id == body.patient_id)
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status_code=409, detail="patient_id already registered")
        conn.execute(
            patients.insert().values(
                id=body.patient_id,
                display_name=body.display_name,
                age=body.age,
                sex=body.sex,
                arrival_time=body.arrival_time or now,
                triage_category=body.triage_category,
                status="active",
                created_at=now,
            )
        )
        from .modules.audit import record_audit

        record_audit(
            conn,
            actor=user["username"],
            event_type="patient_registered",
            entity_type="patient",
            entity_id=body.patient_id,
            payload={"triage_category": body.triage_category},
        )
    return {"patient_id": body.patient_id, "triage_category": body.triage_category}


@api.get("/patients", tags=["patients"])
def list_patients(limit: int = Query(default=200, le=1000), user: dict = Depends(current_user)) -> Any:
    with get_session() as session:
        rows = session.execute(
            select(patients).order_by(desc(patients.c.arrival_time)).limit(limit)
        ).mappings().all()
    return [_row_json(r) for r in rows]


def _row_json(row: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in dict(row).items():
        out[k] = v.isoformat() if isinstance(v, datetime) else v
    return out


@api.get("/patients/{patient_id}", tags=["patients"])
def get_patient(patient_id: str, user: dict = Depends(current_user)) -> Any:
    with get_session() as session:
        row = session.execute(select(patients).where(patients.c.id == patient_id)).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="patient not found")
    return _row_json(row)


# --------------------------------------------------------------------------
# Observations (ingestion)
# --------------------------------------------------------------------------
@api.post("/observations", response_model=IngestResult, tags=["ingestion"])
async def submit_observation(body: ObservationIn, request: Request, user: dict = Depends(ClinicianUser)) -> Any:
    from .realtime import hub as realtime_hub

    payload = body.model_dump(mode="json")
    try:
        with get_engine().begin() as conn:
            result = process_observation(conn, payload, actor=user["username"])
        committed_events = result.events
    except PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message})
    except Exception as exc:  # includes AuditWriteError -> rollback already happened
        raise HTTPException(
            status_code=500,
            detail={"code": "processing_failed", "message": f"observation not accepted: {exc}"},
        )

    if committed_events:
        await realtime_hub.broadcast(
            [{"topic": e["topic"], "patient_id": e["patient_id"], "payload": e["data"]} for e in committed_events]
        )

    processing_ms = sum(result.stages_ms.values())
    return IngestResult(
        status=result.status,  # type: ignore[arg-type]
        observation_id=result.observation_id,
        processing_ms=round(processing_ms, 3),
        risk_assessment_id=result.risk_assessment_id,
        risk_score=result.risk_score,
        risk_band=result.risk_band,
        low_confidence=result.low_confidence,
        stale=result.stale,
        alert_ids=result.alert_ids,
        recommendation_ids=result.recommendation_ids,
        stages_ms={k: round(v, 3) for k, v in result.stages_ms.items()},
        detail=result.detail,
    )


# --------------------------------------------------------------------------
# Risk & history
# --------------------------------------------------------------------------
def _latest_assessment(conn: Any, patient_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        select(risk_assessments)
        .where(risk_assessments.c.patient_id == patient_id)
        .order_by(risk_assessments.c.id.desc())
        .limit(1)
    ).mappings().first()
    return dict(row) if row else None


@api.get("/patients/{patient_id}/risk", response_model=RiskAssessmentOut, tags=["risk"])
def latest_risk(patient_id: str, user: dict = Depends(current_user)) -> Any:
    with get_session() as session:
        row = _latest_assessment(session.connection(), patient_id)
    if row is None:
        raise HTTPException(status_code=404, detail="no risk assessment for patient")
    return row


@api.get("/patients/{patient_id}/history", tags=["history"])
def patient_history(
    patient_id: str,
    window_hours: float | None = Query(default=None, gt=0, le=24),
    user: dict = Depends(current_user),
) -> Any:
    as_of = utcnow()
    with get_session() as session:
        conn = session.connection()
        rows = load_window(conn, patient_id, as_of=as_of, window_hours=window_hours)
        feat_row = conn.execute(
            select(feature_sets)
            .where(feature_sets.c.patient_id == patient_id)
            .order_by(feature_sets.c.id.desc())
            .limit(1)
        ).mappings().first()
        latest = _latest_assessment(conn, patient_id)

    features_payload: dict[str, Any] | None = None
    if feat_row:
        features_payload = {
            "computed_at": feat_row["computed_at"].isoformat(),
            "low_confidence": feat_row["low_confidence"],
            "missing_vitals": json.loads(feat_row["missing_vitals_json"] or "[]"),
            "features": json.loads(feat_row["payload_json"] or "{}"),
        }
    return {
        "patient_id": patient_id,
        "as_of": as_of.isoformat(),
        "observations": [
            {
                "id": r["id"],
                "vital_type": r["vital_type"],
                "value": r["value"],
                "value_diastolic": r["value_diastolic"],
                "unit": r["unit"],
                "device_ts": r["device_ts"].isoformat(),
                "ingest_ts": r["ingest_ts"].isoformat(),
                "source_id": r["source_id"],
            }
            for r in rows
        ],
        "latest_features": features_payload,
        "latest_assessment": None
        if latest is None
        else {
            "risk_score": latest["risk_score"],
            "risk_band": latest["risk_band"],
            "status": latest["status"],
            "stale": latest["stale"],
            "low_confidence": latest["low_confidence"],
            "created_at": latest["created_at"].isoformat(),
        },
    }


@api.get("/patients/{patient_id}/timeline", tags=["risk"])
def patient_timeline(patient_id: str, limit: int = Query(default=100, le=500), user: dict = Depends(current_user)) -> Any:
    with get_session() as session:
        conn = session.connection()
        assessments = conn.execute(
            select(risk_assessments)
            .where(risk_assessments.c.patient_id == patient_id)
            .order_by(risk_assessments.c.id.desc())
            .limit(limit)
        ).mappings().all()
        alert_rows = conn.execute(
            select(alerts)
            .where(alerts.c.patient_id == patient_id)
            .order_by(alerts.c.id.desc())
            .limit(limit)
        ).mappings().all()
        recs = conn.execute(
            select(recommendations)
            .where(recommendations.c.patient_id == patient_id)
            .order_by(recommendations.c.id.desc())
            .limit(limit)
        ).mappings().all()

    def _alert_json(r: dict[str, Any]) -> dict[str, Any]:
        out = _row_json(r)
        out["explanation"] = json.loads(r["explanation_json"] or "{}")
        out.pop("explanation_json", None)
        out.pop("dedup_key", None)
        return out

    return {
        "patient_id": patient_id,
        "assessments": [
            {
                **_row_json(a),
            }
            for a in assessments
        ],
        "alerts": [_alert_json(dict(a)) for a in alert_rows],
        "recommendations": [_row_json(r) for r in recs],
    }


# --------------------------------------------------------------------------
# Alerts
# --------------------------------------------------------------------------
@api.get("/alerts", tags=["alerts"])
def list_active_alerts(
    status: Literal["open", "resolved", "suppressed", "all"] | None = "open",
    patient_id: str | None = None,
    limit: int = Query(default=200, le=1000),
    user: dict = Depends(current_user),
) -> Any:
    stmt = select(alerts).order_by(desc(alerts.c.last_seen)).limit(limit)
    if status and status != "all":
        stmt = stmt.where(alerts.c.status == status)
    if patient_id:
        stmt = stmt.where(alerts.c.patient_id == patient_id)
    with get_session() as session:
        rows = session.execute(stmt).mappings().all()
    out = []
    for r in rows:
        item = _row_json(dict(r))
        item["explanation"] = json.loads(r["explanation_json"] or "{}")
        item.pop("explanation_json", None)
        item.pop("dedup_key", None)
        out.append(item)
    return {"alerts": out}


# --------------------------------------------------------------------------
# Queue & recommendations
# --------------------------------------------------------------------------
def _rec_json(r: dict[str, Any]) -> dict[str, Any]:
    return _row_json(r)


@api.get("/queue", response_model=QueueOut, tags=["queue"])
def get_queue(user: dict = Depends(current_user)) -> Any:
    now = utcnow()
    with get_session() as session:
        conn = session.connection()
        active = conn.execute(
            select(patients)
            .where(patients.c.status == "active")
            .order_by(patients.c.triage_category.asc(), patients.c.arrival_time.asc())
        ).mappings().all()

        items = []
        for p in active:
            p = dict(p)
            latest = _latest_assessment(conn, p["id"])
            pending = conn.execute(
                select(recommendations)
                .where(
                    recommendations.c.patient_id == p["id"],
                    recommendations.c.status == "pending",
                )
                .order_by(desc(recommendations.c.id))
                .limit(1)
            ).mappings().first()
            open_alert_count = conn.execute(
                select(func.count())
                .select_from(alerts)
                .where(alerts.c.patient_id == p["id"], alerts.c.status == "open")
            ).scalar_one()
            items.append(
                {
                    "patient_id": p["id"],
                    "display_name": p["display_name"],
                    "arrival_time": p["arrival_time"],
                    "triage_category": p["triage_category"],
                    "status": p["status"],
                    "latest_risk_score": latest["risk_score"] if latest else None,
                    "latest_risk_band": latest["risk_band"] if latest else None,
                    "latest_assessment_stale": bool(latest["stale"]) if latest else False,
                    "latest_assessment_low_confidence": bool(latest["low_confidence"]) if latest else False,
                    "latest_assessment_status": latest["status"] if latest else "none",
                    "latest_assessment_at": latest["created_at"] if latest else None,
                    "model_version_id": latest["model_version_id"] if latest else None,
                    "pending_recommendation": _rec_json(dict(pending)) if pending else None,
                    "open_alert_count": int(open_alert_count),
                }
            )
    return QueueOut(generated_at=now, items=items)  # type: ignore[arg-type]


@api.get("/recommendations", tags=["queue"])
def get_recommendations(
    status: str | None = None,
    patient_id: str | None = None,
    limit: int = Query(default=100, le=500),
    user: dict = Depends(current_user),
) -> Any:
    with get_session() as session:
        rows = list_recommendations(session.connection(), patient_id=patient_id, status=status, limit=limit)
    return {"recommendations": [_rec_json(r) for r in rows]}


def _apply_decision(
    rec_id: int, action: str, body: DecisionIn, username: str
) -> dict[str, Any]:
    try:
        with get_engine().begin() as conn:
            if action == "confirm":
                row = confirm_recommendation(conn, rec_id, username, body.rationale)
            elif action == "reject":
                row = reject_recommendation(conn, rec_id, username, body.rationale)
            elif action == "override":
                if body.override_priority is None:
                    raise RecommendationError("invalid_priority", "override_priority is required")
                row = override_recommendation(
                    conn, rec_id, username, body.override_priority, body.rationale
                )
            else:
                raise RecommendationError("invalid_action", f"unknown action {action}")
            from .db import patients as patients_tbl
            from .modules.audit import record_audit

            record_audit(
                conn,
                actor=username,
                event_type="queue_event",
                entity_type="patient",
                entity_id=row["patient_id"],
                payload={
                    "action": action,
                    "recommendation_id": rec_id,
                    "applied_priority": row.get("applied_priority"),
                },
            )
            patient = conn.execute(
                select(patients_tbl.c.triage_category).where(patients_tbl.c.id == row["patient_id"])
            ).scalar_one()
        final_row = row
        final_row["queue_priority_now"] = int(patient)
    except RecommendationError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message})
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "decision_failed", "message": f"decision not applied: {exc}"},
        )
    return final_row


async def _broadcast_queue_event(rec: dict[str, Any], action: str) -> None:
    await hub.broadcast(
        [
            {
                "topic": "queue_update",
                "patient_id": rec.get("patient_id"),
                "payload": {
                    "recommendation_id": rec.get("id"),
                    "action": action,
                    "status": rec.get("status"),
                    "applied_priority": rec.get("applied_priority"),
                    "queue_priority_now": rec.get("queue_priority_now"),
                },
            }
        ]
    )


@api.post("/recommendations/{rec_id}/confirm", tags=["queue"])
async def api_confirm(rec_id: int, body: DecisionIn, user: dict = Depends(ClinicianUser)) -> Any:
    row = _apply_decision(rec_id, "confirm", body, user["username"])
    await _broadcast_queue_event(row, "confirm")
    return _rec_json(row)


@api.post("/recommendations/{rec_id}/reject", tags=["queue"])
async def api_reject(rec_id: int, body: DecisionIn, user: dict = Depends(ClinicianUser)) -> Any:
    row = _apply_decision(rec_id, "reject", body, user["username"])
    await _broadcast_queue_event(row, "reject")
    return _rec_json(row)


@api.post("/recommendations/{rec_id}/override", tags=["queue"])
async def api_override(rec_id: int, body: DecisionIn, user: dict = Depends(ClinicianUser)) -> Any:
    row = _apply_decision(rec_id, "override", body, user["username"])
    await _broadcast_queue_event(row, "override")
    return _rec_json(row)


# --------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------
@api.get("/audit", response_model=list[AuditEventOut], tags=["audit"])
def get_audit(
    event_type: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    since_id: int | None = None,
    limit: int = Query(default=200, le=1000),
    user: dict = Depends(AuditorUser),
) -> Any:
    with get_session() as session:
        rows = query_audit(
            session.connection(),
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            since_id=since_id,
            limit=limit,
        )
    return rows


@api.get("/audit/export", tags=["audit"])
def export_audit(
    event_type: str | None = None,
    limit: int = Query(default=5000, le=20000),
    user: dict = Depends(AuditorUser),
) -> Any:
    with get_session() as session:
        rows = query_audit(session.connection(), event_type=event_type, limit=limit)
    content = json.dumps(rows, indent=2, default=str)
    return JSONResponse(
        content=json.loads(content),
        headers={"Content-Disposition": "attachment; filename=mediqueue_audit.json"},
    )


# --------------------------------------------------------------------------
# Events (polling fallback)
# --------------------------------------------------------------------------
@api.get("/events", response_model=list[EventOut], tags=["realtime"])
def get_events(since_id: int = Query(default=0, ge=0), limit: int = Query(default=100, le=1000), user: dict = Depends(current_user)) -> Any:
    with get_session() as session:
        rows = session.execute(
            select(events).where(events.c.id > since_id).order_by(events.c.id.asc()).limit(limit)
        ).mappings().all()
    out = []
    for r in rows:
        out.append(
            EventOut(
                id=r["id"],
                ts=r["ts"],
                topic=r["topic"],
                patient_id=r["patient_id"],
                payload=json.loads(r["payload_json"] or "{}"),
            )
        )
    return out


# --------------------------------------------------------------------------
# Synthetic replay controls
# --------------------------------------------------------------------------
@api.post("/replay/start", response_model=ReplayStatusOut, tags=["replay"])
async def api_replay_start(body: ReplayStartIn, user: dict = Depends(ReplayOperator)) -> Any:
    try:
        state = await start_replay(
            n_patients=body.n_patients,
            rate_per_min=body.rate_per_min,
            scenario=body.scenario,
            duration_seconds=body.duration_seconds,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    with get_engine().begin() as conn:
        from .modules.audit import record_audit

        record_audit(
            conn,
            actor=user["username"],
            event_type="replay_started",
            entity_type="replay",
            entity_id="synthetic",
            payload={
                "n_patients": body.n_patients,
                "rate_per_min": body.rate_per_min,
                "scenario": body.scenario,
            },
        )
    return _replay_status(state)


@api.post("/replay/stop", response_model=ReplayStatusOut, tags=["replay"])
async def api_replay_stop(user: dict = Depends(ReplayOperator)) -> Any:
    state = stop_replay()
    return _replay_status(state)


@api.get("/replay/status", response_model=ReplayStatusOut, tags=["replay"])
async def api_replay_status() -> Any:
    return _replay_status(get_replay_state())


def _replay_status(state: Any) -> ReplayStatusOut:
    return ReplayStatusOut(
        running=state.running,
        n_patients=state.n_patients,
        rate_per_min=state.rate_per_min,
        scenario=state.scenario,
        events_emitted=state.events_emitted,
        started_at=state.started_at,
        finished_at=state.finished_at,
        last_error=state.last_error,
    )
