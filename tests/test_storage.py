
from winpulse.storage import (
    connect_database,
    get_database_counts,
    initialize_database,
    insert_process_sample,
    insert_system_sample,
)


def make_system_row():
    return {
        "timestamp": "2026-10-13T10:00:00+00:00",
        "cpu_percent": 25.5,
        "memory_total_bytes": 8_000_000_000,
        "memory_available_bytes": 4_000_000_000,
        "memory_used_bytes": 4_000_000_000,
        "memory_percent": 50.0,
        "disk_total_bytes": 100_000_000_000,
        "disk_used_bytes": 40_000_000_000,
        "disk_free_bytes": 60_000_000_000,
        "disk_usage_percent": 40.0,
    }


def make_process_row():
    return {
        "timestamp": "2026-10-13T10:00:00+00:00",
        "pid": 1234,
        "name": "example.exe",
        "cpu_percent": 12.5,
        "memory_rss_bytes": 1_000_000,
        "memory_percent": 0.1,
        "num_threads": 8,
        "status": "running",
    }


def test_database_initializes_tables(tmp_path):
    db_path = tmp_path / "test.db"

    initialize_database(db_path)

    with connect_database(db_path) as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert "system_samples" in tables
    assert "process_samples" in tables


def test_system_sample_inserts_once(tmp_path):
    db_path = tmp_path / "test.db"
    initialize_database(db_path)

    with connect_database(db_path) as connection:
        assert insert_system_sample(connection, make_system_row())
        assert not insert_system_sample(connection, make_system_row())

    assert get_database_counts(db_path)["system_samples"] == 1


def test_process_sample_inserts_once_per_timestamp_and_pid(tmp_path):
    db_path = tmp_path / "test.db"
    initialize_database(db_path)

    with connect_database(db_path) as connection:
        row = make_process_row()

        assert insert_process_sample(connection, row)
        assert not insert_process_sample(connection, row)

        another_process = dict(row)
        another_process["pid"] = 5678
        another_process["name"] = "another.exe"

        assert insert_process_sample(connection, another_process)

    assert get_database_counts(db_path)["process_samples"] == 2
