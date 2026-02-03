# src/ui/main_window.py
from __future__ import annotations

from PySide6 import QtCore, QtWidgets, QtGui
import pyqtgraph as pg

from src.core.race_state import RaceState
from src.core.telemetry_session import TelemetrySession
from src.ui.track_map import TrackMapWidget
from src.ui.graphs import GraphsWidget, GraphsOverlayWidget
from src.ui.telemetry_table import TelemetryTableWidget
from src.ui.corner_table import CornerTableWidget
from src.ui.settings_tab import SettingsTab
from src.ui.track_map_3d import TrackMap3DWidget


class MainWindow(QtWidgets.QMainWindow):
    sig_force_ip = QtCore.Signal(str)

    sig_apply_settings = QtCore.Signal(dict)
    sig_start_new_run = QtCore.Signal()
    sig_open_run_dir = QtCore.Signal()
    sig_export_dataset = QtCore.Signal()

    sig_apply_run_metadata = QtCore.Signal(dict)
    sig_start_new_run_with_meta = QtCore.Signal(dict)

    # Reference controls
    sig_set_reference_best = QtCore.Signal()
    sig_toggle_reference_lock = QtCore.Signal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GT7 Race Engineer")
        self.resize(980, 720)

        self._analysis_n = 300

        self.setDockOptions(
            QtWidgets.QMainWindow.DockOption.AllowTabbedDocks
            | QtWidgets.QMainWindow.DockOption.AllowNestedDocks
            | QtWidgets.QMainWindow.DockOption.AnimatedDocks
        )

        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        self.overview = QtWidgets.QWidget()
        self.tabs.addTab(self.overview, "Overview")
        self._build_overview_ui(self.overview)

        self.telemetry_table = TelemetryTableWidget()
        self.tabs.addTab(self.telemetry_table, "Telemetry (All Fields)")

        self.settings_tab = SettingsTab()
        self.tabs.addTab(self.settings_tab, "Research/Config")

        self.settings_tab.sig_apply.connect(self.sig_apply_settings.emit)
        self.settings_tab.sig_start_new_run.connect(self.sig_start_new_run.emit)
        self.settings_tab.sig_open_run_dir.connect(self.sig_open_run_dir.emit)
        self.settings_tab.sig_export_dataset.connect(self.sig_export_dataset.emit)

        self.settings_tab.sig_apply_run_metadata.connect(self.sig_apply_run_metadata.emit)
        self.settings_tab.sig_start_new_run_with_meta.connect(self.sig_start_new_run_with_meta.emit)

        self.settings_tab.sig_set_reference_best.connect(self.sig_set_reference_best.emit)
        self.settings_tab.sig_toggle_reference_lock.connect(self.sig_toggle_reference_lock.emit)

        self.track_map = TrackMapWidget()
        self.track_map_3d = TrackMap3DWidget()
        self.graphs = GraphsWidget()
        self.graphs_overlay = GraphsOverlayWidget()
        self.corner_table = CornerTableWidget()

        self.dock_track = self._make_dock("Track Map", self.track_map)
        self.dock_graphs = self._make_dock("Graphs", self.graphs)
        self.dock_graphs_overlay = self._make_dock("Graphs (Overlay)", self.graphs_overlay)
        self.dock_corners = self._make_dock("Corners", self.corner_table)
        self.dock_track_3d = self._make_dock("Track Map (3D)", self.track_map_3d)

        self.dock_track_3d.topLevelChanged.connect(self._on_track3d_top_level_changed)

        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_track)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_track_3d)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_graphs)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_graphs_overlay)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_corners)

        self.tabifyDockWidget(self.dock_track, self.dock_graphs)
        self.tabifyDockWidget(self.dock_track, self.dock_track_3d)
        self.tabifyDockWidget(self.dock_track, self.dock_graphs_overlay)
        self.tabifyDockWidget(self.dock_track, self.dock_corners)
        self.dock_track.raise_()

        try:
            self.resizeDocks([self.dock_track], [380], QtCore.Qt.Horizontal)
        except Exception:
            pass

        self._settings = QtCore.QSettings("GT7RaceEngineer", "GT7RaceEngineerApp")
        theme_default = self._settings.value("ui/theme", "studio_gray", type=str)

        menubar = self.menuBar()
        view_menu = menubar.addMenu("View")
        theme_menu = view_menu.addMenu("Theme")

        self._theme_group = QtGui.QActionGroup(self)
        self._theme_group.setExclusive(True)

        def add_theme_action(label: str, key: str) -> QtGui.QAction:
            act = QtGui.QAction(label, self)
            act.setCheckable(True)
            act.setData(key)
            self._theme_group.addAction(act)
            theme_menu.addAction(act)
            return act

        self.act_theme_light = add_theme_action("Light (White)", "light")
        self.act_theme_gray = add_theme_action("Studio Gray", "studio_gray")
        self.act_theme_dark = add_theme_action("Dark (Near-black)", "dark")

        matched = False
        for act in self._theme_group.actions():
            if str(act.data()) == str(theme_default):
                act.setChecked(True)
                matched = True
                break
        if not matched:
            self.act_theme_gray.setChecked(True)
            theme_default = "studio_gray"

        self._theme_group.triggered.connect(self._on_theme_selected)
        self._apply_theme(str(theme_default))

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

    @QtCore.Slot(bool)
    def _on_track3d_top_level_changed(self, floating: bool) -> None:
        QtCore.QTimer.singleShot(50, self.track_map_3d.recover_gl_context)

    def set_controller(self, controller):
        self._controller = controller

    def set_analysis_bins(self, n: int) -> None:
        try:
            n = int(n)
        except Exception:
            n = 300
        self._analysis_n = max(50, min(n, 5000))

    def set_current_run_info(self, *, run_id: str | None, run_dir: str | None,
                             track_name: str | None, car_name: str | None, run_alias: str | None) -> None:
        self.settings_tab.set_current_run_info(
            run_id=run_id,
            run_dir=run_dir,
            track_name=track_name,
            car_name=car_name,
            run_alias=run_alias,
        )

    def set_reference_info(self, *, lap_num: int | None, lap_time_ms: int | None, locked: bool) -> None:
        self.settings_tab.set_reference_info(lap_num=lap_num, lap_time_ms=lap_time_ms, locked=locked)

    def set_qa_summary(self, text: str) -> None:
        self.settings_tab.set_qa_summary(text)

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

        controls.addStretch(1)

        self.event_log = QtWidgets.QPlainTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setMaximumBlockCount(2000)
        layout.addWidget(self.event_log, stretch=1)

    def _emit_set_ip(self):
        self.sig_force_ip.emit(self.ip_edit.text())

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

        if getattr(state, "fuel_capacity", 0) and state.fuel_capacity > 0:
            self.val_fuel.setText(f"{state.fuel:.1f} ({state.fuel_pct:.0f}%)")
        else:
            self.val_fuel.setText(f"{state.fuel:.1f}")

        self.val_last.setText(getattr(state, "last_lap_str", "--:--.---"))
        self.val_best.setText(getattr(state, "best_lap_str", "--:--.---"))

    def update_visualizations(self, session: TelemetrySession, snap: dict) -> None:
        n = getattr(self, "_analysis_n", 300)

        try:
            self.track_map.update_from_session(session, n=n)
        except TypeError:
            self.track_map.update_from_session(session)

        if hasattr(self, "track_map_3d") and self.track_map_3d is not None:
            try:
                self.track_map_3d.update_from_session(session)
            except Exception:
                pass

        self.graphs.update_from_session(session)
        self.graphs_overlay.update_from_session(session)

        try:
            self.corner_table.update_from_session(session, n=n)
        except TypeError:
            self.corner_table.update_from_session(session)

        self.telemetry_table.update_from_snapshot(session.latest_snapshot())

    def append_event(self, ev) -> None:
        self.event_log.appendPlainText(
            f"[{QtCore.QDateTime.currentDateTime().toString('HH:mm:ss')}] {ev.title} — {ev.speech}"
        )

    @QtCore.Slot(QtGui.QAction)
    def _on_theme_selected(self, action: QtGui.QAction) -> None:
        key = str(action.data())
        self._settings.setValue("ui/theme", key)
        self._apply_theme(key)

    def _apply_theme(self, theme: str) -> None:
        app = QtWidgets.QApplication.instance()
        if app is None:
            return

        app.setStyle("Fusion")
        p = QtGui.QPalette()

        theme = (theme or "studio_gray").strip().lower()

        if theme == "light":
            p.setColor(QtGui.QPalette.Window, QtGui.QColor(245, 245, 245))
            p.setColor(QtGui.QPalette.WindowText, QtGui.QColor(15, 15, 15))
            p.setColor(QtGui.QPalette.Base, QtGui.QColor(255, 255, 255))
            p.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(240, 240, 240))
            p.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(255, 255, 255))
            p.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(15, 15, 15))
            p.setColor(QtGui.QPalette.Text, QtGui.QColor(15, 15, 15))
            p.setColor(QtGui.QPalette.Button, QtGui.QColor(240, 240, 240))
            p.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(15, 15, 15))
            p.setColor(QtGui.QPalette.Highlight, QtGui.QColor(38, 79, 120))
            p.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255))
            p.setColor(QtGui.QPalette.Link, QtGui.QColor(0, 102, 204))

            app.setPalette(p)
            pg.setConfigOption("background", "w")
            pg.setConfigOption("foreground", "k")
            app.setStyleSheet("QToolTip { color: #111; background-color: #fff; border: 1px solid #888; }")

        elif theme == "dark":
            p.setColor(QtGui.QPalette.Window, QtGui.QColor(18, 18, 18))
            p.setColor(QtGui.QPalette.WindowText, QtGui.QColor(220, 220, 220))
            p.setColor(QtGui.QPalette.Base, QtGui.QColor(25, 25, 25))
            p.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(35, 35, 35))
            p.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(255, 255, 255))
            p.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(255, 255, 255))
            p.setColor(QtGui.QPalette.Text, QtGui.QColor(220, 220, 220))
            p.setColor(QtGui.QPalette.Button, QtGui.QColor(35, 35, 35))
            p.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(220, 220, 220))
            p.setColor(QtGui.QPalette.BrightText, QtGui.QColor(255, 0, 0))
            p.setColor(QtGui.QPalette.Highlight, QtGui.QColor(38, 79, 120))
            p.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255))
            p.setColor(QtGui.QPalette.Link, QtGui.QColor(80, 170, 255))

            app.setPalette(p)
            pg.setConfigOption("background", (18, 18, 18))
            pg.setConfigOption("foreground", (220, 220, 220))
            app.setStyleSheet("QToolTip { color: #ffffff; background-color: #2b2b2b; border: 1px solid #555; }")

        else:
            p.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
            p.setColor(QtGui.QPalette.WindowText, QtGui.QColor(230, 230, 230))
            p.setColor(QtGui.QPalette.Base, QtGui.QColor(42, 42, 42))
            p.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(60, 60, 60))
            p.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(255, 255, 255))
            p.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(255, 255, 255))
            p.setColor(QtGui.QPalette.Text, QtGui.QColor(230, 230, 230))
            p.setColor(QtGui.QPalette.Button, QtGui.QColor(60, 60, 60))
            p.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(230, 230, 230))
            p.setColor(QtGui.QPalette.BrightText, QtGui.QColor(255, 0, 0))
            p.setColor(QtGui.QPalette.Highlight, QtGui.QColor(90, 135, 200))
            p.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(0, 0, 0))
            p.setColor(QtGui.QPalette.Link, QtGui.QColor(80, 170, 255))

            app.setPalette(p)
            pg.setConfigOption("background", (35, 35, 35))
            pg.setConfigOption("foreground", (230, 230, 230))
            app.setStyleSheet("QToolTip { color: #ffffff; background-color: #2b2b2b; border: 1px solid #555; }")
