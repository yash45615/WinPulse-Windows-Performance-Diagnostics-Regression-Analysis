
import pytest

from winpulse.benchmark import (
    compare_benchmarks,
    run_benchmark,
    validate_parameters,
)


def test_cpu_benchmark_returns_repeatable_checksums():
    result = run_benchmark(
        workload="cpu",
        iterations=1000,
        rounds=2,
        size_mb=1,
    )

    assert result["workload"] == "cpu"
    assert len(result["results"]["checksums"]) == 2
    assert result["results"]["all_checksums_match"] is True
    assert result["results"]["median_wall_seconds"] > 0


def test_memory_benchmark_runs():
    result = run_benchmark(
        workload="memory",
        iterations=100,
        rounds=2,
        size_mb=1,
    )

    assert result["workload"] == "memory"
    assert result["parameters"]["size_mb"] == 1
    assert result["results"]["all_checksums_match"] is True


@pytest.mark.parametrize(
    ("workload", "iterations", "rounds", "size_mb"),
    [
        ("unknown", 100, 1, 1),
        ("cpu", 0, 1, 1),
        ("cpu", 100, 0, 1),
        ("cpu", 100, 11, 1),
        ("memory", 100, 1, 129),
    ],
)
def test_invalid_parameters_are_rejected(
    workload, iterations, rounds, size_mb
):
    with pytest.raises(ValueError):
        validate_parameters(workload, iterations, rounds, size_mb)


def test_slow_candidate_is_flagged():
    baseline = {
        "workload": "cpu",
        "parameters": {"iterations": 1000, "size_mb": None, "rounds": 3},
        "results": {"median_wall_seconds": 1.0},
    }
    candidate = {
        "workload": "cpu",
        "parameters": {"iterations": 1000, "size_mb": None, "rounds": 3},
        "results": {"median_wall_seconds": 1.15},
    }

    result = compare_benchmarks(baseline, candidate)

    assert result["status"] == "possible_regression"
    assert result["change_percent"] == 15.0


def test_small_slowdown_stays_within_threshold():
    baseline = {
        "workload": "cpu",
        "parameters": {"iterations": 1000, "size_mb": None, "rounds": 3},
        "results": {"median_wall_seconds": 1.0},
    }
    candidate = {
        "workload": "cpu",
        "parameters": {"iterations": 1000, "size_mb": None, "rounds": 3},
        "results": {"median_wall_seconds": 1.05},
    }

    result = compare_benchmarks(baseline, candidate)

    assert result["status"] == "within_threshold"


def test_comparison_rejects_different_parameters():
    baseline = {
        "workload": "cpu",
        "parameters": {"iterations": 1000, "size_mb": None, "rounds": 3},
        "results": {"median_wall_seconds": 1.0},
    }
    candidate = {
        "workload": "cpu",
        "parameters": {"iterations": 2000, "size_mb": None, "rounds": 3},
        "results": {"median_wall_seconds": 1.2},
    }

    with pytest.raises(ValueError, match="parameters must match"):
        compare_benchmarks(baseline, candidate)
