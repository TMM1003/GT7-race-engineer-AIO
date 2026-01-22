from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any


def ms_to_laptime(ms: int) -> str:
    if not ms or ms < 0:
        return "--:--.---"
    total_s = ms / 1000.0
    m = int(total_s // 60)
    s = total_s - (m * 60)
    return f"{m}:{s:06.3f}"


@dataclass
class RaceState:
    connected: bool = False
    ip: Optional[str] = None

    lap: int = 0
    total_laps: int = 0
    speed_kmh: float = 0.0
    rpm: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0
    fuel: float = 0.0
    fuel_capacity: float = 0.0
    in_race: Optional[bool] = None
    paused: Optional[bool] = None

    best_lap_ms: int = 0
    last_lap_ms: int = 0

    fuel_pct: float = 0.0

    def update(self, snap: Dict[str, Any]) -> None:
        self.connected = bool(snap.get("connected", False))
        self.ip = snap.get("ip")

        self.lap = int(snap.get("lap") or 0)
        self.total_laps = int(snap.get("total_laps") or 0)

        self.speed_kmh = float(snap.get("speed_kmh") or 0.0)
        self.rpm = float(snap.get("rpm") or 0.0)
        self.throttle = float(snap.get("throttle") or 0.0)
        self.brake = float(snap.get("brake") or 0.0)

        self.fuel = float(snap.get("fuel") or 0.0)
        self.fuel_capacity = float(snap.get("fuel_capacity") or 0.0)

        self.in_race = snap.get("in_race")
        self.paused = snap.get("paused")

        self.best_lap_ms = int(snap.get("best_lap_ms") or 0)
        self.last_lap_ms = int(snap.get("last_lap_ms") or 0)

        self.fuel_pct = (self.fuel / self.fuel_capacity * 100.0) if self.fuel_capacity > 0 else 0.0

    @property
    def best_lap_str(self) -> str:
        return ms_to_laptime(self.best_lap_ms)

    @property
    def last_lap_str(self) -> str:
        return ms_to_laptime(self.last_lap_ms)

    def format_snapshot_for_speech(self, snap: Dict[str, Any]) -> str:
        lap = snap.get("lap") or 0
        spd = snap.get("speed_kmh") or 0.0
        rpm = snap.get("rpm") or 0.0
        fuel = snap.get("fuel")
        if fuel is None:
            return f"Lap {lap}. Speed {int(spd)}. RPM {int(rpm)}."
        return f"Lap {lap}. Speed {int(spd)}. RPM {int(rpm)}. Fuel {fuel:.1f}."
