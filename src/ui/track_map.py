# src/ui/track_map.py
from __future__ import annotations

from PySide6 import QtWidgets
import pyqtgraph as pg

from src.core.telemetry_session import TelemetrySession, LapData, _resample_by_distance


class TrackMapWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)

        self.plot = pg.PlotWidget(title="Track Map (X vs Z) — last vs reference")
        self.plot.setAspectLocked(True)
        self.plot.showGrid(x=True, y=True, alpha=0.2)

        # reference + last lap polylines
        self._ref_line = self.plot.plot([], [], pen=pg.mkPen(width=2))
        self._last_line = self.plot.plot([], [], pen=pg.mkPen(width=2))

        # delta overlay (scatter along last lap)
        self._delta_scatter = pg.ScatterPlotItem(size=6)
        self.plot.addItem(self._delta_scatter)

        # current car position
        self._car_dot = pg.ScatterPlotItem(size=10)
        self.plot.addItem(self._car_dot)

        # start/finish gate + sector markers
        self._gate_line = self.plot.plot([], [], pen=pg.mkPen(width=2))
        self._sector_scatter = pg.ScatterPlotItem(size=10)
        self.plot.addItem(self._sector_scatter)

        layout.addWidget(self.plot)

        self._last_session_id = None

    def update_from_session(self, session: TelemetrySession) -> None:
        # session reset handling for visuals
        if self._last_session_id is None:
            self._last_session_id = session.session_id()
        elif session.session_id() != self._last_session_id:
            self._clear()
            self._last_session_id = session.session_id()

        laps = session.completed_laps()
        ref = session.reference_lap()
        last = laps[-1] if laps else None

        # draw reference lap
        if ref:
            self._set_polyline(self._ref_line, ref.points_xz)
            self._draw_gate_and_sectors(session, ref)
        else:
            self._set_polyline(self._ref_line, [])

        # draw last completed lap
        if last:
            self._set_polyline(self._last_line, last.points_xz)
        else:
            self._set_polyline(self._last_line, [])

        # delta overlay (speed delta along distance-aligned resample)
        self._draw_delta(session, last, ref)

        # current car dot from current lap points (not completed)
        cur_pts = session.current_lap_points()
        if cur_pts:
            x, z = cur_pts[-1]
            self._car_dot.setData([x], [z])
        else:
            self._car_dot.setData([], [])

    def _set_polyline(self, item: pg.PlotDataItem, pts: list[tuple[float, float]]) -> None:
        if not pts:
            item.setData([], [])
            return
        xs = [p[0] for p in pts]
        zs = [p[1] for p in pts]
        item.setData(xs, zs)

    def _draw_gate_and_sectors(self, session: TelemetrySession, lap: LapData) -> None:
        # start/finish gate line
        if lap.start_gate:
            (a, b) = lap.start_gate
            self._gate_line.setData([a[0], b[0]], [a[1], b[1]])
        else:
            self._gate_line.setData([], [])

        # sector markers at 1/3 and 2/3 distance (synthetic)
        if not lap.cum_dist_m:
            self._sector_scatter.setData([], [])
            return

        d1, d2 = session.sector_splits_m(lap)
        p1 = self._point_at_distance(lap, d1)
        p2 = self._point_at_distance(lap, d2)
        spots = []
        if p1:
            spots.append({"pos": p1})
        if p2:
            spots.append({"pos": p2})
        self._sector_scatter.setData(spots)

    def _point_at_distance(self, lap: LapData, target_d: float) -> tuple[float, float] | None:
        cd = lap.cum_dist_m
        pts = lap.points_xz
        if not cd or not pts or len(cd) != len(pts):
            return None
        if target_d <= 0:
            return pts[0]
        if target_d >= cd[-1]:
            return pts[-1]
        j = 0
        while j + 1 < len(cd) and cd[j + 1] < target_d:
            j += 1
        d0, d1 = cd[j], cd[j + 1]
        if d1 - d0 < 1e-9:
            return pts[j]
        a = (target_d - d0) / (d1 - d0)
        x = pts[j][0] + a * (pts[j + 1][0] - pts[j][0])
        z = pts[j][1] + a * (pts[j + 1][1] - pts[j][1])
        return (x, z)

    def _draw_delta(self, session: TelemetrySession, last: LapData | None, ref: LapData | None) -> None:
        if not last or not ref:
            self._delta_scatter.setData([])
            return
        if not last.cum_dist_m or not ref.cum_dist_m:
            self._delta_scatter.setData([])
            return

        n = 220  # point density on overlay
        last_r_pts = _resample_by_distance(last.points_xz, last.cum_dist_m, n=n)
        deltas = session.delta_profile_speed(last, ref, n=n)
        if not last_r_pts or not deltas or len(last_r_pts) != len(deltas):
            self._delta_scatter.setData([])
            return

        # Two-tone first pass: faster vs slower than reference (by speed delta)
        spots = []
        for (x, z), dv in zip(last_r_pts, deltas):
            # dv > 0 => last faster; dv < 0 => last slower
            brush = pg.mkBrush(0, 200, 0, 180) if dv >= 0 else pg.mkBrush(200, 0, 0, 180)
            spots.append({"pos": (x, z), "brush": brush})
        self._delta_scatter.setData(spots)

    def _clear(self) -> None:
        self._ref_line.setData([], [])
        self._last_line.setData([], [])
        self._delta_scatter.setData([])
        self._car_dot.setData([], [])
        self._gate_line.setData([], [])
        self._sector_scatter.setData([], [])
