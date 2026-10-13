
from pathlib import Path

from winpulse.release_report import (
    add_json_section,
    build_report,
    load_json,
    markdown_value,
)


def test_load_json_returns_none_for_missing_file(tmp_path: Path):
    assert load_json(tmp_path / "missing.json") is None


def test_load_json_reads_object(tmp_path: Path):
    path = tmp_path / "sample.json"
    path.write_text('{"sample_count": 4}', encoding="utf-8")

    assert load_json(path) == {"sample_count": 4}


def test_markdown_value_handles_nested_values():
    assert markdown_value(None) == "Not available"
    assert markdown_value(True) == "Yes"
    assert markdown_value({"count": 3}) == "count: 3"


def test_report_discloses_missing_artifacts(tmp_path: Path):
    analytics_path = tmp_path / "analytics.json"
    benchmark_path = tmp_path / "benchmark.json"
    power_path = tmp_path / "power.json"

    report = build_report(
        analytics=None,
        benchmark=None,
        power=None,
        analytics_path=analytics_path,
        benchmark_path=benchmark_path,
        power_path=power_path,
    )

    assert "# WinPulse Engineering Report" in report
    assert "No artifact found" in report
    assert "Evidence integrity" in report
    assert "does not claim" in report



def test_report_includes_available_metrics(tmp_path: Path):
    analytics_path = tmp_path / "analytics.json"
    benchmark_path = tmp_path / "benchmark.json"
    power_path = tmp_path / "power.json"

    report = build_report(
        analytics={"sample_count": 25},
        benchmark={"status": "within_threshold"},
        power={"sample_count": 12},
        analytics_path=analytics_path,
        benchmark_path=benchmark_path,
        power_path=power_path,
    )

    assert "**sample_count:** 25" in report
    assert "**status:** within_threshold" in report
    assert "**sample_count:** 12" in report
