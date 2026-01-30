# src/research/dataset.py
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# Optional deps
try:
    import numpy as _np  # type: ignore
except Exception:
    _np = None

try:
    import pandas as _pd  # type: ignore
except Exception:
    _pd = None


_CORNER_JSON_RE = re.compile(r"^corner_(\d+)_(\d+)\.json$", re.IGNORECASE)


@dataclass(frozen=True)
class DatasetBuildReport:
    run_dir: Path
    corners_seen: int
    rows_emitted: int
    corners_skipped: int
    reasons: Dict[str, int]


def _safe_float(x: Any, default: float = float("nan")) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _safe_int(x: Any, default: int = -1) -> int:
    try:
        if x is None:
            return default
        return int(x)
    except Exception:
        return default


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_corner_json(path: Path) -> Tuple[List[List[float]], Dict[str, Any]]:
    obj = _read_json(path)
    X = obj.get("X")
    meta = obj.get("meta", {})
    if not isinstance(X, list):
        raise ValueError(f"{path.name}: expected list X")
    # ensure list[list[float]]
    X2: List[List[float]] = []
    for row in X:
        if not isinstance(row, list):
            continue
        X2.append([_safe_float(v) for v in row])
    return X2, dict(meta)


def _nanmean(vals: Sequence[float]) -> float:
    good = [v for v in vals if v == v and not math.isinf(v)]
    return sum(good) / len(good) if good else float("nan")


def _nanmin(vals: Sequence[float]) -> float:
    good = [v for v in vals if v == v and not math.isinf(v)]
    return min(good) if good else float("nan")


def _nanmax(vals: Sequence[float]) -> float:
    good = [v for v in vals if v == v and not math.isinf(v)]
    return max(good) if good else float("nan")


def _nanstd(vals: Sequence[float]) -> float:
    mu = _nanmean(vals)
    if not (mu == mu):
        return float("nan")
    good = [v for v in vals if v == v and not math.isinf(v)]
    if len(good) < 2:
        return 0.0
    var = sum((v - mu) ** 2 for v in good) / (len(good) - 1)
    return math.sqrt(var)


def _first_index_where(vals: Sequence[float], pred) -> Optional[int]:
    for i, v in enumerate(vals):
        try:
            if pred(v):
                return i
        except Exception:
            continue
    return None


def _ratio_where(vals: Sequence[float], pred) -> float:
    good = 0
    hit = 0
    for v in vals:
        if v != v or math.isinf(v):
            continue
        good += 1
        try:
            if pred(v):
                hit += 1
        except Exception:
            pass
    return (hit / good) if good else float("nan")


def _integral(vals: Sequence[float]) -> float:
    # simple sum; bins are uniform in distance-percent space
    good = [v for v in vals if v == v and not math.isinf(v)]
    return float(sum(good)) if good else float("nan")


def _summarize_X(X: List[List[float]], features: Sequence[str]) -> Dict[str, Any]:
    """
    Build engineered features from a corner tensor.
    Assumes X rows are aligned to distance bins within the corner segment.

    Supported canonical feature names expected from your pipeline:
      speed_kmh, throttle, brake, rpm, gear, curvature
    """
    out: Dict[str, Any] = {}
    if not X:
        out["corner_len"] = 0
        return out

    out["corner_len"] = len(X)
    dim = len(X[0]) if X[0] else 0
    out["corner_dim"] = dim

    # transpose to per-feature vectors (best effort)
    cols: Dict[str, List[float]] = {}
    for j, name in enumerate(features):
        cols[name] = [row[j] if j < len(row) else float("nan") for row in X]

    # speed stats
    spd = cols.get("speed_kmh", [])
    if spd:
        out["speed_min"] = _nanmin(spd)
        out["speed_max"] = _nanmax(spd)
        out["speed_mean"] = _nanmean(spd)
        out["speed_std"] = _nanstd(spd)

    # throttle stats
    thr = cols.get("throttle", [])
    if thr:
        out["throttle_mean"] = _nanmean(thr)
        out["throttle_std"] = _nanstd(thr)
        out["throttle_integral"] = _integral(thr)
        out["throttle_ratio_gt_05"] = _ratio_where(thr, lambda v: v > 0.5)

    # brake stats
    brk = cols.get("brake", [])
    if brk:
        out["brake_mean"] = _nanmean(brk)
        out["brake_std"] = _nanstd(brk)
        out["brake_integral"] = _integral(brk)
        out["brake_ratio_gt_05"] = _ratio_where(brk, lambda v: v > 0.5)

    # RPM stats
    rpm = cols.get("rpm", [])
    if rpm:
        out["rpm_mean"] = _nanmean(rpm)
        out["rpm_std"] = _nanstd(rpm)

    # Gear stats (gear may be float-cast already)
    gear = cols.get("gear", [])
    if gear:
        out["gear_min"] = _nanmin(gear)
        out["gear_max"] = _nanmax(gear)
        out["gear_mean"] = _nanmean(gear)

    # Curvature stats
    curv = cols.get("curvature", [])
    if curv:
        out["curvature_abs_mean"] = _nanmean([abs(v) if (v == v and not math.isinf(v)) else float("nan") for v in curv])
        out["curvature_abs_max"] = _nanmax([abs(v) if (v == v and not math.isinf(v)) else float("nan") for v in curv])
        # sign tendency: left vs right
        out["curvature_mean"] = _nanmean(curv)

    # Event-ish indices (normalized 0..1 within corner)
    # These are *heuristic*; we use them as ML features, not ground truth.
    if brk:
        i_brk_on = _first_index_where(brk, lambda v: v > 0.1)
        out["brake_onset_rel"] = (i_brk_on / max(1, len(brk) - 1)) if i_brk_on is not None else float("nan")
        i_brk_off = _first_index_where(reversed(brk), lambda v: v > 0.1)
        if i_brk_off is not None:
            idx = len(brk) - 1 - i_brk_off
            out["brake_release_rel"] = idx / max(1, len(brk) - 1)
        else:
            out["brake_release_rel"] = float("nan")

    if thr:
        i_thr_on = _first_index_where(thr, lambda v: v > 0.1)
        out["throttle_onset_rel"] = (i_thr_on / max(1, len(thr) - 1)) if i_thr_on is not None else float("nan")

    return out


