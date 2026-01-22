# src/app.py
import os
import sys
import subprocess
import platform

from dataclasses import replace
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from src.telemetry.gt7communication import GT7Communication
from src.core.race_state import RaceState
from src.core.events import EventEngine
from src.core.telemetry_session import TelemetrySession
from src.voice.tts import VoiceEngine
from src.ui.main_window import MainWindow

# Thesis/research layer (additive). Disable with RESEARCH_ENABLED=0.
from src.research.config import load_config
from src.research.registry import create_run
from src.research.export import export_lap_bundle


class AppController(QtCore.QObject):
    def __init__(self):
        super().__init__()

        self.voice = VoiceEngine(enabled=True)
        self.state = RaceState()
        self.events = EventEngine()

        #Telemetry history for plots/map/table
        #self.session = TelemetrySession(max_samples=6000)

        # Telemetry history for plots/map/table
        # NOTE: sampling rate is controlled by the Qt timer; you confirmed GT7 is 60 Hz.
        # We keep the UI responsive by throttling visualization redraws.
        self.session = TelemetrySession(max_samples=36000)

        # Thesis/research integration (additive): dataset export + reproducible run registry
        self.research_cfg = load_config()
        self.run = None
        if self.research_cfg.enabled:
            self.run = create_run(
                output_root=self.research_cfg.output_root,
                run_tag=self.research_cfg.run_tag,
                extra_meta={
                    "sampling_hz_source_confirmed": 60,
                    "n_bins": self.research_cfg.n_bins,
                },
            )

            # Export each finalized lap automatically
            self.session.on_lap_finalized = self._on_lap_finalized

        ps_ip = os.getenv("GT7_PLAYSTATION_IP", "").strip() or None
        self.comm = GT7Communication(playstation_ip=ps_ip)
        self.comm.start()

        self.window = MainWindow()
        self.window.set_controller(self)

        self.window.sig_toggle_voice.connect(self._on_toggle_voice)
        self.window.sig_apply_settings.connect(self._on_apply_settings)
        self.window.sig_start_new_run.connect(self._on_start_new_run)
        self.window.sig_open_run_dir.connect(self._on_open_run_dir)

        
        
        self.window.sig_force_ip.connect(self._on_force_ip)
        self.window.sig_speak_now.connect(self._on_speak_now)

        self._timer = QtCore.QTimer(self)
        #self._timer.setInterval(100)  # 10 Hz
        self._timer.setInterval(16)  # 60 Hz
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        # Visualization throttling (render at ~12 Hz by default)
        self._tick_i = 0
        self._viz_div = 5
    
    @QtCore.Slot(bool)
    def _on_toggle_voice(self, enabled: bool) -> None:
        self.voice.enabled = enabled

    @QtCore.Slot(str)
    def _on_force_ip(self, ip: str) -> None:
        ip = ip.strip()
        if not ip:
            return
        self.comm.set_playstation_ip(ip)
        self.comm.restart()

    @QtCore.Slot()
    def _on_speak_now(self) -> None:
        snap = self.comm.snapshot()
        msg = self.state.format_snapshot_for_speech(snap)
        self.voice.say(msg)

    def _tick(self) -> None:
        snap = self.comm.snapshot()

        # existing scalar state (used by voice/events + overview)
        self.state.update(snap)
        self.window.update_state(self.state, snap)

        # history/session for visualizations + thesis export (60 Hz collection)
        self.session.update_from_snapshot(snap)

        # Throttle expensive redraws (keep UI responsive while sampling at ~60 Hz)
        # Ensure these are set in __init__:
        #   self._tick_i = 0
        #   self._viz_div = 5   # ~12 Hz if timer interval ~16 ms
        self._tick_i = getattr(self, "_tick_i", 0) + 1
        self._viz_div = getattr(self, "_viz_div", 5)

        if (self._tick_i % self._viz_div) == 0:
            # Prevent one missing method / plot error from hard-looping every tick
            try:
                self.window.update_visualizations(self.session, snap)
            except Exception as e:
                # If you want, replace print with logging later
                print("Visualization error:", repr(e))

        for ev in self.events.consume(self.state):
            self.window.append_event(ev)
            if self.voice.enabled and ev.should_speak:
                self.voice.say(ev.speech)

    def shutdown(self) -> None:
        try:
            self.comm.stop()
        except Exception:
            pass
        try:
            self.voice.close()
        except Exception:
            pass

    def _on_lap_finalized(self, lap, session) -> None:
        """Called by TelemetrySession after a lap is finalized (research mode only)."""
        if not self.research_cfg.enabled or self.run is None:
            return
        try:
            export_lap_bundle(
                run_dir=self.run.run_dir,
                session=session,
                lap=lap,
                n=self.research_cfg.n_bins,
                export_npz_if_available=self.research_cfg.export_npz_if_available,
                export_json_always=self.research_cfg.export_json_always,
                export_baselines=(
                    self.research_cfg.export_delta_profile or self.research_cfg.export_corner_rows
                ),
            )
        except Exception as e:
            # Never allow export failures to impact driving session.
            print("Research export error:", repr(e))
    @QtCore.Slot(dict)
    def _on_apply_settings(self, s: dict) -> None:
        # 1) UI update rate (visualizations only; keep sampling at ~60 Hz)
        ui_hz = int(s.get("ui_rate_hz", 10))
        self._viz_div = 1 if ui_hz >= 60 else 6  # 60/6 ≈ 10 Hz

        # 2) Session buffer length (requires rebuilding TelemetrySession to change deque maxlen)
        new_buf = int(s.get("buffer_samples", 36000))
        # Rebuild session only if changed; this clears history (acceptable for a new run or deliberate change).
        try:
            current_max = self.session._samples.maxlen  # ok for internal tool; you own the codebase
        except Exception:
            current_max = None

        if current_max != new_buf:
            old_cb = getattr(self.session, "on_lap_finalized", None)
            self.session = TelemetrySession(max_samples=new_buf)
            if old_cb is not None:
                self.session.on_lap_finalized = old_cb

        # 3) Research config (frozen dataclass -> replace)
        enabled = bool(s.get("research_enabled", True))

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
            run_tag=s.get("run_tag", None),
        )

        # Store extra “representation” settings (feature list, normalize) in controller for metadata
        # (These don’t change export until you update schema.py to honor them; still worth recording now.)
        self._research_features = list(s.get("features", []))
        self._research_normalize = bool(s.get("normalize", False))

        # Ensure callback installed/removed based on enabled
        if self.research_cfg.enabled:
            self.session.on_lap_finalized = self._on_lap_finalized
            if self.run is None:
                self._create_new_run()
        else:
            self.run = None
            # keep session callback unset
            self.session.on_lap_finalized = None


    def _create_new_run(self) -> None:
        self.run = create_run(
            output_root=self.research_cfg.output_root,
            run_tag=self.research_cfg.run_tag,
            extra_meta={
                "sampling_hz_source_confirmed": 60,
                "n_bins": self.research_cfg.n_bins,
                "features": getattr(self, "_research_features", None),
                "normalize": getattr(self, "_research_normalize", False),
                "ui_visualization_rate_hz": (60 if self._viz_div == 1 else 10),
                "buffer_samples": getattr(self.session._samples, "maxlen", None),
                "platform": platform.platform(),
            },
        )


    @QtCore.Slot()
    def _on_start_new_run(self) -> None:
        if not self.research_cfg.enabled:
            return
        self._create_new_run()


    @QtCore.Slot()
    def _on_open_run_dir(self) -> None:
        if self.run is None:
            return
        path = str(self.run.run_dir)
        # Cross-platform "open folder"
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            print("Open run folder error:", repr(e))


def main():
    app = QtWidgets.QApplication(sys.argv)

    # Use Fusion for predictable palette rendering across OS themes
    app.setStyle("Fusion")

    ctl = AppController()
    ctl.window.show()

    app.aboutToQuit.connect(ctl.shutdown)
    sys.exit(app.exec())



if __name__ == "__main__":
    main()
