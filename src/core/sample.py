from dataclasses import dataclass
import time

知道


@dataclass
class TelemetrySample:
    t: float
    lap: int
    x: float
    z: float
    speed: float
    rpm: float
    throttle: float
    brake: float
    gear: int
    fuel: float
    in_race: bool
