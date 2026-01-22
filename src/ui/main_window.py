# src/ui/main_window.py
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from src.core.race_state import RaceState
from src.core.telemetry_session import TelemetrySession
from src.ui.track_map import TrackMapWidget
from src.ui.graphs import GraphsWidget
from src.ui.telemetry_table import TelemetryTableWidget


class MainWindow(QtWidgets.QMainWindow):
    sig_toggle_voice = QtCore.Signal(bool)
    sig_force_ip = QtCore.Signal(str)
    sig_speak_now = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GT7 Race Engineer")
        self.resize(980, 720)

        # --- Tabs container ---
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        # --- Overview tab (your existing UI, almost unchanged) ---
        self.overview = QtWidgets.QWidget()
        self.tabs.addTab(self.overview, "Overview")
        self._build_overview_ui(self.overview)

        # --- New tabs ---
        self.track_map = TrackMapWidget()
        self.tabs.addTab(self.track_map, "Track Map")

        self.graphs = GraphsWidget()
        self.tabs.addTab(self.graphs, "Graphs")

        self.telemetry_table = TelemetryTableWidget()
        self.tabs.addTab(self.telemetry_table, "Telemetry (All Fields)")

    def set_controller(self, controller):
        self._controller = controller

    # --------------------
    # Overview UI builder
    # --------------------
    def _build_overview_ui(self, parent: QtWidgets.QWidget) -> None:
        layout = QtWidgets.QVBoxLayout(parent)

        top = QtWidgets.QHBoxLayout()
        layout.addLayout(top)

        self.lbl_status = QtWidgets.QLabel("● DISCONNECTED")
        self.lbl_status.setStyleSheet("font-weight: 700; color: #c0392b;")
        top.addWidget(self.lbl_status)

        top.addStretch(1)

        self.ip_edit = QtWidgets.QLineEdit()
        self.ip_edit.setPlaceholderText("PS5 IP (optional)")
        self.ip_edit.setMaximumWidth(180)
        top.addWidget(self.ip_edit)

        self.btn_set_ip = QtWidgets.QPushButton("Set IP")
        self.btn_set_ip.clicked.connect(self._emit_set_ip)
        top.addWidget(self.btn_set_ip)

        grid = QtWidgets.QGridLayout()
        layout.addLayout(grid)

        def add_row(r, name):
            grid.addWidget(QtWidgets.QLabel(name), r, 0)
            val = QtWidgets.QLabel("--")
            val.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            val.setStyleSheet("font-weight: 600;")
            grid.addWidget(val, r, 1)
            return val

        self.val_ip = add_row(0, "PS5 IP")
        self.val_lap = add_row(1, "Lap")
        self.val_speed = add_row(2, "Speed (km/h)")
        self.val_rpm = add_row(3, "RPM")
        self.val_throttle = add_row(4, "Throttle (%)")
        self.val_brake = add_row(5, "Brake (%)")
        self.val_fuel = add_row(6, "Fuel")
        self.val_last = add_row(7, "Last Lap")
        self.val_best = add_row(8, "Best Lap")

        controls = QtWidgets.QHBoxLayout()
        layout.addLayout(controls)

        self.chk_voice = QtWidgets.QCheckBox("Voice Enabled")
        self.chk_voice.setChecked(True)
        self.chk_voice.toggled.connect(self.sig_toggle_voice.emit)
        controls.addWidget(self.chk_voice)

        self.btn_speak = QtWidgets.QPushButton("Speak Now")
        self.btn_speak.clicked.connect(self.sig_speak_now.emit)
        controls.addWidget(self.btn_speak)

        controls.addStretch(1)

        self.event_log = QtWidgets.QPlainTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setMaximumBlockCount(2000)
        layout.addWidget(self.event_log, stretch=1)

    def _emit_set_ip(self):
        self.sig_force_ip.emit(self.ip_edit.text())

    # --------------------
    # Existing behavior
    # --------------------
    def update_state(self, state: RaceState, snap: dict) -> None:
        if state.connected:
            self.lbl_status.setText("● CONNECTED")
            self.lbl_status.setStyleSheet("font-weight: 700; color: #27ae60;")
        else:
            self.lbl_status.setText("● DISCONNECTED")
            self.lbl_status.setStyleSheet("font-weight: 700; color: #c0392b;")

        self.val_ip.setText(str(state.ip or "--"))
        self.val_lap.setText(f"{state.lap} / {state.total_laps}" if state.total_laps else str(state.lap))
        self.val_speed.setText(f"{state.speed_kmh:.1f}")
        self.val_rpm.setText(f"{state.rpm:.0f}")
        self.val_throttle.setText(f"{state.throttle:.0f}")
        self.val_brake.setText(f"{state.brake:.0f}")

        if state.fuel_capacity > 0:
            self.val_fuel.setText(f"{state.fuel:.1f} ({state.fuel_pct:.0f}%)")
        else:
            self.val_fuel.setText(f"{state.fuel:.1f}")

        self.val_last.setText(state.last_lap_str)
        self.val_best.setText(state.best_lap_str)

    def update_visualizations(self, session: TelemetrySession, snap: dict) -> None:
        """
        NEW: called by AppController every tick. Keeps the heavy visual work out of update_state().
        """
        self.track_map.update_from_session(session)
        self.graphs.update_from_session(session)
        self.telemetry_table.update_from_snapshot(session.latest_snapshot())

    def append_event(self, ev) -> None:
        self.event_log.appendPlainText(
            f"[{QtCore.QDateTime.currentDateTime().toString('HH:mm:ss')}] {ev.title} — {ev.speech}"
        )