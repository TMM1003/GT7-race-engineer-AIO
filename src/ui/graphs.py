from __future__ import annotations

from collections.abc import Mapping

from PySide6 import QtCore, QtWidgets
import pyqtgraph as pg

from src.core.telemetry_session import LapData, TelemetrySession
from src.ui.graph_colors import (
    graph_series_palette,
    normalized_graph_color_settings,
    overlay_series_palette,
)


def _time_axis(samples, window_s: float) -> tuple[list[float], int]:
    """
    Return (xs, start_index), where xs are seconds
    relative to the latest sample.
    xs will be negative -> 0 over the window.
    """
    if not samples:
        return [], 0
    t_end = samples[-1].t

    start = 0
    for i in range(len(samples) - 1, -1, -1):
        if (t_end - samples[i].t) > window_s:
            start = i + 1
            break

    xs = [samples[i].t - t_end for i in range(start, len(samples))]
    return xs, start


class GraphsWidget(QtWidgets.QWidget):
    """
    Original graphs tab: four stacked time-series plots.
    Updated to use consistent coloring and a legend key.
    """

    def __init__(self, window_s: float = 60.0):
        super().__init__()
        self._window_s = float(window_s)
        self._color_settings = normalized_graph_color_settings(None)

        layout = QtWidgets.QVBoxLayout(self)

        self._plots: dict[str, pg.PlotWidget] = {}
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._compare_curves: dict[str, pg.PlotDataItem] = {}

        graph_palette = graph_series_palette(self._color_settings)

        def add_plot(key: str, title: str, y_label: str) -> None:
            w = pg.PlotWidget(title=title)
            w.showGrid(x=True, y=True, alpha=0.2)
            w.setLabel("left", y_label)
            w.setLabel("bottom", "time", units="s")
            w.addLegend(offset=(10, 10))

            c = w.plot(
                [],
                [],
                pen=pg.mkPen(graph_palette[key], width=2),
                name="Primary",
            )
            c_compare = w.plot(
                [],
                [],
                pen=pg.mkPen(
                    self._color_settings["compare"],
                    width=2,
                    style=QtCore.Qt.DashLine,
                ),
                name="Compare",
            )
            self._plots[key] = w
            self._curves[key] = c
            self._compare_curves[key] = c_compare
            layout.addWidget(w)

        add_plot("speed", "Speed", "km/h")
        add_plot("rpm", "RPM", "rpm")
        add_plot("throttle", "Throttle", "%")
        add_plot("brake", "Brake", "%")

    def set_color_settings(
        self, settings: Mapping[str, object] | None
    ) -> None:
        self._color_settings = normalized_graph_color_settings(settings)
        graph_palette = graph_series_palette(self._color_settings)
        compare_pen = pg.mkPen(
            self._color_settings["compare"],
            width=2,
            style=QtCore.Qt.DashLine,
        )
        for key, curve in self._curves.items():
            curve.setPen(pg.mkPen(graph_palette[key], width=2))
        for curve in self._compare_curves.values():
            curve.setPen(compare_pen)

    def update_from_session(self, session: TelemetrySession) -> None:
        replay_compare = session.replay_comparison_state()
        if replay_compare is not None and replay_compare.compare_lap_num is not None:
            laps = session.completed_laps()
            compare = session.reference_lap()
            primary = laps[-1] if laps else None
            if (
                primary is not None
                and compare is not None
                and primary.lap_num != compare.lap_num
            ):
                self._update_replay_compare(
                    primary, compare, replay_compare.compare_color
                )
                return

        samples = session.samples()
        xs, start = _time_axis(samples, self._window_s)
        if not xs:
            for c in self._curves.values():
                c.setData([], [])
            for c in self._compare_curves.values():
                c.setData([], [])
            for key, title in (
                ("speed", "Speed"),
                ("rpm", "RPM"),
                ("throttle", "Throttle"),
                ("brake", "Brake"),
            ):
                self._plots[key].setTitle(title)
            return

        spd = [samples[i].speed_kmh for i in range(start, len(samples))]
        rpm = [samples[i].rpm for i in range(start, len(samples))]
        thr = [samples[i].throttle for i in range(start, len(samples))]
        brk = [samples[i].brake for i in range(start, len(samples))]

        self._curves["speed"].setData(xs, spd)
        self._curves["rpm"].setData(xs, rpm)
        self._curves["throttle"].setData(xs, thr)
        self._curves["brake"].setData(xs, brk)
        for key, title in (
            ("speed", "Speed"),
            ("rpm", "RPM"),
            ("throttle", "Throttle"),
            ("brake", "Brake"),
        ):
            self._plots[key].setTitle(title)
            self._compare_curves[key].setData([], [])

    def _update_replay_compare(
        self, primary: LapData, compare: LapData, compare_color: str
    ) -> None:
        primary_xs = self._lap_elapsed_axis(primary)
        compare_xs = self._lap_elapsed_axis(compare)
        if not primary_xs or not compare_xs:
            for c in self._curves.values():
                c.setData([], [])
            for c in self._compare_curves.values():
                c.setData([], [])
            return

        primary_series = {
            "speed": [sample.speed_kmh for sample in primary.samples],
            "rpm": [sample.rpm for sample in primary.samples],
            "throttle": [sample.throttle for sample in primary.samples],
            "brake": [sample.brake for sample in primary.samples],
        }
        compare_series = {
            "speed": [sample.speed_kmh for sample in compare.samples],
            "rpm": [sample.rpm for sample in compare.samples],
            "throttle": [sample.throttle for sample in compare.samples],
            "brake": [sample.brake for sample in compare.samples],
        }

        compare_pen = pg.mkPen(
            compare_color or self._color_settings["compare"],
            width=2,
            style=QtCore.Qt.DashLine,
        )
        for key, title in (
            ("speed", "Speed"),
            ("rpm", "RPM"),
            ("throttle", "Throttle"),
            ("brake", "Brake"),
        ):
            self._plots[key].setTitle(
                f"{title} - Lap {primary.lap_num} vs Lap {compare.lap_num}"
            )
            self._curves[key].setData(primary_xs, primary_series[key])
            self._compare_curves[key].setPen(compare_pen)
            self._compare_curves[key].setData(
                compare_xs, compare_series[key]
            )

    def _lap_elapsed_axis(self, lap: LapData) -> list[float]:
        if not lap.samples:
            return []
        start_t = float(lap.samples[0].t)
        return [float(sample.t) - start_t for sample in lap.samples]


