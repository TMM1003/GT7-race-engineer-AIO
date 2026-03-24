# src/research/baselines.py
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from catboost import CatBoostRegressor
except Exception:
    CatBoostRegressor = None


# Columns that should NEVER be used as model inputs (IDs, labels, target).
NON_FEATURE_COLS = {
    "loss_ms",
    "run_id",
    "track_name",
    "corner_uid",
    # Non-numeric categorical; keep out unless one-hot encoded later.
    "corner_direction",
}

# Heuristics-only baseline feature set (these should exist in your dataset).
HEURISTIC_FEATURES = [
    "brake_start_delta_m",
    "throttle_on_delta_m",
    "min_speed_delta_kmh",
    "exit_speed_delta_kmh",
]

# Grouping preference for CV (prevents leakage across the same lap or run).
GROUP_PRIORITY = ["lap_num", "run_id"]  # use lap_num if present, else run_id
FEATURE_MODES = ("heuristics", "all_numeric")

PREPROCESS_SCALED = "scaled_numeric"
PREPROCESS_IMPUTED = "imputed_numeric"
PREPROCESS_NATIVE_MISSING = "native_missing"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    preprocess: str
    make_estimator: Callable[[int], object]
    available: bool = True
    unavailable_reason: Optional[str] = None


@dataclass
class ModelResult:
    model_name: str
    feature_set: str
    n_rows: int
    n_features: int
    cv_splits: int
    rmse_mean: float
    rmse_std: float
    r2_mean: float
    r2_std: float
    top_features: List[Tuple[str, float]]


def _build_model_specs() -> Dict[str, ModelSpec]:
    specs: Dict[str, ModelSpec] = {
        "ridge": ModelSpec(
            name="ridge",
            preprocess=PREPROCESS_SCALED,
            make_estimator=lambda seed: Ridge(alpha=1.0, random_state=seed),
        ),
        "rf": ModelSpec(
            name="rf",
            preprocess=PREPROCESS_IMPUTED,
            make_estimator=lambda seed: RandomForestRegressor(
                n_estimators=400,
                random_state=seed,
                n_jobs=1,
                max_depth=None,
                min_samples_leaf=2,
            ),
        ),
    }

    if CatBoostRegressor is None:
        specs["catboost"] = ModelSpec(
            name="catboost",
            preprocess=PREPROCESS_NATIVE_MISSING,
            make_estimator=lambda seed: None,
            available=False,
            unavailable_reason=(
                "catboost is not installed. Install dependencies from "
                "requirements.txt to enable this model."
            ),
        )
    else:
        specs["catboost"] = ModelSpec(
            name="catboost",
            preprocess=PREPROCESS_NATIVE_MISSING,
            make_estimator=lambda seed: CatBoostRegressor(
                loss_function="RMSE",
                random_seed=seed,
                iterations=500,
                learning_rate=0.05,
                depth=6,
                l2_leaf_reg=5.0,
                subsample=0.9,
                verbose=False,
                allow_writing_files=False,
                thread_count=1,
            ),
        )

    return specs


