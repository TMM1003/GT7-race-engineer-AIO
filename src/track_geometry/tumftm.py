from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable
from urllib.request import urlopen

from src.paths import resource_path

from .alignment import Point2, TrackGeometry


REPOSITORY_URL = "https://github.com/TUMFTM/racetrack-database"
RAW_BASE_URL = (
    "https://raw.githubusercontent.com/TUMFTM/"
    "racetrack-database/master"
)
DEFAULT_CACHE_ROOT = resource_path("trackdb")

SUPPORTED_TRACKDB_TRACKS = (
    "Brands Hatch",
    "Circuit de Barcelona-Catalunya",
    "Circuit Gilles-Villeneuve",
    "Autodromo Nazionale Monza",
    "Nurburgring GP",
    "Autodromo de Interlagos",
    "Circuit de Spa-Francorchamps",
    "Red Bull Ring",
    "Suzuka Circuit",
    "Yas Marina Circuit",
)

_TRACK_ALIASES = {
    "autodromo de interlagos": "SaoPaulo",
    "autodromo jose carlos pace": "SaoPaulo",
    "autodromo nazionale monza": "Monza",
    "barcelona": "Catalunya",
    "barcelona catalunya": "Catalunya",
    "brands hatch": "BrandsHatch",
    "brands hatch grand prix": "BrandsHatch",
    "brands hatch grand prix circuit": "BrandsHatch",
    "brands hatch gp": "BrandsHatch",
    "catalunya": "Catalunya",
    "circuit de barcelona catalunya": "Catalunya",
    "circuit de barcelona catalunya grand prix layout": "Catalunya",
    "circuit de catalunya": "Catalunya",
    "circuit de gilles villeneuve": "Montreal",
    "circuit de spa francorchamps": "Spa",
    "circuit de spa-francorchamps": "Spa",
    "circuit gilles villeneuve": "Montreal",
    "gilles villeneuve": "Montreal",
    "interlagos": "SaoPaulo",
    "monza": "Monza",
    "montreal": "Montreal",
    "nuerburgring gp": "Nuerburgring",
    "nurburgring gp": "Nuerburgring",
    "nurburgring grand prix": "Nuerburgring",
    "nürburgring gp": "Nuerburgring",
    "red bull ring": "Spielberg",
    "sao paulo": "SaoPaulo",
    "spa": "Spa",
    "spa francorchamps": "Spa",
    "spa-francorchamps": "Spa",
    "spielberg": "Spielberg",
    "suzuka": "Suzuka",
    "suzuka circuit": "Suzuka",
    "yas marina": "YasMarina",
    "yas marina circuit": "YasMarina",
}

_UNSUPPORTED_LAYOUT_PATTERNS = (
    "24h",
    "east course",
    "endurance",
    "horse thief",
    "indy",
    "national",
    "no chicane",
    "nordschleife",
    "rallycross",
    "reverse",
    "short",
    "sprint",
    "tourist",
)


def canonical_track_key(track_name: str | None) -> str | None:
    raw = unicodedata.normalize(
        "NFKD", (track_name or "").lower()
    ).encode("ascii", "ignore").decode("ascii")
    key = re.sub(r"[^a-z0-9]+", " ", raw).strip()
    key = re.sub(r"\s+", " ", key)
    if any(pattern in key for pattern in _UNSUPPORTED_LAYOUT_PATTERNS):
        if key not in {
            "circuit de barcelona catalunya grand prix layout",
            "brands hatch grand prix",
            "brands hatch grand prix circuit",
        }:
            return None
    return _TRACK_ALIASES.get(key)


def ensure_tumftm_track_cached(
    track_name: str,
    *,
    cache_root: str | Path = DEFAULT_CACHE_ROOT,
    overwrite: bool = False,
) -> dict[str, Path]:
    key = canonical_track_key(track_name)
    if key is None:
        raise ValueError(f"No TUMFTM track mapping for: {track_name!r}")

    cache_root = Path(cache_root)
    paths = {
        "track": cache_root / "tracks" / f"{key}.csv",
        "raceline": cache_root / "racelines" / f"{key}.csv",
        "source": cache_root / "SOURCE.json",
        "license": cache_root / "LICENSE",
    }

    downloads = {
        "track": f"{RAW_BASE_URL}/tracks/{key}.csv",
        "raceline": f"{RAW_BASE_URL}/racelines/{key}.csv",
        "license": f"{RAW_BASE_URL}/LICENSE",
    }
    for kind, url in downloads.items():
        path = paths[kind]
        if path.exists() and not overwrite:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(url, timeout=30) as response:
            path.write_bytes(response.read())

    source_payload = {
        "repository": REPOSITORY_URL,
        "license": "LGPL-3.0",
        "files": {
            "tracks": downloads["track"],
            "racelines": downloads["raceline"],
            "license": downloads["license"],
        },
    }
    paths["source"].parent.mkdir(parents=True, exist_ok=True)
    paths["source"].write_text(
        json.dumps(source_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return paths


def load_tumftm_track(
    track_name: str,
    *,
    cache_root: str | Path = DEFAULT_CACHE_ROOT,
    allow_download: bool = False,
) -> TrackGeometry:
    key = canonical_track_key(track_name)
    if key is None:
        raise ValueError(f"No TUMFTM track mapping for: {track_name!r}")

    cache_root = Path(cache_root)
    track_path = cache_root / "tracks" / f"{key}.csv"
    raceline_path = cache_root / "racelines" / f"{key}.csv"
    if allow_download and (not track_path.exists() or not raceline_path.exists()):
        ensure_tumftm_track_cached(track_name, cache_root=cache_root)

    if not track_path.exists() or not raceline_path.exists():
        raise FileNotFoundError(
            "TUMFTM track CSVs are not cached. Run "
            "`python scripts/align_trackdb_to_gt7.py --cache-only` "
            "or call with allow_download=True. The default cache root is "
            f"`{cache_root}`."
        )

    track_rows = _read_numeric_csv(track_path)
    raceline_rows = _read_numeric_csv(raceline_path)
    centerline: list[Point2] = []
    width_right: list[float] = []
    width_left: list[float] = []

    for row in track_rows:
        if len(row) < 4:
            continue
        centerline.append((float(row[0]), float(row[1])))
        width_right.append(float(row[2]))
        width_left.append(float(row[3]))

    raceline = [
        (float(row[0]), float(row[1]))
        for row in raceline_rows
        if len(row) >= 2
    ]
    if len(centerline) < 10 or len(raceline) < 10:
        raise ValueError(f"TUMFTM {key} CSVs did not contain enough points.")

    return TrackGeometry(
        name=key,
        centerline=tuple(centerline),
        width_right_m=tuple(width_right),
        width_left_m=tuple(width_left),
        raceline=tuple(raceline),
        source=REPOSITORY_URL,
    )


def _read_numeric_csv(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for raw_row in csv.reader(f):
            row = list(_numeric_cells(raw_row))
            if row:
                rows.append(row)
    return rows


def _numeric_cells(cells: Iterable[str]) -> Iterable[float]:
    for cell in cells:
        text = str(cell).strip()
        if not text or text.startswith("#"):
            continue
        try:
            yield float(text)
        except ValueError:
            continue
