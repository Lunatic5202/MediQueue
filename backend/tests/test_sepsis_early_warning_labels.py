"""Regression tests for early-warning labels on PhysioNet sepsis timelines."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mediqueue.training.datasets import PatientSeries, build_feature_matrix


def _series_with_onset(onset_hour: int | None) -> PatientSeries:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = []
    labels = []
    for hour in range(10):
        ts = start + timedelta(hours=hour)
        observations.append({
            "patient_id": "p1",
            "vital_type": "heart_rate",
            "value": 80.0 + hour,
            "value_diastolic": None,
            "unit": "bpm",
            "device_ts": ts,
            "ingest_ts": ts,
            "source_id": "test",
            "idempotency_key": f"p1|hr|{hour}",
        })
        labels.append((ts, int(onset_hour is not None and hour >= onset_hour)))
    return PatientSeries(
        patient_id="p1",
        observations=observations,
        labels=labels,
        positive=onset_hour is not None,
    )


def test_sepsis_target_marks_six_hours_before_onset_and_excludes_onset():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    frame = build_feature_matrix([_series_with_onset(8)], grid_minutes=60, task="sepsis")
    labels_by_hour = {
        int((row.sample_ts - start).total_seconds() // 3600): int(row.label)
        for row in frame.itertuples()
    }

    # Six hours before onset (hour 2) through the last pre-onset hour are
    # positive; earlier observations are negative, and hour 8+ is excluded.
    assert labels_by_hour == {
        0: 0, 1: 0, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1
    }


def test_sepsis_target_without_onset_keeps_all_samples_negative():
    frame = build_feature_matrix([_series_with_onset(None)], grid_minutes=60, task="sepsis")

    assert len(frame) == 10
    assert set(frame["label"]) == {0}