def _read_dataset(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported dataset format: {path}")


def _choose_group_col(df: pd.DataFrame) -> Optional[str]:
    for col in GROUP_PRIORITY:
        if col in df.columns:
            return col
    return None


def _select_features(
    df: pd.DataFrame, mode: str
) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    if "loss_ms" not in df.columns:
        raise ValueError("Dataset must contain target column 'loss_ms'.")

    y = df["loss_ms"].astype(float)

    if mode == "heuristics":
        missing = [c for c in HEURISTIC_FEATURES if c not in df.columns]
        if missing:
            raise ValueError(
                f"Heuristic features missing from dataset: {missing}"
            )
        X = df[HEURISTIC_FEATURES].copy()
        feature_names = HEURISTIC_FEATURES.copy()

    elif mode == "all_numeric":
        # Use all numeric and boolean columns except NON_FEATURE_COLS and
        # obvious identifiers.
        numeric_cols = df.select_dtypes(
            include=["number", "bool"]
        ).columns.tolist()
        feature_names = [c for c in numeric_cols if c not in NON_FEATURE_COLS]
        if not feature_names:
            raise ValueError(
                "No numeric feature columns found after exclusions."
            )
        X = df[feature_names].copy()

    else:
        raise ValueError(
            f"mode must be one of: {', '.join(FEATURE_MODES)}"
        )

    X = X.apply(pd.to_numeric, errors="coerce")

    return X, y, feature_names


def _build_preprocess_pipeline(
    feature_names: List[str], preprocess: str
) -> ColumnTransformer:
    if preprocess == PREPROCESS_SCALED:
        numeric_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
    elif preprocess == PREPROCESS_IMPUTED:
        numeric_transformer = Pipeline(
            steps=[("imputer", SimpleImputer(strategy="median"))]
        )
    elif preprocess == PREPROCESS_NATIVE_MISSING:
        numeric_transformer = "passthrough"
    else:
        raise ValueError(f"Unknown preprocess mode: {preprocess}")

    return ColumnTransformer(
        transformers=[("num", numeric_transformer, feature_names)],
        remainder="drop",
        sparse_threshold=0.0,
    )


def _resolve_model_specs(
    selected_models: Optional[Sequence[str]],
) -> Tuple[List[ModelSpec], List[Tuple[str, str]]]:
    specs = _build_model_specs()
    requested = [
        name.strip() for name in (selected_models or ["all"]) if name.strip()
    ]

    if not requested or requested == ["all"]:
        model_names = list(specs.keys())
    else:
        unknown = [name for name in requested if name not in specs]
        if unknown:
            raise ValueError(
                f"Unknown model selection: {unknown}. "
                f"Available models: {list(specs.keys())}"
            )
        model_names = requested

    enabled: List[ModelSpec] = []
    skipped: List[Tuple[str, str]] = []
    for name in model_names:
        spec = specs[name]
        if spec.available:
            enabled.append(spec)
        else:
            skipped.append(
                (
                    spec.name,
                    spec.unavailable_reason or "Unavailable dependency.",
                )
            )

    if not enabled:
        raise ValueError(
            "No selected models are currently available. "
            "Install optional dependencies or choose a different model set."
        )

    return enabled, skipped


def _resolve_feature_modes(
    selected_modes: Optional[Sequence[str]],
) -> List[str]:
    requested = [
        mode.strip() for mode in (selected_modes or ["all"]) if mode.strip()
    ]

    if not requested or requested == ["all"]:
        return list(FEATURE_MODES)

    unknown = [mode for mode in requested if mode not in FEATURE_MODES]
    if unknown:
        raise ValueError(
            f"Unknown feature mode selection: {unknown}. "
            f"Available feature modes: {list(FEATURE_MODES)}"
        )

    return requested


def _effective_group_splits(
    groups: Optional[pd.Series], n_rows: int, n_splits: int
) -> Tuple[pd.Series, int]:
    if groups is None:
        groups = pd.Series(np.arange(n_rows), index=np.arange(n_rows))

    unique_groups = pd.unique(groups)
    if len(unique_groups) < 2:
        raise ValueError(
            "Need at least 2 distinct groups for grouped cross-validation. "
            "Add more laps/runs or change the grouping strategy."
        )

    return groups, min(n_splits, len(unique_groups))


def _cv_eval(
    X: pd.DataFrame,
    y: pd.Series,
    feature_names: List[str],
    groups: Optional[pd.Series],
    spec: ModelSpec,
    estimator_seed: int,
    n_splits: int,
    n_perm_repeats: int,
) -> Tuple[float, float, float, float, List[Tuple[str, float]]]:
    preprocessor = _build_preprocess_pipeline(feature_names, spec.preprocess)
    pipe = Pipeline(
        steps=[
            ("pre", preprocessor),
            ("model", spec.make_estimator(estimator_seed)),
        ]
    )

    groups, effective_splits = _effective_group_splits(groups, len(X), n_splits)
    splitter = GroupKFold(n_splits=effective_splits)
    rmses: List[float] = []
    r2s: List[float] = []

    # Aggregate permutation importance across folds (on held-out).
    importances_accum = np.zeros(len(feature_names), dtype=float)
    importances_count = 0

    for train_idx, test_idx in splitter.split(X, y, groups):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        pipe.fit(X_train, y_train)
        preds = pipe.predict(X_test)

        rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
        r2 = float(r2_score(y_test, preds))
        rmses.append(rmse)
        r2s.append(r2)

        # Permutation importance on test fold (model-agnostic).
        try:
            perm = permutation_importance(
                pipe,
                X_test,
                y_test,
                n_repeats=n_perm_repeats,
                random_state=estimator_seed,
                scoring="neg_root_mean_squared_error",
            )
            # Higher is better for neg RMSE; convert to positive importance by
            # negating.
            fold_imp = -perm.importances_mean
            importances_accum += fold_imp
            importances_count += 1
        except Exception:
            # If permutation importance fails (tiny folds), skip gracefully.
            pass

    rmse_mean = float(np.mean(rmses))
    rmse_std = float(np.std(rmses)) if len(rmses) > 1 else 0.0
    r2_mean = float(np.mean(r2s))
    r2_std = float(np.std(r2s)) if len(r2s) > 1 else 0.0

    if importances_count > 0:
        imp_mean = importances_accum / importances_count
        ranked = sorted(
            zip(feature_names, imp_mean.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )
        top_features = ranked[:15]
    else:
        top_features = []

    return rmse_mean, rmse_std, r2_mean, r2_std, top_features


def run(
    dataset_path: Path,
    out_path: Optional[Path],
    seed: int,
    n_splits: int,
    n_perm_repeats: int,
    model_names: Optional[Sequence[str]] = None,
    feature_modes: Optional[Sequence[str]] = None,
) -> List[ModelResult]:
    df = _read_dataset(dataset_path)

    # Basic sanity filters
    df = df.dropna(subset=["loss_ms"]).copy()
    if len(df) < 6:
        raise ValueError(
            f"Dataset too small after filtering (rows={len(df)}). "
            "Need more corners/laps."
        )

    group_col = _choose_group_col(df)
    groups = df[group_col] if group_col else None

    results: List[ModelResult] = []
    model_specs, skipped_models = _resolve_model_specs(model_names)
    selected_feature_modes = _resolve_feature_modes(feature_modes)
    _, effective_splits = _effective_group_splits(groups, len(df), n_splits)

    for feature_mode in selected_feature_modes:
        X, y, feature_names = _select_features(df, feature_mode)

        for spec in model_specs:
            rmse_mean, rmse_std, r2_mean, r2_std, top_feats = _cv_eval(
                X=X,
                y=y,
                feature_names=feature_names,
                groups=groups,
                spec=spec,
                estimator_seed=seed,
                n_splits=n_splits,
                n_perm_repeats=n_perm_repeats,
            )

            results.append(
                ModelResult(
                    model_name=spec.name,
                    feature_set=feature_mode,
                    n_rows=len(X),
                    n_features=len(feature_names),
                    cv_splits=effective_splits,
                    rmse_mean=rmse_mean,
                    rmse_std=rmse_std,
                    r2_mean=r2_mean,
                    r2_std=r2_std,
                    top_features=top_feats,
                )
            )

    print("\n=== Baseline Results (CV) ===")
    for r in results:
        print(
            f"- {r.model_name:9s} | {r.feature_set:10s} | "
            f"RMSE {r.rmse_mean:.2f}+/-{r.rmse_std:.2f} ms | "
            f"R^2 {r.r2_mean:.3f}+/-{r.r2_std:.3f} | "
            f"rows={r.n_rows} feats={r.n_features} splits={r.cv_splits}"
        )

        if r.top_features:
            print(
                "  Top features (perm importance, higher=worse RMSE impact):"
            )
            for feat, val in r.top_features[:10]:
                print(f"    - {feat}: {val:.4f}")
        print()

    if skipped_models:
        print("Skipped models:")
        for name, reason in skipped_models:
            print(f"  - {name}: {reason}")
        print()

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "dataset_path": str(dataset_path),
            "group_col": group_col,
            "selected_models": [spec.name for spec in model_specs],
            "selected_feature_modes": selected_feature_modes,
            "skipped_models": [
                {"model_name": name, "reason": reason}
                for name, reason in skipped_models
            ],
            "results": [asdict(r) for r in results],
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote report: {out_path}")

    return results


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Baseline ML evaluation for corner_dataset."
    )
    ap.add_argument(
        "dataset",
        type=str,
        help="Path to corner_dataset.csv or corner_dataset.parquet",
    )
    ap.add_argument(
        "--out",
        type=str,
        default="",
        help="Optional path to write JSON report",
    )
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument(
        "--splits",
        type=int,
        default=5,
        help="GroupKFold splits (limited by number of groups)",
    )
    ap.add_argument(
        "--perm-repeats",
        type=int,
        default=20,
        help="Permutation importance repeats per fold",
    )
    ap.add_argument(
        "--models",
        type=str,
        default="all",
        help=(
            "Comma-separated models to run "
            "(ridge, rf, catboost) or 'all'."
        ),
    )
    ap.add_argument(
        "--feature-modes",
        type=str,
        default="all",
        help=(
            "Comma-separated feature modes to run "
            "(heuristics, all_numeric) or 'all'."
        ),
    )
    args = ap.parse_args()

    dataset_path = Path(args.dataset)
    out_path = Path(args.out) if args.out.strip() else None

    run(
        dataset_path=dataset_path,
        out_path=out_path,
        seed=args.seed,
        n_splits=args.splits,
        n_perm_repeats=args.perm_repeats,
        model_names=args.models.split(","),
        feature_modes=args.feature_modes.split(","),
    )


if __name__ == "__main__":
    main()
