# src/ai/inference.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

# Keep this dependency-free. You can swap in torch/jax later.


@dataclass
class InferenceResult:
    # Example fields; adapt to your model outputs
    lap_score: Optional[float] = None          # e.g., probability "good lap"
    anomaly_score: Optional[float] = None      # e.g., reconstruction error
    per_distance_score: Optional[list[float]] = None  # length N, for localization
    notes: Optional[str] = None


class ModelBundle:
    """
    Placeholder container. You can implement:
      - torch.load(...)
      - joblib.load(...)
      - onnxruntime session
    """
    def __init__(self, path: Path):
        self.path = Path(path)
        self.kind = self.path.suffix.lower()
        self.model = None

    def is_loaded(self) -> bool:
        return self.model is not None


def load_model_if_present(path: str | Path) -> Optional[ModelBundle]:
    p = Path(path)
    if not p.exists():
        return None
    b = ModelBundle(p)
    # Defer actual loading to your chosen framework.
    # Keep bundle non-None so the app can show "model found" vs "not found".
    b.model = object()
    return b


def infer_on_lap(model: Optional[ModelBundle], X_lap: list[list[float]], meta: Dict[str, Any]) -> Optional[InferenceResult]:
    """
    Runtime inference entrypoint for the app.
    If no model is loaded, returns None.
    """
    if model is None or not model.is_loaded():
        return None

    # Stub behavior: replace with real inference.
    # Keep deterministic structure for UI integration.
    return InferenceResult(
        lap_score=None,
        anomaly_score=None,
        per_distance_score=None,
        notes=f"Model placeholder loaded from {model.path.name}, but inference not implemented yet.",
    )
