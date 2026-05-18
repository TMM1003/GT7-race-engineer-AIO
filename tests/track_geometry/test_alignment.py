from __future__ import annotations

import math
import unittest

from src.track_geometry import (
    TrackGeometry,
    align_track_to_lap,
    lap_track_metrics,
)


def _source_track() -> TrackGeometry:
    center = []
    race = []
    wr = []
    wl = []
    for i in range(96):
        t = 2.0 * math.pi * i / 96.0
        # Asymmetric closed shape so circular alignment has one clear answer.
        r = 70.0 + 8.0 * math.sin(3.0 * t) + 5.0 * math.cos(5.0 * t)
        x = r * math.cos(t)
        y = 42.0 * math.sin(t) + 6.0 * math.sin(2.0 * t)
        center.append((x, y))
        race.append((x + 1.5 * math.sin(t), y - 1.0 * math.cos(t)))
        wr.append(5.0 + 0.2 * math.sin(t))
        wl.append(6.0 + 0.2 * math.cos(t))
    return TrackGeometry(
        name="Synthetic",
        centerline=tuple(center),
        width_right_m=tuple(wr),
        width_left_m=tuple(wl),
        raceline=tuple(race),
        source="unit-test",
    )


def _transform(points, *, scale, radians, tx, ty):
    c = math.cos(radians)
    s = math.sin(radians)
    out = []
    for x, y in points:
        # Reflection across source y followed by rotation/translation.
        xr = x
        yr = -y
        out.append(
            (
                scale * (c * xr - s * yr) + tx,
                scale * (s * xr + c * yr) + ty,
            )
        )
    return out


class TrackAlignmentTests(unittest.TestCase):
    def test_align_track_to_lap_recovers_similarity_transform(self) -> None:
        track = _source_track()
        lap_points = _transform(
            track.raceline,
            scale=1.03,
            radians=0.73,
            tx=250.0,
            ty=-120.0,
        )

        aligned = align_track_to_lap(
            track,
            lap_points,
            n_fit_points=192,
            max_shift_bins=3,
            allow_reverse=False,
        )

        self.assertLess(aligned.transform.rmse_m, 0.25)
        self.assertAlmostEqual(aligned.transform.scale, 1.03, places=2)
        self.assertTrue(aligned.transform.reflected)
        self.assertFalse(aligned.transform.reversed)
        self.assertEqual(len(aligned.boundary_left), len(track.centerline))
        self.assertEqual(len(aligned.boundary_right), len(track.centerline))

    def test_lap_track_metrics_report_margins_and_raceline_error(self) -> None:
        track = _source_track()
        lap_points = _transform(
            track.raceline,
            scale=1.0,
            radians=0.2,
            tx=10.0,
            ty=20.0,
        )
        aligned = align_track_to_lap(
            track,
            lap_points,
            n_fit_points=192,
            max_shift_bins=3,
            allow_reverse=False,
        )

        metrics = lap_track_metrics(lap_points, aligned, n=120)

        self.assertLess(metrics["raceline_error_mean_m"], 1.0)
        self.assertEqual(metrics["off_track_bins"], 0)
        self.assertEqual(len(metrics["raceline_error_m"]), 120)
        self.assertEqual(len(metrics["right_margin_m"]), 120)


if __name__ == "__main__":
    unittest.main()
