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
from pathlib import Path
from src.gt7db.loader import GT7Database


class MainWindow(QtWidgets.QMainWindow):
    sig_force_ip = QtCore.Signal(str)
    sig_speak_now = QtCore.Signal()

    sig_apply_settings = QtCore.Signal(dict)
    sig_start_new_run = QtCore.Signal()
    sig_open_run_dir = QtCore.Signal()
    sig_export_dataset = QtCore.Signal()
    # Run metadata
    sig_apply_run_metadata = QtCore.Signal(dict)
    sig_start_new_run_with_meta = QtCore.Signal(dict)

    def __init__(self):
        super().__init__()
        self.settings_tab = SettingsTab()
        self.setWindowTitle("GT7 Race Engineer")
        self.resize(980, 720)

        # Dock behavior: tabbed docks, nested docks, animations
        self.setDockOptions(
            QtWidgets.QMainWindow.DockOption.AllowTabbedDocks
            | QtWidgets.QMainWindow.DockOption.AllowNestedDocks
            | QtWidgets.QMainWindow.DockOption.AnimatedDocks
        )

        # Central Tabs
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        # Overview tab
        self.overview = QtWidgets.QWidget()
        self.tabs.addTab(self.overview, "Overview")
        self._build_overview_ui(self.overview)

        # Telemetry table stays as a normal tab
        self.telemetry_table = TelemetryTableWidget()
        self.tabs.addTab(self.telemetry_table, "Telemetry (All Fields)")

        # Settings / Research tab
        self.settings_tab = SettingsTab()
        self.tabs.addTab(self.settings_tab, "Research/Config")

        self._gt7db = None
        try:
            db_root = Path("src/gt7db")
            # expects: gt7_car.csv, gt7_venues.csv, gt7_layouts.csv
            self._gt7db = GT7Database.load(db_root)
            self.settings_tab.set_gt7_database(self._gt7db)
        except Exception:
            # best-effort: app should still run even if db isn't present
            self._gt7db = None

        # Forward signals
        self.settings_tab.sig_apply.connect(self.sig_apply_settings.emit)
        self.settings_tab.sig_start_new_run.connect(
            self.sig_start_new_run.emit
        )
        self.settings_tab.sig_open_run_dir.connect(self.sig_open_run_dir.emit)

        # Run metadata (SettingsTab -> MainWindow)
        if hasattr(self.settings_tab, "sig_apply_run_metadata"):
            self.settings_tab.sig_apply_run_metadata.connect(
                self.sig_apply_run_metadata.emit
            )
        if hasattr(self.settings_tab, "sig_start_new_run_with_meta"):
            self.settings_tab.sig_start_new_run_with_meta.connect(
                self.sig_start_new_run_with_meta.emit
            )

        # Export dataset signal (new)
        if hasattr(self.settings_tab, "sig_export_dataset"):
            self.settings_tab.sig_export_dataset.connect(
                self.sig_export_dataset.emit
            )
        elif hasattr(self.settings_tab, "btn_export_dataset"):
            self.settings_tab.btn_export_dataset.clicked.connect(
                self.sig_export_dataset.emit
            )

        # Dockable Panels
        self.track_map = TrackMapWidget()
        self.graphs = GraphsWidget()
        self.graphs_overlay = GraphsOverlayWidget()
        self.corner_table = CornerTableWidget()

        # Standardize dock attribute names
        self.dock_track = self._make_dock("Track Map", self.track_map)
        self.dock_graphs = self._make_dock("Graphs", self.graphs)
        self.dock_graphs_overlay = self._make_dock(
            "Graphs (Overlay)", self.graphs_overlay
        )
        self.dock_corners = self._make_dock("Corners", self.corner_table)

        # Add docks to the right area
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_track)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_graphs)
        self.addDockWidget(
            QtCore.Qt.RightDockWidgetArea, self.dock_graphs_overlay
        )
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.dock_corners)

        # Tabify into one dock stack
        self.tabifyDockWidget(self.dock_track, self.dock_graphs)
        self.tabifyDockWidget(self.dock_track, self.dock_graphs_overlay)
        self.tabifyDockWidget(self.dock_track, self.dock_corners)
        self.dock_track.raise_()

        # Optional: size docks
        try:
            self.resizeDocks([self.dock_track], [380], QtCore.Qt.Horizontal)
        except Exception:
            pass

        # Theme preference + menu
        self._settings = QtCore.QSettings(
            "GT7RaceEngineer", "GT7RaceEngineerApp"
        )
        theme_default = self._settings.value(
            "ui/theme", "studio_gray", type=str
        )

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
            act.triggered.connect(lambda: self._apply_theme(key))
            return act

        self._theme_actions = {
            "studio_gray": add_theme_action("Studio Gray", "studio_gray"),
            "dark": add_theme_action("Dark", "dark"),
        }

        if theme_default in self._theme_actions:
            self._theme_actions[theme_default].setChecked(True)
        else:
            self._theme_actions["studio_gray"].setChecked(True)

        self._apply_theme(
            theme_default
            if theme_default in self._theme_actions
            else "studio_gray"
        )

        def set_controller(self, controller: object) -> None:
            self._controller = controller

        def set_current_run_info(
            self,
            run_id: str,
            run_dir: str,
            track: str | None = None,
            car: str | None = None,
            alias: str | None = None,
        ) -> None:
            if hasattr(self, "settings_tab") and hasattr(
                self.settings_tab, "set_current_run_info"
            ):
                self.settings_tab.set_current_run_info(
                    run_id, run_dir, track=track, car=car, alias=alias
                )

        def set_reference_info(
            self, ref_lap: int | None, ref_time_ms: int | None
        ) -> None:
            if hasattr(self, "settings_tab") and hasattr(
                self.settings_tab, "set_reference_info"
            ):
                self.settings_tab.set_reference_info(ref_lap, ref_time_ms)

    def _make_dock(
        self, title: str, widget: QtWidgets.QWidget
    ) -> QtWidgets.QDockWidget:
        dock = QtWidgets.QDockWidget(title, self)
        dock.setWidget(widget)
        dock.setObjectName(title.replace(" ", "_").lower())
        dock.setAllowedAreas(
            QtCore.Qt.LeftDockWidgetArea
            | QtCore.Qt.RightDockWidgetArea
            | QtCore.Qt.BottomDockWidgetArea
            | QtCore.Qt.TopDockWidgetArea
        )
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        return dock

    def _apply_theme(self, key: str) -> None:
        # Save
        self._settings.setValue("ui/theme", key)

        # Simple palette themes
        app = QtWidgets.QApplication.instance()
        if not app:
            return

        if key == "dark":
            palette = QtGui.QPalette()
            palette.setColor(QtGui.QPalette.Window, QtGui.QColor(30, 30, 30))
            palette.setColor(
                QtGui.QPalette.WindowText, QtGui.QColor(220, 220, 220)
            )
            palette.setColor(QtGui.QPalette.Base, QtGui.QColor(20, 20, 20))
            palette.setColor(
                QtGui.QPalette.AlternateBase, QtGui.QColor(30, 30, 30)
            )
            palette.setColor(QtGui.QPalette.Text, QtGui.QColor(220, 220, 220))
            palette.setColor(QtGui.QPalette.Button, QtGui.QColor(45, 45, 45))
            palette.setColor(
                QtGui.QPalette.ButtonText, QtGui.QColor(220, 220, 220)
            )
            palette.setColor(
                QtGui.QPalette.Highlight, QtGui.QColor(70, 70, 120)
            )
            palette.setColor(
                QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255)
            )
            app.setPalette(palette)
        else:
            app.setPalette(app.style().standardPalette())

    def _build_overview_ui(self, parent: QtWidgets.QWidget) -> None:
        layout = QtWidgets.QVBoxLayout(parent)

        top_row = QtWidgets.QHBoxLayout()
        layout.addLayout(top_row)

        self.lbl_status = QtWidgets.QLabel("DISCONNECTED")
        self.lbl_status.setStyleSheet("color: #cc4444; font-weight: bold;")
        top_row.addWidget(self.lbl_status)

        top_row.addStretch(1)

        ip_row = QtWidgets.QHBoxLayout()
        layout.addLayout(ip_row)

        ip_row.addWidget(QtWidgets.QLabel("PS5 IP (optional)"))
        self.edit_ip = QtWidgets.QLineEdit("")
        self.edit_ip.setPlaceholderText("192.168.x.x")
        ip_row.addWidget(self.edit_ip, 1)

        self.btn_set_ip = QtWidgets.QPushButton("Set IP")
        self.btn_set_ip.clicked.connect(self._emit_force_ip)
        ip_row.addWidget(self.btn_set_ip)

        diag_group = QtWidgets.QGroupBox("Connection Diagnostics")
        diag_grid = QtWidgets.QGridLayout(diag_group)
        layout.addWidget(diag_group)

        def add_diag_row(r: int, name: str) -> QtWidgets.QLabel:
            diag_grid.addWidget(QtWidgets.QLabel(name), r, 0)
            val = QtWidgets.QLabel("N/A")
            val.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            diag_grid.addWidget(val, r, 1)
            return val

        self.val_diag_connected = add_diag_row(0, "Connected")
        self.val_diag_live = add_diag_row(1, "Telemetry Live (In-Race)")
        self.val_diag_mode = add_diag_row(2, "Connection Mode")
        self.val_diag_target_ip = add_diag_row(3, "Configured PS5 IP")
        self.val_diag_active_ip = add_diag_row(4, "Active PS5 IP")
        self.val_diag_rx_age = add_diag_row(5, "Last Packet Age")
        self.val_diag_seq = add_diag_row(6, "Telemetry Sequence")
        self.val_diag_pkg = add_diag_row(7, "Packet ID")
        self.val_diag_paused = add_diag_row(8, "Paused")
        self.val_diag_send_port = add_diag_row(9, "UDP Send Port")
        self.val_diag_recv_port = add_diag_row(10, "UDP Receive Port")
        self.val_diag_bound_port = add_diag_row(11, "UDP Bound Port")
        self.val_diag_error = add_diag_row(12, "Last Error")
        self.val_diag_rx_datagrams = add_diag_row(13, "UDP Datagrams RX")
        self.val_diag_rx_valid = add_diag_row(14, "Valid GT7 Packets")
        self.val_diag_tx_hb = add_diag_row(15, "Heartbeat TX")
        self.val_diag_last_sender = add_diag_row(16, "Last Sender IP")

        # Basic telemetry labels
        grid = QtWidgets.QGridLayout()
        layout.addLayout(grid)

        def add_row(r: int, name: str) -> QtWidgets.QLabel:
            grid.addWidget(QtWidgets.QLabel(name), r, 0)
            val = QtWidgets.QLabel("—")
            grid.addWidget(val, r, 1)
            return val

        self.val_speed = add_row(0, "Speed (km/h)")
        self.val_rpm = add_row(1, "RPM")
        self.val_throttle = add_row(2, "Throttle (%)")
        self.val_brake = add_row(3, "Brake (%)")
        self.val_fuel = add_row(4, "Fuel")
        self.val_lap = add_row(5, "Lap")
        self.val_last_lap = add_row(6, "Last Lap")
        self.val_best_lap = add_row(7, "Best Lap")

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)

    def _emit_force_ip(self) -> None:
        ip = self.edit_ip.text().strip()
        self.sig_force_ip.emit(ip)

    def set_connected(self, connected: bool) -> None:
        if connected:
            self.lbl_status.setText("● CONNECTED")
            self.lbl_status.setStyleSheet("color: #44cc44; font-weight: bold;")
        else:
            self.lbl_status.setText("● DISCONNECTED")
            self.lbl_status.setStyleSheet("color: #cc4444; font-weight: bold;")

    def update_connection_diagnostics(self, diag: dict) -> None:
        def t(v, default: str = "N/A") -> str:
            if v is None:
                return default
            s = str(v).strip()
            return s if s else default

        try:
            self.val_diag_connected.setText(
                "Yes" if bool(diag.get("connected", False)) else "No"
            )
            self.val_diag_live.setText(
                "Yes" if bool(diag.get("in_race", False)) else "No"
            )
            self.val_diag_mode.setText(t(diag.get("mode")))
            self.val_diag_target_ip.setText(t(diag.get("configured_ip")))
            self.val_diag_active_ip.setText(t(diag.get("active_ip")))

            rx_age = diag.get("rx_age_s")
            if rx_age is None:
                self.val_diag_rx_age.setText("N/A")
            else:
                self.val_diag_rx_age.setText(f"{float(rx_age):.3f}s")

            self.val_diag_seq.setText(t(diag.get("telemetry_seq")))
            self.val_diag_pkg.setText(t(diag.get("package_id")))
            self.val_diag_paused.setText(
                "Yes" if bool(diag.get("paused", False)) else "No"
            )
            self.val_diag_send_port.setText(t(diag.get("send_port")))
            self.val_diag_recv_port.setText(t(diag.get("recv_port")))
            self.val_diag_bound_port.setText(t(diag.get("bound_recv_port")))
            self.val_diag_error.setText(
                t(diag.get("connection_error"), default="None")
            )
            self.val_diag_rx_datagrams.setText(
                t(diag.get("rx_datagrams"), default="0")
            )
            self.val_diag_rx_valid.setText(
                t(diag.get("rx_valid_packets"), default="0")
            )
            self.val_diag_tx_hb.setText(
                t(diag.get("tx_heartbeats"), default="0")
            )
            self.val_diag_last_sender.setText(t(diag.get("last_sender_ip")))
        except Exception:
            pass

    def update_state(self, state: RaceState, snap: dict) -> None:
        # Scalar values in the overview panel
        try:
            self.val_speed.setText(f"{snap.get('speed_kmh', 0):.1f}")
            self.val_rpm.setText(str(int(snap.get("rpm", 0))))
            self.val_throttle.setText(f"{snap.get('throttle', 0):.0f}")
            self.val_brake.setText(f"{snap.get('brake', 0):.0f}")
            fuel = snap.get("fuel_percent", None)
            if fuel is None:
                self.val_fuel.setText("—")
            else:
                self.val_fuel.setText(f"{fuel:.1f} ({fuel:.0f}%)")
            self.val_lap.setText(str(int(snap.get("lap", 0))))
            self.val_last_lap.setText(state.last_lap_str or "—")
            self.val_best_lap.setText(state.best_lap_str or "—")
        except Exception:
            pass

    def update_visualizations(
        self, session: TelemetrySession, snap: dict
    ) -> None:
        # Update dock widgets using session buffers
        n = 300
        self.track_map.update_from_session(session, n=n)
        self.graphs.update_from_session(session)
        self.graphs_overlay.update_from_session(session)
        self.corner_table.update_from_session(session, n=n)

    def append_event(self, ev) -> None:
        # Event to log area
        try:
            self.log.appendPlainText(str(ev))
        except Exception:
            pass
