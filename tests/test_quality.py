
from winpulse.quality import (
    parse_timestamp,
    validate_process_row,
    validate_system_row,
)


def valid_system_row():
    return {
        "timestamp": "2026-10-13T10:00:00+00:00",
        "cpu_percent": "25.5",
        "memory_total_bytes": "8000000000",
        "memory_available_bytes": "4000000000",
        "memory_used_bytes": "4000000000",
        "memory_percent": "50.0",
        "disk_total_bytes": "100000000000",
        "disk_used_bytes": "40000000000",
        "disk_free_bytes": "60000000000",
        "disk_usage_percent": "40.0",
    }


def valid_process_row():
    return {
        "timestamp": "2026-10-13T10:00:00+00:00",
        "pid": "1234",
        "name": "example.exe",
        "cpu_percent": "12.5",
        "memory_rss_bytes": "1000000",
        "memory_percent": "0.1",
        "num_threads": "8",
        "status": "running",
    }


def test_timestamp_is_normalized_to_utc():
    result = parse_timestamp("2026-10-13T12:00:00+02:00")

    assert result == "2026-10-13T10:00:00+00:00"


def test_timestamp_without_timezone_is_rejected():
    try:
        parse_timestamp("2026-10-13T10:00:00")
        assert False, "Expected timestamp validation to fail"
    except ValueError as exc:
        assert "timezone" in str(exc)


def test_valid_system_row_is_accepted():
    clean, errors = validate_system_row(valid_system_row())

    assert errors == []
    assert clean is not None
    assert clean["cpu_percent"] == 25.5
    assert clean["memory_total_bytes"] == 8_000_000_000


def test_system_cpu_out_of_range_is_rejected():
    row = valid_system_row()
    row["cpu_percent"] = "150"

    clean, errors = validate_system_row(row)

    assert clean is None
    assert any("cpu_percent" in error for error in errors)


def test_missing_system_field_is_rejected():
    row = valid_system_row()
    del row["memory_percent"]

    clean, errors = validate_system_row(row)

    assert clean is None
    assert any("memory_percent" in error for error in errors)


def test_valid_process_row_is_accepted():
    clean, errors = validate_process_row(valid_process_row())

    assert errors == []
    assert clean is not None
    assert clean["pid"] == 1234


def test_pid_zero_is_rejected():
    row = valid_process_row()
    row["pid"] = "0"

    clean, errors = validate_process_row(row)

    assert clean is None
    assert any("pid must be positive" in error for error in errors)


def test_process_cpu_can_exceed_100_percent():
    row = valid_process_row()
    row["cpu_percent"] = "175"

    clean, errors = validate_process_row(row)

    assert errors == []
    assert clean is not None
    assert clean["cpu_percent"] == 175


def test_invalid_process_memory_is_rejected():
    row = valid_process_row()
    row["memory_rss_bytes"] = "-10"

    clean, errors = validate_process_row(row)

    assert clean is None
    assert any("memory_rss_bytes" in error for error in errors)
