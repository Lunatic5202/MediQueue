"""Module 10 / offline path tests: training, versioning, evaluation."""

from __future__ import annotations

import json

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
    assert (result.artifact_dir / "model.joblib").exists()
    assert "auroc" in meta["metrics"]["test"]
    assert meta["metrics"]["test"]["n_samples"] > 0

    from mediqueue.db import get_engine, init_db, model_versions
    from sqlalchemy.orm import Session

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
