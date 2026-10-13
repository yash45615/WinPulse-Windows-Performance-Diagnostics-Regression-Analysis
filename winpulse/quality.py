
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


SYSTEM_NUMERIC_FIELDS = {
    "cpu_percent",
    "memory_total_bytes",
    "memory_available_bytes",
    "memory_used_bytes",
    "memory_percent",
    "disk_total_bytes",
    "disk_used_bytes",
    "disk_free_bytes",
    "disk_usage_percent",
}

PROCESS_NUMERIC_FIELDS = {
    "pid",
    "cpu_percent",
    "memory_rss_bytes",
    "memory_percent",
    "num_threads",
}

SYSTEM_REQUIRED_FIELDS = {
    "timestamp",
    *SYSTEM_NUMERIC_FIELDS,
}

PROCESS_REQUIRED_FIELDS = {
    "timestamp",
    "pid",
    "name",
    "cpu_percent",
    "memory_rss_bytes",
    "memory_percent",
    "num_threads",
    "status",
}


def parse_timestamp(value: Any) -> str:
    """Validate a timestamp and normalize it to UTC ISO-8601."""
    if value is None or not str(value).strip():
        raise ValueError("timestamp is missing")

    try:
        parsed = datetime.fromisoformat(
            str(value).strip().replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError("timestamp is not valid ISO-8601") from exc

    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")

    return parsed.astimezone(timezone.utc).isoformat()


def _number(row: dict[str, Any], field: str) -> float:
    value = row.get(field)

    if value is None or str(value).strip() == "":
        raise ValueError(f"{field} is missing")

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc

    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{field} must be finite")

    return number


def _integer(row: dict[str, Any], field: str) -> int:
    number = _number(row, field)

    if not number.is_integer():
        raise ValueError(f"{field} must be an integer")

    return int(number)


def validate_system_row(
    row: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return a normalized system row or its validation errors."""
    errors: list[str] = []

    missing = SYSTEM_REQUIRED_FIELDS - row.keys()
    if missing:
        errors.append(
            "missing fields: " + ", ".join(sorted(missing))
        )

    if errors:
        return None, errors

    try:
        normalized: dict[str, Any] = {
            "timestamp": parse_timestamp(row["timestamp"]),
        }

        for field in SYSTEM_NUMERIC_FIELDS:
            value = _number(row, field)

            if field.endswith("_bytes"):
                if not value.is_integer() or value < 0:
                    raise ValueError(
                        f"{field} must be a non-negative integer"
                    )
                normalized[field] = int(value)
            else:
                normalized[field] = value

        for field in (
            "cpu_percent",
            "memory_percent",
            "disk_usage_percent",
        ):
            if not 0 <= normalized[field] <= 100:
                raise ValueError(f"{field} must be between 0 and 100")

        if normalized["memory_total_bytes"] <= 0:
            raise ValueError("memory_total_bytes must be positive")

        if normalized["disk_total_bytes"] <= 0:
            raise ValueError("disk_total_bytes must be positive")

        if normalized["memory_available_bytes"] > normalized["memory_total_bytes"]:
            raise ValueError("available memory exceeds total memory")

        if normalized["memory_used_bytes"] > normalized["memory_total_bytes"]:
            raise ValueError("used memory exceeds total memory")

        if normalized["disk_used_bytes"] > normalized["disk_total_bytes"]:
            raise ValueError("used disk space exceeds total disk space")

        if normalized["disk_free_bytes"] > normalized["disk_total_bytes"]:
            raise ValueError("free disk space exceeds total disk space")

        return normalized, []

    except ValueError as exc:
        return None, [str(exc)]


def validate_process_row(
    row: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return a normalized process row or its validation errors."""
    missing = PROCESS_REQUIRED_FIELDS - row.keys()

    if missing:
        return None, [
            "missing fields: " + ", ".join(sorted(missing))
        ]

    try:
        timestamp = parse_timestamp(row["timestamp"])
        pid = _integer(row, "pid")
        cpu = _number(row, "cpu_percent")
        rss = _integer(row, "memory_rss_bytes")
        memory_percent = _number(row, "memory_percent")
        threads = _integer(row, "num_threads")
        name = str(row["name"]).strip()
        status = str(row["status"]).strip()

        if pid <= 0:
            raise ValueError("pid must be positive")

        if cpu < 0:
            raise ValueError("cpu_percent must be non-negative")

        if rss < 0:
            raise ValueError("memory_rss_bytes must be non-negative")

        if not 0 <= memory_percent <= 100:
            raise ValueError("memory_percent must be between 0 and 100")

        if threads < 0:
            raise ValueError("num_threads must be non-negative")

        if not name:
            raise ValueError("process name is missing")

        if not status:
            raise ValueError("process status is missing")

        return {
            "timestamp": timestamp,
            "pid": pid,
            "name": name,
            "cpu_percent": cpu,
            "memory_rss_bytes": rss,
            "memory_percent": memory_percent,
            "num_threads": threads,
            "status": status,
        }, []

    except ValueError as exc:
        return None, [str(exc)]
