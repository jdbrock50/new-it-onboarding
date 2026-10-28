"""Read-only filtering helpers for onboarding audit events."""

from datetime import date
from typing import Any


def _parse_filter_date(value: str, label: str) -> date | None:
    """Validate an optional ISO calendar date without changing the event data."""
    value = value.strip()
    if not value:
        return None
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise ValueError(f"{label} must use YYYY-MM-DD format.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid date in YYYY-MM-DD format.") from exc


def _event_date(event: dict[str, Any]) -> date | None:
    """Read the calendar date from an ISO-formatted audit timestamp."""
    timestamp = event.get("timestamp")
    if not isinstance(timestamp, str) or len(timestamp) < 10:
        return None
    try:
        return date.fromisoformat(timestamp[:10])
    except ValueError:
        return None


def filter_audit_events(
    events: list[dict[str, Any]],
    *,
    employee_email: str = "",
    event_type: str = "",
    start_date: str = "",
    end_date: str = "",
) -> list[dict[str, Any]]:
    """Return matching audit events without modifying input records.

    Email searches are case-insensitive partial matches. Event type searches
    are case-insensitive exact matches. Date bounds are inclusive and use
    YYYY-MM-DD; either boundary may be blank. Events with missing or invalid
    timestamps do not match an active date filter. Original order is preserved.

    Raise ValueError for an invalid date or a start date after the end date.
    """
    email_query = employee_email.strip().casefold()
    type_query = event_type.strip().casefold()
    start = _parse_filter_date(start_date, "Start date")
    end = _parse_filter_date(end_date, "End date")
    if start is not None and end is not None and start > end:
        raise ValueError("Start date cannot be after end date.")

    filtered = []
    for event in events:
        if email_query and email_query not in str(event.get("employee_email", "")).casefold():
            continue
        if type_query and type_query != str(event.get("event_type", "")).casefold():
            continue
        if start is not None or end is not None:
            recorded = _event_date(event)
            if recorded is None:
                continue
            if start is not None and recorded < start:
                continue
            if end is not None and recorded > end:
                continue
        filtered.append(event)
    return filtered
