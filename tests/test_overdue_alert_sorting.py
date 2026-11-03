"""Phase 3C sorting and filtering tests using synthetic records only."""
from copy import deepcopy
from datetime import date, timedelta

import pytest

from src import overdue_alerts

TODAY = date(2026, 11, 3)


def _record(ident, offset, program="A", location="CFS"):
    return {"onboarding_id": ident, "start_date": (TODAY + timedelta(days=offset)).isoformat(),
            "program": program, "location": location, "status": "Pending"}


def _dashboard(records, progress_path=None):
    return {"rows": [{"employee": record["onboarding_id"],
                      "onboarding_id": record["onboarding_id"],
                      "shore_email": "fake@example.invalid", "status": "Pending",
                      "error": None, "total": 5, "completed": 1, "percentage": 20}
                     for record in records]}


@pytest.fixture(autouse=True)
def fake_dashboard(monkeypatch):
    monkeypatch.setattr(overdue_alerts, "build_progress_dashboard", _dashboard)


def test_priority_sort_and_oldest_first():
    records = [_record("low", 3), _record("high", -2), _record("critical-new", -7),
               _record("medium", 0), _record("critical-old", -30), _record("high-old", -6)]
    result = overdue_alerts.build_overdue_alerts(records, today=TODAY)
    assert [item["onboarding_id"] for item in result["alerts"]] == [
        "critical-old", "critical-new", "high-old", "high", "medium", "low"]


@pytest.mark.parametrize("selected,expected", [
    ("critical", "Critical"), (" HIGH ", "High"), ("Medium", "Medium"), ("low", "Low")])
def test_filter_priority_case_insensitive(selected, expected):
    records = [_record("critical", -8), _record("high", -2),
               _record("medium", 0), _record("low", 2)]
    result = overdue_alerts.build_overdue_alerts(records, today=TODAY, priority=selected)
    assert result["total_alerts"] == 1
    assert result["alerts"][0]["priority"] == expected
    assert result["priority_counts"][expected] == 1
    assert sum(result["priority_counts"].values()) == 1
    assert sum(result["counts"].values()) == 1


def test_all_and_blank_priority_match_unfiltered():
    records = [_record("critical", -8), _record("low", 1)]
    results = [overdue_alerts.build_overdue_alerts(records, today=TODAY, priority=value)
               for value in (None, "", "  ", "all", " ALL ")]
    assert all(result["total_alerts"] == 2 for result in results)


def test_combined_filters_and_empty_summary():
    records = [_record("one", -8, "Adult", "Peabody"),
               _record("two", -2, "Adult", "Peabody"),
               _record("three", -8, "Other", "Peabody")]
    result = overdue_alerts.build_overdue_alerts(
        records, today=TODAY, program=" adult ", location="peabody", priority="High")
    assert [a["onboarding_id"] for a in result["alerts"]] == ["two"]
    empty = overdue_alerts.build_overdue_alerts(records, today=TODAY, priority="Low")
    assert empty["total_alerts"] == 0
    assert sum(empty["counts"].values()) == 0
    assert sum(empty["priority_counts"].values()) == 0


def test_invalid_priority_rejected():
    with pytest.raises(ValueError, match="priority"):
        overdue_alerts.build_overdue_alerts([], today=TODAY, priority="urgent")


def test_sort_and_filter_does_not_mutate_records():
    records = [_record("one", -8), _record("two", 2)]
    before = deepcopy(records)
    overdue_alerts.build_overdue_alerts(records, today=TODAY, priority="Critical")
    assert records == before
