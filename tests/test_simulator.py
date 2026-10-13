
import json

import pytest

from winpulse.simulator import (
    run_simulation,
    validate_parameters,
)


@pytest.mark.parametrize(
    ("mode", "duration", "memory_mb"),
    [
        ("unknown", 10, 64),
        ("cpu", 0, 64),
        ("cpu", 121, 64),
        ("cpu", 10, -1),
        ("cpu", 10, 513),
        ("memory", 10, 0),
        ("mixed", 10, 0),
    ],
)
def test_invalid_parameters_are_rejected(mode, duration, memory_mb):
    with pytest.raises(ValueError):
        validate_parameters(mode, duration, memory_mb)


def test_valid_cpu_parameters():
    validate_parameters("cpu", 10, 0)


def test_valid_memory_parameters():
    validate_parameters("memory", 5, 16)


def test_cpu_simulation_writes_incident_record(tmp_path):
    record = run_simulation(
        mode="cpu",
        duration=1,
        memory_mb=0,
        output_dir=tmp_path,
    )

    assert record["status"] == "completed"
    assert record["mode"] == "cpu"
    assert record["ended_at"] is not None
    assert record["actual_duration_seconds"] >= 1

    files = list(tmp_path.glob("incident_*.json"))
    assert len(files) == 1

    saved = json.loads(files[0].read_text(encoding="utf-8"))
    assert saved["incident_id"] == record["incident_id"]


def test_memory_simulation_releases_workload_and_writes_record(tmp_path):
    record = run_simulation(
        mode="memory",
        duration=1,
        memory_mb=2,
        output_dir=tmp_path,
    )

    assert record["status"] == "completed"
    assert record["requested_memory_mb"] == 2
    assert len(list(tmp_path.glob("incident_*.json"))) == 1
