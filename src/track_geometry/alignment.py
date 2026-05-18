from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Sequence, Tuple

import numpy as np

Point2 = Tuple[float, float]


@dataclass(frozen=True)
class TrackGeometry:
    name: str
    centerline: Tuple[Point2, ...]
    width_right_m: Tuple[float, ...]
    width_left_m: Tuple[float, ...]
    raceline: Tuple[Point2, ...]
    source: str = ""


@dataclass(frozen=True)
class SimilarityTransform:
    matrix: Tuple[Tuple[float, float], Tuple[float, float]]
    scale: float
    translation: Point2
    reflected: bool
    reversed: bool
    shift_bins: int
    n_fit_points: int
    rmse_m: float
    mean_error_m: float
    p95_error_m: float
    max_error_m: float

    def apply_point(self, point: Point2) -> Point2:
        x, y = float(point[0]), float(point[1])
        m = self.matrix
        tx, ty = self.translation
        return (
            self.scale * (m[0][0] * x + m[0][1] * y) + tx,
            self.scale * (m[1][0] * x + m[1][1] * y) + ty,
        )

    def apply_points(self, points: Sequence[Point2]) -> Tuple[Point2, ...]:
        if not points:
            return tuple()
        arr = np.asarray(points, dtype=float)
        mat = np.asarray(self.matrix, dtype=float)
        trans = np.asarray(self.translation, dtype=float)
        out = self.scale * (arr @ mat.T) + trans
        return tuple((float(x), float(y)) for x, y in out)


@dataclass(frozen=True)
class AlignedTrackGeometry:
    source: TrackGeometry
    transform: SimilarityTransform
    centerline: Tuple[Point2, ...]
    raceline: Tuple[Point2, ...]
    boundary_right: Tuple[Point2, ...]
    boundary_left: Tuple[Point2, ...]
    width_right_m: Tuple[float, ...]
    width_left_m: Tuple[float, ...]


def cumdist(points: Sequence[Point2], *, closed: bool = False) -> list[float]:
    pts = _clean_points(points)
    if not pts:
        return []

    out = [0.0]
    for i in range(1, len(pts)):
        out.append(out[-1] + _dist(pts[i - 1], pts[i]))
    if closed and len(pts) > 1:
        out.append(out[-1] + _dist(pts[-1], pts[0]))
    return out


def resample_polyline(
    points: Sequence[Point2],
    n: int,
    *,
    closed: bool = False,
) -> Tuple[Point2, ...]:
    pts = _clean_points(points)
    n = int(n)
    if n <= 0 or not pts:
        return tuple()
    if len(pts) == 1:
        return tuple(pts[0] for _ in range(n))

    work = pts + [pts[0]] if closed else pts
    cd = cumdist(pts, closed=closed)
    if not cd or cd[-1] <= 1e-9:
        return tuple(work[0] for _ in range(n))

    if closed:
        targets = [cd[-1] * (i / n) for i in range(n)]
    else:
        if n == 1:
            return (work[0],)
        targets = [cd[-1] * (i / (n - 1)) for i in range(n)]

    return tuple(_point_at_distance(work, cd, target) for target in targets)


def resample_series_by_polyline(
    values: Sequence[float],
    points: Sequence[Point2],
    n: int,
    *,
    closed: bool = False,
) -> Tuple[float, ...]:
    pts = _clean_points(points)
    vals = [float(v) for v in values]
    n = int(n)
    if n <= 0 or not pts or not vals:
        return tuple()

    count = min(len(pts), len(vals))
    pts = pts[:count]
    vals = vals[:count]
    if count == 1:
        return tuple(vals[0] for _ in range(n))

    work_vals = vals + [vals[0]] if closed else vals
    cd = cumdist(pts, closed=closed)
    if not cd or cd[-1] <= 1e-9:
        return tuple(work_vals[0] for _ in range(n))

    if closed:
        targets = [cd[-1] * (i / n) for i in range(n)]
    else:
        if n == 1:
            return (work_vals[0],)
        targets = [cd[-1] * (i / (n - 1)) for i in range(n)]

    return tuple(_series_at_distance(work_vals, cd, target) for target in targets)


