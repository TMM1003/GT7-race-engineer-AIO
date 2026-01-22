# src/ui/graphs.py
from __future__ import annotations

from PySide6 import QtWidgets
import pyqtgraph as pg

from src.core.telemetry_session import TelemetrySession


class GraphsWidget(QtWidgets.QWidget):
    """
    Lightweight live graphs using the TelemetrySession rolling samples.
    Safe to run even when disconnected (it will just show empty/flat data).
    """

    def __init__(self):
        super().__init__()

        layout = QtWidgets.QVBoxLayout(self)

        self._glw = pg.GraphicsLayoutWidget()
        layout.addWidget(self._glw)

        # 4 stacked plots sharing the same x-axis index (sample index)
        self._p_speed = self._glw.addPlot(title="Speed (km/h)")
        self._p_speed.showGrid(x=True, y=True, alpha=0.2)
        self._c_speed = self._p_speed.plot(pen=pg.mkPen(width=2))

        self._glw.nextRow()
        self._p_rpm = self._glw.addPlot(title="RPM")
        self._p_rpm.showGrid(x=True, y=True, alpha=0.2)
        self._c_rpm = self._p_rpm.plot(pen=pg.mkPen(width=2))

        self._glw.nextRow()
        self._p_throttle = self._glw.addPlot(title="Throttle (%)")
        self._p_throttle.setYRange(0, 100)
        self._p_throttle.showGrid(x=True, y=True, alpha=0.2)
        self._c_throttle = self._p_throttle.plot(pen=pg.mkPen(width=2))

        self._glw.nextRow()
        self._p_brake = self._glw.addPlot(title="Brake (%)")
        self._p_brake.setYRange(0, 100)
        self._p_brake.showGrid(x=True, y=True, alpha=0.2)
        self._c_brake = self._p_brake.plot(pen=pg.mkPen(width=2))

    def update_from_session(self, session: TelemetrySession) -> None:
        samples = session.samples()
        if not samples:
            # Clear plots when nothing is available
            self._c_speed.setData([], [])
            self._c_rpm.setData([], [])
            self._c_throttle.setData([], [])
            self._c_brake.setData([], [])
            return

        # Use sample index as x axis (cheap and stable)
        xs = list(range(len(samples)))

        speed = [s.speed_kmh for s in samples]
        rpm = [s.rpm for s in samples]
        throttle = [s.throttle for s in samples]
        brake = [s.brake for s in samples]

        self._c_speed.setData(xs, speed)
        self._c_rpm.setData(xs, rpm)
        self._c_throttle.setData(xs, throttle)
        self._c_brake.setData(xs, brake)