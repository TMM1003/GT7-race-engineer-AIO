# src/app.py
import os
import sys
from PySide6 import QtCore, QtWidgets

from src.telemetry.gt7communication import GT7Communication
from src.core.race_state import RaceState
from src.core.events import EventEngine
from src.core.telemetry_session import TelemetrySession
from src.voice.tts import VoiceEngine
from src.ui.main_window import MainWindow


class AppController(QtCore.QObject):
    def __init__(self):
        super().__init__()

        self.voice = VoiceEngine(enabled=True)
        self.state = RaceState()
        self.events = EventEngine()

        # NEW: telemetry history for plots/map/table
        self.session = TelemetrySession(max_samples=6000)

        ps_ip = os.getenv("GT7_PLAYSTATION_IP", "").strip() or None
        self.comm = GT7Communication(playstation_ip=ps_ip)
        self.comm.start()

        self.window = MainWindow()
        self.window.set_controller(self)

        self.window.sig_toggle_voice.connect(self._on_toggle_voice)
        self.window.sig_force_ip.connect(self._on_force_ip)
        self.window.sig_speak_now.connect(self._on_speak_now)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(100)  # 10 Hz
        self._timer.timeout.connect(self._tick)
        self._timer.start()

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

        # NEW: history/session for visualizations
        self.session.update_from_snapshot(snap)

        # Prevent one missing method / plot error from hard-looping every 100 ms
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


def main():
    app = QtWidgets.QApplication(sys.argv)
    ctl = AppController()
    ctl.window.show()
    app.aboutToQuit.connect(ctl.shutdown)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
