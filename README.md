# GT7 Machine Learning Tool (Telemetry & Research Platform)

GT7 Machine Learning Tool is a real-time telemetry analysis and research platform for *Gran Turismo 7*.
It combines live telemetry capture, deterministic lap and corner analysis, and reproducible dataset generation to support both **driver performance analysis** and **machine learning research**.

The project is developed alongside an academic thesis focused on **corner-level performance loss analysis using telemetry-derived features**, with an emphasis on interpretability and reproducibility.

---

## Key Capabilities

### Live Telemetry Capture
- UDP telemetry ingestion from GT7
- Real-time vehicle state monitoring (speed, RPM, throttle, brake, gear, etc.)
- Session-aware lap tracking and buffering
- Reference lap selection and comparison

### Visualization
- Track map (2D and 3D elevation views)
- Time delta visualization (last lap vs reference)
- Telemetry graphs (speed, throttle, brake, coasting)
- Corner-level performance tables

### Research-Oriented Data Export
- Full-lap telemetry tensors
- Lap-to-reference delta-time profiles
- Algorithmically detected corner segments
- Optional external track/raceline/boundary baselines from curated `trackdb`
- Deterministic artifact export at lap finalization

---

## Corner Definition (Important)

Corners are **not** defined using external track metadata or FIA corner labels.

Instead, the system defines corners **algorithmically** as:

> Contiguous regions of sustained track curvature derived from the reference lap.

- Curvature is computed from `(X, Z)` position telemetry
- Corner boundaries are detected on the reference lap
- The same boundaries are reused across all subsequent laps
- Multi-apex or chicane complexes may be represented as a single corner instance

This approach is:
- deterministic
- track-agnostic
- reproducible
- aligned with driver control behavior rather than track naming conventions

---

## Dataset Generation

### Corner-Level Dataset

For each run, the system can construct a **machine-learning-ready dataset** where:

- Each row corresponds to **one corner instance from one lap**
- The primary target variable is **corner-level time loss or gain** relative to the reference lap (milliseconds)
- Feature columns include:
  - entry / exit speed
  - throttle and brake behavior
  - curvature-derived metrics
  - engineered summary statistics

This dataset is suitable for:
- supervised regression
- feature importance analysis
- comparison between heuristic metrics and learned models

---

## External Track Geometry Baselines

