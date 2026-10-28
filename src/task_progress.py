"""Persistent completion tracking for Shore IT onboarding tasks.

Progress is keyed by permanent onboarding ID and deterministic task ID.
The storage file is local and should remain excluded from version control.
"""

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.onboarding import OnboardingTask

PROGRESS_FILE = Path("data/task_progress.json")


def task_id(task: OnboardingTask) -> str:
    """Return a deterministic ID for a category/description pair."""
    key = json.dumps([task.category, task.description], ensure_ascii=False)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def load_task_progress(path: Path | None = None) -> dict[str, Any]:
    """Read progress without creating or changing the storage file."""
    target = path if path is not None else PROGRESS_FILE
    if not target.exists():
        return {}
    with target.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Task progress file must contain a JSON object.")
    return data


def save_task_progress(data: dict[str, Any], path: Path | None = None) -> Path:
    """Atomically replace the progress file with validated JSON data."""
    target = path if path is not None else PROGRESS_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent,
            prefix=f".{target.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(data, handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
        os.replace(temporary_path, target)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return target


def set_task_completed(
    onboarding_id: str,
    task: OnboardingTask,
    completed: bool,
    path: Path | None = None,
) -> None:
    """Persist one task's completion state for one onboarding."""
    if not onboarding_id.strip():
        raise ValueError("onboarding_id is required")
    if not isinstance(completed, bool):
        raise TypeError("completed must be a boolean")
    data = load_task_progress(path)
    onboarding = data.setdefault(onboarding_id, {})
    if not isinstance(onboarding, dict):
        raise ValueError("Invalid onboarding progress entry")
    tasks = onboarding.setdefault("tasks", {})
    if not isinstance(tasks, dict):
        raise ValueError("Invalid task progress entry")
    tasks[task_id(task)] = {
        "completed": completed,
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    save_task_progress(data, path)


def apply_task_progress(
    onboarding_id: str,
    tasks: list[OnboardingTask],
    path: Path | None = None,
) -> list[OnboardingTask]:
    """Apply saved completion states to generated tasks in place."""
    onboarding = load_task_progress(path).get(onboarding_id, {})
    if not isinstance(onboarding, dict):
        raise ValueError("Invalid onboarding progress entry")
    saved_tasks = onboarding.get("tasks", {})
    if not isinstance(saved_tasks, dict):
        raise ValueError("Invalid task progress entry")
    for task in tasks:
        entry = saved_tasks.get(task_id(task))
        if isinstance(entry, dict) and isinstance(entry.get("completed"), bool):
            task.completed = entry["completed"]
    return tasks


def calculate_task_progress(tasks: list[OnboardingTask]) -> dict[str, int]:
    """Return completed, total, and integer completion percentage."""
    total = len(tasks)
    completed = sum(task.completed for task in tasks)
    return {
        "completed": completed,
        "total": total,
        "percentage": round(completed * 100 / total) if total else 0,
    }
