# src/research/schema.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import math
import hashlib
import json

# We intentionally import the internal resampling helpers you already use
# for baselines.
from src.core.telemetry_session import (
    LapData,
    TelemetrySession,
    _resample_by_distance,
    _resample_series_by_distance,
)

# Dataset schema version for thesis reproducibility
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class FeatureSpec:
    """
    Defines which features are included in the exported tensor and their order.

    Tensor shape: [N, F]
      N = distance bins
      F = len(features)
    """

    features: Tuple[str, ...] = (
        "speed_kmh",
        "throttle",
        "brake",
        "rpm",
        "gear",
        "curvature",  # derived from resampled heading deltas (proxy)
    )

    def index(self, name: str) -> int:
        return self.features.index(name)


def schema_hash(
    *,
    spec: FeatureSpec,
    normalize: bool,
    n_bins: int,
    extra: Dict[str, Any] | None = None,
) -> str:
    """
    Stable hash describing the exported tensor meaning.
    If any of these change, training artifacts must not be mixed.
    """
    payload = {
        "schema_version": SCHEMA_VERSION,
        "features": list(spec.features),
        "normalize": bool(normalize),
        "n_bins": int(n_bins),
        "extra": extra or {},
    }
    b = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(b).hexdigest()[:16]


def _wrap_pi(a: float) -> float:
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def _curvature_proxy(points_xz: List[Tuple[float, float]]) -> List[float]:
    """
    Compute a simple curvature proxy over resampled points:
      curvature[i] = delta_heading between segments (wrapped to [-pi, pi])
    """
    n = len(points_xz)
    if n < 3:
        return [0.0] * n

    headings = [0.0] * n
    for i in range(1, n):
        dx = points_xz[i][0] - points_xz[i - 1][0]
        dz = points_xz[i][1] - points_xz[i - 1][1]
        headings[i] = math.atan2(dz, dx)

    curv = [0.0] * n
    for i in range(2, n):
        curv[i] = _wrap_pi(headings[i] - headings[i - 1])

    return curv


def build_lap_tensor(
    session: TelemetrySession,
    lap: LapData,
    n: int = 300,
    spec: FeatureSpec = FeatureSpec(),
) -> tuple[List[List[float]], Dict[str, Any]]:
    """
    Build a distance-normalized lap tensor X: [n, F] + metadata.

    Uses existing distance resampling helpers for consistency
    with baselines.
    """
    if not lap.samples or not lap.cum_dist_m:
        X = [[0.0 for _ in spec.features] for _ in range(n)]
        meta = {
            "ok": False,
            "reason": "empty lap",
            "lap_num": getattr(lap, "lap_num", None),
            "n": n,
            "features": list(spec.features),
        }
        return X, meta

    aligned_samples = [
        s
        for s in lap.samples
        if (
            abs(getattr(s, "x", 0.0)) > 1e-6
            or abs(getattr(s, "z", 0.0)) > 1e-6
        )
    ]

    cum = lap.cum_dist_m
    L = min(len(aligned_samples), len(cum))
    aligned_samples = aligned_samples[:L]
    cum = cum[:L]

    if len(aligned_samples) < 5 or len(cum) < 5:
        X = [[0.0 for _ in spec.features] for _ in range(n)]
        meta = {
            "ok": False,
            "reason": "too few samples",
            "lap_num": getattr(lap, "lap_num", None),
            "n": n,
            "features": list(spec.features),
        }
        return X, meta

    speed = [float(getattr(s, "speed_kmh", 0.0)) for s in aligned_samples]
    thr = [float(getattr(s, "throttle", 0.0)) for s in aligned_samples]
    brk = [float(getattr(s, "brake", 0.0)) for s in aligned_samples]
    rpm = [float(getattr(s, "rpm", 0.0)) for s in aligned_samples]
    gear = [float(getattr(s, "gear", 0.0)) for s in aligned_samples]

    speed_r = _resample_series_by_distance(speed, cum, n=n)
    thr_r = _resample_series_by_distance(thr, cum, n=n)
    brk_r = _resample_series_by_distance(brk, cum, n=n)
    rpm_r = _resample_series_by_distance(rpm, cum, n=n)
    gear_r = _resample_series_by_distance(gear, cum, n=n)

    pts_r = (
        _resample_by_distance(lap.points_xz, lap.cum_dist_m, n=n)
        if getattr(lap, "points_xz", None)
        else []
    )
    curv_r = _curvature_proxy(pts_r) if pts_r else [0.0] * n

    series_map: Dict[str, List[float]] = {
        "speed_kmh": speed_r,
        "throttle": thr_r,
        "brake": brk_r,
        "rpm": rpm_r,
        "gear": gear_r,
        "curvature": curv_r,
    }

    X: List[List[float]] = []
    for i in range(n):
        row = []
        for name in spec.features:
            arr = series_map.get(name)
            row.append(float(arr[i]) if arr and i < len(arr) else 0.0)
        X.append(row)

    ref = session.reference_lap()
    meta: Dict[str, Any] = {
        "ok": True,
        "lap_num": int(getattr(lap, "lap_num", 0)),
        "lap_time_ms": int(getattr(lap, "lap_time_ms", 0) or 0),
        "total_dist_m": float(lap.cum_dist_m[-1] if lap.cum_dist_m else 0.0),
        "n": n,
        "features": list(spec.features),
        "session_id": int(session.session_id()),
        "reference_lap_num": (ref.lap_num if ref else None),
    }
    return X, meta
