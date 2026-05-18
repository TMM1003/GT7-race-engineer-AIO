from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.track_geometry import (
    align_track_to_lap,
    aligned_track_to_payload,
    lap_track_metrics,
)
from src.track_geometry.tumftm import (
    DEFAULT_CACHE_ROOT,
    canonical_track_key,
    ensure_tumftm_track_cached,
    load_tumftm_track,
)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Fit retained TUMFTM/trackdb geometry into GT7 X/Z coordinates "
            "using a saved lap with exported resampled positions."
        )
    )
    ap.add_argument(
        "--run-dir",
        type=Path,
        help="Run folder containing run.json and laps/lap_####.json.",
    )
    ap.add_argument(
        "--lap",
        type=int,
        default=None,
        help="Lap number to align against. Defaults to run reference lap.",
    )
    ap.add_argument(
        "--track",
        default="Spa-Francorchamps",
        help="Track name or GT7 layout name, e.g. Spa-Francorchamps.",
    )
    ap.add_argument(
        "--cache-root",
        type=Path,
        default=DEFAULT_CACHE_ROOT,
        help="Local cache for TUMFTM CSVs.",
    )
    ap.add_argument(
        "--cache-only",
        action="store_true",
        help="Validate/download the trackdb CSVs and exit without alignment.",
    )
    ap.add_argument(
        "--download",
        action="store_true",
        help="Download missing TUMFTM CSVs into the cache root.",
    )
    ap.add_argument(
        "--n",
        type=int,
        default=720,
        help="Number of resampled geometry bins to write.",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON path. Defaults to run_dir/track_alignment_<track>.json.",
    )
    ap.add_argument(
        "--plot",
        action="store_true",
        help="Also write a PNG alignment QA plot beside the JSON.",
    )
    args = ap.parse_args()

    track_key = canonical_track_key(args.track)
    if track_key is None:
        raise SystemExit(f"No retained trackdb mapping for: {args.track!r}")

    if args.download:
        paths = ensure_tumftm_track_cached(
            args.track,
            cache_root=args.cache_root,
        )
        print(f"TUMFTM {track_key} cache ready:")
        print("  track:", paths["track"])
        print("  raceline:", paths["raceline"])
    else:
        track_path = args.cache_root / "tracks" / f"{track_key}.csv"
        raceline_path = args.cache_root / "racelines" / f"{track_key}.csv"
        if not track_path.exists() or not raceline_path.exists():
            raise SystemExit(
                f"Missing local trackdb CSVs for {track_key}. "
                "Use --download to fetch them."
            )

    if args.cache_only:
        print(f"trackdb {track_key} files are available.")
        return

    if args.run_dir is None:
        ap.error("--run-dir is required unless --cache-only is set.")

    run_dir = args.run_dir.expanduser().resolve()
    lap_path = _choose_lap_json(run_dir, args.lap)
    lap_payload = _read_json(lap_path)
    points = _extract_points_xz(lap_payload)
    if not points:
        raise SystemExit(
            "This lap artifact does not contain geometry.points_xz. "
            "It likely predates the GT7 position export added for external "
            "track alignment. Capture/export a new run, then rerun this script."
        )

    track = load_tumftm_track(
        args.track,
        cache_root=args.cache_root,
        allow_download=args.download,
    )
    aligned = align_track_to_lap(track, points, n_fit_points=max(120, args.n))
    metrics = lap_track_metrics(points, aligned, n=300)

    out_path = (
        args.out.expanduser().resolve()
        if args.out is not None
        else run_dir / f"track_alignment_{track_key}.json"
    )
    payload = aligned_track_to_payload(aligned, n=args.n)
    payload["gt7_reference"] = {
        "run_dir": str(run_dir),
        "lap_file": str(lap_path),
        "lap_num": _lap_num_from_payload(lap_payload),
        "lap_distance_m": _lap_distance_from_payload(lap_payload),
    }
    payload["lap_metrics"] = metrics
    _write_json(out_path, payload)

    print("Alignment written:", out_path)
    print(f"  rmse_m: {aligned.transform.rmse_m:.3f}")
    print(f"  mean_error_m: {aligned.transform.mean_error_m:.3f}")
    print(f"  p95_error_m: {aligned.transform.p95_error_m:.3f}")
    print(f"  max_error_m: {aligned.transform.max_error_m:.3f}")
    print(f"  scale: {aligned.transform.scale:.6f}")
    print(f"  reflected: {aligned.transform.reflected}")
    print(f"  reversed: {aligned.transform.reversed}")
    print(f"  shift_bins: {aligned.transform.shift_bins}")
    print(f"  raceline_error_mean_m: {metrics['raceline_error_mean_m']:.3f}")
    print(f"  off_track_bins: {metrics['off_track_bins']}")

    if args.plot:
        plot_path = out_path.with_suffix(".png")
        _write_plot(plot_path, payload, points)
        print("QA plot written:", plot_path)


def _choose_lap_json(run_dir: Path, lap_num: Optional[int]) -> Path:
    if lap_num is None:
        run_json = _read_json(run_dir / "run.json")
        raw = run_json.get("reference_lap_num")
        try:
            lap_num = int(raw)
        except Exception:
            lap_num = None

    laps_dir = run_dir / "laps"
    if lap_num is not None:
        path = laps_dir / f"lap_{int(lap_num):04d}.json"
        if path.exists():
            return path
        raise FileNotFoundError(f"Lap JSON not found: {path}")

    candidates = sorted(laps_dir.glob("lap_*.json"))
    if not candidates:
        raise FileNotFoundError(f"No lap JSON files found in: {laps_dir}")
    return candidates[-1]


def _extract_points_xz(payload: dict[str, Any]) -> list[tuple[float, float]]:
    geometry = payload.get("geometry") or {}
    raw_points = geometry.get("points_xz") if isinstance(geometry, dict) else None
    if not isinstance(raw_points, list):
        return []
    points: list[tuple[float, float]] = []
    for raw in raw_points:
        if not isinstance(raw, (list, tuple)) or len(raw) < 2:
            continue
        try:
            points.append((float(raw[0]), float(raw[1])))
        except Exception:
            continue
    return points


def _lap_num_from_payload(payload: dict[str, Any]) -> Optional[int]:
    try:
        return int((payload.get("meta") or {}).get("lap_num"))
    except Exception:
        return None


def _lap_distance_from_payload(payload: dict[str, Any]) -> Optional[float]:
    try:
        return float((payload.get("meta") or {}).get("lap_distance_m"))
    except Exception:
        return None


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_plot(
    path: Path,
    payload: dict[str, Any],
    lap_points: list[tuple[float, float]],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    resampled = payload["resampled"]
    fig, ax = plt.subplots(figsize=(8.5, 8.5))

    def draw(points, label, color, width=1.2, alpha=1.0):
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        if points:
            xs.append(points[0][0])
            ys.append(points[0][1])
        ax.plot(xs, ys, label=label, color=color, linewidth=width, alpha=alpha)

    draw(resampled["left_boundary_xz"], "TUM left edge", "#7f8c8d", 0.9)
    draw(resampled["right_boundary_xz"], "TUM right edge", "#7f8c8d", 0.9)
    draw(resampled["centerline_xz"], "TUM centerline", "#95a5a6", 1.0, 0.8)
    draw(resampled["raceline_xz"], "TUM raceline", "#f39c12", 1.6)
    draw(lap_points, "GT7 reference lap", "#2ecc71", 1.6)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.2)
    ax.legend(loc="best")
    track = payload.get("source", {}).get("name", "trackdb")
    ax.set_title(f"TUMFTM {track} aligned to GT7 reference lap")
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
