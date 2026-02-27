# src/research/config.py
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional, Tuple


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or not str(v).strip():
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _env_csv_tuple(name: str, default: Tuple[str, ...]) -> Tuple[str, ...]:
    v = os.getenv(name)
    if v is None or not v.strip():
        return default
    items = [x.strip() for x in v.split(",") if x.strip()]
    return tuple(items) if items else default


@dataclass(frozen=True)
class ResearchConfig:
    enabled: bool = True
    output_root: str = "data/runs"
    n_bins: int = 300

    # representation controls
    features: Tuple[str, ...] = (
        "speed_kmh",
        "throttle",
        "brake",
        "rpm",
        "gear",
        "curvature",
    )
    normalize: bool = False

    export_npz_if_available: bool = True
    export_json_always: bool = True
    export_corners: bool = True

    export_delta_profile: bool = True
    export_corner_rows: bool = True


def load_config() -> ResearchConfig:
    return ResearchConfig(
        enabled=_env_bool("RESEARCH_ENABLED", True),
        output_root=os.getenv("RESEARCH_OUTPUT_ROOT", "data/runs").strip()
        or "data/runs",
        n_bins=_env_int("RESEARCH_N_BINS", 300),
        features=_env_csv_tuple(
            "RESEARCH_FEATURES",
            ("speed_kmh", "throttle", "brake", "rpm", "gear", "curvature"),
        ),
        normalize=_env_bool("RESEARCH_NORMALIZE", False),
        export_npz_if_available=_env_bool("RESEARCH_EXPORT_NPZ", True),
        export_json_always=_env_bool("RESEARCH_EXPORT_JSON", True),
        export_corners=_env_bool("RESEARCH_EXPORT_CORNERS", True),
        export_delta_profile=_env_bool("RESEARCH_EXPORT_DELTA_PROFILE", True),
        export_corner_rows=_env_bool("RESEARCH_EXPORT_CORNER_ROWS", True),
    )
