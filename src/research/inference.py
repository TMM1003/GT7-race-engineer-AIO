# src/research/inference.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, Dict, Optional, Sequence

from .model_artifacts import TrainedModelBundle, load_training_bundle


@dataclass
class InferenceResult:
    lap_score: Optional[float] = None
    anomaly_score: Optional[float] = None
    per_distance_score: Optional[list[float]] = None
    corner_predictions: Optional[list[float]] = None
    model_name: Optional[str] = None
    feature_set: Optional[str] = None
    notes: Optional[str] = None


ModelBundle = TrainedModelBundle


def load_model_if_present(path: str | Path) -> Optional[ModelBundle]:
    p = Path(path)
    if not p.exists():
        return None
    return load_training_bundle(p)


def predict_corner_rows(
    model: Optional[ModelBundle],
    rows: Sequence[Dict[str, Any]],
) -> Optional[InferenceResult]:
    if model is None:
        return None

    predictions = model.predict_rows(rows)
    mean_prediction = float(fmean(predictions)) if predictions else None

    return InferenceResult(
        lap_score=mean_prediction,
        corner_predictions=predictions,
        model_name=model.manifest.model_name,
        feature_set=model.manifest.feature_set,
        notes=(
            "lap_score is the mean predicted corner loss_ms across the "
            "provided corner rows."
        ),
    )


def infer_on_lap(
    model: Optional[ModelBundle],
    X_lap: list[list[float]],
    meta: Dict[str, Any],
) -> Optional[InferenceResult]:
    """
    Runtime inference entrypoint for the app.

    The saved training artifacts in this repo are corner-level tabular models.
    To use them at runtime, provide `meta["corner_rows"]` as a list of dicts
    with the same engineered feature columns used in training.
    """
    if model is None:
        return None

    corner_rows = meta.get("corner_rows")
    if isinstance(corner_rows, Sequence) and not isinstance(
        corner_rows, (str, bytes)
    ):
        try:
            return predict_corner_rows(model, corner_rows)
        except Exception as exc:
            return InferenceResult(
                model_name=model.manifest.model_name,
                feature_set=model.manifest.feature_set,
                notes=f"Inference failed: {exc!r}",
            )

    return InferenceResult(
        model_name=model.manifest.model_name,
        feature_set=model.manifest.feature_set,
        notes=(
            "Model is loaded, but this artifact predicts corner-level rows. "
            "Provide meta['corner_rows'] to run inference with the trained "
            "pipeline."
        ),
    )
