# GT7 Race Engineer (Desktop App)

A desktop **race engineer / crew chief** application for **Gran Turismo 7 (PS5)** driven by the GT7 UDP telemetry stream.

This repository intentionally supports **two tightly coupled but distinct use cases**:

1. **GT7 Race Engineer Software** – a real‑time telemetry analysis and driver‑feedback tool.
2. **Research & Thesis Platform** – a controlled experimental system for AI‑driven motorsport telemetry analysis.

The sections below are organized accordingly.

---

# Part I — Software (GT7 Race Engineer)

## Purpose

The software component functions as a **live race engineer dashboard**, designed to help a driver understand where lap time is gained or lost while driving in Gran Turismo 7.

It focuses on:
- Real‑time situational awareness
- Lap‑to‑lap comparison
- Localizing performance differences to specific corners

---

## Core Software Features

- Desktop UI (Qt via PySide6)
- Live telemetry ingestion via GT7 UDP stream
- Modular, dockable interface
- Configurable UI refresh rate (10 Hz or full 60 Hz)
- Theme support
  - Light
  - Studio Gray
  - Dark

---

## Live Telemetry Visualization

- **Track Map**
  - Auto‑generated track geometry from telemetry
  - Real‑time position and path visualization
  - Delta‑colored overlays (last vs reference lap)

- **Graphs Panel**
  - Speed, throttle, brake, RPM, gear
  - Distance‑aligned and time‑aligned views

- **Telemetry Table**
  - Live numerical values
  - Lap context and delta context

---

## Lap & Delta Analysis

- Automatic lap detection
- Distance‑based lap alignment
- Reference lap selection (best lap or user‑defined)
- Delta profiles:
  - Time delta (last vs reference)
  - Speed delta (last vs reference)

---

## Corner Detection & Coaching Analysis

- Automatic corner detection from reference lap geometry
- Curvature‑based segmentation
- Direction classification (left / right)
- Corner strength estimation

### Corner‑Level Metrics

For each detected corner (last lap vs reference lap):

- Time loss per corner (ms)
- Brake start delta (m)
- Throttle reapplication delta (m)
- Minimum speed delta (km/h)
- Exit speed delta (km/h)

Corners are ranked by time loss to localize driver mistakes or improvements.

---

## Software Usage

### Running the Application

```bash
python -m src.app
```

### Manual PS5 IP (optional)

```bash
set GT7_PLAYSTATION_IP=<PS5_IPV4_ADDRESS>
python -m src.app
```

---

# Part II — Research & Thesis Platform

## Research Motivation

Beyond live driver feedback, this software is designed as a **research‑grade telemetry instrumentation platform** supporting an academic thesis on:

> *AI‑driven analysis of motorsport telemetry using real driving data.*

Rather than relying on simulated telemetry, the system captures and structures **authentic, human‑driven racing data** suitable for quantitative modeling.

---

## Research Mode

When research mode is enabled, the application enforces experimental constraints:

- Reference lap is frozen for the duration of a run
- Lap finalization always triggers artifact export
- UI refresh rate is decoupled from telemetry sampling rate
- Outputs are deterministic and versionable

This ensures repeatability and experimental validity.

---

## Research Artifacts & Data Model

Each run produces a structured directory of artifacts:

- `laps/` – full lap telemetry tensors
- `baselines/` – lap‑to‑reference delta bundles
- `corners/` – per‑corner telemetry tensors and metadata

These artifacts form the raw material for dataset construction and modeling.

---

## Dataset Generation

A dedicated dataset builder (`src/research/dataset.py`) consolidates raw artifacts into **machine‑learning‑ready datasets**.

### Corner Dataset

- One row per **corner per lap**
- Includes:
  - Identifiers (run, lap, corner)
  - Target variable (`loss_ms`)
  - Heuristic deltas (brake, throttle, speed)
  - Engineered features derived from corner telemetry tensors

Outputs:
- `corner_dataset.csv`
- `corner_dataset.parquet` (optional)

This dataset is the primary input for ML experiments.

#### Corner Dataset Schema (`corner_dataset.csv`)