class GraphsOverlayWidget(QtWidgets.QWidget):
    """
    Second graphs tab: overlays four signals onto one plot
    with consistent coloring and a legend.
    Since units differ, speed and RPM are normalized to 0-100
    for visual comparison.
    """

    def __init__(self, window_s: float = 60.0):
        super().__init__()
        self._window_s = float(window_s)
        self._color_settings = normalized_graph_color_settings(None)
        overlay_palette = overlay_series_palette(self._color_settings)

        layout = QtWidgets.QVBoxLayout(self)

        self.plot = pg.PlotWidget(
            title="Overlay (normalized) - Speed, RPM, Throttle, Brake"
        )
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.setLabel("left", "normalized", units="")
        self.plot.setLabel("bottom", "time", units="s")
        self.plot.addLegend(offset=(10, 10))

        self._c_speed = self.plot.plot(
            [],
            [],
            pen=pg.mkPen(overlay_palette["speed"], width=2),
            name="Speed (norm)",
        )
        self._c_rpm = self.plot.plot(
            [],
            [],
            pen=pg.mkPen(overlay_palette["rpm"], width=2),
            name="RPM (norm)",
        )
        self._c_thr = self.plot.plot(
            [],
            [],
            pen=pg.mkPen(overlay_palette["throttle"], width=2),
            name="Throttle (0-100)",
        )
        self._c_brk = self.plot.plot(
            [],
            [],
            pen=pg.mkPen(overlay_palette["brake"], width=2),
            name="Brake (0-100)",
        )

        layout.addWidget(self.plot)

        note = QtWidgets.QLabel(
            (
                "Note: Speed and RPM are normalized to 0-100 so they "
                "can be compared visually with throttle/brake."
            )
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(note)

    def set_color_settings(
        self, settings: Mapping[str, object] | None
    ) -> None:
        self._color_settings = normalized_graph_color_settings(settings)
        overlay_palette = overlay_series_palette(self._color_settings)
        self._c_speed.setPen(pg.mkPen(overlay_palette["speed"], width=2))
        self._c_rpm.setPen(pg.mkPen(overlay_palette["rpm"], width=2))
        self._c_thr.setPen(
            pg.mkPen(overlay_palette["throttle"], width=2)
        )
        self._c_brk.setPen(pg.mkPen(overlay_palette["brake"], width=2))

    def update_from_session(self, session: TelemetrySession) -> None:
        samples = session.samples()
        xs, start = _time_axis(samples, self._window_s)
        if not xs:
            self._c_speed.setData([], [])
            self._c_rpm.setData([], [])
            self._c_thr.setData([], [])
            self._c_brk.setData([], [])
            return

        spd = [samples[i].speed_kmh for i in range(start, len(samples))]
        rpm = [samples[i].rpm for i in range(start, len(samples))]
        thr = [samples[i].throttle for i in range(start, len(samples))]
        brk = [samples[i].brake for i in range(start, len(samples))]

        def norm_0_100(arr: list[float]) -> list[float]:
            if not arr:
                return []
            mn = min(arr)
            mx = max(arr)
            if mx - mn < 1e-9:
                return [0.0 for _ in arr]
            return [100.0 * (v - mn) / (mx - mn) for v in arr]

        self._c_speed.setData(xs, norm_0_100(spd))
        self._c_rpm.setData(xs, norm_0_100(rpm))
        self._c_thr.setData(xs, thr)
        self._c_brk.setData(xs, brk)
