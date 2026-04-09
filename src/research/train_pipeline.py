from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold

from .model_artifacts import (
    append_training_manifest_entry,
    default_artifact_dir,
    save_training_bundle,
)
from .model_factory import (
    build_training_pipeline,
    choose_group_col,
    resolve_feature_mode,
    resolve_model_spec,
    select_feature_names,
)
from .training_manifest import TrainingArtifactManifest


def _utc_iso(ts: float | None = None) -> str:
    if ts is None:
        ts = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_dataset(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported dataset format: {path}")


def resolve_dataset_path(path: str | Path) -> Path:
    p = Path(path)
    if p.is_dir():
        parquet_path = p / "corner_dataset.parquet"
        csv_path = p / "corner_dataset.csv"
        if parquet_path.exists():
            return parquet_path
        if csv_path.exists():
            return csv_path
        raise FileNotFoundError(
            f"No corner_dataset.parquet or corner_dataset.csv found in: {p}"
        )
    return p


def _infer_run_dir(dataset_path: Path) -> Optional[Path]:
    parent = dataset_path.parent
    if (parent / "run.json").exists():
        return parent
    return None


def _dataset_context(dataset_path: Path) -> Dict[str, Any]:
    run_dir = _infer_run_dir(dataset_path)
    run_json = _read_json(run_dir / "run.json") if run_dir else {}

    build_json_path = dataset_path.with_name(f"{dataset_path.stem}_build.json")
    build_json = _read_json(build_json_path) if build_json_path.exists() else {}

    return {
        "run_dir": run_dir,
        "run_id": run_json.get("run_id") if run_json else None,
        "schema_hash": (
            build_json.get("schema_hash")
            or run_json.get("schema_hash")
            or None
        ),
        "schema_version": (
            build_json.get("schema_version")
            or run_json.get("schema_version")
            or None
        ),
    }


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return repr(value)


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


def _select_training_frame(
    df: pd.DataFrame, feature_mode: str
) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    if "loss_ms" not in df.columns:
        raise ValueError("Dataset must contain target column 'loss_ms'.")

    feature_names = select_feature_names(df, feature_mode)
    X = df[feature_names].copy().apply(pd.to_numeric, errors="coerce")
    y = df["loss_ms"].astype(float)
    return X, y, feature_names


def _cv_metrics(
    X: pd.DataFrame,
    y: pd.Series,
    feature_names: Sequence[str],
    groups: Optional[pd.Series],
    *,
    model_name: str,
    seed: int,
    n_splits: int,
    n_perm_repeats: int,
) -> Tuple[Dict[str, float], List[Tuple[str, float]], int]:
    spec = resolve_model_spec(model_name)
    pipeline = build_training_pipeline(feature_names, spec, seed)
    groups, effective_splits = _effective_group_splits(groups, len(X), n_splits)
    splitter = GroupKFold(n_splits=effective_splits)

    rmses: List[float] = []
    r2s: List[float] = []
    importances_accum = np.zeros(len(feature_names), dtype=float)
    importances_count = 0

    for train_idx, test_idx in splitter.split(X, y, groups):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        pipeline.fit(X_train, y_train)
        preds = pipeline.predict(X_test)

        rmses.append(float(np.sqrt(mean_squared_error(y_test, preds))))
        r2s.append(float(r2_score(y_test, preds)))

        if n_perm_repeats <= 0:
            continue

        try:
            perm = permutation_importance(
                pipeline,
                X_test,
                y_test,
                n_repeats=n_perm_repeats,
                random_state=seed,
                scoring="neg_root_mean_squared_error",
            )
            fold_importance = -perm.importances_mean
            importances_accum += fold_importance
            importances_count += 1
        except Exception:
            pass

    metrics = {
        "rmse_mean": float(np.mean(rmses)),
        "rmse_std": float(np.std(rmses)) if len(rmses) > 1 else 0.0,
        "r2_mean": float(np.mean(r2s)),
        "r2_std": float(np.std(r2s)) if len(r2s) > 1 else 0.0,
    }

    if importances_count > 0:
        ranked = sorted(
            zip(feature_names, (importances_accum / importances_count).tolist()),
            key=lambda item: item[1],
            reverse=True,
        )
        top_features = [(str(name), float(score)) for name, score in ranked[:15]]
    else:
        top_features = []

    return metrics, top_features, effective_splits


@dataclass(frozen=True)
class TrainingRunResult:
    manifest: TrainingArtifactManifest
    model_path: Path
    manifest_path: Path


def train_and_save_model(
    dataset_path: str | Path,
    *,
    model_name: str,
    feature_mode: str = "all_numeric",
    seed: int = 7,
    n_splits: int = 5,
    n_perm_repeats: int = 20,
    out_dir: str | Path | None = None,
    overwrite: bool = False,
) -> TrainingRunResult:
    dataset_path = resolve_dataset_path(dataset_path)
    feature_mode = resolve_feature_mode(feature_mode)
    spec = resolve_model_spec(model_name)

    df = _read_dataset(dataset_path)
    df = df.dropna(subset=["loss_ms"]).copy()
    if len(df) < 6:
        raise ValueError(
            f"Dataset too small after filtering (rows={len(df)}). "
            "Need more corners/laps."
        )

    context = _dataset_context(dataset_path)
    group_col = choose_group_col(df.columns)
    groups = df[group_col] if group_col else None
    X, y, feature_names = _select_training_frame(df, feature_mode)

    metrics, top_features, effective_splits = _cv_metrics(
        X=X,
        y=y,
        feature_names=feature_names,
        groups=groups,
        model_name=spec.name,
        seed=seed,
        n_splits=n_splits,
        n_perm_repeats=n_perm_repeats,
    )

    final_pipeline = build_training_pipeline(feature_names, spec, seed)
    final_pipeline.fit(X, y)

    manifest = TrainingArtifactManifest(
        created_utc=_utc_iso(),
        model_name=spec.name,
        feature_set=feature_mode,
        preprocess=spec.preprocess,
        dataset_path=str(dataset_path),
        dataset_format=dataset_path.suffix.lower().lstrip("."),
        dataset_schema_hash=context["schema_hash"],
        dataset_schema_version=context["schema_version"],
        source_run_id=context["run_id"],
        source_run_dir=str(context["run_dir"]) if context["run_dir"] else None,
        n_rows=int(len(X)),
        n_features=int(len(feature_names)),
        feature_names=list(feature_names),
        group_col=group_col,
        cv_splits=effective_splits,
        seed=int(seed),
        n_perm_repeats=int(n_perm_repeats),
        metrics=metrics,
        top_features=top_features,
        estimator_params=_json_safe(
            final_pipeline.named_steps["model"].get_params(deep=False)
        ),
    )

    target_dir = (
        Path(out_dir)
        if out_dir is not None
        else default_artifact_dir(dataset_path, context["run_dir"])
    )
    model_path, manifest_path = save_training_bundle(
        final_pipeline,
        manifest,
        target_dir,
        overwrite=overwrite,
    )

    if context["run_dir"] is not None:
        append_training_manifest_entry(
            context["run_dir"],
            manifest,
            model_path=model_path,
            manifest_path=manifest_path,
        )

    return TrainingRunResult(
        manifest=manifest,
        model_path=model_path,
        manifest_path=manifest_path,
    )
