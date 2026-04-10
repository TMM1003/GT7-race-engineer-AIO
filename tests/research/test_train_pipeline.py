from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.research.model_artifacts import load_training_bundle
from src.research.train_pipeline import _select_training_frame, train_and_save_model


def _write_dataset(run_dir: Path) -> Path:
    rows = [
        {
            "loss_ms": 120.0,
            "lap_num": 1,
            "run_id": "run_alpha",
            "brake_start_delta_m": 1.0,
            "throttle_on_delta_m": -1.5,
            "min_speed_delta_kmh": 3.0,
            "exit_speed_delta_kmh": -2.0,
            "entry_speed_kmh": 140.0,
        },
        {
            "loss_ms": 95.0,
            "lap_num": 1,
            "run_id": "run_alpha",
            "brake_start_delta_m": 0.5,
            "throttle_on_delta_m": -1.0,
            "min_speed_delta_kmh": 2.5,
            "exit_speed_delta_kmh": -1.0,
            "entry_speed_kmh": 141.0,
        },
        {
            "loss_ms": 88.0,
            "lap_num": 2,
            "run_id": "run_alpha",
            "brake_start_delta_m": 0.2,
            "throttle_on_delta_m": -0.5,
            "min_speed_delta_kmh": 2.0,
            "exit_speed_delta_kmh": 0.0,
            "entry_speed_kmh": 142.0,
        },
        {
            "loss_ms": 70.0,
            "lap_num": 2,
            "run_id": "run_alpha",
            "brake_start_delta_m": -0.5,
            "throttle_on_delta_m": 0.2,
            "min_speed_delta_kmh": 1.0,
            "exit_speed_delta_kmh": 1.0,
            "entry_speed_kmh": 144.0,
        },
        {
            "loss_ms": 55.0,
            "lap_num": 3,
            "run_id": "run_alpha",
            "brake_start_delta_m": -1.0,
            "throttle_on_delta_m": 0.8,
            "min_speed_delta_kmh": 0.5,
            "exit_speed_delta_kmh": 2.0,
            "entry_speed_kmh": 145.0,
        },
        {
            "loss_ms": 40.0,
            "lap_num": 3,
            "run_id": "run_alpha",
            "brake_start_delta_m": -1.4,
            "throttle_on_delta_m": 1.2,
            "min_speed_delta_kmh": 0.1,
            "exit_speed_delta_kmh": 3.0,
            "entry_speed_kmh": 146.0,
        },
    ]

    dataset_path = run_dir / "corner_dataset.csv"
    with dataset_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    (run_dir / "run.json").write_text(
        '{"run_id":"test_run","schema_hash":"abc123","schema_version":1}',
        encoding="utf-8",
    )
    return dataset_path


class TrainPipelineTests(unittest.TestCase):
    def test_select_training_frame_normalizes_nullable_float_columns(self) -> None:
        df = pd.DataFrame(
            {
                "loss_ms": [120.0, 95.0, 88.0],
                "lap_num": [1, 1, 2],
                "brake_start_delta_m": pd.array(
                    [1.0, None, -0.5], dtype="Float64"
                ),
                "throttle_on_delta_m": [0.5, -1.0, 0.25],
                "min_speed_delta_kmh": [2.0, 1.5, 0.5],
                "exit_speed_delta_kmh": [0.0, -1.0, 1.0],
            }
        )

        X, y, feature_names = _select_training_frame(df, "heuristics")

        self.assertEqual(
            feature_names,
            [
                "brake_start_delta_m",
                "throttle_on_delta_m",
                "min_speed_delta_kmh",
                "exit_speed_delta_kmh",
            ],
        )
        self.assertTrue(all(str(dtype) == "float64" for dtype in X.dtypes))
        self.assertEqual(len(y), 3)
        self.assertTrue(pd.isna(X.loc[1, "brake_start_delta_m"]))

    def test_train_and_save_model_writes_reloadable_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            dataset_path = _write_dataset(run_dir)

            result = train_and_save_model(
                dataset_path=dataset_path,
                model_name="ridge",
                feature_mode="heuristics",
                n_splits=3,
                n_perm_repeats=1,
            )

            self.assertTrue(result.model_path.exists())
            self.assertTrue(result.manifest_path.exists())
            self.assertEqual(result.manifest.model_name, "ridge")
            self.assertEqual(result.manifest.feature_set, "heuristics")
            self.assertEqual(result.manifest.source_run_id, "test_run")
            self.assertEqual(result.manifest.dataset_schema_hash, "abc123")

            bundle = load_training_bundle(result.model_path)
            preds = bundle.predict_rows(
                [
                    {
                        "brake_start_delta_m": 0.0,
                        "throttle_on_delta_m": 0.0,
                        "min_speed_delta_kmh": 1.0,
                        "exit_speed_delta_kmh": 1.0,
                    }
                ]
            )
            self.assertEqual(len(preds), 1)


if __name__ == "__main__":
    unittest.main()