The project includes a curated `trackdb/` subset from
[`TUMFTM/racetrack-database`](https://github.com/TUMFTM/racetrack-database)
for GT7-supported real-world circuits. The upstream project is licensed under
LGPL-3.0; attribution and a local copy of the upstream license are kept in
`trackdb/ATTRIBUTION.md` and `trackdb/LICENSE`.

Each retained track provides:

- `tracks/<Track>.csv`: centerline plus left/right track widths
- `racelines/<Track>.csv`: optimized minimum-curvature raceline
- optional raceline and curvature reference plots

When the current run metadata maps to a retained `trackdb` circuit, the app
fits the external raceline into GT7 `(X, Z)` coordinates using the current
reference lap. The same transform is applied to the centerline and track
widths, enabling GT7-space boundary and raceline comparisons.

The Track Map view also shows a **TrackDB Baseline** panel with fit RMSE,
raceline error, left/right margin, and off-track bin counts for the latest
completed lap. The same panel controls TrackDB overlay visibility for the
raceline, boundaries, and centerline, plus trace color modes for TrackDB line
error, margin, off-track state, and time delta. Replay mode exposes the same
TrackDB baseline controls in the Replay tab so recorded laps can be reviewed
against the external reference without leaving the replay menu.

Currently retained mappings include:

- Brands Hatch
- Circuit de Barcelona-Catalunya
- Circuit Gilles-Villeneuve / Montreal
- Autodromo Nazionale Monza
- Nurburgring GP
- Autodromo de Interlagos / Sao Paulo
- Circuit de Spa-Francorchamps
- Red Bull Ring / Spielberg
- Suzuka Circuit
- Yas Marina Circuit

Known incompatible layout variants are intentionally not mapped to full-course
geometry, such as Nordschleife, Monza No Chicane, Suzuka East, Red Bull Ring
Short, and Brands Hatch Indy.

### Exported Baseline Metrics

Future lap exports include resampled GT7 path geometry:

- `laps/lap_####.json` -> `geometry.points_xz`
- `laps/lap_####.npz` -> `points_xz` and `distance_axis_m`

When external geometry is available, baseline JSON files include an
`external_track` block with:

- alignment transform and fit error statistics
- raceline error
- lateral offset from centerline
- left/right track margin
- off-track bin counts
- a `track_alignment_<Track>.json` artifact containing the aligned track
  geometry in GT7 coordinates

Old run artifacts created before this feature do not contain `geometry.points_xz`,
so offline alignment requires newly exported laps.

### Offline Alignment QA

Use the helper script to validate local `trackdb` files or write an alignment
artifact/plot for a run:

```bash
python scripts/align_trackdb_to_gt7.py --cache-only --track "Circuit de Spa-Francorchamps"
python scripts/align_trackdb_to_gt7.py --run-dir data/runs/<RUN_ID> --track "Circuit de Spa-Francorchamps" --plot
```

---

## Offline Dataset Reconstruction (CLI)

In addition to live telemetry capture, datasets can be rebuilt **offline** from previously recorded run artifacts.  
This enables reproducible dataset construction without launching the UI and clean separation between data collection and model development.

A dedicated script is provided:

```bash
python scripts/build_dataset.py data/runs/<RUN_ID> --overwrite
```

Where `<RUN_ID>` is a single run directory containing:
- `run.json`
- `laps/`
- `corners/`

### Outputs

Each dataset build produces:

- `corner_dataset.csv`  
  Human-readable format for inspection and debugging

- `corner_dataset.parquet`  
  Columnar, ML-optimized format for training and analysis

- `corner_dataset_build.json`  
  Provenance and metadata, including schema version and build statistics

### Format Notes
- CSV is intended for inspection and lightweight analysis
- Parquet is the canonical format for machine learning workflows due to efficient column access, type preservation, and reduced file size

---

## Model Training

The `Research/Config` tab now includes an offline **Model Training** panel for
training saved regression models directly from:

- the current run
- an existing run folder
- a `corner_dataset.csv` or `corner_dataset.parquet` file

The training workflow supports:

- `CatBoost`, `Random Forest`, and `Ridge`
- `all_numeric` and `heuristics` feature modes
- grouped cross-validation
- permutation-importance evaluation
- optional dataset rebuild before training
- saved model artifacts written into a run's `models/` folder

Typical run-folder output:

- `models/<model>_<feature_mode>.joblib`
- `models/<model>_<feature_mode>.json`

You can also train from the CLI:

```bash
python scripts/train_model.py data/runs/<RUN_ID> --model catboost --feature-mode all_numeric
```

For the full UI walkthrough and tutorial, see:

- [ModelTraining_README.md](ModelTraining_README.md)

---

## Project Structure

```text
src/
├── core/            # Session state, buffers, lap logic
├── telemetry/       # GT7 UDP communication
├── ui/              # Qt-based UI components
├── track_geometry/  # External track alignment and boundary metrics
├── research/        # Dataset, schema, baselines, metrics
│   ├── dataset.py
│   ├── baselines.py
│   ├── schema.py
│   ├── export.py
│   └── registry.py
├── app.py           # Application entry point
scripts/
├── build_dataset.py # Offline dataset reconstruction
├── align_trackdb_to_gt7.py # External geometry alignment QA
trackdb/
└── tracks/, racelines/ # Curated TUMFTM GT7-compatible geometry
data/
└── runs/            # Recorded telemetry runs
```

---

## Research Focus

This software directly supports an academic research project with the following goals:

- Quantify **localized performance loss** at the corner level
- Compare deterministic, heuristic telemetry metrics against learned models
- Evaluate whether machine learning can explain performance variance beyond hand-engineered features
- Maintain interpretability, empirical grounding, and reproducibility throughout

Machine learning models are used as **evaluative tools**, not as real-time control systems.

Initial experiments prioritize:
- supervised regression on engineered corner features
- transparent model comparison and feature attribution

More complex sequence-based or unsupervised approaches may be explored in later stages but are not central to the current research objectives.

---

## Experimental Validity & Limitations

- Telemetry data is sourced from a closed commercial simulator (GT7)
- Track and vehicle conditions are controlled but simulator-specific
- Corner definitions are geometry-based and may not align with official corner naming
- External track geometry is real-world/OSM-derived and aligned to GT7 by a fitted transform; it is useful as a baseline, not absolute GT7 ground truth
- Results are most directly applicable to comparative driving analysis rather than absolute lap time prediction

These limitations are explicitly acknowledged in the associated research work.

---

## Requirements

- Python 3.9+
- PySide6 (UI)
- Pycryptodome
- Pyqtgraph
- PyOpenGL
- Scikit
- numpy
- pandas
- pyarrow (for Parquet support)

Install dependencies with:

```bash
pip install -r requirements.txt
```

---

## Windows Installer

Build the bundled executable:

```bat
package.bat
```

Build the friend-facing installer:

```bat
build_installer.bat
```

The installer is written to:

```text
dist-installer\GT7-Machine-Learning-Tool-Setup.exe
```

Installed runs are stored by default in:

```text
Documents\GT7 Machine Learning Tool\data\runs
```

Friends should send the full `runs` folder or the specific timestamped run
folder from that location. The installed app also includes
`Participant_Guide.md` with study information, setup,
firewall, and upload notes.

If Inno Setup is not installed yet, you can still create a zip-based friend
package:

```bat
build_friend_package.bat
```

That writes:

```text
dist-installer\GT7-Machine-Learning-Tool-Install.zip
```

Friends can unzip it and run `install.bat`.

---

## License

GT7 Machine Learning Tool is released under a custom source-available,
non-commercial research-use license. See [LICENSE](LICENSE).

In short: official releases may be used for personal, academic, educational,
and non-commercial telemetry collection and research. Commercial use,
redistribution of modified builds, sublicensing, resale, and rebranding are
not permitted without written permission.

The bundled `trackdb/` data is derived from
[`TUMFTM/racetrack-database`](https://github.com/TUMFTM/racetrack-database)
and remains subject to its upstream LGPL-3.0 license. See
`trackdb/ATTRIBUTION.md` and `trackdb/LICENSE`.

Additional dependency and trademark notes are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
