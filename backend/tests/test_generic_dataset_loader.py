"""Regression tests for generic offline training CSV loading."""

from __future__ import annotations

import pytest

from mediqueue.training.datasets import load_generic_csv


def _write_csv(tmp_path, label: str) -> str:
    path = tmp_path / "observations.csv"
    path.write_text(
        "patient_id,vital_type,value,unit,device_ts,label\n"
        f"p1,heart_rate,80,bpm,2026-01-01T00:00:00Z,{label}\n",
        encoding="utf-8",
    )
    return str(path)


@pytest.mark.parametrize("label", ["0.5", "2", "-1", "abc", "inf"])
def test_generic_csv_rejects_non_binary_labels(tmp_path, label):
    with pytest.raises(ValueError, match="label must be 0 or 1"):
        load_generic_csv(_write_csv(tmp_path, label))


@pytest.mark.parametrize(("label", "expected"), [("0", 0), ("1", 1), ("1.0", 1)])
def test_generic_csv_accepts_binary_labels(tmp_path, label, expected):
    corpus = load_generic_csv(_write_csv(tmp_path, label))

    assert len(corpus) == 1
    assert corpus[0].labels[0][1] == expected
    assert corpus[0].positive is bool(expected)


def test_generic_csv_can_require_labels_for_supervised_use(tmp_path):
    path = tmp_path / "unlabeled.csv"
    path.write_text(
        "patient_id,vital_type,value,unit,device_ts\n"
        "p1,heart_rate,80,bpm,2026-01-01T00:00:00Z\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires a label column"):
        load_generic_csv(path, require_labels=True)


def test_generic_csv_rejects_missing_labels_when_required(tmp_path):
    path = tmp_path / "partially-labeled.csv"
    path.write_text(
        "patient_id,vital_type,value,unit,device_ts,label\n"
        "p1,heart_rate,80,bpm,2026-01-01T00:00:00Z,0\n"
        "p1,spo2,98,%,2026-01-01T00:00:00Z,\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-missing label on every row"):
        load_generic_csv(path, require_labels=True)