def build_track_edges(
    centerline: Sequence[Point2],
    width_right_m: Sequence[float],
    width_left_m: Sequence[float],
) -> tuple[Tuple[Point2, ...], Tuple[Point2, ...]]:
    pts = _clean_points(centerline)
    wr = [float(v) for v in width_right_m]
    wl = [float(v) for v in width_left_m]
    n = min(len(pts), len(wr), len(wl))
    if n == 0:
        return tuple(), tuple()
    pts = pts[:n]
    wr = wr[:n]
    wl = wl[:n]

    right: list[Point2] = []
    left: list[Point2] = []
    for i, (x, y) in enumerate(pts):
        if n == 1:
            tx, ty = 1.0, 0.0
        else:
            p_prev = pts[i - 1]
            p_next = pts[(i + 1) % n]
            tx = p_next[0] - p_prev[0]
            ty = p_next[1] - p_prev[1]
            norm = math.hypot(tx, ty)
            if norm <= 1e-9:
                tx, ty = 1.0, 0.0
            else:
                tx /= norm
                ty /= norm

        # Right-hand normal for x/y coordinates with path direction tangent.
        nx, ny = ty, -tx
        right.append((x + nx * wr[i], y + ny * wr[i]))
        left.append((x - nx * wl[i], y - ny * wl[i]))

    return tuple(right), tuple(left)


def align_track_to_lap(
    geometry: TrackGeometry,
    lap_points_xz: Sequence[Point2],
    *,
    n_fit_points: int = 720,
    max_shift_bins: int | None = None,
    allow_reverse: bool = True,
    allow_reflection: bool = True,
) -> AlignedTrackGeometry:
    if len(geometry.raceline) < 10:
        raise ValueError("Track geometry needs at least 10 raceline points.")
    if len(lap_points_xz) < 10:
        raise ValueError("GT7 lap needs at least 10 position points.")

    transform = fit_similarity_to_closed_paths(
        geometry.raceline,
        lap_points_xz,
        n=n_fit_points,
        max_shift_bins=max_shift_bins,
        allow_reverse=allow_reverse,
        allow_reflection=allow_reflection,
    )

    right_src, left_src = build_track_edges(
        geometry.centerline,
        geometry.width_right_m,
        geometry.width_left_m,
    )

    return AlignedTrackGeometry(
        source=geometry,
        transform=transform,
        centerline=transform.apply_points(geometry.centerline),
        raceline=transform.apply_points(geometry.raceline),
        boundary_right=transform.apply_points(right_src),
        boundary_left=transform.apply_points(left_src),
        width_right_m=tuple(float(w) * transform.scale for w in geometry.width_right_m),
        width_left_m=tuple(float(w) * transform.scale for w in geometry.width_left_m),
    )


