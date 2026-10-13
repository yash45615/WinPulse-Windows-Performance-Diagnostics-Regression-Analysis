
from __future__ import annotations

import argparse
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any] | None:
    """Load a JSON object, returning None when the optional file is absent."""
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")

    return data


def markdown_value(value: Any) -> str:
    """Format a value safely for a Markdown report."""
    if value is None:
        return "Not available"

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, str):
        return value.replace("\n", " ")

    if isinstance(value, list):
        if not value:
            return "None"
        return "; ".join(markdown_value(item) for item in value[:8])

    if isinstance(value, dict):
        return ", ".join(
            f"{key}: {markdown_value(item)}"
            for key, item in list(value.items())[:8]
        )

    return str(value)


def add_json_section(
    lines: list[str],
    heading: str,
    data: dict[str, Any] | None,
    source_path: Path,
) -> None:
    """Add a concise summary of a JSON artifact."""
    lines.append(f"## {heading}")
    lines.append("")

    if data is None:
        lines.append(
            f"No artifact found at `{source_path.as_posix()}`. "
            "Run the corresponding WinPulse command to generate it."
        )
        lines.append("")
        return

    lines.append(f"Source: `{source_path.as_posix()}`")
    lines.append("")

    for key, value in data.items():
        # Avoid dumping raw per-sample data into the portfolio report.
        if isinstance(value, list) and len(value) > 8:
            lines.append(f"- **{key}:** {len(value)} entries")
        else:
            lines.append(f"- **{key}:** {markdown_value(value)}")

    lines.append("")


def build_report(
    analytics: dict[str, Any] | None,
    benchmark: dict[str, Any] | None,
    power: dict[str, Any] | None,
    analytics_path: Path,
    benchmark_path: Path,
    power_path: Path,
) -> str:
    """Build a Markdown engineering report from available artifacts."""
    generated_at = datetime.now(timezone.utc).isoformat()

    lines = [
        "# WinPulse Engineering Report",
        "",
        f"- **Generated (UTC):** {generated_at}",
        f"- **Platform:** {platform.platform()}",
        f"- **Python:** {platform.python_version()}",
        "- **Project:** Windows telemetry, diagnostics, and regression analysis",
        "",
        "## Executive summary",
        "",
        "WinPulse is a Python-based engineering prototype for collecting "
        "Windows system and process telemetry, validating measurements, "
        "storing samples, identifying potential anomalies, running controlled "
        "workloads, and comparing repeatable benchmark runs.",
        "",
        "This report summarizes the artifacts available at generation time. "
        "Missing artifacts are not treated as successful experiments.",
        "",
    ]

    add_json_section(
        lines, "Telemetry and anomaly analysis", analytics, analytics_path
    )
    add_json_section(
        lines, "Benchmark comparison", benchmark, benchmark_path
    )
    add_json_section(
        lines, "Power observations", power, power_path
    )

    lines.extend([
        "## Methodology and interpretation",
        "",
        "- Benchmark comparisons are sensitive to background activity, "
        "thermal conditions, power mode, and other system variability.",
        "- A detected anomaly is a signal for investigation, not proof of "
        "a root cause.",
        "- Battery percentage and estimated remaining time are not direct "
        "measurements of watts or watt-hours.",
        "- Synthetic workloads are controlled experiments and do not "
        "represent every real-world Windows workload.",
        "",
        "## Reproducibility",
        "",
        "Run the automated tests:",
        "",
        "```powershell",
        "python -m pytest -v",
        "```",
        "",
        "Collect telemetry:",
        "",
        "```powershell",
        "python -m winpulse.collector --duration 60 --interval 2",
        "python -m winpulse.ingest",
        "python -m winpulse.analytics",
        "```",
        "",
        "Run a benchmark:",
        "",
        "```powershell",
        "python -m winpulse.benchmark --workload cpu "
        "--iterations 500000 --rounds 5 "
        "--output reports/benchmarks/baseline.json",
        "```",
        "",
        "## Limitations",
        "",
        "- Results depend on the host machine and current system conditions.",
        "- Short captures may miss intermittent problems.",
        "- Windows ETW trace analysis and the optional native C++ probe "
        "require additional Windows tooling that may not be installed.",
        "- This prototype does not claim to establish the root cause of "
        "every performance regression.",
        "",
        "## Evidence integrity",
        "",
        "Only the artifacts found at the specified input paths are included. "
        "No performance improvement, power saving, or root-cause finding "
        "is claimed unless supported by the supplied measurements.",
        "",
    ])

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a WinPulse engineering report."
    )
    parser.add_argument(
        "--analytics",
        type=Path,
        default=PROJECT_ROOT / "reports" / "analytics_report.json",
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=PROJECT_ROOT
        / "reports"
        / "benchmarks"
        / "candidate_comparison.json",
    )
    parser.add_argument(
        "--power",
        type=Path,
        default=PROJECT_ROOT / "reports" / "power_analysis.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT
        / "reports"
        / "portfolio_engineering_report.md",
    )
    args = parser.parse_args()

    try:
        analytics = load_json(args.analytics)
        benchmark = load_json(args.benchmark)
        power = load_json(args.power)

        report = build_report(
            analytics,
            benchmark,
            power,
            args.analytics,
            args.benchmark,
            args.power,
        )

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")

        print(f"Engineering report written to: {args.output.resolve()}")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
