
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS system_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL UNIQUE,
    cpu_percent REAL NOT NULL,
    memory_total_bytes INTEGER NOT NULL,
    memory_available_bytes INTEGER NOT NULL,
    memory_used_bytes INTEGER NOT NULL,
    memory_percent REAL NOT NULL,
    disk_total_bytes INTEGER NOT NULL,
    disk_used_bytes INTEGER NOT NULL,
    disk_free_bytes INTEGER NOT NULL,
    disk_usage_percent REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS process_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    pid INTEGER NOT NULL,
    name TEXT NOT NULL,
    cpu_percent REAL NOT NULL,
    memory_rss_bytes INTEGER NOT NULL,
    memory_percent REAL NOT NULL,
    num_threads INTEGER NOT NULL,
    status TEXT NOT NULL,
    UNIQUE(timestamp, pid)
);

CREATE INDEX IF NOT EXISTS idx_system_timestamp
    ON system_samples(timestamp);

CREATE INDEX IF NOT EXISTS idx_process_timestamp
    ON process_samples(timestamp);

CREATE INDEX IF NOT EXISTS idx_process_pid_timestamp
    ON process_samples(pid, timestamp);
"""


@contextmanager
def connect_database(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection and always close it."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(db_path: Path) -> None:
    """Create database tables and indexes if they do not exist."""
    with connect_database(db_path) as connection:
        connection.executescript(SCHEMA)


def insert_system_sample(
    connection: sqlite3.Connection,
    row: dict[str, Any],
) -> bool:
    """
    Insert one system telemetry sample.

    Returns True if inserted, or False if its timestamp already exists.
    """
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO system_samples (
            timestamp,
            cpu_percent,
            memory_total_bytes,
            memory_available_bytes,
            memory_used_bytes,
            memory_percent,
            disk_total_bytes,
            disk_used_bytes,
            disk_free_bytes,
            disk_usage_percent
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["timestamp"],
            row["cpu_percent"],
            row["memory_total_bytes"],
            row["memory_available_bytes"],
            row["memory_used_bytes"],
            row["memory_percent"],
            row["disk_total_bytes"],
            row["disk_used_bytes"],
            row["disk_free_bytes"],
            row["disk_usage_percent"],
        ),
    )

    return cursor.rowcount == 1


def insert_process_sample(
    connection: sqlite3.Connection,
    row: dict[str, Any],
) -> bool:
    """
    Insert one process telemetry sample.

    Returns True if inserted, or False if the timestamp/PID pair
    already exists.
    """
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO process_samples (
            timestamp,
            pid,
            name,
            cpu_percent,
            memory_rss_bytes,
            memory_percent,
            num_threads,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["timestamp"],
            row["pid"],
            row["name"],
            row["cpu_percent"],
            row["memory_rss_bytes"],
            row["memory_percent"],
            row["num_threads"],
            row["status"],
        ),
    )

    return cursor.rowcount == 1


def get_database_counts(db_path: Path) -> dict[str, int]:
    """Return the number of stored system and process samples."""
    initialize_database(db_path)

    with connect_database(db_path) as connection:
        system_count = connection.execute(
            "SELECT COUNT(*) FROM system_samples"
        ).fetchone()[0]

        process_count = connection.execute(
            "SELECT COUNT(*) FROM process_samples"
        ).fetchone()[0]

    return {
        "system_samples": system_count,
        "process_samples": process_count,
    }
