"""Tests for read-only onboarding audit event filtering."""

from copy import deepcopy

import pytest

from src.audit_filters import filter_audit_events


def sample_events():
    """Return representative audit events in recorded order."""
    return [
        {"employee_email": "jsmith@shorecollaborative.org", "event_type": "verification_completed", "details": {"verified": True}},
        {"employee_email": "adoe@shorecollaborative.org", "event_type": "override_approved", "details": {"reason": "urgent"}},
        {"employee_email": "JSMITH@shorecollaborative.org", "event_type": "onboarding_created", "details": {}},
    ]


def dated_events():
    """Return dated records, including one without a timestamp."""
    return [
        {"timestamp": "2026-09-30T23:59:59Z", "employee_email": "jsmith@shorecollaborative.org", "event_type": "override_approved"},
        {"timestamp": "2026-10-01T00:00:00Z", "employee_email": "jsmith@shorecollaborative.org", "event_type": "override_approved"},
        {"timestamp": "2026-10-15T12:30:00+00:00", "employee_email": "adoe@shorecollaborative.org", "event_type": "onboarding_created"},
        {"timestamp": "2026-10-31T23:59:59Z", "employee_email": "JSMITH@shorecollaborative.org", "event_type": "override_approved"},
        {"timestamp": "2026-11-01T00:00:00Z", "employee_email": "jsmith@shorecollaborative.org", "event_type": "override_approved"},
        {"employee_email": "jsmith@shorecollaborative.org", "event_type": "override_approved"},
    ]


def test_blank_filters_return_all_events_in_original_order():
    events = sample_events()
    assert filter_audit_events(events) == events


def test_email_partial_match_is_case_insensitive():
    events = sample_events()
    result = filter_audit_events(events, employee_email=" SMITH ")
    assert result == [events[0], events[2]]


def test_event_type_match_is_case_insensitive_and_exact():
    events = sample_events()
    assert filter_audit_events(events, event_type=" OVERRIDE_APPROVED ") == [events[1]]
    assert filter_audit_events(events, event_type="override") == []


def test_combined_filters_require_both_to_match():
    events = sample_events()
    assert filter_audit_events(events, employee_email="smith", event_type="onboarding_created") == [events[2]]
    assert filter_audit_events(events, employee_email="doe", event_type="onboarding_created") == []


def test_missing_fields_do_not_crash_filtering():
    events = [{}, {"employee_email": "test@shorecollaborative.org"}, {"event_type": "override_declined"}]
    assert filter_audit_events(events, employee_email="test") == [events[1]]
    assert filter_audit_events(events, event_type="override_declined") == [events[2]]


def test_filtering_does_not_modify_source_events():
    events = sample_events()
    original = deepcopy(events)
    filter_audit_events(events, employee_email="smith", event_type="onboarding_created")
    assert events == original


def test_date_range_includes_both_boundaries():
    events = dated_events()
    assert filter_audit_events(events, start_date="2026-10-01", end_date="2026-10-31") == events[1:4]


def test_start_date_only_and_end_date_only():
    events = dated_events()
    assert filter_audit_events(events, start_date="2026-10-31") == events[3:5]
    assert filter_audit_events(events, end_date="2026-10-01") == events[:2]


def test_same_day_date_range():
    events = dated_events()
    assert filter_audit_events(events, start_date="2026-10-15", end_date="2026-10-15") == [events[2]]


@pytest.mark.parametrize("bad_date", ["2026/10/01", "2026-02-30", "2026-1-01", "not-a-date"])
def test_invalid_start_date_is_rejected(bad_date):
    with pytest.raises(ValueError, match="Start date"):
        filter_audit_events(dated_events(), start_date=bad_date)


def test_invalid_end_date_is_rejected():
    with pytest.raises(ValueError, match="End date"):
        filter_audit_events(dated_events(), end_date="2026-13-01")


def test_reversed_date_range_is_rejected():
    with pytest.raises(ValueError, match="Start date cannot be after end date"):
        filter_audit_events(dated_events(), start_date="2026-11-01", end_date="2026-10-01")


def test_combined_email_event_and_date_filters():
    events = dated_events()
    assert filter_audit_events(
        events,
        employee_email="SMITH",
        event_type="OVERRIDE_APPROVED",
        start_date="2026-10-01",
        end_date="2026-10-31",
    ) == [events[1], events[3]]


def test_missing_or_invalid_timestamps_are_excluded_only_when_dates_active():
    events = dated_events() + [{"timestamp": "invalid", "employee_email": "x"}]
    assert filter_audit_events(events) == events
    assert filter_audit_events(events, start_date="2026-01-01") == events[:5]


def test_date_filter_preserves_source_events_and_order():
    events = dated_events()
    original = deepcopy(events)
    assert filter_audit_events(events, start_date="2026-10-01", end_date="2026-10-31") == events[1:4]
    assert events == original
