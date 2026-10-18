"""End-to-end API tests: ingestion -> risk -> alerts -> recommendations ->
clinician decisions -> queue updates -> audit, plus auth, replay, and
fail-safe behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import feed_vitals, mild_series, worsening_series

NOW = datetime.now(timezone.utc)


def test_login_and_auth_required(client):
    assert client.get("/api/queue").status_code == 401
    resp = client.post("/api/auth/login", json={"username": "clinician1", "password": "wrong"})
    assert resp.status_code == 401
    resp = client.post("/api/auth/login", json={"username": "clinician1", "password": "clinician1-pass"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "clinician"
    client.headers.update({"Authorization": f"Bearer {body['token']}"})
    assert client.get("/api/auth/me").status_code == 200


def test_validation_errors_are_422_with_codes(auth_client):
    resp = auth_client.post(
        "/api/observations",
        json={
            "patient_id": "px",
            "vital_type": "heart_rate",
            "value": 999,
            "unit": "bpm",
            "device_timestamp": NOW.isoformat(),
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "out_of_range"


def test_full_triage_lifecycle(auth_client):
    pid = "p-life-1"
    r = auth_client.post("/api/patients", json={"patient_id": pid, "triage_category": 3})
    assert r.status_code == 200

    # First readings: insufficient history -> abstained, never "safe".
    first = worsening_series(n=1)
    r = feed_vitals(auth_client, pid, first)
    assert r.json()["risk_score"] is None
    assert r.json()["low_confidence"] is True

    # Continue the adverse trajectory past the low-history rule.
    r = feed_vitals(auth_client, pid, worsening_series(n=6))
    body = r.json()
    assert body["risk_score"] is not None
    assert body["risk_band"] in ("low", "watch", "elevated", "high")

    risk = auth_client.get(f"/api/patients/{pid}/risk").json()
    assert risk["status"] == "ok"

    queue = auth_client.get("/api/queue").json()["items"]
    item = [q for q in queue if q["patient_id"] == pid][0]
    assert item["triage_category"] == 3
    alerts = auth_client.get("/api/alerts", params={"patient_id": pid}).json()["alerts"]
    assert alerts, "expected adverse-trend alerts for the worsening series"

    # If a pending recommendation exists, exercise confirm path.
    item = [q for q in auth_client.get("/api/queue").json()["items"] if q["patient_id"] == pid][0]
    rec = item["pending_recommendation"]
    if rec:
        resp = auth_client.post(f"/api/recommendations/{rec['id']}/confirm", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"
        assert resp.json()["applied_priority"] == 2  # one step: 3 -> 2
        item = [
            q for q in auth_client.get("/api/queue").json()["items"] if q["patient_id"] == pid
        ][0]
        assert item["triage_category"] == 2

    # Timeline and audit are traceable.
    timeline = auth_client.get(f"/api/patients/{pid}/timeline").json()
    assert timeline["assessments"]
    assert any(a["event_type"] == "patient_registered" for a in auth_client.get("/api/audit?limit=500").json())


def test_duplicate_observation_acknowledged(auth_client):
    pid = "p-dup-1"
    payload = {
        "patient_id": pid,
        "vital_type": "heart_rate",
        "value": 85,
        "unit": "bpm",
        "device_timestamp": (NOW - timedelta(minutes=1)).isoformat(),
        "source_id": "dup-src",
    }
    r1 = auth_client.post("/api/observations", json=payload)
    r2 = auth_client.post("/api/observations", json=payload)
    assert r1.json()["status"] == "accepted"
    assert r2.json()["status"] == "duplicate"
    assert r2.json()["observation_id"] == r1.json()["observation_id"]


def test_late_event_inserted_by_device_timestamp(auth_client):
    pid = "p-late-1"
    feed_vitals(auth_client, pid, worsening_series(n=3, step=10))
    # now insert an older reading (device time 40 min before last)
    older = worsening_series(n=1, end_minutes_ago=45)
    r = feed_vitals(auth_client, pid, older, source="late")
    assert r.status_code == 200
    hist = auth_client.get(f"/api/patients/{pid}/history").json()
    ts = [o["device_ts"] for o in hist["observations"]]
    assert ts == sorted(ts)


def test_reject_requires_rationale_and_override_applies(auth_client):
    pid = "p-dec-1"
    auth_client.post("/api/patients", json={"patient_id": pid, "triage_category": 4})
    feed_vitals(auth_client, pid, mild_series(n=5))
    queue = auth_client.get("/api/queue").json()["items"]
    item = [q for q in queue if q["patient_id"] == pid][0]
    rec = item["pending_recommendation"]
    assert rec is not None, "expected pending recommendation for deteriorating patient"

    # reject without rationale -> 400
    resp = auth_client.post(f"/api/recommendations/{rec['id']}/reject", json={})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "rationale_required"

    # reject with rationale
    resp = auth_client.post(
        f"/api/recommendations/{rec['id']}/reject", json={"rationale": "clinically stable at bedside"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    # stronger worsening: severity upgrades on remaining open alerts -> new rec
    feed_vitals(auth_client, pid, worsening_series(n=6, end_minutes_ago=0))
    item = [q for q in auth_client.get("/api/queue").json()["items"] if q["patient_id"] == pid][0]
    rec2 = item["pending_recommendation"]
    assert rec2 is not None
    resp = auth_client.post(
        f"/api/recommendations/{rec2['id']}/override",
        json={"override_priority": 1, "rationale": "per senior clinician review"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "overridden"
    assert resp.json()["applied_priority"] == 1
    item = [q for q in auth_client.get("/api/queue").json()["items"] if q["patient_id"] == pid][0]
    assert item["triage_category"] == 1


def test_rbac_auditor_cannot_confirm(client):
    token = client.post(
        "/api/auth/login", json={"username": "auditor1", "password": "auditor-pass"}
    ).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    resp = client.post("/api/recommendations/1/confirm", json={})
    assert resp.status_code == 403


def test_inference_failure_marks_prior_score_stale(auth_client, app_env):
    pid = "p-stale-1"
    feed_vitals(auth_client, pid, worsening_series(n=5, end_minutes_ago=10))
    before = auth_client.get(f"/api/patients/{pid}/risk").json()
    assert before["stale"] is False
    assert before["risk_score"] is not None

    from mediqueue.modules.inference import get_inference_engine

    engine = get_inference_engine()
    saved = engine._artifact
    engine._artifact = None
    engine._error = "simulated failure"
    try:
        r = feed_vitals(auth_client, pid, worsening_series(n=6, end_minutes_ago=0))
        body = r.json()
        assert body["risk_score"] is None
        assert body["stale"] is True
    finally:
        engine._artifact = saved
        engine._error = None

    # The previous score is visibly stale, not silently "safe".
    assessments = auth_client.get(f"/api/patients/{pid}/timeline").json()["assessments"]
    stale_rows = [a for a in assessments if a["stale"]]
    assert stale_rows


def test_audit_failure_blocks_success_report(auth_client, monkeypatch):
    pid = "p-audit-fail"
    auth_client.post("/api/patients", json={"patient_id": pid, "triage_category": 3})
    # Enough history that the next observation computes a risk score.
    feed_vitals(auth_client, pid, mild_series(n=5))

    from mediqueue.modules import audit as audit_mod

    original = audit_mod.record_audit

    def failing_record_audit(conn, **kwargs):
        if kwargs.get("event_type") == "risk_score_computed":
            raise audit_mod.AuditWriteError("disk full")
        return original(conn, **kwargs)

    monkeypatch.setattr("mediqueue.pipeline.record_audit", failing_record_audit)

    payload = {
        "patient_id": pid,
        "vital_type": "heart_rate",
        "value": 90,
        "unit": "bpm",
        "device_timestamp": NOW.isoformat(),
    }
    resp = auth_client.post("/api/observations", json=payload)
    assert resp.status_code == 500
    assert resp.json()["detail"]["code"] == "processing_failed"

    # The failed request rolled back: the prior successful score is intact.
    r = auth_client.get(f"/api/patients/{pid}/risk")
    assert r.status_code == 200
    assert r.json()["risk_score"] is not None


def test_audit_events_are_append_only(client):
    from sqlalchemy.exc import DBAPIError
    from sqlalchemy.orm import Session

    from mediqueue.db import audit_events, get_engine, init_db, utcnow

    init_db(get_engine())
    with Session(get_engine()) as session:
        session.execute(
            audit_events.insert().values(
                actor="seed",
                event_type="test_seed",
                entity_type="test",
                entity_id="1",
                payload_json="{}",
                ts=utcnow(),
            )
        )
        session.commit()
        try:
            session.execute(audit_events.update().values(actor="tamper"))
            session.commit()
            raised = False
        except DBAPIError:
            session.rollback()
            raised = True
    assert raised, "UPDATE on audit_events must be rejected by the append-only trigger"


def test_events_polling_endpoint(auth_client):
    pid = "p-ev-1"
    feed_vitals(auth_client, pid, worsening_series(n=2))
    events = auth_client.get("/api/events", params={"since_id": 0, "limit": 500}).json()
    assert events
    assert any(e["topic"] == "observation" for e in events)
    last_id = events[-1]["id"]
    more = auth_client.get("/api/events", params={"since_id": last_id, "limit": 500}).json()
    assert more == [] or all(e["id"] > last_id for e in more)


def test_replay_lifecycle(auth_client):
    resp = auth_client.post(
        "/api/replay/start",
        json={"n_patients": 3, "rate_per_min": 60, "scenario": "stable", "duration_seconds": 3},
    )
    assert resp.status_code == 200
    assert resp.json()["running"] is True
    # second start conflicts
    resp2 = auth_client.post(
        "/api/replay/start",
        json={"n_patients": 3, "rate_per_min": 60, "scenario": "stable", "duration_seconds": 3},
    )
    assert resp2.status_code == 409
    import time

    time.sleep(4)
    status = auth_client.get("/api/replay/status").json()
    assert status["events_emitted"] > 0
    queue = auth_client.get("/api/queue").json()["items"]
    assert any(q["patient_id"].startswith("sim-") for q in queue)


def test_model_info_exposes_version_and_hashes(auth_client, app_env):
    info = auth_client.get("/api/model").json()
    assert info["loaded"] is True
    assert info["model_version_id"] == app_env["version"]
    assert info["feature_schema_hash"]


def test_websocket_requires_token(client):
    try:
        with client.websocket_connect("/ws?token=bogus") as ws:
            ws.receive_text()
            connected = True
    except Exception:  # noqa: BLE001
        connected = False
    assert connected is False
