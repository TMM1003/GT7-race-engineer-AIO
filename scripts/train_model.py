from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.research.train_pipeline import (
    resolve_dataset_path,
    train_and_save_model,
)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Train a corner-level regression model from corner_dataset.csv "
            "or corner_dataset.parquet and save reloadable artifacts."
        )
    )
    ap.add_argument(
        "dataset_or_run",
        type=str,
        help=(
            "Path to a corner_dataset.csv/parquet file or a run directory "
            "containing that dataset."
        ),
    )
    ap.add_argument(
        "--model",
        type=str,
        default="catboost",
        help="Model to train: ridge, rf, or catboost.",
    )
    ap.add_argument(
        "--feature-mode",
        type=str,
        default="all_numeric",
        help="Feature mode to train: heuristics or all_numeric.",
    )
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument(
        "--splits",
        type=int,
        default=5,
        help="Grouped cross-validation splits.",
    )
    ap.add_argument(
        "--perm-repeats",
        type=int,
        default=20,
        help="Permutation-importance repeats during CV evaluation.",
    )
    ap.add_argument(
        "--out-dir",
        type=str,
        default="",
        help=(
            "Optional output directory for saved artifacts. "
            "Defaults to <run_dir>/models."
        ),
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite an existing artifact with the same model/feature name.",
    )
    args = ap.parse_args()

    dataset_path = resolve_dataset_path(Path(args.dataset_or_run))
    result = train_and_save_model(
        dataset_path=dataset_path,
        model_name=args.model,
        feature_mode=args.feature_mode,
        seed=args.seed,
        n_splits=args.splits,
        n_perm_repeats=args.perm_repeats,
        out_dir=(args.out_dir.strip() or None),
        overwrite=bool(args.overwrite),
    )

    print("[train_model] Training complete")
    print("  Dataset:", dataset_path)
    print("  Model:", result.manifest.model_name)
    print("  Feature set:", result.manifest.feature_set)
    print(
        "  CV RMSE:",
        f"{result.manifest.metrics.get('rmse_mean', float('nan')):.2f}",
        "+/-",
        f"{result.manifest.metrics.get('rmse_std', float('nan')):.2f}",
        "ms",
    )
    print(
        "  CV R^2:",
        f"{result.manifest.metrics.get('r2_mean', float('nan')):.3f}",
        "+/-",
        f"{result.manifest.metrics.get('r2_std', float('nan')):.3f}",
    )
    print("  Model artifact:", result.model_path)
    print("  Manifest:", result.manifest_path)


if __name__ == "__main__":
    main()
