# src/research/export.py
from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Dict, Optional, Tuple, List

from src.core.telemetry_session import LapData, TelemetrySession
from .schema import FeatureSpec, build_lap_tensor

try:
    import numpy as _np  # optional
except Exception:
    _np = None


def _safe_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)


def _lap_baselines(
    session: TelemetrySession,
    last: LapData,
    ref: Optional[LapData],
    n: int,
) -> Dict[str, Any]:
    """
    Export the deterministic baselines promised in the proposal:
      - distance-aligned delta-time profile
      - corner coaching rows
    """
    out: Dict[str, Any] = {
        "has_reference": bool(ref),
        "reference_lap_num": (ref.lap_num if ref else None),
        "n": n,
    }

    if not ref or ref.lap_num == last.lap_num:
        return out

    # Time delta profile (last - ref) aligned by distance
    dt = session.delta_profile_time_ms(last, ref, n=n)
    out["delta_profile_time_ms"] = [float(x) for x in dt] if dt else None

    # Corner rows (uses your existing heuristic extraction)
    rows = session.corner_coaching_rows(last, ref, n=n)
    if rows is None:
        out["corner_rows"] = None
    else:
        # Make rows JSON-serializable
        serial_rows: List[Dict[str, Any]] = []
        for r in rows:
            seg = r.get("seg")
            serial_rows.append(
                {
                    "seg": None if seg is None else {
                        "start_idx": int(seg.start_idx),
                        "end_idx": int(seg.end_idx),
                        "direction": int(seg.direction),
                        "strength": float(seg.strength),
                    },
                    "loss_ms": float(r.get("loss_ms", 0.0)),
                    "brake_start_delta_m": (None if r.get("brake_start_delta_m") is None else float(r["brake_start_delta_m"])),
                    "throttle_on_delta_m": (None if r.get("throttle_on_delta_m") is None else float(r["throttle_on_delta_m"])),
                    "min_speed_delta_kmh": float(r.get("min_speed_delta_kmh", 0.0)),
                    "exit_speed_delta_kmh": float(r.get("exit_speed_delta_kmh", 0.0)),
                }
            )
        out["corner_rows"] = serial_rows

    return out


def export_lap_bundle(
    run_dir: Path,
    session: TelemetrySession,
    lap: LapData,
    n: int = 300,
    spec: FeatureSpec = FeatureSpec(),
    export_npz_if_available: bool = True,
    export_json_always: bool = True,
    export_baselines: bool = True,
) -> Tuple[Path, Optional[Path], Optional[Path]]:
    """
    Exports a single lap as:
      - laps/lap_<lapnum>.json  (always if export_json_always)
      - laps/lap_<lapnum>.npz   (if numpy available and export_npz_if_available)
      - baselines/lap_<lapnum>_vs_ref.json  (if export_baselines)
    Returns (json_path, npz_path, baseline_path)
    """
    run_dir = Path(run_dir)
    laps_dir = run_dir / "laps"
    base_dir = run_dir / "baselines"
    laps_dir.mkdir(parents=True, exist_ok=True)
    base_dir.mkdir(parents=True, exist_ok=True)

    X, meta = build_lap_tensor(session, lap, n=n, spec=spec)

    json_path = laps_dir / f"lap_{lap.lap_num:04d}.json"
    npz_path: Optional[Path] = None
    baseline_path: Optional[Path] = None

    if export_json_always:
        _safe_write_json(json_path, {"X": X, "meta": meta})

    if export_npz_if_available and _np is not None:
        npz_path = laps_dir / f"lap_{lap.lap_num:04d}.npz"
        arr = _np.array(X, dtype=_np.float32)
        # store meta as JSON string for portability
        meta_str = json.dumps(meta, sort_keys=True)
        _np.savez_compressed(npz_path, X=arr, meta_json=meta_str)

    if export_baselines:
        ref = session.reference_lap()
        baseline = _lap_baselines(session, lap, ref, n=n)
        baseline_path = base_dir / f"lap_{lap.lap_num:04d}_vs_ref.json"
        _safe_write_json(baseline_path, baseline)

    return json_path, npz_path, baseline_path
