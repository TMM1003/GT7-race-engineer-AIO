# GT7 Race Engineer (Telemetry & Research Platform)

GT7 Race Engineer is a real-time telemetry analysis and research platform for *Gran Turismo 7*.  
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
- Optional voice feedback (experimental)

### Research-Oriented Data Export
- Full-lap telemetry tensors
- Lap-to-reference delta-time profiles
- Algorithmically detected corner segments
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

## Project Structure

```text
src/
├── core/            # Session state, buffers, lap logic
├── telemetry/       # GT7 UDP communication
├── ui/              # Qt-based UI components
├── research/        # Dataset, schema, baselines, metrics
│   ├── dataset.py
│   ├── baselines.py
│   ├── schema.py
│   ├── export.py
│   └── registry.py
├── app.py           # Application entry point
scripts/
├── build_dataset.py # Offline dataset reconstruction
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
- Results are most directly applicable to comparative driving analysis rather than absolute lap time prediction

These limitations are explicitly acknowledged in the associated research work.

---

## Requirements

- Python 3.9+
- numpy
- pandas
- pyarrow (for Parquet support)
- PySide6 (UI)

Install dependencies with:

```bash
pip install -r requirements.txt
```

---

## License

This project is currently intended for academic and research use.  
Licensing will be finalized following thesis submission.
