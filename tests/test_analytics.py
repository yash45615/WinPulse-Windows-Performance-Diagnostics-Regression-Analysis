
from winpulse.analytics import (
    build_report,
    describe_values,
    detect_anomalies,
    rank_processes,
)


def system_row(timestamp, cpu, memory=50.0, disk=40.0):
    return {
        "timestamp": timestamp,
        "cpu_percent": cpu,
        "memory_total_bytes": 8_000_000_000,
        "memory_available_bytes": 4_000_000_000,
        "memory_used_bytes": 4_000_000_000,
        "memory_percent": memory,
        "disk_total_bytes": 100_000_000_000,
        "disk_used_bytes": 40_000_000_000,
        "disk_free_bytes": 60_000_000_000,
        "disk_usage_percent": disk,
    }


def process_row(timestamp, pid, name, cpu, rss):
    return {
        "timestamp": timestamp,
        "pid": pid,
        "name": name,
        "cpu_percent": cpu,
        "memory_rss_bytes": rss,
        "memory_percent": 5.0,
        "num_threads": 8,
        "status": "running",
    }


def test_describe_values_calculates_statistics():
    result = describe_values([10.0, 20.0, 30.0])

    assert result["count"] == 3
    assert result["average"] == 20.0
    assert result["minimum"] == 10.0
    assert result["maximum"] == 30.0
    assert result["standard_deviation"] > 0


def test_describe_values_handles_empty_input():
    result = describe_values([])

    assert result["count"] == 0
    assert result["average"] is None
    assert result["maximum"] is None


def test_high_cpu_is_flagged():
    rows = [
        system_row("2026-10-13T10:00:00+00:00", 20),
        system_row("2026-10-13T10:00:02+00:00", 25),
        system_row("2026-10-13T10:00:04+00:00", 95),
    ]

    findings = detect_anomalies(rows)

    assert any(
        item["metric"] == "cpu_percent"
        and item["observed_value"] == 95
        for item in findings
    )


def test_normal_system_usage_does_not_trigger_static_thresholds():
    rows = [
        system_row("2026-10-13T10:00:00+00:00", 20, 40, 30),
        system_row("2026-10-13T10:00:02+00:00", 25, 42, 35),
        system_row("2026-10-13T10:00:04+00:00", 30, 45, 40),
    ]

    findings = detect_anomalies(rows)

    assert findings == []


def test_process_rankings_sort_by_average_cpu_and_memory():
    rows = [
        process_row("t1", 100, "app-a.exe", 10, 1_000),
        process_row("t2", 100, "app-a.exe", 30, 2_000),
        process_row("t1", 200, "app-b.exe", 70, 500),
    ]

    result = rank_processes(rows)

    assert result["highest_average_cpu"][0]["name"] == "app-b.exe"
    assert result["highest_average_cpu"][1]["average_cpu_percent"] == 20
    assert result["highest_peak_memory"][0]["name"] == "app-a.exe"
    assert result["highest_peak_memory"][0]["peak_memory_rss_bytes"] == 2_000


def test_process_ranking_rejects_invalid_limit():
    try:
        rank_processes([], limit=0)
        assert False, "Expected invalid limit to fail"
    except ValueError as exc:
        assert "at least 1" in str(exc)


def test_build_report_handles_empty_samples():
    report = build_report([], [])

    assert report["sample_counts"]["system_samples"] == 0
    assert report["sample_counts"]["process_samples"] == 0
    assert report["anomaly_count"] == 0
    assert report["anomalies"] == []


def test_build_report_contains_statistics_and_rankings():
    systems = [
        system_row("2026-10-13T10:00:00+00:00", 20),
        system_row("2026-10-13T10:00:02+00:00", 30),
    ]
    processes = [
        process_row("2026-10-13T10:00:00+00:00", 100, "app.exe", 10, 1000)
    ]

    report = build_report(systems, processes)

    assert report["sample_counts"]["system_samples"] == 2
    assert report["system_metrics"]["cpu_percent"]["average"] == 25
    assert report["process_rankings"]["highest_average_cpu"][0]["name"] == "app.exe"
    assert "generated_at" in report
