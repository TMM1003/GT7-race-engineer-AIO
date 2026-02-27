from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from src.core.race_state import RaceState, ms_to_laptime


@dataclass
class EngineerEvent:
    id: str
    title: str
    speech: str
    should_speak: bool = True


class EventEngine:
    def __init__(self):
        self._prev_last_lap_ms: int = 0
        self._prev_bucket: Optional[int] = None

    def consume(self, state: RaceState) -> List[EngineerEvent]:
        events: List[EngineerEvent] = []

        if state.connected and state.lap > 0:
            if (
                state.last_lap_ms
                and state.last_lap_ms != self._prev_last_lap_ms
            ):
                lap_completed = max(state.lap - 1, 0)
                lt = ms_to_laptime(state.last_lap_ms)
                fuel_pct = (
                    int(round(state.fuel_pct))
                    if state.fuel_capacity > 0
                    else None
                )
                speech = (
                    f"Lap {lap_completed}. {lt}."
                    if fuel_pct is None
                    else f"Lap {lap_completed}. {lt}. Fuel {fuel_pct} percent."
                )
                events.append(
                    EngineerEvent(
                        id=f"lap:{lap_completed}:{state.last_lap_ms}",
                        title=f"Lap {lap_completed} complete",
                        speech=speech,
                        should_speak=True,
                    )
                )
            self._prev_last_lap_ms = state.last_lap_ms

        if state.fuel_capacity > 0:
            pct = state.fuel_pct
            bucket = 100
            if pct <= 10:
                bucket = 10
            elif pct <= 25:
                bucket = 25
            elif pct <= 50:
                bucket = 50

            if self._prev_bucket is None:
                self._prev_bucket = bucket
            elif bucket != self._prev_bucket:
                if bucket < self._prev_bucket:
                    events.append(
                        EngineerEvent(
                            id=f"fuel:{bucket}",
                            title="Fuel warning",
                            speech=f"Fuel at {bucket} percent.",
                            should_speak=True,
                        )
                    )
                self._prev_bucket = bucket

        return events
