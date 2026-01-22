# src/ui/track_map.py
from __future__ import annotations

from PySide6 import QtWidgets
import pyqtgraph as pg

from src.core.telemetry_session import TelemetrySession


class TrackMapWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)

        self.plot = pg.PlotWidget(title="Track Map (X vs Z)")
        self.plot.setAspectLocked(True)
        self.plot.showGrid(x=True, y=True, alpha=0.2)

        self._lap_items: list[pg.PlotDataItem] = []
        self._car_dot = pg.ScatterPlotItem(size=10)
        self.plot.addItem(self._car_dot)

        layout.addWidget(self.plot)

    def update_from_session(self, session: TelemetrySession) -> None:
        lines = session.lap_lines()

        # Ensure we have enough plot items
        while len(self._lap_items) < len(lines):
            item = self.plot.plot([], [], pen=pg.mkPen(width=2))
            self._lap_items.append(item)

        # Update lines
        for i, pts in enumerate(lines):
            if not pts:
                self._lap_items[i].setData([], [])
                continue
            xs = [p[0] for p in pts]
            zs = [p[1] for p in pts]
            self._lap_items[i].setData(xs, zs)

        # Hide extras if fewer lines now
        for j in range(len(lines), len(self._lap_items)):
            self._lap_items[j].setData([], [])

        # Update car dot (last point of last line)
        if lines and lines[-1]:
            x, z = lines[-1][-1]
            self._car_dot.setData([x], [z])
