"""Offline evaluation and reporting (separate evidence from live operation).

Retrospective model metrics and synthetic system-performance results are
reported separately; neither is a claim of clinical effectiveness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from ..modules.features import feature_names
from .datasets import (
    build_feature_matrix,
    generate_synthetic_corpus,
    load_physionet2019,
)
from .train import _metrics, patient_level_split

OPERATING_THRESHOLDS = (0.30, 0.50, 0.60, 0.75, 0.85)  # includes band cutoffs + default alert 0.60


def operating_points(y: np.ndarray, p: np.ndarray, thresholds=OPERATING_THRESHOLDS) -> list[dict]:
    """Precision/recall/alert-rate at fixed thresholds (what the dashboard would do)."""
    rows = []
    for t in thresholds:
        pred = p >= t
        tp = int((pred & (y == 1)).sum())
        fp = int((pred & (y == 0)).sum())
        fn = int((~pred & (y == 1)).sum())
        rows.append(
            {
                "threshold": t,
                "precision": tp / (tp + fp) if tp + fp else float("nan"),
                "recall": tp / (tp + fn) if tp + fn else float("nan"),
                "alert_rate": float(pred.mean()),
            }
        )
    return rows


def calibration(y: np.ndarray, p: np.ndarray, bins: int = 10) -> dict:
    """Brier score, expected calibration error and reliability bins."""
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    rows, ece = [], 0.0
    for b in range(bins):
        m = idx == b
        if not m.any():
            continue
        conf, obs = float(p[m].mean()), float(y[m].mean())
        ece += m.mean() * abs(conf - obs)
        rows.append({"bin": f"{edges[b]:.1f}-{edges[b + 1]:.1f}", "n": int(m.sum()),
                     "mean_predicted": conf, "observed_rate": obs})
    return {"brier": float(np.mean((p - y) ** 2)), "ece": float(ece), "bins": rows}


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
    p_arr = np.asarray(probs)
    metrics = _metrics(y, p_arr, threshold)

    report = {
        "model_version_id": meta["id"],
        "model_task": task,
        "evaluated_dataset": dataset,
        "split": split,
        "threshold": threshold,
        "metrics": metrics,
        "operating_points": operating_points(y, p_arr),
        "calibration": calibration(y, p_arr),
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
        "## Operating points",
        "",
        "| Threshold | Precision | Recall | Alert rate |",
        "| --- | --- | --- | --- |",
        *[
            f"| {o['threshold']:.2f} | {o['precision']:.3f} | {o['recall']:.3f} | {o['alert_rate']:.3f} |"
            for o in report.get("operating_points", [])
        ],
        "",
        "## Calibration",
        "",
        f"Brier score **{report.get('calibration', {}).get('brier', float('nan')):.4f}**, "
        f"expected calibration error **{report.get('calibration', {}).get('ece', float('nan')):.4f}**.",
        "",
        "| Predicted bin | n | Mean predicted | Observed rate |",
        "| --- | --- | --- | --- |",
        *[
            f"| {b['bin']} | {b['n']} | {b['mean_predicted']:.3f} | {b['observed_rate']:.3f} |"
            for b in report.get("calibration", {}).get("bins", [])
        ],
        "",
        f"> {report.get('disclaimer', '')}",
        "",
    ]
    (out / f"{vid}_{report.get('evaluated_dataset')}_{report.get('split')}.md").write_text(
        "\n".join(md), encoding="utf-8"
    )
    return out
