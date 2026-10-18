""""Content-addressed fingerprint tests for offline training datasets."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def _series(patient_id="p1", value=80.0, label_offset=10):
    from mediqueue.training.datasets import PatientSeries

    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = [
        {
            "patient_id": patient_id,
            "vital_type": "heart_rate",
            "value": value,
            "unit": "bpm",
            "device_ts": start,
        },
        {
            "patient_id": patient_id,
            "vital_type": "spo2",
            "value": 98.0,
            "unit": "%",
            "device_ts": start + timedelta(minutes=5),
        },
    ]
    return PatientSeries(
        patient_id=patient_id,
        observations=observations,
        labels=[(start + timedelta(minutes=label_offset), 1)],
        positive=True,
    )


def test_dataset_hash_changes_when_observation_value_changes():
    from mediqueue.training.datasets import dataset_hash

    assert dataset_hash([_series(value=80.0)]) != dataset_hash([_series(value=81.0)])


def test_dataset_hash_changes_when_label_timestamp_changes():
    from mediqueue.training.datasets import dataset_hash

    assert dataset_hash([_series(label_offset=10)]) != dataset_hash([_series(label_offset=15)])


def test_dataset_hash_is_stable_under_row_and_corpus_reordering():
    from mediqueue.training.datasets import dataset_hash

    first = _series("p1")
    second = _series("p2", value=90.0)
    reordered = _series("p1")
    reordered.observations.reverse()

    assert dataset_hash([first, second]) == dataset_hash([second, reordered])


def test_dataset_hash_includes_generation_parameters():
    from mediqueue.training.datasets import dataset_hash

    assert dataset_hash([_series()], {"seed": 1}) != dataset_hash([_series()], {"seed": 2})


def test_dataset_hash_changes_when_label_class_changes():
    from mediqueue.training.datasets import dataset_hash

    positive = _series()
    negative = _series()
    negative.labels = [(timestamp, 0) for timestamp, _ in negative.labels]
    negative.positive = False

    assert dataset_hash([positive]) != dataset_hash([negative])


def test_dataset_hash_changes_when_patient_identity_changes():
    from mediqueue.training.datasets import dataset_hash

    assert dataset_hash([_series(patient_id="p1")]) != dataset_hash([_series(patient_id="p2")])
"