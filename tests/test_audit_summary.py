"""Tests for read-only Shore onboarding audit summaries."""

from copy import deepcopy

from src.audit_summary import summarize_audit_events


def _event(event_type, email="employee@shorecollaborative.org", details=None):
    return {"timestamp": "2026-10-28T12:00:00+00:00", "event_type": event_type,
            "employee_email": email, "details": details if details is not None else {}}


def test_empty_events_have_zero_totals():
    result = summarize_audit_events([])
    assert result == {
        "total_events": 0, "unique_employee_emails": 0, "events_by_type": {},
        "verification_outcomes": {"successful": 0, "incomplete": 0, "unknown": 0},
        "overrides_approved": 0, "overrides_declined": 0,
        "onboardings_created": 0, "onboardings_cancelled": 0,
    }


def test_event_counts_include_each_record():
    events = [_event("onboarding_created"), _event("onboarding_created"),
              _event("onboarding_cancelled")]
    result = summarize_audit_events(events)
    assert result["total_events"] == 3
    assert result["events_by_type"] == {"onboarding_cancelled": 1, "onboarding_created": 2}
    assert result["onboardings_created"] == 2
    assert result["onboardings_cancelled"] == 1


def test_unique_emails_are_case_insensitive_and_ignore_blanks():
    events = [_event("a", "User@shorecollaborative.org"),
              _event("b", " user@shorecollaborative.org "),
              _event("c", "another@shorecollaborative.org"),
              _event("d", " "), _event("e", "")]
    assert summarize_audit_events(events)["unique_employee_emails"] == 2


def test_verification_outcomes_are_counted_from_verification_events_only():
    events = [_event("verification_completed", details={"verification_complete": True}),
              _event("verification_completed", details={"verification_complete": False}),
              _event("verification_completed", details={"verification_complete": True}),
              _event("override_approved", details={"verification_complete": False})]
    assert summarize_audit_events(events)["verification_outcomes"] == {
        "successful": 2, "incomplete": 1, "unknown": 0,
    }


def test_missing_and_nonboolean_verification_flags_are_unknown():
    events = [_event("verification_completed"),
              _event("verification_completed", details={"verification_complete": "true"}),
              _event("verification_completed", details={"verification_complete": 1}),
              {"event_type": "verification_completed", "details": None}]
    assert summarize_audit_events(events)["verification_outcomes"] == {
        "successful": 0, "incomplete": 0, "unknown": 4,
    }


def test_override_counts_are_independent_of_verification_counts():
    events = [_event("override_approved", details={"administrator_name": "Admin"}),
              _event("override_approved"), _event("override_declined")]
    result = summarize_audit_events(events)
    assert result["overrides_approved"] == 2
    assert result["overrides_declined"] == 1
    assert result["verification_outcomes"] == {"successful": 0, "incomplete": 0, "unknown": 0}


def test_missing_event_fields_are_handled():
    result = summarize_audit_events([{}, {"event_type": "", "employee_email": None}])
    assert result["total_events"] == 2
    assert result["events_by_type"] == {"unknown": 2}
    assert result["unique_employee_emails"] == 0


def test_summary_does_not_modify_input_events():
    events = [_event("verification_completed", details={"verification_complete": True}),
              _event("override_approved", details={"reason": "Urgent"})]
    original = deepcopy(events)
    summarize_audit_events(events)
    assert events == original
