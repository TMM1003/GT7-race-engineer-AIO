# src/research/dataset.py
from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.research.schema import SCHEMA_VERSION

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


def _utc_iso(ts: float | None = None) -> str:
    if ts is None:
        ts = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


@dataclass(frozen=True)
class DatasetBuildReport:
    run_dir: Path
    corners_seen: int
    rows_emitted: int
    corners_skipped: int
    reasons: Dict[str, int]
    schema_version: int
    schema_hash: Optional[str]


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


def _safe_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)


def _load_corner_json(path: Path) -> Tuple[List[List[float]], Dict[str, Any]]:
    obj = _read_json(path)
    X = obj.get("X")
    meta = obj.get("meta", {})
    if not isinstance(X, list):
        raise ValueError(f"{path.name}: expected list X")
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
    good = [v for v in vals if v == v and not math.isinf(v)]
    return float(sum(good)) if good else float("nan")


def _summarize_X(X: List[List[float]], features: Sequence[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not X:
        out["corner_len"] = 0
        return out

    out["corner_len"] = len(X)
    dim = len(X[0]) if X[0] else 0
    out["corner_dim"] = dim

    cols: Dict[str, List[float]] = {}
    for j, name in enumerate(features):
        cols[name] = [row[j] if j < len(row) else float("nan") for row in X]

    spd = cols.get("speed_kmh", [])
    if spd:
        out["speed_min"] = _nanmin(spd)
        out["speed_max"] = _nanmax(spd)
        out["speed_mean"] = _nanmean(spd)
        out["speed_std"] = _nanstd(spd)

    thr = cols.get("throttle", [])
    if thr:
        out["throttle_mean"] = _nanmean(thr)
        out["throttle_std"] = _nanstd(thr)
        out["throttle_integral"] = _integral(thr)
        out["throttle_ratio_gt_05"] = _ratio_where(thr, lambda v: v > 0.5)

    brk = cols.get("brake", [])
    if brk:
        out["brake_mean"] = _nanmean(brk)
        out["brake_std"] = _nanstd(brk)
        out["brake_integral"] = _integral(brk)
        out["brake_ratio_gt_05"] = _ratio_where(brk, lambda v: v > 0.5)

    rpm = cols.get("rpm", [])
    if rpm:
        out["rpm_mean"] = _nanmean(rpm)
        out["rpm_std"] = _nanstd(rpm)

    gear = cols.get("gear", [])
    if gear:
        out["gear_min"] = _nanmin(gear)
        out["gear_max"] = _nanmax(gear)
        out["gear_mean"] = _nanmean(gear)

    curv = cols.get("curvature", [])
    if curv:
        out["curvature_abs_mean"] = _nanmean([abs(v) if (v == v and not math.isinf(v)) else float("nan") for v in curv])
        out["curvature_abs_max"] = _nanmax([abs(v) if (v == v and not math.isinf(v)) else float("nan") for v in curv])
        out["curvature_mean"] = _nanmean(curv)

    # Event-ish indices (normalized 0..1 within corner)
    if brk:
        i_brk_on = _first_index_where(brk, lambda v: v > 0.1)
        out["brake_onset_rel"] = (i_brk_on / max(1, len(brk) - 1)) if i_brk_on is not None else float("nan")
        i_brk_off = _first_index_where(list(reversed(brk)), lambda v: v > 0.1)
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
    tn = (track_name or "UNKNOWN_TRACK").strip().replace(" ", "_")
    return f"{tn}_C{corner_index:02d}"


def _should_skip_corner(meta: Dict[str, Any]) -> Tuple[bool, str]:
    lap_time_ms = _safe_float(meta.get("lap_time_ms"), default=float("nan"))
    if lap_time_ms != lap_time_ms or lap_time_ms <= 0:
        return True, "partial_or_unknown_lap_time"

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

    Determinism rules:
      - iterate corner JSONs sorted by (lap_num, corner_index)
      - emit rows in that order
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

    schema_hash = run_meta.get("schema_hash")
    tn = track_name or run_meta.get("track_name") or run_meta.get("track") or None

    rows: List[Dict[str, Any]] = []

    if not corners_dir.exists():
        report = DatasetBuildReport(
            run_dir=run_dir,
            corners_seen=0,
            rows_emitted=0,
            corners_skipped=0,
            reasons={"no_corners_dir": 1},
            schema_version=SCHEMA_VERSION,
            schema_hash=schema_hash if isinstance(schema_hash, str) else None,
        )
        return (_pd.DataFrame([]) if _pd else []), report

    corner_files: List[Tuple[int, int, Path]] = []
    for p in corners_dir.iterdir():
        if not p.is_file() or p.suffix.lower() != ".json":
            continue
        m = _CORNER_JSON_RE.match(p.name)
        if not m:
            continue
        lap_num = int(m.group(1))
        corner_index = int(m.group(2))
        corner_files.append((lap_num, corner_index, p))

    corner_files.sort(key=lambda t: (t[0], t[1]))

    for lap_num, corner_index, p in corner_files:
        corners_seen += 1

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
            features = ["speed_kmh", "throttle", "brake", "rpm", "gear", "curvature"]

        row: Dict[str, Any] = {
            "run_id": run_meta.get("run_id") or meta.get("run_id"),
            "run_tag": run_meta.get("run_tag") or meta.get("run_tag"),
            "run_alias": run_meta.get("run_alias"),
            "track_name": tn,
            "car_name": run_meta.get("car_name"),
            "notes": run_meta.get("notes"),
            "lap_num": _safe_int(meta.get("lap_num", lap_num), default=lap_num),
            "corner_index": _safe_int(meta.get("corner_index", corner_index), default=corner_index),
            "corner_uid": _corner_uid(tn, corner_index),
            "corner_direction": meta.get("corner_direction"),
            "corner_strength": _safe_float(meta.get("corner_strength")),
            "corner_start_idx": _safe_int(meta.get("corner_start_idx")),
            "corner_end_idx": _safe_int(meta.get("corner_end_idx")),
            "n_bins": _safe_int(meta.get("n_bins")),
            "sampling_hz": _safe_int(meta.get("sampling_hz")),
            "schema_version": int(run_meta.get("schema_version") or SCHEMA_VERSION),
            "schema_hash": (schema_hash if isinstance(schema_hash, str) else None),
            "reference_locked": bool(run_meta.get("reference_locked", False)),
            "reference_lap_num": run_meta.get("reference_lap_num"),
        }

        row.update({
            "loss_ms": _safe_float(meta.get("loss_ms")),
            "brake_start_delta_m": _safe_float(meta.get("brake_start_delta_m")),
            "throttle_on_delta_m": _safe_float(meta.get("throttle_on_delta_m")),
            "min_speed_delta_kmh": _safe_float(meta.get("min_speed_delta_kmh")),
            "exit_speed_delta_kmh": _safe_float(meta.get("exit_speed_delta_kmh")),
        })

        row.update({
            "lap_time_ms": _safe_float(meta.get("lap_time_ms")),
            "lap_distance_m": _safe_float(meta.get("lap_distance_m")),
        })

        row.update(_summarize_X(X, features))

        if include_raw_X:
            row["X"] = X
            row["features"] = features

        rows.append(row)
        rows_emitted += 1

    report = DatasetBuildReport(
        run_dir=run_dir,
        corners_seen=corners_seen,
        rows_emitted=rows_emitted,
        corners_skipped=corners_skipped,
        reasons=dict(reasons),
        schema_version=int(run_meta.get("schema_version") or SCHEMA_VERSION),
        schema_hash=(schema_hash if isinstance(schema_hash, str) else None),
    )

    if _pd is not None:
        df = _pd.DataFrame(rows)

        # Deterministic column order (stable)
        preferred = [
            "run_id", "run_tag", "run_alias", "track_name", "car_name", "notes",
            "schema_version", "schema_hash",
            "reference_locked", "reference_lap_num",
            "lap_num", "corner_index", "corner_uid", "corner_direction", "corner_strength",
            "corner_start_idx", "corner_end_idx",
            "n_bins", "sampling_hz",
            "lap_time_ms", "lap_distance_m",
            "loss_ms", "brake_start_delta_m", "throttle_on_delta_m", "min_speed_delta_kmh", "exit_speed_delta_kmh",
            "corner_len", "corner_dim",
            "speed_min", "speed_max", "speed_mean", "speed_std",
            "throttle_mean", "throttle_std", "throttle_integral", "throttle_ratio_gt_05",
            "brake_mean", "brake_std", "brake_integral", "brake_ratio_gt_05",
            "rpm_mean", "rpm_std",
            "gear_min", "gear_max", "gear_mean",
            "curvature_abs_mean", "curvature_abs_max", "curvature_mean",
            "brake_onset_rel", "brake_release_rel", "throttle_onset_rel",
        ]
        cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
        df = df[cols]

        # Stable sorting in case upstream changes
        if "lap_num" in df.columns and "corner_index" in df.columns:
            df = df.sort_values(["lap_num", "corner_index"], kind="mergesort").reset_index(drop=True)

        return df, report

    return rows, report


def save_corner_dataset(
    df: "Any",
    run_dir: Path | str,
    stem: str = "corner_dataset",
    write_parquet: bool = True,
    overwrite: bool = True,
    dataset_build: Optional[Dict[str, Any]] = None,
) -> Dict[str, Optional[Path]]:
    # Save dataset outputs into the run directory
    run_dir = Path(run_dir)

    out_csv = run_dir / f"{stem}.csv"
    out_parquet = run_dir / f"{stem}.parquet" if write_parquet else None
    out_build = run_dir / f"{stem}_build.json"

    # Enforce overwrite semantics
    if not overwrite:
        if out_csv.exists():
            raise FileExistsError(f"Refusing to overwrite existing file: {out_csv}")
        if out_build.exists():
            raise FileExistsError(f"Refusing to overwrite existing file: {out_build}")
        if out_parquet is not None and out_parquet.exists():
            raise FileExistsError(f"Refusing to overwrite existing file: {out_parquet}")

    paths: Dict[str, Optional[Path]] = {
        "csv": out_csv,
        "parquet": out_parquet,
        "build": out_build,
    }

    # CSV is always written
    df.to_csv(out_csv, index=False)

    # Parquet is optional and best-effort
    if out_parquet is not None:
        try:
            df.to_parquet(out_parquet, index=False)
        except Exception:
            paths["parquet"] = None

    # Build report JSON is always written (if provided)
    if dataset_build is None:
        dataset_build = {}

    out_build.write_text(json.dumps(dataset_build, indent=2), encoding="utf-8")

    return paths



def build_and_save_corner_dataset(
    run_dir: Path | str,
    track_name: Optional[str] = None,
    include_raw_X: bool = False,
    write_parquet: bool = True,
    stem: str = "corner_dataset",
    overwrite: bool = True,
) -> Tuple[Dict[str, Optional[Path]], "DatasetBuildReport"]:
    run_dir = Path(run_dir)

    df_or_rows, report = build_corner_dataset(
        run_dir=run_dir,
        track_name=track_name,
        include_raw_X=include_raw_X,
    )

    # If pandas is unavailable, build_corner_dataset returns list[dict]
    # Save expects a DataFrame-like with .to_csv; convert if needed.
    df = df_or_rows
    if not hasattr(df_or_rows, "to_csv"):
        import pandas as pd
        df = pd.DataFrame(df_or_rows)

    dataset_build = {
        "run_dir": str(run_dir),
        "track_name": track_name,
        "include_raw_X": include_raw_X,
        "rows_emitted": report.rows_emitted,
        "corners_seen": report.corners_seen,
        "corners_skipped": report.corners_skipped,
        "reasons": report.reasons,
        "schema_version": report.schema_version,
        "schema_hash": report.schema_hash,
    }

    paths = save_corner_dataset(
        df,
        run_dir,
        stem=stem,
        write_parquet=write_parquet,
        overwrite=overwrite,
        dataset_build=dataset_build,
    )

    return paths, report


def _print_report(report: DatasetBuildReport) -> None:
    print(f"[dataset] run_dir: {report.run_dir}")
    print(f"[dataset] corners_seen: {report.corners_seen}")
    print(f"[dataset] rows_emitted: {report.rows_emitted}")
    print(f"[dataset] corners_skipped: {report.corners_skipped}")
    print(f"[dataset] schema_version: {report.schema_version}")
    print(f"[dataset] schema_hash: {report.schema_hash}")
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

    paths, report = build_and_save_corner_dataset(
        args.run_dir,
        track_name=args.track,
        include_raw_X=args.include_raw,
    )
    _print_report(report)
    print(f"[dataset] wrote: {paths['csv']}")
    if paths.get("parquet"):
        print(f"[dataset] wrote: {paths['parquet']}")
    print(f"[dataset] wrote: {paths['build']}")
