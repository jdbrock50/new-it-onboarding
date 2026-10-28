"""Read-only onboarding progress dashboard reporting.

The dashboard reconstructs tasks from history and applies existing saved
completion states. It never writes to onboarding history or progress storage.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from src.employee import Employee
from src.onboarding import generate_onboarding_tasks
from src.task_progress import apply_task_progress, calculate_task_progress


def _employee_from_record(record: dict[str, str]) -> Employee:
    """Reconstruct an employee using the same history mapping as the console."""
    devices = [item.strip() for item in record.get("devices", "").split(",")]
    return Employee(
        first_name=record["first_name"],
        middle_name=record.get("middle_name", ""),
        last_name=record["last_name"],
        job_title=record["position"],
        program=record["program"],
        location=record["location"],
        supervisor=record["supervisor"],
        start_date=date.fromisoformat(record["start_date"]),
        personal_email=record["personal_email"],
        device_needs=[item for item in devices if item and item.lower() != "none"],
    )


def build_progress_dashboard(
    records: list[dict[str, str]],
    progress_path: Path | None = None,
) -> dict[str, Any]:
    """Return dashboard rows and aggregate counts without writing files.

    Invalid records appear as error rows rather than preventing other records
    from being reported. Completion and overall onboarding status are separate.
    """
    rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    completed_checklists = 0
    incomplete_checklists = 0
    errors = 0

    for record in records:
        status = record.get("status", "") or "Unknown"
        status_counts[status] += 1
        name = " ".join(
            part.strip()
            for part in (
                record.get("first_name", ""),
                record.get("middle_name", ""),
                record.get("last_name", ""),
            )
            if part and part.strip()
        ) or "Unknown employee"
        row: dict[str, Any] = {
            "employee": name,
            "onboarding_id": record.get("onboarding_id", "").strip(),
            "shore_email": record.get("shore_email", ""),
            "status": status,
            "completed": None,
            "total": None,
            "percentage": None,
            "error": None,
        }
        try:
            if not row["onboarding_id"]:
                raise ValueError("Missing onboarding ID")
            employee = _employee_from_record(record)
            tasks = generate_onboarding_tasks(
                employee, shore_email=record.get("shore_email") or None
            )
            apply_task_progress(row["onboarding_id"], tasks, path=progress_path)
            progress = calculate_task_progress(tasks)
            row.update(progress)
            if progress["total"] and progress["completed"] == progress["total"]:
                completed_checklists += 1
            else:
                incomplete_checklists += 1
        except (KeyError, ValueError, TypeError, OSError) as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            errors += 1
        rows.append(row)

    return {
        "rows": rows,
        "total_onboardings": len(records),
        "status_counts": dict(status_counts),
        "completed_checklists": completed_checklists,
        "incomplete_checklists": incomplete_checklists,
        "errors": errors,
    }
