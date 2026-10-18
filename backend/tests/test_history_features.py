"""Module 3 & 4 tests: history ordering, duplicates, feature computation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from mediqueue.db import get_engine, init_db, observations
from mediqueue.modules import history
from mediqueue.modules.features import compute_features, feature_names, to_model_vector
from mediqueue.modules.validation import validate_and_normalize

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _obs(pid, vital, value, ts, **extra):
    units = {"heart_rate": "bpm", "spo2": "%", "blood_pressure": "mmHg", "temperature": "°C"}
    payload = {
        "patient_id": pid,
        "vital_type": vital,
        "value": value,
        "unit": units[vital],
        "device_timestamp": ts.isoformat(),
        "source_id": "test",
    }
    payload.update(extra)
    return validate_and_normalize(payload, now=NOW)


def test_duplicate_insert_acknowledged_idempotently(app_env):
    init_db(get_engine())
    with Session(get_engine()) as session, session.begin():
        a = _obs("p1", "heart_rate", 80, NOW - timedelta(minutes=1))
        id1, dup1 = history.insert_observation_idempotent(session.connection(), a)
        id2, dup2 = history.insert_observation_idempotent(session.connection(), a)
    assert dup1 is False and id1 is not None
    assert dup2 is True and id2 == id1
    with Session(get_engine()) as session:
        count = session.connection().execute(
            __import__("sqlalchemy").select(__import__("sqlalchemy").func.count()).select_from(observations)
        ).scalar_one()
    assert count == 1


def test_late_observation_inserted_in_device_time_order(app_env):
    init_db(get_engine())
    with Session(get_engine()) as session, session.begin():
        conn = session.connection()
        history.insert_observation_idempotent(conn, _obs("p1", "spo2", 97, NOW - timedelta(minutes=10)))
        history.insert_observation_idempotent(conn, _obs("p1", "spo2", 93, NOW - timedelta(minutes=5)))
        # late arrival: device time between the two
        history.insert_observation_idempotent(conn, _obs("p1", "spo2", 95, NOW - timedelta(minutes=7)))
        rows = history.load_window(conn, "p1", as_of=NOW)
    values = [r["value"] for r in rows]
    assert values == [97, 95, 93]
    assert history.is_late(NOW - timedelta(minutes=7), NOW, threshold_minutes=2) is True


def test_prune_history_bounds_rows(app_env, monkeypatch):

    monkeypatch.setenv("MEDIQUEUE_MAX_HISTORY_PER_PATIENT", "5")
    monkeypatch.setenv("MEDIQUEUE_HISTORY_WINDOW_HOURS", "4")
    from mediqueue.config import reset_settings

    reset_settings()
    init_db(get_engine())
    with Session(get_engine()) as session, session.begin():
        conn = session.connection()
        for i in range(12):
            history.insert_observation_idempotent(
                conn, _obs("p1", "heart_rate", 70 + i, NOW - timedelta(minutes=30 - i))
            )
        deleted = history.prune_history(conn, "p1", now=NOW)
        rows = history.load_window(conn, "p1", as_of=NOW, window_hours=6)
    assert deleted >= 7
    assert len(rows) <= 5
    reset_settings()


def test_feature_computation_values():
    base = NOW - timedelta(minutes=20)
    rows = [
        {"vital_type": "heart_rate", "value": 70.0, "value_diastolic": None, "unit": "bpm", "device_ts": base},
        {"vital_type": "heart_rate", "value": 80.0, "value_diastolic": None, "unit": "bpm", "device_ts": base + timedelta(minutes=10)},
        {"vital_type": "heart_rate", "value": 90.0, "value_diastolic": None, "unit": "bpm", "device_ts": base + timedelta(minutes=20)},
        {"vital_type": "spo2", "value": 97.0, "value_diastolic": None, "unit": "%", "device_ts": base + timedelta(minutes=20)},
        {"vital_type": "blood_pressure", "value": 110.0, "value_diastolic": 70.0, "unit": "mmHg", "device_ts": base + timedelta(minutes=20)},
    ]
    fr = compute_features(rows, as_of=NOW)
    f = fr.features
    assert f["heart_rate__latest"] == 90.0
    assert f["heart_rate__mean"] == 80.0
    assert f["heart_rate__std"] == 10.0
    assert f["heart_rate__min"] == 70.0
    assert f["heart_rate__max"] == 90.0
    assert abs(f["heart_rate__slope_per_min"] - 1.0) < 1e-9
    # short-horizon delta: latest(90) - reading >=15min ago(70) = 20
    assert f["heart_rate__delta_short_horizon"] == 20.0
    assert f["heart_rate__count"] == 3
    assert f["heart_rate__missing"] == 0.0
    # spo2 has a single reading; delta cannot be computed (missing, not imputed)
    assert f["spo2__delta_short_horizon"] is None
    assert f["spo2__std"] is None
    # shock index = 90 / 110 (stored rounded to 4 decimals)
    assert f["shock_index"] == round(90 / 110, 4)
    assert f["blood_pressure__latest_diastolic"] == 70.0
    # span = 20 min over 5 readings -> confident
    assert fr.low_confidence is False
    assert fr.missing_vitals == ["temperature"]


def test_low_history_flags_insufficient_data():
    rows = [
        {
            "vital_type": "heart_rate",
            "value": 80.0,
            "value_diastolic": None,
            "unit": "bpm",
            "device_ts": NOW - timedelta(minutes=2),
        }
    ]
    fr = compute_features(rows, as_of=NOW)
    assert fr.low_confidence is True
    assert fr.features["global__low_history"] == 1.0


def test_abrupt_change_flagged():
    base = NOW - timedelta(minutes=8)
    rows = [
        {"vital_type": "spo2", "value": 98.0, "value_diastolic": None, "unit": "%", "device_ts": base},
        {"vital_type": "spo2", "value": 90.0, "value_diastolic": None, "unit": "%", "device_ts": base + timedelta(minutes=8)},
    ]
    fr = compute_features(rows, as_of=NOW)
    assert any(flag["vital"] == "spo2" and flag["delta"] == -8.0 for flag in fr.abrupt_changes)


def test_missing_values_stay_null_and_vector_is_nan():
    fr = compute_features([], as_of=NOW)
    assert fr.features["heart_rate__latest"] is None
    vec = to_model_vector(fr.features)
    assert len(vec) == len(feature_names())
    import math

    # Vital-derived entries are NaN; only structural defaults are present.
    names = feature_names()
    hr_idx = names.index("heart_rate__latest")
    spo2_idx = names.index("spo2__latest")
    assert math.isnan(vec[hr_idx])
    assert math.isnan(vec[spo2_idx])
    assert fr.features["global__low_history"] == 1.0
    assert fr.features["heart_rate__count"] is None
    # every vital-latest entry is NaN on an empty window
    for name in names:
        if name.endswith("__latest"):
            assert math.isnan(vec[names.index(name)]), name


def test_minutes_since_last_is_small_age_not_epoch_offset():
    from datetime import datetime, timedelta

    from mediqueue.modules.features import compute_features

    now = datetime.now(UTC)
    rows = [
        {"vital_type": "heart_rate", "value": 80.0, "value_diastolic": None,
         "device_ts": now - timedelta(minutes=m)}
        for m in (12, 6, 3)
    ]
    feats = compute_features(rows, as_of=now).features
    assert abs(feats["heart_rate__minutes_since_last"] - 3.0) < 0.01
    assert abs(feats["global__minutes_since_last_any"] - 3.0) < 0.01
