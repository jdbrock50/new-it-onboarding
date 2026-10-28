"""Read-only summary reporting for Shore onboarding audit events."""

from collections import Counter
from typing import Any


def summarize_audit_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize recorded events without changing their contents or order.

    Verification outcomes are counted only from verification_completed events.
    Missing or unrecognized verification flags are counted as unknown.
    Each event is counted independently; this is not a count of unique hires.
    """
    event_counts: Counter[str] = Counter()
    unique_emails: set[str] = set()
    verification = {"successful": 0, "incomplete": 0, "unknown": 0}

    for event in events:
        event_type = str(event.get("event_type", "") or "unknown")
        event_counts[event_type] += 1

        email = str(event.get("employee_email", "") or "").strip().casefold()
        if email:
            unique_emails.add(email)

        if event_type == "verification_completed":
            details = event.get("details")
            flag = details.get("verification_complete") if isinstance(details, dict) else None
            if flag is True:
                verification["successful"] += 1
            elif flag is False:
                verification["incomplete"] += 1
            else:
                verification["unknown"] += 1

    return {
        "total_events": len(events),
        "unique_employee_emails": len(unique_emails),
        "events_by_type": dict(sorted(event_counts.items())),
        "verification_outcomes": verification,
        "overrides_approved": event_counts["override_approved"],
        "overrides_declined": event_counts["override_declined"],
        "onboardings_created": event_counts["onboarding_created"],
        "onboardings_cancelled": event_counts["onboarding_cancelled"],
    }
