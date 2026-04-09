from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

import joblib
import pandas as pd

from .training_manifest import (
    TrainingArtifactManifest,
    training_manifest_from_dict,
)


def _utc_iso(ts: float | None = None) -> str:
    if ts is None:
        ts = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _safe_write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)


def _artifact_stem(model_name: str, feature_set: str) -> str:
    return f"{model_name.strip().lower()}_{feature_set.strip().lower()}"


def _resolve_manifest_path(path: str | Path) -> Path:
    p = Path(path)
    if p.suffix.lower() == ".json":
        return p
    if p.suffix.lower() == ".joblib":
        return p.with_suffix(".json")
    raise ValueError(
        f"Expected a .joblib or .json artifact path, received: {path}"
    )


def _resolve_model_path(path: str | Path) -> Path:
    p = Path(path)
    if p.suffix.lower() == ".joblib":
        return p
    if p.suffix.lower() == ".json":
        return p.with_suffix(".joblib")
    raise ValueError(
        f"Expected a .joblib or .json artifact path, received: {path}"
    )


def _resolve_relative_path(
    path_text: Optional[str], base_dir: Path
) -> Optional[Path]:
    if not path_text:
        return None
    p = Path(path_text)
    if p.is_absolute():
        return p
    return base_dir / p


def default_artifact_dir(
    dataset_path: str | Path, source_run_dir: str | Path | None = None
) -> Path:
    if source_run_dir:
        return Path(source_run_dir) / "models"
    return Path(dataset_path).parent / "models"


def save_training_bundle(
    pipeline: Any,
    manifest: TrainingArtifactManifest,
    out_dir: str | Path,
    *,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    stem = _artifact_stem(manifest.model_name, manifest.feature_set)
    model_path = out_root / f"{stem}.joblib"
    manifest_path = out_root / f"{stem}.json"

    if not overwrite and (model_path.exists() or manifest_path.exists()):
        raise FileExistsError(
            f"Training artifact already exists: {model_path} / {manifest_path}"
        )

    manifest.artifact_model_path = model_path.name
    manifest.artifact_manifest_path = manifest_path.name
    if not manifest.created_utc:
        manifest.created_utc = _utc_iso()

    joblib.dump(pipeline, model_path)
    _safe_write_json(manifest_path, asdict(manifest))
    return model_path, manifest_path


@dataclass
class TrainedModelBundle:
    pipeline: Any
    manifest: TrainingArtifactManifest
    model_path: Path
    manifest_path: Path

    def required_feature_names(self) -> list[str]:
        return list(self.manifest.feature_names)

    def predict_dataframe(self, frame: pd.DataFrame) -> list[float]:
        missing = [
            col for col in self.required_feature_names() if col not in frame.columns
        ]
        if missing:
            raise ValueError(
                f"Prediction frame is missing required features: {missing}"
            )
        preds = self.pipeline.predict(frame[self.required_feature_names()])
        return [float(v) for v in preds]

    def predict_rows(
        self, rows: Sequence[Dict[str, Any]] | Iterable[Dict[str, Any]]
    ) -> list[float]:
        frame = pd.DataFrame(list(rows))
        return self.predict_dataframe(frame)


def load_training_bundle(path: str | Path) -> TrainedModelBundle:
    manifest_path = _resolve_manifest_path(path)
    model_path = _resolve_model_path(path)

    if manifest_path.exists():
        data = _read_json(manifest_path)
        manifest = training_manifest_from_dict(data)
        resolved = _resolve_relative_path(
            manifest.artifact_model_path, manifest_path.parent
        )
        if resolved is not None:
            model_path = resolved
    else:
        raise FileNotFoundError(f"Artifact manifest not found: {manifest_path}")

    if not model_path.exists():
        raise FileNotFoundError(f"Trained model not found: {model_path}")

    pipeline = joblib.load(model_path)
    return TrainedModelBundle(
        pipeline=pipeline,
        manifest=manifest,
        model_path=model_path,
        manifest_path=manifest_path,
    )


def append_training_manifest_entry(
    run_dir: str | Path,
    manifest: TrainingArtifactManifest,
    *,
    model_path: str | Path,
    manifest_path: str | Path,
) -> None:
    root = Path(run_dir)
    root.mkdir(parents=True, exist_ok=True)
    manifest_json = root / "manifest.json"
    payload = _read_json(manifest_json) if manifest_json.exists() else {}
    payload.setdefault("run_id", root.name)
    payload.setdefault("created_utc", manifest.created_utc or _utc_iso())
    payload["updated_utc"] = _utc_iso()
    payload.setdefault("trained_models", [])

    try:
        rel_model = str(Path(model_path).relative_to(root))
    except Exception:
        rel_model = str(model_path)

    try:
        rel_manifest = str(Path(manifest_path).relative_to(root))
    except Exception:
        rel_manifest = str(manifest_path)

    payload["trained_models"].append(
        {
            "timestamp_utc": manifest.created_utc or _utc_iso(),
            "model_name": manifest.model_name,
            "feature_set": manifest.feature_set,
            "target_column": manifest.target_column,
            "schema_hash": manifest.dataset_schema_hash,
            "schema_version": manifest.dataset_schema_version,
            "paths": {
                "model": rel_model,
                "manifest": rel_manifest,
            },
            "metrics": dict(manifest.metrics),
            "top_features": list(manifest.top_features),
        }
    )
    _safe_write_json(manifest_json, payload)
