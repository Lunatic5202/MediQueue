# MediQueue — Architecture

## Overview

MediQueue is a single-service FastAPI application with a React dashboard.
The ingestion → scoring → alerting → recommendation → audit path runs in
**one database transaction** per observation, so a committed observation
always has a consistent risk assessment, alert state, and audit record — or
none of them.

```
                 ┌──────────────────────────────────────────────────────┐
 HL7-style POST  │  FastAPI (backend/mediqueue)                         │
 /api/observations ──▶ Pipeline (single transaction)                   │
                 │    1 validation        modules/validation.py         │
                 │    2 dedup             modules/validation.py         │
                 │    3 history window    modules/history.py            │
                 │    4 features          modules/features.py           │
                 │    5 inference         modules/inference.py          │
                 │    6 banding           modules/risk.py               │
                 │    7 alert rules       modules/risk.py               │
                 │    8 recommendations   modules/recommendation.py     │
                 │    9 audit write       modules/audit.py              │
                 │         │                                           │
                 │         ├── risk_assessments, alerts, recommendations│
                 │         ├── events (durable realtime feed)           │
                 │         └── audit_events (append-only)               │
                 │                                                      │
                 │  WebSocket /ws  ◀── realtime.py hub                  │
                 │  /api/events    ◀── durable polling fallback         │
                 └───────────────┬──────────────────────────────────────┘
                                 │ HTTP/WS
                 ┌───────────────▼──────────────────────────────────────┐
                 │  React dashboard (frontend/dist, served by FastAPI)  │
                 │  Queue · Patient detail · Alerts · Audit · Replay    │
                 └──────────────────────────────────────────────────────┘
```

## Modules

| Module | Responsibility |
| --- | --- |
| `validation.py` | Unit/range checks (HR 20–300 bpm, SpO₂ 50–100 %, SBP 40–300 mmHg, Temp 25–45 °C), unit normalization (e.g. `%` / `percent`), future-timestamp rejection, idempotency keys |
| `history.py` | 4-hour rolling window per patient, bounded reads (`max_history_per_patient`), device-timestamp ordering (late events insert in order) |
| `features.py` | Per-vital latest/mean/std/min/max/slope/short-horizon-delta/abrupt-change + shock index + missingness. **The same code runs offline in `training/datasets.py`** — training/serving parity by construction |
| `inference.py` | Versioned artifact loading (joblib + metadata.json), feature-schema-hash verification, LightGBM/logreg scoring, latency measurement, abstain/stale semantics |
| `risk.py` | Score → band (watch/elevated/high thresholds), absolute-threshold alerts, adverse-trend rules (≥3 readings, ≥20 min span, abrupt-change shortcut), dedup + cooldown + material-worsening bypass, structured explanations |
| `recommendation.py` | Alert → pending ESI recommendation (bounded one step), confirm/reject/override with mandatory rationale for reject/override, audit in-transaction |
| `audit.py` | Append-only `audit_events` writer + durable `events` writer for the realtime feed |
| `simulator.py` | Synthetic patient timelines (stable / sepsis-like / respiratory-decline / mixed) injected through the same POST /api/observations path |
| `realtime.py` | In-process WebSocket fan-out; events also persisted so clients can poll `/api/events?since_id=` |
| `pipeline.py` | Orchestrates steps 1–9; owns the transaction boundary and stale-score marking |

## Data model (core tables)

- `patients` — id, ESI triage category (1–5), registered_at
- `observations` — normalized vitals with `device_ts`, `ingest_ts`, `source_id`, `idempotency_key` (unique)
- `risk_assessments` — score [0,1], band, `model_version_id`, latency_ms, stale flag, low_confidence, features snapshot (JSON)
- `alerts` — trigger_type (`absolute_threshold` | `adverse_trend`), triggering_vital, severity, status (`open` | `suppressed` | `resolved`), `dedup_key`, cooldown_until, explanation (JSON)
- `recommendations` — current/proposed ESI, direction, status (`pending` | `confirmed` | `rejected` | `overridden` | `superseded`), rationale, decided_by/at, applied_priority
- `events` — durable realtime feed (topic, patient_id, payload); powers WebSocket broadcast + polling fallback
- `audit_events` — append-only (SQLite triggers enforce UPDATE/DELETE rejection; see deployment doc for PostgreSQL rules)

## Key decisions

1. **Single transaction per observation.** Consistency over raw throughput.
   A 500 on audit failure means nothing was half-committed.
2. **Abstention over false reassurance.** <3 readings or <10 min span →
   score is `null` with reason `insufficient_history`. The UI never renders
   "safe" for an abstained score.
3. **Stale, not silent.** Inference failure retains the prior score but
   marks it stale; the dashboard shows a STALE badge.
4. **Structured explanations only.** No LLM anywhere in the clinical
   pathway. Explanations are deterministic templates with evidence rows.
5. **Clinician in the loop.** Recommendations are pending until confirmed;
   reject/override require rationale; max one ESI step per confirm
   (override may exceed, by explicit clinician choice).
6. **Patient-level splits.** 70/15/15 by patient id, never by row —
   prevents leakage across a patient's timeline.
7. **Task separation.** Sepsis (PhysioNet 2019 label) and general
   deterioration (synthetic proxy) are separate models, artifacts, and
   reports. Labels are never blended.

## Realtime path

1. Pipeline commits → events rows inserted in the same transaction.
2. After commit, the API broadcasts the events over WebSocket.
3. Clients track `since_id`; on WS loss they poll `/api/events?since_id=`.
4. Server also broadcasts queue updates on clinician decisions.

## Failure modes

| Failure | Behavior |
| --- | --- |
| Model artifact missing/corrupt | App starts without a model; `/api/health` shows `model_loaded: false`; observations 503 with `model_unavailable` |
| Inference exception | No new assessment; prior score marked stale; observation still accepted (200) with `stale: true` |
| Audit write failure | Whole transaction rolls back; HTTP 500 `processing_failed` |
| DB down | Ingest 500; dashboard shows connection error; WS retries with backoff, polling continues attempting |
| WS unreachable | Dashboard falls back to 3-second polling of `/api/events` |

## Performance

`scripts/benchmark.py` measures client-observed latency. On a laptop-class
machine with SQLite, p95 ingest→persisted-score is ~3 ms server-side
stage time (see `artifacts/reports/`). PostgreSQL raises write concurrency
headroom; the pipeline is I/O-bound on the history window read.

## Why not microservices?

For this prototype a modular monolith keeps the transaction boundary
trivially correct. Module seams (`pipeline.py` orchestration, pure
`modules/*`) allow extracting services later without redesign.
