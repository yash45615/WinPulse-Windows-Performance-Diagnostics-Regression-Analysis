
from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_ITERATIONS = 10_000_000
MAX_ROUNDS = 10
MAX_MEMORY_MB = 128
REGRESSION_THRESHOLD_PERCENT = 10.0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_parameters(
    workload: str,
    iterations: int,
    rounds: int,
    size_mb: int,
) -> None:
    if workload not in {"cpu", "memory"}:
        raise ValueError("workload must be 'cpu' or 'memory'")

    if not isinstance(iterations, int) or isinstance(iterations, bool):
        raise ValueError("iterations must be an integer")
    if not 1 <= iterations <= MAX_ITERATIONS:
        raise ValueError(f"iterations must be between 1 and {MAX_ITERATIONS}")

    if not isinstance(rounds, int) or isinstance(rounds, bool):
        raise ValueError("rounds must be an integer")
    if not 1 <= rounds <= MAX_ROUNDS:
        raise ValueError(f"rounds must be between 1 and {MAX_ROUNDS}")

    if not isinstance(size_mb, int) or isinstance(size_mb, bool):
        raise ValueError("size_mb must be an integer")
    if not 1 <= size_mb <= MAX_MEMORY_MB:
        raise ValueError(f"size_mb must be between 1 and {MAX_MEMORY_MB}")


def cpu_workload(iterations: int) -> int:
    """Run a deterministic integer workload and return its checksum."""
    value = 0

    for number in range(iterations):
        value = (value * 1664525 + number + 1013904223) & 0xFFFFFFFF

    return value


def memory_workload(size_mb: int) -> int:
    """Allocate bounded memory, touch each page, and return a checksum."""
    block = bytearray(size_mb * 1024 * 1024)

    checksum = 0
    for offset in range(0, len(block), 4096):
        block[offset] = (offset // 4096) % 256
        checksum = (checksum + block[offset]) & 0xFFFFFFFF

    return checksum


def run_benchmark(
    workload: str = "cpu",
    iterations: int = 500_000,
    rounds: int = 3,
    size_mb: int = 16,
) -> dict[str, Any]:
    validate_parameters(workload, iterations, rounds, size_mb)

    measurements = []
    checksums = []

    for round_number in range(1, rounds + 1):
        wall_start = time.perf_counter()
        cpu_start = time.process_time()

        if workload == "cpu":
            checksum = cpu_workload(iterations)
        else:
            checksum = memory_workload(size_mb)

        cpu_seconds = time.process_time() - cpu_start
        wall_seconds = time.perf_counter() - wall_start

        measurements.append(
            {
                "round": round_number,
                "wall_seconds": round(wall_seconds, 6),
                "process_cpu_seconds": round(cpu_seconds, 6),
            }
        )
        checksums.append(checksum)

    wall_times = [item["wall_seconds"] for item in measurements]
    cpu_times = [item["process_cpu_seconds"] for item in measurements]

    return {
        "schema_version": 1,
        "created_at": utc_now(),
        "workload": workload,
        "parameters": {
            "iterations": iterations if workload == "cpu" else None,
            "size_mb": size_mb if workload == "memory" else None,
            "rounds": rounds,
        },
        "environment": {
            "python_version": __import__("sys").version.split()[0],
            "platform": __import__("platform").platform(),
        },
        "results": {
            "median_wall_seconds": round(statistics.median(wall_times), 6),
            "median_process_cpu_seconds": round(statistics.median(cpu_times), 6),
            "min_wall_seconds": round(min(wall_times), 6),
            "max_wall_seconds": round(max(wall_times), 6),
            "checksums": checksums,
            "all_checksums_match": len(set(checksums)) == 1,
            "round_measurements": measurements,
        },
    }


def compare_benchmarks(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    threshold_percent: float = REGRESSION_THRESHOLD_PERCENT,
) -> dict[str, Any]:
    if not 0 <= threshold_percent <= 1000:
        raise ValueError("threshold_percent must be between 0 and 1000")

    baseline_workload = baseline.get("workload")
    candidate_workload = candidate.get("workload")

    if baseline_workload != candidate_workload:
        raise ValueError("Baseline and candidate workloads must match")

    if baseline.get("parameters") != candidate.get("parameters"):
        raise ValueError("Baseline and candidate parameters must match")

    baseline_time = float(baseline["results"]["median_wall_seconds"])
    candidate_time = float(candidate["results"]["median_wall_seconds"])

    if baseline_time <= 0 or candidate_time < 0:
        raise ValueError("Benchmark times must be valid positive measurements")

    change_percent = ((candidate_time - baseline_time) / baseline_time) * 100
    is_regression = change_percent >= threshold_percent

    return {
        "created_at": utc_now(),
        "workload": baseline_workload,
        "baseline_median_seconds": baseline_time,
        "candidate_median_seconds": candidate_time,
        "change_percent": round(change_percent, 2),
        "threshold_percent": threshold_percent,
        "status": "possible_regression" if is_regression else "within_threshold",
        "interpretation": (
            "Candidate took longer than the configured regression threshold."
            if is_regression
            else "Candidate did not exceed the configured slowdown threshold."
        ),
        "warning": (
            "A timing difference alone does not establish causation. "
            "Repeat measurements under comparable system conditions."
        ),
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, allow_nan=False)
        file.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run and compare lightweight WinPulse benchmarks."
    )
    parser.add_argument("--workload", choices=["cpu", "memory"], default="cpu")
    parser.add_argument("--iterations", type=int, default=500_000)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--size-mb", type=int, default=16)
    parser.add_argument(
        "--output",
        default="reports/benchmarks/candidate.json",
        help="Path for the new benchmark JSON report",
    )
    parser.add_argument(
        "--baseline",
        help="Optional baseline JSON file to compare against",
    )
    parser.add_argument(
        "--threshold-percent",
        type=float,
        default=REGRESSION_THRESHOLD_PERCENT,
    )
    args = parser.parse_args()

    try:
        result = run_benchmark(
            workload=args.workload,
            iterations=args.iterations,
            rounds=args.rounds,
            size_mb=args.size_mb,
        )

        output_path = Path(args.output)
        write_json(output_path, result)

        print(f"Benchmark saved: {output_path}")
        print(f"Workload: {result['workload']}")
        print(
            "Median wall time: "
            f"{result['results']['median_wall_seconds']:.6f} seconds"
        )
        print(
            "Median process CPU time: "
            f"{result['results']['median_process_cpu_seconds']:.6f} seconds"
        )
        print(
            "Deterministic checksum: "
            f"{result['results']['all_checksums_match']}"
        )

        if args.baseline:
            with Path(args.baseline).open("r", encoding="utf-8") as file:
                baseline = json.load(file)

            comparison = compare_benchmarks(
                baseline,
                result,
                threshold_percent=args.threshold_percent,
            )

            comparison_path = output_path.with_name(
                output_path.stem + "_comparison.json"
            )
            write_json(comparison_path, comparison)

            print(f"Comparison saved: {comparison_path}")
            print(f"Change: {comparison['change_percent']:+.2f}%")
            print(f"Status: {comparison['status']}")

    except (ValueError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
