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
- **Raw label:** 0 before the hidden deterioration onset and 1 from onset
  through series end. The feature-matrix builder projects these onset labels
  backward by the configured prediction horizon (default 30 minutes), exactly
  once. This keeps the target horizon explicit and avoids double-extending
  positive labels.
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

### 4. VitalDB open dataset (recorded perioperative measurements)

- Website and access terms: https://physionet.org/content/vitaldb/1.0.0/ and
  https://vitaldb.net/docs/?documentId=OpenDataset%2FOverview.md
- VitalDB contains de-identified operating-room/anesthesia recordings, not
  emergency-department waiting-room observations. Treat it as a source for
  ingestion and time-series experiments, not proof that MediQueue works for ED triage.
- Track names and units vary by device. Map source tracks explicitly; do not
  infer a unit or treat arterial waveforms as cuff blood-pressure readings.
- The public data API exposes case metadata, track metadata, and per-track
  time/value data. Numeric tracks may have irregular sample times. Preserve
  source-relative timing and document any chosen time anchor.
- Review and comply with the dataset's Data Use Agreement before downloading
  or using it. Never commit downloaded records to this repository.

The offline `scripts/export_observations.py` utility accepts a **normalized
long-format CSV** and emits NDJSON payloads. It does not download or parse
VitalDB's native tracks, call the MediQueue API, or write to the database.
Use the optional `scripts/export_vitaldb.py` adapter for a single case. It maps explicitly selected numeric tracks
to the four supported vital types and leaves clinical scoring untouched. Install its optional dependency with `python -m pip install vitaldb`, then run for example:

```bash
python scripts/export_vitaldb.py --case-id 1 \\
  --start-time 2024-01-01T00:00:00Z --interval 60 \\
  --output vitaldb-case-1.ndjson
```

The required `--start-time` is a **synthetic UTC anchor** because VitalDB times are relative to case start, not the patient's real wall-clock time. Output is for offline replay/testing only; do not feed it into a live clinical queue as if these were current readings. The default tracks are `Solar8000/HR`, `Solar8000/PLETH_SPO2`, `Solar8000/NIBP_SBP`, `Solar8000/NIBP_DBP`, and `Solar8000/BT`; use the `--*-track` options to override them when a case uses different tracks. Missing samples are skipped, and BP is emitted only when both systolic and diastolic samples are present.

Before using an export in any downstream workflow, run the offline validator:

```bash
python scripts/validate_observations.py vitaldb-case-1.ndjson
```

It applies MediQueue's existing unit, timestamp, and plausibility checks without making API calls or writing to the database. It reports line numbers and validation errors, plus per-vital counts, value ranges, and timestamp coverage for valid rows; it deliberately does not print patient IDs. A non-zero exit status means the file contains invalid rows or no valid observations. This checks payload compatibility only; it does not validate the clinical usefulness of the dataset or the triage model.

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
