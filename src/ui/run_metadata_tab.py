# src/ui/run_metadata_tab.py
from __future__ import annotations

import re
from PySide6 import QtCore, QtWidgets


def _slug(s: str) -> str:
    """
    Make a safe, human-readable identifier chunk.
    Lowercase, alnum/underscore only.
    """
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


class RunMetadataTab(QtWidgets.QWidget):
    """
    Manual run labeling metadata.

    Emits:
      - sig_apply_meta(meta_dict): apply to current run (patches run.json)
      - sig_start_new_run(meta_dict): start new run using these metadata values
    """
    sig_apply_meta = QtCore.Signal(dict)
    sig_start_new_run = QtCore.Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)

        # Current run info (read-only)
        self.grp_current = QtWidgets.QGroupBox("Current run labels (read-only)")
        cur = QtWidgets.QFormLayout(self.grp_current)
        self.lbl_run_id = QtWidgets.QLabel("--")
        self.lbl_run_dir = QtWidgets.QLabel("--")
        self.lbl_track = QtWidgets.QLabel("--")
        self.lbl_car = QtWidgets.QLabel("--")
        self.lbl_alias = QtWidgets.QLabel("--")

        for lab in (self.lbl_run_id, self.lbl_run_dir, self.lbl_track, self.lbl_car, self.lbl_alias):
            lab.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        cur.addRow("Run ID", self.lbl_run_id)
        cur.addRow("Run dir", self.lbl_run_dir)
        cur.addRow("Track", self.lbl_track)
        cur.addRow("Car", self.lbl_car)
        cur.addRow("Alias", self.lbl_alias)

        layout.addWidget(self.grp_current)

        # Editable inputs
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)

        self.edit_track = QtWidgets.QLineEdit()
        self.edit_track.setPlaceholderText("e.g., Monza (GP)")
        form.addRow("Track name", self.edit_track)

        self.edit_car = QtWidgets.QLineEdit()
        self.edit_car.setPlaceholderText("e.g., Porsche 911 RSR '17")
        form.addRow("Car name", self.edit_car)

        alias_row = QtWidgets.QHBoxLayout()
        self.edit_alias = QtWidgets.QLineEdit()
        self.edit_alias.setPlaceholderText("Optional: monza_rsr_baseline")
        self.btn_autofill_alias = QtWidgets.QPushButton("Auto-fill alias")
        self.btn_autofill_alias.clicked.connect(self._autofill_alias)
        alias_row.addWidget(self.edit_alias, 1)
        alias_row.addWidget(self.btn_autofill_alias)
        form.addRow("Run alias", alias_row)

        self.edit_notes = QtWidgets.QPlainTextEdit()
        self.edit_notes.setPlaceholderText("Optional notes: tires, BoP, setup, objective, conditions, etc.")
        self.edit_notes.setMaximumBlockCount(2000)
        form.addRow("Notes", self.edit_notes)

        # Buttons
        btns = QtWidgets.QHBoxLayout()
        layout.addLayout(btns)

        self.btn_apply = QtWidgets.QPushButton("Apply to current run")
        self.btn_apply.clicked.connect(self._emit_apply)
        btns.addWidget(self.btn_apply)

        self.btn_start = QtWidgets.QPushButton("Start new run with metadata")
        self.btn_start.clicked.connect(self._emit_start_new_run)
        btns.addWidget(self.btn_start)

        btns.addStretch(1)
        layout.addStretch(1)

    def set_current_run_info(self, *, run_id: str | None, run_dir: str | None,
                             track_name: str | None, car_name: str | None, run_alias: str | None) -> None:
        """
        Called by controller to reflect the currently active run in the UI.
        """
        self.lbl_run_id.setText(run_id or "--")
        self.lbl_run_dir.setText(run_dir or "--")
        self.lbl_track.setText(track_name or "--")
        self.lbl_car.setText(car_name or "--")
        self.lbl_alias.setText(run_alias or "--")

    def _autofill_alias(self) -> None:
        track = _slug(self.edit_track.text())
        car = _slug(self.edit_car.text())
        if not track and not car:
            return
        if track and car:
            self.edit_alias.setText(f"{track}_{car}")
        else:
            self.edit_alias.setText(track or car)

    def _collect(self) -> dict:
        return {
            "track_name": self.edit_track.text().strip() or None,
            "car_name": self.edit_car.text().strip() or None,
            "run_alias": self.edit_alias.text().strip() or None,
            "notes": self.edit_notes.toPlainText().strip() or None,
        }

    def _emit_apply(self) -> None:
        self.sig_apply_meta.emit(self._collect())

    def _emit_start_new_run(self) -> None:
        self.sig_start_new_run.emit(self._collect())