# Model Results Summary

Run: `20260409_192758_spa_firstfulltest`  
Track: `Spa-Francorchamps`  
Dataset: `corner_dataset.parquet`

## Dataset Context

This summary is based on the cleaned dataset for this run after removing
incident laps associated with crashes, spins, or other severe off-nominal
events.

- Rows before cleaning: `402`
- Rows after cleaning: `326`
- Laps before cleaning: `44`
- Laps after cleaning: `36`
- Removed laps: `14, 17, 26, 35, 46, 47, 48, 50`

Cleaning details are recorded in `corner_dataset_cleaning.json`.

## Model Comparison

Cleaned Spa-Francorchamps run, grouped cross-validation on `36` laps and `326`
corner samples.

| Model | Feature Set | CV RMSE (ms) | CV R^2 |
|---|---|---:|---:|
| CatBoost | `all_numeric` | **133.89 +/- 27.41** | **0.783 +/- 0.054** |
| Random Forest | `all_numeric` | `138.37 +/- 22.63` | `0.769 +/- 0.032` |
| Ridge | `all_numeric` | `154.19 +/- 19.93` | `0.711 +/- 0.038` |
| CatBoost | `heuristics` | `207.54 +/- 21.03` | `0.477 +/- 0.037` |
| Ridge | `heuristics` | `232.55 +/- 37.20` | `0.350 +/- 0.081` |

## Interpretation Notes

On the cleaned Spa-Francorchamps dataset, models trained on the full numeric
feature representation substantially outperformed heuristics-only variants.
CatBoost with `all_numeric` features achieved the best overall performance, with
a cross-validated RMSE of `133.89 +/- 27.41 ms` and an R^2 of
`0.783 +/- 0.054`, followed closely by Random Forest on the same feature set
(`138.37 +/- 22.63 ms`, `R^2 = 0.769 +/- 0.032`). Ridge regression also
benefited markedly from the richer feature representation, improving from
`232.55 +/- 37.20 ms` and `R^2 = 0.350 +/- 0.081` under the heuristics-only
configuration to `154.19 +/- 19.93 ms` and `R^2 = 0.711 +/- 0.038` with all
numeric features. CatBoost trained on heuristics alone
(`207.54 +/- 21.03 ms`, `R^2 = 0.477 +/- 0.037`) outperformed the linear
heuristics baseline but remained clearly below models trained on the broader
engineered feature set. Overall, these results suggest that feature richness
contributes the largest share of predictive improvement, while nonlinear
tabular models provide additional gains once a stronger telemetry-derived
representation is available.

## Feature Signals

Top features reported by the saved manifests include:

- `catboost_all_numeric`: `speed_max`, `speed_min`, `throttle_on_delta_m`,
  `throttle_onset_rel`, `curvature_mean`
- `rf_all_numeric`: `rpm_std`, `throttle_std`, `throttle_on_delta_m`,
  `lap_num`, `speed_min`
- `ridge_all_numeric`: `brake_start_delta_m`, `throttle_onset_rel`,
  `gear_mean`, `brake_release_rel`, `lap_distance_m`
- `catboost_heuristics`: `exit_speed_delta_kmh`, `min_speed_delta_kmh`,
  `brake_start_delta_m`, `throttle_on_delta_m`
- `ridge_heuristics`: `min_speed_delta_kmh`, `exit_speed_delta_kmh`,
  `brake_start_delta_m`, `throttle_on_delta_m`

## Caveat

The current `all_numeric` feature mode appears to include some bookkeeping-style
columns in addition to telemetry-derived predictors. Before final thesis
submission, it would be worth checking whether columns such as `lap_num` or
other run-structure identifiers should be excluded from the final feature set
for a stricter telemetry-only interpretation.

## Artifact Files

- `models/catboost_all_numeric.joblib`
- `models/catboost_all_numeric.json`
- `models/rf_all_numeric.joblib`
- `models/rf_all_numeric.json`
- `models/ridge_all_numeric.joblib`
- `models/ridge_all_numeric.json`
- `models/catboost_heuristics.joblib`
- `models/catboost_heuristics.json`
- `models/ridge_heuristics.joblib`
- `models/ridge_heuristics.json`
