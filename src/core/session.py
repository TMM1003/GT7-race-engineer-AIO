# src/core/session.py
from .buffers import RingBuffer

# Legacy session buffer (pre TelemetrySession)
# Kept for backward compatibility and to avoid breaking imports


class Session:
    def __init__(self):
        self.live = RingBuffer()
        self.laps = []
        self.current_lap_samples = []
        self.current_lap = -1

    def add(self, sample):
        self.live.append(sample)

        if sample.lap != self.current_lap:
            if self.current_lap_samples:
                self.laps.append(self.current_lap_samples)
            self.current_lap_samples = []
            self.current_lap = sample.lap

        self.current_lap_samples.append(sample)
