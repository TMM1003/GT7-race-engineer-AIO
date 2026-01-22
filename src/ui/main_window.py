# src/ui/main_window.py
from __future__ import annotations

from PySide6 import QtCore, QtWidgets, QtGui
import pyqtgraph as pg

from src.core.race_state import RaceState
from src.core.telemetry_session import TelemetrySession
from src.ui.track_map import TrackMapWidget
from src.ui.graphs import GraphsWidget, GraphsOverlayWidget
from src.ui.telemetry_table import TelemetryTableWidget


class MainWindow(QtWidgets.QMainWindow):
    sig_toggle_voice = QtCore.Signal(bool)
    sig_force_ip = QtCore.Signal(str)
    sig_speak_now = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GT7 Race Engineer")
        self.resize(980, 720)

        # Enable dock behavior: tabbed docks, nested docks, animations.
        self.setDockOptions(
            QtWidgets.QMainWindow.DockOption.AllowTabbedDocks
            | QtWidgets.QMainWindow.DockOption.AllowNestedDocks
            | QtWidgets.QMainWindow.DockOption.AnimatedDocks
        )

        # Central Tabs (keep lightweight "pages" here)
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        # Overview tab (existing UI)
        self.overview = QtWidgets.QWidget()
        self.tabs.addTab(self.overview, "Overview")
        self._build_overview_ui(self.overview)

        # Telemetry table stays as a normal tab (it benefits from full-page space)
        self.telemetry_table = TelemetryTableWidget()
        self.tabs.addTab(self.telemetry_table, "Telemetry (All Fields)")

        # Dockable Panels (map + graphs visible simultaneously / floatable windows)
        self.track_map = TrackMapWidget()
        self.graphs = GraphsWidget()
        self.graphs_overlay = GraphsOverlayWidget()

        self.dock_track = self._make_dock("Track Map", self.track_map)
        self.dock_graphs = self._make_dock("Graphs", self.graphs)
        self.dock_graphs_overlay = self._make_dock("Graphs (Overlay)", self.graphs_overlay)

        # Default layout:
        # - Track Map on the right
        # - Graphs tabified with Track Map
        # - Graphs (Overlay) tabified as well (same dock area)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_track)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_graphs)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_graphs_overlay)

        # Tabify (creates a single dock area with tabs)
        self.tabifyDockWidget(self.dock_track, self.dock_graphs)
        self.tabifyDockWidget(self.dock_track, self.dock_graphs_overlay)
        self.dock_track.raise_()

        # Optional: give the central tabs more room by starting docks narrower
        # (user can resize/undock as they like)
        try:
            self.resizeDocks([self.dock_track], [360], QtCore.Qt.Horizontal)
        except Exception:
            pass
        # ---- Theme preference (persisted) ----
        self._settings = QtCore.QSettings("GT7RaceEngineer", "GT7RaceEngineerApp")
        dark_default = self._settings.value("ui/dark_mode", True, type=bool)

        # ---- Menu ----
        menubar = self.menuBar()
        view_menu = menubar.addMenu("View")

        self.act_dark_mode = QtGui.QAction("Dark Mode", self)
        self.act_dark_mode.setCheckable(True)
        self.act_dark_mode.setChecked(bool(dark_default))
        self.act_dark_mode.toggled.connect(self._on_toggle_dark_mode)
        view_menu.addAction(self.act_dark_mode)

        # Apply immediately
        self._apply_theme(bool(dark_default))


    def _make_dock(self, title: str, widget: QtWidgets.QWidget) -> QtWidgets.QDockWidget:
        dock = QtWidgets.QDockWidget(title, self)
        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetClosable
        )
        return dock

    def set_controller(self, controller):
        self._controller = controller

    # Overview UI builder
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

    # Existing behavior
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
        Called by AppController every tick. Keeps the heavy visual work out of update_state().
        Docked widgets are still normal widgets, so updates remain the same.
        """
        self.track_map.update_from_session(session)
        self.graphs.update_from_session(session)
        self.graphs_overlay.update_from_session(session)
        self.telemetry_table.update_from_snapshot(session.latest_snapshot())

    def append_event(self, ev) -> None:
        self.event_log.appendPlainText(
            f"[{QtCore.QDateTime.currentDateTime().toString('HH:mm:ss')}] {ev.title} — {ev.speech}"
        )

    def _apply_theme(self, dark: bool) -> None:
        # Applies a Fusion-based light/dark palette to the whole app and keeps pyqtgraph consistent.
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        
        app.setStyle("Fusion")
        palette = QtGui.QPalette()

        if dark:
            # Dark palette (Fusion-friendly)
            palette.setColor(QtGui.QPalette.Window, QtGui.QColor(18, 18, 18))
            palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(220, 220, 220))
            palette.setColor(QtGui.QPalette.Base, QtGui.QColor(30, 30, 30))
            palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(45, 45, 45))
            palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(255, 255, 255))
            palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(255, 255, 255))
            palette.setColor(QtGui.QPalette.Text, QtGui.QColor(220, 220, 220))
            palette.setColor(QtGui.QPalette.Button, QtGui.QColor(45, 45, 45))
            palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(220, 220, 220))
            palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor(255, 0, 0))
            palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(38, 79, 120))
            palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255))
            palette.setColor(QtGui.QPalette.Link, QtGui.QColor(80, 170, 255))

            app.setPalette(palette)

            # pyqtgraph colors (global defaults)
            pg.setConfigOption("background", (18, 18, 18))
            pg.setConfigOption("foreground", (220, 220, 220))

            # Optional tooltip styling
            app.setStyleSheet(
                "QToolTip { color: #ffffff; background-color: #2b2b2b; border: 1px solid #555; }"
            )
        else:
            # Light palette reset
            app.setPalette(app.style().standardPalette())
            pg.setConfigOption("background", "w")
            pg.setConfigOption("foreground", "k")
            app.setStyleSheet("")
        
    @QtCore.Slot(bool)
    def _on_toggle_dark_mode(self, enabled: bool) -> None:
        self._settings.setValue("ui/dark_mode", bool(enabled))
        self._apply_theme(bool(enabled))

