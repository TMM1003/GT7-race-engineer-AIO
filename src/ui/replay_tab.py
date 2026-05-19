from __future__ import annotations

from collections.abc import Mapping
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.ui.graph_colors import (
    DEFAULT_GRAPH_COLOR_SETTINGS,
    normalized_graph_color_settings,
)


class ReplayTab(QtWidgets.QWidget):
    sig_replay_load = QtCore.Signal(str)
    sig_replay_lap_changed = QtCore.Signal(int)
    sig_replay_compare_lap_changed = QtCore.Signal(int)
    sig_replay_speed_changed = QtCore.Signal(float)
    sig_replay_loop_changed = QtCore.Signal(bool)
    sig_replay_compare_color_changed = QtCore.Signal(str)
    sig_graph_colors_changed = QtCore.Signal(dict)
    sig_trackdb_overlay_changed = QtCore.Signal(dict)
    sig_replay_play = QtCore.Signal()
    sig_replay_pause = QtCore.Signal()
    sig_replay_restart = QtCore.Signal()
    sig_replay_stop = QtCore.Signal()
    sig_replay_seek = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._current_run_id: Optional[str] = None
        self._current_run_dir: Optional[str] = None
        self._replay_lap_numbers: list[int] = []
        self._replay_reference_lap_num: Optional[int] = None
        self._graph_color_settings = normalized_graph_color_settings(None)
        self._replay_compare_color = self._graph_color_settings["compare"]
        self._color_previews: dict[str, QtWidgets.QLabel] = {}
        self._color_dialog_titles = {
            "compare": "Choose 2nd lap color",
            "graph_speed": "Choose speed graph color",
            "graph_rpm": "Choose RPM graph color",
            "graph_throttle": "Choose throttle graph color",
            "graph_brake": "Choose brake graph color",
            "overlay_speed": "Choose speed overlay color",
            "overlay_rpm": "Choose RPM overlay color",
            "overlay_throttle": "Choose throttle overlay color",
            "overlay_brake": "Choose brake overlay color",
        }

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        root_layout.addWidget(scroll)

        content = QtWidgets.QWidget()
        scroll.setWidget(content)

        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)

        source_box = QtWidgets.QGroupBox("Replay Source")
        source_layout = QtWidgets.QVBoxLayout(source_box)
        source_layout.setContentsMargins(12, 12, 12, 12)
        source_layout.setSpacing(10)

        self.lbl_replay_hint = QtWidgets.QLabel(
            "Load a recorded run and replay a saved lap through the existing graphs for poster capture."
        )
        self.lbl_replay_hint.setWordWrap(True)
        source_layout.addWidget(self.lbl_replay_hint)

        self.lbl_run_hint = QtWidgets.QLabel("Current run: -")
        self.lbl_run_hint.setWordWrap(True)
        source_layout.addWidget(self.lbl_run_hint)

        source_form = QtWidgets.QFormLayout()
        source_form.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow
        )
        source_form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        source_form.setVerticalSpacing(8)

        self.edit_replay_path = QtWidgets.QLineEdit()
        self.edit_replay_path.setPlaceholderText(
            "Choose a run folder containing laps/lap_####.json or .npz files"
        )
        source_form.addRow("Replay source", self.edit_replay_path)

        source_btns = QtWidgets.QHBoxLayout()
        self.btn_browse_replay = QtWidgets.QPushButton("Browse run")
        self.btn_browse_replay.clicked.connect(self._browse_replay_run)
        source_btns.addWidget(self.btn_browse_replay)

        self.btn_load_replay = QtWidgets.QPushButton("Load replay")
        self.btn_load_replay.clicked.connect(self._emit_replay_load)
        source_btns.addWidget(self.btn_load_replay)
        source_btns.addStretch(1)
        source_form.addRow("", source_btns)

        source_layout.addLayout(source_form)
        layout.addWidget(source_box)

        playback_box = QtWidgets.QGroupBox("Playback")
        playback_layout = QtWidgets.QVBoxLayout(playback_box)
        playback_layout.setContentsMargins(12, 12, 12, 12)
        playback_layout.setSpacing(10)

        playback_form = QtWidgets.QFormLayout()
        playback_form.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow
        )
        playback_form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        playback_form.setVerticalSpacing(8)

        self.combo_replay_lap = QtWidgets.QComboBox()
        self.combo_replay_lap.currentIndexChanged.connect(
            self._emit_replay_lap_changed
        )
        playback_form.addRow("Replay lap", self.combo_replay_lap)

        self.lbl_replay_reference = QtWidgets.QLabel("Reference lap: -")
        self.lbl_replay_reference.setWordWrap(True)
        playback_form.addRow("Run reference", self.lbl_replay_reference)

        self.combo_replay_compare_lap = QtWidgets.QComboBox()
        self.combo_replay_compare_lap.currentIndexChanged.connect(
            self._emit_replay_compare_lap_changed
        )
        playback_form.addRow("Compare lap", self.combo_replay_compare_lap)

        self.combo_replay_speed = QtWidgets.QComboBox()
        self.combo_replay_speed.addItem("0.25x", 0.25)
        self.combo_replay_speed.addItem("0.5x", 0.5)
        self.combo_replay_speed.addItem("1.0x", 1.0)
        self.combo_replay_speed.addItem("2.0x", 2.0)
        self.combo_replay_speed.addItem("4.0x", 4.0)
        self.combo_replay_speed.setCurrentIndex(2)
        self.combo_replay_speed.currentIndexChanged.connect(
            self._emit_replay_speed_changed
        )
        playback_form.addRow("Playback speed", self.combo_replay_speed)

        self.chk_replay_loop = QtWidgets.QCheckBox("Restart automatically")
        self.chk_replay_loop.toggled.connect(self._emit_replay_loop_changed)
        playback_form.addRow("Loop replay", self.chk_replay_loop)

        self.lbl_replay_compare_color = QtWidgets.QLabel()
        self.lbl_replay_compare_color.setFixedWidth(84)
        self._color_previews["compare"] = self.lbl_replay_compare_color

        compare_color_row = QtWidgets.QHBoxLayout()
        compare_color_row.addWidget(self.lbl_replay_compare_color)

        self.btn_replay_compare_color = QtWidgets.QPushButton("Pick color")
        self.btn_replay_compare_color.clicked.connect(
            self._choose_replay_compare_color
        )
        compare_color_row.addWidget(self.btn_replay_compare_color)
        compare_color_row.addStretch(1)
        playback_form.addRow("2nd lap color", compare_color_row)

        playback_layout.addLayout(playback_form)

        playback_btns = QtWidgets.QHBoxLayout()
        self.btn_replay_play = QtWidgets.QPushButton("Play")
        self.btn_replay_play.clicked.connect(self.sig_replay_play.emit)
        playback_btns.addWidget(self.btn_replay_play)

        self.btn_replay_pause = QtWidgets.QPushButton("Pause")
        self.btn_replay_pause.clicked.connect(self.sig_replay_pause.emit)
        playback_btns.addWidget(self.btn_replay_pause)

        self.btn_replay_restart = QtWidgets.QPushButton("Restart")
        self.btn_replay_restart.clicked.connect(self.sig_replay_restart.emit)
        playback_btns.addWidget(self.btn_replay_restart)

        self.btn_replay_stop = QtWidgets.QPushButton("Close replay")
        self.btn_replay_stop.clicked.connect(self.sig_replay_stop.emit)
        playback_btns.addWidget(self.btn_replay_stop)
        playback_btns.addStretch(1)
        playback_layout.addLayout(playback_btns)

        self.slider_replay = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider_replay.setRange(0, 0)
        self.slider_replay.sliderReleased.connect(self._emit_replay_seek)
        playback_layout.addWidget(self.slider_replay)

        self.lbl_replay_progress = QtWidgets.QLabel("Frame 0 / 0")
        self.lbl_replay_progress.setWordWrap(True)
        playback_layout.addWidget(self.lbl_replay_progress)

        self.lbl_replay_status = QtWidgets.QLabel("Idle")
        self.lbl_replay_status.setWordWrap(True)
        playback_layout.addWidget(self.lbl_replay_status)

        layout.addWidget(playback_box)

        trackdb_box = QtWidgets.QGroupBox("TrackDB Baseline")
        trackdb_layout = QtWidgets.QVBoxLayout(trackdb_box)
        trackdb_layout.setContentsMargins(12, 12, 12, 12)
        trackdb_layout.setSpacing(10)

        self.chk_replay_trackdb_enabled = QtWidgets.QCheckBox(
            "Use TrackDB on Track Map"
        )
        self.chk_replay_trackdb_enabled.setChecked(True)
        self.chk_replay_trackdb_enabled.toggled.connect(
            self._emit_trackdb_overlay_changed
        )
        trackdb_layout.addWidget(self.chk_replay_trackdb_enabled)

        overlay_row = QtWidgets.QHBoxLayout()
        self.chk_replay_trackdb_raceline = QtWidgets.QCheckBox("Raceline")
        self.chk_replay_trackdb_raceline.setChecked(True)
        self.chk_replay_trackdb_raceline.toggled.connect(
            self._emit_trackdb_overlay_changed
        )
        self.chk_replay_trackdb_boundaries = QtWidgets.QCheckBox(
            "Boundaries"
        )
        self.chk_replay_trackdb_boundaries.setChecked(True)
        self.chk_replay_trackdb_boundaries.toggled.connect(
            self._emit_trackdb_overlay_changed
        )
        self.chk_replay_trackdb_centerline = QtWidgets.QCheckBox(
            "Centerline"
        )
        self.chk_replay_trackdb_centerline.setChecked(False)
        self.chk_replay_trackdb_centerline.toggled.connect(
            self._emit_trackdb_overlay_changed
        )
        overlay_row.addWidget(self.chk_replay_trackdb_raceline)
        overlay_row.addWidget(self.chk_replay_trackdb_boundaries)
        overlay_row.addWidget(self.chk_replay_trackdb_centerline)
        overlay_row.addStretch(1)
        trackdb_layout.addLayout(overlay_row)

        trace_form = QtWidgets.QFormLayout()
        trace_form.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow
        )
        trace_form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        self.combo_replay_trackdb_trace = QtWidgets.QComboBox()
        self.combo_replay_trackdb_trace.addItem(
            "TrackDB line error", "trackdb_line_error"
        )
        self.combo_replay_trackdb_trace.addItem(
            "TrackDB margin", "trackdb_margin"
        )
        self.combo_replay_trackdb_trace.addItem(
            "Off-track", "trackdb_off_track"
        )
        self.combo_replay_trackdb_trace.addItem("Time delta", "time_delta")
        self.combo_replay_trackdb_trace.addItem("Off", "off")
        self.combo_replay_trackdb_trace.currentIndexChanged.connect(
            self._emit_trackdb_overlay_changed
        )
        trace_form.addRow("Trace color", self.combo_replay_trackdb_trace)
        trackdb_layout.addLayout(trace_form)

        layout.addWidget(trackdb_box)

        colors_box = QtWidgets.QGroupBox("Visual Colors")
        colors_layout = QtWidgets.QVBoxLayout(colors_box)
        colors_layout.setContentsMargins(12, 12, 12, 12)
        colors_layout.setSpacing(10)

        lbl_colors_hint = QtWidgets.QLabel(
            "These colors update the Graphs and Graphs (Overlay) docks immediately and are saved automatically."
        )
        lbl_colors_hint.setWordWrap(True)
        colors_layout.addWidget(lbl_colors_hint)

        graphs_colors_box = QtWidgets.QGroupBox("Graphs")
        graphs_colors_form = QtWidgets.QFormLayout(graphs_colors_box)
        graphs_colors_form.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow
        )
        graphs_colors_form.setRowWrapPolicy(
            QtWidgets.QFormLayout.WrapLongRows
        )
        graphs_colors_form.setVerticalSpacing(8)

        self._add_color_control(
            graphs_colors_form, "Speed", "graph_speed"
        )
        self._add_color_control(
            graphs_colors_form, "RPM", "graph_rpm"
        )
        self._add_color_control(
            graphs_colors_form, "Throttle", "graph_throttle"
        )
        self._add_color_control(
            graphs_colors_form, "Brake", "graph_brake"
        )
        colors_layout.addWidget(graphs_colors_box)

        overlay_colors_box = QtWidgets.QGroupBox("Graphs (Overlay)")
        overlay_colors_form = QtWidgets.QFormLayout(overlay_colors_box)
        overlay_colors_form.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow
        )
        overlay_colors_form.setRowWrapPolicy(
            QtWidgets.QFormLayout.WrapLongRows
        )
        overlay_colors_form.setVerticalSpacing(8)

        self._add_color_control(
            overlay_colors_form, "Speed", "overlay_speed"
        )
        self._add_color_control(
            overlay_colors_form, "RPM", "overlay_rpm"
        )
        self._add_color_control(
            overlay_colors_form, "Throttle", "overlay_throttle"
        )
        self._add_color_control(
            overlay_colors_form, "Brake", "overlay_brake"
        )
        colors_layout.addWidget(overlay_colors_box)

        colors_btns = QtWidgets.QHBoxLayout()
        colors_btns.addStretch(1)
        self.btn_reset_graph_colors = QtWidgets.QPushButton(
            "Reset colors"
        )
        self.btn_reset_graph_colors.clicked.connect(self._reset_graph_colors)
        colors_btns.addWidget(self.btn_reset_graph_colors)
        colors_layout.addLayout(colors_btns)

        layout.addWidget(colors_box)
        layout.addStretch(1)

        self.set_graph_color_settings(self._graph_color_settings)
        self._update_trackdb_controls_enabled()

    def set_current_run_info(
        self,
        run_id: str,
        run_dir: str,
        **kwargs,
    ) -> None:
        old_run_dir = self._current_run_dir
        self._current_run_id = run_id or None
        self._current_run_dir = run_dir or None

        if self._current_run_dir:
            self.lbl_run_hint.setText(
                f"Current run: {run_id or '-'}\n{self._current_run_dir}"
            )
        else:
            self.lbl_run_hint.setText("Current run: -")

        current_path = self.edit_replay_path.text().strip()
        if self._current_run_dir and (
            not current_path or (old_run_dir and current_path == old_run_dir)
        ):
            self.edit_replay_path.setText(self._current_run_dir)
        elif (
            not self._current_run_dir
            and old_run_dir
            and current_path == old_run_dir
        ):
            self.edit_replay_path.clear()

    def set_replay_laps(
        self,
        lap_numbers: list[int],
        *,
        reference_lap_num: int | None = None,
        selected_lap_num: int | None = None,
        compare_lap_num: int | None = None,
    ) -> None:
        self._replay_lap_numbers = [int(lap_num) for lap_num in lap_numbers]
        self._replay_reference_lap_num = (
            int(reference_lap_num) if reference_lap_num is not None else None
        )

        self.combo_replay_lap.blockSignals(True)
        self.combo_replay_lap.clear()
        for lap_num in lap_numbers:
            self.combo_replay_lap.addItem(f"Lap {lap_num}", int(lap_num))

        if selected_lap_num is not None:
            idx = self.combo_replay_lap.findData(int(selected_lap_num))
            if idx >= 0:
                self.combo_replay_lap.setCurrentIndex(idx)
        self.combo_replay_lap.blockSignals(False)
        self._refresh_compare_lap_options(
            selected_lap_num=selected_lap_num,
            compare_lap_num=compare_lap_num,
        )

        if reference_lap_num is None:
            self.lbl_replay_reference.setText("Reference lap: -")
        else:
            self.lbl_replay_reference.setText(
                f"Reference lap: {int(reference_lap_num)}"
            )

    def set_graph_color_settings(
        self,
        settings: Mapping[str, object] | None,
        *,
        emit_signal: bool = False,
    ) -> None:
        current_compare = self._replay_compare_color
        self._graph_color_settings = normalized_graph_color_settings(settings)
        self._replay_compare_color = self._graph_color_settings["compare"]
        for key in self._color_previews:
            self._apply_color_preview(key)
        if emit_signal:
            self.sig_graph_colors_changed.emit(self.current_graph_color_settings())
            if self._replay_compare_color != current_compare:
                self.sig_replay_compare_color_changed.emit(
                    self._replay_compare_color
                )

    def set_replay_status(self, text: str, *, error: bool = False) -> None:
        self.lbl_replay_status.setText(text or "")
        self.lbl_replay_status.setStyleSheet(
            "color: #cc6666;" if error else ""
        )

    def current_graph_color_settings(self) -> dict[str, str]:
        return dict(self._graph_color_settings)

    def current_replay_compare_lap_num(self) -> int | None:
        lap_num = self.combo_replay_compare_lap.currentData()
        if lap_num in (None, 0):
            return None
        return int(lap_num)

    def current_replay_compare_color(self) -> str:
        return self._replay_compare_color

    def current_trackdb_overlay_settings(self) -> dict[str, object]:
        return {
            "enabled": self.chk_replay_trackdb_enabled.isChecked(),
            "raceline": self.chk_replay_trackdb_raceline.isChecked(),
            "boundaries": self.chk_replay_trackdb_boundaries.isChecked(),
            "centerline": self.chk_replay_trackdb_centerline.isChecked(),
            "color_mode": str(
                self.combo_replay_trackdb_trace.currentData()
                or "trackdb_line_error"
            ),
        }

    def set_replay_progress(
        self,
        current_frame: int,
        max_frame: int,
        *,
        playing: bool = False,
    ) -> None:
        self.slider_replay.blockSignals(True)
        self.slider_replay.setRange(0, max(0, int(max_frame)))
        self.slider_replay.setValue(
            max(0, min(int(current_frame), int(max_frame)))
        )
        self.slider_replay.blockSignals(False)
        state = "Playing" if playing else "Paused"
        self.lbl_replay_progress.setText(
            f"{state}  |  Frame {int(current_frame)} / {int(max_frame)}"
        )

    def _browse_replay_run(self) -> None:
        start_dir = (
            self.edit_replay_path.text().strip()
            or self._current_run_dir
            or "data/runs"
        )
        selected = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose replay run folder", start_dir
        )
        if selected:
            self.edit_replay_path.setText(selected)

    def _emit_replay_load(self) -> None:
        source_path = (
            self.edit_replay_path.text().strip() or self._current_run_dir or ""
        )
        if not source_path:
            QtWidgets.QMessageBox.information(
                self,
                "No replay source",
                "Choose a recorded run folder before loading replay mode.",
            )
            return
        self.sig_replay_load.emit(source_path)

    def _emit_replay_lap_changed(self) -> None:
        lap_num = self.combo_replay_lap.currentData()
        if lap_num is None:
            return
        self._refresh_compare_lap_options(
            selected_lap_num=int(lap_num),
            compare_lap_num=self.current_replay_compare_lap_num(),
        )
        self.sig_replay_lap_changed.emit(int(lap_num))

    def _emit_replay_compare_lap_changed(self) -> None:
        lap_num = self.combo_replay_compare_lap.currentData()
        self.sig_replay_compare_lap_changed.emit(int(lap_num or 0))

    def _emit_replay_speed_changed(self) -> None:
        rate = self.combo_replay_speed.currentData()
        if rate is None:
            return
        self.sig_replay_speed_changed.emit(float(rate))

    def _emit_replay_loop_changed(self, checked: bool) -> None:
        self.sig_replay_loop_changed.emit(bool(checked))

    def _emit_trackdb_overlay_changed(self, *args) -> None:
        self._update_trackdb_controls_enabled()
        self.sig_trackdb_overlay_changed.emit(
            self.current_trackdb_overlay_settings()
        )

    def _emit_replay_seek(self) -> None:
        self.sig_replay_seek.emit(int(self.slider_replay.value()))

    def _refresh_compare_lap_options(
        self,
        *,
        selected_lap_num: int | None,
        compare_lap_num: int | None,
    ) -> None:
        if (
            compare_lap_num is None
            and self._replay_reference_lap_num is not None
            and self._replay_reference_lap_num != selected_lap_num
        ):
            compare_lap_num = self._replay_reference_lap_num

        self.combo_replay_compare_lap.blockSignals(True)
        self.combo_replay_compare_lap.clear()
        self.combo_replay_compare_lap.addItem("Off", 0)
        for lap_num in self._replay_lap_numbers:
            if selected_lap_num is not None and int(lap_num) == int(
                selected_lap_num
            ):
                continue
            self.combo_replay_compare_lap.addItem(
                f"Lap {int(lap_num)}", int(lap_num)
            )

        if compare_lap_num is not None:
            idx = self.combo_replay_compare_lap.findData(int(compare_lap_num))
            self.combo_replay_compare_lap.setCurrentIndex(
                idx if idx >= 0 else 0
            )
        else:
            self.combo_replay_compare_lap.setCurrentIndex(0)
        self.combo_replay_compare_lap.blockSignals(False)

    def _choose_replay_compare_color(self) -> None:
        self._choose_graph_color("compare")

    def _choose_graph_color(self, key: str) -> None:
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self._graph_color_settings[key]),
            self,
            self._color_dialog_titles[key],
        )
        if not color.isValid():
            return
        updated = self.current_graph_color_settings()
        updated[key] = color.name()
        self.set_graph_color_settings(updated, emit_signal=True)

    def _reset_graph_colors(self) -> None:
        self.set_graph_color_settings(
            DEFAULT_GRAPH_COLOR_SETTINGS,
            emit_signal=True,
        )

    def _add_color_control(
        self,
        form: QtWidgets.QFormLayout,
        label_text: str,
        key: str,
    ) -> None:
        preview = QtWidgets.QLabel()
        preview.setFixedWidth(84)
        self._color_previews[key] = preview

        row = QtWidgets.QHBoxLayout()
        row.addWidget(preview)

        btn = QtWidgets.QPushButton("Pick color")
        btn.clicked.connect(
            lambda _checked=False, key=key: self._choose_graph_color(key)
        )
        row.addWidget(btn)
        row.addStretch(1)
        form.addRow(label_text, row)

    def _apply_replay_compare_color_preview(self) -> None:
        self._apply_color_preview("compare")

    def _update_trackdb_controls_enabled(self) -> None:
        enabled = self.chk_replay_trackdb_enabled.isChecked()
        self.chk_replay_trackdb_raceline.setEnabled(enabled)
        self.chk_replay_trackdb_boundaries.setEnabled(enabled)
        self.chk_replay_trackdb_centerline.setEnabled(enabled)
        self.combo_replay_trackdb_trace.setEnabled(enabled)

    def _apply_color_preview(self, key: str) -> None:
        preview = self._color_previews.get(key)
        if preview is None:
            return
        color = self._graph_color_settings[key]
        preview.setText(color)
        preview.setAlignment(QtCore.Qt.AlignCenter)
        preview.setStyleSheet(self._color_preview_style(color))

    def _color_preview_style(self, color: str) -> str:
        return (
            "border: 1px solid #777;"
            f"background: {color};"
            f"color: {self._preview_text_color(color)};"
            "padding: 4px;"
            "font-family: Consolas, monospace;"
        )

    def _preview_text_color(self, color: str) -> str:
        qcolor = QtGui.QColor(color)
        if not qcolor.isValid():
            return "#111111"
        luminance = (
            (0.299 * qcolor.red())
            + (0.587 * qcolor.green())
            + (0.114 * qcolor.blue())
        )
        return "#111111" if luminance >= 160 else "#f8f8f8"