| Column Name | Type | Description | Source |
|------------|------|-------------|--------|
| `run_id` | string | Unique identifier for a data collection run | Metadata |
| `run_tag` | string | Optional user-defined run label | Metadata |
| `track_name` | string | Circuit name (e.g., Monza) | Metadata |
| `lap_num` | int | Lap number within the run | Metadata |
| `corner_uid` | string | Stable identifier for a detected corner | Derived |
| `corner_index` | int | Index of corner within the detected sequence | Derived |
| `corner_direction` | string | Left or right turn classification | Derived (geometry) |
| `corner_strength` | float | Estimated corner severity from curvature | Derived |
| `loss_ms` | float | Time gained or lost vs reference lap (ms) | Target |
| `brake_start_delta_m` | float | Braking onset difference vs reference (m) | Heuristic |
| `throttle_on_delta_m` | float | Throttle reapplication difference vs reference (m) | Heuristic |
| `min_speed_delta_kmh` | float | Minimum speed difference vs reference | Heuristic |
| `exit_speed_delta_kmh` | float | Exit speed difference vs reference | Heuristic |
| `speed_mean` | float | Mean speed through the corner | Engineered |
| `speed_min` | float | Minimum speed through the corner | Engineered |
| `speed_max` | float | Maximum speed through the corner | Engineered |
| `throttle_integral` | float | Integrated throttle usage across corner | Engineered |
| `brake_integral` | float | Integrated brake usage across corner | Engineered |
| `throttle_onset_rel` | float | Normalized throttle application point (0–1) | Engineered |
| `brake_onset_rel` | float | Normalized braking onset point (0–1) | Engineered |
| `corner_len` | int | Number of distance bins in the corner | Derived |
| `n_bins` | int | Total distance bins per lap | Metadata |
| `sampling_hz` | int | Telemetry sampling frequency (Hz) | Metadata |

**Note:** Each row corresponds to one corner instance from one lap, aligned against a fixed reference lap.

---


## AI / ML Research Direction

The platform is designed to support:

- Baseline regression models predicting corner-level time loss
- Comparison of heuristic telemetry metrics vs learned feature importance
- Explainable AI analysis of driver performance
- Corner-specific and track-specific modeling

The emphasis is on **interpretability and causal insight**, not just predictive accuracy.

---

### Experimental Validity & Limitations

This system is designed to support **controlled, repeatable telemetry experiments**, but its results are subject to the following assumptions and constraints:

- **Corner identity stability**  
  Corners are identified via curvature-based segmentation of a reference lap. The current implementation assumes that corner ordering and approximate boundaries remain stable across laps. Extreme driving deviations or segmentation drift may affect corner alignment.

- **Human driver variability**  
  Telemetry reflects real human inputs rather than scripted agents. While this improves ecological validity, it introduces intra-driver variability that cannot be fully controlled.

- **Single-track and limited-condition scope**  
  Initial datasets are collected on a single circuit (e.g., Monza) under consistent conditions. Results should not be generalized across tracks, vehicles, or weather without additional data collection.

- **Reference-lap dependence**  
  All delta metrics are computed relative to a fixed reference lap. Model outputs therefore reflect *relative performance differences*, not absolute driving quality.

- **Telemetry resolution constraints**  
  Gran Turismo 7 telemetry is sampled at a fixed frequency (~60 Hz). Very short-duration events (e.g., micro-corrections) may not be fully captured.

- **Simulation environment limitations**  
  While GT7 provides high-fidelity physics, results may not directly transfer to real-world motorsport contexts without validation.

These limitations are explicitly acknowledged to ensure that experimental conclusions are interpreted within appropriate bounds.

---


## Dataset Export (CLI)

```bash
python -m src.research.dataset data/runs/<RUN_ID> --track Monza
```

---

## System Requirements

- Windows 10/11 (recommended)
- Python 3.11 or 3.12
- PS5 and PC on the same LAN

---

## Installation (Development)

```bat
cd <project_root>
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -U pip wheel setuptools
pip install -r requirements.txt
python -m src.app
```

---

## Project Status

- Live telemetry & UI: **Stable**
- Corner analysis pipeline: **Stable**
- Dataset generation: **Stable**
- Baseline ML experiments: **In progress**
- Advanced AI models: **Planned**

---

## Academic Use & Notes

This repository is actively used for academic research. Dataset schemas and analysis methods may evolve, but changes are documented and versioned to preserve reproducibility.

