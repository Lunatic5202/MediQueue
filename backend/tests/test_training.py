"""Module 10 / offline path tests: training, versioning, evaluation."""

from __future__ import annotations

import json


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
    assert 0.0 <= report["metrics"]["auroc"] <= 1.0 or report["metrics"]["auroc"] != report["metrics"]["auroc"]
    out = write_report(report, tmp_path / "reports")
    files = list(out.glob("*.md"))
    assert files
    assert "AUROC" in files[0].read_text()
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



def test_dataset_hash_changes_when_observation_changes():
    from copy import deepcopy
    from mediqueue.training.datasets import dataset_hash, generate_synthetic_corpus

    corpus = generate_synthetic_corpus(n_patients=2, seed=17)
    original = dataset_hash(corpus, {"dataset": "synthetic"})
    changed = deepcopy(corpus)
    changed[0].observations[0]["value"] += 0.25

    assert dataset_hash(corpus, {"dataset": "synthetic"}) == original
    assert dataset_hash(changed, {"dataset": "synthetic"}) != original


def test_dataset_hash_changes_when_label_changes():
    from copy import deepcopy
    from mediqueue.training.datasets import dataset_hash, generate_synthetic_corpus

    corpus = generate_synthetic_corpus(n_patients=2, seed=17)
    changed = deepcopy(corpus)
    ts, label = changed[0].labels[0]
    changed[0].labels[0] = (ts, 1 - label)

    assert dataset_hash(changed) != dataset_hash(corpus)


def test_dataset_hash_is_independent_of_corpus_order():
    from mediqueue.training.datasets import dataset_hash, generate_synthetic_corpus

    corpus = generate_synthetic_corpus(n_patients=4, seed=21)
    assert dataset_hash(corpus) == dataset_hash(list(reversed(corpus)))


def test_synthetic_data_cannot_train_sepsis_task():
    import pytest
    from mediqueue.training.train import train_model

    with pytest.raises(ValueError, match="not sepsis"):
        train_model(task="sepsis", dataset="synthetic", n_patients=20, register=False)
