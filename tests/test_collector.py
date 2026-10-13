
import csv

import pytest

from winpulse.collector import (
    PROCESS_FIELDS,
    SYSTEM_FIELDS,
    append_csv_rows,
    collect_process_metrics,
    collect_system_metrics,
    run_collector,
)


def test_system_metrics_have_expected_fields():
    metrics = collect_system_metrics()

    assert set(metrics) == set(SYSTEM_FIELDS)
    assert 0 <= metrics["cpu_percent"] <= 100
    assert metrics["memory_total_bytes"] > 0
    assert metrics["memory_available_bytes"] > 0
    assert metrics["memory_used_bytes"] > 0
    assert 0 <= metrics["memory_percent"] <= 100
    assert metrics["disk_total_bytes"] > 0
    assert 0 <= metrics["disk_usage_percent"] <= 100
    assert metrics["timestamp"]


def test_process_metrics_have_expected_fields():
    rows = collect_process_metrics({})

    assert isinstance(rows, list)

    for row in rows:
        assert set(row) == set(PROCESS_FIELDS)
        assert row["pid"] > 0
        assert isinstance(row["name"], str)
        assert row["cpu_percent"] >= 0
        assert row["memory_rss_bytes"] >= 0
        assert row["num_threads"] >= 0


def test_csv_writer_creates_header_and_rows(tmp_path):
    path = tmp_path / "metrics.csv"
    fields = ["timestamp", "cpu_percent"]

    rows = [
        {"timestamp": "t1", "cpu_percent": 10},
        {"timestamp": "t2", "cpu_percent": 20},
    ]

    append_csv_rows(path, fields, rows)

    with path.open(newline="", encoding="utf-8") as file:
        saved_rows = list(csv.DictReader(file))

    assert len(saved_rows) == 2
    assert saved_rows[0]["timestamp"] == "t1"
    assert float(saved_rows[1]["cpu_percent"]) == 20


def test_csv_writer_appends_without_duplicate_header(tmp_path):
    path = tmp_path / "metrics.csv"
    fields = ["timestamp", "cpu_percent"]

    append_csv_rows(
        path, fields, [{"timestamp": "t1", "cpu_percent": 10}]
    )
    append_csv_rows(
        path, fields, [{"timestamp": "t2", "cpu_percent": 20}]
    )

    with path.open(newline="", encoding="utf-8") as file:
        content = file.readlines()

    assert len(content) == 3
    normalized_content = [line.rstrip("\r\n") for line in content]
    assert normalized_content.count("timestamp,cpu_percent") == 1


def test_empty_batch_does_not_create_file(tmp_path):
    path = tmp_path / "empty.csv"

    append_csv_rows(path, ["timestamp"], [])

    assert not path.exists()


@pytest.mark.parametrize(
    ("duration", "interval"),
    [(0, 1), (-1, 1), (5, 0), (5, -1)],
)
def test_invalid_collection_parameters_are_rejected(
    tmp_path, duration, interval
):
    with pytest.raises(ValueError):
        run_collector(duration, interval, tmp_path)
