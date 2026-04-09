from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


TRAINING_ARTIFACT_VERSION = 1


@dataclass
class TrainingArtifactManifest:
    artifact_version: int = TRAINING_ARTIFACT_VERSION
    artifact_kind: str = "corner_regression_pipeline"
    created_utc: str = ""

    model_name: str = ""
    feature_set: str = ""
    preprocess: str = ""
    target_column: str = "loss_ms"

    dataset_path: str = ""
    dataset_format: str = ""
    dataset_schema_hash: Optional[str] = None
    dataset_schema_version: Optional[int] = None
    source_run_id: Optional[str] = None
    source_run_dir: Optional[str] = None

    artifact_model_path: Optional[str] = None
    artifact_manifest_path: Optional[str] = None

    n_rows: int = 0
    n_features: int = 0
    feature_names: List[str] = field(default_factory=list)
    group_col: Optional[str] = None
    cv_splits: int = 0
    seed: int = 0
    n_perm_repeats: int = 0

    metrics: Dict[str, float] = field(default_factory=dict)
    top_features: List[Tuple[str, float]] = field(default_factory=list)
    estimator_params: Dict[str, Any] = field(default_factory=dict)


def training_manifest_from_dict(
    data: Dict[str, Any],
) -> TrainingArtifactManifest:
    payload = dict(data or {})

    top_features = []
    for item in payload.get("top_features", []) or []:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            try:
                top_features.append((str(item[0]), float(item[1])))
            except Exception:
                continue
    payload["top_features"] = top_features

    return TrainingArtifactManifest(**payload)
