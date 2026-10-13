
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from winpulse.quality import (
    validate_process_row,
    validate_system_row,
)
from winpulse.storage import (
    connect_database,
    initialize_database,
    insert_process_sample,
    insert_system_sample,
)


def read_csv(path: Path) -> list[dict[str, Any]]:
    """Read a CSV file using its header as field names."""
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def ingest_directory(
    data_dir: Path,
    db_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    """Validate and import all collector CSV files in a directory."""
    data_dir = Path(data_dir)
    db_path = Path(db_path)
    report_path = Path(report_path)

    if not data_dir.is_dir():
        raise FileNotFoundError(
            f"Telemetry directory does not exist: {data_dir}"
        )

    system_files = sorted(data_dir.glob("system_*.csv"))
    process_files = sorted(data_dir.glob("processes_*.csv"))

    initialize_database(db_path)

    summary: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_directory": str(data_dir.resolve()),
        "database": str(db_path.resolve()),
        "files_found": len(system_files) + len(process_files),
        "system": {
            "rows_read": 0,
            "inserted": 0,
            "duplicates": 0,
            "rejected": 0,
        },
        "process": {
            "rows_read": 0,
            "inserted": 0,
            "duplicates": 0,
            "rejected": 0,
        },
        "errors": [],
    }

    with connect_database(db_path) as connection:
        for file_path in system_files:
            try:
                rows = read_csv(file_path)
            except (OSError, UnicodeError, csv.Error) as exc:
                summary["errors"].append({
                    "file": str(file_path),
                    "row": None,
                    "errors": [f"could not read CSV: {exc}"],
                })
                continue

            for row_number, raw_row in enumerate(rows, start=2):
                stats = summary["system"]
                stats["rows_read"] += 1

                clean_row, errors = validate_system_row(raw_row)

                if errors:
                    stats["rejected"] += 1
                    summary["errors"].append({
                        "file": file_path.name,
                        "row": row_number,
                        "type": "system",
                        "errors": errors,
                    })
                    continue

                assert clean_row is not None
                if insert_system_sample(connection, clean_row):
                    stats["inserted"] += 1
                else:
                    stats["duplicates"] += 1

        for file_path in process_files:
            try:
                rows = read_csv(file_path)
            except (OSError, UnicodeError, csv.Error) as exc:
                summary["errors"].append({
                    "file": str(file_path),
                    "row": None,
                    "errors": [f"could not read CSV: {exc}"],
                })
                continue

            for row_number, raw_row in enumerate(rows, start=2):
                stats = summary["process"]
                stats["rows_read"] += 1

                clean_row, errors = validate_process_row(raw_row)

                if errors:
                    stats["rejected"] += 1
                    summary["errors"].append({
                        "file": file_path.name,
                        "row": row_number,
                        "type": "process",
                        "errors": errors,
                    })
                    continue

                assert clean_row is not None
                if insert_process_sample(connection, clean_row):
                    stats["inserted"] += 1
                else:
                    stats["duplicates"] += 1

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and import WinPulse telemetry into SQLite."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data"),
        help="Directory containing collector CSV files.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data") / "winpulse.db",
        help="SQLite database path.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports") / "ingestion_report.json",
        help="JSON data-quality report path.",
    )

    args = parser.parse_args()

    try:
        summary = ingest_directory(
            args.data,
            args.db,
            args.report,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    print("\nWinPulse ingestion complete")
    print("=" * 32)

    for category in ("system", "process"):
        stats = summary[category]
        print(f"\n{category.title()} telemetry")
        print(f"  Rows read:  {stats['rows_read']}")
        print(f"  Inserted:   {stats['inserted']}")
        print(f"  Duplicates: {stats['duplicates']}")
        print(f"  Rejected:   {stats['rejected']}")

    print(f"\nFiles found: {summary['files_found']}")
    print(f"Data-quality issues: {len(summary['errors'])}")
    print(f"Database: {args.db.resolve()}")
    print(f"Report: {args.report.resolve()}")


if __name__ == "__main__":
    main()
