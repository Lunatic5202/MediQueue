from __future__ import annotations

from mediqueue.training.datasets import load_physionet2019


def test_load_physionet_official_pipe_separated_psv(tmp_path):
    patient = tmp_path / "training_setA" / "p00001.psv"
    patient.parent.mkdir()
    patient.write_text(
        "Hour|HR|O2Sat|Temp|SBP|DBP|SepsisLabel\n"
        "1|88|98|36.8|120|75|0\n"
        "2|105|95|37.5|110|70|1\n",
        encoding="utf-8",
    )

    corpus = load_physionet2019(tmp_path)

    assert len(corpus) == 1
    series = corpus[0]
    assert series.patient_id == "p00001"
    assert series.positive is True
    assert [label for _, label in series.labels] == [0, 1]
    assert len(series.observations) == 8
    bp = [row for row in series.observations if row["vital_type"] == "blood_pressure"]
    assert bp[0]["value"] == 120.0
    assert bp[0]["value_diastolic"] == 75.0


def test_load_physionet_still_supports_comma_separated_csv(tmp_path):
    patient = tmp_path / "patient.csv"
    patient.write_text(
        "Hour,HR,O2Sat,Temp,SBP,DBP,SepsisLabel\n"
        "1,88,98,36.8,120,75,0\n",
        encoding="utf-8",
    )

    corpus = load_physionet2019(tmp_path)

    assert len(corpus) == 1
    assert corpus[0].positive is False
    assert len(corpus[0].observations) == 4
