# src/research/formatting.py
from __future__ import annotations

from pathlib import Path


def lap_stem(lap_num: int) -> str:
    return f"lap_{lap_num:04d}"


def ensure_dirs(run_dir: Path) -> None:
    (run_dir / "laps").mkdir(parents=True, exist_ok=True)
    (run_dir / "corners").mkdir(parents=True, exist_ok=True)
    (run_dir / "baselines").mkdir(parents=True, exist_ok=True)
