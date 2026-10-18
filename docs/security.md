# Security & safety notes

MediQueue handles health-adjacent data and influences (but does not make)
clinical prioritization. This document covers the prototype's security
posture and the safety controls around the AI pathway.

## Authentication

- Username/password login at `POST /api/auth/login`.
- Passwords stored as **PBKDF2-HMAC-SHA256** (salted, high iteration count).
- Sessions are **stateless HMAC-signed bearer tokens** with an expiry
  (`MEDIQUEUE_TOKEN_TTL_SECONDS`, default 8 h). Each token carries a `jti`; `POST /api/auth/logout` adds it to a server-side denylist (`revoked_tokens`) until it would expire. Tokens are sent in the
  `Authorization: Bearer` header (WebSocket: `?token=` query param or
  `x-mq-token` header).
- **Deployment requirement:** set `MEDIQUEUE_SECRET_KEY` to a random
  32+ byte secret from a vault. The built-in dev default must never be used
  outside local development.

## Authorization (RBAC)

| Capability | clinician | administrator | auditor |
| --- | :-: | :-: | :-: |
| View queue/patients/alerts | ✓ | ✓ | ✓ (read-only) |
| Confirm / reject / override recommendations | ✓ | ✓ | ✗ (403) |
| Start/stop replay simulator | ✗ | ✓ | ✗ |
| Read audit log | ✓ | ✓ | ✓ |

Enforced server-side via FastAPI dependencies (`ClinicianUser`,
`ReplayOperator`, `current_user`); the UI hides buttons the role cannot use,
but the API is the authority.

## Audit

- All clinician decisions (confirm/reject/override) and all pipeline
  lifecycle events are written to `audit_events`.
- **Append-only:** SQLite installs `BEFORE UPDATE`/`BEFORE DELETE` triggers
  that RAISE; on PostgreSQL/Db2 the equivalent is a DBA-managed rule or
  privilege revocation (see `docs/ibm-z-deployment.md`).
- **Same-transaction guarantee:** risk-scoring actions persist their audit
  row in the same DB transaction as the action. If the audit write fails,
  the entire action rolls back and the API returns HTTP 500
  (`processing_failed`). There is no path where a clinical-relevant state
  change exists without an audit record.

## Input validation

- All request bodies validated by Pydantic models (`extra="forbid"`).
- Vital ranges enforced (`validation.py`): HR 20–300 bpm, SpO₂ 50–100 %,
  SBP 40–300 mmHg, Temp 25–45 °C; ambiguous/unknown units rejected (422
  with a stable error code, never silently coerced).
- Future device timestamps (> 5 min ahead) rejected.
- Idempotency keys deduplicate retries (safe at-least-once ingestion).

## Transport

- Prototype serves HTTP on localhost. **Production must terminate TLS** at
  a reverse proxy or API gateway; bearer tokens must never travel
  plaintext. See `docs/ibm-z-deployment.md`.

## AI-specific safety controls

1. **Human in the loop.** The model never changes triage category itself.
   It produces a pending recommendation; a clinician must confirm.
   Reject/override require a rationale.
2. **Bounded automation.** Confirmed actions move at most one ESI step.
   Larger moves require an explicit clinician override (audited).
3. **Abstention.** Insufficient history → no score; never shown as "safe".
4. **Staleness.** Inference failure → prior score retained but flagged
   stale; the dashboard surfaces the STALE badge prominently.
5. **No LLM in the clinical path.** Explanations are deterministic
   structured templates with evidence rows; no generative text is used for
   anything a clinician sees as rationale.
6. **Explainability.** Every alert carries the contributing readings,
   trend statistics, model version, and missing-vital flags.
7. **Sepsis ≠ deterioration.** The two label spaces are never blended;
   evaluation reports state the evidence category (synthetic vs public
   retrospective) and disclaim prospective validation.

## Known limitations (prototype)

- Login throttling is in-memory per process (IP + username); use a gateway
  or shared store when running multiple replicas.
- SQLite default is for the prototype only; use PostgreSQL with least-
  privilege roles in deployment.
- No PHI should be loaded for development — use the synthetic corpus or
  properly de-identified public datasets under their licenses.

## Reporting security issues

Open a GitHub issue with the `security` label, or contact the maintainers
privately for undisclosed vulnerabilities. Do not include real patient data
in reports.
