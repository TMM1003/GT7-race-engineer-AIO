# src/ui/corner_table.py
from __future__ import annotations

from PySide6 import QtWidgets, QtCore

from src.core.telemetry_session import TelemetrySession, CornerSegment


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

        self.table = QtWidgets.QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["#", "Start %", "End %", "Dir", "Loss (ms)", "ΔBrake (m)", "ΔThrottle (m)", "ΔMinSpd", "ΔExitSpd"]
        )

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

    def update_from_session(self, session: TelemetrySession, n: int = 300) -> None:
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

        rows = session.corner_coaching_rows(last, ref, n=n)
        if rows is None:
            self.clear()
            return

        # show top N
        top_n = 12
        rows = rows[:top_n]

        self.table.setRowCount(len(rows))

        def qitem(txt: str) -> QtWidgets.QTableWidgetItem:
            it = QtWidgets.QTableWidgetItem(txt)
            it.setTextAlignment(QtCore.Qt.AlignCenter)
            return it

        def fmt_opt(x, fmt: str = "{:+.1f}") -> str:
            return "—" if x is None else fmt.format(float(x))

        for r, row in enumerate(rows):
            seg: CornerSegment = row["seg"]
            loss_ms: float = float(row["loss_ms"])

            den = float(max(1, n - 1))
            start_pct = 100.0 * (seg.start_idx / den)
            end_pct = 100.0 * (seg.end_idx / den)


            if seg.direction > 0:
                d = "R"
            elif seg.direction < 0:
                d = "L"
            else:
                d = "?"

            bdm = row.get("brake_start_delta_m")
            tdm = row.get("throttle_on_delta_m")
            dmin = float(row.get("min_speed_delta_kmh", 0.0))
            dexit = float(row.get("exit_speed_delta_kmh", 0.0))

            self.table.setItem(r, 0, qitem(str(r + 1)))
            self.table.setItem(r, 1, qitem(f"{start_pct:.1f}"))
            self.table.setItem(r, 2, qitem(f"{end_pct:.1f}"))
            self.table.setItem(r, 3, qitem(d))
            self.table.setItem(r, 4, qitem(f"{loss_ms:.0f}"))
            self.table.setItem(r, 5, qitem(fmt_opt(bdm, "{:+.1f}")))
            self.table.setItem(r, 6, qitem(fmt_opt(tdm, "{:+.1f}")))
            self.table.setItem(r, 7, qitem(f"{dmin:+.1f}"))
            self.table.setItem(r, 8, qitem(f"{dexit:+.1f}"))

        self.table.resizeColumnsToContents()
