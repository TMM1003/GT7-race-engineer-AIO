# src/core/telemetry_session.py
from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Deque, Dict, Any, Optional, List, Tuple
import time
import math


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


@dataclass
class LapData:
    lap_num: int
    samples: List[TelemetrySample]           # raw samples (10 Hz in your current architecture)
    points_xz: List[Tuple[float, float]]     # extracted (x,z)
    cum_dist_m: List[float]                  # cumulative distance along points (meters, if GT7 units are meters)
    lap_time_ms: int                         # from snapshot last_lap_ms at lap change, if available
    start_gate: Optional[Tuple[Tuple[float, float], Tuple[float, float]]]  # ((x1,z1),(x2,z2)) line segment


def _dist2d(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dz = a[1] - b[1]
    return math.hypot(dx, dz)


def _cumdist(points: List[Tuple[float, float]]) -> List[float]:
    if not points:
        return []
    out = [0.0]
    for i in range(1, len(points)):
        out.append(out[-1] + _dist2d(points[i - 1], points[i]))
    return out


def _make_start_gate(points: List[Tuple[float, float]]) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """
    Build a start/finish 'gate' line segment:
    - use first point as center
    - estimate forward direction from early points
    - gate is perpendicular to direction
    """
    if len(points) < 6:
        return None

    p0 = points[0]
    # direction = p5 - p0 (robust-ish)
    vx = points[5][0] - p0[0]
    vz = points[5][1] - p0[1]
    norm = math.hypot(vx, vz)
    if norm < 1e-6:
        return None
    vx /= norm
    vz /= norm

    # perpendicular (normal) for gate line: (-vz, vx)
    nx, nz = (-vz, vx)

    # gate half-length: arbitrary but stable; based on early spread
    # If this is too short/long, we can adapt later.
    half = 20.0  # "meters" scale-ish; good first pass

    a = (p0[0] - nx * half, p0[1] - nz * half)
    b = (p0[0] + nx * half, p0[1] + nz * half)
    return (a, b)


def _resample_by_distance(
    points: List[Tuple[float, float]],
    cumdist: List[float],
    n: int = 300,
) -> List[Tuple[float, float]]:
    """
    Resample polyline to N points evenly spaced in distance.
    Linear interpolation between vertices.
    """
    if not points or not cumdist or len(points) != len(cumdist):
        return []
    total = cumdist[-1]
    if total <= 1e-6:
        return [points[0]] * n

    targets = [total * (i / (n - 1)) for i in range(n)]
    out: List[Tuple[float, float]] = []
    j = 0
    for td in targets:
        while j + 1 < len(cumdist) and cumdist[j + 1] < td:
            j += 1
        if j + 1 >= len(cumdist):
            out.append(points[-1])
            continue
        d0 = cumdist[j]
        d1 = cumdist[j + 1]
        if d1 - d0 < 1e-9:
            out.append(points[j])
            continue
        alpha = (td - d0) / (d1 - d0)
        x = points[j][0] + alpha * (points[j + 1][0] - points[j][0])
        z = points[j][1] + alpha * (points[j + 1][1] - points[j][1])
        out.append((x, z))
    return out


def _resample_series_by_distance(
    series: List[float],
    cumdist: List[float],
    n: int = 300,
) -> List[float]:
    """
    Resample a scalar series aligned with points/cumdist to N by distance.
    """
    if not series or not cumdist or len(series) != len(cumdist):
        return []
    total = cumdist[-1]
    if total <= 1e-6:
        return [series[0]] * n

    targets = [total * (i / (n - 1)) for i in range(n)]
    out: List[float] = []
    j = 0
    for td in targets:
        while j + 1 < len(cumdist) and cumdist[j + 1] < td:
            j += 1
        if j + 1 >= len(cumdist):
            out.append(series[-1])
            continue
        d0 = cumdist[j]
        d1 = cumdist[j + 1]
        if d1 - d0 < 1e-9:
            out.append(series[j])
            continue
        alpha = (td - d0) / (d1 - d0)
        v = series[j] + alpha * (series[j + 1] - series[j])
        out.append(v)
    return out


class TelemetrySession:
    """
    Rolling history + per-lap storage + derived lap distance axis.

    This is fed at ~10 Hz by AppController._tick via snapshot().
    """

    def __init__(self, max_samples: int = 6000):
        self._samples: Deque[TelemetrySample] = deque(maxlen=max_samples)

        self._completed_laps: List[LapData] = []
        self._current_lap_samples: List[TelemetrySample] = []
        self._last_lap_num: Optional[int] = None

        self._last_snapshot: Dict[str, Any] = {}

        # crude session reset detection
        self._last_time_on_track_s: Optional[int] = None
        self._session_id: int = 0

        # cached auto-reference lap index
        self._reference_idx: Optional[int] = None

        # robust pause/freeze detection
        self._last_pos: Optional[Tuple[float, float]] = None
        self._last_moving_t: Optional[float] = None

    #public API
    def latest_snapshot(self) -> Dict[str, Any]:
        return self._last_snapshot

    def samples(self) -> List[TelemetrySample]:
        return list(self._samples)

    def completed_laps(self) -> List[LapData]:
        return list(self._completed_laps)

    def current_lap_points(self) -> List[Tuple[float, float]]:
        return [(s.x, s.z) for s in self._current_lap_samples if (abs(s.x) > 1e-6 or abs(s.z) > 1e-6)]

    def session_id(self) -> int:
        return self._session_id

    def reference_lap(self) -> Optional[LapData]:
        self._ensure_reference()
        if self._reference_idx is None:
            return None
        if 0 <= self._reference_idx < len(self._completed_laps):
            return self._completed_laps[self._reference_idx]
        return None

    def set_reference_by_lap_num(self, lap_num: int) -> None:
        for i, lap in enumerate(self._completed_laps):
            if lap.lap_num == lap_num:
                self._reference_idx = i
                return

    def sector_splits_m(self, lap: LapData) -> Tuple[float, float]:
        """Synthetic thirds of lap distance."""
        total = lap.cum_dist_m[-1] if lap.cum_dist_m else 0.0
        return (total / 3.0, 2.0 * total / 3.0)

    def sector_times_ms(self, lap: LapData) -> Optional[Tuple[int, int, int]]:
        """
        Estimate sector times from sample timestamps + distance axis.
        Uses interpolation of time along distance.
        """
        pts = lap.points_xz
        if len(pts) < 2:
            return None
        # Build time series aligned with points using sample times
        # We take times from samples that contributed to points.
        # Since points are derived from samples 1:1 here, it aligns.
        ts = [s.t for s in lap.samples if (abs(s.x) > 1e-6 or abs(s.z) > 1e-6)]
        if len(ts) != len(lap.cum_dist_m):
            # fallback: cannot compute
            return None

        d1, d2 = self.sector_splits_m(lap)
        t0 = ts[0]
        t_at_d1 = _interp_time_at_distance(lap.cum_dist_m, ts, d1)
        t_at_d2 = _interp_time_at_distance(lap.cum_dist_m, ts, d2)
        t_end = ts[-1]

        s1 = int(round((t_at_d1 - t0) * 1000))
        s2 = int(round((t_at_d2 - t_at_d1) * 1000))
        s3 = int(round((t_end - t_at_d2) * 1000))
        return (max(s1, 0), max(s2, 0), max(s3, 0))

    def delta_profile_speed(self, last: LapData, ref: LapData, n: int = 300) -> Optional[List[float]]:
        """
        Compute speed delta (last - ref) aligned by lap distance, resampled to N points.
        """
        if not last.cum_dist_m or not ref.cum_dist_m:
            return None

        last_speeds = [s.speed_kmh for s in last.samples if (abs(s.x) > 1e-6 or abs(s.z) > 1e-6)]
        ref_speeds = [s.speed_kmh for s in ref.samples if (abs(s.x) > 1e-6 or abs(s.z) > 1e-6)]

        if len(last_speeds) != len(last.cum_dist_m) or len(ref_speeds) != len(ref.cum_dist_m):
            return None

        last_r = _resample_series_by_distance(last_speeds, last.cum_dist_m, n=n)
        ref_r = _resample_series_by_distance(ref_speeds, ref.cum_dist_m, n=n)
        if not last_r or not ref_r or len(last_r) != len(ref_r):
            return None
        return [last_r[i] - ref_r[i] for i in range(n)]

    def delta_profile_time_ms(self, last: LapData, ref: LapData, n: int = 300) -> Optional[List[float]]:
        """
        Compute time delta (last - ref) aligned by lap distance, resampled to N points.
        Returns list of delta in milliseconds for each resampled distance bin.
        """
        if not last.cum_dist_m or not ref.cum_dist_m:
            return None

        # timestamps aligned to points (we filtered coords when building LapData)
        last_ts = [s.t for s in last.samples if (abs(s.x) > 1e-6 or abs(s.z) > 1e-6)]
        ref_ts = [s.t for s in ref.samples if (abs(s.x) > 1e-6 or abs(s.z) > 1e-6)]

        if len(last_ts) != len(last.cum_dist_m) or len(ref_ts) != len(ref.cum_dist_m):
            return None
        # convert to "elapsed since lap start"
        last_t0 = last_ts[0]
        ref_t0 = ref_ts[0]
        last_elapsed = [t - last_t0 for t in last_ts]
        ref_elapsed = [t - ref_t0 for t in ref_ts]

        last_r = _resample_series_by_distance(last_elapsed, last.cum_dist_m, n=n)
        ref_r = _resample_series_by_distance(ref_elapsed, ref.cum_dist_m, n=n)
        if not last_r or not ref_r or len(last_r) != len(ref_r):
            return None

        # seconds -> milliseconds
        return [(last_r[i] - ref_r[i]) * 1000.0 for i in range(n)]

    #main update 
    def update_from_snapshot(self, snap: Dict[str, Any]) -> None:
        self._last_snapshot = dict(snap)

        # session reset detection (time_on_track decreasing implies a new session or restart)
        tot = snap.get("time_on_track_s")
        tot_s = int(tot) if isinstance(tot, (int, float)) else None
        if tot_s is not None:
            if self._last_time_on_track_s is not None and tot_s + 2 < self._last_time_on_track_s:
                self._reset_session()
            self._last_time_on_track_s = tot_s

        # Pull fields with safe defaults
        t = time.time()
        lap = int(snap.get("lap") or 0)
        total_laps = int(snap.get("total_laps") or 0)
        speed = float(snap.get("speed_kmh") or 0.0)
        rpm = float(snap.get("rpm") or 0.0)
        throttle = float(snap.get("throttle") or 0.0)
        brake = float(snap.get("brake") or 0.0)
        gear = int(snap.get("gear") or snap.get("current_gear") or 0)
        fuel = float(snap.get("fuel") or 0.0)
        fuel_capacity = float(snap.get("fuel_capacity") or 0.0)
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

        # initialize
        if self._last_lap_num is None:
            self._last_lap_num = lap

        # lap transition: finalize previous lap
        if lap != self._last_lap_num:
            self._finalize_current_lap(on_lap_change_snapshot=snap)
            self._current_lap_samples = []
            self._last_lap_num = lap


        coords_ok = (abs(x) > 1e-6 or abs(z) > 1e-6)
        # Determine "paused" robustly (flag OR freeze heuristic)
        snap_paused = bool(snap.get("paused") or False)
        effective_paused = self._effective_paused(
            snap_paused=snap_paused,
            x=x,
            z=z,
            speed_kmh=speed,
            throttle=throttle,
            brake=brake,
            now=t,
        )

        # Only append lap-geometry samples when we are actively running
        # If in_race is reliable, this prevents menu/staging pollution.
        collect_ok = (not effective_paused) and coords_ok
        if in_race:
            collect_ok = collect_ok and (not paused)

        if collect_ok:
            self._current_lap_samples.append(sample)


    #internals
    def _reset_session(self) -> None:
        self._session_id += 1
        self._completed_laps.clear()
        self._current_lap_samples.clear()
        self._last_lap_num = None
        self._reference_idx = None

        # reset pause/freeze heuristic state
        self._last_pos = None
        self._last_moving_t = None


    def _finalize_current_lap(self, on_lap_change_snapshot: Dict[str, Any]) -> None:
        if len(self._current_lap_samples) < 10:
            return

        points = [(s.x, s.z) for s in self._current_lap_samples if (abs(s.x) > 1e-6 or abs(s.z) > 1e-6)]
        if len(points) < 10:
            return

        cum = _cumdist(points)
        lap_num = int(self._current_lap_samples[0].lap or 0)

        # last_lap_ms in the snapshot at lap change should correspond to the lap that just ended
        lap_time_ms = int(on_lap_change_snapshot.get("last_lap_ms") or 0)

        gate = _make_start_gate(points)

        lap = LapData(
            lap_num=lap_num,
            samples=list(self._current_lap_samples),
            points_xz=points,
            cum_dist_m=cum,
            lap_time_ms=lap_time_ms,
            start_gate=gate,
        )
        self._completed_laps.append(lap)

        # invalidate reference cache (new best might appear)
        self._ensure_reference(force=True)

    def _ensure_reference(self, force: bool = False) -> None:
        if self._reference_idx is not None and not force:
            return
        if not self._completed_laps:
            self._reference_idx = None
            return

        # Choose best lap by lap_time_ms if available, else choose longest/most complete (largest cumdist)
        best_i: Optional[int] = None
        best_time: Optional[int] = None

        for i, lap in enumerate(self._completed_laps):
            if lap.lap_time_ms and lap.lap_time_ms > 0:
                if best_time is None or lap.lap_time_ms < best_time:
                    best_time = lap.lap_time_ms
                    best_i = i

        if best_i is not None:
            self._reference_idx = best_i
            return

        # fallback: most distance (in case times not coming through)
        best_i = max(
            range(len(self._completed_laps)),
            key=lambda j: (self._completed_laps[j].cum_dist_m[-1] if self._completed_laps[j].cum_dist_m else 0.0),
        )
        self._reference_idx = best_i

        
    def _effective_paused(
        self,
        snap_paused: bool,
        x: float,
        z: float,
        speed_kmh: float,
        throttle: float,
        brake: float,
        now: float,
    ) -> bool:
        """
        Returns True when we should pause lap-geometry collection.

        Uses BOTH:
        - snapshot paused flag (fast path)
        - heuristic freeze detection (works even if flag decode is imperfect)

        Heuristic: treat as "paused/frozen" if position is stable AND controls are idle AND speed is low
        continuously for >0.7s.
        """

        # Initialize moving timer so heuristic works even if we start while paused/idle.
        if self._last_moving_t is None:
            self._last_moving_t = now

        #position stability
        pos = (x, z)
        pos_stable = False
        if self._last_pos is not None:
            dx = pos[0] - self._last_pos[0]
            dz = pos[1] - self._last_pos[1]
            # threshold is in "coord units"; tune later if needed
            pos_stable = (dx * dx + dz * dz) < 0.01  # ~0.1 units
        self._last_pos = pos

        #controls/speed idle
        controls_idle = (throttle < 0.5 and brake < 0.5)
        speed_idle = (speed_kmh < 1.0)

        # Update last moving time whenever we appear to be moving/active.
        if not (pos_stable and controls_idle and speed_idle):
            self._last_moving_t = now

        heuristic_paused = (now - self._last_moving_t) > 0.7
        
        return bool(snap_paused) or heuristic_paused



def _interp_time_at_distance(cumdist: List[float], ts: List[float], target_d: float) -> float:
    """
    Interpolate time at target distance along lap.
    """
    if not cumdist or not ts or len(cumdist) != len(ts):
        return ts[-1] if ts else 0.0
    if target_d <= 0:
        return ts[0]
    if target_d >= cumdist[-1]:
        return ts[-1]

    j = 0
    while j + 1 < len(cumdist) and cumdist[j + 1] < target_d:
        j += 1
    d0 = cumdist[j]
    d1 = cumdist[j + 1]
    t0 = ts[j]
    t1 = ts[j + 1]
    if d1 - d0 < 1e-9:
        return t0
    a = (target_d - d0) / (d1 - d0)
    return t0 + a * (t1 - t0)
