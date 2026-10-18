# Offline evaluation — deterioration-lightgbm-20261018T055043Z-d2ee00c4

- Task: **deterioration**
- Dataset: **synthetic** (test split)
- Threshold: 0.17

| Metric | Value |
| --- | --- |
| AUROC | 0.8215 |
| AUPRC | 0.7064 |
| Precision | 0.4303 |
| Recall | 0.8212 |
| F1 | 0.5647 |
| Prevalence | 0.2512 |
| Samples | 1692 |

## Operating points

| Threshold | Precision | Recall | Alert rate |
| --- | --- | --- | --- |
| 0.30 | 0.748 | 0.525 | 0.176 |
| 0.50 | 0.990 | 0.480 | 0.122 |
| 0.60 | 0.990 | 0.480 | 0.122 |
| 0.75 | 0.990 | 0.480 | 0.122 |
| 0.85 | 0.990 | 0.480 | 0.122 |

## Calibration

Brier score **0.1093**, expected calibration error **0.0375**.

| Predicted bin | n | Mean predicted | Observed rate |
| --- | --- | --- | --- |
| 0.0-0.1 | 497 | 0.034 | 0.052 |
| 0.1-0.2 | 513 | 0.149 | 0.185 |
| 0.2-0.3 | 474 | 0.278 | 0.209 |
| 0.3-0.4 | 1 | 0.318 | 1.000 |
| 0.4-0.5 | 1 | 0.403 | 0.000 |
| 0.9-1.0 | 206 | 1.000 | 0.990 |

> Retrospective public/synthetic data only. Not prospective clinical validation. Public datasets do not represent the waiting-room target population. Synthetic system performance is a separate evidence category.
