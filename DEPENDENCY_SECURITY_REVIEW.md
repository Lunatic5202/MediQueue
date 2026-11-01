# MediQueue frontend dependency security review

**Review date:** 2026-11-02  
**Reviewed lockfile:** `frontend/package-lock.json`  
**Runtime:** Node.js 22 in GitHub Actions  
**Scope:** npm frontend dependency tree only. Python backend dependencies are not included.

## Baseline

The original locked frontend dependency tree reported:

| Severity | Count |
|---|---:|
| Critical | 2 |
| High | 0 |
| Moderate | 8 |
| Low | 0 |
| **Total** | **10** |

All affected package entries in this report were development/build/test tooling (`dev: true` in the lockfile). No production dependency entry was identified in the npm audit output.

## Remediation validated on a branch

| Package | Before | Candidate version | Reason |
|---|---:|---:|---|
| `vite` | 6.4.4 | 6.4.5 | Fixes GHSA-8g5g-mxqh-grgj |
| `vitest` | 3.2.7 | 5.0.5 | Moves past the affected Vitest mocker and tinypool ranges |

The candidate lockfile was generated using npm, then installed from scratch with `npm ci`.

### Validation

- Frontend tests: passed (11 tests).
- Production frontend build: passed.
- ESLint: passed.
- Post-update npm audit: 0 critical, 0 high, 6 moderate.

The Vitest 5 migration requires Vite 6.4 or newer and Node 22.12 or newer. The CI runner uses Node 22, and the candidate uses Vite 6.4.5.

## Remaining moderate advisory: minimatch

The six remaining npm audit entries resolve through this single locked package:

- `minimatch@3.1.5`
- Lockfile path: `node_modules/minimatch`
- It is a development dependency.

The GitHub Advisory Database currently records GHSA-g3hv-75wg-m249 as affecting versions below 11.0.1. However, the upstream maintainer's advisory describes the vulnerable implementation in `minimatch@10.2.6`, with 11.0.1 as the patched release. An open advisory-database issue specifically asks whether the broader range incorrectly includes 3.1.5, whose source does not contain the described preprocessing implementation.

References:

- [Upstream minimatch advisory](https://github.com/isaacs/minimatch/security/advisories/GHSA-g3hv-75wg-m249)
- [GitHub Advisory Database record](https://github.com/advisories/GHSA-g3hv-75wg-m249)
- [Open clarification issue about the affected range](https://github.com/github/advisory-database/issues/10811)

I have **not** forced a minimatch major upgrade or downgraded ESLint / eslint-plugin-react just to make the scanner count disappear. The affected range should be clarified, and the ESLint dependency chain should be reviewed against compatible upstream releases before changing it.

## Release decision

The Vite and Vitest updates are validated candidates and are isolated on the `security/mediqueue-toolchain-remediation` branch. They should be merged after review.

The remaining moderate findings are documented as unresolved scanner findings pending authoritative clarification and a compatible ESLint dependency update. This review is not a claim that the frontend has zero dependency risk.

## Reproduction

From `frontend/`:

```bash
npm ci
npm audit
npm test
npm run build
npm run lint
```
