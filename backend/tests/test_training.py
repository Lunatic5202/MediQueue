"""Module 10 / offline path tests: training, versioning, evaluation."""

from __future__ import annotations

import json

import pandas as pd
import pytest


def test_train_creates_versioned_artifact_with_hashes(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIQUEUE_DATABASE_URL", f"sqlite:///{tmp_path/'t.db'}")
    monkeypatch.setenv("MEDIQUEUE_ARTIFACTS_DIR", str(tmp_path / "models"))
    from mediqueue.config import reset_settings

    reset_settings()

    from mediqueue.training.train import train_model

    result = train_model(
        task="deterioration",
        dataset="synthetic",
        n_patients=40,
        seed=3,
        kind="logreg",
        out_dir=str(tmp_path / "models"),
        register=True,
    )
    assert result.kind == "logreg"
    meta = json.loads((result.artifact_dir / "metadata.json").read_text())
    assert meta["dataset_hash"] == result.dataset_hash
    assert meta["feature_schema_hash"] == result.feature_schema_hash
    assert meta["training_seed"] == 3
    patient_counts = meta["split_patient_counts"]
    assert set(patient_counts) == {"train", "validation", "test"}
    assert sum(patient_counts.values()) == 40
    assert (result.artifact_dir / "model.joblib").exists()
    assert "auroc" in meta["metrics"]["test"]
    assert meta["metrics"]["test"]["n_samples"] > 0

    from sqlalchemy.orm import Session

    from mediqueue.db import get_engine, init_db, model_versions

    init_db()
    with Session(get_engine()) as session:
        row = session.connection().execute(
            model_versions.select().where(model_versions.c.id == result.version_id)
        ).mappings().first()
    assert row is not None
    reset_settings()


def test_evaluate_artifact_writes_report(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIQUEUE_DATABASE_URL", f"sqlite:///{tmp_path/'t.db'}")
    monkeypatch.setenv("MEDIQUEUE_ARTIFACTS_DIR", str(tmp_path / "models"))
    from mediqueue.config import reset_settings

    reset_settings()

    from mediqueue.training.evaluate import evaluate_artifact, write_report
    from mediqueue.training.train import train_model

    result = train_model(
        task="deterioration",
        dataset="synthetic",
        n_patients=30,
        seed=5,
        kind="logreg",
        out_dir=str(tmp_path / "models"),
        register=False,
    )
    report = evaluate_artifact(
        result.artifact_dir, dataset="synthetic", n_patients=15, seed=123, split="all"
    )
    assert report["evidence_category"] == "retrospective_model_performance"
    assert len(report["evaluation_dataset_hash"]) == 64
    assert report["evaluation_patient_count"] == 15
    assert report["evaluation_sample_count"] == report["metrics"]["n_samples"]
    assert report["evaluation_seed"] == 123
    assert 0.0 <= report["metrics"]["auroc"] <= 1.0 or report["metrics"]["auroc"] != report["metrics"]["auroc"]
    out = write_report(report, tmp_path / "reports")
    files = list(out.glob("*.md"))
    assert files
    assert "AUROC" in files[0].read_text()
    assert "Evaluation dataset fingerprint" in files[0].read_text()
    reset_settings()


def test_patient_level_split_has_no_overlap():
    from mediqueue.training.datasets import PatientSeries
    from mediqueue.training.train import patient_level_split

    corpus = [
        PatientSeries(patient_id=f"p{i}", observations=[], labels=[], positive=(i % 4 == 0))
        for i in range(100)
    ]
    tr, va, te = patient_level_split(corpus, seed=1)
    assert len(set(tr) & set(va)) == 0
    assert len(set(tr) & set(te)) == 0
    assert len(set(va) & set(te)) == 0
    assert len(tr) + len(va) + len(te) == 100
    # ~70/15/15
    assert 0.6 <= len(tr) / 100 <= 0.8


def test_pick_threshold_is_recall_first():
    import numpy as np

    from mediqueue.training.train import pick_threshold

    y = np.array([1] * 10 + [0] * 90)
    p = np.concatenate([np.linspace(0.5, 0.95, 10), np.linspace(0.0, 0.6, 90)])
    t, policy = pick_threshold(y, p, target_recall=0.9)
    assert ((p >= t)[y == 1].mean()) >= 0.9 and "recall" in policy
    t_f1, policy_f1 = pick_threshold(y, p, target_recall=None)
    assert "F1" in policy_f1


def test_trained_artifact_is_calibrated(tmp_path):
    from mediqueue.training.train import train_model

    r = train_model(n_patients=60, out_dir=str(tmp_path), register=False)
    assert (r.artifact_dir / "calibrator.joblib").exists()



def test_evaluate_rejects_unknown_split_before_loading_data(tmp_path):
    from mediqueue.training.evaluate import evaluate_artifact

    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "metadata.json").write_text(
        json.dumps({"id": "test-model", "task": "deterioration", "threshold": 0.5})
    )

    with pytest.raises(ValueError, match="split must be one of"):
        evaluate_artifact(artifact, split="production")


def test_evaluate_rejects_empty_selected_split(tmp_path, monkeypatch):
    from mediqueue.training import evaluate
    from mediqueue.training.datasets import PatientSeries

    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "metadata.json").write_text(
        json.dumps({"id": "test-model", "task": "deterioration", "threshold": 0.5})
    )
    monkeypatch.setattr(
        evaluate, "generate_synthetic_corpus",
        lambda **kwargs: [PatientSeries("p1", observations=[], labels=[], positive=False)],
    )
    monkeypatch.setattr(
        evaluate, "build_feature_matrix",
        lambda corpus, task: pd.DataFrame({"patient_id": ["p1"], "label": [0]}),
    )
    monkeypatch.setattr(evaluate, "patient_level_split", lambda corpus, seed: (["p1"], [], []))

    with pytest.raises(ValueError, match="evaluation split 'test' contains no samples"):
        evaluate.evaluate_artifact(artifact, dataset="synthetic", split="test")



@pytest.mark.parametrize("empty_split", ["train", "validation", "test"])
def test_train_rejects_empty_patient_split(tmp_path, monkeypatch, empty_split):
    from mediqueue.training import train
    from mediqueue.training.datasets import PatientSeries

    corpus = [
        PatientSeries("p1", observations=[], labels=[], positive=True),
        PatientSeries("p2", observations=[], labels=[], positive=False),
    ]
    monkeypatch.setattr(train, "generate_synthetic_corpus", lambda **kwargs: corpus)
    monkeypatch.setattr(
        train, "build_feature_matrix",
        lambda corpus, task: pd.DataFrame({
            "patient_id": ["p1", "p2"], "label": [1, 0], "feature": [1.0, 0.0]
        }),
    )
    monkeypatch.setattr(train, "feature_names", lambda: ["feature"])
    split_ids = {
        "train": ([], ["p1"], ["p2"]),
        "validation": (["p1"], [], ["p2"]),
        "test": (["p1"], ["p2"], []),
    }
    monkeypatch.setattr(train, "patient_level_split", lambda corpus, seed: split_ids[empty_split])

    with pytest.raises(ValueError, match=f"{empty_split} split contains no samples"):
        train.train_model(
            dataset="synthetic", n_patients=2, kind="logreg",
            out_dir=str(tmp_path), register=False,
        )
