# src/research/export.py
from __future__ import annotations

from pathlib import Path
import json
import time
from typing import Any, Dict, Optional, Tuple, List

from src.core.telemetry_session import (
    LapData,
    TelemetrySession,
    _resample_by_distance,
)
from .schema import FeatureSpec, build_lap_tensor
from src.track_geometry import (
    align_track_to_lap,
    aligned_track_to_payload,
    lap_track_metrics,
)
from src.track_geometry.tumftm import canonical_track_key, load_tumftm_track

try:
    import numpy as _np  # optional
except Exception:
    _np = None


def _utc_iso(ts: float | None = None) -> str:
    if ts is None:
        ts = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _safe_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _update_manifest(
    run_dir: Path, entry: Dict[str, Any], *, section: str
) -> None:
    """
    Append an entry to manifest.json.
    """
    mpath = run_dir / "manifest.json"
    if mpath.exists():
        try:
            manifest = _read_json(mpath)
        except Exception:
            manifest = {}
    else:
        manifest = {}

    if not isinstance(manifest, dict):
        manifest = {}

    manifest.setdefault("run_id", run_dir.name)
    manifest.setdefault("created_utc", _utc_iso())
    manifest["updated_utc"] = _utc_iso()
    manifest.setdefault("laps", [])
    manifest.setdefault("baselines", [])
    manifest.setdefault("corners", [])
    manifest.setdefault("dataset_builds", [])

    if section not in manifest or not isinstance(manifest.get(section), list):
        manifest[section] = []

    manifest[section].append(entry)

    _safe_write_json(mpath, manifest)


def _export_corner_tensors(
    corners_dir: Path,
    lap_num: int,
    X_lap: List[List[float]],
    meta: Dict[str, Any],
    corner_rows: Optional[List[Dict[str, Any]]],
    export_npz_if_available: bool,
    export_json_always: bool,
) -> List[Dict[str, Any]]:
    """
    Returns list of manifest entries for corner artifacts.
    """
    exported: List[Dict[str, Any]] = []
    if not corner_rows:
        return exported

    corners_dir.mkdir(parents=True, exist_ok=True)

    for i, r in enumerate(corner_rows, start=1):
        seg = r.get("seg")
        if not seg:
            continue

        s = int(seg["start_idx"])
        e = int(seg["end_idx"])
        if e <= s or s < 0 or e > len(X_lap):
            continue

        Xc = X_lap[s:e]
        cmeta = dict(meta)
        cmeta.update(
            {
                "corner_index": i,
                "corner_start_idx": s,
                "corner_end_idx": e,
                "corner_direction": seg.get("direction"),
                "corner_strength": seg.get("strength"),
                "loss_ms": r.get("loss_ms"),
                "brake_start_delta_m": r.get("brake_start_delta_m"),
                "throttle_on_delta_m": r.get("throttle_on_delta_m"),
                "min_speed_delta_kmh": r.get("min_speed_delta_kmh"),
                "exit_speed_delta_kmh": r.get("exit_speed_delta_kmh"),
            }
        )

        json_rel = f"corners/corner_{lap_num:04d}_{i:02d}.json"
        npz_rel = f"corners/corner_{lap_num:04d}_{i:02d}.npz"

        json_path = corners_dir / f"corner_{lap_num:04d}_{i:02d}.json"
        npz_path = corners_dir / f"corner_{lap_num:04d}_{i:02d}.npz"

        if export_json_always:
            _safe_write_json(json_path, {"X": Xc, "meta": cmeta})

        if export_npz_if_available and _np is not None:
            arr = _np.array(Xc, dtype=_np.float32)
            meta_str = json.dumps(cmeta, sort_keys=True)
            _np.savez_compressed(npz_path, X=arr, meta_json=meta_str)

        exported.append(
            {
                "lap_num": int(lap_num),
                "corner_index": int(i),
                "paths": {
                    "json": (json_rel if export_json_always else None),
                    "npz": (
                        npz_rel
                        if (export_npz_if_available and _np is not None)
                        else None
                    ),
                },
                "timestamp_utc": _utc_iso(),
            }
        )

    return exported


