# Dependency license metadata audit

**Snapshot reviewed:** `frontend/package-lock.json`  
**Scope:** npm package metadata recorded in the committed lockfile; this is not a legal opinion or a complete asset-rights review.

## Inventory

The lockfile contains 537 package entries under `packages`. Every entry has a declared license field in the inspected snapshot.

| Declared license metadata | Package entries |
|---|---:|
| MIT | 456 |
| Apache-2.0 | 19 |
| MPL-2.0 | 12 |
| ISC | 26 |
| BSD-3-Clause | 7 |
| BSD-2-Clause | 8 |
| MIT-0 | 2 |
| CC-BY-4.0 | 1 |
| CC0-1.0 | 1 |
| Unlicense | 1 |
| Python-2.0 | 1 |
| BlueOak-1.0.0 | 1 |
| 0BSD | 1 |
| MIT AND ISC | 1 |

## Python dependencies

The project uses `pyproject.toml` and `requirements.txt`. No resolved Python lockfile was included in this audit, so the exact transitive Python package versions and license metadata remain unverified.

## Follow-up

1. Generate a resolved Python dependency lock and license inventory.
2. Review dataset provenance, model artifacts, sample patient/queue data, and any externally sourced medical content separately.
3. Preserve all applicable third-party notices.
4. Regenerate this report whenever the npm lockfile changes.

**Limitations:** a declared package license field is a lead for review, not proof that all required notices are present or that the project has satisfied every license obligation.
