import queue
import threading

import pyttsx3


class VoiceEngine:
    # Offline TTS using pyttsx3. Runs a worker thread so speaking doesn't block the UI.

    def __init__(self, enabled: bool = True, rate: int = 185):
        self.enabled = enabled
        self._q: "queue.Queue[str]" = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", rate)

        self._thread.start()

    def say(self, text: str) -> None:
        if not self.enabled:
            return
        if not text:
            return
        self._q.put(text)

    def close(self) -> None:
        self._stop.set()
        self._q.put("")  # unblock
        try:
            self._thread.join(timeout=1.0)
        except Exception:
            pass
        try:
            self._engine.stop()
        except Exception:
            pass

    def _run(self) -> None:
        while not self._stop.is_set():
            text = self._q.get()
            if self._stop.is_set():
                break
            if not text:
                continue
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception:
                continue
