from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets


class ReplayTab(QtWidgets.QWidget):
    sig_replay_load = QtCore.Signal(str)
    sig_replay_lap_changed = QtCore.Signal(int)
    sig_replay_speed_changed = QtCore.Signal(float)
    sig_replay_play = QtCore.Signal()
    sig_replay_pause = QtCore.Signal()
    sig_replay_restart = QtCore.Signal()
    sig_replay_stop = QtCore.Signal()
    sig_replay_seek = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._current_run_id: Optional[str] = None
        self._current_run_dir: Optional[str] = None

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
        playback_form.addRow("Reference", self.lbl_replay_reference)

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
        layout.addStretch(1)

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
    ) -> None:
        self.combo_replay_lap.blockSignals(True)
        self.combo_replay_lap.clear()
        for lap_num in lap_numbers:
            self.combo_replay_lap.addItem(f"Lap {lap_num}", int(lap_num))

        if selected_lap_num is not None:
            idx = self.combo_replay_lap.findData(int(selected_lap_num))
            if idx >= 0:
                self.combo_replay_lap.setCurrentIndex(idx)
        self.combo_replay_lap.blockSignals(False)

        if reference_lap_num is None:
            self.lbl_replay_reference.setText("Reference lap: -")
        else:
            self.lbl_replay_reference.setText(
                f"Reference lap: {int(reference_lap_num)}"
            )

    def set_replay_status(self, text: str, *, error: bool = False) -> None:
        self.lbl_replay_status.setText(text or "")
        self.lbl_replay_status.setStyleSheet(
            "color: #cc6666;" if error else ""
        )

    def set_replay_progress(
        self,
        current_frame: int,
        max_frame: int,
        *,
        playing: bool = False,
    ) -> None:
        self.slider_replay.blockSignals(True)
        self.slider_replay.setRange(0, max(0, int(max_frame)))
        self.slider_replay.setValue(max(0, min(int(current_frame), int(max_frame))))
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
        self.sig_replay_lap_changed.emit(int(lap_num))

    def _emit_replay_speed_changed(self) -> None:
        rate = self.combo_replay_speed.currentData()
        if rate is None:
            return
        self.sig_replay_speed_changed.emit(float(rate))

    def _emit_replay_seek(self) -> None:
        self.sig_replay_seek.emit(int(self.slider_replay.value()))
