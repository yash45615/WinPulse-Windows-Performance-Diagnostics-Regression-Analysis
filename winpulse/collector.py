
from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import psutil


SYSTEM_FIELDS = [
    "timestamp",
    "cpu_percent",
    "memory_total_bytes",
    "memory_available_bytes",
    "memory_used_bytes",
    "memory_percent",
    "disk_total_bytes",
    "disk_used_bytes",
    "disk_free_bytes",
    "disk_usage_percent",
]

PROCESS_FIELDS = [
    "timestamp",
    "pid",
    "name",
    "cpu_percent",
    "memory_rss_bytes",
    "memory_percent",
    "num_threads",
    "status",
]


def utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def collect_system_metrics() -> dict[str, Any]:
    """Collect a snapshot of system-wide resource usage."""
    memory = psutil.virtual_memory()

    # Measure the drive containing the project.
    drive_root = Path.cwd().anchor or str(Path.cwd())
    disk = psutil.disk_usage(drive_root)

    return {
        "timestamp": utc_timestamp(),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_total_bytes": memory.total,
        "memory_available_bytes": memory.available,
        "memory_used_bytes": memory.used,
        "memory_percent": memory.percent,
        "disk_total_bytes": disk.total,
        "disk_used_bytes": disk.used,
        "disk_free_bytes": disk.free,
        "disk_usage_percent": disk.percent,
    }


def collect_process_metrics(
    process_cache: dict[int, psutil.Process],
) -> list[dict[str, Any]]:
    """Collect accessible process metrics without waiting per process."""
    rows: list[dict[str, Any]] = []
    timestamp = utc_timestamp()
    active_pids: set[int] = set()

    for item in psutil.process_iter(["pid"]):
        pid = item.info["pid"]

        if pid is None or pid <= 0:
            continue

        active_pids.add(pid)

        try:
            process = process_cache.get(pid)

            if process is None:
                process = psutil.Process(pid)
                process_cache[pid] = process

            with process.oneshot():
                rows.append(
                    {
                        "timestamp": timestamp,
                        "pid": pid,
                        "name": process.name(),
                        "cpu_percent": process.cpu_percent(
                            interval=None
                        ),
                        "memory_rss_bytes": process.memory_info().rss,
                        "memory_percent": process.memory_percent(),
                        "num_threads": process.num_threads(),
                        "status": process.status(),
                    }
                )

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue

    # Remove exited processes from the cache.
    for pid in process_cache.keys() - active_pids:
        del process_cache[pid]

    return rows


def append_csv_rows(
    path: Path,
    fields: list[str],
    rows: Iterable[dict[str, Any]],
) -> None:
    """Append a batch of rows, writing the header only once."""
    batch = list(rows)

    if not batch:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not path.exists() or path.stat().st_size == 0

    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="raise",
        )

        if needs_header:
            writer.writeheader()

        writer.writerows(batch)


def run_collector(
    duration: int,
    interval: int,
    output_dir: Path,
) -> None:
    """Collect metrics for a bounded period."""
    if duration < 1:
        raise ValueError("Duration must be at least 1 second.")

    if interval < 1:
        raise ValueError("Interval must be at least 1 second.")

    output_dir.mkdir(parents=True, exist_ok=True)

    session = datetime.now().strftime("%Y%m%d_%H%M%S")
    system_file = output_dir / f"system_{session}.csv"
    process_file = output_dir / f"processes_{session}.csv"

    process_cache: dict[int, psutil.Process] = {}

    # Prime CPU counters. The first reading is not a useful interval.
    psutil.cpu_percent(interval=None)

    try:
        for item in psutil.process_iter(["pid"]):
            pid = item.info["pid"]
            if pid is not None:
                try:
                    process_cache[pid] = psutil.Process(pid)
                    process_cache[pid].cpu_percent(interval=None)
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue

        deadline = time.monotonic() + duration
        samples = 0

        print(f"WinPulse collection started: {duration}s")
        print(f"Sampling interval: {interval}s")
        print(f"Output directory: {output_dir.resolve()}")

        next_sample = time.monotonic() + interval

        while next_sample < deadline:
            time.sleep(max(0.0, next_sample - time.monotonic()))

            system_row = collect_system_metrics()
            process_rows = collect_process_metrics(process_cache)

            append_csv_rows(system_file, SYSTEM_FIELDS, [system_row])
            append_csv_rows(process_file, PROCESS_FIELDS, process_rows)

            samples += 1
            print(
                f"Sample {samples}: "
                f"CPU {system_row['cpu_percent']:.1f}% | "
                f"RAM {system_row['memory_percent']:.1f}% | "
                f"Processes {len(process_rows)}"
            )

            next_sample += interval

        print("Collection complete.")
        print(f"System metrics: {system_file}")
        print(f"Process metrics: {process_file}")
        print(f"System samples collected: {samples}")

    except KeyboardInterrupt:
        print("\nCollection interrupted by user.")
        print("Any completed samples remain saved in the CSV files.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lightweight Windows performance telemetry collector."
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Collection duration in seconds (default: 30).",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Seconds between samples (default: 2).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data"),
        help="Directory for generated CSV files (default: data).",
    )

    args = parser.parse_args()

    try:
        run_collector(
            duration=args.duration,
            interval=args.interval,
            output_dir=args.output,
        )
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
