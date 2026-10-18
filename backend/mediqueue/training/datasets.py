"""Dataset loading and synthetic corpus generation (offline path).

Datasets used offline:
- PhysioNet/CinC Challenge 2019: sepsis task with the supplied SepsisLabel.
  Data must be downloaded by the operator under its license (see docs).
- Synthetic corpus: patient timelines with known deterioration onsets, used
  to exercise training/serving parity and the general-deterioration proxy
  label. Synthetic results are system evidence, not clinical evidence.
- MIMIC-IV Demo: small external dataset for a broader deterioration proxy.
  MIMIC-IV Demo requires credentialing; provide pre-extracted CSVs in the
  documented format (see loaders below).

Prediction targets are NOT interchangeable: the sepsis label and the general
deterioration proxy are trained and reported separately.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import get_settings
from ..modules.features import compute_features, feature_names


@dataclass
class PatientSeries:
    patient_id: str
    # Raw observations sorted by device_ts (dicts compatible with compute_features).
    observations: list[dict[str, Any]]
    # (timestamp, label) pairs at label times.
    labels: list[tuple[datetime, int]] = field(default_factory=list)
    positive: bool = False


def _base_obs(patient_id: str, ts: datetime, vital: str, value: float, **extra: Any) -> dict[str, Any]:
    units = {"heart_rate": "bpm", "spo2": "%", "blood_pressure": "mmHg", "temperature": "°C"}
    row = {
        "patient_id": patient_id,
        "vital_type": vital,
        "value": float(value),
        "value_diastolic": extra.get("value_diastolic"),
        "unit": units[vital],
        "device_ts": ts,
        "ingest_ts": ts,
        "source_id": "synthetic",
        "idempotency_key": f"{patient_id}|{vital}|{ts.isoformat()}|synthetic",
    }
    return row


def generate_synthetic_corpus(
    n_patients: int = 600,
    seed: int = 42,
    hours: float = 3.0,
    step_minutes: float = 1.0,
    deteriorating_fraction: float = 0.35,
) -> list[PatientSeries]:
    """Patient timelines with stable and deteriorating trajectories.

    Deterioration onset is hidden from features. Labels mark the onset itself
    and all later samples; build_feature_matrix applies the configured
    prediction horizon when constructing deterioration targets.
    """
    rng = random.Random(seed)
    corpus: list[PatientSeries] = []
    n_steps = int((hours * 60.0) / step_minutes)

    for i in range(n_patients):
        pid = f"syn-{i:05d}"
        deteriorates = rng.random() < deteriorating_fraction
        onset_step = rng.uniform(n_steps * 0.35, n_steps * 0.85) if deteriorates else None

        hr0 = rng.uniform(62, 92)
        spo20 = rng.uniform(95.5, 99.5)
        sbp0 = rng.uniform(100, 135)
        temp0 = rng.uniform(36.3, 37.2)

        obs: list[dict[str, Any]] = []
        labels: list[tuple[datetime, int]] = []
        t0 = datetime(2026, 1, 1, tzinfo=UTC)
        for s in range(n_steps):
            ts = t0 + timedelta(minutes=s * step_minutes)
            mins = s * step_minutes
            if onset_step is not None and mins >= onset_step * step_minutes:
                t = mins - onset_step * step_minutes
                hr = hr0 + min(50.0, 0.9 * t) + rng.gauss(0, 1.5)
                spo2 = spo20 - min(14.0, 0.16 * t) + rng.gauss(0, 0.3)
                sbp = sbp0 - min(45.0, 0.5 * t) + rng.gauss(0, 2.0)
                temp = temp0 + min(2.8, 0.04 * t) + rng.gauss(0, 0.05)
            else:
                hr = hr0 + rng.gauss(0, 1.5)
                spo2 = spo20 + rng.gauss(0, 0.25)
                sbp = sbp0 + rng.gauss(0, 2.0)
                temp = temp0 + rng.gauss(0, 0.04)

            hr = min(210.0, max(35.0, hr))
            spo2 = min(100.0, max(55.0, spo2))
            sbp = min(240.0, max(50.0, sbp))
            dbp = min(180.0, max(25.0, sbp - rng.uniform(30, 55)))
            temp = min(42.5, max(28.0, temp))

            obs.append(_base_obs(pid, ts, "heart_rate", hr))
            obs.append(_base_obs(pid, ts, "spo2", spo2))
            obs.append(_base_obs(pid, ts, "blood_pressure", sbp, value_diastolic=dbp))
            obs.append(_base_obs(pid, ts, "temperature", temp))

            label = 0
            if onset_step is not None:
                onset_min = onset_step * step_minutes
                # Store the observed onset label here. The feature-matrix
                # builder applies the prediction horizon exactly once.
                if mins >= onset_min:
                    label = 1
            labels.append((ts, label))

        corpus.append(
            PatientSeries(
                patient_id=pid,
                observations=obs,
                labels=labels,
                positive=any(l for _, l in labels),
            )
        )
    return corpus


def load_physionet2019(data_dir: str | Path, max_patients: int | None = None) -> list[PatientSeries]:
    """Load PhysioNet/CinC 2019 training files (one CSV per patient).

    Expected columns include: Hour, HR, O2Sat, Temp, SBP, DBP, SepsisLabel.
    Files may live in nested folders (e.g., training_setA). Requires the
    operator to download the dataset under its license.
    """
    root = Path(data_dir)
    files = sorted(root.rglob("*.csv"))
    if not files:
        raise FileNotFoundError(f"no per-patient CSV files under {root}")
    if max_patients is not None:
        files = files[:max_patients]

    corpus: list[PatientSeries] = []
    for f in files:
        try:
            df = pd.read_csv(f)
        except Exception:  # noqa: BLE001 - skip unreadable files
            continue
        cols = {c.lower(): c for c in df.columns}
        if "hour" not in cols or "sepsislabel" not in cols:
            continue
        pid = f.stem

        def col(*names: str) -> str | None:
            for n in names:
                if n.lower() in cols:
                    return cols[n.lower()]
            return None

        c_hr = col("HR")
        c_o2 = col("O2Sat")
        c_temp = col("Temp")
        c_sbp = col("SBP")
        c_dbp = col("DBP")

        obs: list[dict[str, Any]] = []
        labels: list[tuple[datetime, int]] = []
        t0 = datetime(2026, 1, 1, tzinfo=UTC)
        for _, row in df.iterrows():
            hour = float(row[cols["hour"]])
            ts = t0 + timedelta(hours=hour)
            label = int(float(row[cols["sepsislabel"]]) or 0)
            labels.append((ts, label))
            for vital, c, unit in (
                ("heart_rate", c_hr, "bpm"),
                ("spo2", c_o2, "%"),
                ("temperature", c_temp, "°C"),
            ):
                if c is None:
                    continue
                v = row[c]
                if pd.isna(v):
                    continue
                obs.append(
                    {
                        "patient_id": pid,
                        "vital_type": vital,
                        "value": float(v),
                        "value_diastolic": None,
                        "unit": unit,
                        "device_ts": ts,
                        "ingest_ts": ts,
                        "source_id": "physionet2019",
                        "idempotency_key": f"{pid}|{vital}|{ts.isoformat()}|p19",
                    }
                )
            if c_sbp is not None and not pd.isna(row[c_sbp]):
                sbp = float(row[c_sbp])
                dbp = float(row[c_dbp]) if (c_dbp is not None and not pd.isna(row[c_dbp])) else None
                obs.append(
                    {
                        "patient_id": pid,
                        "vital_type": "blood_pressure",
                        "value": sbp,
                        "value_diastolic": dbp,
                        "unit": "mmHg",
                        "device_ts": ts,
                        "ingest_ts": ts,
                        "source_id": "physionet2019",
                        "idempotency_key": f"{pid}|blood_pressure|{ts.isoformat()}|p19",
                    }
                )
        if obs:
            corpus.append(
                PatientSeries(
                    patient_id=pid,
                    observations=obs,
                    labels=labels,
                    positive=any(l for _, l in labels),
                )
            )
    return corpus


def load_generic_csv(path: str | Path) -> list[PatientSeries]:
    """Generic long-format CSV loader (documented in docs/datasets.md).

    Required columns: patient_id, vital_type, value, unit, device_ts, label
    (label is 0/1 at that timestamp; optional).
    """
    df = pd.read_csv(path)
    required = {"patient_id", "vital_type", "value", "unit", "device_ts"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"generic CSV missing columns: {sorted(missing)}")
    df["device_ts"] = pd.to_datetime(df["device_ts"], utc=True)
    corpus: list[PatientSeries] = []
    for pid, group in df.groupby("patient_id"):
        group = group.sort_values("device_ts")
        obs: list[dict[str, Any]] = []
        labels: list[tuple[datetime, int]] = []
        for _, row in group.iterrows():
            ts = row["device_ts"].to_pydatetime()
            obs.append(
                {
                    "patient_id": str(pid),
                    "vital_type": str(row["vital_type"]),
                    "value": float(row["value"]),
                    "value_diastolic": None
                    if ("value_diastolic" not in group.columns or pd.isna(row.get("value_diastolic")))
                    else float(row["value_diastolic"]),
                    "unit": str(row["unit"]),
                    "device_ts": ts,
                    "ingest_ts": ts,
                    "source_id": "generic_csv",
                    "idempotency_key": f"{pid}|{row['vital_type']}|{ts.isoformat()}|generic",
                }
            )
            if "label" in group.columns and not pd.isna(row.get("label")):
                try:
                    label_value = float(row["label"])
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"generic CSV label must be 0 or 1 for patient {pid!r} at {ts.isoformat()}"
                    ) from exc
                if label_value not in (0.0, 1.0):
                    raise ValueError(
                        f"generic CSV label must be 0 or 1 for patient {pid!r} at {ts.isoformat()}"
                    )
                labels.append((ts, int(label_value)))
        corpus.append(
            PatientSeries(
                patient_id=str(pid),
                observations=obs,
                labels=labels,
                positive=any(l for _, l in labels),
            )
        )
    return corpus


def _canonical_json(value: Any) -> str:
    """Serialize dataset values deterministically, including timestamps."""
    def normalize(item: Any) -> Any:
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, dict):
            return {str(key): normalize(val) for key, val in item.items()}
        if isinstance(item, (list, tuple)):
            return [normalize(val) for val in item]
        return item

    return json.dumps(
        normalize(value), sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
    )


def dataset_hash(corpus: Iterable[PatientSeries], params: dict[str, Any] | None = None) -> str:
    """Hash all patient observations, labels, and generation parameters."""
    h = hashlib.sha256()
    h.update(_canonical_json(params or {}).encode("utf-8"))
    h.update(b"\\n")

    # Sorting makes the fingerprint independent of corpus/row iteration order.
    for series in sorted(corpus, key=lambda item: item.patient_id):
        observations = sorted(_canonical_json(row) for row in series.observations)
        labels = sorted((ts.isoformat(), int(label)) for ts, label in series.labels)
        record = {
            "patient_id": series.patient_id,
            "positive": bool(series.positive),
            "observations": observations,
            "labels": labels,
        }
        h.update(_canonical_json(record).encode("utf-8"))
        h.update(b"\\n")
    return h.hexdigest()


def build_feature_matrix(
    corpus: list[PatientSeries],
    grid_minutes: float = 5.0,
    task: str = "deterioration",
) -> pd.DataFrame:
    """Compute training samples at a regular per-patient time grid.

    Features are computed with the SAME window logic used online
    (modules.features.compute_features over the trailing history window).
    Rows with insufficient history are retained but flagged via
    global__low_history; the trainer drops or down-weights them as configured.
    """
    settings = get_settings()
    rows: list[dict[str, Any]] = []
    names = feature_names()

    for series in corpus:
        obs = sorted(series.observations, key=lambda r: r["device_ts"])
        if not obs:
            continue
        start = obs[0]["device_ts"]
        end = obs[-1]["device_ts"]
        label_map = {ts: lab for ts, lab in series.labels}

        grid: list[datetime] = []
        cur = start
        while cur <= end:
            grid.append(cur)
            cur = cur + timedelta(minutes=grid_minutes)

        idx = 0
        for ts in grid:
            while idx + 1 < len(obs) and obs[idx + 1]["device_ts"] <= ts:
                idx += 1
            if obs[idx]["device_ts"] > ts:
                continue
            window = [
                r
                for r in obs
                if ts - timedelta(hours=settings.history_window_hours) <= r["device_ts"] <= ts
            ]
            if not window:
                continue
            fr = compute_features(window, as_of=ts)
            row: dict[str, Any] = {
                "patient_id": series.patient_id,
                "sample_ts": ts,
            }
            for name in names:
                row[name] = fr.features.get(name)
            # Labels: exact grid match when available; else nearest label <= ts.
            if task == "sepsis":
                lab = label_map.get(ts)
                if lab is None:
                    prior = [t for t in label_map if t <= ts]
                    lab = label_map[max(prior)] if prior else 0
            else:
                # Deterioration proxy: positive if any positive label within the
                # prediction horizon after this sample time.
                horizon = timedelta(minutes=settings.deterioration_horizon_minutes)
                lab = 0
                for t, l in series.labels:
                    if l == 1 and ts <= t <= ts + horizon:
                        lab = 1
                        break
                if lab == 0 and label_map.get(ts) == 1:
                    lab = 1
            row["label"] = int(lab)
            rows.append(row)

    return pd.DataFrame(rows)
