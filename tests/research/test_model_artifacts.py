from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.research.inference import load_model_if_present, predict_corner_rows
from src.research.train_pipeline import train_and_save_model


def _write_dataset(run_dir: Path) -> Path:
    rows = [
        {
            "loss_ms": 110.0,
            "lap_num": 1,
            "run_id": "run_beta",
            "brake_start_delta_m": 1.2,
            "throttle_on_delta_m": -1.2,
            "min_speed_delta_kmh": 2.8,
            "exit_speed_delta_kmh": -1.5,
            "entry_speed_kmh": 139.0,
        },
        {
            "loss_ms": 92.0,
            "lap_num": 1,
            "run_id": "run_beta",
            "brake_start_delta_m": 0.8,
            "throttle_on_delta_m": -0.6,
            "min_speed_delta_kmh": 2.1,
            "exit_speed_delta_kmh": -0.8,
            "entry_speed_kmh": 141.0,
        },
        {
            "loss_ms": 76.0,
            "lap_num": 2,
            "run_id": "run_beta",
            "brake_start_delta_m": 0.1,
            "throttle_on_delta_m": 0.1,
            "min_speed_delta_kmh": 1.2,
            "exit_speed_delta_kmh": 0.5,
            "entry_speed_kmh": 144.0,
        },
        {
            "loss_ms": 63.0,
            "lap_num": 2,
            "run_id": "run_beta",
            "brake_start_delta_m": -0.4,
            "throttle_on_delta_m": 0.4,
            "min_speed_delta_kmh": 0.8,
            "exit_speed_delta_kmh": 1.1,
            "entry_speed_kmh": 145.0,
        },
        {
            "loss_ms": 48.0,
            "lap_num": 3,
            "run_id": "run_beta",
            "brake_start_delta_m": -0.9,
            "throttle_on_delta_m": 1.0,
            "min_speed_delta_kmh": 0.3,
            "exit_speed_delta_kmh": 2.0,
            "entry_speed_kmh": 147.0,
        },
        {
            "loss_ms": 34.0,
            "lap_num": 3,
            "run_id": "run_beta",
            "brake_start_delta_m": -1.3,
            "throttle_on_delta_m": 1.4,
            "min_speed_delta_kmh": 0.0,
            "exit_speed_delta_kmh": 2.9,
            "entry_speed_kmh": 148.0,
        },
    ]

    dataset_path = run_dir / "corner_dataset.csv"
    with dataset_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    (run_dir / "run.json").write_text(
        '{"run_id":"artifact_run","schema_hash":"def456","schema_version":1}',
        encoding="utf-8",
    )
    return dataset_path


class ModelArtifactTests(unittest.TestCase):
    def test_loaded_bundle_predicts_dataframe_and_corner_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            dataset_path = _write_dataset(run_dir)

            result = train_and_save_model(
                dataset_path=dataset_path,
                model_name="rf",
                feature_mode="all_numeric",
                n_splits=3,
                n_perm_repeats=1,
            )

            bundle = load_model_if_present(result.model_path)
            assert bundle is not None

            frame = pd.DataFrame(
                [
                    {
                        "lap_num": 4,
                        "brake_start_delta_m": -0.7,
                        "throttle_on_delta_m": 0.7,
                        "min_speed_delta_kmh": 0.5,
                        "exit_speed_delta_kmh": 1.7,
                        "entry_speed_kmh": 146.5,
                    }
                ]
            )
            preds = bundle.predict_dataframe(frame)
            self.assertEqual(len(preds), 1)

            info = predict_corner_rows(
                bundle,
                frame.to_dict(orient="records"),
            )
            self.assertIsNotNone(info)
            assert info is not None
            self.assertEqual(len(info.corner_predictions or []), 1)
            self.assertEqual(info.model_name, "rf")


if __name__ == "__main__":
    unittest.main()
