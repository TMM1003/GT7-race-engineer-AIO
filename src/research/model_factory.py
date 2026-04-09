from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from catboost import CatBoostRegressor
except Exception:
    CatBoostRegressor = None


NON_FEATURE_COLS = {
    "loss_ms",
    "run_id",
    "track_name",
    "corner_uid",
    "corner_direction",
}

HEURISTIC_FEATURES = [
    "brake_start_delta_m",
    "throttle_on_delta_m",
    "min_speed_delta_kmh",
    "exit_speed_delta_kmh",
]

GROUP_PRIORITY = ["lap_num", "run_id"]
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


def build_model_specs() -> Dict[str, ModelSpec]:
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


def available_model_names() -> List[str]:
    return [name for name, spec in build_model_specs().items() if spec.available]


def resolve_model_spec(model_name: str) -> ModelSpec:
    specs = build_model_specs()
    key = (model_name or "").strip().lower()
    if key not in specs:
        raise ValueError(
            f"Unknown model '{model_name}'. Available models: {list(specs)}"
        )

    spec = specs[key]
    if not spec.available:
        raise ValueError(
            spec.unavailable_reason
            or f"Model '{model_name}' is not available in this environment."
        )
    return spec


def resolve_feature_mode(feature_mode: str) -> str:
    key = (feature_mode or "").strip().lower()
    if key not in FEATURE_MODES:
        raise ValueError(
            f"Unknown feature mode '{feature_mode}'. "
            f"Available modes: {list(FEATURE_MODES)}"
        )
    return key


def choose_group_col(columns: Sequence[str]) -> Optional[str]:
    names = set(columns)
    for col in GROUP_PRIORITY:
        if col in names:
            return col
    return None


def select_feature_names(df, feature_mode: str) -> List[str]:
    mode = resolve_feature_mode(feature_mode)

    if "loss_ms" not in df.columns:
        raise ValueError("Dataset must contain target column 'loss_ms'.")

    if mode == "heuristics":
        missing = [c for c in HEURISTIC_FEATURES if c not in df.columns]
        if missing:
            raise ValueError(
                f"Heuristic features missing from dataset: {missing}"
            )
        return list(HEURISTIC_FEATURES)

    numeric_cols = df.select_dtypes(include=["number", "bool"]).columns.tolist()
    feature_names = [c for c in numeric_cols if c not in NON_FEATURE_COLS]
    if not feature_names:
        raise ValueError("No numeric feature columns found after exclusions.")
    return feature_names


def build_preprocess_pipeline(
    feature_names: Sequence[str], preprocess: str
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
        transformers=[("num", numeric_transformer, list(feature_names))],
        remainder="drop",
        sparse_threshold=0.0,
    )


def build_training_pipeline(
    feature_names: Sequence[str], spec: ModelSpec, seed: int
) -> Pipeline:
    return Pipeline(
        steps=[
            (
                "pre",
                build_preprocess_pipeline(feature_names, spec.preprocess),
            ),
            ("model", spec.make_estimator(seed)),
        ]
    )
