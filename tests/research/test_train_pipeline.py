from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from src.research.model_artifacts import load_training_bundle
from src.research.train_pipeline import train_and_save_model


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
