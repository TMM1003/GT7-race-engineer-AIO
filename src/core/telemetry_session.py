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
    cum_dist_m: List[float]                  # cumulative distance along points
    lap_time_ms: int                         # from snapshot last_lap_ms at lap change, if available
    start_gate: Optional[Tuple[Tuple[float, float], Tuple[float, float]]]  # ((x1,z1),(x2,z2)) line segment


@dataclass
class CornerSegment:
    start_idx: int          # index into resampled arrays (0..n-1)
    end_idx: int            # inclusive
    direction: int          # -1 left, +1 right, 0 unknown
    strength: float         # avg curvature metric in the segment


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
    half = 20.0

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


def _wrap_pi(a: float) -> float:
    """Wrap angle to [-pi, pi]."""
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def _moving_average(xs: List[float], w: int) -> List[float]:
    if not xs or w <= 1:
        return xs
    w = min(w, len(xs))
    out = [0.0] * len(xs)
    s = 0.0
    q = deque()
    for i, v in enumerate(xs):
        q.append(v)
        s += v
        if len(q) > w:
            s -= q.popleft()
        out[i] = s / len(q)
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

    # public API
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

        ts = [s.t for s in lap.samples if (abs(s.x) > 1e-6 or abs(s.z) > 1e-6)]
        if len(ts) != len(lap.cum_dist_m):
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

        last_ts = [s.t for s in last.samples if (abs(s.x) > 1e-6 or abs(s.z) > 1e-6)]
        ref_ts = [s.t for s in ref.samples if (abs(s.x) > 1e-6 or abs(s.z) > 1e-6)]

        if len(last_ts) != len(last.cum_dist_m) or len(ref_ts) != len(ref.cum_dist_m):
            return None

        last_t0 = last_ts[0]
        ref_t0 = ref_ts[0]
        last_elapsed = [t - last_t0 for t in last_ts]
        ref_elapsed = [t - ref_t0 for t in ref_ts]

        last_r = _resample_series_by_distance(last_elapsed, last.cum_dist_m, n=n)
        ref_r = _resample_series_by_distance(ref_elapsed, ref.cum_dist_m, n=n)
        if not last_r or not ref_r or len(last_r) != len(ref_r):
            return None

        return [(last_r[i] - ref_r[i]) * 1000.0 for i in range(n)]

    def corner_segments(
        self,
        ref: LapData,
        n: int = 300,
        curvature_thresh: float = 0.020,
        min_len: int = 6,
        max_gap: int = 2,
        smooth_w: int = 7,
    ) -> List[CornerSegment]:
        """
        Detect corner segments from the reference lap using a curvature proxy.
        """
        if not ref.points_xz or not ref.cum_dist_m or len(ref.points_xz) < 10:
            return []

        pts = _resample_by_distance(ref.points_xz, ref.cum_dist_m, n=n)
        if len(pts) < 10:
            return []

        headings: List[float] = []
        for i in range(1, len(pts)):
            dx = pts[i][0] - pts[i - 1][0]
            dz = pts[i][1] - pts[i - 1][1]
            headings.append(math.atan2(dz, dx))

        curv = [0.0] * n
        for i in range(1, len(headings)):
            curv[i] = _wrap_pi(headings[i] - headings[i - 1])

        curv_s = _moving_average(curv, smooth_w)
        strong = [abs(v) > curvature_thresh for v in curv_s]

        segs: List[CornerSegment] = []
        i = 0
        while i < n:
            if not strong[i]:
                i += 1
                continue

            start = i
            gaps = 0
            signed_sum = 0.0
            abs_sum = 0.0
            count = 0

            j = i
            while j < n:
                if strong[j]:
                    gaps = 0
                    signed_sum += curv_s[j]
                    abs_sum += abs(curv_s[j])
                    count += 1
                else:
                    gaps += 1
                    if gaps > max_gap:
                        break
                j += 1

            end = min(n - 1, j - gaps - 1)
            length = end - start + 1

            if length >= min_len and count > 0:
                avg_signed = signed_sum / count
                avg_abs = abs_sum / count
                direction = 1 if avg_signed > 0 else -1 if avg_signed < 0 else 0
                segs.append(CornerSegment(start, end, direction, avg_abs))

            i = j

        return segs

    def corner_time_losses_ms(
        self,
        last: LapData,
        ref: LapData,
        n: int = 300,
    ) -> Optional[List[Tuple[CornerSegment, float]]]:
        """
        Returns [(CornerSegment, loss_ms)] sorted by loss descending.
        loss_ms = Δt(exit) - Δt(entry) where Δt is (last - ref) in ms.
        """
        dt = self.delta_profile_time_ms(last, ref, n=n)
        if not dt or len(dt) != n:
            return None

        corners = self.corner_segments(ref, n=n)
        if not corners:
            return []

        out: List[Tuple[CornerSegment, float]] = []
        for seg in corners:
            a = max(0, min(n - 1, seg.start_idx))
            b = max(0, min(n - 1, seg.end_idx))
            if b > a:
                out.append((seg, float(dt[b] - dt[a])))

        out.sort(key=lambda x: x[1], reverse=True)
        return out

    # main update
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

        if self._last_lap_num is None:
            self._last_lap_num = lap

        # lap transition: finalize previous lap
        if lap != self._last_lap_num:
            self._finalize_current_lap(on_lap_change_snapshot=snap)
            self._current_lap_samples = []
            self._last_lap_num = lap

        coords_ok = (abs(x) > 1e-6 or abs(z) > 1e-6)

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

        collect_ok = (not effective_paused) and coords_ok
        if in_race:
            collect_ok = collect_ok and (not paused)

        if collect_ok:
            self._current_lap_samples.append(sample)

    # internals
    def _reset_session(self) -> None:
        self._session_id += 1
        self._completed_laps.clear()
        self._current_lap_samples.clear()
        self._last_lap_num = None
        self._reference_idx = None

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

        self._ensure_reference(force=True)

    def _ensure_reference(self, force: bool = False) -> None:
        if self._reference_idx is not None and not force:
            return
        if not self._completed_laps:
            self._reference_idx = None
            return

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
        - heuristic freeze detection

        Heuristic: treat as "paused/frozen" if position is stable AND controls are idle AND speed is low
        continuously for >0.7s.
        """
        if self._last_moving_t is None:
            self._last_moving_t = now

        pos = (x, z)
        pos_stable = False
        if self._last_pos is not None:
            dx = pos[0] - self._last_pos[0]
            dz = pos[1] - self._last_pos[1]
            pos_stable = (dx * dx + dz * dz) < 0.01
        self._last_pos = pos

        controls_idle = (throttle < 0.5 and brake < 0.5)
        speed_idle = (speed_kmh < 1.0)

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