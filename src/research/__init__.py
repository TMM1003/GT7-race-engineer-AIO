from __future__ import annotations

from .config import ResearchConfig, load_config
from .registry import RunRegistry, create_run
from .schema import FeatureSpec, build_lap_tensor
from .export import export_lap_bundle
from .model_artifacts import (
    TrainedModelBundle,
    load_training_bundle,
    save_training_bundle,
)
from .train_pipeline import (
    TrainingRunResult,
    resolve_dataset_path,
    train_and_save_model,
)
from .training_manifest import (
    TRAINING_ARTIFACT_VERSION,
    TrainingArtifactManifest,
)

# NEW: dataset exports
from .dataset import (
    DatasetBuildReport,
    build_corner_dataset,
    save_corner_dataset,
    build_and_save_corner_dataset,
)

__all__ = [
    # config / lifecycle
    "ResearchConfig",
    "load_config",
    "RunRegistry",
    "create_run",
    # schema / export
    "FeatureSpec",
    "build_lap_tensor",
    "export_lap_bundle",
    # training
    "TRAINING_ARTIFACT_VERSION",
    "TrainingArtifactManifest",
    "TrainingRunResult",
    "TrainedModelBundle",
    "resolve_dataset_path",
    "train_and_save_model",
    "load_training_bundle",
    "save_training_bundle",
    # dataset (NEW)
    "DatasetBuildReport",
    "build_corner_dataset",
    "save_corner_dataset",
    "build_and_save_corner_dataset",
]
