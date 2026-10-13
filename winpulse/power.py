
from __future__ import annotations

import argparse
import ctypes
import json
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any



class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", ctypes.c_uint32),
        ("BatteryFullLifeTime", ctypes.c_uint32),
    ]



def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()




def decode_power_status(status: SYSTEM_POWER_STATUS) -> dict[str, Any]:
    ac_codes = {
        0: "battery",
        1: "ac",
        255: "unknown",
    }

    battery_flags = int(status.BatteryFlag)
    battery_percent = int(status.BatteryLifePercent)
    battery_life = int(status.BatteryLifeTime)
    full_life = int(status.BatteryFullLifeTime)

    # Check the special unknown value BEFORE checking individual bits.
    if battery_flags == 255:
        battery_state = "unknown"
    elif battery_flags & 128:
        battery_state = "no_battery"
    elif battery_flags & 8:
        battery_state = "charging"
    elif battery_flags & 4:
        battery_state = "critical"
    elif battery_flags & 2:
        battery_state = "low"
    elif battery_flags & 1:
        battery_state = "high"
    else:
        battery_state = "normal_or_unspecified"

    return {
        "ac_status": ac_codes.get(int(status.ACLineStatus), "unknown"),
        "battery_state": battery_state,
        "battery_percent": (
            battery_percent if battery_percent <= 100 else None
        ),
        "battery_life_seconds": (
            battery_life if battery_life != 0xFFFFFFFF else None
        ),
        "battery_full_life_seconds": (
            full_life if full_life != 0xFFFFFFFF else None
        ),
        "system_status_flag": int(status.SystemStatusFlag),
    }




def get_power_reading() -> dict[str, Any]:
    """Read current Windows power information."""
    if not hasattr(ctypes, "windll"):
        raise OSError("Windows power APIs are available only on Windows.")

    status = SYSTEM_POWER_STATUS()
    success = ctypes.windll.kernel32.GetSystemPowerStatus(
        ctypes.byref(status)
    )

    if not success:
        error_code = ctypes.get_last_error()
        raise OSError(
            error_code,
            "GetSystemPowerStatus failed",
        )

    return {
        "timestamp": utc_now(),
        **decode_power_status(status),
    }


def collect_power_samples(
    duration_seconds: int,
    interval_seconds: float,
    output_path: Path,
) -> int:
    if not isinstance(duration_seconds, int) or isinstance(
        duration_seconds, bool
    ):
        raise ValueError("duration_seconds must be an integer")
    if not 1 <= duration_seconds <= 3600:
        raise ValueError("duration_seconds must be between 1 and 3600")
    if not isinstance(interval_seconds, (int, float)) or isinstance(
        interval_seconds, bool
    ):
        raise ValueError("interval_seconds must be a number")
    if not 0.2 <= interval_seconds <= 60:
        raise ValueError("interval_seconds must be between 0.2 and 60")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    deadline = started + duration_seconds
    count = 0

    with output_path.open("a", encoding="utf-8") as output:
        while True:
            record = get_power_reading()
            output.write(json.dumps(record, allow_nan=False) + "\n")
            output.flush()
            count += 1

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            time.sleep(min(interval_seconds, remaining))

    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect Windows battery and power-status samples."
    )
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument(
        "--output",
        default="data/power_samples.jsonl",
    )
    args = parser.parse_args()

    try:
        count = collect_power_samples(
            args.duration,
            args.interval,
            Path(args.output),
        )
        print(f"Power samples collected: {count}")
        print(f"Output file: {Path(args.output)}")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
