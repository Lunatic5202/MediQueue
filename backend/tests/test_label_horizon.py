"""Regression tests for the offline deterioration prediction horizon."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def test_synthetic_labels_start_at_observed_onset(monkeypatch):
    from mediqueue.config import reset_settings
    from mediqueue.training.datasets import generate_synthetic_corpus

    monkeypatch.setenv("MEDIQUEUE_DETERIORATION_HORIZON_MINUTES", "30")
    reset_settings()
    try:
        series = generate_synthetic_corpus(
            n_patients=1, seed=42, hours=1, step_minutes=1, deteriorating_fraction=1.0
        )[0]
        positive_times = [ts for ts, label in series.labels if label == 1]
        assert positive_times
        # The onset is sampled no earlier than 35% of the 60-minute series.
        # Raw event labels must not already be shifted backward by 30 minutes.
        assert (positive_times[0] - series.labels[0][0]).total_seconds() / 60 >= 21
    finally:
        reset_settings()


def test_feature_matrix_applies_prediction_horizon_once(monkeypatch):
    from mediqueue.config import reset_settings
    from mediqueue.training.datasets import PatientSeries, build_feature_matrix

    monkeypatch.setenv("MEDIQUEUE_DETERIORATION_HORIZON_MINUTES", "30")
    reset_settings()
    try:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        observations = []
        for minute in range(0, 61, 5):
            ts = start + timedelta(minutes=minute)
            for vital, value, unit in (
                ("heart_rate", 80.0, "bpm"),
                ("spo2", 98.0, "%"),
                ("blood_pressure", 120.0, "mmHg"),
                ("temperature", 36.8, "°C"),
            ):
                observations.append(
                    {
                        "patient_id": "synthetic-test",
                        "vital_type": vital,
                        "value": value,
                        "value_diastolic": 80.0 if vital == "blood_pressure" else None,
                        "unit": unit,
                        "device_ts": ts,
                        "ingest_ts": ts,
                        "source_id": "test",
                        "idempotency_key": f"{vital}-{minute}",
                    }
                )
        event_time = start + timedelta(minutes=40)
        series = PatientSeries(
            patient_id="synthetic-test",
            observations=observations,
            labels=[(event_time, 1)],
            positive=True,
        )

        frame = build_feature_matrix([series], grid_minutes=5, task="deterioration")
        labels = frame.set_index("sample_ts")["label"]
        assert labels.loc[start + timedelta(minutes=10)] == 1
        assert labels.loc[start + timedelta(minutes=5)] == 0
        assert labels.loc[event_time] == 1
    finally:
        reset_settings()
