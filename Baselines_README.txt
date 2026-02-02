GT7 Race Engineer – Baseline Modeling Notes

This document explains how to run the baseline machine learning evaluation,
how to interpret its outputs, and how to correctly reason about the results
given the current dataset size and experimental setup.


3. Running the Baseline Models

Baseline models are executed using the baselines.py module, which evaluates
corner-level telemetry datasets produced by the research export pipeline.

Supported dataset formats:
- corner_dataset.csv
- corner_dataset.parquet

Each dataset row represents a single corner instance from a single lap.
The target variable is corner-level time loss (loss_ms) relative to the
reference lap.

Example commands:

CSV input:
    python -m src.research.baselines data/runs/<RUN_ID>/corner_dataset.csv \
        --out data/runs/<RUN_ID>/baseline_report.json

Parquet input:
    python -m src.research.baselines data/runs/<RUN_ID>/corner_dataset.parquet \
        --out data/runs/<RUN_ID>/baseline_report.json

The script performs grouped cross-validation (GroupKFold) to prevent data
leakage between corners from the same lap or run.


4. Interpreting Baseline Results

For each run, the script evaluates four configurations:

1. Ridge Regression + heuristic features
2. Ridge Regression + all numeric features
3. Random Forest + heuristic features
4. Random Forest + all numeric features

Metrics reported:
- RMSE (root mean squared error, in milliseconds)
- R² (coefficient of determination)
- Mean and standard deviation across CV folds

Interpretation guidance:

- RMSE reflects how accurately the model predicts localized corner time loss.
  Lower RMSE indicates better explanatory power.

- R² reflects how much variance in corner time loss is explained by the model.
  Values near 0 indicate little explanatory value; higher values indicate
  stronger relationships.

Primary comparison of interest:

    Heuristic-only features  vs.  All numeric features

If models using all numeric features materially outperform heuristic-only
models, this provides evidence that the engineered telemetry features capture
additional explanatory structure beyond traditional racing heuristics.

Permutation importance is also reported for each model, indicating which
features most strongly affect prediction error when perturbed. These rankings
are used for interpretability, not as causal claims.



5. Dataset Size, Validity, and Intended Use

Early baseline results should be interpreted as pipeline validation rather
than definitive performance claims.

Important considerations:

- Small numbers of laps limit the number of cross-validation splits and increase
  variance in reported metrics.

- Results obtained from only a few laps primarily confirm that:
    • Dataset construction is correct
    • Feature columns behave sensibly
    • Models train and evaluate without leakage

- Meaningful statistical conclusions require additional laps, varied driving
  conditions, and multiple runs.

At this stage, baseline modeling serves three purposes:
1. Verifying correctness and stability of the dataset pipeline
2. Establishing heuristic-only performance as a reference baseline
3. Identifying promising features for later analysis and visualization

As additional data is collected, the same baseline framework can be reused
without modification to assess generalization, robustness, and feature
consistency across tracks and sessions.


