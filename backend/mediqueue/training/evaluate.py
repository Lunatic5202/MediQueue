"""Offline evaluation and reporting (separate evidence from live operation).

Retrospective model metrics and synthetic system-performance results are
reported separately; neither is a claim of clinical effectiveness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..config import get_settings
from ..modules.features import feature_names
from .datasets import (
    build_feature_matrix,
    generate_synthetic_corpus,
    load_physionet2019,
)
from .train import _metrics, patient_level_split


def load_artifact_metadata(artifact_dir: Path) -> dict[str, Any]:
    return json.loads((Path(artifact_dir) / "metadata.json").read_text(encoding="utf-8"))


def evaluate_artifact(
    artifact_dir: str | Path,
    dataset: str = "synthetic",
    data_dir: str | None = None,
    n_patients: int = 300,
    seed: int = 7,
    split: str = "test",
) -> dict[str, Any]:
    """Evaluate a versioned artifact on an independent corpus.

    Uses the artifact's stored threshold. For the synthetic dataset the
    corpus seed differs from training by default to avoid train/test leakage.
    """
    from ..modules.inference import InferenceEngine

    art = Path(artifact_dir)
    meta = load_artifact_metadata(art)
    task = meta["task"]
    threshold = float(meta.get("threshold", 0.5))

    if dataset == "synthetic":
        corpus = generate_synthetic_corpus(n_patients=n_patients, seed=seed)
    elif dataset == "physionet":
        if not data_dir:
            raise ValueError("data_dir required for physionet")
        corpus = load_physionet2019(data_dir)
    else:
        raise ValueError(f"unknown dataset {dataset!r}")

    df = build_feature_matrix(corpus, task=task)
    names = feature_names()
    train_ids, val_ids, test_ids = patient_level_split(corpus, seed=seed)
    chosen = {"test": test_ids, "validation": val_ids, "train": train_ids, "all": None}[split]
    if chosen is not None:
        df = df[df["patient_id"].isin(chosen)]

    engine = InferenceEngine()
    # Load from a pinned version id by pointing artifacts_dir at its parent.
    import os

    prev = os.environ.get("MEDIQUEUE_ARTIFACTS_DIR")
    os.environ["MEDIQUEUE_ARTIFACTS_DIR"] = str(art.parent)
    try:
        from ..config import reset_settings

        reset_settings()
        engine.load(version_id=meta["id"])
    finally:
        if prev is None:
            os.environ.pop("MEDIQUEUE_ARTIFACTS_DIR", None)
        else:
            os.environ["MEDIQUEUE_ARTIFACTS_DIR"] = prev
        reset_settings()

    probs: list[float] = []
    batch = df[names].astype(float).to_numpy()
    # Chunked predict to keep memory bounded on larger corpora.
    for i in range(0, len(batch), 2048):
        chunk = batch[i : i + 2048]
        for row in chunk:
            feats = {n: (None if np.isnan(v) else float(v)) for n, v in zip(names, row)}
            preds = engine.predict(feats)
            probs.append(preds.risk_score)
    y = df["label"].astype(int).to_numpy()
    metrics = _metrics(y, np.asarray(probs), threshold)

    report = {
        "model_version_id": meta["id"],
        "model_task": task,
        "evaluated_dataset": dataset,
        "split": split,
        "threshold": threshold,
        "metrics": metrics,
        "evidence_category": "retrospective_model_performance",
        "disclaimer": (
            "Retrospective public/synthetic data only. Not prospective clinical "
            "validation. Public datasets do not represent the waiting-room "
            "target population. Synthetic system performance is a separate "
            "evidence category."
        ),
    }
    return report


def write_report(report: dict[str, Any], out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    vid = report.get("model_version_id", "unknown")
    (out / f"{vid}_{report.get('evaluated_dataset')}_{report.get('split')}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    m = report["metrics"]
    md = [
        f"# Offline evaluation — {vid}",
        "",
        f"- Task: **{report.get('model_task')}**",
        f"- Dataset: **{report.get('evaluated_dataset')}** ({report.get('split')} split)",
        f"- Threshold: {report.get('threshold')}",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| AUROC | {m.get('auroc', float('nan')):.4f} |",
        f"| AUPRC | {m.get('auprc', float('nan')):.4f} |",
        f"| Precision | {m.get('precision', float('nan')):.4f} |",
        f"| Recall | {m.get('recall', float('nan')):.4f} |",
        f"| F1 | {m.get('f1', float('nan')):.4f} |",
        f"| Prevalence | {m.get('prevalence', float('nan')):.4f} |",
        f"| Samples | {m.get('n_samples')} |",
        "",
        f"> {report.get('disclaimer', '')}",
        "",
    ]
    (out / f"{vid}_{report.get('evaluated_dataset')}_{report.get('split')}.md").write_text(
        "\n".join(md), encoding="utf-8"
    )
    return out
