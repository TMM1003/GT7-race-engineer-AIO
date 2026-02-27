# src/ui/track_map.py
from __future__ import annotations

from PySide6 import QtWidgets, QtCore
import pyqtgraph as pg

from src.core.telemetry_session import (
    TelemetrySession,
    LapData,
    _resample_by_distance,
)

TIME_PLACEHOLDER = "--.--"
DELTA_PLACEHOLDER = "—"


def _ms_str(ms: int | None) -> str:
    if ms is None or ms <= 0:
        return TIME_PLACEHOLDER
    return f"{(ms / 1000.0):0.3f}"


def _delta_ms_str(ms: int | None) -> str:
    if ms is None:
        return DELTA_PLACEHOLDER
    sign = "+" if ms > 0 else ""
    return f"{sign}{(ms / 1000.0):0.3f}"


def _delta_ms_color_style(delta_ms: float | None) -> str:
    # negative = faster (green), positive = slower (red)
    if delta_ms is None:
        return ""
    return "color: #27ae60;" if delta_ms <= 0 else "color: #c0392b;"


def _delta_at_fraction(
    delta_ms_profile: list[float], frac: float
) -> float | None:
    if not delta_ms_profile:
        return None
    frac = max(0.0, min(1.0, frac))
    idx = int(round(frac * (len(delta_ms_profile) - 1)))
    if 0 <= idx < len(delta_ms_profile):
        return float(delta_ms_profile[idx])
    return None


class TrackMapWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)

        # Sector panel
        self._sector_panel = QtWidgets.QGroupBox(
            "Sector Times (synthetic thirds)"
        )
        grid = QtWidgets.QGridLayout(self._sector_panel)

        # Header row
        grid.addWidget(QtWidgets.QLabel(""), 0, 0)
        grid.addWidget(self._hdr("S1"), 0, 1)
        grid.addWidget(self._hdr("S2"), 0, 2)
        grid.addWidget(self._hdr("S3"), 0, 3)

        # Ref row
        grid.addWidget(self._hdr("Ref"), 1, 0)
        self._ref_s1 = self._cell(TIME_PLACEHOLDER)
        self._ref_s2 = self._cell(TIME_PLACEHOLDER)
        self._ref_s3 = self._cell(TIME_PLACEHOLDER)
        grid.addWidget(self._ref_s1, 1, 1)
        grid.addWidget(self._ref_s2, 1, 2)
        grid.addWidget(self._ref_s3, 1, 3)

        # Last row
        grid.addWidget(self._hdr("Last"), 2, 0)
        self._last_s1 = self._cell(TIME_PLACEHOLDER)
        self._last_s2 = self._cell(TIME_PLACEHOLDER)
        self._last_s3 = self._cell(TIME_PLACEHOLDER)
        grid.addWidget(self._last_s1, 2, 1)
        grid.addWidget(self._last_s2, 2, 2)
        grid.addWidget(self._last_s3, 2, 3)

        # Δ sector-times row (Last - Ref)
        grid.addWidget(self._hdr("Δ"), 3, 0)
        self._delta_sector_s1 = self._cell(DELTA_PLACEHOLDER)
        self._delta_sector_s2 = self._cell(DELTA_PLACEHOLDER)
        self._delta_sector_s3 = self._cell(DELTA_PLACEHOLDER)
        grid.addWidget(self._delta_sector_s1, 3, 1)
        grid.addWidget(self._delta_sector_s2, 3, 2)
        grid.addWidget(self._delta_sector_s3, 3, 3)

        # Δ checkpoints row (distance-aligned Δt at 1/3, 2/3, finish)
        grid.addWidget(self._hdr("Δ@split"), 4, 0)
        self._delta_split_s1 = self._cell(DELTA_PLACEHOLDER, bold=True)
        self._delta_split_s2 = self._cell(DELTA_PLACEHOLDER, bold=True)
        self._delta_split_fin = self._cell(DELTA_PLACEHOLDER, bold=True)
        grid.addWidget(self._delta_split_s1, 4, 1)
        grid.addWidget(self._delta_split_s2, 4, 2)
        grid.addWidget(self._delta_split_fin, 4, 3)

        layout.addWidget(self._sector_panel)

        # Plot
        self.plot = pg.PlotWidget(
            title="Track Map (X vs Z) — last vs reference"
        )
        self.plot.setAspectLocked(True)
        self.plot.showGrid(x=True, y=True, alpha=0.2)

        # reference + last lap polylines
        self._ref_line = self.plot.plot([], [], pen=pg.mkPen(width=2))
        self._last_line = self.plot.plot([], [], pen=pg.mkPen(width=2))
        # current lap trace (LIVE)
        self._cur_line = self.plot.plot(
            [], [], pen=pg.mkPen(width=2, style=QtCore.Qt.DashLine)
        )

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

        layout.addWidget(self.plot, stretch=1)

        self._last_session_id = None

    def _hdr(self, text: str) -> QtWidgets.QLabel:
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet("font-weight: 700;")
        return lbl

    def _cell(self, text: str, bold: bool = False) -> QtWidgets.QLabel:
        lbl = QtWidgets.QLabel(text)
        lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        weight = "700" if bold else "600"
        lbl.setStyleSheet(
            f"font-family: Consolas, monospace; font-weight: {weight};"
        )
        return lbl

    def update_from_session(
        self, session: TelemetrySession, n: int = 300
    ) -> None:
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
            self._gate_line.setData([], [])
            self._sector_scatter.setData([])

        # draw last completed lap
        if last:
            self._set_polyline(self._last_line, last.points_xz)
        else:
            self._set_polyline(self._last_line, [])

        # delta overlay (time delta along distance-aligned resample)
        self._draw_delta(session, last, ref)

        # current car dot from current lap points (not completed)
        cur_pts = session.current_lap_points()
        if cur_pts:
            # draw live polyline
            self._set_polyline(self._cur_line, cur_pts)
            # dot at current position
            x, z = cur_pts[-1]
            self._car_dot.setData([x], [z])
        else:
            self._set_polyline(self._cur_line, [])
            self._car_dot.setData([], [])
        # sector panel values
        self._update_sector_panel(session, last, ref, n=n)

    # Sector panel logic

    def _update_sector_panel(
        self,
        session: TelemetrySession,
        last: LapData | None,
        ref: LapData | None,
        n: int = 300,
    ) -> None:
        ref_times = session.sector_times_ms(ref) if ref else None
        last_times = session.sector_times_ms(last) if last else None

        # Ref times
        if ref_times:
            self._ref_s1.setText(_ms_str(ref_times[0]))
            self._ref_s2.setText(_ms_str(ref_times[1]))
            self._ref_s3.setText(_ms_str(ref_times[2]))
        else:
            self._ref_s1.setText(TIME_PLACEHOLDER)
            self._ref_s2.setText(TIME_PLACEHOLDER)
            self._ref_s3.setText(TIME_PLACEHOLDER)

        # Last times
        if last_times:
            self._last_s1.setText(_ms_str(last_times[0]))
            self._last_s2.setText(_ms_str(last_times[1]))
            self._last_s3.setText(_ms_str(last_times[2]))
        else:
            self._last_s1.setText(TIME_PLACEHOLDER)
            self._last_s2.setText(TIME_PLACEHOLDER)
            self._last_s3.setText(TIME_PLACEHOLDER)

        # Δ sector times (Last - Ref)
        if ref_times and last_times:
            d1 = last_times[0] - ref_times[0]
            d2 = last_times[1] - ref_times[1]
            d3 = last_times[2] - ref_times[2]
            self._delta_sector_s1.setText(_delta_ms_str(d1))
            self._delta_sector_s2.setText(_delta_ms_str(d2))
            self._delta_sector_s3.setText(_delta_ms_str(d3))
        else:
            self._delta_sector_s1.setText(DELTA_PLACEHOLDER)
            self._delta_sector_s2.setText(DELTA_PLACEHOLDER)
            self._delta_sector_s3.setText(DELTA_PLACEHOLDER)

        # Δ checkpoints from distance-aligned time delta profile
        prof = (
            session.delta_profile_time_ms(last, ref, n=n)
            if (last and ref)
            else None
        )
        if prof:
            d_s1 = _delta_at_fraction(prof, 1.0 / 3.0)
            d_s2 = _delta_at_fraction(prof, 2.0 / 3.0)
            d_fin = _delta_at_fraction(prof, 1.0)

            self._delta_split_s1.setText(
                _delta_ms_str(int(round(d_s1)))
                if d_s1 is not None
                else DELTA_PLACEHOLDER
            )
            self._delta_split_s2.setText(
                _delta_ms_str(int(round(d_s2)))
                if d_s2 is not None
                else DELTA_PLACEHOLDER
            )
            self._delta_split_fin.setText(
                _delta_ms_str(int(round(d_fin)))
                if d_fin is not None
                else DELTA_PLACEHOLDER
            )

            # colorize
            self._delta_split_s1.setStyleSheet(
                "font-family: Consolas, monospace; font-weight: 700; "
                + _delta_ms_color_style(d_s1)
            )
            self._delta_split_s2.setStyleSheet(
                "font-family: Consolas, monospace; font-weight: 700; "
                + _delta_ms_color_style(d_s2)
            )
            self._delta_split_fin.setStyleSheet(
                "font-family: Consolas, monospace; font-weight: 700; "
                + _delta_ms_color_style(d_fin)
            )
        else:
            self._delta_split_s1.setText(DELTA_PLACEHOLDER)
            self._delta_split_s2.setText(DELTA_PLACEHOLDER)
            self._delta_split_fin.setText(DELTA_PLACEHOLDER)
            self._delta_split_s1.setStyleSheet(
                "font-family: Consolas, monospace; font-weight: 700;"
            )
            self._delta_split_s2.setStyleSheet(
                "font-family: Consolas, monospace; font-weight: 700;"
            )
            self._delta_split_fin.setStyleSheet(
                "font-family: Consolas, monospace; font-weight: 700;"
            )

    # Existing drawing helpers

    def _set_polyline(
        self, item: pg.PlotDataItem, pts: list[tuple[float, float]]
    ) -> None:
        if not pts:
            item.setData([], [])
            return
        xs = [p[0] for p in pts]
        zs = [p[1] for p in pts]
        item.setData(xs, zs)

    def _draw_gate_and_sectors(
        self, session: TelemetrySession, lap: LapData
    ) -> None:
        # start/finish gate line
        if lap.start_gate:
            (a, b) = lap.start_gate
            self._gate_line.setData([a[0], b[0]], [a[1], b[1]])
        else:
            self._gate_line.setData([], [])

        # sector markers at 1/3 and 2/3 distance (synthetic)
        if not lap.cum_dist_m:
            self._sector_scatter.setData([])
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

    def _point_at_distance(
        self, lap: LapData, target_d: float
    ) -> tuple[float, float] | None:
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

    def _draw_delta(
        self,
        session: TelemetrySession,
        last: LapData | None,
        ref: LapData | None,
    ) -> None:
        if not last or not ref:
            self._delta_scatter.setData([])
            return
        if not last.cum_dist_m or not ref.cum_dist_m:
            self._delta_scatter.setData([])
            return

        n = 220
        last_r_pts = _resample_by_distance(
            last.points_xz, last.cum_dist_m, n=n
        )
        deltas_ms = session.delta_profile_time_ms(last, ref, n=n)

        if (
            not last_r_pts
            or not deltas_ms
            or len(last_r_pts) != len(deltas_ms)
        ):
            self._delta_scatter.setData([])
            return

        # delta_ms > 0 => behind (red), delta_ms <= 0 => ahead (green)
        spots = []
        for (x, z), dt in zip(last_r_pts, deltas_ms):
            brush = (
                pg.mkBrush(0, 200, 0, 180)
                if dt <= 0
                else pg.mkBrush(200, 0, 0, 180)
            )
            spots.append({"pos": (x, z), "brush": brush})
        self._delta_scatter.setData(spots)

    def _clear(self) -> None:
        self._ref_line.setData([], [])
        self._last_line.setData([], [])
        self._delta_scatter.setData([])
        self._car_dot.setData([], [])
        self._gate_line.setData([], [])
        self._sector_scatter.setData([])
        self._cur_line.setData([], [])

        self._ref_s1.setText(TIME_PLACEHOLDER)
        self._ref_s2.setText(TIME_PLACEHOLDER)
        self._ref_s3.setText(TIME_PLACEHOLDER)

        self._last_s1.setText(TIME_PLACEHOLDER)
        self._last_s2.setText(TIME_PLACEHOLDER)
        self._last_s3.setText(TIME_PLACEHOLDER)

        self._delta_sector_s1.setText(DELTA_PLACEHOLDER)
        self._delta_sector_s2.setText(DELTA_PLACEHOLDER)
        self._delta_sector_s3.setText(DELTA_PLACEHOLDER)

        self._delta_split_s1.setText(DELTA_PLACEHOLDER)
        self._delta_split_s2.setText(DELTA_PLACEHOLDER)
        self._delta_split_fin.setText(DELTA_PLACEHOLDER)
        self._delta_split_s1.setStyleSheet(
            "font-family: Consolas, monospace; font-weight: 700;"
        )
        self._delta_split_s2.setStyleSheet(
            "font-family: Consolas, monospace; font-weight: 700;"
        )
        self._delta_split_fin.setStyleSheet(
            "font-family: Consolas, monospace; font-weight: 700;"
        )
