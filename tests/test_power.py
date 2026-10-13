
import json

import pytest

from winpulse.power import (
    SYSTEM_POWER_STATUS,
    decode_power_status,
    collect_power_samples,
)
from winpulse.power_analysis import analyze_power_file


def make_status(
    ac=1,
    flags=1,
    percent=80,
    battery_life=3600,
    full_life=7200,
):
    status = SYSTEM_POWER_STATUS()
    status.ACLineStatus = ac
    status.BatteryFlag = flags
    status.BatteryLifePercent = percent
    status.SystemStatusFlag = 0
    status.BatteryLifeTime = battery_life
    status.BatteryFullLifeTime = full_life
    return status


def test_decodes_ac_and_battery_percentage():
    result = decode_power_status(make_status(ac=1, percent=80))

    assert result["ac_status"] == "ac"
    assert result["battery_percent"] == 80
    assert result["battery_state"] == "high"


def test_unknown_battery_values_are_none():
    result = decode_power_status(
        make_status(
            ac=255,
            flags=255,
            percent=255,
            battery_life=0xFFFFFFFF,
            full_life=0xFFFFFFFF,
        )
    )

    assert result["ac_status"] == "unknown"
    assert result["battery_state"] == "unknown"
    assert result["battery_percent"] is None
    assert result["battery_life_seconds"] is None
    assert result["battery_full_life_seconds"] is None


def test_detects_charging_state():
    result = decode_power_status(make_status(ac=1, flags=8))
    assert result["battery_state"] == "charging"


def test_rejects_invalid_duration(tmp_path):
    with pytest.raises(ValueError):
        collect_power_samples(0, 1, tmp_path / "power.jsonl")


def test_power_analysis_reports_percentage_change(tmp_path):
    sample_file = tmp_path / "power.jsonl"
    sample_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {"timestamp": "t1", "battery_percent": 80,
                     "ac_status": "battery", "battery_state": "normal"}
                ),
                json.dumps(
                    {"timestamp": "t2", "battery_percent": 77,
                     "ac_status": "battery", "battery_state": "low"}
                ),
            ]
        ) + "\n",
        encoding="utf-8",
    )

    report = analyze_power_file(sample_file)

    assert report["sample_count"] == 2
    assert report["battery_percentage_point_change"] == -3.0
    assert report["ac_status_counts"]["battery"] == 2


def test_power_analysis_handles_unknown_battery_percentage(tmp_path):
    sample_file = tmp_path / "unknown.jsonl"
    sample_file.write_text(
        json.dumps(
            {"timestamp": "t1", "battery_percent": None,
             "ac_status": "unknown", "battery_state": "unknown"}
        ) + "\n",
        encoding="utf-8",
    )

    report = analyze_power_file(sample_file)

    assert report["known_battery_percentage_samples"] == 0
    assert report["battery_percentage_point_change"] is None
