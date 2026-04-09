# Research Tab - Model Training

This document explains the new model training tools available in the
`Research/Config` tab of the GT7 Race Engineer app.

The training UI is built for the current research workflow:

- collect telemetry into a run folder
- export or rebuild a corner-level dataset
- train an offline regression model from that dataset
- save the trained model and its metadata into the run folder

The system is designed for thesis and research use, not for real-time vehicle
control.

## New Addition

The `Research/Config` tab now includes a `Model Training` section with:

- current-run awareness
- run-folder or dataset-file selection
- model selection
- feature-mode selection
- seed selection
- grouped cross-validation split count
- permutation-importance repeat count
- optional dataset rebuild before training
- optional overwrite of existing model artifacts
- background training execution
- live status output in the UI

## Supported Models

The UI currently exposes these models:

- `CatBoost`
- `Random Forest`
- `Ridge`

These map to the same backend training pipeline used by the CLI and research
modules.

## Supported Feature Modes

- `All numeric features`
  Uses all numeric and boolean dataset columns except excluded identifiers and
  target columns.

- `Heuristics only`
  Uses the compact heuristic feature set:
  - `brake_start_delta_m`
  - `throttle_on_delta_m`
  - `min_speed_delta_kmh`
  - `exit_speed_delta_kmh`

## Where the Training UI Lives

Open the app, then go to:

- `Research/Config` tab
- `Model Training` box

## What the Controls Do

### Training source

This is the path the training job will use.

You can point it at:

- a run folder such as `data/runs/runFolder`
- a dataset file such as `corner_dataset.csv`
- a dataset file such as `corner_dataset.parquet`

If the field is left blank, the UI will try to use the current run.

### Use current run

Copies the active run folder into the training source field.

### Browse run

Lets you pick an existing run directory.

### Browse dataset

Lets you pick a `corner_dataset.csv` or `corner_dataset.parquet` file directly.

### Model

Chooses which estimator to train.

### Feature mode

Chooses whether to train on all numeric features or the smaller heuristics-only
subset.

### Seed

Controls the random seed passed into the training pipeline.

### CV splits

Controls grouped cross-validation split count. The pipeline uses grouped CV to
reduce leakage across related samples.

### Permutation repeats

Controls how many times permutation importance is repeated during evaluation.

Higher values:

- are slower
- usually produce more stable feature-importance estimates

### Rebuild/export the corner dataset first when training from a run folder

If checked, and the source is a run directory, the app will rebuild the corner
dataset from that run before training.

This is the safest option when:

- you have added new laps
- the dataset might be stale
- schema-related metadata has changed

### Overwrite existing model artifacts with the same name

If checked, the app may replace an existing artifact such as:

- `models/catboost_all_numeric.joblib`
- `models/catboost_all_numeric.json`

If unchecked, an existing artifact with the same model and feature-mode name
will cause the training job to fail instead of silently replacing it.

### Train model

Starts the training job in a background Qt worker thread so the app stays
responsive.

### Status panel

Shows:

- dataset rebuild progress
- training progress
- summary metrics
- saved artifact locations
- failures and stack traces if something goes wrong

## Output Files

When training from a run folder, the app writes model artifacts into:

```text
<run_dir>/models/
```

Typical output:

```text
<run_dir>/models/catboost_all_numeric.joblib
<run_dir>/models/catboost_all_numeric.json
```

The run-level `manifest.json` is also updated with a `trained_models` entry.

If training from a dataset file outside a run folder, the app writes to:

```text
<dataset_parent>/models/
```

## What the Saved Files Mean

### `.joblib`

This is the trained sklearn-compatible pipeline bundle used for later loading
and prediction.

### `.json`

This is the training manifest. It stores metadata such as:

- model name
- feature mode
- preprocessing mode
- dataset path
- schema hash
- schema version
- seed
- CV metrics
- top features

## Full Tutorial

This walkthrough covers the full workflow from telemetry collection to a saved
trained model.

### 1. Launch the app

Start the GT7 Race Engineer app normally.

Make sure:

- the app can receive GT7 telemetry
- the `Research/Config` tab is enabled for research export

### 2. Configure research export settings

In the `Research/Config` tab:

- confirm `Enable research export` is checked
- confirm the output folder is correct, usually `data/runs`
- choose your distance-bin count and exported features
- click `Apply settings`

These settings affect how run artifacts and dataset-compatible research outputs
are produced.

### 3. Start or continue a run

To create a fresh run:

- enter run metadata such as track and car
- click `Start new run` or `Start new run with metadata`

To keep using the active run:

- continue collecting laps normally

The app creates a run folder under `data/runs/` once research export begins.

### 4. Drive and collect useful laps

Run several laps in GT7 so the system can export enough corner examples for the
dataset.

Best practice:

- include multiple valid laps
- avoid training from extremely tiny datasets
- use consistent car, track, and conditions within a run when possible

### 5. Export the dataset

In the `Research/Config` tab:

- click `Export dataset`

This creates or refreshes:

- `corner_dataset.csv`
- `corner_dataset.parquet`
- `corner_dataset_build.json`

If you skip this step, the training UI can still rebuild the dataset for you
when training from a run folder, as long as the rebuild checkbox is enabled.

### 6. Open the Model Training box

Still in `Research/Config`, scroll to the `Model Training` section.

You should see:

- a `Current run` label
- the training source field
- model controls
- training status output

### 7. Choose the training source

Option A: train from the active run

- click `Use current run`

Option B: train from an older run

- click `Browse run`
- pick the desired run folder

Option C: train from a dataset file directly

- click `Browse dataset`
- select a `corner_dataset.csv` or `corner_dataset.parquet`

### 8. Choose the model

Pick one:

