# src/ui/telemetry_table.py
from __future__ import annotations

from PySide6 import QtWidgets


class TelemetryTableWidget(QtWidgets.QTableWidget):
    def __init__(self):
        super().__init__(0, 2)
        self.setHorizontalHeaderLabels(["Field", "Value"])
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)

    def update_from_snapshot(self, snap: dict) -> None:
        self.setRowCount(0)
        # stable ordering: sort keys
        for k in sorted(snap.keys()):
            v = snap[k]
            r = self.rowCount()
            self.insertRow(r)
            self.setItem(r, 0, QtWidgets.QTableWidgetItem(str(k)))
            self.setItem(r, 1, QtWidgets.QTableWidgetItem(str(v)))
