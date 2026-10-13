
from __future__ import annotations

import argparse
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


ALLOWED_MODES = {"cpu", "memory", "mixed"}
MAX_DURATION_SECONDS = 120
MAX_MEMORY_MB = 512
MEMORY_CHUNK_BYTES = 1024 * 1024


def utc_now() -> str:
    """Return the current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def validate_parameters(
    mode: str,
    duration: int,
    memory_mb: int,
) -> None:
    """Reject unsupported or excessive workload settings."""
    if mode not in ALLOWED_MODES:
        raise ValueError(
            f"Unsupported mode: {mode}. Choose cpu, memory, or mixed."
        )

    if not isinstance(duration, int) or isinstance(duration, bool):
        raise ValueError("Duration must be an integer.")

    if not 1 <= duration <= MAX_DURATION_SECONDS:
        raise ValueError(
            f"Duration must be between 1 and {MAX_DURATION_SECONDS} seconds."
        )

    if not isinstance(memory_mb, int) or isinstance(memory_mb, bool):
        raise ValueError("Memory allocation must be an integer.")

    if not 0 <= memory_mb <= MAX_MEMORY_MB:
        raise ValueError(
            f"Memory allocation must be between 0 and {MAX_MEMORY_MB} MB."
        )

    if mode in {"memory", "mixed"} and memory_mb < 1:
        raise ValueError(
            f"Mode '{mode}' requires at least 1 MB of memory."
        )


def cpu_worker(stop_event: threading.Event) -> None:
    """Run a simple CPU-bound loop until asked to stop."""
    value = 0

    while not stop_event.is_set():
        value = (value + 1) % 1_000_003


def allocate_memory(memory_mb: int) -> list[bytearray]:
    """Allocate and touch memory in small chunks."""
    blocks: list[bytearray] = []
    remaining = memory_mb * MEMORY_CHUNK_BYTES

    while remaining > 0:
        chunk_size = min(MEMORY_CHUNK_BYTES, remaining)
        block = bytearray(chunk_size)

        # Touch each page so the operating system has to back the allocation.
        page_size = 4096
        for offset in range(0, chunk_size, page_size):
            block[offset] = 1

        blocks.append(block)
        remaining -= chunk_size

    return blocks


def write_incident_record(
    output_dir: Path,
    record: dict[str, Any],
) -> Path:
    """Write a uniquely named JSON incident record."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = (
        f"incident_{record['started_at'][:19].replace(':', '-')}_"
        f"{record['incident_id'][:8]}.json"
    )
    output_path = output_dir / filename

    output_path.write_text(
        json.dumps(record, indent=2, allow_nan=False),
        encoding="utf-8",
    )

    return output_path


def run_simulation(
    mode: str,
    duration: int,
    memory_mb: int,
    output_dir: Path,
) -> dict[str, Any]:
    """Run a bounded workload and save its incident record."""
    validate_parameters(mode, duration, memory_mb)

    incident_id = str(uuid4())
    started_at = utc_now()
    start_monotonic = time.monotonic()

    stop_event = threading.Event()
    worker: threading.Thread | None = None
    memory_blocks: list[bytearray] = []

    record: dict[str, Any] = {
        "incident_id": incident_id,
        "mode": mode,
        "requested_duration_seconds": duration,
        "requested_memory_mb": (
            memory_mb if mode in {"memory", "mixed"} else 0
        ),
        "started_at": started_at,
        "ended_at": None,
        "actual_duration_seconds": None,
        "status": "running",
        "workload_description": {
            "cpu": (
                "One CPU-bound worker thread."
                if mode in {"cpu", "mixed"}
                else "No intentional CPU-bound worker."
            ),
            "memory": (
                "Touched memory blocks held during the run."
                if mode in {"memory", "mixed"}
                else "No intentional memory allocation."
            ),
        },
        "error": None,
    }

    print(f"Starting {mode} incident for {duration} seconds.")

    try:
        if mode in {"cpu", "mixed"}:
            worker = threading.Thread(
                target=cpu_worker,
                args=(stop_event,),
                name="WinPulseCPUWorker",
                daemon=True,
            )
            worker.start()

        if mode in {"memory", "mixed"}:
            memory_blocks = allocate_memory(memory_mb)

        deadline = start_monotonic + duration

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.2, remaining))

        record["status"] = "completed"

    except KeyboardInterrupt:
        record["status"] = "interrupted"

    except Exception as exc:
        record["status"] = "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"

    finally:
        stop_event.set()

        if worker is not None:
            worker.join(timeout=2)

        # Release the memory allocation promptly.
        memory_blocks.clear()

        record["ended_at"] = utc_now()
        record["actual_duration_seconds"] = round(
            time.monotonic() - start_monotonic, 3
        )

    record_path = write_incident_record(output_dir, record)

    print(f"Incident status: {record['status']}")
    print(f"Elapsed time: {record['actual_duration_seconds']} seconds")
    print(f"Incident record: {record_path.resolve()}")

    if record["error"]:
        print(f"Error: {record['error']}")

    return record


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a bounded WinPulse performance incident."
    )

    parser.add_argument(
        "--mode",
        choices=sorted(ALLOWED_MODES),
        default="cpu",
        help="Workload type: cpu, memory, or mixed.",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Run duration in seconds (1-120).",
    )
    parser.add_argument(
        "--memory-mb",
        type=int,
        default=64,
        help="Memory allocation in MB for memory/mixed modes (1-512).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports") / "incidents",
        help="Directory for incident JSON records.",
    )

    args = parser.parse_args()

    try:
        run_simulation(
            mode=args.mode,
            duration=args.duration,
            memory_mb=args.memory_mb,
            output_dir=args.output,
        )
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
