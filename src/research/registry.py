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
from datetime import datetime
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
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _make_run_id(*, run_alias: Optional[str], run_tag: Optional[str]) -> str:
    base = run_alias or run_tag or "run"
    base = _slug(base) or "run"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base}__{ts}"


def _ensure_unique_dir(root: Path, run_id: str) -> Path:
    candidate = root / run_id
    if not candidate.exists():
        return candidate

    i = 1
    while True:
        alt = root / f"{run_id}__{i:02d}"
        if not alt.exists():
            return alt
        i += 1


@dataclass(frozen=True)
class RunRegistry:
    run_id: str
    run_dir: Path
    created_utc: str
    meta: Dict[str, Any]


def create_run(
    output_root: str,
    run_alias: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> RunRegistry:
    """
    Creates:
      <output_root>/<run_id>/
        run.json
        laps/
        corners/
        baselines/
        manifest.json

    Folder naming scheme:
      <run_alias-or-run_tag-or-run>__YYYYMMDD_HHMMSS[__NN]

    Compatibility:
      - Older callers may still pass run_tag and/or extra_meta.
      - Newer callers should pass run_alias + metadata.
    """
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    # Merge metadata sources in a stable precedence order.
    # Highest priority: metadata (new API), then extra_meta (legacy API).
    merged_meta: Dict[str, Any] = {}
    if extra_meta:
        merged_meta.update(dict(extra_meta))
    if metadata:
        merged_meta.update(dict(metadata))

    # If run_alias not provided explicitly, allow it to be derived from merged metadata.
    if run_alias is None:
        run_alias = merged_meta.get("run_alias")

    desired_run_id = _make_run_id(run_alias=run_alias, run_tag=run_tag)
    run_dir = _ensure_unique_dir(root, desired_run_id)

    run_id = run_dir.name
    run_dir.mkdir(parents=True, exist_ok=False)

    # Standard subdirs
    (run_dir / "laps").mkdir(exist_ok=True)
    (run_dir / "corners").mkdir(exist_ok=True)
    (run_dir / "baselines").mkdir(exist_ok=True)

    meta: Dict[str, Any] = {
        "run_id": run_id,
        "created_utc": _utc_iso(),
        "run_alias": run_alias,
        "git_commit": _git_commit_short(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "hostname": platform.node(),
        "env": {
            "RESEARCH_ENABLED": os.getenv("RESEARCH_ENABLED"),
            "RESEARCH_N_BINS": os.getenv("RESEARCH_N_BINS"),
            "RESEARCH_OUTPUT_ROOT": os.getenv("RESEARCH_OUTPUT_ROOT"),
        },
        # Reference selection is session-derived but we persist a header slot here
        "reference_locked": False,
        "reference_lap_num": None,
        "reference_lap_time_ms": None,
    }

    # Overlay merged metadata (track/car/notes/feature_spec/schema version/hash/etc.)
    meta.update(merged_meta)

    with (run_dir / "run.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, sort_keys=True)

    # Initialize manifest
    manifest = {
        "run_id": run_id,
        "created_utc": meta["created_utc"],
        "updated_utc": meta["created_utc"],
        "laps": [],
        "baselines": [],
        "corners": [],
        "dataset_builds": [],
    }
    with (run_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    return RunRegistry(run_id=run_id, run_dir=run_dir, created_utc=meta["created_utc"], meta=meta)
