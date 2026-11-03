"""Tests for date-based onboarding alert priority levels (fake records only)."""

from copy import deepcopy
from datetime import date, timedelta
from unittest.mock import Mock

import pytest

from src import overdue_alerts


TODAY = date(2026, 11, 3)


def _record(offset: int, *, program: str = "Program A", location: str = "CFS", status: str = "Pending") -> dict[str, str]:
    return {
        "onboarding_id": f"fake-{offset}",
        "start_date": (TODAY + timedelta(days=offset)).isoformat(),
        "program": program,
        "location": location,
        "status": status,
    }


def _dashboard(records: list[dict[str, str]], progress_path=None) -> dict:
    return {"rows": [{
        "employee": f"Fake Employee {index}",
        "onboarding_id": record["onboarding_id"],
        "shore_email": "fake@example.invalid",
        "status": record["status"],
        "error": None,
        "total": 10,
        "completed": 2,
        "percentage": 20,
    } for index, record in enumerate(records)]}


@pytest.fixture(autouse=True)
def fake_dashboard(monkeypatch):
    monkeypatch.setattr(overdue_alerts, "build_progress_dashboard", _dashboard)


@pytest.mark.parametrize(("offset", "expected_alert", "expected_priority"), [
    (-30, "Overdue", "Critical"),
    (-7, "Overdue", "Critical"),
    (-6, "Overdue", "High"),
    (-1, "Overdue", "High"),
    (0, "Due Today", "Medium"),
    (1, "Upcoming", "Low"),
    (7, "Upcoming", "Low"),
])
def test_priority_boundaries(offset, expected_alert, expected_priority):
    report = overdue_alerts.build_overdue_alerts([_record(offset)], today=TODAY)
    assert report["alerts"][0]["alert"] == expected_alert
    assert report["alerts"][0]["priority"] == expected_priority
    assert report["priority_counts"][expected_priority] == 1


def test_priority_summary_counts_all_levels():
    records = [_record(-8), _record(-2), _record(0), _record(4)]
    report = overdue_alerts.build_overdue_alerts(records, today=TODAY)
    assert report["priority_counts"] == {"Critical": 1, "High": 1, "Medium": 1, "Low": 1}
    assert report["counts"] == {"Overdue": 2, "Due Today": 1, "Upcoming": 1}


def test_no_alerts_has_zero_priority_counts():
    report = overdue_alerts.build_overdue_alerts([_record(8)], today=TODAY)
    assert report["total_alerts"] == 0
    assert report["priority_counts"] == {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}


def test_program_and_location_filters_apply_to_priorities():
    records = [_record(-8, program="A", location="CFS"), _record(-2, program="B", location="CFS"), _record(0, program="A", location="Cambridge")]
    report = overdue_alerts.build_overdue_alerts(records, today=TODAY, program=" a ", location="cfs")
    assert report["total_alerts"] == 1
    assert report["priority_counts"] == {"Critical": 1, "High": 0, "Medium": 0, "Low": 0}


def test_cancelled_and_completed_checklists_do_not_count(monkeypatch):
    records = [_record(-8, status="Cancelled"), _record(-2)]
    def dashboard(records, progress_path=None):
        result = _dashboard(records, progress_path)
        result["rows"][1]["completed"] = 10
        return result
    monkeypatch.setattr(overdue_alerts, "build_progress_dashboard", dashboard)
    report = overdue_alerts.build_overdue_alerts(records, today=TODAY)
    assert report["total_alerts"] == 0
    assert sum(report["priority_counts"].values()) == 0


def test_priority_calculation_does_not_mutate_records():
    records = [_record(-7), _record(1)]
    before = deepcopy(records)
    overdue_alerts.build_overdue_alerts(records, today=TODAY)
    assert records == before


def test_upcoming_window_excludes_outside_dates():
    report = overdue_alerts.build_overdue_alerts([_record(3), _record(4)], today=TODAY, upcoming_days=3)
    assert report["total_alerts"] == 1
    assert report["priority_counts"]["Low"] == 1
