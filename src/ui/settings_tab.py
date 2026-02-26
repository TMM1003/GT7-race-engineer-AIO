# src/ui/settings_tab.py
from __future__ import annotations

from PySide6 import QtCore, QtWidgets
from typing import Optional
import re


class SettingsTab(QtWidgets.QWidget):
    # Thesis/Research control panel
    # Emits a dict of settings that AppController applies and records into run
    # metadata
    sig_apply = QtCore.Signal(dict)
    sig_start_new_run = QtCore.Signal()
    sig_open_run_dir = QtCore.Signal()
    sig_export_dataset = QtCore.Signal()
    sig_apply_run_metadata = QtCore.Signal(dict)
    sig_start_new_run_with_meta = QtCore.Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        layout.addLayout(form)

        # Research export master toggle
        self.chk_research_enabled = QtWidgets.QCheckBox(
            "Enable research export"
        )
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

        # Representation bins
        self.spin_n_bins = QtWidgets.QSpinBox()
        self.spin_n_bins.setRange(100, 2000)
        self.spin_n_bins.setSingleStep(50)
        self.spin_n_bins.setValue(300)
        form.addRow("Distance bins (N)", self.spin_n_bins)

        # Session buffer length
        self.spin_buffer_samples = QtWidgets.QSpinBox()
        self.spin_buffer_samples.setRange(1000, 200000)
        self.spin_buffer_samples.setSingleStep(5000)
        self.spin_buffer_samples.setValue(36000)
        form.addRow("Session buffer (samples)", self.spin_buffer_samples)

        # Feature selection
        feat_group = QtWidgets.QGroupBox("Features exported (X columns)")
        feat_layout = QtWidgets.QGridLayout(feat_group)

        self.chk_speed = QtWidgets.QCheckBox("speed_kmh")
        self.chk_speed.setChecked(True)
        self.chk_throttle = QtWidgets.QCheckBox("throttle")
        self.chk_throttle.setChecked(True)
        self.chk_brake = QtWidgets.QCheckBox("brake")
        self.chk_brake.setChecked(True)
        self.chk_rpm = QtWidgets.QCheckBox("rpm")
        self.chk_rpm.setChecked(True)
        self.chk_gear = QtWidgets.QCheckBox("gear")
        self.chk_gear.setChecked(True)
        self.chk_curvature = QtWidgets.QCheckBox("curvature")
        self.chk_curvature.setChecked(True)

        feat_layout.addWidget(self.chk_speed, 0, 0)
        feat_layout.addWidget(self.chk_throttle, 0, 1)
        feat_layout.addWidget(self.chk_brake, 0, 2)
        feat_layout.addWidget(self.chk_rpm, 1, 0)
        feat_layout.addWidget(self.chk_gear, 1, 1)
        feat_layout.addWidget(self.chk_curvature, 1, 2)

        layout.addWidget(feat_group)

        # Optional normalization (stored in run metadata; apply in training
        # scripts)
        self.chk_normalize = QtWidgets.QCheckBox(
            (
                "Normalize features (recorded for research; "
                "apply in training scripts)"
            )
        )
        self.chk_normalize.setChecked(False)
        layout.addWidget(self.chk_normalize)

        # Export knobs
        exp_group = QtWidgets.QGroupBox("Export options")
        exp_layout = QtWidgets.QVBoxLayout(exp_group)

        self.chk_npz = QtWidgets.QCheckBox("Export NPZ if NumPy available")
        self.chk_npz.setChecked(True)

        self.chk_json = QtWidgets.QCheckBox("Export JSON always")
        self.chk_json.setChecked(True)

        self.chk_export_corners = QtWidgets.QCheckBox("Export corners")
        self.chk_export_corners.setChecked(True)

        self.chk_delta_profile = QtWidgets.QCheckBox(
            "Export delta-time profile baseline"
        )
        self.chk_delta_profile.setChecked(True)

        self.chk_corner_rows = QtWidgets.QCheckBox(
            "Export corner coaching rows baseline"
        )
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
        self.combo_ui_rate.setCurrentText("10 Hz")

        ui_layout.addWidget(QtWidgets.QLabel("Update visuals at:"))
        ui_layout.addWidget(self.combo_ui_rate, 1)

        layout.addWidget(ui_group)

        # Run Metadata
        meta_box = QtWidgets.QGroupBox("Run Metadata")
        meta_layout = QtWidgets.QVBoxLayout(meta_box)

        # Read-only current labels
        self._lbl_run_id = QtWidgets.QLabel("—")
        self._lbl_run_dir = QtWidgets.QLabel("—")
        self._lbl_track = QtWidgets.QLabel("—")
        self._lbl_car = QtWidgets.QLabel("—")
        self._lbl_alias = QtWidgets.QLabel("—")

        ro = QtWidgets.QFormLayout()
        ro.addRow("Run ID", self._lbl_run_id)
        ro.addRow("Run dir", self._lbl_run_dir)
        ro.addRow("Track", self._lbl_track)
        ro.addRow("Car", self._lbl_car)
        ro.addRow("Alias", self._lbl_alias)
        meta_layout.addLayout(ro)

        meta_layout.addSpacing(8)

        # Editable metadata
        self.edit_track_name = QtWidgets.QLineEdit()
        self.edit_track_name.setPlaceholderText("e.g., Monza")
        self.edit_car_name = QtWidgets.QLineEdit()
        self.edit_car_name.setPlaceholderText("e.g., Toyota SF '23")
        self.edit_run_alias = QtWidgets.QLineEdit()
        self.edit_run_alias.setPlaceholderText("e.g., monza_toyota_sf_23")

        self.btn_autofill_alias = QtWidgets.QPushButton("Auto-fill alias")
        self.btn_autofill_alias.clicked.connect(self._autofill_alias)

        alias_row = QtWidgets.QHBoxLayout()
        alias_row.addWidget(self.edit_run_alias, 1)
        alias_row.addWidget(self.btn_autofill_alias)

        self.edit_notes = QtWidgets.QTextEdit()
        self.edit_notes.setPlaceholderText(
            "Optional notes: tires, BoP, setup, objective, conditions, etc."
        )
        self.edit_notes.setFixedHeight(70)

        fm = QtWidgets.QFormLayout()
        fm.addRow("Track name", self.edit_track_name)
        fm.addRow("Car name", self.edit_car_name)
        fm.addRow("Run alias", alias_row)
        fm.addRow("Notes", self.edit_notes)
        meta_layout.addLayout(fm)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_apply_meta = QtWidgets.QPushButton("Apply to current run")
        self.btn_new_run_with_meta = QtWidgets.QPushButton(
            "Start new run with metadata"
        )
        self.btn_apply_meta.clicked.connect(self._emit_apply_run_metadata)
        self.btn_new_run_with_meta.clicked.connect(
            self._emit_start_new_run_with_meta
        )
        btn_row.addWidget(self.btn_apply_meta)
        btn_row.addWidget(self.btn_new_run_with_meta)
        btn_row.addStretch(1)
        meta_layout.addLayout(btn_row)

        layout.addWidget(meta_box)

        self._gt7db = None
        self._car_id_lookup_enabled = False
        self._last_auto_car_name: Optional[str] = None
        self._detected_car_id: Optional[int] = None
        self._detected_car_name: Optional[str] = None

        self.chk_auto_detect_car = QtWidgets.QCheckBox(
            "Auto-detect car from telemetry (temporarily disabled)"
        )
        self.chk_auto_detect_car.setChecked(False)
        self.chk_auto_detect_car.setEnabled(False)
        self.chk_auto_detect_car.setToolTip(
            (
                "Disabled while GT7 telemetry Car IDs are being "
                "remapped to a verified CSV."
            )
        )

        self.lbl_detected_car = QtWidgets.QLabel(
            "Telemetry car ID: - (lookup disabled)"
        )
        self.lbl_detected_car.setWordWrap(True)
        self.lbl_detected_car.setStyleSheet("color: #888;")  # subtle

        form.addRow(self.chk_auto_detect_car)
        form.addRow("", self.lbl_detected_car)

        self.edit_car_name.textEdited.connect(self._on_car_name_user_edited)

        # Buttons
        btns = QtWidgets.QHBoxLayout()
        layout.addLayout(btns)

        self.btn_apply = QtWidgets.QPushButton("Apply settings")
        self.btn_apply.clicked.connect(self._emit_apply)
        btns.addWidget(self.btn_apply)

        self.btn_new_run = QtWidgets.QPushButton("Start new run")
        self.btn_new_run.clicked.connect(self.sig_start_new_run.emit)
        btns.addWidget(self.btn_new_run)

        self.btn_export_dataset = QtWidgets.QPushButton("Export dataset")
        self.btn_export_dataset.clicked.connect(self.sig_export_dataset.emit)
        btns.addWidget(self.btn_export_dataset)

        self.btn_open_run = QtWidgets.QPushButton("Open run folder")
        self.btn_open_run.clicked.connect(self.sig_open_run_dir.emit)
        btns.addWidget(self.btn_open_run)

        btns.addStretch(1)
        layout.addStretch(1)

        self.btn_export_dataset.clicked.connect(self._on_export_clicked)

    def set_current_run_info(
        self,
        run_id: str,
        run_dir: str,
        track: str | None = None,
        car: str | None = None,
        alias: str | None = None,
    ) -> None:
        self._lbl_run_id.setText(run_id or "—")
        self._lbl_run_dir.setText(run_dir or "—")
        self._lbl_track.setText(track or "—")
        self._lbl_car.setText(car or "—")
        self._lbl_alias.setText(alias or "—")

    def set_reference_info(
        self, ref_lap: int | None, ref_time_ms: int | None
    ) -> None:
        # Optional: expand later if you want to show reference details in this
        # tab.
        return

    def _collect_run_metadata(self) -> dict:
        return {
            "track_name": self.edit_track_name.text().strip() or None,
            "car_name": self.edit_car_name.text().strip() or None,
            "run_alias": self.edit_run_alias.text().strip() or None,
            "notes": self.edit_notes.toPlainText().strip() or None,
        }

    def _emit_apply_run_metadata(self) -> None:
        self.sig_apply_run_metadata.emit(self._collect_run_metadata())

    def _emit_start_new_run_with_meta(self) -> None:
        self.sig_start_new_run_with_meta.emit(self._collect_run_metadata())

    def _autofill_alias(self) -> None:
        track = (self.edit_track_name.text() or "").strip()
        car = (self.edit_car_name.text() or "").strip()

        def slug(s: str) -> str:
            s = s.lower()
            s = re.sub(r"[^a-z0-9]+", "_", s)
            s = re.sub(r"_+", "_", s).strip("_")
            return s

        parts = [p for p in [slug(track), slug(car)] if p]
        if parts:
            self.edit_run_alias.setText("_".join(parts))

    # src/ui/settings_tab.py

    def set_gt7_database(self, db) -> None:
        """Attach a GT7Database loaded from CSVs (currently unused)."""
        self._gt7db = db

    def _on_car_name_user_edited(self, _text: str) -> None:
        # User is manually overriding: stop treating previous value as “auto”
        self._last_auto_car_name = None

    def update_from_snapshot(self, snap: dict) -> None:
        """
        Called from the main UI update loop.
        Car-ID-based lookup is intentionally disabled until
        a validated ID CSV exists.
        """
        car_id = snap.get("car_id")
        try:
            car_id_int = int(car_id) if car_id is not None else None
        except Exception:
            car_id_int = None

        # Temporarily disable CSV/lookup driven car detection until IDs are
        # validated.
        self._detected_car_id = car_id_int
        self._detected_car_name = None
        if car_id_int is None:
            self.lbl_detected_car.setText(
                "Telemetry car ID: - (lookup disabled)"
            )
        else:
            self.lbl_detected_car.setText(
                f"Telemetry car ID: {car_id_int} (lookup disabled)"
            )
        return

        # Update detected fields
        self._detected_car_id = car_id_int
        detected_name = None

        if car_id_int is not None and self._gt7db is not None:
            car_obj = self._gt7db.find_car_by_id(car_id_int)
            if car_obj is not None:
                detected_name = getattr(car_obj, "name", None)

        self._detected_car_name = detected_name

        # Update label
        if car_id_int is None:
            self.lbl_detected_car.setText("Detected car: —")
        elif detected_name:
            self.lbl_detected_car.setText(
                f"Detected car: {detected_name} (ID {car_id_int})"
            )
        else:
            self.lbl_detected_car.setText(
                f"Detected car: Unknown (ID {car_id_int})"
            )

        # Auto-fill car name (non-clobbering)
        if not self.chk_auto_detect_car.isChecked():
            return
        if not detected_name:
            return

        current = (self.edit_car_name.text() or "").strip()

        # Only auto-fill if:
        # - field is empty, OR
        # - field equals the last value we auto-filled
        #   (so we can keep it updated)
        if (not current) or (
            self._last_auto_car_name is not None
            and current == self._last_auto_car_name
        ):
            self.edit_car_name.setText(detected_name)
            self._last_auto_car_name = detected_name

            # If you have an alias autofill helper, call it
            if hasattr(self, "_autofill_alias"):
                try:
                    self._autofill_alias()
                except Exception:
                    pass

    def _collect_run_metadata(self) -> dict:
        """
        If you already have this method, merge these fields in.
        """
        meta = {
            "track_name": (self.edit_track_name.text() or "").strip() or None,
            "car_name": (self.edit_car_name.text() or "").strip() or None,
            "run_alias": (self.edit_run_alias.text() or "").strip() or None,
            "notes": (self.edit_notes.toPlainText() or "").strip() or None,
        }

        # ✅ new stable metadata
        return meta

    def _on_export_clicked(self) -> None:
        self.sig_export_dataset.emit()

    def _browse_output_root(self) -> None:
        d = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose output folder", self.edit_output_root.text()
        )
        if d:
            self.edit_output_root.setText(d)

    def _emit_apply(self) -> None:
        features = []
        if self.chk_speed.isChecked():
            features.append("speed_kmh")
        if self.chk_throttle.isChecked():
            features.append("throttle")
        if self.chk_brake.isChecked():
            features.append("brake")
        if self.chk_rpm.isChecked():
            features.append("rpm")
        if self.chk_gear.isChecked():
            features.append("gear")
        if self.chk_curvature.isChecked():
            features.append("curvature")

        settings = {
            "research_enabled": bool(self.chk_research_enabled.isChecked()),
            "output_root": self.edit_output_root.text().strip() or "data/runs",
            "n_bins": int(self.spin_n_bins.value()),
            "features": features,
            "normalize": bool(self.chk_normalize.isChecked()),
            "export_npz_if_available": bool(self.chk_npz.isChecked()),
            "export_json_always": bool(self.chk_json.isChecked()),
            "export_corners": bool(self.chk_export_corners.isChecked()),
            "export_delta_profile": bool(self.chk_delta_profile.isChecked()),
            "export_corner_rows": bool(self.chk_corner_rows.isChecked()),
            "ui_rate_hz": 60
            if self.combo_ui_rate.currentText().startswith("60")
            else 10,
            "buffer_samples": int(self.spin_buffer_samples.value()),
        }
        self.sig_apply.emit(settings)
