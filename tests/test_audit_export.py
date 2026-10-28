"""Tests for read-only CSV audit report exports."""

import csv
import json
from copy import deepcopy
from pathlib import Path

from src.audit_export import export_audit_events_csv, export_audit_summary_csv


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read an exported CSV, including its UTF-8 BOM if present."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def test_event_export_creates_file_and_returns_path(tmp_path):
    destination = tmp_path / "reports" / "events.csv"
    assert export_audit_events_csv([], destination) == destination
    assert destination.is_file()


def test_event_export_has_expected_columns_when_empty(tmp_path):
    destination = tmp_path / "events.csv"
    export_audit_events_csv([], destination)
    with destination.open(encoding="utf-8-sig", newline="") as stream:
        assert next(csv.reader(stream)) == [
            "timestamp", "event_type", "employee_email", "details"
        ]
    assert read_csv(destination) == []


def test_event_export_preserves_order_and_values(tmp_path):
    events = [
        {"timestamp": "2026-10-28T09:00:00+00:00", "event_type": "verification_completed",
         "employee_email": "jdoe@example.com", "details": {"verification_complete": True}},
        {"timestamp": "2026-10-28T09:01:00+00:00", "event_type": "onboarding_created",
         "employee_email": "asmith@example.com", "details": {"checklist_path": "sample.txt"}},
    ]
    destination = tmp_path / "events.csv"
    export_audit_events_csv(events, destination)
    rows = read_csv(destination)
    assert [row["event_type"] for row in rows] == [
        "verification_completed", "onboarding_created"
    ]
    assert [row["employee_email"] for row in rows] == [
        "jdoe@example.com", "asmith@example.com"
    ]
    assert rows[0]["timestamp"] == "2026-10-28T09:00:00+00:00"
    assert json.loads(rows[0]["details"]) == {"verification_complete": True}


def test_event_export_serializes_nested_details_and_unicode(tmp_path):
    events = [{"event_type": "override_approved", "employee_email": "test@example.com",
               "details": {"administrator_name": "José", "reasons": ["review", "approved"]}}]
    destination = tmp_path / "events.csv"
    export_audit_events_csv(events, destination)
    assert json.loads(read_csv(destination)[0]["details"]) == events[0]["details"]


def test_event_export_defaults_missing_fields(tmp_path):
    destination = tmp_path / "events.csv"
    export_audit_events_csv([{}], destination)
    assert read_csv(destination) == [{
        "timestamp": "", "event_type": "", "employee_email": "", "details": "{}"
    }]


def test_event_export_does_not_mutate_input(tmp_path):
    events = [{"event_type": "verification_completed", "details": {"ok": True}}]
    original = deepcopy(events)
    export_audit_events_csv(events, tmp_path / "events.csv")
    assert events == original


def test_summary_export_creates_file_and_returns_path(tmp_path):
    destination = tmp_path / "reports" / "summary.csv"
    assert export_audit_summary_csv({}, destination) == destination
    assert destination.is_file()


def test_summary_export_has_expected_columns_when_empty(tmp_path):
    destination = tmp_path / "summary.csv"
    export_audit_summary_csv({}, destination)
    with destination.open(encoding="utf-8-sig", newline="") as stream:
        assert next(csv.reader(stream)) == ["metric", "category", "value"]
    assert read_csv(destination) == []


def test_summary_export_flattens_scalar_and_category_counts(tmp_path):
    summary = {
        "total_events": 3,
        "unique_employee_emails": 2,
        "events_by_type": {"onboarding_created": 1, "verification_completed": 2},
        "verification_outcomes": {"successful": 2, "incomplete": 0},
        "overrides_approved": 0,
    }
    destination = tmp_path / "summary.csv"
    export_audit_summary_csv(summary, destination)
    assert read_csv(destination) == [
        {"metric": "total_events", "category": "", "value": "3"},
        {"metric": "unique_employee_emails", "category": "", "value": "2"},
        {"metric": "events_by_type", "category": "onboarding_created", "value": "1"},
        {"metric": "events_by_type", "category": "verification_completed", "value": "2"},
        {"metric": "verification_outcomes", "category": "successful", "value": "2"},
        {"metric": "verification_outcomes", "category": "incomplete", "value": "0"},
        {"metric": "overrides_approved", "category": "", "value": "0"},
    ]


def test_summary_export_does_not_mutate_input(tmp_path):
    summary = {"total_events": 1, "events_by_type": {"onboarding_created": 1}}
    original = deepcopy(summary)
    export_audit_summary_csv(summary, tmp_path / "summary.csv")
    assert summary == original
