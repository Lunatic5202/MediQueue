"""Module 5: ML Inference.

Loads a versioned model artifact and scores feature vectors. Returns
risk_score in [0,1], model_version_id, and inference latency. On any failure
the pipeline must NOT create a new score; the previous score is marked stale
and the failure is logged (see pipeline.py).
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from ..config import get_settings
from .features import feature_names


class InferenceError(Exception):
    pass


@dataclass
class ModelArtifact:
    version_id: str
    kind: str  # lightgbm | logreg
    task: str  # sepsis | deterioration
    dataset_hash: str
    feature_schema_hash: str
    metrics: dict[str, Any]
    created_at: str
    predictor: Any
    feature_order: list[str]
    calibrator: Any = None  # optional isotonic map raw score -> calibrated probability


@dataclass
class Prediction:
    risk_score: float
    model_version_id: str
    latency_ms: float


class InferenceEngine:
    """Process-wide model holder with explicit load/refresh."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._artifact: ModelArtifact | None = None
        self._error: str | None = None

    @property
    def loaded(self) -> bool:
        return self._artifact is not None

    @property
    def error(self) -> str | None:
        return self._error

    def artifact(self) -> ModelArtifact:
        if self._artifact is None:
            raise InferenceError(self._error or "model not loaded")
        return self._artifact

    def info(self) -> dict[str, Any]:
        if self._artifact is None:
            return {
                "model_version_id": None,
                "kind": None,
                "task": None,
                "dataset_hash": None,
                "feature_schema_hash": None,
                "metrics": {},
                "created_at": None,
                "loaded": False,
                "detail": self._error or "model not loaded",
            }
        a = self._artifact
        return {
            "model_version_id": a.version_id,
            "kind": a.kind,
            "task": a.task,
            "dataset_hash": a.dataset_hash,
            "feature_schema_hash": a.feature_schema_hash,
            "metrics": a.metrics,
            "created_at": a.created_at,
            "loaded": True,
            "detail": None,
        }

    def load(self, version_id: str | None = None) -> ModelArtifact:
        settings = get_settings()
        root = Path(settings.artifacts_dir)
        with self._lock:
            try:
                artifact = self._load_locked(root, version_id, settings.model_version)
                self._artifact = artifact
                self._error = None
                return artifact
            except Exception as exc:  # noqa: BLE001 - surfaced to callers/ops
                self._artifact = None
                self._error = f"model load failed: {exc}"
                raise InferenceError(self._error) from exc

    def _load_locked(
        self, root: Path, version_id: str | None, pinned: str
    ) -> ModelArtifact:
        requested = version_id or pinned or ""
        if requested:
            model_dir = root / requested
            if not model_dir.is_dir():
                raise InferenceError(f"model version {requested!r} not found under {root}")
        else:
            candidates = sorted(
                [p for p in root.iterdir() if p.is_dir() and (p / "metadata.json").exists()],
                key=lambda p: p.stat().st_mtime,
            )
            if not candidates:
                raise InferenceError(f"no model artifacts under {root}; run scripts/train_model.py")
            model_dir = candidates[-1]

        meta = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8"))
        kind = meta["kind"]
        if kind == "lightgbm":
            import lightgbm as lgb

            predictor = lgb.Booster(model_file=str(model_dir / "model.txt"))
        elif kind == "logreg":
            predictor = joblib.load(model_dir / "model.joblib")
        else:
            raise InferenceError(f"unknown model kind {kind!r}")

        cal_path = model_dir / "calibrator.joblib"
        calibrator = joblib.load(cal_path) if cal_path.exists() else None

        return ModelArtifact(
            version_id=meta["id"],
            kind=kind,
            task=meta.get("task", "unknown"),
            dataset_hash=meta.get("dataset_hash", ""),
            feature_schema_hash=meta.get("feature_schema_hash", ""),
            metrics=meta.get("metrics", {}),
            created_at=meta.get("created_at", ""),
            predictor=predictor,
            feature_order=meta.get("feature_order", feature_names()),
            calibrator=calibrator,
        )

    def predict(self, features: dict[str, float | None]) -> Prediction:
        artifact = self.artifact()
        vector = self._align(features, artifact.feature_order)
        arr = np.asarray([vector], dtype=float)
        start = time.perf_counter()
        try:
            if artifact.kind == "lightgbm":
                raw = artifact.predictor.predict(arr)
                score = float(np.asarray(raw).reshape(-1)[0])
            else:
                # logreg pipeline: imputer handles NaN; decision function -> proba
                if hasattr(artifact.predictor, "predict_proba"):
                    score = float(artifact.predictor.predict_proba(arr)[0, 1])
                else:
                    score = float(artifact.predictor.predict(arr)[0])
        except Exception as exc:  # noqa: BLE001
            raise InferenceError(f"prediction failed: {exc}") from exc
        if artifact.calibrator is not None:
            score = float(artifact.calibrator.predict([score])[0])
        latency_ms = (time.perf_counter() - start) * 1000.0
        score = min(1.0, max(0.0, score))
        return Prediction(risk_score=score, model_version_id=artifact.version_id, latency_ms=latency_ms)

    @staticmethod
    def _align(features: dict[str, float | None], order: list[str]) -> list[float]:
        vec: list[float] = []
        for name in order:
            val = features.get(name)
            vec.append(float("nan") if val is None else float(val))
        return vec


_engine: InferenceEngine | None = None


def get_inference_engine() -> InferenceEngine:
    global _engine
    if _engine is None:
        _engine = InferenceEngine()
    return _engine


def reset_inference_engine() -> None:
    global _engine
    _engine = None
