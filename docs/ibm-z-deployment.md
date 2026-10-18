# Deploying MediQueue on IBM Z (Linux on Z / s390x)

MediQueue is pure Python + LightGBM — no architecture-specific code. It runs
unchanged on Linux on IBM Z (IBM LinuxONE / z16 / z17) under s390x.

## Supported environments

- RHEL 9.x or Ubuntu 22.04/24.04 for s390x
- Python 3.11+ (system python3 or a venv built with `uv`/`pip`)
- Node.js 20+ (only needed to rebuild the dashboard; `frontend/dist` is
  committed-ready and can be copied in without Node)
- SQLite (prototype) or PostgreSQL 15+ (production posture)

## Install

```bash
# s390x wheels exist for numpy/pandas/scikit-learn/lightgbm on PyPI;
# if your network is air-gapped, mirror the wheels internally first.
python3 -m venv /opt/mediqueue/venv
/opt/mediqueue/venv/bin/pip install -r requirements.txt

# Model artifacts: copy the trained artifacts/ tree, or retrain on Z
# (LightGBM trains fine on s390x; same seeds → same splits).
/opt/mediqueue/venv/bin/python scripts/train_model.py --dataset synthetic

# Dashboard: build on any arch (output is arch-independent JS) or
# copy a pre-built frontend/dist.
cd frontend && npm ci && npm run build && cd ..
```

## systemd unit

```ini
# /etc/systemd/system/mediqueue.service
[Unit]
Description=MediQueue API
After=network.target postgresql.service

[Service]
Type=simple
User=mediqueue
Group=mediqueue
WorkingDirectory=/opt/mediqueue
Environment=MEDIQUEUE_DATABASE_URL=postgresql+psycopg://mediqueue:…@localhost/mediqueue
Environment=MEDIQUEUE_SECRET_KEY=<random 32+ bytes, from vault>
Environment=MEDIQUEUE_MODEL_VERSION=deterioration-lightgbm-<pin-a-version>
Environment=MEDIQUEUE_ARTIFACTS_DIR=/opt/mediqueue/artifacts/models
ExecStart=/opt/mediqueue/venv/bin/python -m uvicorn mediqueue.app:app \
  --app-dir backend --host 127.0.0.1 --port 8000 --workers 4
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/mediqueue/artifacts /var/lib/mediqueue
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Terminate TLS at a front proxy (nginx/HAproxy) or use uvicorn behind
z/OS Connect / IBM Data Power as site standards dictate. Never expose the
uvicorn port directly.

## PostgreSQL notes (production posture)

- Create a dedicated database and role; grant only DML on the schema.
- Append-only audit: rely on a trigger-managed rule or a separate
  append-only tablespace; the app's SQLite triggers do not apply.
  Example (DBA-managed):

  ```sql
  CREATE RULE audit_events_no_update AS ON UPDATE TO audit_events
    DO INSTEAD NOTHING;
  CREATE RULE audit_events_no_delete AS ON DELETE TO audit_events
    DO INSTEAD NOTHING;
  ```

  (Or use `REVOKE UPDATE, DELETE ON audit_events FROM app_role;`.)

- Set `MEDIQUEUE_DATABASE_URL=postgresql+psycopg://…`.
- Run `init_db` once (the app does it at startup; idempotent).

## Performance tips on Z

- s390x has strong single-thread integer performance; LightGBM inference
  is microseconds — the pipeline is DB-bound. Prefer PostgreSQL for
  concurrent writers.
- Pin `MEDIQUEUE_MODEL_VERSION` so all app workers load the identical
  artifact.
- If using CPU-count-based worker pools, size uvicorn workers to the
  number of available IFLs (cpus allowed to the LPAR/VM).

## Air-gapped checklist

1. Mirror PyPI wheels (fastapi, uvicorn, sqlalchemy, numpy, pandas,
   scikit-learn, lightgbm, joblib, httpx, pydantic) to your internal index.
2. Copy `frontend/node_modules` from a build server, or ship `dist/` only.
3. Copy trained `artifacts/models/<version>/` + `artifacts/reports/`.
4. Provide datasets separately (not redistributed here) if retraining.
5. Verify `/api/health` returns `model_loaded: true` and the pinned
   `model_version_id` on the Model & Health page.

## Verification

```bash
curl -s localhost:8000/api/health
# {"status":"ok","version":"0.1.0","model_loaded":true,"database":"postgresql",…}

.venv/bin/python -m pytest backend/tests -q   # 43 tests
.venv/bin/python scripts/benchmark.py --patients 20 --minutes 5
```
