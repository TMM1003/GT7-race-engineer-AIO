# src/core/telemetry_session.py
from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Deque, Dict, Any, Optional, List
import time


@dataclass
class TelemetrySample:
    t: float
    lap: int
    total_laps: int
    speed_kmh: float
    rpm: float
    throttle: float
    brake: float
    gear: int
    fuel: float
    fuel_capacity: float
    x: float
    z: float
    in_race: bool
    paused: bool
    raw: Dict[str, Any]


class TelemetrySession:
    """
    Stores a rolling history of samples for plotting + per-lap polylines for track map.
    This version is fed from AppController's 10 Hz tick via snapshot().

    If later you want full 60 Hz fidelity, we can feed this directly inside GT7Communication.
    """

    def __init__(self, max_samples: int = 6000):
        self._samples: Deque[TelemetrySample] = deque(maxlen=max_samples)

        # Lap storage: list of laps, each lap is a list of (x,z) points
        self._lap_lines: List[List[tuple[float, float]]] = []
        self._current_lap_points: List[tuple[float, float]] = []
        self._last_lap_num: Optional[int] = None

        self._last_snapshot: Dict[str, Any] = {}

    def update_from_snapshot(self, snap: Dict[str, Any]) -> None:
        self._last_snapshot = dict(snap)

        # Pull fields with safe defaults
        t = time.time()
        lap = int(snap.get("lap") or 0)
        total_laps = int(snap.get("total_laps") or 0)
        speed = float(snap.get("speed_kmh") or 0.0)
        rpm = float(snap.get("rpm") or 0.0)
        throttle = float(snap.get("throttle") or 0.0)
        brake = float(snap.get("brake") or 0.0)

        # If gear isn't in your snapshot yet, default to 0 and we can add it later
        gear = int(snap.get("gear") or snap.get("current_gear") or 0)

        fuel = float(snap.get("fuel") or 0.0)
        fuel_capacity = float(snap.get("fuel_capacity") or 0.0)

        # If x/z aren't in snapshot yet, they'll be 0 until we add them
        x = float(snap.get("position_x") or snap.get("x") or 0.0)
        z = float(snap.get("position_z") or snap.get("z") or 0.0)

        in_race = bool(snap.get("in_race") or False)
        paused = bool(snap.get("paused") or False)

        sample = TelemetrySample(
            t=t,
            lap=lap,
            total_laps=total_laps,
            speed_kmh=speed,
            rpm=rpm,
            throttle=throttle,
            brake=brake,
            gear=gear,
            fuel=fuel,
            fuel_capacity=fuel_capacity,
            x=x,
            z=z,
            in_race=in_race,
            paused=paused,
            raw=dict(snap),
        )
        self._samples.append(sample)

        # Track map lap segmentation: close lap when lap number changes (and lap>0)
        if self._last_lap_num is None:
            self._last_lap_num = lap

        if lap != self._last_lap_num and self._current_lap_points:
            # Finish previous lap line
            self._lap_lines.append(self._current_lap_points)
            self._current_lap_points = []
            self._last_lap_num = lap

        # Only collect track points when we have meaningful coordinates
        if abs(x) > 1e-6 or abs(z) > 1e-6:
            self._current_lap_points.append((x, z))

    def latest_snapshot(self) -> Dict[str, Any]:
        return self._last_snapshot

    def samples(self) -> List[TelemetrySample]:
        return list(self._samples)

    def lap_lines(self) -> List[List[tuple[float, float]]]:
        # Include current lap as last line for drawing
        lines = list(self._lap_lines)
        if self._current_lap_points:
            lines.append(list(self._current_lap_points))
        return lines