def fit_similarity_to_closed_paths(
    source_points: Sequence[Point2],
    target_points: Sequence[Point2],
    *,
    n: int = 720,
    max_shift_bins: int | None = None,
    allow_reverse: bool = True,
    allow_reflection: bool = True,
) -> SimilarityTransform:
    n = max(12, int(n))
    src_base = np.asarray(
        resample_polyline(source_points, n, closed=True),
        dtype=float,
    )
    dst = np.asarray(
        resample_polyline(target_points, n, closed=True),
        dtype=float,
    )
    if src_base.shape != dst.shape or src_base.size == 0:
        raise ValueError("Source and target paths could not be resampled.")

    if max_shift_bins is None:
        shifts = range(n)
    else:
        limit = max(0, min(int(max_shift_bins), n // 2))
        shifts = [(s % n) for s in range(-limit, limit + 1)]

    best: SimilarityTransform | None = None
    for reversed_order in ([False, True] if allow_reverse else [False]):
        src_ordered = src_base[::-1] if reversed_order else src_base
        for shift in shifts:
            src = np.roll(src_ordered, int(shift), axis=0)
            candidate = _fit_similarity(
                src,
                dst,
                allow_reflection=allow_reflection,
                reversed_order=reversed_order,
                shift_bins=int(shift),
            )
            if best is None or candidate.rmse_m < best.rmse_m:
                best = candidate

    if best is None:
        raise ValueError("Could not fit a similarity transform.")
    return best


def lap_track_metrics(
    lap_points_xz: Sequence[Point2],
    aligned: AlignedTrackGeometry,
    *,
    n: int = 300,
) -> dict[str, Any]:
    lap = np.asarray(resample_polyline(lap_points_xz, n, closed=False), dtype=float)
    center, right_w, left_w = _matched_centerline_and_widths(aligned, n)
    race = np.asarray(_matched_source_points(aligned.source.raceline, aligned, n), dtype=float)

    normals = _right_normals(center)
    delta_center = lap - center
    lateral = np.sum(delta_center * normals, axis=1)
    raceline_error = np.linalg.norm(lap - race, axis=1)
    right_margin = right_w - lateral
    left_margin = left_w + lateral
    on_track = (right_margin >= 0.0) & (left_margin >= 0.0)

    return {
        "lateral_offset_m": _float_list(lateral),
        "raceline_error_m": _float_list(raceline_error),
        "right_margin_m": _float_list(right_margin),
        "left_margin_m": _float_list(left_margin),
        "on_track": [bool(v) for v in on_track.tolist()],
        "raceline_error_mean_m": float(np.mean(raceline_error)),
        "raceline_error_p95_m": float(np.percentile(raceline_error, 95)),
        "min_right_margin_m": float(np.min(right_margin)),
        "min_left_margin_m": float(np.min(left_margin)),
        "off_track_bins": int(np.count_nonzero(~on_track)),
    }


def aligned_track_to_payload(
    aligned: AlignedTrackGeometry,
    *,
    n: int = 720,
) -> dict[str, Any]:
    center, right_w, left_w = _matched_centerline_and_widths(aligned, n)
    raceline = _matched_source_points(aligned.source.raceline, aligned, n)
    right_edge, left_edge = build_track_edges(
        tuple((float(x), float(y)) for x, y in center),
        tuple(float(v) for v in right_w),
        tuple(float(v) for v in left_w),
    )
    return {
        "source": {
            "name": aligned.source.name,
            "source": aligned.source.source,
        },
        "transform": asdict(aligned.transform),
        "resampled": {
            "n": int(n),
            "centerline_xz": _points_payload(center),
            "raceline_xz": _points_payload(raceline),
            "right_boundary_xz": _points_payload(right_edge),
            "left_boundary_xz": _points_payload(left_edge),
            "width_right_m": _float_list(right_w),
            "width_left_m": _float_list(left_w),
        },
    }


def _fit_similarity(
    src: np.ndarray,
    dst: np.ndarray,
    *,
    allow_reflection: bool,
    reversed_order: bool,
    shift_bins: int,
) -> SimilarityTransform:
    src_mean = np.mean(src, axis=0)
    dst_mean = np.mean(dst, axis=0)
    src0 = src - src_mean
    dst0 = dst - dst_mean

    h = src0.T @ dst0
    u, _, vt = np.linalg.svd(h)
    matrix = vt.T @ u.T

    if not allow_reflection and np.linalg.det(matrix) < 0:
        vt[-1, :] *= -1.0
        matrix = vt.T @ u.T

    rotated = src0 @ matrix.T
    denom = float(np.sum(rotated * rotated))
    if denom <= 1e-12:
        raise ValueError("Degenerate source path.")
    scale = float(np.sum(dst0 * rotated) / denom)
    if scale < 0.0:
        scale = -scale
        matrix = -matrix

    translation = dst_mean - scale * (matrix @ src_mean)
    transformed = scale * (src @ matrix.T) + translation
    err = np.linalg.norm(transformed - dst, axis=1)

    return SimilarityTransform(
        matrix=(
            (float(matrix[0, 0]), float(matrix[0, 1])),
            (float(matrix[1, 0]), float(matrix[1, 1])),
        ),
        scale=scale,
        translation=(float(translation[0]), float(translation[1])),
        reflected=bool(np.linalg.det(matrix) < 0),
        reversed=bool(reversed_order),
        shift_bins=int(shift_bins),
        n_fit_points=int(src.shape[0]),
        rmse_m=float(math.sqrt(np.mean(err * err))),
        mean_error_m=float(np.mean(err)),
        p95_error_m=float(np.percentile(err, 95)),
        max_error_m=float(np.max(err)),
    )


def _matched_source_points(
    points: Sequence[Point2],
    aligned: AlignedTrackGeometry,
    n: int,
) -> Tuple[Point2, ...]:
    pts = np.asarray(resample_polyline(points, n, closed=True), dtype=float)
    if aligned.transform.reversed:
        pts = pts[::-1]
    pts = np.roll(pts, aligned.transform.shift_bins, axis=0)
    return aligned.transform.apply_points(tuple((float(x), float(y)) for x, y in pts))


def _matched_centerline_and_widths(
    aligned: AlignedTrackGeometry,
    n: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    center = np.asarray(
        _matched_source_points(aligned.source.centerline, aligned, n),
        dtype=float,
    )
    wr = np.asarray(
        resample_series_by_polyline(
            aligned.source.width_right_m,
            aligned.source.centerline,
            n,
            closed=True,
        ),
        dtype=float,
    )
    wl = np.asarray(
        resample_series_by_polyline(
            aligned.source.width_left_m,
            aligned.source.centerline,
            n,
            closed=True,
        ),
        dtype=float,
    )
    if aligned.transform.reversed:
        wr = wr[::-1]
        wl = wl[::-1]
    wr = np.roll(wr, aligned.transform.shift_bins) * aligned.transform.scale
    wl = np.roll(wl, aligned.transform.shift_bins) * aligned.transform.scale
    return center, wr, wl


def _right_normals(points: np.ndarray) -> np.ndarray:
    n = len(points)
    out = np.zeros_like(points)
    for i in range(n):
        p_prev = points[i - 1]
        p_next = points[(i + 1) % n]
        tangent = p_next - p_prev
        norm = float(np.linalg.norm(tangent))
        if norm <= 1e-12:
            out[i] = np.array([0.0, -1.0])
        else:
            tangent = tangent / norm
            out[i] = np.array([tangent[1], -tangent[0]])
    return out


def _point_at_distance(points: Sequence[Point2], cd: Sequence[float], target: float) -> Point2:
    if target <= 0:
        return points[0]
    if target >= cd[-1]:
        return points[-1]
    j = 0
    while j + 1 < len(cd) and cd[j + 1] < target:
        j += 1
    d0 = cd[j]
    d1 = cd[j + 1]
    if d1 - d0 <= 1e-12:
        return points[j]
    alpha = (target - d0) / (d1 - d0)
    return (
        float(points[j][0] + alpha * (points[j + 1][0] - points[j][0])),
        float(points[j][1] + alpha * (points[j + 1][1] - points[j][1])),
    )


def _series_at_distance(values: Sequence[float], cd: Sequence[float], target: float) -> float:
    if target <= 0:
        return float(values[0])
    if target >= cd[-1]:
        return float(values[-1])
    j = 0
    while j + 1 < len(cd) and cd[j + 1] < target:
        j += 1
    d0 = cd[j]
    d1 = cd[j + 1]
    if d1 - d0 <= 1e-12:
        return float(values[j])
    alpha = (target - d0) / (d1 - d0)
    return float(values[j] + alpha * (values[j + 1] - values[j]))


def _dist(a: Point2, b: Point2) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _clean_points(points: Sequence[Point2]) -> list[Point2]:
    out: list[Point2] = []
    for point in points:
        if len(point) < 2:
            continue
        x = float(point[0])
        y = float(point[1])
        if math.isfinite(x) and math.isfinite(y):
            out.append((x, y))
    return out


def _points_payload(points: Sequence[Point2] | np.ndarray) -> list[list[float]]:
    return [[float(p[0]), float(p[1])] for p in points]


def _float_list(values: Sequence[float] | np.ndarray) -> list[float]:
    return [float(v) for v in values]
