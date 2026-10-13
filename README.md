# WinPulse — Windows Performance Diagnostics & Regression Analysis

**A Windows-focused engineering toolkit for system telemetry, performance anomaly detection, controlled workload simulation, benchmark comparison, and power-aware diagnostics.**

WinPulse is a Python-based engineering project designed to explore how operating-system performance can be measured, investigated, and validated through repeatable experiments. It combines system and process monitoring, data quality checks, SQLite storage, anomaly detection, benchmark comparisons, and automated testing.

The goal is to build a reproducible workflow for identifying unusual resource usage and investigating potential performance regressions on Windows.

## Key Features

- **System Telemetry Collection:** Capture CPU, memory, and other supported system-level metrics over time.
- **Process Monitoring:** Collect process-level resource usage to help identify resource-intensive applications.
- **Data Quality Validation:** Validate telemetry records, reject invalid values, and normalize timestamps.
- **SQLite Storage:** Store validated system and process samples for subsequent analysis.
- **Performance Analytics:** Generate summary statistics, flag potential anomalies, and rank resource-intensive processes.
- **Controlled Workload Simulation:** Run bounded CPU, memory, and mixed workloads to explore system behavior.
- **Benchmarking:** Execute repeated CPU or memory benchmark runs and compare candidate results against a baseline.
- **Power-Aware Diagnostics:** Capture Windows battery and AC status where supported and analyze available observations.
- **Engineering Reports:** Generate a Markdown report summarizing available analytics, benchmark, and power artifacts.
- **Automated Testing:** Use pytest to validate core behavior and GitHub Actions to automate regression checks.

## Architecture

```text
Windows System
      |
      v
Telemetry Collection
      |
      v
CSV Samples
      |
      v
Data Quality Validation
      |
      v
SQLite Storage
      |
      v
Performance Analytics
      |
      +-------------------+
      |                   |
      v                   v
Anomaly Detection    Process Rankings
      |
      v
Benchmark & Workload Experiments
      |
      v
Power Analysis and Engineering Reports
      |
      v
Automated Regression Testing
```

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Telemetry, analysis, simulation, and reporting |
| psutil | System and process monitoring |
| SQLite | Local telemetry storage |
| ctypes | Access to supported Windows system APIs |
| pytest | Automated unit and integration tests |
| Git and GitHub | Version control and project collaboration |
| GitHub Actions | Continuous integration and regression testing |

## Project Structure

```text
WinPulse/
├── winpulse/
│   ├── collector.py
│   ├── quality.py
│   ├── storage.py
│   ├── ingest.py
│   ├── analytics.py
│   ├── simulator.py
│   ├── benchmark.py
│   ├── power.py
│   ├── power_analysis.py
│   └── release_report.py
├── tests/
│   ├── test_collector.py
│   ├── test_quality.py
│   ├── test_storage.py
│   ├── test_analytics.py
│   ├── test_simulator.py
│   ├── test_benchmark.py
│   ├── test_power.py
│   └── test_release_report.py
├── data/
├── reports/
├── .github/
│   └── workflows/
│       └── tests.yml
├── requirements.txt
├── .gitignore
└── README.md
```

*The tree describes the intended project layout. Keep it aligned with the files actually present in your repository.*

## Getting Started

### Prerequisites

- Windows 10 or Windows 11
- Python 3.10 or a compatible version supported by the project
- Git
- PowerShell

Docker is not required.

### 1. Clone the repository

```powershell
git clone https://github.com/YOUR_USERNAME/WinPulse.git
cd WinPulse
```

Replace `YOUR_USERNAME` with your GitHub username.

### 2. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pytest
```

### 4. Run the automated tests

```powershell
python -m pytest -v
```

The tests cover telemetry collection, data validation, storage, analytics, workload simulation, benchmarking, power analysis, and report generation.

## Usage

### Collect system and process telemetry

```powershell
python -m winpulse.collector --duration 60 --interval 2
```

This collects telemetry for 60 seconds at a two-second interval. Output files are written to the configured data directory.

### Ingest telemetry into SQLite

```powershell
python -m winpulse.ingest
```

The ingestion pipeline validates the available CSV samples and stores accepted records in the local database.

### Run performance analytics

```powershell
python -m winpulse.analytics
```

The analytics pipeline produces summary statistics, potential anomaly indicators, and process rankings based on the collected data.

### Simulate a CPU workload

```powershell
python -m winpulse.simulator --mode cpu --duration 10 --memory-mb 0
```

### Simulate a memory workload

```powershell
python -m winpulse.simulator --mode memory --duration 5 --memory-mb 64
```

### Run a CPU benchmark

```powershell
python -m winpulse.benchmark --workload cpu --iterations 500000 --rounds 5 --output reports/benchmarks/baseline.json
```

Benchmark comparison can be performed by supplying a baseline to a subsequent run:

```powershell
python -m winpulse.benchmark --workload cpu --iterations 500000 --rounds 5 --output reports/benchmarks/candidate.json --baseline reports/benchmarks/baseline.json
```

### Collect power-status observations

```powershell
python -m winpulse.power --duration 30 --interval 2 --output data/power_phase8.jsonl
```

Analyze the collected data:

```powershell
python -m winpulse.power_analysis --input data/power_phase8.jsonl --output reports/power_analysis.json
```

### Generate an engineering report

```powershell
python -m winpulse.release_report
```

The report summarizes the artifacts available at the configured paths. Missing inputs are reported rather than treated as successful experiments.

## Automated Testing and CI

WinPulse includes a GitHub Actions workflow intended to:

1. Check out the repository.
2. Set up Python on a Windows runner.
3. Install dependencies.
4. Execute the pytest suite.
5. Fail the workflow if any test fails.

This helps identify regressions before changes are merged.

Workflow location:

```text
.github/workflows/tests.yml
```

## Engineering Design Principles

**Reproducibility:** Use consistent workload parameters and repeated measurements when comparing performance.

**Data quality:** Validate telemetry before storing it or drawing conclusions from it.

**Controlled experiments:** Keep workload duration and resource allocation bounded.

**Regression awareness:** Treat performance differences as investigation signals rather than definitive proof of a defect.

**Evidence-based reporting:** Report measured outcomes and disclose missing data instead of inventing results.

## Limitations

- Results depend on the host machine, background processes, thermal conditions, and power settings.
- An anomaly detector identifies suspicious behavior but does not independently establish root cause.
- Short captures may miss intermittent performance problems.
- Benchmark timings are sensitive to system load and should be interpreted across repeated runs.
- Battery percentage and estimated remaining time are not direct measurements of power consumption in watts or energy in watt-hours.
- Windows Performance Recorder/Analyzer integration and the optional native C++ probe require additional tooling and setup if those features are pursued.

## Future Improvements

- Integrate Windows ETW traces into a repeatable investigation workflow.
- Add native diagnostics through Windows APIs and a compiled C++ probe.
- Introduce richer regression baselines and environment-aware comparisons.
- Expand diagnostic reports with trace-linked evidence.
- Strengthen CI coverage and publish reproducible benchmark examples.

## Project Status

WinPulse is an evolving engineering prototype for learning and demonstrating Windows performance diagnostics and regression-analysis workflows. Features should be considered complete only when implemented, tested, and documented in the repository.

## Author

**Yash Kalbhile**

GitHub: https://github.com/yash45615

LinkedIn: Add your LinkedIn profile URL here.
