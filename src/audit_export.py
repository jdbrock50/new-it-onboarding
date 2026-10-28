"""CSV exports for Shore IT Onboarding audit reports.

Exports are read-only with respect to the supplied audit events. The caller
chooses the output path and is responsible for selecting any filters first.
"""

import csv
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

EVENT_COLUMNS = ("timestamp", "event_type", "employee_email", "details")
SUMMARY_COLUMNS = ("metric", "category", "value")


def export_audit_events_csv(
    events: Sequence[Mapping[str, Any]], output_path: str | Path
) -> Path:
    """Export audit events to CSV, preserving input order and nested details.

    ``details`` is serialized as JSON so it remains readable and reversible.
    Pass an already-filtered collection to export only matching events.
    """
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EVENT_COLUMNS)
        writer.writeheader()
        for event in events:
            details = event.get("details", {})
            writer.writerow(
                {
                    "timestamp": event.get("timestamp", ""),
                    "event_type": event.get("event_type", ""),
                    "employee_email": event.get("employee_email", ""),
                    "details": json.dumps(details, ensure_ascii=False, sort_keys=True),
                }
            )
    return destination


def export_audit_summary_csv(
    summary: Mapping[str, Any], output_path: str | Path
) -> Path:
    """Export a summary dictionary to a tidy metric/category/value CSV.

    Nested count dictionaries (such as events_by_type) become one row per
    category; scalar summary values use a blank category.
    """
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        for metric, value in summary.items():
            if isinstance(value, Mapping):
                for category, count in value.items():
                    writer.writerow(
                        {"metric": metric, "category": category, "value": count}
                    )
            else:
                writer.writerow({"metric": metric, "category": "", "value": value})
    return destination