- `CatBoost`
- `Random Forest`
- `Ridge`

Recommended starting point:

- `CatBoost` with `All numeric features`

### 9. Choose the feature mode

Recommended for strongest baseline:

- `All numeric features`

Recommended for a simpler interpretability comparison:

- `Heuristics only`

### 10. Set training parameters

Good default starting values:

- `Seed`: `7`
- `CV splits`: `5`
- `Permutation repeats`: `20`

If the dataset is small, you may need fewer CV splits.

### 11. Decide whether to rebuild the dataset first

Leave this checked if:

- you are training from a run folder
- you want to ensure the dataset matches current run artifacts

You can uncheck it if:

- you already exported the dataset
- you want to avoid the extra rebuild step

### 12. Decide whether to overwrite old artifacts

Check `Overwrite existing model artifacts...` only if you intentionally want to
replace an existing saved model with the same name.

### 13. Start training

Click `Train model`.

The app will:

1. optionally rebuild the dataset
2. load the resulting dataset
3. run grouped cross-validation
4. fit the final model on the full dataset
5. save the model artifact and manifest
6. update the run manifest

Because this runs in a background worker thread, the main app window should stay
responsive during training.

### 14. Read the status output

When training succeeds, the status panel will report:

- source path
- dataset path
- chosen model
- chosen feature mode
- CV RMSE
- CV R^2
- saved artifact path
- saved manifest path
- top features if available

Example summary:

```text
Source: data/runs/20260409_123456_monza_sf
Dataset: data/runs/20260409_123456_monza_sf/corner_dataset.parquet
Model: catboost
Feature set: all_numeric
CV RMSE: 18.42 +/- 2.91 ms
CV R^2: 0.673 +/- 0.052
Model artifact: data/runs/20260409_123456_monza_sf/models/catboost_all_numeric.joblib
Manifest: data/runs/20260409_123456_monza_sf/models/catboost_all_numeric.json
```

### 15. Inspect the saved artifacts

After training, open the run folder and look inside:

```text
<run_dir>/models/
```

You should find the new model files there.

You can also inspect:

- `<run_dir>/manifest.json`

to see the appended `trained_models` history.

## Recommended First-Time Workflow

If this is your first time using the feature, use this exact sequence:

1. Start the app.
2. Enable research export.
3. Start a new run with track and car metadata filled in.
4. Drive several clean laps.
5. Click `Export dataset`.
6. In `Model Training`, click `Use current run`.
7. Choose `CatBoost`.
8. Choose `All numeric features`.
9. Leave `Rebuild/export the corner dataset first...` checked.
10. Leave overwrite unchecked.
11. Click `Train model`.
12. Read the metrics and inspect the saved files under `models/`.

## Tutorial: Training From an Older Run

You do not need an active live telemetry session to train from older data.

Steps:

1. Open the app.
2. Go to `Research/Config`.
3. In `Model Training`, click `Browse run`.
4. Select an older run folder in `data/runs/`.
5. Leave dataset rebuild checked if you want a fresh dataset.
6. Choose model and feature mode.
7. Click `Train model`.

This is useful for:

- re-running experiments
- comparing models on the same run
- thesis iteration and report generation

## Tutorial: Training Directly From a Dataset File

You can bypass the run folder and point training directly at a dataset file.

Steps:

1. Open the app.
2. Go to `Research/Config`.
3. In `Model Training`, click `Browse dataset`.
4. Choose `corner_dataset.csv` or `corner_dataset.parquet`.
5. Choose model and feature mode.
6. Optionally set overwrite.
7. Click `Train model`.

When doing this, the app will save artifacts beside that dataset under:

```text
<dataset_parent>/models/
```

## Common Failure Cases

### Training source not found

Cause:

- the selected path no longer exists

Fix:

- re-select the run folder or dataset file

### Dataset too small

Cause:

- not enough corner rows after filtering
- too few laps or groups for grouped CV

Fix:

- collect more laps
- export a larger run
- reduce the number of CV splits

### Missing heuristic features

Cause:

- you selected `Heuristics only`, but the dataset does not include all required
  heuristic columns

Fix:

- switch to `All numeric features`
- or rebuild the dataset if those fields should exist

### Existing artifact already exists

Cause:

- the same model/feature-mode output already exists and overwrite is off

Fix:

- enable overwrite
- or remove/rename the old artifact

### CatBoost unavailable

Cause:

- `catboost` is not installed in the current environment

Fix:

- install dependencies from `requirements.txt`
- or choose `Random Forest` or `Ridge`

## Interpretation Notes

These models predict corner-level `loss_ms` from engineered telemetry-derived
features.

Keep in mind:

- metrics are only meaningful relative to the dataset used
- small datasets can produce unstable CV estimates
- `Ridge` is useful as a linear baseline
- `Random Forest` is useful as a nonlinear baseline
- `CatBoost` is usually the strongest practical tabular baseline here

## Best Practices

- train on runs with clean, consistent data
- keep track and car metadata accurate
- prefer Parquet-backed datasets when available
- compare multiple model/feature-mode combinations
- save experimental notes in the run metadata
- do not overwrite artifacts unless you mean to replace them

## Related Files

Relevant implementation files:

- `src/ui/settings_tab.py`
- `src/ui/main_window.py`
- `src/app.py`
- `src/research/train_pipeline.py`
- `src/research/model_factory.py`
- `src/research/model_artifacts.py`
- `src/research/inference.py`
- `scripts/train_model.py`

## Short Version

If you just want the fastest path:

1. Export a run dataset.
2. Open `Research/Config`.
3. In `Model Training`, choose the current run.
4. Pick `CatBoost` and `All numeric features`.
5. Click `Train model`.
6. Read the status output.
7. Find the saved model under `<run_dir>/models/`.
