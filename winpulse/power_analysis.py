
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def analyze_power_file(input_path: Path) -> dict[str, Any]:
    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(f"Power sample file not found: {input_path}")

    records = []
    with input_path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number}"
                ) from exc

            if not isinstance(record, dict):
                raise ValueError(
                    f"Expected a JSON object on line {line_number}"
                )

            records.append(record)

    if not records:
        raise ValueError("Power sample file contains no records")

    known_percentages = []
    for record in records:
        percent = record.get("battery_percent")
        if percent is None:
            continue

        if (
            isinstance(percent, bool)
            or not isinstance(percent, (int, float))
            or not 0 <= percent <= 100
        ):
            raise ValueError("Battery percentages must be between 0 and 100")

        known_percentages.append(float(percent))

    ac_counts: dict[str, int] = {}
    state_counts: dict[str, int] = {}

    for record in records:
        ac = str(record.get("ac_status", "unknown"))
        state = str(record.get("battery_state", "unknown"))
        ac_counts[ac] = ac_counts.get(ac, 0) + 1
        state_counts[state] = state_counts.get(state, 0) + 1

    if known_percentages:
        battery_change = round(
            known_percentages[-1] - known_percentages[0], 2
        )
        first_percent = known_percentages[0]
        last_percent = known_percentages[-1]
    else:
        battery_change = None
        first_percent = None
        last_percent = None

    return {
        "schema_version": 1,
        "source_file": str(input_path),
        "sample_count": len(records),
        "known_battery_percentage_samples": len(known_percentages),
        "first_known_battery_percent": first_percent,
        "last_known_battery_percent": last_percent,
        "battery_percentage_point_change": battery_change,
        "ac_status_counts": ac_counts,
        "battery_state_counts": state_counts,
        "limitations": [
            "Battery percentage is a coarse, rounded indicator.",
            "A short capture may show no battery percentage change.",
            "Battery percentage change is not a measurement of watts or watt-hours.",
            "Battery status and runtime estimates depend on hardware and Windows.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize WinPulse power-status samples."
    )
    parser.add_argument(
        "--input",
        default="data/power_samples.jsonl",
    )
    parser.add_argument(
        "--output",
        default="reports/power_analysis.json",
    )
    args = parser.parse_args()

    try:
        report = analyze_power_file(Path(args.input))
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        print(f"Power analysis saved: {output_path}")
        print(f"Samples: {report['sample_count']}")
        print(
            "Battery percentage-point change: "
            f"{report['battery_percentage_point_change']}"
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
