# GT7 Race Engineer (Desktop App)

A desktop "race engineer / crew chief" for Gran Turismo 7 (PS5), driven by the GT7 UDP telemetry stream.  
The application provides live telemetry, lap analysis, and data-driven driving feedback similar to an on-track race engineer.

## Core Features

- Desktop UI (Qt via PySide6)
- Live telemetry display
  - Lap, speed, RPM, throttle, brake, fuel
  - Last lap and best lap tracking
- Event engine with debounced announcements
- Offline voice output (pyttsx3)
- Optional automatic discovery of the PlayStation IP on the local network

## Telemetry Analysis & Visualization

- Live track map visualization
  - Auto-generated track geometry from telemetry
  - Real-time position updates
- Multi-window, dockable UI
  - Track map, graphs, tables can be shown simultaneously
  - Panels can be tabbed or popped out into separate windows
- Theme support
  - Light
  - Studio Gray
  - Dark

## Lap & Delta Analysis

- Automatic lap detection and storage
- Reference lap selection (best lap by default)
- Distance-based lap alignment
- Delta profiles
  - Speed delta (last vs reference)
  - Time delta (last vs reference)

## Sector Analysis

- Synthetic sector splitting (three equal-distance sectors)
- Sector time comparison between laps
- Sector delta display

## Corner Detection

- Automatic corner detection from reference lap geometry
- Curvature-based corner segmentation
- Per-corner direction classification (left / right)
- Corner ranking by time loss

## Corner Coaching Metrics

For each detected corner (last lap vs reference lap):

- Time loss per corner
- Brake start delta (meters)
  - Positive: braked later than reference
  - Negative: braked earlier
- Throttle reapplication delta (meters)
  - Positive: throttle applied later
  - Negative: throttle applied earlier
- Minimum speed delta (km/h)
- Exit speed delta (km/h)

These metrics are presented in a ranked table to identify where lap time is being lost and why.

## System Requirements

- Windows 10/11 recommended
- Python 3.11 or 3.12 recommended
- PS5 and PC must be on the same LAN / Wi-Fi network

## Windows Setup (Standard)
- Run the .exe

## Windows Setup (Advanced Users)

```bat
cd (containing folder)
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -U pip wheel setuptools
pip install -r requirements.txt
python -m src.app
```

#### Run (Auto Discovery)
```
python -m src.app
```


## Troubleshooting Checklist

### If auto-discovery fails

#### Set the PS5 IP explicitly
- set GT7_PLAYSTATION_IP='PS5s IPV4'
- python -m src.app

### Verify the following
- Allow UDP inbound on port 33740 in Windows Firewall
- Ensure your router does not isolate Wi-Fi clients (AP isolation)
- PS5 must be powered on and Gran Turismo 7 must be running
- If auto-discovery fails, set GT7_PLAYSTATION_IP manually
