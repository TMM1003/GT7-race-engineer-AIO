# src/ui/graphs.py
from __future__ import annotations
from PySide6 import QtWidgets
from src.core.telemetry_session import TelemetrySession
import pyqtgraph as pg


# Keep colors consistent across all graph views.
PENS = {
    "speed": pg.mkPen((52, 152, 219), width=2),     # blue
    "rpm": pg.mkPen((155, 89, 182), width=2),       # purple
    "throttle": pg.mkPen((46, 204, 113), width=2),  # green
    "brake": pg.mkPen((231, 76, 60), width=2),      # red
}


def _time_axis(samples, window_s: float) -> tuple[list[float], int]:
    """
    Return (xs, start_index) where xs are seconds relative to the latest sample.
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
    Updated to use consistent coloring and a legend “key”.
    """

    def __init__(self, window_s: float = 60.0):
        super().__init__()
        self._window_s = float(window_s)

        layout = QtWidgets.QVBoxLayout(self)

        self._plots: dict[str, pg.PlotWidget] = {}
        self._curves: dict[str, pg.PlotDataItem] = {}

        def add_plot(key: str, title: str, y_label: str) -> None:
            w = pg.PlotWidget(title=title)
            w.showGrid(x=True, y=True, alpha=0.2)
            w.setLabel("left", y_label)
            w.setLabel("bottom", "time", units="s")

            # Legend acts as the “key”
            w.addLegend(offset=(10, 10))

            c = w.plot([], [], pen=PENS[key], name=title)
            self._plots[key] = w
            self._curves[key] = c
            layout.addWidget(w)

        add_plot("speed", "Speed", "km/h")
        add_plot("rpm", "RPM", "rpm")
        add_plot("throttle", "Throttle", "%")
        add_plot("brake", "Brake", "%")

    def update_from_session(self, session: TelemetrySession) -> None:
        samples = session.samples()
        xs, start = _time_axis(samples, self._window_s)
        if not xs:
            for c in self._curves.values():
                c.setData([], [])
            return

        spd = [samples[i].speed_kmh for i in range(start, len(samples))]
        rpm = [samples[i].rpm for i in range(start, len(samples))]
        thr = [samples[i].throttle for i in range(start, len(samples))]
        brk = [samples[i].brake for i in range(start, len(samples))]

        self._curves["speed"].setData(xs, spd)
        self._curves["rpm"].setData(xs, rpm)
        self._curves["throttle"].setData(xs, thr)
        self._curves["brake"].setData(xs, brk)


class GraphsOverlayWidget(QtWidgets.QWidget):
    """
    Second graphs tab: overlays four signals onto one plot with consistent coloring + legend.
    Since units differ wildly, Speed & RPM are normalized to 0–100 for visual comparison.
    """

    def __init__(self, window_s: float = 60.0):
        super().__init__()
        self._window_s = float(window_s)

        layout = QtWidgets.QVBoxLayout(self)

        self.plot = pg.PlotWidget(title="Overlay (normalized) — Speed, RPM, Throttle, Brake")
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.setLabel("left", "normalized", units="")
        self.plot.setLabel("bottom", "time", units="s")
        self.plot.addLegend(offset=(10, 10))

        self._c_speed = self.plot.plot([], [], pen=PENS["speed"], name="Speed (norm)")
        self._c_rpm = self.plot.plot([], [], pen=PENS["rpm"], name="RPM (norm)")
        self._c_thr = self.plot.plot([], [], pen=PENS["throttle"], name="Throttle (0–100)")
        self._c_brk = self.plot.plot([], [], pen=PENS["brake"], name="Brake (0–100)")

        layout.addWidget(self.plot)

        note = QtWidgets.QLabel(
            "Note: Speed and RPM are normalized to 0–100 so they can be compared visually with throttle/brake."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(note)

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
