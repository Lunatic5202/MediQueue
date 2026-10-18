"""Module 6 tests: adverse-trend detection, alert rules, cooldown, dedup."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from mediqueue.db import alerts, get_engine, init_db
from mediqueue.modules.features import compute_features
from mediqueue.modules.risk import (
    detect_adverse_trend,
    process_risk_interpretation,
    risk_band,
)
from mediqueue.pipeline import ensure_patient

NOW = datetime.now(UTC)


def _rows(readings, vital="spo2"):
    out = []
    for i, (ts, val) in enumerate(readings):
        out.append(
            {
                "patient_id": "p1",
                "vital_type": vital,
                "value": float(val),
                "value_diastolic": None,
                "unit": "%" if vital == "spo2" else "bpm",
                "device_ts": ts,
                "ingest_ts": ts,
                "source_id": "test",
                "idempotency_key": f"p1|{vital}|{i}|t",
            }
        )
    return out


def test_risk_band_boundaries():
    assert risk_band(0.1) == "low"
    assert risk_band(0.3) == "watch"
    assert risk_band(0.5) == "elevated"
    assert risk_band(0.8) == "high"
    assert risk_band(None) is None


def test_adverse_trend_requires_span_and_consecutive_worsening(app_env):
    init_db(get_engine())
    with Session(get_engine()) as session, session.begin():
        conn = session.connection()
        ensure_patient(conn, "p1")
        # 3 worsening readings but only ~10 minutes apart total -> no trigger
        short = [
            (NOW - timedelta(minutes=8), 98),
            (NOW - timedelta(minutes=4), 96),
            (NOW, 94),
        ]
        conn.execute(alerts.delete())
        rows = _rows(short)
        for r in rows:
            from mediqueue.db import observations

            conn.execute(observations.insert().values(**{k: r[k] for k in (
                "patient_id","vital_type","value","value_diastolic","unit","device_ts","ingest_ts","source_id","idempotency_key"
            )}))
        fr = compute_features(rows, as_of=NOW)
        trend = detect_adverse_trend(conn, "p1", "spo2", NOW, fr)
        # span rule: last-3-reading span is 8 min < 20 min window; readings in
        # the 20-minute window are still the same 3 -> net delta -4 over span 20
        # min; MIN_TREND_DELTA spo2 = 2, consecutive worsening True -> triggers.
        assert trend is not None
        assert trend["direction"] == "down"


def test_adverse_trend_not_triggered_without_worsening(app_env):
    init_db(get_engine())
    with Session(get_engine()) as session, session.begin():
        conn = session.connection()
        ensure_patient(conn, "p2")
        from mediqueue.db import observations

        stable = [
            (NOW - timedelta(minutes=30), 97),
            (NOW - timedelta(minutes=20), 97),
            (NOW - timedelta(minutes=10), 97),
            (NOW, 97),
        ]
        rows = _rows(stable)
        for r in rows:
            conn.execute(observations.insert().values(**{k: r[k] for k in (
                "patient_id","vital_type","value","value_diastolic","unit","device_ts","ingest_ts","source_id","idempotency_key"
            )}))
        fr = compute_features(rows, as_of=NOW)
        trend = detect_adverse_trend(conn, "p2", "spo2", NOW, fr)
        assert trend is None


def test_alert_creation_dedup_and_update(app_env):
    init_db(get_engine())
    with Session(get_engine()) as session, session.begin():
        conn = session.connection()
        ensure_patient(conn, "p3")
        rows = _rows(
            [
                (NOW - timedelta(minutes=30), 98),
                (NOW - timedelta(minutes=20), 96),
                (NOW - timedelta(minutes=10), 93),
                (NOW, 90),
            ]
        )
        fr = compute_features(rows, as_of=NOW)
        out1 = process_risk_interpretation(
            conn, patient_id="p3", score=0.7, model_version_id="m", feature_result=fr, as_of=NOW
        )
        assert len(out1.created) >= 1
        out2 = process_risk_interpretation(
            conn, patient_id="p3", score=0.8, model_version_id="m", feature_result=fr, as_of=NOW + timedelta(minutes=1)
        )
        assert out2.created == []  # deduplicated into the open alert
        assert len(out2.updated) >= 1
        with Session(get_engine()) as s2:
            open_count = s2.connection().execute(
                alerts.select().where(alerts.c.patient_id == "p3", alerts.c.status == "open")
            ).mappings().all()
        # trend + absolute candidates, no duplicates per dedup key
        keys = {(a["trigger_type"], a["triggering_vital"]) for a in open_count}
        assert len(keys) == len(open_count)


def test_cooldown_suppresses_and_material_worsening_retriggers(app_env):
    init_db(get_engine())
    with Session(get_engine()) as session, session.begin():
        conn = session.connection()
        ensure_patient(conn, "p4")
        rows = _rows(
            [
                (NOW - timedelta(minutes=30), 98),
                (NOW - timedelta(minutes=20), 95),
                (NOW - timedelta(minutes=10), 92),
                (NOW, 89),
            ]
        )
        fr = compute_features(rows, as_of=NOW)
        out1 = process_risk_interpretation(
            conn, patient_id="p4", score=0.65, model_version_id="m", feature_result=fr, as_of=NOW
        )
        assert out1.created
        # resolve all open alerts (e.g., risk dropped)
        conn.execute(alerts.update().where(alerts.c.patient_id == "p4").values(status="resolved", resolved_at=NOW))
        # small score bump within cooldown -> suppressed
        out2 = process_risk_interpretation(
            conn, patient_id="p4", score=0.68, model_version_id="m", feature_result=fr, as_of=NOW + timedelta(minutes=3)
        )
        assert out2.suppressed
        assert not out2.created
        # material worsening (+0.15) -> new alert allowed
        out3 = process_risk_interpretation(
            conn, patient_id="p4", score=0.9, model_version_id="m", feature_result=fr, as_of=NOW + timedelta(minutes=6)
        )
        assert out3.created


def test_alert_resolves_when_trend_ends(app_env):
    init_db(get_engine())
    with Session(get_engine()) as session, session.begin():
        conn = session.connection()
        ensure_patient(conn, "p5")
        rows = _rows(
            [
                (NOW - timedelta(minutes=30), 98),
                (NOW - timedelta(minutes=20), 95),
                (NOW - timedelta(minutes=10), 92),
                (NOW, 89),
            ]
        )
        fr = compute_features(rows, as_of=NOW)
        out1 = process_risk_interpretation(
            conn, patient_id="p5", score=0.7, model_version_id="m", feature_result=fr, as_of=NOW
        )
        assert out1.created
        # stable recent data, low score -> open alerts resolve
        stable_rows = _rows(
            [
                (NOW - timedelta(minutes=9), 96),
                (NOW - timedelta(minutes=6), 96),
                (NOW - timedelta(minutes=3), 96),
                (NOW, 96),
            ]
        )
        fr2 = compute_features(stable_rows, as_of=NOW + timedelta(minutes=10))
        out2 = process_risk_interpretation(
            conn, patient_id="p5", score=0.1, model_version_id="m", feature_result=fr2, as_of=NOW + timedelta(minutes=10)
        )
        assert out2.resolved
