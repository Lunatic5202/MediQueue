# Datasets

MediQueue trains and evaluates on datasets loaded through
`backend/mediqueue/training/datasets.py`. **No dataset is redistributed in
this repository** — operators download public datasets under their own
licenses.

## Supported datasets

### 1. Synthetic corpus (default; built-in)

- Generated in-process by `generate_synthetic_corpus()`; no download needed.
- Patient timelines (default 3 h, 1-min or 5-min cadence) with 4 vitals;
  ~35 % of patients have a hidden deterioration onset.
- **Label (general-deterioration proxy):** positive from
  `deterioration_horizon_minutes` (default 30) before onset **through series
  end** — a deteriorated patient stays at risk, so the worst states are not
  labeled negative.
- **Evidence category: system evidence only.** Synthetic performance shows
  the pipeline works; it is *not* clinical evidence and must never be
  reported as model clinical performance.

```bash
.venv/bin/python scripts/train_model.py --dataset synthetic --n-patients 600
```

### 2. PhysioNet/CinC Challenge 2019 (sepsis task)

- Website: https://physionet.org/content/challenge-2019/1.0.0/
- License: PhysioNet Credentialed Health Data License 1.5.0 — credentialing
  and a signed DUA are required. Download yourself; do not commit the files.
- Expected layout: one CSV per patient (e.g. `training_setA/*.csv`) with
  columns `Hour, HR, O2Sat, Temp, SBP, DBP, SepsisLabel` (column names
  matched case-insensitively).
- **Label: the supplied `SepsisLabel`.** This sepsis label is a *different
  clinical target* from the general-deterioration proxy — never blend the
  two labels, never mix their metrics in one report.

```bash
.venv/bin/python scripts/train_model.py --task sepsis --dataset physionet \
  --data-dir /secure/downloads/physionet2019/training_setA
```

### 3. MIMIC-IV Demo / generic CSV

- MIMIC-IV Demo requires credentialing (PhysioNet). Export pre-extracted
  long-format CSVs; do not commit patient data.
- **Generic CSV format** (`load_generic_csv`), long format, required columns:

  | column | type | notes |
  | --- | --- | --- |
  | patient_id | str | |
  | vital_type | str | `heart_rate` \| `spo2` \| `blood_pressure` \| `temperature` |
  | value | float | systolic for BP |
  | value_diastolic | float, optional | diastolic for BP |
  | unit | str | `bpm` \| `%` \| `mmHg` \| `°C` |
  | device_ts | ISO-8601 | measurement time |
  | label | 0/1, optional | per-timestamp label |

## Feature-engineering parity

`build_feature_matrix()` computes training samples with the **same
`compute_features()` used online**, over the same 4-hour rolling window.
Any feature change automatically applies to both paths; the artifact's
`feature_schema_hash` must match at load time or the server refuses to load
the model.

## Split & metrics policy

- **Patient-level 70/15/15** train/validation/test — no patient appears in
  more than one split (`training/train.py::patient_level_split`).
- **Class-weighted loss** (`scale_pos_weight` / `class_weight=balanced`).
  SMOTE is intentionally not used — synthetic minority trajectories may be
  clinically implausible.
- Reported metrics: AUROC, AUPRC, precision/recall/F1 at the operating
  threshold, prevalence, sample counts — per split, per task, per artifact
  version, with `dataset_hash` and `feature_schema_hash` recorded.
- Every report carries the disclaimer: retrospective public/synthetic data
  only; not prospective clinical validation; public datasets do not
  represent the waiting-room target population.

## Reproducibility

Artifacts are directory-versioned:

```
artifacts/models/<task>-<kind>-<UTC timestamp>-<dataset_hash8>/
  model.joblib
  metadata.json      # id, kind, task, dataset, dataset_hash,
                     # feature_schema_hash, feature_order, threshold,
                     # metrics, created_at
artifacts/reports/<artifact-id>_<dataset>_<split>.{json,md}
```

Pin a version in production with `MEDIQUEUE_MODEL_VERSION`.
