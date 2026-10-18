# Model card — MediQueue deterioration model

**Status:** research/teaching prototype. Not validated for clinical use. Decision support only; clinicians confirm every action.

## Intended use
Rank ED patients by short-horizon (30 min) deterioration risk from four vitals (heart rate, SpO₂, blood pressure, temperature) over a rolling 4-hour window. Output feeds alerts and *pending* queue recommendations.

**Out of scope:** diagnosis, autonomous triage, paediatric patients, any population not represented in the training data.

## Model
- LightGBM classifier, 48 engineered features (latest/mean/std/min/max/slope/short-horizon delta/abrupt change per vital, shock index, history flags). The same feature code runs offline and online.
- Class-weighted loss (no SMOTE).
- **Isotonic calibration** fitted on the validation split (`calibrator.joblib`), applied at inference.
- **Operating threshold:** highest validation threshold that reaches ≥ 0.80 recall (sensitivity-first, since a missed deterioration is costlier than an extra alert). Recorded in `metadata.json` with its policy.
- **Abstains** (no score) with < 3 readings or < 10 min of history; inference failure marks the prior score stale.

## Data
Synthetic corpus only (patient-level 70/15/15 split, no patient leakage). A PhysioNet/CinC 2019 sepsis path exists but no sepsis model is shipped. Sepsis and deterioration labels are never mixed.

## Results (synthetic, independent corpus, test split, n = 1,692 samples)
| Metric | Value |
| --- | --- |
| AUROC | 0.822 |
| AUPRC | 0.706 |
| Recall / precision at operating threshold 0.17 | 0.821 / 0.430 |
| Brier score / ECE (isotonic-calibrated) | 0.109 / 0.038 |

On the held-out split from the training corpus the same model scores AUROC 0.802 and recall 0.718 at 0.17. Full tables: `artifacts/reports/`.

## Known limitations
- **Synthetic data flatters the model.** Scores are bimodal: obvious cases score ≈ 1.0, the rest stay below ≈ 0.3. Real data will be messier.
- **Config mismatch.** The default alert threshold (0.60) and risk bands (watch 0.30 / elevated 0.50 / high 0.75) were set independently of the model. At 0.60 recall is only ≈ 0.48 (the high-score cluster). Before any demo that claims sensitivity, set `MEDIQUEUE_BAND_WATCH` and `MEDIQUEUE_ALERT_THRESHOLD` near the model's operating threshold.
- Isotonic calibration is fitted on a small validation set; the 0.8–1.0 range is sparse and unreliable.
- No subgroup analysis (age, sex), no prospective or external validation, no drift monitoring.

## Offline evaluation report provenance

The offline evaluation command writes JSON and Markdown reports. These reports include the model version, task, dataset, selected split, threshold, metrics, operating points, calibration summary, and an evidence disclaimer.

- **Evaluation dataset fingerprint:** a SHA-256 digest of canonicalized dataset parameters and patient records, including patient IDs, observations, timestamps, positive flags, and labels. Patient and observation ordering is normalized, so changing iteration order alone does not change the digest.
- **Evaluation seed:** records the seed supplied to the evaluator. For generated synthetic data, use the same seed and patient count to recreate the same generated corpus.
- **Patient and sample counts:** describe the selected evaluation data after feature-matrix construction and split filtering. They are useful for checking report scope, but do not establish dataset representativeness.
- **Split:** `test`, `validation`, `train`, or `all`. Prefer the held-out test split for final offline reporting; validation data is used during model development and threshold/calibration selection.
- **Interpretation:** matching fingerprints help identify matching source data and generation parameters. They do not prove that the evaluation is unbiased, that labels are correct, or that the model generalizes clinically. Synthetic and public-data metrics are not prospective clinical validation.

## Reproduce
```
python scripts/train_model.py --n-patients 400 --target-recall 0.80
python scripts/evaluate_model.py artifacts/models/<version>
```
