# scripts/build_dataset.py
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `import src...` works
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.research.dataset import build_and_save_corner_dataset


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Offline rebuild of corner-level dataset from a GT7 run folder"
    )
    ap.add_argument(
        "run_dir",
        type=Path,
        help="Path to data/runs/<run_id> directory",
    )
    ap.add_argument(
        "--track",
        type=str,
        default=None,
        help="Override track name (e.g., Monza)",
    )
    ap.add_argument(
        "--include-raw",
        action="store_true",
        help="Include raw per-sample X sequences (not recommended for CSV)",
    )
    ap.add_argument(
        "--no-parquet",
        action="store_true",
        help="Disable Parquet output",
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing dataset files if present",
    )

    args = ap.parse_args()
    run_dir = args.run_dir.expanduser().resolve()

    if not run_dir.exists():
        print(f"ERROR: Run directory does not exist: {run_dir}", file=sys.stderr)
        return 1

    if not (run_dir / "run.json").exists():
        print(f"ERROR: run.json not found in: {run_dir}", file=sys.stderr)
        return 1

    paths, report = build_and_save_corner_dataset(
        run_dir=run_dir,
        track_name=args.track,
        include_raw_X=args.include_raw,
        write_parquet=not args.no_parquet,
        overwrite=args.overwrite,
    )

    print("[build_dataset] Dataset build complete")
    print(f"  rows_emitted: {report.rows_emitted}")
    print(f"  corners_seen: {report.corners_seen}")
    print(f"  corners_skipped: {report.corners_skipped}")

    for k, v in paths.items():
        if v is not None:
            print(f"  wrote {k}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
