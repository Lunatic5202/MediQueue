"""Offline model training and versioned artifact export.

Patient-level splits (70/15/15 train/validation/held-out test), class-weighted
loss as the default response to imbalance, and versioned artifacts carrying
dataset hash + feature-schema hash. The held-out test set is evaluated once.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ..config import get_settings
from ..modules.features import feature_names, feature_schema_hash
from .datasets import (
    PatientSeries,
    build_feature_matrix,
    dataset_hash,
    generate_synthetic_corpus,
    load_physionet2019,
)


@dataclass
class TrainResult:
    version_id: str
    kind: str
    task: str
    artifact_dir: Path
    metrics: dict[str, Any]
    dataset_hash: str
    feature_schema_hash: str
    n_train: int
    n_val: int
    n_test: int


def patient_level_split(
    corpus: list[PatientSeries], seed: int = 42
) -> tuple[list[str], list[str], list[str]]:
    """70/15/15 patient-level split, stratified by patient positivity."""
    rng_seed = seed
    positives = [s.patient_id for s in corpus if s.positive]
    negatives = [s.patient_id for s in corpus if not s.positive]

    import random

    def split_group(ids: list[str]) -> tuple[list[str], list[str], list[str]]:
        rng = random.Random(rng_seed)
        rng.shuffle(ids)
        n = len(ids)
        n_train = int(n * 0.70)
        n_val = int(n * 0.15)
        return ids[:n_train], ids[n_train : n_train + n_val], ids[n_train + n_val :]

    p_tr, p_va, p_te = split_group(positives)
    n_tr, n_va, n_te = split_group(negatives)
    return p_tr + n_tr, p_va + n_va, p_te + n_te


def _metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> dict[str, float]:
    y_pred = (y_prob >= threshold).astype(int)
    out: dict[str, float] = {}
    out["auroc"] = float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else float("nan")
    out["auprc"] = float(average_precision_score(y_true, y_prob)) if y_true.sum() > 0 else float("nan")
    out["precision"] = float(precision_score(y_true, y_pred, zero_division=0))
    out["recall"] = float(recall_score(y_true, y_pred, zero_division=0))
    out["f1"] = float(f1_score(y_true, y_pred, zero_division=0))
    out["threshold"] = float(threshold)
    out["prevalence"] = float(y_true.mean()) if len(y_true) else float("nan")
    out["n_samples"] = int(len(y_true))
    return out


def _tune_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    best_t, best_f1 = 0.5, -1.0
    for t in np.linspace(0.05, 0.95, 19):
        f1 = f1_score(y_true, (y_prob >= t).astype(int), zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = float(f1), float(t)
    return best_t


def pick_threshold(
    y_true: np.ndarray, y_prob: np.ndarray, target_recall: float | None = 0.80
) -> tuple[float, str]:
    """Sensitivity-first operating point for an early-warning model.

    Returns the highest threshold whose validation recall is >= target_recall
    (fewest alerts that still catch the target share of deteriorations). Falls
    back to the F1-optimal threshold if the target is unreachable or disabled.
    """
    if target_recall is not None:
        for t in np.arange(0.95, 0.049, -0.01):
            pred = (y_prob >= t).astype(int)
            if recall_score(y_true, pred, zero_division=0) >= target_recall:
                return float(round(t, 2)), f"highest threshold with validation recall >= {target_recall:.2f}"
    return _tune_threshold(y_true, y_prob), "F1-optimal on validation"


def train_model(
    task: str = "deterioration",
    dataset: str = "synthetic",
    data_dir: str | None = None,
    n_patients: int = 600,
    seed: int = 42,
    kind: str = "lightgbm",
    out_dir: str | None = None,
    register: bool = True,
    target_recall: float | None = 0.80,
) -> TrainResult:
    settings = get_settings()
    if task not in ("deterioration", "sepsis"):
        raise ValueError("task must be 'deterioration' or 'sepsis'")

    gen_params: dict[str, Any] = {"dataset": dataset, "seed": seed, "n_patients": n_patients, "task": task}
    if dataset == "synthetic":
        corpus = generate_synthetic_corpus(n_patients=n_patients, seed=seed)
    elif dataset == "physionet":
        if not data_dir:
            raise ValueError("data_dir is required for the physionet dataset")
        corpus = load_physionet2019(data_dir)
        gen_params["data_dir"] = str(data_dir)
    else:
        raise ValueError(f"unknown dataset {dataset!r}")

    if not corpus:
        raise ValueError("empty corpus")

    d_hash = dataset_hash(corpus, gen_params)
    f_hash = feature_schema_hash()

    df = build_feature_matrix(corpus, task=task)
    names = feature_names()
    feature_cols = names

    train_ids, val_ids, test_ids = patient_level_split(corpus, seed=seed)
    train_df = df[df["patient_id"].isin(train_ids)]
    val_df = df[df["patient_id"].isin(val_ids)]
    test_df = df[df["patient_id"].isin(test_ids)]

    for split_name, split_df in (("train", train_df), ("validation", val_df), ("test", test_df)):
        if split_df.empty:
            raise ValueError(f"{split_name} split contains no samples; adjust corpus/labels")

    X_train = train_df[feature_cols].astype(float)
    y_train = train_df["label"].astype(int)
    X_val = val_df[feature_cols].astype(float)
    y_val = val_df["label"].astype(int)
    X_test = test_df[feature_cols].astype(float)
    y_test = test_df["label"].astype(int)

    if y_train.nunique() < 2:
        raise ValueError("training split has a single class; adjust corpus/labels")

    pos = float(y_train.sum())
    neg = float(len(y_train) - pos)
    scale_pos_weight = neg / max(pos, 1.0)

    if kind == "lightgbm":
        import lightgbm as lgb

        model = lgb.LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=20,
            subsample=0.9,
            subsample_freq=1,
            colsample_bytree=0.9,
            scale_pos_weight=scale_pos_weight,
            random_state=seed,
            verbose=-1,
        )
        model.fit(X_train, y_train)
        predictor = model
        kind_name = "lightgbm"
    elif kind == "logreg":
        pipe = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                ("scaler", StandardScaler(with_mean=False)),
                (
                    "clf",
                    LogisticRegression(
                        class_weight="balanced", max_iter=2000, random_state=seed
                    ),
                ),
            ]
        )
        pipe.fit(X_train, y_train)
        predictor = pipe
        kind_name = "logreg"
    else:
        raise ValueError("kind must be 'lightgbm' or 'logreg'")

    def probs(X: pd.DataFrame) -> np.ndarray:
        if kind_name == "lightgbm":
            return np.asarray(predictor.predict_proba(X[feature_cols].astype(float))[:, 1])
        return np.asarray(predictor.predict_proba(X)[:, 1])

    # Calibrate raw scores on the validation split (class weighting distorts
    # probabilities). Thresholds below are chosen on calibrated validation scores;
    # the test split is untouched until the single final evaluation.
    from sklearn.isotonic import IsotonicRegression

    calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    calibrator.fit(probs(X_val), y_val.to_numpy())
    raw_probs = probs

    def probs(X: pd.DataFrame) -> np.ndarray:  # noqa: F811 - calibrated scorer
        return np.asarray(calibrator.predict(raw_probs(X)))

    y_val_prob = probs(X_val)
    best_t, threshold_policy = pick_threshold(y_val.to_numpy(), y_val_prob, target_recall)

    # Held-out test evaluated exactly once, at the tuned threshold.
    y_test_prob = probs(X_test)
    test_metrics = _metrics(y_test.to_numpy(), y_test_prob, best_t)
    val_metrics = _metrics(y_val.to_numpy(), y_val_prob, best_t)

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    version_id = f"{task}-{kind_name}-{ts}-{d_hash[:8]}"
    root = Path(out_dir or settings.artifacts_dir) / version_id
    root.mkdir(parents=True, exist_ok=True)

    if kind_name == "lightgbm":
        booster = predictor.booster_
        booster.save_model(str(root / "model.txt"))
    else:
        joblib.dump(predictor, root / "model.joblib")

    joblib.dump(calibrator, root / "calibrator.joblib")

    metrics = {
        "validation": val_metrics,
        "test": test_metrics,
        "train_samples": int(len(train_df)),
        "val_samples": int(len(val_df)),
        "test_samples": int(len(test_df)),
        "positive_rate_train": float(y_train.mean()),
        "class_imbalance_note": (
            "Class-weighted loss used (scale_pos_weight / class_weight=balanced). "
            "SMOTE not used: synthetic minority trajectories may be implausible."
        ),
    }
    meta = {
        "id": version_id,
        "kind": kind_name,
        "task": task,
        "dataset": dataset,
        "dataset_hash": d_hash,
        "training_seed": seed,
        "split_patient_counts": {
            "train": int(train_df["patient_id"].nunique()),
            "validation": int(val_df["patient_id"].nunique()),
            "test": int(test_df["patient_id"].nunique()),
        },
        "feature_schema_hash": f_hash,
        "feature_order": feature_cols,
        "threshold": best_t,
        "threshold_policy": threshold_policy,
        "calibration": "isotonic regression fitted on the validation split",
        "metrics": metrics,
        "created_at": datetime.now(UTC).isoformat(),
    }
    (root / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    if register:
        _register_in_db(meta, root)

    return TrainResult(
        version_id=version_id,
        kind=kind_name,
        task=task,
        artifact_dir=root,
        metrics=metrics,
        dataset_hash=d_hash,
        feature_schema_hash=f_hash,
        n_train=len(train_df),
        n_val=len(val_df),
        n_test=len(test_df),
    )


def _register_in_db(meta: dict[str, Any], artifact_dir: Path) -> None:
    from ..db import get_engine, init_db, model_versions, utcnow

    init_db()
    with get_engine().begin() as conn:
        conn.execute(
            model_versions.insert().values(
                id=meta["id"],
                kind=meta["kind"],
                task=meta["task"],
                artifact_path=str(artifact_dir.resolve()),
                dataset_hash=meta["dataset_hash"],
                feature_schema_hash=meta["feature_schema_hash"],
                metrics_json=json.dumps(meta["metrics"]),
                created_at=utcnow(),
            )
        )
