
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Conservative starting thresholds. These can be tuned later
# against measured workloads and Windows performance traces.
STATIC_THRESHOLDS = {
    "cpu_percent": 80.0,
    "memory_percent": 85.0,
    "disk_usage_percent": 90.0,
}


def load_samples(db_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load system and process samples from an existing WinPulse database."""
    db_path = Path(db_path)

    if not db_path.is_file():
        raise FileNotFoundError(
            f"Database not found: {db_path}. Run the collector and ingestion first."
        )

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row

        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

        required = {"system_samples", "process_samples"}
        missing = required - tables

        if missing:
            raise ValueError(
                "Database is missing required tables: "
                + ", ".join(sorted(missing))
            )

        system_rows = connection.execute(
            """
            SELECT timestamp, cpu_percent,
                   memory_total_bytes, memory_available_bytes,
                   memory_used_bytes, memory_percent,
                   disk_total_bytes, disk_used_bytes,
                   disk_free_bytes, disk_usage_percent
            FROM system_samples
            ORDER BY timestamp
            """
        ).fetchall()

        process_rows = connection.execute(
            """
            SELECT timestamp, pid, name, cpu_percent,
                   memory_rss_bytes, memory_percent,
                   num_threads, status
            FROM process_samples
            ORDER BY timestamp
            """
        ).fetchall()

    return (
        [dict(row) for row in system_rows],
        [dict(row) for row in process_rows],
    )


def describe_values(values: list[float]) -> dict[str, float | None]:
    """Calculate descriptive statistics without external libraries."""
    if not values:
        return {
            "count": 0,
            "average": None,
            "minimum": None,
            "maximum": None,
            "standard_deviation": None,
        }

    return {
        "count": len(values),
        "average": round(statistics.fmean(values), 3),
        "minimum": round(min(values), 3),
        "maximum": round(max(values), 3),
        "standard_deviation": round(
            statistics.pstdev(values), 3
        ) if len(values) > 1 else 0.0,
    }


def detect_anomalies(
    system_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Flag system samples that exceed a static threshold or a
    mean-plus-two-standard-deviations threshold.

    This is a lightweight screening method, not proof of a regression.
    """
    findings: list[dict[str, Any]] = []

    for metric, static_limit in STATIC_THRESHOLDS.items():
        values = [float(row[metric]) for row in system_rows]

        if not values:
            continue

        baseline_mean = statistics.fmean(values)
        baseline_std = statistics.pstdev(values)

        statistical_limit = baseline_mean + (2 * baseline_std)
        effective_limit = min(static_limit, statistical_limit)

        for row in system_rows:
            value = float(row[metric])

            if value >= effective_limit:
                findings.append({
                    "timestamp": row["timestamp"],
                    "metric": metric,
                    "observed_value": round(value, 3),
                    "static_threshold": static_limit,
                    "baseline_mean": round(baseline_mean, 3),
                    "baseline_stddev": round(baseline_std, 3),
                    "effective_threshold": round(effective_limit, 3),
                    "reason": (
                        "Value exceeded the static threshold and/or "
                        "the statistical baseline threshold."
                    ),
                })

    findings.sort(
        key=lambda item: (
            item["timestamp"],
            item["metric"],
        )
    )
    return findings


def rank_processes(
    process_rows: list[dict[str, Any]],
    limit: int = 10,
) -> dict[str, list[dict[str, Any]]]:
    """Rank process observations by CPU and resident-memory usage."""
    if limit < 1:
        raise ValueError("limit must be at least 1")

    groups: dict[tuple[int, str], list[dict[str, Any]]] = {}

    for row in process_rows:
        key = (int(row["pid"]), str(row["name"]))
        groups.setdefault(key, []).append(row)

    summaries: list[dict[str, Any]] = []

    for (pid, name), rows in groups.items():
        cpu_values = [float(row["cpu_percent"]) for row in rows]
        rss_values = [int(row["memory_rss_bytes"]) for row in rows]

        summaries.append({
            "pid": pid,
            "name": name,
            "observations": len(rows),
            "average_cpu_percent": round(
                statistics.fmean(cpu_values), 3
            ),
            "peak_cpu_percent": round(max(cpu_values), 3),
            "peak_memory_rss_bytes": max(rss_values),
            "latest_status": rows[-1]["status"],
        })

    by_average_cpu = sorted(
        summaries,
        key=lambda item: item["average_cpu_percent"],
        reverse=True,
    )

    by_peak_cpu = sorted(
        summaries,
        key=lambda item: item["peak_cpu_percent"],
        reverse=True,
    )

    by_peak_memory = sorted(
        summaries,
        key=lambda item: item["peak_memory_rss_bytes"],
        reverse=True,
    )

    return {
        "highest_average_cpu": by_average_cpu[:limit],
        "highest_peak_cpu": by_peak_cpu[:limit],
        "highest_peak_memory": by_peak_memory[:limit],
    }


def build_report(
    system_rows: list[dict[str, Any]],
    process_rows: list[dict[str, Any]],
    top_n: int = 10,
) -> dict[str, Any]:
    """Build the complete performance-analysis report."""
    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    metric_stats = {
        metric: describe_values(
            [float(row[metric]) for row in system_rows]
        )
        for metric in (
            "cpu_percent",
            "memory_percent",
            "disk_usage_percent",
        )
    }

    anomalies = detect_anomalies(system_rows)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_version": 1,
        "sample_counts": {
            "system_samples": len(system_rows),
            "process_samples": len(process_rows),
        },
        "system_metrics": metric_stats,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "process_rankings": rank_processes(process_rows, limit=top_n),
        "interpretation_notes": [
            "Threshold alerts are screening signals, not proof of a regression.",
            "A process ranking describes observed samples, not necessarily the cause of a system slowdown.",
            "CPU and memory observations depend on the collection interval and workload.",
            "A performance regression should be confirmed against a comparable baseline and, where possible, Windows trace evidence.",
        ],
    }


def analyze_database(
    db_path: Path,
    report_path: Path,
    top_n: int = 10,
) -> dict[str, Any]:
    """Load stored telemetry, analyze it, and write a JSON report."""
    system_rows, process_rows = load_samples(db_path)

    report = build_report(
        system_rows=system_rows,
        process_rows=process_rows,
        top_n=top_n,
    )

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report_path.write_text(
        json.dumps(report, indent=2, allow_nan=False),
        encoding="utf-8",
    )

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze WinPulse system and process telemetry."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data") / "winpulse.db",
        help="Path to the WinPulse SQLite database.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports") / "analytics_report.json",
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of process rankings to include.",
    )

    args = parser.parse_args()

    try:
        report = analyze_database(
            db_path=args.db,
            report_path=args.report,
            top_n=args.top,
        )
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.error(str(exc))

    print("\nWinPulse performance analysis complete")
    print("=" * 40)
    print(
        "System samples:",
        report["sample_counts"]["system_samples"],
    )
    print(
        "Process samples:",
        report["sample_counts"]["process_samples"],
    )
    print("Anomaly alerts:", report["anomaly_count"])

    for metric, stats in report["system_metrics"].items():
        print(
            f"{metric}: average={stats['average']}, "
            f"max={stats['maximum']}"
        )

    print(f"Report: {args.report.resolve()}")


if __name__ == "__main__":
    main()
