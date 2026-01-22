# src/ui/corner_table.py
from __future__ import annotations

from PySide6 import QtWidgets, QtCore

from src.core.telemetry_session import TelemetrySession, LapData, CornerSegment


class CornerTableWidget(QtWidgets.QWidget):
    """
    Shows detected corners and time loss per corner (ranked).
    """

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Corner Time Loss (last vs reference)")
        title.setStyleSheet("font-weight: 700;")
        layout.addWidget(title)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "Start %", "End %", "Dir", "Loss (ms)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        layout.addWidget(self.table)

        self.note = QtWidgets.QLabel(
            "Corners are auto-detected from the reference lap curvature; loss is Δt(exit) − Δt(entry)."
        )
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(self.note)

        # cache so we don't recompute corner segments constantly
        self._cache_ref_key = None  # (session_id, ref_lap_num)
        self._cache = None

    def clear(self) -> None:
        self.table.setRowCount(0)

    def update_from_session(self, session: TelemetrySession) -> None:
        laps = session.completed_laps()
        if len(laps) < 2:
            self.clear()
            return

        ref = session.reference_lap()
        last = laps[-1] if laps else None
        if ref is None or last is None:
            self.clear()
            return

        # Avoid comparing ref against itself if ref is also the last
        if ref.lap_num == last.lap_num and len(laps) >= 2:
            last = laps[-2]

        if last is None or last.lap_num == ref.lap_num:
            self.clear()
            return

        losses = session.corner_time_losses_ms(last, ref, n=300)
        if losses is None:
            self.clear()
            return

        # show top N
        top_n = 12
        rows = losses[:top_n]

        self.table.setRowCount(len(rows))

        def qitem(txt: str) -> QtWidgets.QTableWidgetItem:
            it = QtWidgets.QTableWidgetItem(txt)
            it.setTextAlignment(QtCore.Qt.AlignCenter)
            return it

        for r, (seg, loss_ms) in enumerate(rows, start=0):
            start_pct = 100.0 * (seg.start_idx / 299.0)
            end_pct = 100.0 * (seg.end_idx / 299.0)

            if seg.direction > 0:
                d = "R"
            elif seg.direction < 0:
                d = "L"
            else:
                d = "?"

            self.table.setItem(r, 0, qitem(str(r + 1)))
            self.table.setItem(r, 1, qitem(f"{start_pct:.1f}"))
            self.table.setItem(r, 2, qitem(f"{end_pct:.1f}"))
            self.table.setItem(r, 3, qitem(d))
            self.table.setItem(r, 4, qitem(f"{loss_ms:.0f}"))

        self.table.resizeColumnsToContents()
