"""Read-only date-based alerts for incomplete onboarding checklists."""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from src.progress_dashboard import build_progress_dashboard


def build_overdue_alerts(
    records: list[dict[str, str]],
    progress_path: Path | None = None,
    today: date | None = None,
    upcoming_days: int = 7,
) -> dict[str, Any]:
    """Classify incomplete checklists relative to the employee start date.

    This function does not modify history, checklist progress, or input records.
    Records and dashboard rows are paired by position, preserving distinct
    onboardings even if they share an email address or an invalid ID.
    """
    if upcoming_days < 0:
        raise ValueError("upcoming_days must be nonnegative")
    reference_date = today if today is not None else date.today()
    dashboard = build_progress_dashboard(records, progress_path=progress_path)
    alerts: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    counts: Counter[str] = Counter()

    for record, row in zip(records, dashboard["rows"], strict=True):
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
        counts[alert_type] += 1
        alerts.append({
            "employee": row["employee"],
            "onboarding_id": row["onboarding_id"],
            "shore_email": row["shore_email"],
            "status": row["status"],
            "start_date": start_date.isoformat(),
            "alert": alert_type,
            "days_overdue": max(-days_until_start, 0),
            "days_until_start": max(days_until_start, 0),
            "completed": row["completed"],
            "total": row["total"],
            "remaining": row["total"] - row["completed"],
            "percentage": row["percentage"],
        })

    priority = {"Overdue": 0, "Due Today": 1, "Upcoming": 2}
    alerts.sort(key=lambda item: (priority[item["alert"]], item["start_date"], item["employee"]))
    return {
        "as_of": reference_date.isoformat(),
        "upcoming_days": upcoming_days,
        "alerts": alerts,
        "counts": {name: counts[name] for name in ("Overdue", "Due Today", "Upcoming")},
        "errors": errors,
        "total_alerts": len(alerts),
    }