def _corner_uid(track_name: Optional[str], corner_index: int) -> str:
    # For now: stable by index within detected corner list.
    # Later: you can make this stable by segment location buckets.
    tn = (track_name or "UNKNOWN_TRACK").strip().replace(" ", "_")
    return f"{tn}_C{corner_index:02d}"


def _should_skip_corner(meta: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Filters out common junk samples (e.g., partial laps).
    """
    lap_time_ms = _safe_float(meta.get("lap_time_ms"), default=float("nan"))
    # partial lap usually has -1 or missing
    if lap_time_ms != lap_time_ms or lap_time_ms <= 0:
        return True, "partial_or_unknown_lap_time"

    # must have indices
    if _safe_int(meta.get("corner_start_idx")) < 0 or _safe_int(meta.get("corner_end_idx")) < 0:
        return True, "missing_indices"

    return False, "ok"


def build_corner_dataset(
    run_dir: Path | str,
    track_name: Optional[str] = None,
    include_raw_X: bool = False,
) -> Tuple["Any", DatasetBuildReport]:
    """
    Build a corner-level dataset from a run folder.

    Returns: (DataFrame, report)
      - DataFrame requires pandas; if pandas isn't installed, returns a list[dict] instead.
    """
    run_dir = Path(run_dir)
    corners_dir = run_dir / "corners"
    run_json_path = run_dir / "run.json"

    reasons: Dict[str, int] = {}
    corners_seen = 0
    rows_emitted = 0
    corners_skipped = 0

    run_meta: Dict[str, Any] = {}
    if run_json_path.exists():
        try:
            run_meta = _read_json(run_json_path)
        except Exception:
            run_meta = {}

    # best effort track name
    tn = track_name or run_meta.get("track_name") or run_meta.get("track") or None

    rows: List[Dict[str, Any]] = []

    if not corners_dir.exists():
        report = DatasetBuildReport(run_dir=run_dir, corners_seen=0, rows_emitted=0, corners_skipped=0, reasons={"no_corners_dir": 1})
        return (_pd.DataFrame([]) if _pd else []), report

    corner_files = sorted([p for p in corners_dir.iterdir() if p.is_file() and p.suffix.lower() == ".json"])

    for p in corner_files:
        m = _CORNER_JSON_RE.match(p.name)
        if not m:
            continue

        corners_seen += 1
        lap_num = int(m.group(1))
        corner_index = int(m.group(2))

        try:
            X, meta = _load_corner_json(p)
        except Exception:
            corners_skipped += 1
            reasons["bad_corner_json"] = reasons.get("bad_corner_json", 0) + 1
            continue

        skip, why = _should_skip_corner(meta)
        if skip:
            corners_skipped += 1
            reasons[why] = reasons.get(why, 0) + 1
            continue

        features = meta.get("features")
        if not isinstance(features, list) or not features:
            # assume canonical order used by your exporter
            features = ["speed_kmh", "throttle", "brake", "rpm", "gear", "curvature"]

        # core identifiers
        row: Dict[str, Any] = {
            "run_id": run_meta.get("run_id") or meta.get("run_id"),
            "run_tag": run_meta.get("run_tag") or meta.get("run_tag"),
            "track_name": tn,
            "lap_num": _safe_int(meta.get("lap_num", lap_num), default=lap_num),
            "corner_index": _safe_int(meta.get("corner_index", corner_index), default=corner_index),
            "corner_uid": _corner_uid(tn, corner_index),
            "corner_direction": meta.get("corner_direction"),
            "corner_strength": _safe_float(meta.get("corner_strength")),
            "corner_start_idx": _safe_int(meta.get("corner_start_idx")),
            "corner_end_idx": _safe_int(meta.get("corner_end_idx")),
            "n_bins": _safe_int(meta.get("n_bins")),
            "sampling_hz": _safe_int(meta.get("sampling_hz")),
        }

        # targets / baseline metrics
        row.update({
            "loss_ms": _safe_float(meta.get("loss_ms")),
            "brake_start_delta_m": _safe_float(meta.get("brake_start_delta_m")),
            "throttle_on_delta_m": _safe_float(meta.get("throttle_on_delta_m")),
            "min_speed_delta_kmh": _safe_float(meta.get("min_speed_delta_kmh")),
            "exit_speed_delta_kmh": _safe_float(meta.get("exit_speed_delta_kmh")),
        })

        # lap context
        row.update({
            "lap_time_ms": _safe_float(meta.get("lap_time_ms")),
            "lap_distance_m": _safe_float(meta.get("lap_distance_m")),
        })

        # engineered features from X
        row.update(_summarize_X(X, features))

        if include_raw_X:
            row["X"] = X
            row["features"] = features

        rows.append(row)
        rows_emitted += 1

    # Build report
    report = DatasetBuildReport(
        run_dir=run_dir,
        corners_seen=corners_seen,
        rows_emitted=rows_emitted,
        corners_skipped=corners_skipped,
        reasons=dict(reasons),
    )

    # Return DataFrame if pandas exists
    if _pd is not None:
        return _pd.DataFrame(rows), report
    return rows, report


def save_corner_dataset(
    df: "Any",
    run_dir: Path | str,
    stem: str = "corner_dataset",
    write_parquet: bool = True,
) -> Dict[str, Optional[Path]]:
    """
    Save dataset next to the run as CSV + (optionally) Parquet.
    Returns paths.
    """
    run_dir = Path(run_dir)
    out_csv = run_dir / f"{stem}.csv"
    out_parquet = run_dir / f"{stem}.parquet" if write_parquet else None

    paths: Dict[str, Optional[Path]] = {"csv": out_csv, "parquet": out_parquet}

    if _pd is None:
        raise RuntimeError("pandas is required to save datasets. Install pandas (and pyarrow for parquet).")

    # CSV always
    df.to_csv(out_csv, index=False)

    # Parquet optional
    if write_parquet and out_parquet is not None:
        try:
            df.to_parquet(out_parquet, index=False)
        except Exception:
            # parquet is optional; keep CSV as source of truth
            paths["parquet"] = None

    return paths


def build_and_save_corner_dataset(
    run_dir: Path | str,
    track_name: Optional[str] = None,
    include_raw_X: bool = False,
) -> Tuple[Dict[str, Optional[Path]], DatasetBuildReport]:
    df, report = build_corner_dataset(run_dir, track_name=track_name, include_raw_X=include_raw_X)
    paths = save_corner_dataset(df, run_dir)
    return paths, report


def _print_report(report: DatasetBuildReport) -> None:
    print(f"[dataset] run_dir: {report.run_dir}")
    print(f"[dataset] corners_seen: {report.corners_seen}")
    print(f"[dataset] rows_emitted: {report.rows_emitted}")
    print(f"[dataset] corners_skipped: {report.corners_skipped}")
    if report.reasons:
        print("[dataset] skip reasons:")
        for k, v in sorted(report.reasons.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  - {k}: {v}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Build a corner-level dataset from a GT7 Race Engineer run folder.")
    ap.add_argument("run_dir", type=str, help="Path to data/runs/<run_id> folder")
    ap.add_argument("--track", type=str, default=None, help="Override track name (e.g., Monza)")
    ap.add_argument("--include-raw", action="store_true", help="Include raw X sequences in memory (not recommended for CSV)")
    ap.add_argument("--no-parquet", action="store_true", help="Disable parquet output")
    args = ap.parse_args()

    if _pd is None:
        raise SystemExit("pandas is required. Install pandas to use this script.")

    df, report = build_corner_dataset(args.run_dir, track_name=args.track, include_raw_X=args.include_raw)
    paths = save_corner_dataset(df, args.run_dir, write_parquet=(not args.no_parquet))
    _print_report(report)
    print(f"[dataset] wrote: {paths['csv']}")
    if paths["parquet"]:
        print(f"[dataset] wrote: {paths['parquet']}")
