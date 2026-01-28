# src/ui/settings_tab.py
from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class SettingsTab(QtWidgets.QWidget):
    """
    Thesis/Research control panel.
    Emits a dict of settings that AppController applies and records into run metadata.
    """
    sig_apply = QtCore.Signal(dict)
    sig_start_new_run = QtCore.Signal()
    sig_open_run_dir = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        layout.addLayout(form)

        # Research export master toggle
        self.chk_research_enabled = QtWidgets.QCheckBox("Enable research export")
        self.chk_research_enabled.setChecked(True)
        form.addRow(self.chk_research_enabled)

        # Output root
        out_row = QtWidgets.QHBoxLayout()
        self.edit_output_root = QtWidgets.QLineEdit("data/runs")
        self.btn_browse = QtWidgets.QPushButton("Browse…")
        self.btn_browse.clicked.connect(self._browse_output_root)
        out_row.addWidget(self.edit_output_root, 1)
        out_row.addWidget(self.btn_browse)
        form.addRow("Output folder", out_row)

        # Run tag
        self.edit_run_tag = QtWidgets.QLineEdit("")
        self.edit_run_tag.setPlaceholderText("e.g., road_atlanta_gr3_softs_stint1")
        form.addRow("Run tag", self.edit_run_tag)

        # Representation bins
        self.spin_n_bins = QtWidgets.QSpinBox()
        self.spin_n_bins.setRange(100, 2000)
        self.spin_n_bins.setSingleStep(50)
        self.spin_n_bins.setValue(300)
        form.addRow("Distance bins (N)", self.spin_n_bins)

        # Feature selection
        feat_group = QtWidgets.QGroupBox("Features exported (X columns)")
        feat_layout = QtWidgets.QGridLayout(feat_group)

        self.chk_speed = QtWidgets.QCheckBox("speed_kmh"); self.chk_speed.setChecked(True)
        self.chk_throttle = QtWidgets.QCheckBox("throttle"); self.chk_throttle.setChecked(True)
        self.chk_brake = QtWidgets.QCheckBox("brake"); self.chk_brake.setChecked(True)
        self.chk_rpm = QtWidgets.QCheckBox("rpm"); self.chk_rpm.setChecked(True)
        self.chk_gear = QtWidgets.QCheckBox("gear"); self.chk_gear.setChecked(True)
        self.chk_curvature = QtWidgets.QCheckBox("curvature"); self.chk_curvature.setChecked(True)

        feat_layout.addWidget(self.chk_speed, 0, 0)
        feat_layout.addWidget(self.chk_throttle, 0, 1)
        feat_layout.addWidget(self.chk_brake, 0, 2)
        feat_layout.addWidget(self.chk_rpm, 1, 0)
        feat_layout.addWidget(self.chk_gear, 1, 1)
        feat_layout.addWidget(self.chk_curvature, 1, 2)

        layout.addWidget(feat_group)

        # Optional normalization (stored in run metadata; you can implement in training later)
        self.chk_normalize = QtWidgets.QCheckBox("Normalize features (recorded for research; apply in training scripts)")
        self.chk_normalize.setChecked(False)
        layout.addWidget(self.chk_normalize)

        # Export knobs
        exp_group = QtWidgets.QGroupBox("Export options")
        exp_layout = QtWidgets.QVBoxLayout(exp_group)

        self.chk_npz = QtWidgets.QCheckBox("Export NPZ if NumPy available")
        self.chk_npz.setChecked(True)
        self.chk_json = QtWidgets.QCheckBox("Export JSON always")
        self.chk_json.setChecked(True)
        self.chk_export_corners = QtWidgets.QCheckBox("Export corners (if implemented later)")
        self.chk_export_corners.setChecked(True)

        self.chk_delta_profile = QtWidgets.QCheckBox("Export delta-time profile baseline")
        self.chk_delta_profile.setChecked(True)
        self.chk_corner_rows = QtWidgets.QCheckBox("Export corner coaching rows baseline")
        self.chk_corner_rows.setChecked(True)

        exp_layout.addWidget(self.chk_npz)
        exp_layout.addWidget(self.chk_json)
        exp_layout.addWidget(self.chk_export_corners)
        exp_layout.addWidget(self.chk_delta_profile)
        exp_layout.addWidget(self.chk_corner_rows)

        layout.addWidget(exp_group)

        # UI update rate
        ui_group = QtWidgets.QGroupBox("UI visualization update rate")
        ui_layout = QtWidgets.QHBoxLayout(ui_group)

        self.combo_ui_rate = QtWidgets.QComboBox()
        self.combo_ui_rate.addItems(["10 Hz", "60 Hz"])
        self.combo_ui_rate.setCurrentText("10 Hz")  # default to throttled UI
        ui_layout.addWidget(QtWidgets.QLabel("Update visuals at:"))
        ui_layout.addWidget(self.combo_ui_rate, 1)

        layout.addWidget(ui_group)

        # Session buffer length
        self.spin_buffer_samples = QtWidgets.QSpinBox()
        self.spin_buffer_samples.setRange(1000, 200000)
        self.spin_buffer_samples.setSingleStep(5000)
        self.spin_buffer_samples.setValue(36000)
        form.addRow("Session buffer (samples)", self.spin_buffer_samples)

        # Buttons
        btns = QtWidgets.QHBoxLayout()
        layout.addLayout(btns)

        self.btn_apply = QtWidgets.QPushButton("Apply settings")
        self.btn_apply.clicked.connect(self._emit_apply)
        btns.addWidget(self.btn_apply)

        self.btn_new_run = QtWidgets.QPushButton("Start new run")
        self.btn_new_run.clicked.connect(self.sig_start_new_run.emit)
        btns.addWidget(self.btn_new_run)

        self.btn_open_run = QtWidgets.QPushButton("Open run folder")
        self.btn_open_run.clicked.connect(self.sig_open_run_dir.emit)
        btns.addWidget(self.btn_open_run)

        btns.addStretch(1)

        layout.addStretch(1)

    def _browse_output_root(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose output folder", self.edit_output_root.text())
        if d:
            self.edit_output_root.setText(d)

    def _emit_apply(self):
        features = []
        if self.chk_speed.isChecked(): features.append("speed_kmh")
        if self.chk_throttle.isChecked(): features.append("throttle")
        if self.chk_brake.isChecked(): features.append("brake")
        if self.chk_rpm.isChecked(): features.append("rpm")
        if self.chk_gear.isChecked(): features.append("gear")
        if self.chk_curvature.isChecked(): features.append("curvature")

        settings = {
            "research_enabled": self.chk_research_enabled.isChecked(),
            "output_root": self.edit_output_root.text().strip() or "data/runs",
            "run_tag": self.edit_run_tag.text().strip() or None,
            "n_bins": int(self.spin_n_bins.value()),
            "features": features,
            "normalize": bool(self.chk_normalize.isChecked()),
            "export_npz_if_available": bool(self.chk_npz.isChecked()),
            "export_json_always": bool(self.chk_json.isChecked()),
            "export_corners": bool(self.chk_export_corners.isChecked()),
            "export_delta_profile": bool(self.chk_delta_profile.isChecked()),
            "export_corner_rows": bool(self.chk_corner_rows.isChecked()),
            "ui_rate_hz": 60 if self.combo_ui_rate.currentText().startswith("60") else 10,
            "buffer_samples": int(self.spin_buffer_samples.value()),
        }
        self.sig_apply.emit(settings)
