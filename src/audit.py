
"""Append-only audit logging for employee onboarding."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path("data")
AUDIT_FILE = DATA_DIR / "onboarding_audit.jsonl"


class AuditWriteError(RuntimeError):
    """Raised when an onboarding audit event cannot be saved."""


def current_timestamp() -> str:
    """Return the current UTC timestamp."""

    return datetime.now(UTC).isoformat(timespec="seconds")


def record_audit_event(
    event_type: str,
    *,
    employee_email: str,
    details: dict[str, Any] | None = None,
) -> Path:
    """Append one structured onboarding audit event.

    Raise AuditWriteError if the event cannot be written.
    """

    event = {
        "timestamp": current_timestamp(),
        "event_type": event_type,
        "employee_email": employee_email,
        "details": details or {},
    }

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        with AUDIT_FILE.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    event,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
            file.flush()
            os.fsync(file.fileno())

    except (OSError, TypeError, ValueError) as exc:
        raise AuditWriteError(
            "Unable to save onboarding audit event."
        ) from exc

    return AUDIT_FILE


def load_audit_events() -> list[dict[str, Any]]:
    """Read previously recorded onboarding audit events."""

    if not AUDIT_FILE.exists():
        return []

    events = []

    with AUDIT_FILE.open(
        encoding="utf-8",
    ) as file:
        for line in file:
            if line.strip():
                events.append(json.loads(line))

    return events
