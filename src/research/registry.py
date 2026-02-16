# src/research/registry.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import platform
import re
import subprocess
import time
import uuid
from typing import Any, Dict, Optional


def _utc_iso(ts: float | None = None) -> str:
    if ts is None:
        ts = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _git_commit_short() -> Optional[str]:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
        s = out.decode("utf-8", "ignore").strip()
        return s or None
    except Exception:
        return None


def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


@dataclass(frozen=True)
class RunRegistry:
    run_id: str
    run_dir: Path
    created_utc: str
    meta: Dict[str, Any]


def create_run(output_root: str, run_alias: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> RunRegistry:
    """
    Creates:
      <output_root>/<run_id>/
        run.json
        laps/
        corners/
        baselines/
    """
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%d_%H%M%S")
    alias = _slug(run_alias or "")
    if alias:
        run_id = f"{ts}_{alias}"
    else:
        run_id = f"{ts}_{uuid.uuid4().hex[:8]}"

    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Standard subdirs
    (run_dir / "laps").mkdir(exist_ok=True)
    (run_dir / "corners").mkdir(exist_ok=True)
    (run_dir / "baselines").mkdir(exist_ok=True)

    meta: Dict[str, Any] = {
        "run_id": run_id,
        "created_utc": _utc_iso(),
        "run_alias": (run_alias or None),
        "git_commit": _git_commit_short(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "hostname": platform.node(),
        "env": {
            "RESEARCH_ENABLED": os.getenv("RESEARCH_ENABLED"),
            "RESEARCH_N_BINS": os.getenv("RESEARCH_N_BINS"),
            "RESEARCH_OUTPUT_ROOT": os.getenv("RESEARCH_OUTPUT_ROOT"),
        },
    }

    if metadata:
        meta.update(metadata)

    with (run_dir / "run.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, sort_keys=True)

    return RunRegistry(run_id=run_id, run_dir=run_dir, created_utc=meta["created_utc"], meta=meta)