def _lap_baselines(
    session: TelemetrySession,
    last: LapData,
    ref: Optional[LapData],
    n: int,
    *,
    run_dir: Optional[Path] = None,
    track_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Export deterministic baselines:
      - distance-aligned delta-time profile
      - corner coaching rows
    """
    out: Dict[str, Any] = {
        "has_reference": bool(ref),
        "reference_lap_num": (ref.lap_num if ref else None),
        "n": n,
    }

    external = _external_track_baseline(
        run_dir=run_dir,
        track_name=track_name,
        lap=last,
        ref=ref,
        n=n,
    )
    if external is not None:
        out["external_track"] = external

    if not ref or ref.lap_num == last.lap_num:
        return out

    dt = session.delta_profile_time_ms(last, ref, n=n)
    out["delta_profile_time_ms"] = [float(x) for x in dt] if dt else None

    rows = session.corner_coaching_rows(last, ref, n=n)
    if rows is None:
        out["corner_rows"] = None
    else:
        serial_rows: List[Dict[str, Any]] = []
        for r in rows:
            seg = r.get("seg")
            serial_rows.append(
                {
                    "seg": None
                    if seg is None
                    else {
                        "start_idx": int(seg.start_idx),
                        "end_idx": int(seg.end_idx),
                        "direction": int(seg.direction),
                        "strength": float(seg.strength),
                    },
                    "loss_ms": float(r.get("loss_ms", 0.0)),
                    "brake_start_delta_m": (
                        None
                        if r.get("brake_start_delta_m") is None
                        else float(r["brake_start_delta_m"])
                    ),
                    "throttle_on_delta_m": (
                        None
                        if r.get("throttle_on_delta_m") is None
                        else float(r["throttle_on_delta_m"])
                    ),
                    "min_speed_delta_kmh": float(
                        r.get("min_speed_delta_kmh", 0.0)
                    ),
                    "exit_speed_delta_kmh": float(
                        r.get("exit_speed_delta_kmh", 0.0)
                    ),
                }
            )
        out["corner_rows"] = serial_rows

    return out


def _external_track_baseline(
    *,
    run_dir: Optional[Path],
    track_name: Optional[str],
    lap: LapData,
    ref: Optional[LapData],
    n: int,
) -> Optional[Dict[str, Any]]:
    if ref is None:
        return None
    key = canonical_track_key(track_name)
    if key is None:
        return None
    if not ref.points_xz or len(ref.points_xz) < 10:
        return None
    if not lap.points_xz or len(lap.points_xz) < 10:
        return None

    try:
        track = load_tumftm_track(key)
        aligned = align_track_to_lap(track, ref.points_xz, n_fit_points=720)
        metrics = lap_track_metrics(lap.points_xz, aligned, n=n)
    except Exception as e:
        return {
            "available": False,
            "track_key": key,
            "reason": f"{type(e).__name__}: {e}",
        }

    alignment_rel = None
    if run_dir is not None:
        try:
            alignment_path = run_dir / f"track_alignment_{key}.json"
            payload = aligned_track_to_payload(aligned, n=720)
            payload["gt7_reference"] = {
                "track_name": track_name,
                "reference_lap_num": int(ref.lap_num),
                "reference_lap_distance_m": float(
                    ref.cum_dist_m[-1] if ref.cum_dist_m else 0.0
                ),
            }
            _safe_write_json(alignment_path, payload)
            alignment_rel = alignment_path.name
        except Exception:
            alignment_rel = None

    return {
        "available": True,
        "track_key": key,
        "source": track.source,
        "alignment_path": alignment_rel,
        "reference_lap_num": int(ref.lap_num),
        "transform": {
            "matrix": aligned.transform.matrix,
            "scale": float(aligned.transform.scale),
            "translation": [
                float(aligned.transform.translation[0]),
                float(aligned.transform.translation[1]),
            ],
            "reflected": bool(aligned.transform.reflected),
            "reversed": bool(aligned.transform.reversed),
            "shift_bins": int(aligned.transform.shift_bins),
            "rmse_m": float(aligned.transform.rmse_m),
            "mean_error_m": float(aligned.transform.mean_error_m),
            "p95_error_m": float(aligned.transform.p95_error_m),
            "max_error_m": float(aligned.transform.max_error_m),
        },
        "lap_metrics": metrics,
    }


def export_lap_bundle(
    run_dir: Path,
    session: TelemetrySession,
    lap: LapData,
    n: int = 300,
    spec: FeatureSpec = FeatureSpec(),
    export_npz_if_available: bool = True,
    export_json_always: bool = True,
    export_baselines: bool = True,
    export_corners: bool = True,
    track_name: Optional[str] = None,
) -> Tuple[Path, Optional[Path], Optional[Path]]:
    """
    Exports a single lap as:
      - laps/lap_<lapnum>.json  (always if export_json_always)
      - laps/lap_<lapnum>.npz
        (if numpy available and export_npz_if_available)
      - baselines/lap_<lapnum>_vs_ref.json  (if export_baselines)
      - corners/corner_<lapnum>_<corner>.{json,npz}
        (if export_corners and corner_rows exist)
    Returns (json_path, npz_path, baseline_path)
    """
    run_dir = Path(run_dir)
    laps_dir = run_dir / "laps"
    base_dir = run_dir / "baselines"
    corners_dir = run_dir / "corners"

    laps_dir.mkdir(parents=True, exist_ok=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    corners_dir.mkdir(parents=True, exist_ok=True)

    X, meta = build_lap_tensor(session, lap, n=n, spec=spec)
    meta["n_bins"] = int(n)
    meta["sampling_hz"] = 60
    meta["run_id"] = run_dir.name

    json_path = laps_dir / f"lap_{lap.lap_num:04d}.json"
    npz_path: Optional[Path] = None
    baseline_path: Optional[Path] = None

    points_xz_resampled = (
        _resample_by_distance(lap.points_xz, lap.cum_dist_m, n=n)
        if getattr(lap, "points_xz", None)
        and getattr(lap, "cum_dist_m", None)
        else []
    )
    distance_axis_m = (
        [
            float(meta["lap_distance_m"]) * (i / max(1, n - 1))
            for i in range(n)
        ]
        if meta.get("ok") and n > 0
        else []
    )
    geometry_payload = {
        "source": "gt7_telemetry_resampled",
        "points_xz": [
            [float(x), float(z)] for x, z in points_xz_resampled
        ],
        "distance_axis_m": distance_axis_m,
    }

    if export_json_always:
        _safe_write_json(
            json_path,
            {"X": X, "meta": meta, "geometry": geometry_payload},
        )

    if export_npz_if_available and _np is not None:
        npz_path = laps_dir / f"lap_{lap.lap_num:04d}.npz"
        arr = _np.array(X, dtype=_np.float32)
        meta_str = json.dumps(meta, sort_keys=True)
        points_arr = _np.array(points_xz_resampled, dtype=_np.float32)
        dist_arr = _np.array(distance_axis_m, dtype=_np.float32)
        _np.savez_compressed(
            npz_path,
            X=arr,
            meta_json=meta_str,
            points_xz=points_arr,
            distance_axis_m=dist_arr,
        )

    # Manifest: lap artifacts
    _update_manifest(
        run_dir,
        {
            "lap_num": int(lap.lap_num),
            "lap_time_ms": int(getattr(lap, "lap_time_ms", 0) or 0),
            "paths": {
                "json": f"laps/{json_path.name}"
                if export_json_always
                else None,
                "npz": f"laps/{npz_path.name}"
                if (npz_path is not None)
                else None,
            },
            "timestamp_utc": _utc_iso(),
        },
        section="laps",
    )

    baseline = None
    if export_baselines:
        ref = session.reference_lap()
        baseline = _lap_baselines(
            session,
            lap,
            ref,
            n=n,
            run_dir=run_dir,
            track_name=track_name,
        )
        baseline_path = base_dir / f"lap_{lap.lap_num:04d}_vs_ref.json"
        _safe_write_json(baseline_path, baseline)

        _update_manifest(
            run_dir,
            {
                "lap_num": int(lap.lap_num),
                "reference_lap_num": baseline.get("reference_lap_num"),
                "paths": {"json": f"baselines/{baseline_path.name}"},
                "timestamp_utc": _utc_iso(),
            },
            section="baselines",
        )

    # Export corner tensors based on baseline corner segments
    if export_corners and baseline is not None:
        corner_entries = _export_corner_tensors(
            corners_dir=corners_dir,
            lap_num=lap.lap_num,
            X_lap=X,
            meta=meta,
            corner_rows=baseline.get("corner_rows"),
            export_npz_if_available=export_npz_if_available,
            export_json_always=export_json_always,
        )
        for ce in corner_entries:
            _update_manifest(run_dir, ce, section="corners")

    return json_path, npz_path, baseline_path
