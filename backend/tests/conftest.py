"""Shared pytest fixtures: in-memory app, tiny deterministic model artifact."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    """Configure an isolated in-memory environment and import the app."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("MEDIQUEUE_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("MEDIQUEUE_SECRET_KEY", "test-secret")
    monkeypatch.setenv("MEDIQUEUE_MIN_BAND_FOR_RECOMMENDATION", "watch")
    artifacts = tmp_path / "models"
    artifacts.mkdir()
    monkeypatch.setenv("MEDIQUEUE_ARTIFACTS_DIR", str(artifacts))

    from mediqueue.config import reset_settings

    reset_settings()
    from mediqueue.security import reset_login_throttle

    reset_login_throttle()

    # Build a tiny deterministic logreg artifact trained on REAL feature rows
    # (from the synthetic corpus + the shared feature-engineering code), so
    # scores behave sensibly on pipeline-computed features.
    import joblib
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    from mediqueue.modules.features import feature_names
    from mediqueue.training.datasets import build_feature_matrix, generate_synthetic_corpus

    names = feature_names()
    corpus = generate_synthetic_corpus(
        n_patients=80, seed=11, hours=1.5, step_minutes=5.0
    )
    df = build_feature_matrix(corpus, task="deterioration")
    X = df[names].astype(float).to_numpy()
    y = df["label"].astype(int).to_numpy()
    if y.sum() == 0 or y.sum() == len(y):
        y = y.copy()
        y[0], y[1] = 0, 1
    model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler(with_mean=False)),
            ("clf", LogisticRegression(max_iter=800)),
        ]
    )
    model.fit(X, y)

    version = "test-logreg-000"
    vdir = artifacts / version
    vdir.mkdir()
    joblib.dump(model, vdir / "model.joblib")
    (vdir / "metadata.json").write_text(
        json.dumps(
            {
                "id": version,
                "kind": "logreg",
                "task": "deterioration",
                "dataset": "synthetic",
                "dataset_hash": "testhash",
                "feature_schema_hash": "testschema",
                "feature_order": names,
                "threshold": 0.5,
                "metrics": {},
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        )
    )

    from mediqueue.db import dispose_engine, get_engine, init_db
    from mediqueue.modules.inference import get_inference_engine, reset_inference_engine
    from mediqueue.security import ensure_seed_users

    dispose_engine()
    reset_inference_engine()
    reset_settings()

    engine = get_engine()
    init_db(engine)
    ensure_seed_users()
    get_inference_engine().load(version)

    from fastapi.testclient import TestClient

    from mediqueue.app import create_app

    application = create_app()
    with TestClient(application) as client:
        yield {"client": client, "artifacts": artifacts, "version": version}

    dispose_engine()
    reset_inference_engine()
    reset_settings()


@pytest.fixture()
def client(app_env):
    return app_env["client"]


@pytest.fixture()
def token(client) -> str:
    resp = client.post(
        "/api/auth/login", json={"username": "clinician1", "password": "clinician1-pass"}
    )
    assert resp.status_code == 200
    return resp.json()["token"]


@pytest.fixture()
def auth_client(client, token):
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def feed_vitals(
    client,
    patient_id: str,
    readings: list[tuple[datetime, float, float, float, float]],
    source: str = "test",
):
    """readings: (ts, hr, spo2, sbp, temp); dbp derived as sbp-40."""
    for ts, hr, spo2, sbp, temp in readings:
        for payload in (
            {
                "patient_id": patient_id,
                "vital_type": "heart_rate",
                "value": hr,
                "unit": "bpm",
                "device_timestamp": ts.isoformat(),
                "source_id": source,
            },
            {
                "patient_id": patient_id,
                "vital_type": "spo2",
                "value": spo2,
                "unit": "%",
                "device_timestamp": ts.isoformat(),
                "source_id": source,
            },
            {
                "patient_id": patient_id,
                "vital_type": "blood_pressure",
                "value": sbp,
                "value_diastolic": sbp - 40,
                "unit": "mmHg",
                "device_timestamp": ts.isoformat(),
                "source_id": source,
            },
            {
                "patient_id": patient_id,
                "vital_type": "temperature",
                "value": temp,
                "unit": "°C",
                "device_timestamp": ts.isoformat(),
                "source_id": source,
            },
        ):
            resp = client.post("/api/observations", json=payload)
            assert resp.status_code == 200, resp.text
    return resp


def worsening_series(n: int = 6, end_minutes_ago: float = 0.0, step: float = 5.0):
    """SpO2 falling and HR rising over the series (adverse trajectories)."""
    now = datetime.now(UTC)
    start = now - timedelta(minutes=end_minutes_ago + step * (n - 1))
    rows = []
    for i in range(n):
        ts = start + timedelta(minutes=step * i)
        rows.append((ts, 80 + 6 * i, 98 - 1.5 * i, 120 - 3 * i, 36.8 + 0.05 * i))
    return rows


def mild_series(n: int = 5, end_minutes_ago: float = 0.0, step: float = 5.0):
    """Gentle adverse drift: enough to trigger alerts with upgrade headroom."""
    now = datetime.now(UTC)
    start = now - timedelta(minutes=end_minutes_ago + step * (n - 1))
    rows = []
    for i in range(n):
        ts = start + timedelta(minutes=step * i)
        rows.append((ts, 78 + 2.5 * i, 97.5 - 0.4 * i, 122 - 1.5 * i, 36.7 + 0.02 * i))
    return rows
