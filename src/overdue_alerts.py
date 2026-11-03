"""Read-only date-based alerts for incomplete onboarding checklists."""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from src.progress_dashboard import build_progress_dashboard

PRIORITY_LEVELS = ("Critical", "High", "Medium", "Low")


def _matches_filter(value: str | None, selected: str | None) -> bool:
    """Match an optional exact program or location, ignoring case and spaces."""
    if selected is None or not selected.strip():
        return True
    return (value or "").strip().casefold() == selected.strip().casefold()


def _alert_priority(days_until_start: int) -> str:
    """Determine urgency from the employee start date."""
    if days_until_start <= -7:
        return "Critical"
    if days_until_start < 0:
        return "High"
    if days_until_start == 0:
        return "Medium"
    return "Low"


def build_overdue_alerts(
    records: list[dict[str, str]],
    progress_path: Path | None = None,
    today: date | None = None,
    upcoming_days: int = 7,
    program: str | None = None,
    location: str | None = None,
    priority: str | None = None,
) -> dict[str, Any]:
    """Build read-only alerts, sorted by urgency, with optional exact filters.

    Program/location filters are applied before checklist evaluation. Priority
    filtering is applied after classification. Counts reflect visible alerts.
    """
    if upcoming_days < 0:
        raise ValueError("upcoming_days must be nonnegative")
    selected_priority = (priority or "").strip().casefold()
    if selected_priority in ("", "all"):
        selected_priority = ""
    elif selected_priority not in {level.casefold() for level in PRIORITY_LEVELS}:
        raise ValueError("priority must be All, Critical, High, Medium, or Low")

    reference_date = today if today is not None else date.today()
    selected_records = [
        record for record in records
        if _matches_filter(record.get("program"), program)
        and _matches_filter(record.get("location"), location)
    ]
    dashboard = build_progress_dashboard(selected_records, progress_path=progress_path)
    alerts: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()

    for record, row in zip(selected_records, dashboard["rows"], strict=True):
        if (record.get("status") or "").strip().casefold() == "cancelled":
            continue
        if row["error"] is not None:
            errors.append({
                "employee": row["employee"],
                "onboarding_id": row["onboarding_id"],
                "error": str(row["error"]),
            })
            continue
        if row["total"] == 0 or row["completed"] == row["total"]:
            continue
        try:
            start_date = date.fromisoformat(record["start_date"])
        except (KeyError, TypeError, ValueError) as exc:
            errors.append({
                "employee": row["employee"],
                "onboarding_id": row["onboarding_id"],
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        days_until_start = (start_date - reference_date).days
        if days_until_start < 0:
            alert_type = "Overdue"
        elif days_until_start == 0:
            alert_type = "Due Today"
        elif days_until_start <= upcoming_days:
            alert_type = "Upcoming"
        else:
            continue
        alert_priority = _alert_priority(days_until_start)
        if selected_priority and alert_priority.casefold() != selected_priority:
            continue
        counts[alert_type] += 1
        priority_counts[alert_priority] += 1
        alerts.append({
            "employee": row["employee"],
            "onboarding_id": row["onboarding_id"],
            "shore_email": row["shore_email"],
            "status": row["status"],
            "program": record.get("program", ""),
            "location": record.get("location", ""),
            "start_date": start_date.isoformat(),
            "alert": alert_type,
            "priority": alert_priority,
            "days_overdue": max(-days_until_start, 0),
            "days_until_start": max(days_until_start, 0),
            "completed": row["completed"],
            "total": row["total"],
            "remaining": row["total"] - row["completed"],
            "percentage": row["percentage"],
        })

    order = {level: index for index, level in enumerate(PRIORITY_LEVELS)}
    alerts.sort(key=lambda item: (
        order[item["priority"]], item["start_date"], item["employee"], item["onboarding_id"]
    ))
    return {
        "as_of": reference_date.isoformat(),
        "upcoming_days": upcoming_days,
        "alerts": alerts,
        "counts": {name: counts[name] for name in ("Overdue", "Due Today", "Upcoming")},
        "priority_counts": {name: priority_counts[name] for name in PRIORITY_LEVELS},
        "errors": errors,
        "total_alerts": len(alerts),
    }
