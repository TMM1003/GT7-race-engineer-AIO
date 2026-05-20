# GT7 Machine Learning Tool Data Collection Guide

Use this guide when collecting Gran Turismo 7 telemetry runs for Thomas.

## Before Driving

1. Install GT7 Machine Learning Tool from `GT7-Machine-Learning-Tool-Setup.exe`.
2. Keep your Windows PC and PlayStation on the same home network.
3. Start GT7 and enter a race, time trial, or practice session.
4. Launch GT7 Machine Learning Tool.
5. If Windows Firewall asks, allow access on private networks.
6. If auto-discovery does not connect, enter your PlayStation IP address in the app.

GT7 Machine Learning Tool uses UDP telemetry traffic on ports `33739` and `33740`.

## During Collection

1. Pick the correct track and car in the Research/Config tab.
2. Add a short run alias, such as `spa_gr3_practice`.
3. Click `Apply to current run` or `Start new run with metadata`.
4. Drive several clean laps.
5. Leave the app running until the laps are complete and the run folder is created.

## Data Folder

By default, collected runs are saved here:

```text
Documents\GT7 Machine Learning Tool\data\runs
```

Each run is a folder with a timestamp in its name. A normal run folder contains files such as:

```text
run.json
manifest.json
laps\
corners\
baselines\
models\
```

## What To Send

Send either:

- The whole `Documents\GT7 Machine Learning Tool\data\runs` folder, or
- The specific timestamped run folder for the session Thomas asked you to collect.

Zip the folder before sending it if possible.

## Quick Troubleshooting

- No connection: confirm PC and PlayStation are on the same network.
- Still no connection: enter the PlayStation IP manually in the app.
- Firewall prompt appeared: allow private network access.
- No run folder: drive while in an active GT7 session, then complete at least one lap.
