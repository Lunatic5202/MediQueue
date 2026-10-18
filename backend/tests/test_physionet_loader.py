"""Tests for native PhysioNet/CinC 2019 PSV loading."""

from __future__ import annotations

from mediqueue.training.datasets import load_physionet2019


def test_load_physionet2019_reads_native_pipe_delimited_psv(tmp_path):
    patient = tmp_path / "training_setA" / "p001.psv"
    patient.parent.mkdir()
    patient.write_text(
        "HR|O2Sat|Temp|SBP|DBP|Hour|SepsisLabel\n"
        "80|98|36.8|120|75|1|0\n"
        "110|94|38.1|100|60|2|1\n",
        encoding="utf-8",
    )

    corpus = load_physionet2019(tmp_path)

    assert len(corpus) == 1
    series = corpus[0]
    assert series.patient_id == "p001"
    assert [label for _, label in series.labels] == [0, 1]
    assert series.positive is True
    assert {row["vital_type"] for row in series.observations} == {
        "heart_rate", "spo2", "temperature", "blood_pressure"
    }
    bp = next(row for row in series.observations if row["vital_type"] == "blood_pressure")
    assert bp["value"] == 120
    assert bp["value_diastolic"] == 75


def test_load_physionet2019_keeps_csv_compatibility(tmp_path):
    (tmp_path / "p002.csv").write_text(
        "HR,O2Sat,Temp,SBP,DBP,Hour,SepsisLabel\n"
        "80,98,36.8,120,75,1,0\n",
        encoding="utf-8",
    )

    corpus = load_physionet2019(tmp_path)

    assert len(corpus) == 1
    assert corpus[0].patient_id == "p002"
    assert corpus[0].labels[0][1] == 0


def test_load_physionet2019_limits_number_of_patients(tmp_path):
    for patient_id in ("p001", "p002"):
        (tmp_path / f"{patient_id}.psv").write_text(
            "HR|Hour|SepsisLabel\n80|1|0\n",
            encoding="utf-8",
        )

    corpus = load_physionet2019(tmp_path, max_patients=1)

    assert len(corpus) == 1
