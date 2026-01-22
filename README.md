# GT7 Race Engineer (Desktop App)

A local desktop "race engineer/crew chief" for Gran Turismo 7 (PS5), driven by the GT7 UDP telemetry stream.

- Desktop UI (Qt via PySide6)
- Live telemetry display (lap, speed, RPM, fuel, last/best lap)
- Event engine (debounced announcements)
- Voice output (offline TTS via pyttsx3)
- Optional auto-discovery of the PlayStation IP on your LAN

## Requirements

- Windows 10/11 recommended
- Python 3.11 or 3.12 recommended
- PS5 and your PC must be on the same LAN/Wi‑Fi

## Setup (Windows)

```bat
cd gt7-race-engineer
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -U pip wheel setuptools
pip install -r requirements.txt
```

## Run

### Auto-discovery
```bat
python -m src.app
```

### Set the PS5 IP explicitly (recommended)
```bat
set GT7_PLAYSTATION_IP=192.168.68.74
python -m src.app
```

## Troubleshooting checklist

- Allow **UDP inbound** on port **33740** in Windows Firewall
- Make sure your router doesn't isolate Wi‑Fi clients (AP isolation)
- PS5 is powered on and GT7 is running
- If auto-discovery fails, set `GT7_PLAYSTATION_IP` manually

## Packaging (optional)

Create a single EXE using PyInstaller:

```bat
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed -n gt7-race-engineer src\app.py
```
