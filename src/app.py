# src/app.py
import os
import sys
import subprocess
import platform
import json
import time

from dataclasses import replace
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from src.telemetry.gt7communication import GT7Communication
from src.core.race_state import RaceState
from src.core.events import EventEngine
from src.core.telemetry_session import TelemetrySession
from src.ui.main_window import MainWindow

from src.research.config import load_config
from src.research.registry import create_run
from src.research.export import export_lap_bundle
from src.research.schema import FeatureSpec, SCHEMA_VERSION, schema_hash
from src.research.dataset import build_and_save_corner_dataset


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _safe_write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


class AppController(QtCore.QObject):
    def __init__(self):
        super().__init__()

        self.state = RaceState()
        self.events = EventEngine()

        self.session = TelemetrySession(max_samples=36000)

        self.research_cfg = load_config()

        # No run should exist at app startup
        self.run = None

        # Do not attach lap-finalize callback until research is enabled
        self.session.on_lap_finalized = None

        self._run_meta = {
            "track_name": None,
            "car_name": None,
            "run_alias": None,
            "notes": None,
        }

        self._research_features = list(self.research_cfg.features)
        self._research_normalize = False
        self._tick_i = 0
        self._viz_div = 5

        ps_ip = os.getenv("GT7_PLAYSTATION_IP", "").strip() or None
        self.comm = GT7Communication(playstation_ip=ps_ip)
        self.comm.start()

        self.window = MainWindow()
        self.window.set_controller(self)

        self.window.sig_apply_settings.connect(self._on_apply_settings)
        self.window.sig_start_new_run.connect(self._on_start_new_run)
        self.window.sig_open_run_dir.connect(self._on_open_run_dir)
        self.window.sig_export_dataset.connect(self._on_export_dataset)

        self.window.sig_apply_run_metadata.connect(self._on_apply_run_metadata)
        self.window.sig_start_new_run_with_meta.connect(self._on_start_new_run_with_meta)

        self.window.sig_set_reference_best.connect(self._on_set_reference_best)
        self.window.sig_toggle_reference_lock.connect(self._on_toggle_reference_lock)

        self.window.sig_force_ip.connect(self._on_force_ip)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self._refresh_run_meta_ui()
        self._refresh_reference_ui()

    @QtCore.Slot(str)
    def _on_force_ip(self, ip: str) -> None:
        ip = ip.strip()
        if not ip:
            return
        self.comm.set_playstation_ip(ip)
        self.comm.restart()

    def _tick(self) -> None:
        snap = self.comm.snapshot()
        if not snap or not snap.get("in_race"):
            return

        self.state.update(snap)
        self.window.update_state(self.state, snap)

        self.session.update_from_snapshot(snap)

        self._tick_i = getattr(self, "_tick_i", 0) + 1
        self._viz_div = getattr(self, "_viz_div", 5)

        if (self._tick_i % self._viz_div) == 0:
            try:
                self.window.update_visualizations(self.session, snap)
            except Exception as e:
                print("Visualization error:", repr(e))

        for ev in self.events.consume(self.state):
            self.window.append_event(ev)

        # Keep reference label current
        if (self._tick_i % 30) == 0:
            self._refresh_reference_ui()

    def shutdown(self) -> None:
        try:
            self.comm.stop()
        except Exception:
            pass

    def _telemetry_live(self) -> bool:
        # Strongest available signal: we are in-race and receiving valid packets
        try:
            return bool(getattr(self.state, "in_race", False))
        except Exception:
            return False

    def _feature_spec_snapshot(self) -> dict:
        feats = list(self._research_features or list(self.research_cfg.features))
        return {
            "schema_version": int(SCHEMA_VERSION),
            "n_bins": int(self.research_cfg.n_bins),
            "features": feats,
            "normalize": bool(self._research_normalize),
        }

    def _build_run_extra_meta(self) -> dict:
        spec = FeatureSpec(tuple(self._research_features or list(self.research_cfg.features)))
        fss = self._feature_spec_snapshot()
        sh = schema_hash(spec=spec, normalize=bool(self._research_normalize), n_bins=int(self.research_cfg.n_bins))

        ref_info = self.session.reference_info()

        return {
            "sampling_hz_source_confirmed": 60,
            "n_bins": int(self.research_cfg.n_bins),
            "features": list(spec.features),
            "normalize": bool(self._research_normalize),
            "schema_version": int(SCHEMA_VERSION),
            "schema_hash": sh,
            "feature_spec": fss,
            "ui_visualization_rate_hz": (60 if getattr(self, "_viz_div", 6) == 1 else 10),
            "buffer_samples": getattr(getattr(self.session, "_samples", None), "maxlen", None),
            "platform": platform.platform(),
            "track_name": self._run_meta.get("track_name"),
            "car_name": self._run_meta.get("car_name"),
            "run_alias": self._run_meta.get("run_alias"),
            "notes": self._run_meta.get("notes"),
            "reference_locked": bool(ref_info.get("locked", False)),
            "reference_lap_num": ref_info.get("lap_num"),
            "reference_lap_time_ms": ref_info.get("lap_time_ms"),
        }

    def _create_new_run(self) -> None:
        # Create the run directory lazily and immediately stamp metadata
        self.run = create_run(
            output_root=self.research_cfg.output_root,
            run_alias=self._run_meta.get("run_alias"),
            metadata=self._run_meta,
        )

        # Arm lap finalization callback only once a run exists
        self.session.on_lap_finalized = self._on_lap_finalized

        # Stamp extended run metadata right away (schema, features, buffer, reference, etc.)
        try:
            self._patch_run_json(Path(self.run.run_dir), self._build_run_extra_meta())
        except Exception:
            pass

        self._refresh_run_meta_ui()

    def _patch_run_json(self, run_dir: Path, patch: dict) -> None:
        run_path = run_dir / "run.json"
        data = _read_json(run_path) if run_path.exists() else {}
        for k, v in patch.items():
            data[k] = v
        _safe_write_json(run_path, data)

    def _patch_manifest(self, run_dir: Path, entry: dict) -> None:
        mpath = run_dir / "manifest.json"
        data = _read_json(mpath) if mpath.exists() else {}
        data.setdefault("run_id", run_dir.name)
        data.setdefault("created_utc", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        data["updated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        data.setdefault("dataset_builds", [])
        data["dataset_builds"].append(entry)
        _safe_write_json(mpath, data)

    def _on_lap_finalized(self, lap, session) -> None:
        if not self.research_cfg.enabled:
            return

        # Lazy run creation at first finalized lap
        if self.run is None:
            self._create_new_run()

        feats = list(self._research_features or list(self.research_cfg.features))
        spec = FeatureSpec(tuple(feats))

        try:
            export_lap_bundle(
                run_dir=self.run.run_dir,
                session=session,
                lap=lap,
                n=int(self.research_cfg.n_bins),
                spec=spec,
                export_npz_if_available=bool(self.research_cfg.export_npz_if_available),
                export_json_always=bool(self.research_cfg.export_json_always),
                export_baselines=(bool(self.research_cfg.export_delta_profile) or bool(self.research_cfg.export_corner_rows)),
                export_corners=bool(self.research_cfg.export_corners),
            )

            # Keep run.json aligned with current reference state
            ref_info = self.session.reference_info()
            self._patch_run_json(Path(self.run.run_dir), {
                "reference_locked": bool(ref_info.get("locked", False)),
                "reference_lap_num": ref_info.get("lap_num"),
                "reference_lap_time_ms": ref_info.get("lap_time_ms"),
            })
        except Exception as e:
            print("Research export error:", repr(e))

    @QtCore.Slot(dict)
    def _on_apply_settings(self, s: dict) -> None:
        ui_hz = int(s.get("ui_rate_hz", 10))
        self._viz_div = 1 if ui_hz >= 60 else 6

        new_buf = int(s.get("buffer_samples", 36000))
        try:
            current_max = self.session._samples.maxlen
        except Exception:
            current_max = None

        if current_max != new_buf:
            old_cb = getattr(self.session, "on_lap_finalized", None)
            locked = self.session.reference_locked()
            ref = self.session.reference_info().get("lap_num")

            self.session = TelemetrySession(max_samples=new_buf)

            # Preserve callback and reference behavior through session rebuild
            self.session.on_lap_finalized = old_cb
            if ref is not None:
                self.session.set_reference_by_lap_num(int(ref))
            self.session.lock_reference(bool(locked))

        enabled = bool(s.get("research_enabled", True))

        # run_tag is deprecated. Do not accept or store it.
        self.research_cfg = replace(
            self.research_cfg,
            enabled=enabled,
            output_root=str(s.get("output_root") or "data/runs"),
            n_bins=int(s.get("n_bins", 300)),
            export_npz_if_available=bool(s.get("export_npz_if_available", True)),
            export_json_always=bool(s.get("export_json_always", True)),
            export_corners=bool(s.get("export_corners", True)),
            export_delta_profile=bool(s.get("export_delta_profile", True)),
            export_corner_rows=bool(s.get("export_corner_rows", True)),
        )

        self._research_features = list(s.get("features", []))
        self._research_normalize = bool(s.get("normalize", False))

        if self.research_cfg.enabled:
            # Arm exports, but do NOT create a run here
            self.session.on_lap_finalized = self._on_lap_finalized

            # If a run already exists, keep metadata aligned
            if self.run is not None:
                try:
                    self._patch_run_json(Path(self.run.run_dir), self._build_run_extra_meta())
                except Exception:
                    pass
        else:
            # Disarm research behavior and drop current run pointer
            self.run = None
            self.session.on_lap_finalized = None

        self._refresh_run_meta_ui()
        self._refresh_reference_ui()

    @QtCore.Slot()
    def _on_start_new_run(self) -> None:
        if not self.research_cfg.enabled:
            return

        # Avoid creating empty runs from menus or pre-race screens
        if not self._telemetry_live():
            QtWidgets.QMessageBox.information(
                self.window,
                "Not connected",
                "Start a run only after GT7 telemetry is live (in-race).",
            )
            return

        self._create_new_run()

    @QtCore.Slot()
    def _on_open_run_dir(self) -> None:
        if self.run is None:
            return

        path = str(self.run.run_dir)
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            print("Open run folder error:", repr(e))

    @QtCore.Slot()
    def _on_export_dataset(self) -> None:
        if self.run is None:
            print("No active run; cannot export dataset.")
            return

        try:
            paths, report = build_and_save_corner_dataset(self.run.run_dir)

            entry = {
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "paths": {
                    "csv": str(paths.get("csv")) if paths.get("csv") else None,
                    "parquet": str(paths.get("parquet")) if paths.get("parquet") else None,
                    "build": str(paths.get("build")) if paths.get("build") else None,
                },
                "counts": {
                    "corners_seen": report.corners_seen,
                    "rows_emitted": report.rows_emitted,
                    "corners_skipped": report.corners_skipped,
                },
                "schema_version": report.schema_version,
                "schema_hash": report.schema_hash,
                "skip_reasons": report.reasons,
            }
            self._patch_manifest(Path(self.run.run_dir), entry)

            # QA summary text for UI
            lines = []
            lines.append(f"Run: {Path(self.run.run_dir).name}")
            lines.append(f"Rows: {report.rows_emitted}  (seen {report.corners_seen}, skipped {report.corners_skipped})")
            lines.append(f"Schema: v{report.schema_version}  hash {report.schema_hash}")
            if report.reasons:
                lines.append("Skips:")
                for k, v in sorted(report.reasons.items(), key=lambda kv: (-kv[1], kv[0])):
                    lines.append(f"  - {k}: {v}")
            else:
                lines.append("Skips: none")

            self.window.set_qa_summary("\n".join(lines))

            print("Dataset export complete:")
            print("  CSV:", paths.get("csv"))
            if paths.get("parquet"):
                print("  Parquet:", paths.get("parquet"))
            print("  Rows:", report.rows_emitted)
        except Exception as e:
            print("Dataset export error:", repr(e))

    def _refresh_run_meta_ui(self) -> None:
        try:
            run_id = getattr(self.run, "run_id", None) if self.run else None
            run_dir = str(getattr(self.run, "run_dir", "")) if self.run else None
            self.window.set_current_run_info(
                run_id=run_id,
                run_dir=run_dir,
                track_name=self._run_meta.get("track_name"),
                car_name=self._run_meta.get("car_name"),
                run_alias=self._run_meta.get("run_alias"),
            )
        except Exception:
            pass

    def _refresh_reference_ui(self) -> None:
        try:
            info = self.session.reference_info()
            self.window.set_reference_info(
                lap_num=info.get("lap_num"),
                lap_time_ms=info.get("lap_time_ms"),
                locked=bool(info.get("locked", False)),
            )
        except Exception:
            pass

    @QtCore.Slot(dict)
    def _on_apply_run_metadata(self, meta: dict) -> None:
        self._run_meta.update(meta or {})

        if self.run is not None:
            self._patch_run_json(Path(self.run.run_dir), {
                "track_name": self._run_meta.get("track_name"),
                "car_name": self._run_meta.get("car_name"),
                "run_alias": self._run_meta.get("run_alias"),
                "notes": self._run_meta.get("notes"),
            })

        self._refresh_run_meta_ui()

    @QtCore.Slot(dict)
    def _on_start_new_run_with_meta(self, meta: dict) -> None:
        self._run_meta.update(meta or {})

        if not self.research_cfg.enabled:
            return

        # Avoid creating empty runs from menus or pre-race screens
        if not self._telemetry_live():
            QtWidgets.QMessageBox.information(
                self.window,
                "Not connected",
                "Start a run only after GT7 telemetry is live (in-race).",
            )
            return

        # Track/car required for research usability
        track = (self._run_meta.get("track_name") or "").strip()
        car = (self._run_meta.get("car_name") or "").strip()
        if not track or not car:
            QtWidgets.QMessageBox.warning(
                self.window,
                "Missing metadata",
                "Track name and car name should be set before starting a new run for research exports.",
            )
            return

        self._create_new_run()

    @QtCore.Slot()
    def _on_set_reference_best(self) -> None:
        ok = self.session.set_reference_best()
        if not ok:
            return
        self._refresh_reference_ui()
        if self.run is not None:
            info = self.session.reference_info()
            self._patch_run_json(Path(self.run.run_dir), {
                "reference_lap_num": info.get("lap_num"),
                "reference_lap_time_ms": info.get("lap_time_ms"),
            })

    @QtCore.Slot(bool)
    def _on_toggle_reference_lock(self, locked: bool) -> None:
        self.session.lock_reference(bool(locked))
        self._refresh_reference_ui()
        if self.run is not None:
            info = self.session.reference_info()
            self._patch_run_json(Path(self.run.run_dir), {
                "reference_locked": bool(locked),
                "reference_lap_num": info.get("lap_num"),
                "reference_lap_time_ms": info.get("lap_time_ms"),
            })


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    ctl = AppController()
    ctl.window.show()

    app.aboutToQuit.connect(ctl.shutdown)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
